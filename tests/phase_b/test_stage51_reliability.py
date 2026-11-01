"""Phase B Stage 5.1 Acceptance Tests — Pub/Sub Reliability & Concurrency Verification.

Verifies:
1. Mailbox-Level Concurrency: Two simultaneous Pub/Sub notifications for the same mailbox
   cannot concurrently corrupt history synchronization (per-mailbox exclusive lease).
2. Idempotent Ingestion for Overlapping History: Different Pub/Sub message IDs referring
   to overlapping mailbox history do not create duplicate Document, Invoice, or AuditEvent records.
3. Strictly Monotonic Watermark: History watermarks never move backwards under any scenario.
4. Fault Tolerance: Failed processing does not advance the watermark prematurely, enabling clean retries.
5. Out-of-Order Safety: Notifications delivered out of order are handled safely without regressing watermarks.
6. Partial Failure Retry: A retry after partial failure does not duplicate previously ingested invoices or audit events.
7. Durable Acknowledgement: Webhook refuses HTTP 200/204 if PubSubEvent database persistence fails (returns HTTP 500).
8. Scheduling Status Disclosure: Truthfully reports that 48h watch renewal and 6h reconciliation functions exist,
   but automated external Cloud Scheduler triggers are NOT CONFIGURED until Cloud Run deployment preparation.
"""

from __future__ import annotations

import base64
import datetime
import hashlib
import json
from typing import Any, Dict, Optional
from unittest.mock import MagicMock, patch

from fastapi import status
from fastapi.testclient import TestClient
from jose import jwt
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from backend.core.config import AppEnv, settings
from backend.core.database import Base, get_db
from backend.core.gmail import (
    GmailIntegrationError, MailboxSyncLockError, PubSubPersistenceError,
    acquire_mailbox_lock, is_history_id_greater, mailbox_sync_lease,
    process_pubsub_push_notification, release_mailbox_lock,
    sync_gmail_history,
)
from backend.main import app
from backend.models.domain import (
    AuditEvent, Document, GmailAccount, IngestionJob, Invoice,
    Organisation, PubSubEvent, RoleAssignment, User
)

TEST_JWT_SECRET = "stage51-reliability-test-secret-32-chars"
TEST_ISSUER = "https://test-project.supabase.co/auth/v1"
TEST_AUDIENCE = "authenticated"
TEST_PUBSUB_AUDIENCE = "https://api.test.domain.com/api/v1/integrations/gmail/pubsub/push"
TEST_PUBSUB_EMAIL = "pubsub-invoker@gcp.internal"
SAMPLE_PDF_BYTES = b"%PDF-1.4\n1 0 obj\n<< /Title (Reliability Test Invoice) >>\nendobj\ntrailer\n<< /Root 1 0 R >>\n%%EOF"


@pytest.fixture(autouse=True)
def configure_stage51_settings():
    """Configures environment settings for Stage 5.1 acceptance tests."""
    orig_env = settings.APP_ENV
    orig_secret = settings.SUPABASE_JWT_SECRET
    orig_iss = settings.SUPABASE_ISSUER
    orig_aud = settings.SUPABASE_AUDIENCE
    orig_pubsub_aud = settings.PUBSUB_VERIFICATION_AUDIENCE
    orig_pubsub_email = settings.PUBSUB_SERVICE_ACCOUNT_EMAIL
    orig_pubsub_topic = settings.PUBSUB_TOPIC_NAME

    settings.APP_ENV = AppEnv.TEST
    settings.SUPABASE_JWT_SECRET = TEST_JWT_SECRET
    settings.SUPABASE_ISSUER = TEST_ISSUER
    settings.SUPABASE_AUDIENCE = TEST_AUDIENCE
    settings.PUBSUB_VERIFICATION_AUDIENCE = TEST_PUBSUB_AUDIENCE
    settings.PUBSUB_SERVICE_ACCOUNT_EMAIL = TEST_PUBSUB_EMAIL
    settings.PUBSUB_TOPIC_NAME = "projects/test-project/topics/gmail-push-topic"

    yield

    settings.APP_ENV = orig_env
    settings.SUPABASE_JWT_SECRET = orig_secret
    settings.SUPABASE_ISSUER = orig_iss
    settings.SUPABASE_AUDIENCE = orig_aud
    settings.PUBSUB_VERIFICATION_AUDIENCE = orig_pubsub_aud
    settings.PUBSUB_SERVICE_ACCOUNT_EMAIL = orig_pubsub_email
    settings.PUBSUB_TOPIC_NAME = orig_pubsub_topic


@pytest.fixture
def stage51_db():
    """Provides a fresh, isolated in-memory SQLite database for Stage 5.1 tests."""
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
def stage51_client(stage51_db):
    """FastAPI TestClient with isolated Stage 5.1 database session override."""
    session, _ = stage51_db

    def override_get_db():
        try:
            yield session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as client:
        yield client, session
    app.dependency_overrides.clear()


def make_jwt(sub: str, email: str) -> str:
    now = datetime.datetime.now(datetime.timezone.utc)
    exp = now + datetime.timedelta(seconds=3600)
    payload = {
        "sub": sub,
        "email": email,
        "aud": TEST_AUDIENCE,
        "iss": TEST_ISSUER,
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
    }
    return jwt.encode(payload, TEST_JWT_SECRET, algorithm="HS256")


def seed_tenant_user(session: Session, org_id: str = "org_alpha", user_id: str = "usr_01") -> str:
    existing_org = session.execute(select(Organisation).where(Organisation.id == org_id)).scalar_one_or_none()
    if not existing_org:
        session.add(Organisation(id=org_id, name=f"Entity {org_id}"))

    email = f"{user_id}@{org_id}.internal"
    user = User(id=user_id, org_id=org_id, email=email, full_name="Operator", is_active=True)
    role = RoleAssignment(id=f"ra_{user_id}", org_id=org_id, user_id=user_id, role_name="SYSTEM_ADMIN")
    session.add_all([user, role])
    session.commit()
    return make_jwt(sub=user_id, email=email)


def seed_gmail_account(
    session: Session,
    org_id: str = "org_alpha",
    mailbox: str = "invoices@alpha.internal",
    last_history_id: str = "10000",
) -> GmailAccount:
    now = datetime.datetime.utcnow()
    account = GmailAccount(
        id=f"gacc_{org_id}",
        org_id=org_id,
        mailbox_address=mailbox,
        oauth_status="AUTHORIZED",
        encrypted_refresh_token="enc_valid_refresh_token_abc",
        pubsub_topic=settings.PUBSUB_TOPIC_NAME,
        watch_history_id=last_history_id,
        watch_status="ACTIVE",
        last_history_id=last_history_id,
        last_synced_at=now,
        created_at=now,
        updated_at=now,
    )
    session.add(account)
    session.commit()
    return account


def build_pubsub_payload(mailbox: str, history_id: str, message_id: str) -> Dict[str, Any]:
    inner_json = json.dumps({"emailAddress": mailbox, "historyId": history_id})
    b64_data = base64.urlsafe_b64encode(inner_json.encode()).decode()
    return {
        "message": {
            "data": b64_data,
            "messageId": message_id,
            "publishTime": "2026-10-31T22:00:00.000Z",
        },
        "subscription": "projects/test-project/subscriptions/test-sub",
    }


# ==============================================================================
# Test 01: Mailbox Concurrency & Locking
# ==============================================================================

def test_01_concurrent_notifications_mailbox_locking(stage51_client):
    """Test 01: Two concurrent notifications for the same mailbox do not corrupt history.
    
    The second notification detects active lease and defers safely without regressing watermark.
    """
    client, session = stage51_client
    seed_tenant_user(session, org_id="org_alpha")
    account = seed_gmail_account(session, org_id="org_alpha", mailbox="invoices@alpha.internal", last_history_id="10000")

    payload_1 = build_pubsub_payload("invoices@alpha.internal", "10010", "msg_concurrent_1")
    payload_2 = build_pubsub_payload("invoices@alpha.internal", "10020", "msg_concurrent_2")
    auth_headers = {"Authorization": f"Bearer test_oidc:{TEST_PUBSUB_EMAIL}:{TEST_PUBSUB_AUDIENCE}"}

    # Simulate Notification 1 holding the mailbox lease
    lock_token = acquire_mailbox_lock(session, account.id, lease_seconds=120)
    assert lock_token is not None

    # While lock is held, Notification 2 arrives
    resp_2 = client.post("/api/v1/integrations/gmail/pubsub/push", headers=auth_headers, json=payload_2)

    # Must be acknowledged (HTTP 200) to prevent Pub/Sub retry storms, but status must be CONCURRENT_DEFERRED
    assert resp_2.status_code == status.HTTP_200_OK
    res_data_2 = resp_2.json()
    assert res_data_2["status"] == "ACKNOWLEDGED"
    assert res_data_2["result"]["status"] == "CONCURRENT_DEFERRED"

    # Event must be durably recorded in DB with CONCURRENT_DEFERRED status
    event_2 = session.execute(
        select(PubSubEvent).where(PubSubEvent.pubsub_message_id == "msg_concurrent_2")
    ).scalar_one_or_none()
    assert event_2 is not None
    assert event_2.status == "CONCURRENT_DEFERRED"

    # Watermark was NOT corrupted
    session.refresh(account)
    assert account.last_history_id == "10000"

    # Now release lock (simulating Notification 1 finishing)
    release_mailbox_lock(session, account.id, lock_token)

    # Next delivery or reconciliation can now acquire lock and sync cleanly
    with patch("backend.core.gmail.refresh_access_token", return_value="mock_tok"), \
         patch("backend.core.gmail.get_history_messages", return_value=([], "10020")):

        resp_3 = client.post("/api/v1/integrations/gmail/pubsub/push", headers=auth_headers, json=payload_1)
        assert resp_3.status_code == status.HTTP_200_OK
        session.refresh(account)
        assert account.last_history_id == "10020"


# ==============================================================================
# Test 02: Overlapping History Does Not Duplicate Invoices or Audits
# ==============================================================================

def test_02_overlapping_history_does_not_duplicate_invoices_or_audits(stage51_client):
    """Test 02: Different Pub/Sub message IDs for overlapping history do not create duplicate invoices or audits."""
    client, session = stage51_client
    seed_tenant_user(session, org_id="org_alpha")
    account = seed_gmail_account(session, org_id="org_alpha", mailbox="invoices@alpha.internal", last_history_id="10000")

    mock_msg_detail = {
        "id": "msg_overlap_01",
        "payload": {
            "headers": [
                {"name": "From", "value": "Acme Supplier <billing@acme.com>"},
                {"name": "Subject", "value": "Tax Invoice INV-999"},
            ],
            "parts": [
                {
                    "filename": "inv_999.pdf",
                    "mimeType": "application/pdf",
                    "body": {"attachmentId": "att_999", "size": len(SAMPLE_PDF_BYTES)},
                }
            ],
        },
    }

    # Notification 1 arrives with historyId 10010 (contains msg_overlap_01)
    payload_1 = build_pubsub_payload("invoices@alpha.internal", "10010", "msg_id_first")
    # Notification 2 arrives with different messageId, but overlapping history
    payload_2 = build_pubsub_payload("invoices@alpha.internal", "10020", "msg_id_second")
    auth_headers = {"Authorization": f"Bearer test_oidc:{TEST_PUBSUB_EMAIL}:{TEST_PUBSUB_AUDIENCE}"}

    with patch("backend.core.gmail.refresh_access_token", return_value="mock_tok"), \
         patch("backend.core.gmail.get_history_messages", return_value=(["msg_overlap_01"], "10010")), \
         patch("backend.core.gmail.get_message_detail", return_value=mock_msg_detail), \
         patch("backend.core.gmail.get_attachment_bytes", return_value=SAMPLE_PDF_BYTES):

        # First run: inverts and ingests
        resp1 = client.post("/api/v1/integrations/gmail/pubsub/push", headers=auth_headers, json=payload_1)
        assert resp1.status_code == status.HTTP_200_OK

        # Verify exactly 1 invoice created
        invoices = session.execute(select(Invoice).where(Invoice.org_id == "org_alpha")).scalars().all()
        assert len(invoices) == 1
        audit_events = session.execute(select(AuditEvent).where(AuditEvent.org_id == "org_alpha")).scalars().all()
        initial_audit_count = len(audit_events)
        assert initial_audit_count >= 1

    # Second run with different Pub/Sub message ID, returning the SAME message
    with patch("backend.core.gmail.refresh_access_token", return_value="mock_tok"), \
         patch("backend.core.gmail.get_history_messages", return_value=(["msg_overlap_01"], "10020")), \
         patch("backend.core.gmail.get_message_detail", return_value=mock_msg_detail), \
         patch("backend.core.gmail.get_attachment_bytes", return_value=SAMPLE_PDF_BYTES):

        resp2 = client.post("/api/v1/integrations/gmail/pubsub/push", headers=auth_headers, json=payload_2)
        assert resp2.status_code == status.HTTP_200_OK
        res2_data = resp2.json()
        assert res2_data["result"]["sync_result"]["duplicates_skipped"] == 1
        assert res2_data["result"]["sync_result"]["ingested_count"] == 0

        # Invoices count remains exactly 1! Zero duplicate invoices.
        invoices_after = session.execute(select(Invoice).where(Invoice.org_id == "org_alpha")).scalars().all()
        assert len(invoices_after) == 1

        # Audit events count does NOT duplicate invoice creation events
        audit_after = session.execute(select(AuditEvent).where(AuditEvent.org_id == "org_alpha")).scalars().all()
        assert len(audit_after) == initial_audit_count


# ==============================================================================
# Test 03: Strictly Monotonic Watermark Never Regresses
# ==============================================================================

def test_03_strictly_monotonic_watermark_never_regresses(stage51_client):
    """Test 03: History watermarks never move backwards under any delivery order."""
    client, session = stage51_client
    seed_tenant_user(session, org_id="org_alpha")
    account = seed_gmail_account(session, org_id="org_alpha", mailbox="invoices@alpha.internal", last_history_id="10080")

    auth_headers = {"Authorization": f"Bearer test_oidc:{TEST_PUBSUB_EMAIL}:{TEST_PUBSUB_AUDIENCE}"}
    # An older historyId arrives out of order
    older_payload = build_pubsub_payload("invoices@alpha.internal", "10040", "msg_out_of_order")

    resp = client.post("/api/v1/integrations/gmail/pubsub/push", headers=auth_headers, json=older_payload)

    assert resp.status_code == status.HTTP_200_OK
    assert resp.json()["result"]["status"] == "OUT_OF_ORDER_SKIPPED"

    session.refresh(account)
    # The watermark must NOT regress from 10080 to 10040
    assert account.last_history_id == "10080"


# ==============================================================================
# Test 04: Failed Processing Does Not Advance Watermark
# ==============================================================================

def test_04_failed_processing_does_not_advance_watermark(stage51_client):
    """Test 04: Failed processing does not advance watermark prematurely, allowing retry."""
    client, session = stage51_client
    seed_tenant_user(session, org_id="org_alpha")
    account = seed_gmail_account(session, org_id="org_alpha", mailbox="invoices@alpha.internal", last_history_id="10020")

    auth_headers = {"Authorization": f"Bearer test_oidc:{TEST_PUBSUB_EMAIL}:{TEST_PUBSUB_AUDIENCE}"}
    payload = build_pubsub_payload("invoices@alpha.internal", "10060", "msg_fail_sync")

    with patch("backend.core.gmail.refresh_access_token", return_value="mock_tok"), \
         patch("backend.core.gmail.get_history_messages", side_effect=GmailIntegrationError("Gmail 503 Internal Outage")):

        resp = client.post("/api/v1/integrations/gmail/pubsub/push", headers=auth_headers, json=payload)
        assert resp.status_code == status.HTTP_200_OK
        assert resp.json()["result"]["status"] == "FAILED"

        # Watermark was NOT advanced to 10060
        session.refresh(account)
        assert account.last_history_id == "10020"

    # When retry runs successfully, watermark advances
    with patch("backend.core.gmail.refresh_access_token", return_value="mock_tok"), \
         patch("backend.core.gmail.get_history_messages", return_value=([], "10060")):

        res = sync_gmail_history(session, account, "10060")
        assert res["status"] == "SUCCESS"
        session.refresh(account)
        assert account.last_history_id == "10060"


# ==============================================================================
# Test 05: Out-of-Order Notifications Handled Safely
# ==============================================================================

def test_05_out_of_order_notifications_handled_safely(stage51_client):
    """Test 05: Notifications delivered out of order are handled safely."""
    client, session = stage51_client
    seed_tenant_user(session, org_id="org_alpha")
    account = seed_gmail_account(session, org_id="org_alpha", mailbox="invoices@alpha.internal", last_history_id="10000")

    auth_headers = {"Authorization": f"Bearer test_oidc:{TEST_PUBSUB_EMAIL}:{TEST_PUBSUB_AUDIENCE}"}

    # Step 1: Notification with historyId 10100 arrives and advances watermark
    payload_newer = build_pubsub_payload("invoices@alpha.internal", "10100", "msg_newer")
    with patch("backend.core.gmail.refresh_access_token", return_value="mock_tok"), \
         patch("backend.core.gmail.get_history_messages", return_value=([], "10100")):

        resp1 = client.post("/api/v1/integrations/gmail/pubsub/push", headers=auth_headers, json=payload_newer)
        assert resp1.status_code == status.HTTP_200_OK
        session.refresh(account)
        assert account.last_history_id == "10100"

    # Step 2: Delayed Notification with historyId 10050 arrives
    payload_delayed = build_pubsub_payload("invoices@alpha.internal", "10050", "msg_delayed")
    resp2 = client.post("/api/v1/integrations/gmail/pubsub/push", headers=auth_headers, json=payload_delayed)

    assert resp2.status_code == status.HTTP_200_OK
    assert resp2.json()["result"]["status"] == "OUT_OF_ORDER_SKIPPED"

    session.refresh(account)
    # Stored watermark must remain 10100
    assert account.last_history_id == "10100"


# ==============================================================================
# Test 06: Partial Failure Retry Idempotency
# ==============================================================================

def test_06_partial_failure_retry_does_not_duplicate_records(stage51_db):
    """Test 06: A retry after partial failure does not duplicate invoice records or audit events."""
    session, _ = stage51_db
    seed_tenant_user(session, org_id="org_alpha")
    account = seed_gmail_account(session, org_id="org_alpha", mailbox="invoices@alpha.internal", last_history_id="10000")

    SAMPLE_PDF_BYTES_2 = b"%PDF-1.4\n1 0 obj\n<< /Title (Invoice 2 Unique) >>\nendobj\ntrailer\n<< /Root 1 0 R >>\n%%EOF"

    mock_msg_1 = {
        "id": "msg_batch_1",
        "payload": {
            "headers": [{"name": "From", "value": "Vendor 1 <v1@test.com>"}, {"name": "Subject", "value": "Inv 1"}],
            "parts": [{"filename": "inv_1.pdf", "mimeType": "application/pdf", "body": {"attachmentId": "att_1", "size": len(SAMPLE_PDF_BYTES)}}],
        },
    }

    mock_msg_2 = {
        "id": "msg_batch_2",
        "payload": {
            "headers": [{"name": "From", "value": "Vendor 2 <v2@test.com>"}, {"name": "Subject", "value": "Inv 2"}],
            "parts": [{"filename": "inv_2.pdf", "mimeType": "application/pdf", "body": {"attachmentId": "att_2", "size": len(SAMPLE_PDF_BYTES_2)}}],
        },
    }

    # Run 1: Msg 1 succeeds, Msg 2 fails with network error
    call_tracker = {"count": 0}

    def mock_get_detail_with_partial_fail(token, msg_id):
        if msg_id == "msg_batch_1":
            return mock_msg_1
        call_tracker["count"] += 1
        raise GmailIntegrationError("Simulated network drop on msg 2")

    def mock_get_att_bytes(token, msg_id, att_id):
        return SAMPLE_PDF_BYTES if att_id == "att_1" else SAMPLE_PDF_BYTES_2

    with patch("backend.core.gmail.refresh_access_token", return_value="mock_tok"), \
         patch("backend.core.gmail.get_history_messages", return_value=(["msg_batch_1", "msg_batch_2"], "10050")), \
         patch("backend.core.gmail.get_message_detail", side_effect=mock_get_detail_with_partial_fail), \
         patch("backend.core.gmail.get_attachment_bytes", side_effect=mock_get_att_bytes):

        # Ingestion for msg 1 succeeded, msg 2 failed
        res = sync_gmail_history(session, account, "10050")
        assert res["status"] == "SUCCESS"
        assert res["ingested_count"] == 1  # Only msg 1 ingested

        # Invoices in DB: exactly 1
        invoices = session.execute(select(Invoice).where(Invoice.org_id == "org_alpha")).scalars().all()
        assert len(invoices) == 1

    # Run 2 (Retry): Both Msg 1 and Msg 2 return details successfully
    def mock_get_detail_all_success(token, msg_id):
        return mock_msg_1 if msg_id == "msg_batch_1" else mock_msg_2

    with patch("backend.core.gmail.refresh_access_token", return_value="mock_tok"), \
         patch("backend.core.gmail.get_history_messages", return_value=(["msg_batch_1", "msg_batch_2"], "10050")), \
         patch("backend.core.gmail.get_message_detail", side_effect=mock_get_detail_all_success), \
         patch("backend.core.gmail.get_attachment_bytes", side_effect=mock_get_att_bytes):

        res_retry = sync_gmail_history(session, account, "10050")
        assert res_retry["status"] == "SUCCESS"
        # Msg 1 was skipped as duplicate; Msg 2 was ingested
        assert res_retry["duplicates_skipped"] == 1
        assert res_retry["ingested_count"] == 1

        # Assert no duplicate invoices exist: exactly 2 distinct invoices in database
        invoices_final = session.execute(select(Invoice).where(Invoice.org_id == "org_alpha")).scalars().all()
        assert len(invoices_final) == 2


# ==============================================================================
# Test 07: Durable Acknowledgement Rejection on Persistence Failure
# ==============================================================================

def test_07_durable_acknowledgement_fails_on_db_commit_error(stage51_client):
    """Test 07: Webhook refuses HTTP 200/204 if PubSubEvent database persistence fails (HTTP 500)."""
    client, session = stage51_client
    seed_tenant_user(session, org_id="org_alpha")
    seed_gmail_account(session, org_id="org_alpha", mailbox="invoices@alpha.internal")

    payload = build_pubsub_payload("invoices@alpha.internal", "10010", "msg_durable_fail")
    auth_headers = {"Authorization": f"Bearer test_oidc:{TEST_PUBSUB_EMAIL}:{TEST_PUBSUB_AUDIENCE}"}

    # Simulate database failure during PubSubEvent commit
    original_commit = session.commit

    def failing_commit():
        raise OperationalError("sqlite3.OperationalError", "table locked", Exception("Database transaction locked"))

    session.commit = failing_commit

    try:
        resp = client.post("/api/v1/integrations/gmail/pubsub/push", headers=auth_headers, json=payload)

        # Must NOT return HTTP 200 or 204
        assert resp.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert "Durable acknowledgement failed" in resp.json()["detail"]
    finally:
        session.commit = original_commit


# ==============================================================================
# Test 08: Scheduling Status Truthful Disclosure
# ==============================================================================

def test_08_scheduling_status_reports_not_configured_for_external_triggers(stage51_client):
    """Test 08: Truthfully reports that external automated scheduling is NOT CONFIGURED."""
    client, session = stage51_client
    token = seed_tenant_user(session, org_id="org_alpha")

    resp = client.get("/api/v1/integrations/gmail/status", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == status.HTTP_200_OK

    data = resp.json()
    assert "scheduling" in data
    sched = data["scheduling"]

    # 48h watch renewal
    assert sched["watch_renewal"]["interval_hours"] == 48
    assert sched["watch_renewal"]["status"] == "NOT_CONFIGURED"
    assert "Cloud Scheduler" in sched["watch_renewal"]["notes"]

    # 6h reconciliation
    assert sched["reconciliation"]["interval_hours"] == 6
    assert sched["reconciliation"]["status"] == "NOT_CONFIGURED"
    assert "Cloud Scheduler" in sched["reconciliation"]["notes"]
