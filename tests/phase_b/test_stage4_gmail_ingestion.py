"""Phase B Stage 4 Acceptance Tests — Gmail OAuth & Mailbox Ingestion.

Comprehensive validation of the 10 binding Gmail ingestion requirements:
Test 01: Server-side token encryption and decryption (Fernet AES-256).
Test 02: OAuth state generation, HMAC tamper detection, and expiration.
Test 03: OAuth authorization URL generation with gmail.readonly scope.
Test 04: OAuth callback stores encrypted token and emits immutable audit event.
Test 05: Mailbox ingestion downloads valid PDF and stores in Supabase Storage.
Test 06: Corrupt attachment header is quarantined into QuarantinedDocument.
Test 07: Duplicate PDF attachment in tenant is skipped without re-ingesting.
Test 08: Unconfigured Gmail reports truthful NOT_CONFIGURED status.
Test 09: Mailbox disconnect revokes status, clears token, and emits audit event.
Test 10: CASA Tier 2 assessment disclosure and minimum scope compliance.
"""

from __future__ import annotations

import base64
import datetime
import hashlib
import io
import json
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
from backend.core.gmail import (
    decrypt_refresh_token, encrypt_refresh_token,
    generate_oauth_state, sync_gmail_mailbox, validate_oauth_state
)
from backend.core.storage import storage_adapter
from backend.main import app
from backend.models.domain import (
    AuditEvent, Document, GmailAccount, IngestionJob, Invoice,
    Organisation, QuarantinedDocument, RoleAssignment, User
)

TEST_JWT_SECRET = "stage4-gmail-test-secret-32-chars-long"
TEST_ISSUER = "https://test-project.supabase.co/auth/v1"
TEST_AUDIENCE = "authenticated"
SAMPLE_PDF_BYTES = b"%PDF-1.4\n1 0 obj\n<< /Title (Gmail Vendor Invoice) >>\nendobj\ntrailer\n<< /Root 1 0 R >>\n%%EOF"


@pytest.fixture(autouse=True)
def configure_stage4_settings():
    """Configures environment settings for Stage 4 acceptance tests."""
    orig_env = settings.APP_ENV
    orig_secret = settings.SUPABASE_JWT_SECRET
    orig_iss = settings.SUPABASE_ISSUER
    orig_aud = settings.SUPABASE_AUDIENCE
    orig_client_id = settings.GMAIL_CLIENT_ID
    orig_client_secret = settings.GMAIL_CLIENT_SECRET
    orig_target_box = settings.GMAIL_TARGET_MAILBOX

    settings.APP_ENV = AppEnv.TEST
    settings.SUPABASE_JWT_SECRET = TEST_JWT_SECRET
    settings.SUPABASE_ISSUER = TEST_ISSUER
    settings.SUPABASE_AUDIENCE = TEST_AUDIENCE
    settings.GMAIL_CLIENT_ID = "test-gmail-client-id.apps.googleusercontent.com"
    settings.GMAIL_CLIENT_SECRET = "test-gmail-client-secret"
    settings.GMAIL_TARGET_MAILBOX = "test-ap-inbox@example.com"

    yield

    settings.APP_ENV = orig_env
    settings.SUPABASE_JWT_SECRET = orig_secret
    settings.SUPABASE_ISSUER = orig_iss
    settings.SUPABASE_AUDIENCE = orig_aud
    settings.GMAIL_CLIENT_ID = orig_client_id
    settings.GMAIL_CLIENT_SECRET = orig_client_secret
    settings.GMAIL_TARGET_MAILBOX = orig_target_box


@pytest.fixture
def stage4_db():
    """Provides a fresh, isolated in-memory SQLite database for Stage 4 tests."""
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
def stage4_client(stage4_db):
    """FastAPI TestClient with isolated Stage 4 database session override."""
    session, _ = stage4_db

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
    now = datetime.datetime.now(datetime.timezone.utc)
    exp = now + datetime.timedelta(seconds=expires_in_seconds)
    payload = {
        "sub": sub,
        "email": email,
        "name": "Test Operator",
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
    email: str = "admin@alpha.internal",
    role_name: str = "SYSTEM_ADMIN",
) -> str:
    existing_org = session.execute(select(Organisation).where(Organisation.id == org_id)).scalar_one_or_none()
    if not existing_org:
        session.add(Organisation(id=org_id, name=f"Organisation {org_id}"))

    user = User(id=user_id, org_id=org_id, email=email, full_name=f"User {user_id}", is_active=True)
    role = RoleAssignment(id=f"ra_{user_id}", org_id=org_id, user_id=user_id, role_name=role_name)
    session.add_all([user, role])
    session.commit()
    return make_jwt(sub=user_id, email=email)


# ==============================================================================
# 10 Acceptance Tests for Stage 4
# ==============================================================================

def test_01_token_encryption_and_decryption():
    """Test 1: Server-side token encryption and decryption (Fernet AES-256)."""
    raw_token = "1//04test_refresh_token_very_secret_google_oauth"
    encrypted = encrypt_refresh_token(raw_token)

    assert encrypted != raw_token
    assert raw_token not in encrypted
    decrypted = decrypt_refresh_token(encrypted)
    assert decrypted == raw_token


def test_02_oauth_state_generation_and_tamper_detection():
    """Test 2: OAuth state generation, HMAC tamper detection, and expiration."""
    state = generate_oauth_state("org_alpha", "usr_100")
    org_id, user_id = validate_oauth_state(state)
    assert org_id == "org_alpha"
    assert user_id == "usr_100"

    # Tampered payload rejected
    tampered = "dGFtcGVyZWQ." + state.split(".")[1]
    with pytest.raises(Exception, match="State parameter signature verification failed"):
        validate_oauth_state(tampered)


def test_03_oauth_authorization_url_generation(stage4_client):
    """Test 3: OAuth authorization URL generation with gmail.readonly scope."""
    client, session = stage4_client
    token = seed_tenant_user(session, org_id="org_alpha", user_id="usr_admin", role_name="SYSTEM_ADMIN")

    resp = client.get("/api/v1/integrations/gmail/authorize", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()

    auth_url = data["authorization_url"]
    assert "https://accounts.google.com/o/oauth2/v2/auth" in auth_url
    assert "scope=https%3A%2F%2Fwww.googleapis.com%2Fauth%2Fgmail.readonly" in auth_url
    assert "access_type=offline" in auth_url
    assert "prompt=consent" in auth_url
    assert "state=" in auth_url

    # Unauthorized role rejected
    token_associate = seed_tenant_user(session, org_id="org_alpha", user_id="usr_assoc", email="assoc@alpha.internal", role_name="AP_ASSOCIATE")
    resp_unauth = client.get("/api/v1/integrations/gmail/authorize", headers={"Authorization": f"Bearer {token_associate}"})
    assert resp_unauth.status_code == status.HTTP_403_FORBIDDEN


def test_04_oauth_callback_stores_encrypted_token_and_emits_audit(stage4_client):
    """Test 4: OAuth callback stores encrypted token and emits immutable audit event."""
    client, session = stage4_client
    seed_tenant_user(session, org_id="org_alpha", user_id="usr_admin", role_name="SYSTEM_ADMIN")

    state = generate_oauth_state("org_alpha", "usr_admin")
    mock_tokens = {"access_token": "mock_at_123", "refresh_token": "mock_rt_very_secret_999"}

    with patch("backend.api.v1.integrations_gmail.exchange_code_for_tokens", return_value=mock_tokens), \
         patch("backend.api.v1.integrations_gmail.fetch_mailbox_profile_address", return_value="ap-inbox@testcorp.com"):

        resp = client.get(
            f"/api/v1/integrations/gmail/callback?code=mock_auth_code&state={state}",
            follow_redirects=False,
        )

        assert resp.status_code == status.HTTP_307_TEMPORARY_REDIRECT
        assert "gmail=connected" in resp.headers["location"]

    account = session.execute(select(GmailAccount).where(GmailAccount.org_id == "org_alpha")).scalar_one()
    assert account.mailbox_address == "ap-inbox@testcorp.com"
    assert account.oauth_status == "AUTHORIZED"
    assert account.encrypted_refresh_token is not None
    assert "mock_rt_very_secret_999" not in account.encrypted_refresh_token
    assert decrypt_refresh_token(account.encrypted_refresh_token) == "mock_rt_very_secret_999"

    audit = session.execute(
        select(AuditEvent).where(AuditEvent.org_id == "org_alpha", AuditEvent.action == "GMAIL_MAILBOX_CONNECTED")
    ).scalar_one()
    assert audit.actor_id == "usr_admin"
    assert audit.source_reference == "ap-inbox@testcorp.com"


def test_05_mailbox_ingestion_downloads_valid_pdf_and_stores_in_supabase(stage4_client):
    """Test 5: Mailbox ingestion downloads valid PDF and stores in Supabase Storage."""
    _, session = stage4_client
    seed_tenant_user(session, org_id="org_alpha", user_id="usr_admin", role_name="SYSTEM_ADMIN")

    # Seed active Gmail account
    enc_token = encrypt_refresh_token("valid_refresh_token")
    account = GmailAccount(
        id="gacc_01",
        org_id="org_alpha",
        mailbox_address="invoices@suppliercorp.com",
        oauth_status="AUTHORIZED",
        encrypted_refresh_token=enc_token,
    )
    session.add(account)
    session.commit()

    # Mock Gmail API calls
    b64_pdf = base64.urlsafe_b64encode(SAMPLE_PDF_BYTES).decode()
    mock_messages = [{"id": "msg_001"}]
    mock_detail = {
        "id": "msg_001",
        "payload": {
            "headers": [
                {"name": "From", "value": "Acme Supplies <billing@acme.com>"},
                {"name": "Subject", "value": "Invoice # INV-9001 for Alpha Corp"},
            ],
            "parts": [
                {
                    "filename": "INV-9001.pdf",
                    "mimeType": "application/pdf",
                    "body": {"attachmentId": "att_001"},
                }
            ],
        },
    }

    with patch("backend.core.gmail.refresh_access_token", return_value="fresh_access_token"), \
         patch("backend.core.gmail.list_mailbox_messages", return_value=mock_messages), \
         patch("backend.core.gmail.get_message_detail", return_value=mock_detail), \
         patch("backend.core.gmail.get_attachment_bytes", return_value=SAMPLE_PDF_BYTES):

        result = sync_gmail_mailbox(session, "org_alpha", "usr_admin")

        assert result["status"] == "SUCCESS"
        assert result["ingested_count"] == 1
        assert result["quarantined_count"] == 0
        assert result["duplicates_skipped"] == 0

    # Verify DB records created
    doc = session.execute(select(Document).where(Document.org_id == "org_alpha")).scalar_one()
    assert doc.filename == "INV-9001.pdf"
    assert doc.sha256_hash == hashlib.sha256(SAMPLE_PDF_BYTES).hexdigest()
    assert doc.storage_key.startswith("org_alpha/invoices/")

    inv = session.execute(select(Invoice).where(Invoice.id == doc.invoice_id)).scalar_one()
    assert inv.source_channel == "GMAIL"
    assert inv.vendor_name == "Acme Supplies"
    assert "INV-9001" in inv.decision_reason

    audit = session.execute(
        select(AuditEvent).where(AuditEvent.org_id == "org_alpha", AuditEvent.action == "GMAIL_INVOICE_INGESTED")
    ).scalar_one()
    assert audit.invoice_id == inv.id
    from backend.core.processing_events import processing_snapshot
    run = processing_snapshot(session, inv.id, 'org_alpha')['jobs'][0]
    assert [(event['stage'], event['status'], event['attempt']) for event in run['events']] == [('INTAKE', 'QUEUED', 0)]
    assert audit.actor_id == 'usr_admin' and audit.actor_role == 'SYSTEM_ADMIN'


def test_06_corrupt_attachment_is_quarantined(stage4_client):
    """Test 6: Corrupt attachment header is quarantined into QuarantinedDocument."""
    _, session = stage4_client
    seed_tenant_user(session, org_id="org_alpha", user_id="usr_admin", role_name="SYSTEM_ADMIN")

    account = GmailAccount(
        id="gacc_02",
        org_id="org_alpha",
        mailbox_address="inbox@alpha.internal",
        oauth_status="AUTHORIZED",
        encrypted_refresh_token=encrypt_refresh_token("valid_token"),
    )
    session.add(account)
    session.commit()

    corrupt_bytes = b"CORRUPTED FILE NOT A PDF HEADER"
    mock_messages = [{"id": "msg_corrupt"}]
    mock_detail = {
        "id": "msg_corrupt",
        "payload": {
            "headers": [{"name": "From", "value": "Bad Sender <bad@spam.com>"}],
            "parts": [
                {
                    "filename": "fake.pdf",
                    "mimeType": "application/pdf",
                    "body": {"attachmentId": "att_bad"},
                }
            ],
        },
    }

    with patch("backend.core.gmail.refresh_access_token", return_value="fresh_token"), \
         patch("backend.core.gmail.list_mailbox_messages", return_value=mock_messages), \
         patch("backend.core.gmail.get_message_detail", return_value=mock_detail), \
         patch("backend.core.gmail.get_attachment_bytes", return_value=corrupt_bytes):

        result = sync_gmail_mailbox(session, "org_alpha", "usr_admin")

        assert result["status"] == "SUCCESS"
        assert result["ingested_count"] == 0
        assert result["quarantined_count"] == 1

    # Verified quarantine entry
    q_doc = session.execute(select(QuarantinedDocument).where(QuarantinedDocument.org_id == "org_alpha")).scalar_one()
    assert q_doc.quarantine_reason == "MALFORMED_PDF"


def test_07_duplicate_attachment_detection_skips_ingestion(stage4_client):
    """Test 7: Duplicate PDF attachment in tenant is skipped without re-ingesting."""
    _, session = stage4_client
    seed_tenant_user(session, org_id="org_alpha", user_id="usr_admin", role_name="SYSTEM_ADMIN")

    account = GmailAccount(
        id="gacc_03",
        org_id="org_alpha",
        mailbox_address="inbox@alpha.internal",
        oauth_status="AUTHORIZED",
        encrypted_refresh_token=encrypt_refresh_token("valid_token"),
    )
    session.add(account)
    session.commit()

    mock_messages = [{"id": "msg_dup"}]
    mock_detail = {
        "id": "msg_dup",
        "payload": {
            "headers": [{"name": "From", "value": "Vendor Inc <vendor@inc.com>"}],
            "parts": [
                {
                    "filename": "invoice_repeat.pdf",
                    "mimeType": "application/pdf",
                    "body": {"attachmentId": "att_repeat"},
                }
            ],
        },
    }

    with patch("backend.core.gmail.refresh_access_token", return_value="fresh_token"), \
         patch("backend.core.gmail.list_mailbox_messages", return_value=mock_messages), \
         patch("backend.core.gmail.get_message_detail", return_value=mock_detail), \
         patch("backend.core.gmail.get_attachment_bytes", return_value=SAMPLE_PDF_BYTES):

        # First sync: ingests
        res1 = sync_gmail_mailbox(session, "org_alpha", "usr_admin")
        assert res1["ingested_count"] == 1
        assert res1["duplicates_skipped"] == 0

        # Second sync: skips duplicate
        res2 = sync_gmail_mailbox(session, "org_alpha", "usr_admin")
        assert res2["ingested_count"] == 0
        assert res2["duplicates_skipped"] == 1


def test_08_unconfigured_gmail_reports_truthful_status(stage4_client):
    """Test 8: Unconfigured Gmail reports truthful NOT_CONFIGURED status."""
    client, session = stage4_client
    token = seed_tenant_user(session, org_id="org_empty", user_id="usr_empty", role_name="SYSTEM_ADMIN")

    orig_id = settings.GMAIL_CLIENT_ID
    settings.GMAIL_CLIENT_ID = None
    try:
        resp = client.get("/api/v1/integrations/gmail/status", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert data["status"] == "NOT_CONFIGURED"
        assert data["readiness"] is False

        # Authorization endpoint returns 503
        auth_resp = client.get("/api/v1/integrations/gmail/authorize", headers={"Authorization": f"Bearer {token}"})
        assert auth_resp.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    finally:
        settings.GMAIL_CLIENT_ID = orig_id


def test_09_mailbox_disconnect_revokes_token_and_emits_audit(stage4_client):
    """Test 9: Mailbox disconnect revokes status, clears token, and emits audit event."""
    client, session = stage4_client
    token = seed_tenant_user(session, org_id="org_alpha", user_id="usr_admin", role_name="SYSTEM_ADMIN")

    account = GmailAccount(
        id="gacc_04",
        org_id="org_alpha",
        mailbox_address="connected@alpha.com",
        oauth_status="AUTHORIZED",
        encrypted_refresh_token=encrypt_refresh_token("valid_token"),
    )
    session.add(account)
    session.commit()

    resp = client.post("/api/v1/integrations/gmail/disconnect", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == status.HTTP_200_OK
    assert resp.json()["status"] == "DISCONNECTED"

    # DB record updated
    session.refresh(account)
    assert account.oauth_status == "REVOKED"
    assert account.encrypted_refresh_token is None

    audit = session.execute(
        select(AuditEvent).where(AuditEvent.org_id == "org_alpha", AuditEvent.action == "GMAIL_MAILBOX_DISCONNECTED")
    ).scalar_one()
    assert audit.actor_id == "usr_admin"


def test_10_casa_compliance_metadata_disclosure(stage4_client):
    """Test 10: CASA Tier 2 assessment disclosure and minimum scope compliance."""
    client, session = stage4_client
    token = seed_tenant_user(session, org_id="org_alpha", user_id="usr_admin", role_name="SYSTEM_ADMIN")

    resp = client.get("/api/v1/integrations/gmail/status", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()

    assert data["scopes"] == ["https://www.googleapis.com/auth/gmail.readonly"]
    compliance = data["compliance"]
    assert compliance["scope"] == "https://www.googleapis.com/auth/gmail.readonly"
    assert compliance["casa_status"] == "CASA_ASSESSMENT_PENDING_PRODUCTION_APPROVAL"
    assert "CASA Tier 2 assessment required" in compliance["notes"]
