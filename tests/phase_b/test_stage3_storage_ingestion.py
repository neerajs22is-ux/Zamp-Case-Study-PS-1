"""Phase B Stage 3 Acceptance Tests — Supabase Storage & Document Ingestion.

Comprehensive validation of the 15 binding storage and ingestion requirements:
Test 01: Valid PDF upload succeeds, stores tenant-scoped file, records DB rows.
Test 02: Invalid MIME type rejected (HTTP 400).
Test 03: Invalid PDF magic-byte rejected (HTTP 400).
Test 04: File size limit enforcement (> 50 MB rejected with HTTP 400).
Test 05: SHA-256 calculation and persistence verified.
Test 06: Duplicate detection within tenant returns DUPLICATE_DETECTED (HTTP 409).
Test 07: Tenant-scoped object path generation (org_{org_id}/invoices/{document_id}/{filename}).
Test 08: Cross-tenant download rejection (HTTP 403).
Test 09: Cross-tenant signed URL rejection (HTTP 403).
Test 10: Failed upload handling (storage adapter error fails cleanly with HTTP 503).
Test 11: Database failure after Storage upload triggers compensating cleanup (orphaned object removed).
Test 12: Soft deletion sets is_deleted=True while physical file in storage is preserved.
Test 13: Audit event generation on upload, soft-delete, and purge.
Test 14: Storage health-check accuracy (NOT_CONFIGURED, CONNECTED, DEGRADED, BLOCKED).
Test 15: Live Supabase integration truthful state (no fake connected state when unconfigured).
"""

from __future__ import annotations

import datetime
import hashlib
import io
from typing import Any, Dict, Optional
from unittest.mock import MagicMock, patch

from fastapi import status
from fastapi.testclient import TestClient
from jose import jwt
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from backend.core.config import AppEnv, settings
from backend.core.database import Base, get_db
from backend.core.storage import (
    SupabaseStorageAdapter, TestInMemoryStorageAdapter,
    build_tenant_storage_path, storage_adapter
)
from backend.main import app
from backend.models.domain import (
    AuditEvent, Document, IngestionJob, Invoice, Organisation, RoleAssignment, User
)

TEST_JWT_SECRET = "stage3-storage-test-secret-32-chars-long"
TEST_ISSUER = "https://test-project.supabase.co/auth/v1"
TEST_AUDIENCE = "authenticated"


@pytest.fixture(autouse=True)
def configure_stage3_settings():
    """Configures storage & auth settings for Stage 3 acceptance tests."""
    orig_env = settings.APP_ENV
    orig_secret = settings.SUPABASE_JWT_SECRET
    orig_iss = settings.SUPABASE_ISSUER
    orig_aud = settings.SUPABASE_AUDIENCE
    orig_max_size = settings.MAX_UPLOAD_FILE_SIZE_BYTES

    settings.APP_ENV = AppEnv.TEST
    settings.SUPABASE_JWT_SECRET = TEST_JWT_SECRET
    settings.SUPABASE_ISSUER = TEST_ISSUER
    settings.SUPABASE_AUDIENCE = TEST_AUDIENCE

    yield

    settings.APP_ENV = orig_env
    settings.SUPABASE_JWT_SECRET = orig_secret
    settings.SUPABASE_ISSUER = orig_iss
    settings.SUPABASE_AUDIENCE = orig_aud
    settings.MAX_UPLOAD_FILE_SIZE_BYTES = orig_max_size


@pytest.fixture
def stage3_db():
    """Provides a fresh, isolated in-memory SQLite database for each acceptance test."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)

    with engine.connect() as conn:
        conn.exec_driver_sql("""
            CREATE TRIGGER IF NOT EXISTS trg_audit_events_no_update
            BEFORE UPDATE ON audit_events
            BEGIN
                SELECT RAISE(ABORT, 'audit_events is strictly append-only: UPDATE operations are prohibited.');
            END;
        """)
        conn.exec_driver_sql("""
            CREATE TRIGGER IF NOT EXISTS trg_audit_events_no_delete
            BEFORE DELETE ON audit_events
            BEGIN
                SELECT RAISE(ABORT, 'audit_events is strictly append-only: DELETE operations are prohibited.');
            END;
        """)
        conn.commit()

    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = SessionLocal()

    yield session, engine

    session.close()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture
def stage3_client(stage3_db):
    """FastAPI TestClient with isolated database session override."""
    session, _ = stage3_db

    def override_get_db():
        try:
            yield session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as client:
        yield client, session
    app.dependency_overrides.clear()


def make_jwt(sub: str, email: str, expires_in_seconds: int = 3600) -> str:
    """Helper to generate valid RFC-compliant JWT for authenticated test calls."""
    now = datetime.datetime.now(datetime.timezone.utc)
    exp = now + datetime.timedelta(seconds=expires_in_seconds)
    payload = {
        "sub": sub,
        "email": email,
        "name": "Test User",
        "aud": TEST_AUDIENCE,
        "iss": TEST_ISSUER,
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
    }
    return jwt.encode(payload, TEST_JWT_SECRET, algorithm="HS256")


def seed_tenant_user(
    session: Session,
    org_id: str = "org_alpha",
    user_id: str = "usr_01",
    email: str = "alice@alpha.internal",
    role_name: str = "AP_ASSOCIATE",
) -> str:
    """Seeds an organisation, active user and role assignment; returns valid JWT."""
    existing_org = session.execute(select(Organisation).where(Organisation.id == org_id)).scalar_one_or_none()
    if not existing_org:
        session.add(Organisation(id=org_id, name=f"Organisation {org_id}"))

    user = User(
        id=user_id,
        org_id=org_id,
        email=email,
        full_name=f"User {user_id}",
        is_active=True,
    )
    role = RoleAssignment(
        id=f"ra_{user_id}",
        org_id=org_id,
        user_id=user_id,
        role_name=role_name,
    )
    session.add_all([user, role])
    session.commit()
    return make_jwt(sub=user_id, email=email)


SAMPLE_VALID_PDF = b"%PDF-1.4\n1 0 obj\n<< /Title (Invoice 101) >>\nendobj\ntrailer\n<< /Root 1 0 R >>\n%%EOF"


# ==============================================================================
# 15 Acceptance Tests
# ==============================================================================

def test_01_valid_pdf_upload_succeeds_and_creates_records(stage3_client):
    """Test 1: Valid PDF upload succeeds, stores tenant-scoped file, records DB rows."""
    client, session = stage3_client
    token = seed_tenant_user(session, org_id="org_alpha", user_id="usr_01", email="alice@alpha.internal")

    files = {"file": ("vendor_invoice.pdf", io.BytesIO(SAMPLE_VALID_PDF), "application/pdf")}
    resp = client.post("/api/v1/documents/upload", files=files, headers={"Authorization": f"Bearer {token}"})

    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()
    assert data["status"] == "QUEUED"
    assert data["filename"] == "vendor_invoice.pdf"
    assert data["sha256"] == hashlib.sha256(SAMPLE_VALID_PDF).hexdigest()
    assert data["size_bytes"] == len(SAMPLE_VALID_PDF)
    assert data["storage_key"].startswith("org_alpha/invoices/")
    assert data["storage_key"].endswith("vendor_invoice.pdf")

    # Verify DB records
    doc = session.execute(select(Document).where(Document.id == data["document_id"])).scalar_one()
    assert doc.org_id == "org_alpha"
    assert doc.filename == "vendor_invoice.pdf"
    assert doc.file_size_bytes == len(SAMPLE_VALID_PDF)
    assert doc.sha256_hash == hashlib.sha256(SAMPLE_VALID_PDF).hexdigest()
    assert doc.is_deleted is False

    inv = session.execute(select(Invoice).where(Invoice.id == data["invoice_id"])).scalar_one()
    assert inv.org_id == "org_alpha"
    assert inv.stage == "RECEIVED"
    assert inv.owner_user_id == "usr_01"

    job = session.execute(select(IngestionJob).where(IngestionJob.org_id == "org_alpha")).scalar_one()
    assert job.status == "QUEUED"

    audit = session.execute(select(AuditEvent).where(AuditEvent.invoice_id == data["invoice_id"])).scalar_one()
    assert audit.action == "DOCUMENT_UPLOADED"
    assert audit.actor_id == "usr_01"


def test_02_invalid_mime_type_rejected(stage3_client):
    """Test 2: Invalid MIME type or extension is rejected with HTTP 400."""
    client, session = stage3_client
    token = seed_tenant_user(session, org_id="org_alpha", user_id="usr_02", email="bob@alpha.internal")

    files = {"file": ("invoice.exe", io.BytesIO(b"MZ\x90\x00\x03"), "application/octet-stream")}
    resp = client.post("/api/v1/documents/upload", files=files, headers={"Authorization": f"Bearer {token}"})

    assert resp.status_code == status.HTTP_400_BAD_REQUEST
    assert "Only PDF documents are supported" in resp.json()["detail"]


def test_03_invalid_pdf_magic_byte_rejected(stage3_client):
    """Test 3: File with .pdf name but missing %PDF- magic bytes header is rejected."""
    client, session = stage3_client
    token = seed_tenant_user(session, org_id="org_alpha", user_id="usr_03", email="carol@alpha.internal")

    corrupt_content = b"THIS IS NOT A VALID PDF FILE AT ALL"
    files = {"file": ("corrupt.pdf", io.BytesIO(corrupt_content), "application/pdf")}
    resp = client.post("/api/v1/documents/upload", files=files, headers={"Authorization": f"Bearer {token}"})

    assert resp.status_code == status.HTTP_400_BAD_REQUEST
    assert "Invalid PDF header signature" in resp.json()["detail"]


def test_04_file_size_limit_enforcement(stage3_client):
    """Test 4: File exceeding maximum permitted size is rejected with HTTP 400."""
    client, session = stage3_client
    token = seed_tenant_user(session, org_id="org_alpha", user_id="usr_04", email="dave@alpha.internal")

    # Temporarily set max size to 50 bytes for test
    orig_max = settings.MAX_UPLOAD_FILE_SIZE_BYTES
    settings.MAX_UPLOAD_FILE_SIZE_BYTES = 50
    try:
        files = {"file": ("large_invoice.pdf", io.BytesIO(SAMPLE_VALID_PDF), "application/pdf")}
        resp = client.post("/api/v1/documents/upload", files=files, headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == status.HTTP_400_BAD_REQUEST
        assert "exceeds maximum permitted size" in resp.json()["detail"]
    finally:
        settings.MAX_UPLOAD_FILE_SIZE_BYTES = orig_max


def test_05_sha256_calculation_and_persistence_verified(stage3_client):
    """Test 5: Cryptographic SHA-256 calculation matches original file bytes."""
    client, session = stage3_client
    token = seed_tenant_user(session, org_id="org_alpha", user_id="usr_05", email="eve@alpha.internal")

    content = b"%PDF-1.7\nUnique content payload\xaa\xbb\xcc\xdd\n%%EOF"
    expected_hash = hashlib.sha256(content).hexdigest()

    files = {"file": ("crypto_test.pdf", io.BytesIO(content), "application/pdf")}
    resp = client.post("/api/v1/documents/upload", files=files, headers={"Authorization": f"Bearer {token}"})

    assert resp.status_code == status.HTTP_200_OK
    assert resp.json()["sha256"] == expected_hash

    doc = session.execute(select(Document).where(Document.id == resp.json()["document_id"])).scalar_one()
    assert doc.sha256_hash == expected_hash


def test_06_duplicate_detection_within_tenant(stage3_client):
    """Test 6: Duplicate detection within same tenant returns DUPLICATE_DETECTED (HTTP 409)."""
    client, session = stage3_client
    token = seed_tenant_user(session, org_id="org_alpha", user_id="usr_06", email="frank@alpha.internal")

    files1 = {"file": ("dup_check.pdf", io.BytesIO(SAMPLE_VALID_PDF), "application/pdf")}
    resp1 = client.post("/api/v1/documents/upload", files=files1, headers={"Authorization": f"Bearer {token}"})
    assert resp1.status_code == status.HTTP_200_OK

    # Second upload of identical file within same tenant
    files2 = {"file": ("dup_check_copy.pdf", io.BytesIO(SAMPLE_VALID_PDF), "application/pdf")}
    resp2 = client.post("/api/v1/documents/upload", files=files2, headers={"Authorization": f"Bearer {token}"})

    assert resp2.status_code == status.HTTP_409_CONFLICT
    assert resp2.json()["status"] == "DUPLICATE_DETECTED"
    assert resp2.json()["document_id"] == resp1.json()["document_id"]


def test_07_tenant_scoped_object_path_generation():
    """Test 7: Tenant-scoped object path generation follows org_{org_id}/invoices/{document_id}/{filename}."""
    path1 = build_tenant_storage_path("org_tenant_1", "doc_101", "invoice 2026.pdf")
    assert path1 == "org_tenant_1/invoices/doc_101/invoice_2026.pdf"

    path2 = build_tenant_storage_path("tenant_2", "doc_102", "receipt.pdf")
    assert path2 == "org_tenant_2/invoices/doc_102/receipt.pdf"

    path3 = build_tenant_storage_path("org_acme", "doc_103", "../../etc/passwd.pdf")
    assert path3 == "org_acme/invoices/doc_103/passwd.pdf"


def test_08_cross_tenant_download_rejection(stage3_client):
    """Test 8: Cross-tenant download is strictly rejected with HTTP 403 Forbidden."""
    client, session = stage3_client
    token_a = seed_tenant_user(session, org_id="org_alpha", user_id="usr_a", email="alice@alpha.internal")
    token_b = seed_tenant_user(session, org_id="org_beta", user_id="usr_b", email="bob@beta.internal")

    # Upload under tenant Alpha
    files = {"file": ("alpha_secret.pdf", io.BytesIO(SAMPLE_VALID_PDF), "application/pdf")}
    up_resp = client.post("/api/v1/documents/upload", files=files, headers={"Authorization": f"Bearer {token_a}"})
    doc_id = up_resp.json()["document_id"]

    # Tenant Beta attempts download
    resp = client.get(f"/api/v1/documents/{doc_id}/download", headers={"Authorization": f"Bearer {token_b}"})
    assert resp.status_code == status.HTTP_403_FORBIDDEN
    assert "Cross-tenant document access is prohibited" in resp.json()["detail"]


def test_09_cross_tenant_signed_url_rejection(stage3_client):
    """Test 9: Cross-tenant presigned URL generation is rejected with HTTP 403 Forbidden."""
    client, session = stage3_client
    token_a = seed_tenant_user(session, org_id="org_alpha", user_id="usr_a2", email="alice2@alpha.internal")
    token_b = seed_tenant_user(session, org_id="org_beta", user_id="usr_b2", email="bob2@beta.internal")

    # Upload under Alpha
    files = {"file": ("alpha_doc.pdf", io.BytesIO(SAMPLE_VALID_PDF), "application/pdf")}
    up_resp = client.post("/api/v1/documents/upload", files=files, headers={"Authorization": f"Bearer {token_a}"})
    doc_id = up_resp.json()["document_id"]

    # Tenant Beta attempts to get presigned URL
    resp = client.get(f"/api/v1/documents/{doc_id}/signed-url", headers={"Authorization": f"Bearer {token_b}"})
    assert resp.status_code == status.HTTP_403_FORBIDDEN
    assert "Cross-tenant document access is prohibited" in resp.json()["detail"]


def test_10_failed_upload_handling(stage3_client):
    """Test 10: Storage adapter failure returns clean HTTP 503 Service Unavailable."""
    client, session = stage3_client
    token = seed_tenant_user(session, org_id="org_alpha", user_id="usr_10", email="fail@alpha.internal")

    with patch.object(storage_adapter, "save_file", side_effect=Exception("Storage network timeout")):
        files = {"file": ("fail.pdf", io.BytesIO(SAMPLE_VALID_PDF), "application/pdf")}
        resp = client.post("/api/v1/documents/upload", files=files, headers={"Authorization": f"Bearer {token}"})

        assert resp.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        assert "Secure storage failed" in resp.json()["detail"]

    # Verify no dangling document in DB
    docs = session.execute(select(Document).where(Document.filename == "fail.pdf")).scalars().all()
    assert len(docs) == 0


def test_11_database_failure_triggers_compensating_cleanup(stage3_client):
    """Test 11: Database failure after Storage upload triggers compensating cleanup (orphaned object deleted)."""
    client, session = stage3_client
    token = seed_tenant_user(session, org_id="org_alpha", user_id="usr_11", email="cleanup@alpha.internal")

    deleted_keys = []
    original_delete = storage_adapter.delete_file

    def mock_delete(key: str) -> bool:
        deleted_keys.append(key)
        return original_delete(key)

    with patch.object(storage_adapter, "delete_file", side_effect=mock_delete):
        # Force DB commit failure
        with patch.object(session, "commit", side_effect=Exception("Simulated SQLite write deadlock")):
            files = {"file": ("cleanup_test.pdf", io.BytesIO(SAMPLE_VALID_PDF), "application/pdf")}
            resp = client.post("/api/v1/documents/upload", files=files, headers={"Authorization": f"Bearer {token}"})

            assert resp.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
            assert "Database transaction failure" in resp.json()["detail"]

    # Assert compensating delete_file was called for the uploaded object
    assert len(deleted_keys) == 1
    assert deleted_keys[0].startswith("org_alpha/invoices/")
    assert deleted_keys[0].endswith("cleanup_test.pdf")


def test_12_soft_deletion_preserves_physical_file(stage3_client):
    """Test 12: Soft deletion sets is_deleted=True while physical file in storage is preserved."""
    client, session = stage3_client
    token = seed_tenant_user(session, org_id="org_alpha", user_id="usr_12", email="softdel@alpha.internal")

    # 1. Upload
    files = {"file": ("preserve_me.pdf", io.BytesIO(SAMPLE_VALID_PDF), "application/pdf")}
    up_resp = client.post("/api/v1/documents/upload", files=files, headers={"Authorization": f"Bearer {token}"})
    doc_id = up_resp.json()["document_id"]
    storage_key = up_resp.json()["storage_key"]

    # 2. Soft Delete
    del_resp = client.delete(f"/api/v1/documents/{doc_id}?reason=Retention+policy+test", headers={"Authorization": f"Bearer {token}"})
    assert del_resp.status_code == status.HTTP_200_OK
    assert del_resp.json()["status"] == "SOFT_DELETED"
    assert del_resp.json()["is_deleted"] is True

    # 3. DB row marked deleted
    doc = session.execute(select(Document).where(Document.id == doc_id)).scalar_one()
    assert doc.is_deleted is True
    assert doc.deleted_at is not None
    assert doc.deleted_by_user_id == "usr_12"

    # 4. Physical file in storage is STILL PRESERVED!
    file_bytes = storage_adapter.get_file(storage_key)
    assert file_bytes == SAMPLE_VALID_PDF

    # 5. Metadata endpoint returns 404 for soft-deleted doc
    get_resp = client.get(f"/api/v1/documents/{doc_id}", headers={"Authorization": f"Bearer {token}"})
    assert get_resp.status_code == status.HTTP_404_NOT_FOUND


def test_13_audit_event_generation_on_upload_soft_delete_and_purge(stage3_client):
    """Test 13: Audit events generated for upload, soft-delete, and dual-control permanent purge."""
    client, session = stage3_client
    token1 = seed_tenant_user(
        session, org_id="org_alpha", user_id="usr_admin1", email="controller@alpha.internal", role_name="CONTROLLER"
    )
    token2 = seed_tenant_user(
        session, org_id="org_alpha", user_id="usr_admin2", email="sysadmin@alpha.internal", role_name="SYSTEM_ADMIN"
    )

    # 1. Upload
    files = {"file": ("audit_doc.pdf", io.BytesIO(SAMPLE_VALID_PDF), "application/pdf")}
    up_resp = client.post("/api/v1/documents/upload", files=files, headers={"Authorization": f"Bearer {token1}"})
    doc_id = up_resp.json()["document_id"]
    inv_id = up_resp.json()["invoice_id"]

    ev_upload = session.execute(
        select(AuditEvent).where(AuditEvent.invoice_id == inv_id, AuditEvent.action == "DOCUMENT_UPLOADED")
    ).scalar_one()
    assert ev_upload.actor_id == "usr_admin1"

    # 2. Permanent Purge before soft-delete is rejected
    purge_before_del = client.post(f"/api/v1/documents/{doc_id}/purge", headers={"Authorization": f"Bearer {token1}"})
    assert purge_before_del.status_code == status.HTTP_400_BAD_REQUEST
    assert "must be soft-deleted" in purge_before_del.json()["detail"]

    # 3. Soft Delete
    client.delete(f"/api/v1/documents/{doc_id}", headers={"Authorization": f"Bearer {token1}"})
    ev_del = session.execute(
        select(AuditEvent).where(AuditEvent.invoice_id == inv_id, AuditEvent.action == "DOCUMENT_SOFT_DELETED")
    ).scalar_one()
    assert ev_del.actor_id == "usr_admin1"

    # 4. Permanent purge when unconfigured returns honest BLOCKED response
    blocked_resp = client.post(f"/api/v1/documents/{doc_id}/purge", headers={"Authorization": f"Bearer {token1}"})
    assert blocked_resp.status_code == status.HTTP_409_CONFLICT
    assert blocked_resp.json()["status"] == "BLOCKED"

    # 5. Enable purge policy and verify retention enforcement
    orig_purge_enable = settings.ENABLE_PERMANENT_PURGE
    orig_retention_days = settings.DOCUMENT_RETENTION_DAYS
    try:
        settings.ENABLE_PERMANENT_PURGE = True
        settings.DOCUMENT_RETENTION_DAYS = 365  # Document deleted 0 days ago

        retention_blocked = client.post(f"/api/v1/documents/{doc_id}/purge", headers={"Authorization": f"Bearer {token1}"})
        assert retention_blocked.status_code == status.HTTP_409_CONFLICT
        assert retention_blocked.json()["status"] == "BLOCKED"
        assert retention_blocked.json()["retention_eligible"] is False

        # Set retention days to 0 to simulate retention expiration
        settings.DOCUMENT_RETENTION_DAYS = 0

        # 6. First Approver initiates purge
        p1_resp = client.post(f"/api/v1/documents/{doc_id}/purge", headers={"Authorization": f"Bearer {token1}"})
        assert p1_resp.status_code == status.HTTP_202_ACCEPTED
        assert p1_resp.json()["status"] == "PENDING_SECOND_APPROVAL"
        assert p1_resp.json()["first_approver_id"] == "usr_admin1"

        # 7. Same approver attempts second approval -> Dual-control violation
        self_confirm_resp = client.post(f"/api/v1/documents/{doc_id}/purge", headers={"Authorization": f"Bearer {token1}"})
        assert self_confirm_resp.status_code == status.HTTP_403_FORBIDDEN
        assert "Dual-control violation" in self_confirm_resp.json()["detail"]

        # 8. Second distinct approver completes permanent purge
        p2_resp = client.post(f"/api/v1/documents/{doc_id}/purge", headers={"Authorization": f"Bearer {token2}"})
        assert p2_resp.status_code == status.HTTP_200_OK
        data = p2_resp.json()
        assert data["status"] == "PERMANENTLY_PURGED"
        assert data["first_approver_id"] == "usr_admin1"
        assert data["second_approver_id"] == "usr_admin2"
        assert data["purged_from_storage"] is True

        # 9. Verify immutable audit trail is preserved and not cascade-deleted
        ev_purge = session.execute(
            select(AuditEvent).where(AuditEvent.invoice_id == inv_id, AuditEvent.action == "DOCUMENT_PERMANENTLY_PURGED")
        ).scalar_one()
        assert ev_purge.actor_id == "usr_admin2"
        assert ev_purge.before_state["first_approver_id"] == "usr_admin1"
        assert ev_purge.before_state["second_approver_id"] == "usr_admin2"

        # Document record removed from DB
        remaining_doc = session.execute(select(Document).where(Document.id == doc_id)).scalar_one_or_none()
        assert remaining_doc is None

    finally:
        settings.ENABLE_PERMANENT_PURGE = orig_purge_enable
        settings.DOCUMENT_RETENTION_DAYS = orig_retention_days


def test_14_storage_health_check_accuracy():
    """Test 14: Storage health check accurately distinguishes NOT_CONFIGURED, CONNECTED, DEGRADED, BLOCKED."""
    adapter = SupabaseStorageAdapter()

    # 1. Unconfigured credentials
    with patch.object(adapter, "supabase_url", ""), patch.object(adapter, "service_role_key", None), patch.object(adapter, "anon_key", None):
        h = adapter.check_health()
        assert h["status"] == "NOT_CONFIGURED"
        assert h["readiness"] is False

    # 2. Connected private bucket
    mock_resp_200 = MagicMock()
    mock_resp_200.status_code = 200
    mock_resp_200.json.return_value = {"id": "invoices", "public": False}

    with patch("httpx.get", return_value=mock_resp_200), \
         patch.object(adapter, "supabase_url", "https://xyz.supabase.co"), \
         patch.object(adapter, "service_role_key", "secret-key"):
        h = adapter.check_health()
        assert h["status"] == "CONNECTED"
        assert h["readiness"] is True

    # 3. Degraded public bucket (warning)
    mock_resp_pub = MagicMock()
    mock_resp_pub.status_code = 200
    mock_resp_pub.json.return_value = {"id": "invoices", "public": True}

    with patch("httpx.get", return_value=mock_resp_pub), \
         patch.object(adapter, "supabase_url", "https://xyz.supabase.co"), \
         patch.object(adapter, "service_role_key", "secret-key"):
        h = adapter.check_health()
        assert h["status"] == "DEGRADED"
        assert "private buckets only" in h["message"]

    # 4. Blocked (HTTP 401/403)
    mock_resp_403 = MagicMock()
    mock_resp_403.status_code = 403

    with patch("httpx.get", return_value=mock_resp_403), \
         patch.object(adapter, "supabase_url", "https://xyz.supabase.co"), \
         patch.object(adapter, "service_role_key", "invalid-key"):
        h = adapter.check_health()
        assert h["status"] == "BLOCKED"
        assert h["readiness"] is False


def test_15_live_supabase_integration_truthful_state():
    """Test 15: Truthful inspection without simulation when live credentials are absent."""
    adapter = SupabaseStorageAdapter()
    health = adapter.check_health()

    # In local testing without actual cloud keys, adapter must report NOT_CONFIGURED or BLOCKED, never fake CONNECTED
    if not (settings.SUPABASE_URL and (settings.SUPABASE_SERVICE_ROLE_KEY or settings.SUPABASE_ANON_KEY)):
        assert health["status"] == "NOT_CONFIGURED"
        assert health["readiness"] is False
    else:
        assert health["status"] in ("CONNECTED", "DEGRADED", "BLOCKED")
