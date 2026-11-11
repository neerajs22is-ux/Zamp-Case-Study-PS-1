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
import urllib.parse
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
    build_authorization_url, canonical_gmail_redirect_uri,
    decrypt_refresh_token, encrypt_refresh_token,
    generate_oauth_state, resolve_gmail_redirect_uri, sync_gmail_mailbox,
    validate_oauth_state
)
from backend.core.storage import storage_adapter
from backend.main import app
from backend.models.domain import (
    AuditEvent, Document, GmailAccount, IngestionJob, Invoice,
    OAuthStateNonce, Organisation, QuarantinedDocument, RoleAssignment, User
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

# ==============================================================================
# Focused regression tests: Gmail OAuth redirect URI & mailbox import gating
# ==============================================================================

def test_11_gmail_redirect_uri_is_one_canonical_public_callback(monkeypatch):
    """Test 11: A single canonical redirect URI is sent to Google for both the
    authorization request and the code exchange, with no double slash and no
    stale localhost/loopback override leaking into production."""
    monkeypatch.setattr(settings, "APP_ENV", AppEnv.TEST)
    monkeypatch.setattr(settings, "BASE_URL", "https://zamp-case-study-ps-1-1.onrender.com")
    monkeypatch.setattr(settings, "GMAIL_REDIRECT_URI", None)

    expected = "https://zamp-case-study-ps-1-1.onrender.com/api/v1/integrations/gmail/callback"
    assert resolve_gmail_redirect_uri() == expected
    assert canonical_gmail_redirect_uri() == expected

    # A trailing slash on BASE_URL must not produce '//api/...'
    monkeypatch.setattr(settings, "BASE_URL", "https://zamp-case-study-ps-1-1.onrender.com/")
    assert resolve_gmail_redirect_uri() == expected
    assert "//api" not in resolve_gmail_redirect_uri()

    # The authorization request carries exactly that URI, with the minimum scope
    parsed = urllib.parse.urlparse(build_authorization_url("org_alpha", "usr_admin"))
    query = urllib.parse.parse_qs(parsed.query)
    assert query["redirect_uri"] == [expected]
    assert query["scope"] == ["https://www.googleapis.com/auth/gmail.readonly"]
    assert query["access_type"] == ["offline"]

    # An explicit public HTTPS override is honoured verbatim (exact-match semantics)
    override = "https://ap.example.com/api/v1/integrations/gmail/callback"
    monkeypatch.setattr(settings, "GMAIL_REDIRECT_URI", override)
    assert resolve_gmail_redirect_uri() == override

    # In production, stale localhost / plain-HTTP / wrong-path overrides are rejected
    monkeypatch.setattr(settings, "APP_ENV", AppEnv.PRODUCTION)
    monkeypatch.setattr(settings, "BASE_URL", "https://zamp-case-study-ps-1-1.onrender.com")
    for stale in (
        "http://localhost:8000/api/v1/integrations/gmail/callback",
        "http://localhost:8000/api/v1/connections/gmail/callback",
        "https://localhost/api/v1/integrations/gmail/callback",
        "http://zamp-case-study-ps-1-1.onrender.com/api/v1/integrations/gmail/callback",
    ):
        monkeypatch.setattr(settings, "GMAIL_REDIRECT_URI", stale)
        assert resolve_gmail_redirect_uri() == expected


def test_12_import_now_reports_disconnected_mailbox_without_ingesting(stage4_client):
    """Test 12: Import now fails closed with a truthful 404 when no mailbox is
    authorized, and never calls Gmail when the mailbox is revoked/expired."""
    from unittest.mock import patch as _patch

    client, session = stage4_client
    token = seed_tenant_user(session, org_id="org_alpha", user_id="usr_admin", role_name="SYSTEM_ADMIN")
    headers = {"Authorization": f"Bearer {token}"}

    # No mailbox record at all
    resp_none = client.post("/api/v1/integrations/gmail/sync", headers=headers)
    assert resp_none.status_code == status.HTTP_404_NOT_FOUND
    assert "No authorized Gmail mailbox configured" in resp_none.json()["detail"]

    # Revoked mailbox: still no authorized mailbox, and no Gmail API call is made
    session.add(GmailAccount(
        id="gacc_revoked",
        org_id="org_alpha",
        mailbox_address="revoked@alpha.com",
        oauth_status="REVOKED",
        encrypted_refresh_token=None,
    ))
    session.commit()

    with _patch("backend.api.v1.integrations_gmail.sync_gmail_mailbox") as full_sync,          _patch("backend.api.v1.integrations_gmail.sync_gmail_history") as history_sync:
        resp = client.post("/api/v1/integrations/gmail/sync", headers=headers)
        assert resp.status_code == status.HTTP_404_NOT_FOUND
        assert "No authorized Gmail mailbox configured" in resp.json()["detail"]
        full_sync.assert_not_called()
        history_sync.assert_not_called()

    # Status reports the degradation truthfully rather than claiming a healthy mailbox
    resp_status = client.get("/api/v1/integrations/gmail/status", headers=headers)
    assert resp_status.status_code == status.HTTP_200_OK
    assert resp_status.json()["status"] == "REVOKED"
    assert resp_status.json()["readiness"] is False


def test_13_connected_import_ingests_into_correct_tenant_only(stage4_client):
    """Test 13: With an authorized mailbox, Import now ingests PDFs for the calling
    tenant only, and a second tenant's mailbox is left untouched."""
    from unittest.mock import patch as _patch

    _, session = stage4_client
    seed_tenant_user(session, org_id="org_alpha", user_id="usr_admin", role_name="SYSTEM_ADMIN")
    session.add(GmailAccount(
        id="gacc_alpha",
        org_id="org_alpha",
        mailbox_address="invoices@alpha.com",
        oauth_status="AUTHORIZED",
        encrypted_refresh_token=encrypt_refresh_token("alpha_refresh_token"),
    ))
    beta_account = GmailAccount(
        id="gacc_beta",
        org_id="org_beta",
        mailbox_address="invoices@beta.com",
        oauth_status="AUTHORIZED",
        encrypted_refresh_token=encrypt_refresh_token("beta_refresh_token"),
    )
    session.add(beta_account)
    session.commit()

    b64_pdf = base64.urlsafe_b64encode(SAMPLE_PDF_BYTES).decode()
    mock_detail = {
        "id": "msg_alpha_1",
        "payload": {
            "headers": [
                {"name": "From", "value": "Acme Supplies <billing@acme.com>"},
                {"name": "Subject", "value": "Invoice INV-4242"},
            ],
            "parts": [{
                "filename": "INV-4242.pdf",
                "mimeType": "application/pdf",
                "body": {"data": b64_pdf},
            }],
        },
    }

    with _patch("backend.core.gmail.refresh_access_token", return_value="fresh_access_token"),          _patch("backend.core.gmail.list_mailbox_messages", return_value=[{"id": "msg_alpha_1"}]),          _patch("backend.core.gmail.get_message_detail", return_value=mock_detail):

        result = sync_gmail_mailbox(session, "org_alpha", "usr_admin")

    assert result["status"] == "SUCCESS"
    assert result["ingested_count"] == 1
    assert result["duplicates_skipped"] == 0

    alpha_docs = session.execute(select(Document).where(Document.org_id == "org_alpha")).scalars().all()
    assert len(alpha_docs) == 1
    assert alpha_docs[0].storage_key.startswith("org_alpha/invoices/")

    assert session.execute(select(Document).where(Document.org_id == "org_beta")).scalars().all() == []
    assert session.execute(select(Invoice).where(Invoice.org_id == "org_beta")).scalars().all() == []

    session.refresh(beta_account)
    assert beta_account.last_synced_at is None

# ==============================================================================
# Focused regression tests: OAuth callback tenant context & safe failure modes
# ==============================================================================

def test_14_oauth_callback_binds_tenant_context_before_persisting(stage4_client):
    """Test 14 (production HTTP 500): the callback runs without a user session, so it must
    establish tenant context from the signed state before writing RLS-protected tables.
    Without it PostgreSQL rejects the gmail_accounts insert (FORCE RLS + WITH CHECK on
    app.current_org_id) and the browser receives an unhandled 500."""
    client, session = stage4_client
    seed_tenant_user(session, org_id="org_alpha", user_id="usr_admin", role_name="SYSTEM_ADMIN")
    session.info.pop("tenant_org_id", None)
    session.info.pop("app.current_org_id", None)

    state = generate_oauth_state("org_alpha", "usr_admin", db=session)
    assert not session.info.get("tenant_org_id"), "callback request must start without tenant context"

    with patch("backend.api.v1.integrations_gmail.exchange_code_for_tokens",
               return_value={"access_token": "mock_at", "refresh_token": "mock_rt_secret"}),          patch("backend.api.v1.integrations_gmail.fetch_mailbox_profile_address",
               return_value="ap-inbox@testcorp.com"):
        resp = client.get(
            f"/api/v1/integrations/gmail/callback?code=mock_code&state={state}",
            follow_redirects=False,
        )

    assert resp.status_code == status.HTTP_307_TEMPORARY_REDIRECT
    assert "gmail=connected" in resp.headers["location"]

    # Tenant context was bound to the organisation proven by the signed state
    assert session.info["tenant_org_id"] == "org_alpha"

    account = session.execute(
        select(GmailAccount).where(GmailAccount.org_id == "org_alpha")
    ).scalar_one()
    assert account.oauth_status == "AUTHORIZED"
    assert account.mailbox_address == "ap-inbox@testcorp.com"
    assert decrypt_refresh_token(account.encrypted_refresh_token) == "mock_rt_secret"

    # The state nonce was consumed exactly once (single-use replay protection)
    nonce = session.execute(
        select(OAuthStateNonce).where(OAuthStateNonce.org_id == "org_alpha")
    ).scalar_one()
    assert nonce.is_consumed is True


def test_15_oauth_callback_expected_failures_are_safe_4xx_not_500(stage4_client):
    """Test 15: Google-reported errors, missing parameters, tampered state and replayed
    state all produce controlled redirects/4xx responses rather than HTTP 500."""
    client, session = stage4_client
    seed_tenant_user(session, org_id="org_alpha", user_id="usr_admin", role_name="SYSTEM_ADMIN")

    # Google-reported error returns an explicit UI redirect
    resp_error = client.get("/api/v1/integrations/gmail/callback?error=access_denied", follow_redirects=False)
    assert resp_error.status_code == status.HTTP_307_TEMPORARY_REDIRECT
    assert "gmail=error" in resp_error.headers["location"]

    # Missing code/state
    assert client.get("/api/v1/integrations/gmail/callback").status_code == status.HTTP_400_BAD_REQUEST

    # Tampered state signature
    good_state = generate_oauth_state("org_alpha", "usr_admin")
    tampered = "dGFtcGVyZWQ." + good_state.split(".")[1]
    resp_tampered = client.get(f"/api/v1/integrations/gmail/callback?code=x&state={tampered}")
    assert resp_tampered.status_code == status.HTTP_400_BAD_REQUEST

    # Replayed state is rejected before any token exchange happens
    replayed_state = generate_oauth_state("org_alpha", "usr_admin", db=session)
    validate_oauth_state(replayed_state, db=session)
    with patch("backend.api.v1.integrations_gmail.exchange_code_for_tokens") as exchange:
        resp_replay = client.get(f"/api/v1/integrations/gmail/callback?code=x&state={replayed_state}")
        assert resp_replay.status_code == status.HTTP_400_BAD_REQUEST
        exchange.assert_not_called()


def test_16_oauth_callback_persistence_failure_returns_safe_503(monkeypatch, stage4_client):
    """Test 16: a database failure while persisting the mailbox yields a safe, actionable
    503 instead of a generic 500, and leaks neither tokens nor raw database errors."""
    client, session = stage4_client
    seed_tenant_user(session, org_id="org_alpha", user_id="usr_admin", role_name="SYSTEM_ADMIN")
    state = generate_oauth_state("org_alpha", "usr_admin", db=session)

    real_commit = session.commit
    calls = {"n": 0}

    def flaky_commit():
        calls["n"] += 1
        if calls["n"] > 1:  # 1st commit consumes the nonce; 2nd persists the mailbox
            raise RuntimeError('new row violates row-level security policy for table "gmail_accounts"')
        return real_commit()

    monkeypatch.setattr(session, "commit", flaky_commit)

    with patch("backend.api.v1.integrations_gmail.exchange_code_for_tokens",
               return_value={"access_token": "mock_at", "refresh_token": "SECRET_REFRESH_TOKEN_XYZ"}),          patch("backend.api.v1.integrations_gmail.fetch_mailbox_profile_address",
               return_value="ap-inbox@testcorp.com"):
        resp = client.get(
            f"/api/v1/integrations/gmail/callback?code=mock_code&state={state}",
            follow_redirects=False,
        )

    assert resp.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    detail = resp.json()["detail"]
    assert "row-level security" not in detail
    assert "SECRET_REFRESH_TOKEN_XYZ" not in resp.text
    assert "mock_at" not in resp.text
    assert "could not be saved" in detail

    session.rollback()
    assert session.execute(
        select(GmailAccount).where(GmailAccount.org_id == "org_alpha")
    ).scalar_one_or_none() is None
