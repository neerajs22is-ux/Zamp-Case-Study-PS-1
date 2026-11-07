"""Phase B Stage 6 Acceptance Tests — Supabase Backup & Recovery Implementation.

Verifies:
1. Database export succeeds.
2. Database export contains expected application tables and data.
3. Custom application roles and grants are accounted for.
4. Storage object listing handles pagination.
5. All expected invoice files are exported.
6. File checksum matches the document record.
7. Missing files are reported.
8. Corrupted files are rejected.
9. Manifest matches the exported archive contents.
10. Archive encryption and decryption work.
11. Restored files match original SHA-256 hashes.
12. Failed or incomplete backup is never marked successful.
13. Existing audit records remain intact.
14. Tenant relationships remain valid after restoration.
15. Live Supabase backup/restore marked BLOCKED when no live project exists.
"""

from __future__ import annotations

import datetime
import hashlib
import io
import json
import os
import tarfile
import tempfile
from typing import Any, Dict, Generator, Tuple
from unittest.mock import patch

from fastapi import status
from fastapi.testclient import TestClient
from jose import jwt
import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from backend.core.backup import (
    create_backup_archive, decrypt_archive, encrypt_archive,
    generate_backup_encryption_key, get_encryption_key,
    inspect_backup_status, prune_backups, restore_backup_archive,
    BackupError, ChecksumMismatchError, DatabaseBackupManager,
    DatabaseRestoreError, DecryptionError, ManifestVerificationError,
    StorageBackupManager
)
from backend.core.config import AppEnv, settings
from backend.core.database import Base, get_db
from backend.core.storage import TestInMemoryStorageAdapter
from backend.main import app
from backend.core.auth import UserRole
from backend.models.domain import (
    AuditEvent, Document, Invoice, Organisation, RoleAssignment,
    User, Vendor
)

SAMPLE_PDF_1 = b"%PDF-1.4\n1 0 obj\n<< /Title (Invoice 1) >>\nendobj\ntrailer\n<< /Root 1 0 R >>\n%%EOF"
SAMPLE_PDF_2 = b"%PDF-1.4\n2 0 obj\n<< /Title (Invoice 2) >>\nendobj\ntrailer\n<< /Root 2 0 R >>\n%%EOF"
CORRUPT_BYTES = b"%PDF-1.4\nTAMPERED_INVOICE_CORRUPTED_BYTES\n%%EOF"


def test_backup_rejects_unavailable_inventory(stage6_db, stage6_storage, monkeypatch):
    session, _ = stage6_db
    def fail(*args, **kwargs):
        raise RuntimeError('private provider details')
    monkeypatch.setattr(stage6_storage, 'list_all_objects', fail)
    with pytest.raises(BackupError, match='completeness') as err:
        StorageBackupManager.export_storage(session, stage6_storage)
    assert 'private provider details' not in str(err.value)


def test_backup_rejects_missing_unindexed_object(stage6_db, stage6_storage, monkeypatch):
    session, _ = stage6_db
    monkeypatch.setattr(stage6_storage, 'list_all_objects', lambda: [{'path': 'orphan.pdf'}])
    _, _, summary = StorageBackupManager.export_storage(session, stage6_storage)
    assert summary['failed_exports'] == 1
    assert summary['completion_status'] == 'FAILED'


def test_restore_rejects_nonempty_or_unavailable_target(stage6_storage, monkeypatch):
    stage6_storage.save_file(content=b'preserve', filename='existing.pdf', storage_key='existing.pdf')
    with pytest.raises(BackupError, match='empty isolated'):
        StorageBackupManager.restore_storage({}, [], stage6_storage)
    assert stage6_storage.get_file('existing.pdf') == b'preserve'
    def fail(*args, **kwargs): raise RuntimeError('private storage detail')
    monkeypatch.setattr(stage6_storage, 'list_all_objects', fail)
    with pytest.raises(BackupError, match='inventory is unavailable') as err:
        StorageBackupManager.restore_storage({}, [], stage6_storage)
    assert 'private storage detail' not in str(err.value)


@pytest.fixture(autouse=True)
def configure_stage6_settings():
    """Configures test environment for Stage 6."""
    orig_env = settings.APP_ENV
    settings.APP_ENV = AppEnv.TEST
    yield
    settings.APP_ENV = orig_env


@pytest.fixture
def stage6_db() -> Generator[Tuple[Session, Any], None, None]:
    """Provides an isolated in-memory SQLite database for Stage 6 tests."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = session_factory()
    try:
        yield session, engine
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def stage6_storage() -> TestInMemoryStorageAdapter:
    """Provides a clean in-memory storage adapter."""
    adapter = TestInMemoryStorageAdapter()
    return adapter


@pytest.fixture
def temp_backup_dir() -> Generator[str, None, None]:
    """Provides a clean temporary directory for backup archives."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


def seed_test_tenant(
    session: Session,
    storage: TestInMemoryStorageAdapter,
    org_id: str = "org_alpha",
) -> Tuple[User, Invoice, Document]:
    """Seeds tenant, user, invoice, document, and storage object."""
    org = Organisation(id=org_id, name="Alpha Corp")
    session.add(org)

    user = User(
        id=f"user_{org_id}",
        org_id=org_id,
        email="operator@alpha.com",
        full_name="Alpha Operator",
        is_active=True,
    )
    session.add(user)

    role = RoleAssignment(
        id=f"ra_{org_id}",
        org_id=org_id,
        user_id=user.id,
        role_name="SYSTEM_ADMIN",
    )
    session.add(role)

    inv = Invoice(
        id=f"inv_{org_id}_1",
        org_id=org_id,
        source_channel="MANUAL_UPLOAD",
        invoice_number="INV-2026-001",
        vendor_name="Acme Supplies",
        stage="RECEIVED",
        decision="APPROVED",
    )
    session.add(inv)

    doc_bytes = SAMPLE_PDF_1
    doc_hash = hashlib.sha256(doc_bytes).hexdigest()
    storage_key = f"org_{org_id}/invoices/doc_{org_id}_1/inv_001.pdf"

    doc = Document(
        id=f"doc_{org_id}_1",
        org_id=org_id,
        invoice_id=inv.id,
        filename="inv_001.pdf",
        mime_type="application/pdf",
        file_size_bytes=len(doc_bytes),
        sha256_hash=doc_hash,
        storage_provider="SUPABASE_STORAGE",
        storage_key=storage_key,
        is_original=True,
        is_deleted=False,
    )
    session.add(doc)

    audit = AuditEvent(
        id=f"evt_{org_id}_1",
        org_id=org_id,
        actor_id=user.id,
        actor_role="SYSTEM_ADMIN",
        action="INVOICE_INGESTED",
        reason="Manual test ingestion",
        source_reference=inv.id,
    )
    session.add(audit)
    session.commit()

    # Save to storage
    storage.save_file(
        content=doc_bytes,
        filename="inv_001.pdf",
        mime_type="application/pdf",
        storage_key=storage_key,
    )

    return user, inv, doc


# ==============================================================================
# Test 01: Database Export Succeeds
# ==============================================================================

def test_01_database_export_succeeds(stage6_db):
    """Test 01: Database export generates valid DDL and data SQL without error."""
    session, _ = stage6_db
    storage = TestInMemoryStorageAdapter()
    seed_test_tenant(session, storage, org_id="org_alpha")

    schema_sql, data_sql, table_counts, auth_summary = DatabaseBackupManager.export_database_state(session)

    assert isinstance(schema_sql, str)
    assert isinstance(data_sql, str)
    assert len(data_sql) > 0
    assert "INSERT INTO organisations" in data_sql
    assert "INSERT INTO users" in data_sql
    assert "INSERT INTO invoices" in data_sql
    assert "INSERT INTO documents" in data_sql
    assert "INSERT INTO audit_events" in data_sql
    assert table_counts["organisations"] == 1
    assert table_counts["users"] == 1
    assert table_counts["invoices"] == 1
    assert table_counts["documents"] == 1
    assert table_counts["audit_events"] == 1
    assert len(auth_summary) == 1
    assert auth_summary[0]["email"] == "operator@alpha.com"


# ==============================================================================
# Test 02: Database Export Contains Expected Application Tables and Data
# ==============================================================================

def test_02_database_export_contains_expected_tables_and_data(stage6_db):
    """Test 02: Database export captures all domain tables and values accurately."""
    session, _ = stage6_db
    storage = TestInMemoryStorageAdapter()
    seed_test_tenant(session, storage, org_id="org_bravo")

    _, data_sql, table_counts, _ = DatabaseBackupManager.export_database_state(session)

    expected_tables = {
        "organisations", "users", "role_assignments", "invoices",
        "documents", "audit_events"
    }
    for t in expected_tables:
        assert t in table_counts
        assert table_counts[t] >= 1
        assert f"INSERT INTO {t}" in data_sql

    assert "org_bravo" in data_sql
    assert "INV-2026-001" in data_sql


# ==============================================================================
# Test 03: Custom Application Roles and Grants Are Accounted For
# ==============================================================================

def test_03_custom_application_roles_and_grants_accounted_for():
    """Test 03: Roles export contains ap_app_user, schema grants, and audit immutability revoke."""
    roles_sql = DatabaseBackupManager.export_roles()

    assert "CREATE ROLE ap_app_user" in roles_sql
    assert "GRANT USAGE ON SCHEMA public TO ap_app_user;" in roles_sql
    assert "GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO ap_app_user;" in roles_sql
    assert "REVOKE UPDATE, DELETE ON TABLE audit_events FROM ap_app_user;" in roles_sql


# ==============================================================================
# Test 04: Storage Object Listing Handles Pagination
# ==============================================================================

def test_04_storage_object_listing_handles_pagination(stage6_storage):
    """Test 04: Storage listing handles pagination and retrieves all items across pages."""
    # Seed 5 objects
    for i in range(5):
        key = f"org_test/invoices/doc_{i}/inv_{i}.pdf"
        stage6_storage.save_file(
            content=SAMPLE_PDF_1,
            filename=f"inv_{i}.pdf",
            storage_key=key,
        )

    # Test page limit 2
    page1 = stage6_storage.list_objects(prefix="org_test", limit=2, offset=0)
    assert len(page1) == 2

    page2 = stage6_storage.list_objects(prefix="org_test", limit=2, offset=2)
    assert len(page2) == 2

    page3 = stage6_storage.list_objects(prefix="org_test", limit=2, offset=4)
    assert len(page3) == 1

    # Test list_all_objects automatically aggregates all 5
    all_objs = stage6_storage.list_all_objects(prefix="org_test")
    assert len(all_objs) == 5


# ==============================================================================
# Test 05: All Expected Invoice Files Are Exported
# ==============================================================================

def test_05_all_expected_invoice_files_are_exported(stage6_db, stage6_storage):
    """Test 05: Export downloads and packages all expected invoice files."""
    session, _ = stage6_db
    seed_test_tenant(session, stage6_storage, org_id="org_alpha")

    files_map, manifest_objs, summary = StorageBackupManager.export_storage(
        session=session,
        storage_adapter=stage6_storage,
    )

    assert summary["total_expected_objects"] == 1
    assert summary["successfully_exported_objects"] == 1
    assert summary["failed_exports"] == 0
    assert summary["checksum_mismatches"] == 0
    assert summary["completion_status"] == "SUCCESS"
    assert len(files_map) == 1
    assert len(manifest_objs) == 1
    assert manifest_objs[0]["verification_result"] == "VERIFIED"


# ==============================================================================
# Test 06: File Checksum Matches the Document Record
# ==============================================================================

def test_06_file_checksum_matches_document_record(stage6_db, stage6_storage):
    """Test 06: Computed SHA-256 matches the database Document record exactly."""
    session, _ = stage6_db
    _, _, doc = seed_test_tenant(session, stage6_storage, org_id="org_alpha")

    files_map, manifest_objs, _ = StorageBackupManager.export_storage(
        session=session,
        storage_adapter=stage6_storage,
    )

    clean_key = doc.storage_key.lstrip("/")
    downloaded_bytes = files_map[clean_key]
    computed_hash = hashlib.sha256(downloaded_bytes).hexdigest()

    assert computed_hash == doc.sha256_hash
    assert manifest_objs[0]["sha256"] == doc.sha256_hash
    assert manifest_objs[0]["verification_result"] == "VERIFIED"


# ==============================================================================
# Test 07: Missing Files Are Reported
# ==============================================================================

def test_07_missing_files_are_reported(stage6_db, stage6_storage):
    """Test 07: When a document is missing from storage, it is flagged as MISSING_FROM_STORAGE."""
    session, _ = stage6_db
    seed_test_tenant(session, stage6_storage, org_id="org_alpha")

    # Add a document record with no physical storage object
    ghost_doc = Document(
        id="doc_ghost",
        org_id="org_alpha",
        filename="ghost.pdf",
        mime_type="application/pdf",
        file_size_bytes=1000,
        sha256_hash="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        storage_provider="SUPABASE_STORAGE",
        storage_key="org_alpha/invoices/doc_ghost/ghost.pdf",
        is_original=True,
        is_deleted=False,
    )
    session.add(ghost_doc)
    session.commit()

    _, manifest_objs, summary = StorageBackupManager.export_storage(
        session=session,
        storage_adapter=stage6_storage,
    )

    assert summary["total_expected_objects"] == 2
    assert summary["successfully_exported_objects"] == 1
    assert summary["failed_exports"] == 1
    assert summary["completion_status"] == "FAILED"

    ghost_entry = [o for o in manifest_objs if o["document_id"] == "doc_ghost"][0]
    assert ghost_entry["verification_result"] == "MISSING_FROM_STORAGE"


# ==============================================================================
# Test 08: Corrupted Files Are Rejected
# ==============================================================================

def test_08_corrupted_files_are_rejected(stage6_db, stage6_storage):
    """Test 08: When a physical file has an altered SHA-256, it is flagged as CORRUPTED."""
    session, _ = stage6_db
    _, _, doc = seed_test_tenant(session, stage6_storage, org_id="org_alpha")

    # Overwrite physical file in storage with corrupted content
    stage6_storage.save_file(
        content=CORRUPT_BYTES,
        filename=doc.filename,
        storage_key=doc.storage_key,
    )

    _, manifest_objs, summary = StorageBackupManager.export_storage(
        session=session,
        storage_adapter=stage6_storage,
    )

    assert summary["checksum_mismatches"] == 1
    assert summary["completion_status"] == "FAILED"

    corrupt_entry = manifest_objs[0]
    assert corrupt_entry["verification_result"] == "CORRUPTED"
    assert corrupt_entry["sha256"] != doc.sha256_hash


# ==============================================================================
# Test 09: Manifest Matches Exported Archive Contents
# ==============================================================================

def test_09_manifest_matches_exported_archive_contents(stage6_db, stage6_storage, temp_backup_dir):
    """Test 09: Manifest recorded in archive accurately matches internal files and bytes."""
    session, _ = stage6_db
    seed_test_tenant(session, stage6_storage, org_id="org_alpha")

    key = generate_backup_encryption_key()
    result = create_backup_archive(
        session=session,
        storage_adapter=stage6_storage,
        backup_dir=temp_backup_dir,
        encryption_key=key,
    )

    archive_path = result["archive_path"]
    assert os.path.exists(archive_path)

    # Decrypt and inspect tarball
    with open(archive_path, "rb") as f:
        enc = f.read()

    raw_tar = decrypt_archive(enc, key)
    with tarfile.open(fileobj=io.BytesIO(raw_tar), mode="r:gz") as tar:
        members = tar.getnames()
        assert "manifest.json" in members
        assert "database/roles.sql" in members
        assert "database/schema.sql" in members
        assert "database/data.sql" in members
        assert "auth_summary.json" in members

        mf = tar.extractfile("manifest.json")
        manifest_data = json.loads(mf.read().decode("utf-8"))

        assert manifest_data["backup_id"] == result["backup_id"]
        assert manifest_data["summary"]["completion_status"] == "SUCCESS"
        assert len(manifest_data["objects"]) == 1

        stored_file_path = f"storage/{manifest_data['objects'][0]['storage_path']}"
        assert stored_file_path in members

        f_stream = tar.extractfile(stored_file_path)
        f_bytes = f_stream.read()
        f_hash = hashlib.sha256(f_bytes).hexdigest()
        assert f_hash == manifest_data["objects"][0]["sha256"]


# ==============================================================================
# Test 10: Archive Encryption and Decryption Work
# ==============================================================================

def test_10_archive_encryption_and_decryption_work():
    """Test 10: Encryption protects bytes and wrong key or altered ciphertext raises DecryptionError."""
    key1 = generate_backup_encryption_key()
    key2 = generate_backup_encryption_key()
    payload = b"Top secret AP Command Center financial backup data"

    ciphertext = encrypt_archive(payload, key1)
    assert ciphertext != payload

    # Decrypt with correct key
    decrypted = decrypt_archive(ciphertext, key1)
    assert decrypted == payload

    # Decrypt with wrong key raises DecryptionError
    with pytest.raises(DecryptionError):
        decrypt_archive(ciphertext, key2)

    # Tampered ciphertext raises DecryptionError
    tampered = bytearray(ciphertext)
    tampered[-5] = (tampered[-5] + 1) % 256
    with pytest.raises(DecryptionError):
        decrypt_archive(bytes(tampered), key1)


# ==============================================================================
# Test 11: Restored Files Match Original SHA-256 Hashes
# ==============================================================================

def test_11_restored_files_match_original_sha256(stage6_db, stage6_storage, temp_backup_dir):
    """Test 11: Files restored into target storage match original cryptographic checksums."""
    session, _ = stage6_db
    _, _, original_doc = seed_test_tenant(session, stage6_storage, org_id="org_alpha")

    key = generate_backup_encryption_key()
    backup_res = create_backup_archive(
        session=session,
        storage_adapter=stage6_storage,
        backup_dir=temp_backup_dir,
        encryption_key=key,
    )

    # Target fresh storage adapter
    fresh_storage = TestInMemoryStorageAdapter()

    # Restore
    restore_res = restore_backup_archive(
        archive_path=backup_res["archive_path"],
        encryption_key=key,
        target_session=None,
        target_storage=fresh_storage,
        confirm_restore=True,
    )

    assert restore_res["status"] == "RESTORE_PARTIAL"
    assert restore_res["storage"]["restored_objects"] == 1
    assert restore_res["storage"]["verified_objects"] == 1

    clean_key = original_doc.storage_key.lstrip("/")
    restored_bytes = fresh_storage.get_file(clean_key)
    restored_hash = hashlib.sha256(restored_bytes).hexdigest()
    assert restored_hash == original_doc.sha256_hash


# ==============================================================================
# Test 12: Failed or Incomplete Backup Is Never Marked Successful
# ==============================================================================

def test_12_failed_or_incomplete_backup_is_never_marked_successful(stage6_db, stage6_storage, temp_backup_dir):
    """Test 12: Incomplete or corrupted backups are strictly flagged as FAILED."""
    session, _ = stage6_db
    seed_test_tenant(session, stage6_storage, org_id="org_alpha")

    # Seed a second document that is missing from physical storage
    missing_doc = Document(
        id="doc_missing_02",
        org_id="org_alpha",
        filename="missing_invoice.pdf",
        mime_type="application/pdf",
        file_size_bytes=2048,
        sha256_hash="1111222233334444555566667777888899990000aaaabbbbccccddddeeeeffff",
        storage_provider="SUPABASE_STORAGE",
        storage_key="org_alpha/invoices/doc_missing_02/missing_invoice.pdf",
        is_original=True,
        is_deleted=False,
    )
    session.add(missing_doc)
    session.commit()

    key = generate_backup_encryption_key()
    res = create_backup_archive(
        session=session,
        storage_adapter=stage6_storage,
        backup_dir=temp_backup_dir,
        encryption_key=key,
    )

    # Strict invariant: MUST NOT BE SUCCESS
    assert res["completion_status"] == "FAILED"
    assert res["summary"]["completion_status"] == "FAILED"
    assert res["summary"]["failed_exports"] == 1


# ==============================================================================
# Test 13: Existing Audit Records Remain Intact
# ==============================================================================

def test_13_existing_audit_records_remain_intact(stage6_db, stage6_storage, temp_backup_dir):
    """Test 13: Audit events are preserved and restored with identical properties."""
    session, _ = stage6_db
    seed_test_tenant(session, stage6_storage, org_id="org_alpha")

    key = generate_backup_encryption_key()
    backup_res = create_backup_archive(
        session=session,
        storage_adapter=stage6_storage,
        backup_dir=temp_backup_dir,
        encryption_key=key,
    )

    # Target fresh database session
    engine2 = create_engine("sqlite:///:memory:", poolclass=StaticPool)
    Base.metadata.create_all(bind=engine2)
    session_factory2 = sessionmaker(bind=engine2)
    target_session = session_factory2()

    try:
        restore_res = restore_backup_archive(
            archive_path=backup_res["archive_path"],
            encryption_key=key,
            target_session=target_session,
            target_storage=None,
            confirm_restore=True,
        )

        assert restore_res["status"] == "RESTORE_PARTIAL"

        # Check audit event in restored target session
        audits = target_session.execute(select(AuditEvent)).scalars().all()
        assert len(audits) == 1
        assert audits[0].id == "evt_org_alpha_1"
        assert audits[0].action == "INVOICE_INGESTED"
        assert audits[0].org_id == "org_alpha"
        assert audits[0].actor_role == "SYSTEM_ADMIN"
    finally:
        target_session.close()
        Base.metadata.drop_all(bind=engine2)


# ==============================================================================
# Test 14: Tenant Relationships Remain Valid After Restoration
# ==============================================================================

def test_14_tenant_relationships_remain_valid_after_restoration(stage6_db, stage6_storage, temp_backup_dir):
    """Test 14: Restored documents, invoices, and users retain exact org_id isolation."""
    session, _ = stage6_db
    seed_test_tenant(session, stage6_storage, org_id="org_alpha")

    key = generate_backup_encryption_key()
    backup_res = create_backup_archive(
        session=session,
        storage_adapter=stage6_storage,
        backup_dir=temp_backup_dir,
        encryption_key=key,
    )

    # Target fresh database session
    engine2 = create_engine("sqlite:///:memory:", poolclass=StaticPool)
    Base.metadata.create_all(bind=engine2)
    session_factory2 = sessionmaker(bind=engine2)
    target_session = session_factory2()

    try:
        restore_backup_archive(
            archive_path=backup_res["archive_path"],
            encryption_key=key,
            target_session=target_session,
            target_storage=None,
            confirm_restore=True,
        )

        # Verify tenant linkages
        orgs = target_session.execute(select(Organisation)).scalars().all()
        assert len(orgs) == 1
        assert orgs[0].id == "org_alpha"

        users = target_session.execute(select(User)).scalars().all()
        assert len(users) == 1
        assert users[0].org_id == "org_alpha"

        invoices = target_session.execute(select(Invoice)).scalars().all()
        assert len(invoices) == 1
        assert invoices[0].org_id == "org_alpha"

        docs = target_session.execute(select(Document)).scalars().all()
        assert len(docs) == 1
        assert docs[0].org_id == "org_alpha"
        assert docs[0].invoice_id == invoices[0].id
    finally:
        target_session.close()
        Base.metadata.drop_all(bind=engine2)


# ==============================================================================
# Test 15: Live Supabase Backup & Restore Truthful BLOCKED State
# ==============================================================================

def test_15_live_supabase_backup_restore_truthful_state():
    """Test 15: Live Supabase project verification reports BLOCKED when credentials are not provisioned."""
    live_tests_enabled = os.getenv("LIVE_SUPABASE_TESTS") == "1"
    has_creds = bool(settings.SUPABASE_URL and settings.SUPABASE_SERVICE_ROLE_KEY)

    if not live_tests_enabled or not has_creds:
        pytest.skip(
            "Live Supabase backup & restoration test BLOCKED: Dedicated Supabase project credentials "
            "(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY) not configured in local environment."
        )

    # In live mode, verify Supabase credentials
    assert settings.SUPABASE_URL is not None
    assert settings.SUPABASE_SERVICE_ROLE_KEY is not None


# ==============================================================================
# Test 16: Restoration Without Confirmation Guard Fails Safe
# ==============================================================================

def test_16_restoration_without_confirmation_guard_fails_safe(temp_backup_dir):
    """Test 16: Attempting restoration without confirm_restore=True is strictly blocked."""
    archive_path = os.path.join(temp_backup_dir, "fake.tar.gz.enc")
    with open(archive_path, "wb") as f:
        f.write(b"fake_enc")

    with pytest.raises(BackupError) as exc_info:
        restore_backup_archive(
            archive_path=archive_path,
            confirm_restore=False,
        )

    assert "Destructive restoration rejected" in str(exc_info.value)


# ==============================================================================
# Test 17: Backup Status Endpoint Reports Truthful State and Scheduling
# ==============================================================================

def test_17_backup_status_endpoint_truthful_disclosure(stage6_db, temp_backup_dir, monkeypatch):
    """Test 17: GET /api/v1/system/backup/status reports NOT_CONFIGURED when empty."""
    session, _ = stage6_db
    app.dependency_overrides[get_db] = lambda: session
    client = TestClient(app)

    # Seed admin user
    org = Organisation(id="org_admin", name="Admin Org")
    session.add(org)
    admin_user = User(
        id="user_sysadmin",
        org_id="org_admin",
        email="sysadmin@alpha.com",
        full_name="Sys Admin",
        is_active=True,
    )
    session.add(admin_user)
    role = RoleAssignment(
        id="ra_sysadmin",
        org_id="org_admin",
        user_id="user_sysadmin",
        role_name="SYSTEM_ADMIN",
    )
    session.add(role)
    session.commit()

    token = "test_token:SYSTEM_ADMIN:user_sysadmin:sysadmin@alpha.com:org_admin"
    monkeypatch.setattr(settings, "PLATFORM_OPERATOR_SUBJECTS", "")
    denied = client.get("/api/v1/system/backup/status", headers={"Authorization": f"Bearer {token}"})
    assert denied.status_code == status.HTTP_403_FORBIDDEN
    monkeypatch.setattr(settings, "PLATFORM_OPERATOR_SUBJECTS", "user_sysadmin")

    with patch("backend.core.backup.settings.BACKUP_DIR", temp_backup_dir):
        resp = client.get(
            "/api/v1/system/backup/status",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()

        assert data["status"] == "NOT_CONFIGURED"
        assert data["backup_count"] == 0
        assert data["scheduling"]["execution_mode"] == "OPERATOR_MANUAL"
        assert data["scheduling"]["background_scheduler"] == "NOT_CONFIGURED"

    app.dependency_overrides.clear()


# ==============================================================================
# Test 18: Foreign-Key Constraint Violation Detected Post-Restore
# ==============================================================================

def test_18_foreign_key_violation_caught_post_restore(stage6_db):
    """Test 18: Post-restoration verification catches orphaned records violating foreign keys."""
    session, _ = stage6_db
    storage = TestInMemoryStorageAdapter()
    seed_test_tenant(session, storage, org_id="org_alpha")

    # Deliberately inject an orphaned invoice referencing a non-existent legal entity
    # To bypass SQLite FK check during insert, disable FK temporarily
    session.execute(text("PRAGMA foreign_keys = OFF;"))
    session.execute(
        text(
            "INSERT INTO invoices (id, org_id, legal_entity_id, source_channel, currency, invoice_number, "
            "vendor_name, stage, decision, created_at, updated_at) "
            "VALUES ('inv_orphan', 'org_alpha', 'non_existent_entity', 'MANUAL_UPLOAD', 'INR', 'INV-ORPHAN', "
            "'Acme Supplies', 'RECEIVED', 'APPROVED', datetime('now'), datetime('now'))"
        )
    )
    session.commit()
    session.execute(text("PRAGMA foreign_keys = ON;"))

    manifest = {
        "database": {"table_counts": {"audit_events": 1}},
        "objects": [],
    }

    with pytest.raises(DatabaseRestoreError) as exc_info:
        from backend.core.backup import verify_restore_integrity
        verify_restore_integrity(session=session, storage_adapter=storage, manifest=manifest)

    assert "Foreign key constraint violation" in str(exc_info.value)


# ==============================================================================
# Test 19: Tenant Isolation Mismatch Detected Post-Restore
# ==============================================================================

def test_19_tenant_isolation_mismatch_caught_post_restore(stage6_db):
    """Test 19: Post-restoration verification detects cross-tenant parent-child mismatches."""
    session, _ = stage6_db
    storage = TestInMemoryStorageAdapter()
    seed_test_tenant(session, storage, org_id="org_alpha")

    # Add second tenant organisation and invoice
    org_b = Organisation(id="org_beta", name="Beta Corp")
    session.add(org_b)
    inv_b = Invoice(
        id="inv_beta_1",
        org_id="org_beta",
        source_channel="MANUAL_UPLOAD",
        invoice_number="INV-B-001",
        vendor_name="Acme",
        stage="RECEIVED",
        decision="APPROVED",
    )
    session.add(inv_b)

    # Inject document belonging to org_alpha but pointing to invoice of org_beta
    cross_tenant_doc = Document(
        id="doc_cross_tenant",
        org_id="org_alpha",
        invoice_id="inv_beta_1",  # Cross-tenant linkage!
        filename="cross.pdf",
        mime_type="application/pdf",
        file_size_bytes=1000,
        sha256_hash="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        storage_provider="SUPABASE_STORAGE",
        storage_key="org_alpha/invoices/doc_cross_tenant/cross.pdf",
        is_original=True,
        is_deleted=False,
    )
    session.add(cross_tenant_doc)
    session.commit()

    manifest = {
        "database": {"table_counts": {"audit_events": 1}},
        "objects": [],
    }

    with pytest.raises(DatabaseRestoreError) as exc_info:
        from backend.core.backup import verify_restore_integrity
        verify_restore_integrity(session=session, storage_adapter=storage, manifest=manifest)

    assert "tenant" in str(exc_info.value).lower() and "mismatch" in str(exc_info.value).lower()


# ==============================================================================
# Test 20: Audit Immutability Trigger Verified Post-Restore
# ==============================================================================

def test_20_audit_immutability_verification_post_restore(stage6_db):
    """Test 20: Post-restoration verification validates audit counts and immutability checks."""
    session, _ = stage6_db
    storage = TestInMemoryStorageAdapter()
    seed_test_tenant(session, storage, org_id="org_alpha")

    # Manifest expecting 5 audit events when only 1 exists
    manifest_mismatch = {
        "database": {"table_counts": {"audit_events": 5}},
        "objects": [],
    }

    with pytest.raises(DatabaseRestoreError) as exc_info:
        from backend.core.backup import verify_restore_integrity
        verify_restore_integrity(session=session, storage_adapter=storage, manifest=manifest_mismatch)

    assert "Audit verification failed: expected 5 events, found 1" in str(exc_info.value)


# ==============================================================================
# Test 21: Secure Key Handling Prefers Environment Variable & Warns on CLI Flag
# ==============================================================================

def test_21_secure_key_handling_prefers_env_and_warns_on_cli(caplog):
    """Test 21: Encryption key resolution prioritizes env vars and warns on CLI usage."""
    test_key = generate_backup_encryption_key()

    # 1. Environment variable resolution
    with patch.dict(os.environ, {"BACKUP_ENCRYPTION_KEY": test_key}):
        resolved = get_encryption_key()
        assert resolved == test_key

    # 2. CLI flag usage logs security warning
    with patch.dict(os.environ, {}, clear=True):
        with patch.object(settings, "BACKUP_ENCRYPTION_KEY", None):
            with caplog.at_level("WARNING"):
                cli_resolved = get_encryption_key(key_override=test_key)
                assert cli_resolved == test_key
                assert any("SECURITY NOTICE" in r.message for r in caplog.records)

    # 3. Missing key without interactive prompt raises BackupError
    with patch.dict(os.environ, {}, clear=True):
        with patch.object(settings, "BACKUP_ENCRYPTION_KEY", None):
            with pytest.raises(BackupError) as exc_info:
                get_encryption_key(prompt_if_missing=False)
            assert "Backup encryption key not provided" in str(exc_info.value)


# ==============================================================================
# Test 22: Auth Reconciliation Updates User ID and Logs Immutable Audit Event
# ==============================================================================

def test_22_email_only_auth_reconciliation_is_denied(stage6_db):
    """Email alone cannot authorize identity binding or changes to historical IDs."""
    session, _ = stage6_db
    storage = TestInMemoryStorageAdapter()
    user, _, _ = seed_test_tenant(session, storage, org_id="org_alpha")

    old_user_id = user.id
    new_uuid = "usr_google_sub_999888"

    with pytest.raises(DatabaseRestoreError):
        DatabaseBackupManager.reconcile_auth_user(
            session=session, email="operator@alpha.com", new_auth_id=new_uuid, actor_id="SYS_OPERATOR")

    # Verify user record updated
    updated_user = session.execute(select(User).where(User.email == "operator@alpha.com")).scalar_one()
    assert updated_user.id == old_user_id

    # Verify role assignment cascaded
    role = session.execute(select(RoleAssignment).where(RoleAssignment.user_id == old_user_id)).scalar_one_or_none()
    assert role is not None
    assert role.user_id == old_user_id

    # Verify audit event logged
    audit = session.execute(
        select(AuditEvent).where(AuditEvent.action == "USER_AUTH_RECONCILED")
    ).scalar_one_or_none()
    assert audit is None
    assert 'INSERT INTO auth.' not in DatabaseBackupManager.export_auth_state(session)
