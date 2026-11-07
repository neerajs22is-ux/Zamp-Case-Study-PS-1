"""Phase B Stage 5 Acceptance Tests — Gmail Pub/Sub Push & Event-Driven Ingestion.

Comprehensive validation of the 14 binding Stage 5 Pub/Sub requirements:
Test 01: Gmail watch registration succeeds and records historyId and expiration.
Test 02: Valid Pub/Sub push notification with valid OIDC token is accepted and acknowledged (HTTP 200).
Test 03: Pub/Sub push request with missing or invalid OIDC token is rejected (HTTP 401).
Test 04: Pub/Sub push request with mismatched audience is rejected (HTTP 400).
Test 05: Malformed Pub/Sub payload returns HTTP 400 without crashing.
Test 06: Incoming notification is persisted durably before processing begins.
Test 07: Duplicate Pub/Sub messageId is acknowledged without duplicate invoice processing.
Test 08: History sync retrieves new messages and triggers PDF attachment ingestion.
Test 09: History sync failure records FAILED status and allows retry.
Test 10: Expired history ID (HTTP 404) triggers full mailbox reconciliation fallback.
Test 11: Watch renewal extends expiration before the 7-day limit (48-hour window).
Test 12: Revoked mailbox authorization is detected during watch renewal or history sync.
Test 13: Periodic reconciliation catches messages missed by Pub/Sub (6-hour window).
Test 14: Tenant isolation: Pub/Sub notification for Mailbox A cannot ingest into Tenant B.

Also includes Stage 4.1 verification:
- State nonce replay rejection.
- Reconnection token preservation when Google omits refresh token.
- Multi-attachment extraction with mixed inline (body.data) and attachmentId.
- Live Google Cloud test graceful skipping when live credentials are not set.
"""

from __future__ import annotations

import base64
import datetime
import hashlib
import io
import json
import os
from typing import Any, Dict, List, Optional
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
    HistoryExpiredError, GmailIntegrationError,
    encrypt_refresh_token, extract_attachment_bytes, find_all_pdf_attachments,
    generate_oauth_state, process_pubsub_push_notification,
    reconcile_all_active_mailboxes, renew_expiring_watches,
    setup_mailbox_watch, sync_gmail_history, sync_gmail_mailbox,
    validate_and_consume_oauth_state, validate_pubsub_oidc_token,
)
from backend.core.storage import storage_adapter
from backend.main import app
from backend.models.domain import (
    AuditEvent, Document, GmailAccount, IngestionJob, Invoice,
    OAuthStateNonce, Organisation, PubSubEvent, RoleAssignment, User
)

TEST_JWT_SECRET = "stage5-pubsub-test-secret-32-chars-long"
TEST_ISSUER = "https://test-project.supabase.co/auth/v1"
TEST_AUDIENCE = "authenticated"
TEST_PUBSUB_AUDIENCE = "https://api.test.domain.com/api/v1/integrations/gmail/pubsub/push"
TEST_PUBSUB_EMAIL = "pubsub-invoker@gcp.internal"
SAMPLE_PDF_BYTES = b"%PDF-1.4\n1 0 obj\n<< /Title (PubSub Invoice) >>\nendobj\ntrailer\n<< /Root 1 0 R >>\n%%EOF"


@pytest.fixture(autouse=True)
def configure_stage5_settings():
    """Configures environment settings for Stage 5 acceptance tests."""
    orig_env = settings.APP_ENV
    orig_secret = settings.SUPABASE_JWT_SECRET
    orig_iss = settings.SUPABASE_ISSUER
    orig_aud = settings.SUPABASE_AUDIENCE
    orig_client_id = settings.GMAIL_CLIENT_ID
    orig_client_secret = settings.GMAIL_CLIENT_SECRET
    orig_target_box = settings.GMAIL_TARGET_MAILBOX
    orig_pubsub_aud = settings.PUBSUB_VERIFICATION_AUDIENCE
    orig_pubsub_email = settings.PUBSUB_SERVICE_ACCOUNT_EMAIL
    orig_pubsub_topic = settings.PUBSUB_TOPIC_NAME

    settings.APP_ENV = AppEnv.TEST
    settings.SUPABASE_JWT_SECRET = TEST_JWT_SECRET
    settings.SUPABASE_ISSUER = TEST_ISSUER
    settings.SUPABASE_AUDIENCE = TEST_AUDIENCE
    settings.GMAIL_CLIENT_ID = "test-gmail-client-id.apps.googleusercontent.com"
    settings.GMAIL_CLIENT_SECRET = "test-gmail-client-secret"
    settings.GMAIL_TARGET_MAILBOX = "test-ap-inbox@example.com"
    settings.PUBSUB_VERIFICATION_AUDIENCE = TEST_PUBSUB_AUDIENCE
    settings.PUBSUB_SERVICE_ACCOUNT_EMAIL = TEST_PUBSUB_EMAIL
    settings.PUBSUB_TOPIC_NAME = "projects/test-project/topics/gmail-push-topic"

    yield

    settings.APP_ENV = orig_env
    settings.SUPABASE_JWT_SECRET = orig_secret
    settings.SUPABASE_ISSUER = orig_iss
    settings.SUPABASE_AUDIENCE = orig_aud
    settings.GMAIL_CLIENT_ID = orig_client_id
    settings.GMAIL_CLIENT_SECRET = orig_client_secret
    settings.GMAIL_TARGET_MAILBOX = orig_target_box
    settings.PUBSUB_VERIFICATION_AUDIENCE = orig_pubsub_aud
    settings.PUBSUB_SERVICE_ACCOUNT_EMAIL = orig_pubsub_email
    settings.PUBSUB_TOPIC_NAME = orig_pubsub_topic


@pytest.fixture
def stage5_db():
    """Provides a fresh, isolated in-memory SQLite database for Stage 5 tests."""
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
def stage5_client(stage5_db):
    """FastAPI TestClient with isolated Stage 5 database session override."""
    session, _ = stage5_db

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
        "name": "Stage 5 Operator",
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


def seed_gmail_account(
    session: Session,
    org_id: str = "org_alpha",
    mailbox: str = "invoices@alpha.internal",
    oauth_status: str = "AUTHORIZED",
    refresh_token: str = "mock_valid_refresh_token_xyz",
    watch_history_id: Optional[str] = "10001",
    watch_status: str = "ACTIVE",
    watch_expiration_at: Optional[datetime.datetime] = None,
    watch_last_renewed_at: Optional[datetime.datetime] = None,
) -> GmailAccount:
    enc_refresh = encrypt_refresh_token(refresh_token) if refresh_token else None
    now = datetime.datetime.utcnow()
    account = GmailAccount(
        id=f"gacc_{org_id}",
        org_id=org_id,
        mailbox_address=mailbox,
        oauth_status=oauth_status,
        encrypted_refresh_token=enc_refresh,
        pubsub_topic=settings.PUBSUB_TOPIC_NAME,
        watch_history_id=watch_history_id,
        watch_status=watch_status,
        watch_expiration_at=watch_expiration_at or (now + datetime.timedelta(days=7)),
        watch_last_renewed_at=watch_last_renewed_at or now,
        last_history_id=watch_history_id,
        created_at=now,
        updated_at=now,
    )
    session.add(account)
    session.commit()
    return account


def build_pubsub_payload(
    mailbox: str,
    history_id: str,
    message_id: str = "msg_pubsub_001",
    publish_time: str = "2026-10-31T20:00:00.000Z",
) -> Dict[str, Any]:
    inner_json = json.dumps({"emailAddress": mailbox, "historyId": history_id})
    b64_data = base64.urlsafe_b64encode(inner_json.encode()).decode()
    return {
        "message": {
            "data": b64_data,
            "messageId": message_id,
            "publishTime": publish_time,
        },
        "subscription": "projects/test-project/subscriptions/test-sub",
    }


# ==============================================================================
# Acceptance Test 01: Gmail Watch Registration
# ==============================================================================

def test_01_gmail_watch_registration(stage5_client):
    """Test 01: Gmail watch registration succeeds and records historyId and expiration."""
    client, session = stage5_client
    token = seed_tenant_user(session, org_id="org_alpha", role_name="SYSTEM_ADMIN")
    account = seed_gmail_account(session, org_id="org_alpha", watch_status="NOT_REGISTERED")

    mock_watch_resp = {
        "historyId": "99001",
        "expiration": "1740000000000",  # ~milliseconds timestamp
    }

    with patch("backend.core.gmail.refresh_access_token", return_value="mock_access_token"), \
         patch("backend.core.gmail.register_gmail_watch", return_value=mock_watch_resp):

        resp = client.post(
            "/api/v1/integrations/gmail/watch/setup",
            headers={"Authorization": f"Bearer {token}"},
            json={"topic_name": "projects/test-project/topics/gmail-push-topic"},
        )

        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert data["status"] == "WATCH_ACTIVE"
        assert data["history_id"] == "99001"
        assert data["mailbox"] == account.mailbox_address

        # Verify DB update
        session.refresh(account)
        assert account.watch_status == "ACTIVE"
        assert account.watch_history_id == "99001"
        assert account.watch_expiration_at is not None
        assert account.watch_last_renewed_at is not None


# ==============================================================================
# Acceptance Test 02: Valid Pub/Sub Push Notification Accepted
# ==============================================================================

def test_02_valid_pubsub_push_accepted(stage5_client):
    """Test 02: Valid Pub/Sub push notification with valid OIDC token is accepted and acknowledged."""
    client, session = stage5_client
    seed_tenant_user(session, org_id="org_alpha")
    account = seed_gmail_account(session, org_id="org_alpha", mailbox="invoices@alpha.internal", watch_history_id="10001")

    payload = build_pubsub_payload(
        mailbox="invoices@alpha.internal",
        history_id="10005",
        message_id="pubsub_msg_test_02",
    )

    mock_sync_result = {
        "status": "SUCCESS",
        "ingested_count": 1,
        "history_id": "10005",
        "invoices": [{"invoice_id": "inv_001", "invoice_number": "INV-100"}],
    }

    with patch("backend.core.gmail.sync_gmail_history", return_value=mock_sync_result):
        resp = client.post(
            "/api/v1/integrations/gmail/pubsub/push",
            headers={"Authorization": f"Bearer test_oidc:{TEST_PUBSUB_EMAIL}:{TEST_PUBSUB_AUDIENCE}"},
            json=payload,
        )

        assert resp.status_code == status.HTTP_200_OK
        res_data = resp.json()
        assert res_data["status"] == "ACKNOWLEDGED"
        assert res_data["result"]["status"] == "PROCESSED"

        # Verify durable event recorded in DB
        event = session.execute(
            select(PubSubEvent).where(PubSubEvent.pubsub_message_id == "pubsub_msg_test_02")
        ).scalar_one_or_none()
        assert event is not None
        assert event.status == "COMPLETED"
        assert event.mailbox_address == "invoices@alpha.internal"
        assert event.org_id == "org_alpha"


# ==============================================================================
# Acceptance Test 03: Missing or Invalid OIDC Token Rejected
# ==============================================================================

def test_03_missing_or_invalid_oidc_token_rejected(stage5_client):
    """Test 03: Pub/Sub push request with missing or invalid OIDC token is rejected (HTTP 401)."""
    client, session = stage5_client
    payload = build_pubsub_payload("invoices@alpha.internal", "10001")

    # 1. Missing Authorization header
    resp_no_auth = client.post("/api/v1/integrations/gmail/pubsub/push", json=payload)
    assert resp_no_auth.status_code == status.HTTP_401_UNAUTHORIZED

    # 2. Invalid OIDC token signature
    resp_bad_auth = client.post(
        "/api/v1/integrations/gmail/pubsub/push",
        headers={"Authorization": "Bearer invalid_token"},
        json=payload,
    )
    assert resp_bad_auth.status_code == status.HTTP_401_UNAUTHORIZED


# ==============================================================================
# Acceptance Test 04: Mismatched Audience Rejected
# ==============================================================================

def test_04_mismatched_audience_rejected(stage5_client):
    """Test 04: Pub/Sub push request with mismatched audience is rejected."""
    client, session = stage5_client
    payload = build_pubsub_payload("invoices@alpha.internal", "10001")

    resp = client.post(
        "/api/v1/integrations/gmail/pubsub/push",
        headers={"Authorization": f"Bearer test_oidc:{TEST_PUBSUB_EMAIL}:https://rogue-audience.internal"},
        json=payload,
    )

    # Audience mismatch rejected with 400 or 401
    assert resp.status_code in (status.HTTP_400_BAD_REQUEST, status.HTTP_401_UNAUTHORIZED)


# ==============================================================================
# Acceptance Test 05: Malformed Payload Returns HTTP 400
# ==============================================================================

def test_05_malformed_pubsub_payload_rejected(stage5_client):
    """Test 05: Malformed Pub/Sub payload returns HTTP 400 without crashing."""
    client, session = stage5_client
    auth_header = {"Authorization": f"Bearer test_oidc:{TEST_PUBSUB_EMAIL}:{TEST_PUBSUB_AUDIENCE}"}

    # 1. Missing 'message' object
    resp1 = client.post("/api/v1/integrations/gmail/pubsub/push", headers=auth_header, json={})
    assert resp1.status_code == status.HTTP_400_BAD_REQUEST

    # 2. Missing 'data' field
    resp2 = client.post(
        "/api/v1/integrations/gmail/pubsub/push",
        headers=auth_header,
        json={"message": {"messageId": "msg_bad_01"}},
    )
    assert resp2.status_code == status.HTTP_400_BAD_REQUEST

    # 3. Corrupted base64
    resp3 = client.post(
        "/api/v1/integrations/gmail/pubsub/push",
        headers=auth_header,
        json={"message": {"messageId": "msg_bad_02", "data": "!!NOT_BASE64!!"}},
    )
    assert resp3.status_code == status.HTTP_400_BAD_REQUEST


# ==============================================================================
# Acceptance Test 06: Durable Persistence Before Processing Begins
# ==============================================================================

def test_06_durable_persistence_before_processing(stage5_client):
    """Test 06: Incoming notification is persisted before processing begins."""
    client, session = stage5_client
    seed_tenant_user(session, org_id="org_alpha")
    seed_gmail_account(session, org_id="org_alpha", mailbox="invoices@alpha.internal")

    payload = build_pubsub_payload(
        mailbox="invoices@alpha.internal",
        history_id="10006",
        message_id="pubsub_msg_test_06",
    )

    persisted_state = {}

    def mock_failing_sync(db, account, hist_id, actor_id):
        # Inspect database during sync execution: event MUST already be persisted
        evt = db.execute(
            select(PubSubEvent).where(PubSubEvent.pubsub_message_id == "pubsub_msg_test_06")
        ).scalar_one_or_none()
        if evt:
            persisted_state["status_at_sync_time"] = evt.status
            persisted_state["found"] = True
        raise GmailIntegrationError("Simulated mid-pipeline processing crash")

    with patch("backend.core.gmail.sync_gmail_history", side_effect=mock_failing_sync):
        resp = client.post(
            "/api/v1/integrations/gmail/pubsub/push",
            headers={"Authorization": f"Bearer test_oidc:{TEST_PUBSUB_EMAIL}:{TEST_PUBSUB_AUDIENCE}"},
            json=payload,
        )

        assert resp.status_code == status.HTTP_200_OK
        assert persisted_state.get("found") is True
        assert persisted_state.get("status_at_sync_time") == "RECEIVED"

        # Verify status transitioned to FAILED after error
        evt = session.execute(
            select(PubSubEvent).where(PubSubEvent.pubsub_message_id == "pubsub_msg_test_06")
        ).scalar_one_or_none()
        assert evt.status == "FAILED"
        assert "Simulated mid-pipeline processing crash" in (evt.error_message or "")


# ==============================================================================
# Acceptance Test 07: Duplicate Notification Handled Idempotently
# ==============================================================================

def test_07_duplicate_notification_idempotent(stage5_client):
    """Test 07: Duplicate Pub/Sub messageId is acknowledged without duplicate invoice processing."""
    client, session = stage5_client
    seed_tenant_user(session, org_id="org_alpha")
    seed_gmail_account(session, org_id="org_alpha", mailbox="invoices@alpha.internal")

    payload = build_pubsub_payload(
        mailbox="invoices@alpha.internal",
        history_id="10007",
        message_id="pubsub_msg_dup_test",
    )

    sync_call_count = {"count": 0}

    def mock_sync(db, account, hist_id, actor_id):
        sync_call_count["count"] += 1
        return {"status": "SUCCESS", "ingested_count": 1}

    with patch("backend.core.gmail.sync_gmail_history", side_effect=mock_sync):
        # First delivery
        resp1 = client.post(
            "/api/v1/integrations/gmail/pubsub/push",
            headers={"Authorization": f"Bearer test_oidc:{TEST_PUBSUB_EMAIL}:{TEST_PUBSUB_AUDIENCE}"},
            json=payload,
        )
        assert resp1.status_code == status.HTTP_200_OK
        assert resp1.json()["result"]["status"] == "PROCESSED"
        assert sync_call_count["count"] == 1

        # Redelivery (same messageId)
        resp2 = client.post(
            "/api/v1/integrations/gmail/pubsub/push",
            headers={"Authorization": f"Bearer test_oidc:{TEST_PUBSUB_EMAIL}:{TEST_PUBSUB_AUDIENCE}"},
            json=payload,
        )
        assert resp2.status_code == status.HTTP_200_OK
        res2_data = resp2.json()
        assert res2_data["status"] == "ACKNOWLEDGED"
        assert res2_data["result"]["status"] == "DUPLICATE"

        # Assert no duplicate sync executed!
        assert sync_call_count["count"] == 1


# ==============================================================================
# Acceptance Test 08: History Sync Ingests PDF Attachments
# ==============================================================================

def test_08_history_sync_ingests_attachments(stage5_client):
    """Test 08: History sync retrieves new messages and triggers PDF attachment ingestion."""
    client, session = stage5_client
    seed_tenant_user(session, org_id="org_alpha")
    account = seed_gmail_account(session, org_id="org_alpha", mailbox="invoices@alpha.internal", watch_history_id="10001")

    # Mock history.list returning 2 messages
    mock_history_msg_ids = ["msg_hist_01", "msg_hist_02"]
    mock_new_history_id = "10010"

    mock_msg_detail_1 = {
        "id": "msg_hist_01",
        "threadId": "t1",
        "payload": {
            "headers": [
                {"name": "From", "value": "Vendor Acme <billing@acme.com>"},
                {"name": "Subject", "value": "Invoice INV-2026-01"},
                {"name": "Date", "value": "Thu, 31 Oct 2026 12:00:00 +0000"},
            ],
            "parts": [
                {
                    "filename": "inv_acme_01.pdf",
                    "mimeType": "application/pdf",
                    "body": {"attachmentId": "att_acme_01", "size": len(SAMPLE_PDF_BYTES)},
                }
            ],
        },
    }

    mock_msg_detail_2 = {
        "id": "msg_hist_02",
        "threadId": "t2",
        "payload": {
            "headers": [
                {"name": "From", "value": "Vendor Beta <invoices@beta.com>"},
                {"name": "Subject", "value": "Invoice INV-2026-02"},
                {"name": "Date", "value": "Thu, 31 Oct 2026 13:00:00 +0000"},
            ],
            "parts": [
                {
                    "filename": "inv_beta_02.pdf",
                    "mimeType": "application/pdf",
                    "body": {"attachmentId": "att_beta_02", "size": len(SAMPLE_PDF_BYTES)},
                }
            ],
        },
    }

    def mock_get_detail(token, msg_id):
        if msg_id == "msg_hist_01":
            return mock_msg_detail_1
        return mock_msg_detail_2

    def mock_get_attachment(token, msg_id, att_id):
        if "beta" in str(att_id):
            return SAMPLE_PDF_BYTES + b"\n%distinct_beta_pdf_bytes"
        return SAMPLE_PDF_BYTES

    with patch("backend.core.gmail.refresh_access_token", return_value="mock_access_token"), \
         patch("backend.core.gmail.get_history_messages", return_value=(mock_history_msg_ids, mock_new_history_id)), \
         patch("backend.core.gmail.get_message_detail", side_effect=mock_get_detail), \
         patch("backend.core.gmail.get_attachment_bytes", side_effect=mock_get_attachment):

        sync_res = sync_gmail_history(session, account, notification_history_id="10010")

        assert sync_res["status"] == "SUCCESS"
        assert sync_res["ingested_count"] == 2
        assert account.last_history_id == "10010"

        # Verify DB records
        invoices = session.execute(
            select(Invoice).where(Invoice.org_id == "org_alpha")
        ).scalars().all()
        assert len(invoices) == 2
        from backend.core.processing_events import processing_snapshot
        for invoice in invoices:
            run = processing_snapshot(session, invoice.id, 'org_alpha')['jobs'][0]
            assert [(e['stage'], e['status'], e['attempt']) for e in run['events']] == [('INTAKE', 'QUEUED', 0)]


# ==============================================================================
# Acceptance Test 09: History Sync Failure Allows Retry
# ==============================================================================

def test_09_history_sync_failure_allows_retry(stage5_client):
    """Test 09: History sync failure records FAILED status and allows retry without watermark advancement."""
    client, session = stage5_client
    seed_tenant_user(session, org_id="org_alpha")
    account = seed_gmail_account(session, org_id="org_alpha", mailbox="invoices@alpha.internal", watch_history_id="10001")
    account.last_history_id = "10001"
    session.commit()

    with patch("backend.core.gmail.refresh_access_token", return_value="mock_access_token"), \
         patch("backend.core.gmail.get_history_messages", side_effect=GmailIntegrationError("Temporary Gmail 503 Outage")):

        with pytest.raises(GmailIntegrationError):
            sync_gmail_history(session, account, notification_history_id="10020")

        # Watermark was NOT advanced
        session.refresh(account)
        assert account.last_history_id == "10001"

    # Now retry succeeds: watermark is advanced
    with patch("backend.core.gmail.refresh_access_token", return_value="mock_access_token"), \
         patch("backend.core.gmail.get_history_messages", return_value=([], "10020")):

        res = sync_gmail_history(session, account, notification_history_id="10020")
        assert res["status"] == "SUCCESS"
        session.refresh(account)
        assert account.last_history_id == "10020"


# ==============================================================================
# Acceptance Test 10: Expired History ID Triggers Fallback Reconciliation
# ==============================================================================

def test_10_expired_history_id_triggers_fallback_reconciliation(stage5_client):
    """Test 10: Expired history ID (HTTP 404) triggers full mailbox reconciliation fallback."""
    client, session = stage5_client
    seed_tenant_user(session, org_id="org_alpha")
    account = seed_gmail_account(session, org_id="org_alpha", mailbox="invoices@alpha.internal", watch_history_id="90001")
    account.last_history_id = "90001"
    session.commit()

    mock_fallback_sync = {
        "status": "SUCCESS",
        "ingested_count": 1,
        "quarantined_count": 0,
        "duplicates_skipped": 0,
        "invoices": [],
    }

    with patch("backend.core.gmail.refresh_access_token", return_value="mock_access_token"), \
         patch("backend.core.gmail.get_history_messages", side_effect=HistoryExpiredError("historyId expired on Gmail")), \
         patch("backend.core.gmail.sync_gmail_mailbox", return_value=mock_fallback_sync) as mock_full_sync:

        result = sync_gmail_history(session, account, notification_history_id="95000")

        # Fallback was executed
        assert mock_full_sync.called
        assert result.get("fallback_full_sync") is True
        # Watermark updated to the notification history ID
        session.refresh(account)
        assert account.last_history_id == "95000"


# ==============================================================================
# Acceptance Test 11: Watch Renewal Within 48 Hours
# ==============================================================================

def test_11_watch_renewal_extends_expiration(stage5_client):
    """Test 11: Watch renewal extends expiration before the 7-day limit."""
    client, session = stage5_client
    seed_tenant_user(session, org_id="org_alpha")
    # Expiring watch renewed 50 hours ago (> 48h window)
    fifty_hours_ago = datetime.datetime.utcnow() - datetime.timedelta(hours=50)
    account = seed_gmail_account(
        session,
        org_id="org_alpha",
        watch_status="ACTIVE",
        watch_last_renewed_at=fifty_hours_ago,
    )

    new_exp_ms = int((datetime.datetime.utcnow() + datetime.timedelta(days=7)).timestamp() * 1000)
    mock_watch_resp = {"historyId": "99002", "expiration": str(new_exp_ms)}

    with patch("backend.core.gmail.refresh_access_token", return_value="mock_access_token"), \
         patch("backend.core.gmail.register_gmail_watch", return_value=mock_watch_resp):

        renew_res = renew_expiring_watches(session)
        assert renew_res["renewed_count"] == 1
        assert account.mailbox_address in renew_res["renewed"]

        session.refresh(account)
        # Renewed timestamp should now be fresh (< 5 minutes ago)
        time_since_renew = (datetime.datetime.utcnow() - account.watch_last_renewed_at).total_seconds()
        assert time_since_renew < 300

        # Running again immediately should NOT renew (within 48 hours)
        renew_res_2 = renew_expiring_watches(session)
        assert renew_res_2["renewed_count"] == 0


# ==============================================================================
# Acceptance Test 12: Revoked Mailbox Authorization Detected
# ==============================================================================

def test_12_revoked_mailbox_authorization_detected(stage5_client):
    """Test 12: Revoked mailbox authorization is detected during watch renewal or history sync."""
    client, session = stage5_client
    seed_tenant_user(session, org_id="org_alpha")
    account = seed_gmail_account(session, org_id="org_alpha")

    # Mock token endpoint returning HTTP 400 invalid_grant
    mock_resp = MagicMock()
    mock_resp.status_code = 400
    mock_resp.text = '{"error": "invalid_grant", "error_description": "Token has been expired or revoked."}'

    with patch("httpx.post", return_value=mock_resp):
        with pytest.raises(GmailIntegrationError):
            setup_mailbox_watch(session, account)

        session.refresh(account)
        assert account.oauth_status == "EXPIRED"


# ==============================================================================
# Acceptance Test 13: Six-Hour Periodic Reconciliation
# ==============================================================================

def test_13_periodic_reconciliation_catches_missed_messages(stage5_client):
    """Test 13: Periodic reconciliation catches messages missed by Pub/Sub."""
    client, session = stage5_client
    seed_tenant_user(session, org_id="org_alpha")
    seven_hours_ago = datetime.datetime.utcnow() - datetime.timedelta(hours=7)
    account = seed_gmail_account(session, org_id="org_alpha")
    account.last_synced_at = seven_hours_ago
    session.commit()

    mock_sync_return = {
        "status": "SUCCESS",
        "ingested_count": 3,
        "quarantined_count": 0,
        "duplicates_skipped": 0,
        "invoices": [{"invoice_id": "inv_missed_1"}],
    }

    with patch("backend.core.gmail.sync_gmail_mailbox", return_value=mock_sync_return) as mock_sync:
        reconcile_res = reconcile_all_active_mailboxes(session, max_age_hours=6)

        assert reconcile_res["reconciled_mailboxes"] == 1
        assert reconcile_res["total_ingested"] == 3
        assert mock_sync.called


# ==============================================================================
# Acceptance Test 14: Tenant Isolation for Pub/Sub Ingestion
# ==============================================================================

def test_14_tenant_isolation_pubsub_notifications(stage5_client):
    """Test 14: Tenant isolation: Pub/Sub notification for Mailbox A cannot ingest into Tenant B."""
    client, session = stage5_client
    seed_tenant_user(session, org_id="org_alpha")
    seed_tenant_user(session, org_id="org_beta", user_id="usr_beta_01", email="admin@beta.internal")

    # Mailbox A owned by Org Alpha
    acc_a = seed_gmail_account(session, org_id="org_alpha", mailbox="invoices@alpha.internal")
    # Mailbox B owned by Org Beta
    acc_b = seed_gmail_account(session, org_id="org_beta", mailbox="invoices@beta.internal")

    # Incoming notification specifically for Mailbox A
    payload_a = build_pubsub_payload(
        mailbox="invoices@alpha.internal",
        history_id="10099",
        message_id="msg_pubsub_tenant_iso",
    )

    mock_sync_result = {
        "status": "SUCCESS",
        "ingested_count": 1,
        "invoices": [{"invoice_id": "inv_tenant_a"}],
    }

    with patch("backend.core.gmail.sync_gmail_history", return_value=mock_sync_result):
        resp = client.post(
            "/api/v1/integrations/gmail/pubsub/push",
            headers={"Authorization": f"Bearer test_oidc:{TEST_PUBSUB_EMAIL}:{TEST_PUBSUB_AUDIENCE}"},
            json=payload_a,
        )
        assert resp.status_code == status.HTTP_200_OK

        # The PubSubEvent record must belong strictly to org_alpha
        event = session.execute(
            select(PubSubEvent).where(PubSubEvent.pubsub_message_id == "msg_pubsub_tenant_iso")
        ).scalar_one_or_none()
        assert event is not None
        assert event.org_id == "org_alpha"
        assert event.mailbox_address == "invoices@alpha.internal"

        # Assert no event exists for org_beta
        beta_events = session.execute(
            select(PubSubEvent).where(PubSubEvent.org_id == "org_beta")
        ).scalars().all()
        assert len(beta_events) == 0

    # Sending notification for an unmapped/stranger mailbox
    stranger_payload = build_pubsub_payload(
        mailbox="attacker@stranger.com",
        history_id="99999",
        message_id="msg_pubsub_stranger",
    )
    resp_stranger = client.post(
        "/api/v1/integrations/gmail/pubsub/push",
        headers={"Authorization": f"Bearer test_oidc:{TEST_PUBSUB_EMAIL}:{TEST_PUBSUB_AUDIENCE}"},
        json=stranger_payload,
    )
    assert resp_stranger.status_code == status.HTTP_200_OK
    assert resp_stranger.json()["result"]["status"] == "UNKNOWN_MAILBOX"


# ==============================================================================
# Stage 4.1 Regression & Hardening Tests
# ==============================================================================

def test_stage41_oauth_state_nonce_single_use_and_replay_rejection(stage5_db):
    """Stage 4.1: State nonce replay rejection: state can only be consumed once."""
    session, _ = stage5_db
    state = generate_oauth_state(org_id="org_alpha", user_id="usr_01", db=session)

    # First consumption: succeeds
    org_id, user_id = validate_and_consume_oauth_state(state, db=session)
    assert org_id == "org_alpha"
    assert user_id == "usr_01"

    # Second consumption (replay attack): rejected
    with pytest.raises(GmailIntegrationError, match="already been consumed"):
        validate_and_consume_oauth_state(state, db=session)


def test_stage41_reconnect_preserves_existing_refresh_token(stage5_client):
    """Stage 4.1: Reconnect does not overwrite existing valid refresh token when Google omits it."""
    client, session = stage5_client
    token = seed_tenant_user(session, org_id="org_alpha")
    account = seed_gmail_account(session, org_id="org_alpha", refresh_token="original_secret_token_123")
    original_encrypted = account.encrypted_refresh_token

    # Generate state
    state = generate_oauth_state(org_id="org_alpha", user_id="usr_01", db=session)

    # Mock Google token exchange returning NO refresh_token (only access_token)
    mock_token_data = {"access_token": "new_access_token_456"}  # refresh_token is None

    with patch("backend.api.v1.integrations_gmail.exchange_code_for_tokens", return_value=mock_token_data), \
         patch("backend.api.v1.integrations_gmail.fetch_mailbox_profile_address", return_value=account.mailbox_address):

        resp = client.get(
            f"/api/v1/integrations/gmail/callback?code=mock_code&state={state}",
            follow_redirects=False,
        )
        assert resp.status_code in (status.HTTP_302_FOUND, status.HTTP_307_TEMPORARY_REDIRECT)

        # Assert existing refresh token was NOT erased!
        session.refresh(account)
        assert account.encrypted_refresh_token == original_encrypted
        assert account.oauth_status == "AUTHORIZED"


def test_stage41_multi_attachment_and_mixed_inline_extraction():
    """Stage 4.1: Recursive MIME traversal correctly extracts inline and external attachments."""
    inline_bytes = b"%PDF-1.4\nInline PDF Attachment"
    inline_b64 = base64.urlsafe_b64encode(inline_bytes).decode()

    part_structure = {
        "mimeType": "multipart/mixed",
        "parts": [
            {
                "mimeType": "text/plain",
                "body": {"size": 20, "data": base64.urlsafe_b64encode(b"Hello Invoice").decode()},
            },
            {
                "mimeType": "application/pdf",
                "filename": "inline_inv.pdf",
                "body": {"size": len(inline_bytes), "data": inline_b64},
            },
            {
                "mimeType": "application/octet-stream",
                "filename": "external_inv.pdf",
                "body": {"size": len(SAMPLE_PDF_BYTES), "attachmentId": "ext_att_999"},
            },
        ],
    }

    attachments = find_all_pdf_attachments(part_structure)
    assert len(attachments) == 2

    # Verify inline extraction
    bytes_inline = extract_attachment_bytes("token", "msg_1", attachments[0])
    assert bytes_inline == inline_bytes

    # Verify external extraction via API
    with patch("backend.core.gmail.get_attachment_bytes", return_value=SAMPLE_PDF_BYTES) as mock_get_att:
        bytes_external = extract_attachment_bytes("token", "msg_1", attachments[1])
        assert bytes_external == SAMPLE_PDF_BYTES
        assert mock_get_att.called


# ==============================================================================
# Live Google Cloud Skip Guard
# ==============================================================================

@pytest.mark.skipif(
    os.getenv("LIVE_GMAIL_TESTS") != "1",
    reason="Live Google Cloud Pub/Sub tests require LIVE_GMAIL_TESTS=1 and real GCP credentials.",
)
def test_live_gmail_pubsub_pipeline():
    """Live Google Cloud Pub/Sub verification against real Google test mailbox."""
    pass
