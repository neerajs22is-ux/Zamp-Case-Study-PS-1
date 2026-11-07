"""Phase B Stage 5.2 Acceptance Tests — Recovery of Persisted but Unfinished Pub/Sub Events.

Verifies:
1. Crash after durable persistence leaves event in RECEIVED status.
2. Redelivery of an event in RECEIVED status reclaims and processes it (not dismissed as duplicate).
3. Retry of FAILED events reclaims and processes them, recording retry_count and clearing error.
4. Recovery of CONCURRENT_DEFERRED events processes them once mailbox lease is available.
5. Duplicate COMPLETED events are acknowledged as duplicates without re-execution.
6. Expired processing leases are safely reclaimed and cleared.
7. Reclaim and retry operations never duplicate invoice or audit records.
8. Reclaim endpoint and scheduling status disclosure report truthful operational state.
"""

from __future__ import annotations

import base64
import datetime
import hashlib
import json
from typing import Any, Dict
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
    acquire_mailbox_lock, clean_expired_mailbox_locks,
    process_pubsub_push_notification, reclaim_unfinished_pubsub_events,
    release_mailbox_lock,
)
from backend.main import app
from backend.models.domain import (
    AuditEvent, Document, GmailAccount, Invoice, Organisation,
    PubSubEvent, RoleAssignment, User
)

TEST_JWT_SECRET = "stage52-recovery-test-secret-32-chars"
TEST_ISSUER = "https://test-project.supabase.co/auth/v1"
TEST_AUDIENCE = "authenticated"
TEST_PUBSUB_AUDIENCE = "https://api.test.domain.com/api/v1/integrations/gmail/pubsub/push"
TEST_PUBSUB_EMAIL = "pubsub-invoker@gcp.internal"
SAMPLE_PDF_BYTES = b"%PDF-1.4\n1 0 obj\n<< /Title (Recovery Invoice) >>\nendobj\ntrailer\n<< /Root 1 0 R >>\n%%EOF"


@pytest.fixture(autouse=True)
def configure_stage52_settings():
    """Configures environment settings for Stage 5.2 acceptance tests."""
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
def stage52_db():
    """Provides a fresh, isolated in-memory SQLite database for Stage 5.2 tests."""
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
def stage52_client(stage52_db):
    """FastAPI TestClient with isolated Stage 5.2 database session override."""
    session, _ = stage52_db

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
    user = User(id=user_id, org_id=org_id, email=email, full_name="Recovery Operator", is_active=True)
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
        encrypted_refresh_token="enc_valid_refresh_token_xyz",
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
            "publishTime": "2026-10-31T23:00:00.000Z",
        },
        "subscription": "projects/test-project/subscriptions/test-sub",
    }


# ==============================================================================
# Test 01: Crash After Durable Persistence Leaves Event in RECEIVED Status
# ==============================================================================

def test_01_crash_after_persistence_leaves_event_in_received_status(stage52_client):
    """Test 01: Crash after durable persistence leaves event in RECEIVED status without data loss."""
    client, session = stage52_client
    seed_tenant_user(session, org_id="org_alpha")
    account = seed_gmail_account(session, org_id="org_alpha", mailbox="invoices@alpha.internal", last_history_id="10000")

    payload = build_pubsub_payload("invoices@alpha.internal", "10010", "msg_crash_before_sync")
    auth_headers = {"Authorization": f"Bearer test_oidc:{TEST_PUBSUB_EMAIL}:{TEST_PUBSUB_AUDIENCE}"}

    # Simulate crash/exception immediately after persistence (during lock acquisition or sync)
    with patch("backend.core.gmail.process_single_pubsub_event", side_effect=Exception("Simulated worker process crash")):
        with pytest.raises(Exception, match="Simulated worker process crash"):
            process_pubsub_push_notification(session, payload)

    # Event was committed durably with status RECEIVED before crash
    event = session.execute(
        select(PubSubEvent).where(PubSubEvent.pubsub_message_id == "msg_crash_before_sync")
    ).scalar_one_or_none()
    assert event is not None
    assert event.status == "RECEIVED"

    # Watermark was NOT advanced prematurely
    session.refresh(account)
    assert account.last_history_id == "10000"


# ==============================================================================
# Test 02: Redelivery of RECEIVED Event Reclaims and Processes
# ==============================================================================

def test_02_redelivery_of_received_event_reclaims_and_processes(stage52_client):
    """Test 02: Redelivery of an event in RECEIVED status reclaims and processes it (not dismissed as duplicate)."""
    client, session = stage52_client
    seed_tenant_user(session, org_id="org_alpha")
    account = seed_gmail_account(session, org_id="org_alpha", mailbox="invoices@alpha.internal", last_history_id="10000")

    # Seed an unfinished event in RECEIVED status (e.g. from prior worker crash)
    unprocessed_event = PubSubEvent(
        id="pse_crashed_01",
        org_id="org_alpha",
        mailbox_address="invoices@alpha.internal",
        history_id="10015",
        pubsub_message_id="msg_redelivered_received",
        payload_json={"emailAddress": "invoices@alpha.internal", "historyId": "10015"},
        status="RECEIVED",
        retry_count=0,
    )
    session.add(unprocessed_event)
    session.commit()

    # Redelivery of the exact same messageId arrives via Pub/Sub push
    payload = build_pubsub_payload("invoices@alpha.internal", "10015", "msg_redelivered_received")
    auth_headers = {"Authorization": f"Bearer test_oidc:{TEST_PUBSUB_EMAIL}:{TEST_PUBSUB_AUDIENCE}"}

    with patch("backend.core.gmail.refresh_access_token", return_value="mock_tok"), \
         patch("backend.core.gmail.get_history_messages", return_value=([], "10015")):

        resp = client.post("/api/v1/integrations/gmail/pubsub/push", headers=auth_headers, json=payload)
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert data["status"] == "ACKNOWLEDGED"
        # Must NOT be dismissed as DUPLICATE; must be PROCESSED
        assert data["result"]["status"] == "PROCESSED"

        # Verify DB state
        session.refresh(unprocessed_event)
        assert unprocessed_event.status == "COMPLETED"
        assert unprocessed_event.retry_count == 1
        assert unprocessed_event.last_attempted_at is not None

        # Watermark was advanced to 10015
        session.refresh(account)
        assert account.last_history_id == "10015"


# ==============================================================================
# Test 03: Retry of FAILED Events
# ==============================================================================

def test_03_retry_of_failed_events_reclaims_and_succeeds(stage52_client):
    """Test 03: Retry of FAILED events reclaims and executes successfully, clearing error."""
    client, session = stage52_client
    seed_tenant_user(session, org_id="org_alpha")
    account = seed_gmail_account(session, org_id="org_alpha", mailbox="invoices@alpha.internal", last_history_id="10000")

    failed_event = PubSubEvent(
        id="pse_failed_01",
        org_id="org_alpha",
        mailbox_address="invoices@alpha.internal",
        history_id="10025",
        pubsub_message_id="msg_retry_failed",
        payload_json={"emailAddress": "invoices@alpha.internal", "historyId": "10025"},
        status="FAILED",
        error_message="Temporary upstream 503 error",
        retry_count=1,
    )
    session.add(failed_event)
    session.commit()

    payload = build_pubsub_payload("invoices@alpha.internal", "10025", "msg_retry_failed")
    auth_headers = {"Authorization": f"Bearer test_oidc:{TEST_PUBSUB_EMAIL}:{TEST_PUBSUB_AUDIENCE}"}

    with patch("backend.core.gmail.refresh_access_token", return_value="mock_tok"), \
         patch("backend.core.gmail.get_history_messages", return_value=([], "10025")):

        resp = client.post("/api/v1/integrations/gmail/pubsub/push", headers=auth_headers, json=payload)
        assert resp.status_code == status.HTTP_200_OK
        assert resp.json()["result"]["status"] == "PROCESSED"

        session.refresh(failed_event)
        assert failed_event.status == "COMPLETED"
        assert failed_event.retry_count == 2
        assert failed_event.error_message is None

        session.refresh(account)
        assert account.last_history_id == "10025"


# ==============================================================================
# Test 04: Recovery of CONCURRENT_DEFERRED Events
# ==============================================================================

def test_04_recovery_of_concurrent_deferred_events(stage52_db):
    """Test 04: Recovery of CONCURRENT_DEFERRED events processes them once lease is available."""
    session, _ = stage52_db
    seed_tenant_user(session, org_id="org_alpha")
    account = seed_gmail_account(session, org_id="org_alpha", mailbox="invoices@alpha.internal", last_history_id="10000")

    # Event deferred because another worker held the lock 10 minutes ago
    ten_mins_ago = datetime.datetime.utcnow() - datetime.timedelta(minutes=10)
    deferred_event = PubSubEvent(
        id="pse_deferred_01",
        org_id="org_alpha",
        mailbox_address="invoices@alpha.internal",
        history_id="10035",
        pubsub_message_id="msg_deferred_rec",
        status="CONCURRENT_DEFERRED",
        error_message="Mailbox currently locked",
        received_at=ten_mins_ago,
        last_attempted_at=ten_mins_ago,
        retry_count=0,
    )
    session.add(deferred_event)
    session.commit()

    with patch("backend.core.gmail.refresh_access_token", return_value="mock_tok"), \
         patch("backend.core.gmail.get_history_messages", return_value=([], "10035")):

        # Run recovery operation without waiting for Pub/Sub redelivery
        reclaim_res = reclaim_unfinished_pubsub_events(session, max_age_seconds=60)

        assert reclaim_res["scanned_count"] >= 1
        assert reclaim_res["completed_count"] >= 1

        session.refresh(deferred_event)
        assert deferred_event.status == "COMPLETED"
        assert deferred_event.error_message is None

        session.refresh(account)
        assert account.last_history_id == "10035"


# ==============================================================================
# Test 05: Duplicate COMPLETED Events Acknowledged Without Reprocessing
# ==============================================================================

def test_05_duplicate_completed_events_acknowledged_without_reprocessing(stage52_client):
    """Test 05: Duplicate COMPLETED events are acknowledged as duplicate without re-syncing."""
    client, session = stage52_client
    seed_tenant_user(session, org_id="org_alpha")
    seed_gmail_account(session, org_id="org_alpha", mailbox="invoices@alpha.internal", last_history_id="10040")

    completed_event = PubSubEvent(
        id="pse_done_01",
        org_id="org_alpha",
        mailbox_address="invoices@alpha.internal",
        history_id="10040",
        pubsub_message_id="msg_already_done",
        status="COMPLETED",
        retry_count=0,
    )
    session.add(completed_event)
    session.commit()

    payload = build_pubsub_payload("invoices@alpha.internal", "10040", "msg_already_done")
    auth_headers = {"Authorization": f"Bearer test_oidc:{TEST_PUBSUB_EMAIL}:{TEST_PUBSUB_AUDIENCE}"}

    with patch("backend.core.gmail.sync_gmail_history") as mock_sync:
        resp = client.post("/api/v1/integrations/gmail/pubsub/push", headers=auth_headers, json=payload)
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert data["status"] == "ACKNOWLEDGED"
        assert data["result"]["status"] == "DUPLICATE"

        # Assert zero history sync calls executed
        assert not mock_sync.called


# ==============================================================================
# Test 06: Expired Processing Lease Recovery
# ==============================================================================

def test_06_expired_processing_lease_recovery(stage52_db):
    """Test 06: Expired processing lease can be reclaimed safely without deadlocking."""
    session, _ = stage52_db
    account = seed_gmail_account(session, org_id="org_alpha", mailbox="invoices@alpha.internal")

    # Simulate worker crash: lease expired 5 minutes ago
    account.sync_lock_token = "stale_token_dead_worker"
    account.sync_lock_expires_at = datetime.datetime.utcnow() - datetime.timedelta(minutes=5)
    session.commit()

    # Clean expired locks
    reclaimed = clean_expired_mailbox_locks(session)
    assert reclaimed == 1

    session.refresh(account)
    assert account.sync_lock_token is None
    assert account.sync_lock_expires_at is None

    # New worker acquires lease smoothly
    new_token = acquire_mailbox_lock(session, account.id, lease_seconds=120)
    assert new_token is not None
    release_mailbox_lock(session, account.id, new_token)


# ==============================================================================
# Test 07: No Duplicate Invoice or Audit Creation on Reclaim
# ==============================================================================

def test_07_no_duplicate_invoice_or_audit_creation_on_reclaim(stage52_db):
    """Test 07: Reclaiming an unfinished event skips already-ingested attachments without duplicate records."""
    session, _ = stage52_db
    seed_tenant_user(session, org_id="org_alpha")
    account = seed_gmail_account(session, org_id="org_alpha", mailbox="invoices@alpha.internal", last_history_id="10000")

    mock_msg_detail = {
        "id": "msg_rec_01",
        "payload": {
            "headers": [
                {"name": "From", "value": "Acme Supplier <billing@acme.com>"},
                {"name": "Subject", "value": "Tax Invoice INV-RECLAIM"},
            ],
            "parts": [
                {
                    "filename": "inv_reclaim.pdf",
                    "mimeType": "application/pdf",
                    "body": {"attachmentId": "att_rec_1", "size": len(SAMPLE_PDF_BYTES)},
                }
            ],
        },
    }

    # Simulate event persisted, partial sync completed invoice creation, but event marked FAILED
    doc_hash = hashlib.sha256(SAMPLE_PDF_BYTES).hexdigest()
    doc = Document(
        id="doc_rec_01",
        org_id="org_alpha",
        invoice_id="inv_rec_01",
        filename="inv_reclaim.pdf",
        mime_type="application/pdf",
        file_size_bytes=len(SAMPLE_PDF_BYTES),
        sha256_hash=doc_hash,
        storage_provider="SUPABASE_STORAGE",
        storage_key="org_org_alpha/invoices/doc_rec_01/inv_reclaim.pdf",
        is_original=True,
        is_deleted=False,
    )
    inv = Invoice(
        id="inv_rec_01",
        org_id="org_alpha",
        source_channel="GMAIL",
        vendor_name="Acme Supplier",
        stage="RECEIVED",
        decision="NEEDS_REVIEW",
    )
    audit = AuditEvent(
        id="evt_rec_01",
        org_id="org_alpha",
        actor_id="GMAIL_SYSTEM",
        actor_role="SYSTEM",
        action="INVOICE_INGESTED",
        reason="Initial ingestion attempt",
    )
    failed_event = PubSubEvent(
        id="pse_rec_fail",
        org_id="org_alpha",
        mailbox_address="invoices@alpha.internal",
        history_id="10050",
        pubsub_message_id="msg_rec_fail_01",
        status="FAILED",
        error_message="Network glitch before completion",
        last_attempted_at=datetime.datetime.utcnow() - datetime.timedelta(minutes=10),
    )
    session.add_all([doc, inv, audit, failed_event])
    session.commit()

    with patch("backend.core.gmail.refresh_access_token", return_value="mock_tok"), \
         patch("backend.core.gmail.get_history_messages", return_value=(["msg_rec_01"], "10050")), \
         patch("backend.core.gmail.get_message_detail", return_value=mock_msg_detail), \
         patch("backend.core.gmail.get_attachment_bytes", return_value=SAMPLE_PDF_BYTES):

        reclaim_res = reclaim_unfinished_pubsub_events(session, max_age_seconds=60)
        assert reclaim_res["completed_count"] == 1

        # Exactly 1 invoice remains in the database
        invoices = session.execute(select(Invoice).where(Invoice.org_id == "org_alpha")).scalars().all()
        assert len(invoices) == 1

        # Zero duplicate audit events created
        audits = session.execute(select(AuditEvent).where(AuditEvent.org_id == "org_alpha")).scalars().all()
        assert len(audits) == 1


# ==============================================================================
# Test 08: Reclaim Endpoint and Truthful Scheduling Disclosure
# ==============================================================================

def test_08_reclaim_endpoint_and_scheduling_status_disclosure(stage52_client, monkeypatch):
    """Test 08: Reclaim endpoint responds correctly and status documents synchronous execution."""
    client, session = stage52_client
    token = seed_tenant_user(session, org_id="org_alpha")
    monkeypatch.setattr(settings, "PLATFORM_OPERATOR_SUBJECTS", "usr_01")

    # 1. Test POST /api/v1/integrations/gmail/pubsub/reclaim
    resp = client.post(
        "/api/v1/integrations/gmail/pubsub/reclaim",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == status.HTTP_200_OK
    assert "scanned_count" in resp.json()

    # 2. Test GET /api/v1/integrations/gmail/status scheduling disclosure
    status_resp = client.get("/api/v1/integrations/gmail/status", headers={"Authorization": f"Bearer {token}"})
    assert status_resp.status_code == status.HTTP_200_OK
    data = status_resp.json()

    assert "scheduling" in data
    sched = data["scheduling"]

    assert "pubsub_recovery" in sched
    assert sched["pubsub_recovery"]["status"] == "NOT_CONFIGURED"
    assert "SYNCHRONOUS_IN_WEBHOOK" in sched["pubsub_recovery"]["processing_mode"]
    assert "automated background worker scheduler is not configured" in sched["pubsub_recovery"]["notes"].lower()
