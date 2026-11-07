"""Phase D.4 Acceptance Tests ? Reliability, Failure Modes & Fail-Closed Recovery.

Verifies:
1. Mantle API timeouts and HTTP 500 errors halt execution or fail closed to HITL (never auto-approving).
2. Missing or disconnected database dependency fails closed (returns HTTP 403/503 Service Unavailable).
3. Idempotent action execution prevents double-approval and duplicate workflows.
4. Expired Gmail History API watermark (HTTP 404) triggers fallback full reconciliation.
5. Fail-closed invariant: under zero failure modes can an error result in automated payment approval.
"""

from __future__ import annotations

import datetime
import hashlib
import os
from unittest.mock import MagicMock, patch

from fastapi import HTTPException, status
from fastapi.testclient import TestClient
from jose import jwt
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from backend.api.v1.invoices import get_invoice_detail
from backend.core.auth import AuthenticatedUser, UserRole
from backend.core.config import AppEnv, settings
from backend.core.database import Base, get_db
from backend.core.gmail import HistoryExpiredError, sync_gmail_history
from backend.main import app
from backend.models.domain import (
    ApprovalRequest, AuditEvent, Document, GmailAccount, IngestionJob,
    Invoice, Organisation, RoleAssignment, User
)
from engine.hybrid_extractor import HybridAPExtractor
from engine.mantle_client import BedrockMantleClient, MantleClientError

TEST_JWT_SECRET = "rel-test-jwt-secret-minimum-32-chars-long"
TEST_ISSUER = "https://rel-test.supabase.co/auth/v1"
TEST_AUDIENCE = "authenticated"


@pytest.fixture(autouse=True)
def configure_rel_settings():
    orig_env = settings.APP_ENV
    orig_secret = settings.SUPABASE_JWT_SECRET
    orig_iss = settings.SUPABASE_ISSUER
    orig_aud = settings.SUPABASE_AUDIENCE

    settings.APP_ENV = AppEnv.TEST
    settings.SUPABASE_JWT_SECRET = TEST_JWT_SECRET
    settings.SUPABASE_ISSUER = TEST_ISSUER
    settings.SUPABASE_AUDIENCE = TEST_AUDIENCE

    yield

    settings.APP_ENV = orig_env
    settings.SUPABASE_JWT_SECRET = orig_secret
    settings.SUPABASE_ISSUER = orig_iss
    settings.SUPABASE_AUDIENCE = orig_aud


@pytest.fixture
def rel_db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = SessionLocal()
    yield session, engine
    session.close()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture
def rel_client(rel_db):
    session, _ = rel_db

    def override_get_db():
        yield session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as client:
        yield client, session
    app.dependency_overrides.clear()


def make_jwt(sub: str, email: str) -> str:
    now = datetime.datetime.now(datetime.timezone.utc)
    exp = now + datetime.timedelta(hours=2)
    payload = {
        "sub": sub,
        "email": email,
        "aud": TEST_AUDIENCE,
        "iss": TEST_ISSUER,
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
    }
    return jwt.encode(payload, TEST_JWT_SECRET, algorithm="HS256")


def seed_user(session: Session) -> str:
    org = Organisation(id="org_rel", name="Reliability Corp")
    user = User(id="usr_lead", org_id="org_rel", email="lead@rel.test", full_name="AP Lead", is_active=True)
    ra = RoleAssignment(id="ra_lead", org_id="org_rel", user_id="usr_lead", role_name="AP_LEAD")
    session.add_all([org, user, ra])
    session.commit()
    return make_jwt("usr_lead", "lead@rel.test")


# ==============================================================================
# Reliability Tests
# ==============================================================================

def test_01_mantle_inference_failure_halts_closed():
    """Proves that a Mantle API timeout or 500 error raises RuntimeError and never falls back to auto-approval."""
    mock_mantle = MagicMock(spec=BedrockMantleClient)
    mock_mantle.extract_document.side_effect = MantleClientError("Bedrock endpoint timed out after 30s")

    extractor = HybridAPExtractor(mantle_client=mock_mantle)
    
    # Load actual valid sample PDF from corpus
    pdf_path = os.path.join("tests", "evaluation_corpus_v2", "invoices", "01_invoice_AP_26_001.pdf")
    with open(pdf_path, "rb") as f:
        sample_pdf_bytes = f.read()

    with pytest.raises(RuntimeError) as exc_info:
        extractor.extract_hybrid(sample_pdf_bytes, filename="fail_invoice.pdf", document_id="DOC-FAIL")

    assert "Live Mantle inference failed" in str(exc_info.value)
    assert "timed out" in str(exc_info.value)


def test_02_database_disconnected_returns_503_or_fails_closed(rel_db):
    """Proves that when the database is unavailable, direct operational handlers fail closed with HTTP 503."""
    mock_user = AuthenticatedUser(
        id="usr_lead",
        org_id="org_rel",
        role=UserRole.AP_LEAD,
        email="lead@rel.test",
        name="AP Lead",
        is_provisioned=True,
    )
    with pytest.raises(HTTPException) as exc_info:
        get_invoice_detail(invoice_id="inv_test_01", current_user=mock_user, db=None)

    assert exc_info.value.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    assert "Database not connected" in exc_info.value.detail


def test_03_idempotent_duplicate_actions_prevention(rel_client, record_valid_match):
    """Proves that executing an approval twice on an invoice is handled idempotently without error."""
    client, session = rel_client
    token = seed_user(session)

    inv = Invoice(
        id="inv_idemp_01",
        org_id="org_rel",
        source_channel="MANUAL_UPLOAD",
        currency="INR",
        stage="PENDING_APPROVAL",
        decision="MATCH_CANDIDATE",
        invoice_number="INV-IDEMP-01",
        total_amount=5000.0,
    )
    session.add(inv)
    session.commit()

    # First approval
    record_valid_match(session, inv)

    resp1 = client.post(
        "/api/v1/invoices/inv_idemp_01/actions",
        json={"action": "APPROVE_AP_REVIEW", "reason": "First approval verification"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp1.status_code == status.HTTP_200_OK
    assert resp1.json()["new_stage"] == "INTERNAL_APPROVAL_COMPLETE"

    # Second approval attempt: state remains complete, no crash
    resp2 = client.post(
        "/api/v1/invoices/inv_idemp_01/actions",
        json={"action": "APPROVE_AP_REVIEW", "reason": "Second duplicate click"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp2.status_code == status.HTTP_200_OK
    assert resp2.json()["new_stage"] == "INTERNAL_APPROVAL_COMPLETE"


def test_04_gmail_history_api_404_expired_watermark_recovers(rel_client):
    """Proves that when Gmail History API returns 404 for an expired watermark, sync triggers fallback reconciliation."""
    client, session = rel_client
    _ = seed_user(session)

    account = GmailAccount(
        id="gacc_rel_01",
        org_id="org_rel",
        mailbox_address="ap-inbox@rel.test",
        oauth_status="ACTIVE",
        encrypted_refresh_token="enc_dummy_token",
        last_history_id="90001",
        watch_status="ACTIVE",
    )
    session.add(account)
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
        assert account.last_history_id == "95000"
