"""Phase B — Stage 8 Acceptance Tests: Zero-Cost Hosting Architecture & Complete Technical Documentation.

Verifies:
1. Render Blueprint specification (render.yaml): Free plan, Docker runtime, health check probe.
2. Complete Technical Documentation Suite (docs/architecture/):
   - ARCHITECTURE_OVERVIEW.md
   - ARCHITECTURE_DECISIONS.md (10 ADRs)
   - ALTERNATIVES_AND_TRADEOFFS.md
   - FREE_TIER_LIMITATIONS.md
   - DATA_FLOW_AND_SECURITY.md
   - DEPLOYMENT_AND_OPERATIONS.md
   - FUTURE_UPGRADE_PATH.md
3. Direct Gmail API incremental history synchronization & watermark management.
4. On-demand sync routing: incremental history vs full reconciliation.
5. Mailbox lease concurrency locking during on-demand sync.
6. Absence of mandatory cloud expenditure ($0.00/month baseline).
"""

import os
from pathlib import Path
import re
from unittest.mock import MagicMock, patch
import pytest
from fastapi.testclient import TestClient

from backend.core.config import settings, AppEnv
from backend.models.domain import GmailAccount, Organisation, User
from backend.main import app

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def test_01_render_blueprint_specification():
    """Verify render.yaml exists and defines a compliant zero-cost Render Free Web Service."""
    blueprint_path = PROJECT_ROOT / "render.yaml"
    assert blueprint_path.exists(), "render.yaml must exist at the project root."

    content = blueprint_path.read_text(encoding="utf-8")

    assert "type: web" in content, "Blueprint must define a web service."
    assert "plan: free" in content, "Service must specify plan: free for $0.00/month cost."
    assert "runtime: docker" in content, "Service must use Docker runtime."
    assert "healthCheckPath: /api/v1/liveness" in content, "Health check probe must target /api/v1/liveness."
    assert "DATABASE_URL" in content, "Must declare DATABASE_URL."
    assert "SUPABASE_JWKS_URL" in content, "Must declare SUPABASE_JWKS_URL."
    assert "SUPABASE_SERVICE_ROLE_KEY" in content, "Must declare SUPABASE_SERVICE_ROLE_KEY."
    assert "ENCRYPTION_KEY" in content, "Must declare ENCRYPTION_KEY."
    assert "GMAIL_CLIENT_ID" in content, "Must declare GMAIL_CLIENT_ID."


def test_02_all_seven_architecture_documents_exist_and_conform():
    """Verify that all 7 required architecture documents exist, are non-empty, and contain status tags."""
    docs_dir = PROJECT_ROOT / "docs" / "architecture"
    assert docs_dir.exists() and docs_dir.is_dir(), "docs/architecture directory must exist."

    expected_files = [
        "ARCHITECTURE_OVERVIEW.md",
        "ARCHITECTURE_DECISIONS.md",
        "ALTERNATIVES_AND_TRADEOFFS.md",
        "FREE_TIER_LIMITATIONS.md",
        "DATA_FLOW_AND_SECURITY.md",
        "DEPLOYMENT_AND_OPERATIONS.md",
        "FUTURE_UPGRADE_PATH.md",
    ]

    for fname in expected_files:
        fpath = docs_dir / fname
        assert fpath.exists(), f"Required documentation file {fname} must exist."
        content = fpath.read_text(encoding="utf-8")
        assert len(content) > 1000, f"{fname} must be substantially populated (>1000 bytes)."
        assert "[IMPLEMENTED]" in content or "[VERIFIED LIMITATION]" in content, \
            f"{fname} must include standard compliance status tags."


def test_03_architecture_decisions_has_ten_adrs():
    """Verify that ARCHITECTURE_DECISIONS.md documents all 10 required architectural decisions."""
    adrs_path = PROJECT_ROOT / "docs" / "architecture" / "ARCHITECTURE_DECISIONS.md"
    content = adrs_path.read_text(encoding="utf-8")

    required_adrs = [
        "ADR-001",
        "ADR-002",
        "ADR-003",
        "ADR-004",
        "ADR-005",
        "ADR-006",
        "ADR-007",
        "ADR-008",
        "ADR-009",
        "ADR-010",
    ]

    for adr in required_adrs:
        assert adr in content, f"{adr} must be present in ARCHITECTURE_DECISIONS.md"
        assert "Context" in content, "ADR must contain Context"
        assert "Decision" in content, "ADR must contain Decision"
        assert "Rationale" in content, "ADR must contain Rationale"
        assert "Trade-offs" in content, "ADR must contain Trade-offs"


def test_04_fetch_mailbox_profile_helpers():
    """Verify fetch_mailbox_profile queries Gmail API profile endpoint."""
    from backend.core.gmail import fetch_mailbox_profile, fetch_mailbox_profile_address

    mock_profile_resp = MagicMock()
    mock_profile_resp.status_code = 200
    mock_profile_resp.json.return_value = {
        "emailAddress": "ap-invoices@zerocost.com",
        "historyId": "987654321",
        "messagesTotal": 42,
    }

    with patch("httpx.get", return_value=mock_profile_resp) as mock_get:
        profile = fetch_mailbox_profile("mock_token")
        assert profile["emailAddress"] == "ap-invoices@zerocost.com"
        assert profile["historyId"] == "987654321"

        email = fetch_mailbox_profile_address("mock_token")
        assert email == "ap-invoices@zerocost.com"


@pytest.fixture
def zc_client(monkeypatch):
    """Fixture providing TestClient with test mode enabled and in-memory SQLite session override."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool
    from backend.core.database import Base, get_db
    import backend.models.domain  # register all domain tables

    monkeypatch.setattr(settings, "APP_ENV", AppEnv.TEST)

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(bind=engine)
    session = TestingSession()

    def override_get_db():
        try:
            yield session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as client:
        yield client, session
    app.dependency_overrides.clear()


def test_05_sync_mailbox_endpoint_incremental_routing(zc_client, monkeypatch):
    """Verify POST /api/v1/integrations/gmail/sync routes to incremental sync when watermark exists."""
    from backend.models.domain import GmailAccount, Organisation, User, RoleAssignment

    client, db = zc_client

    org_id = "org_zerocost_test"
    user_id = "user_zc_controller"

    # Create test org, user, and role
    org = Organisation(id=org_id, name="Zero Cost Test Corp")
    db.add(org)

    user = User(id=user_id, org_id=org_id, email="controller@zerocost.com", full_name="Test Controller")
    db.add(user)

    role_assign = RoleAssignment(id="ra_zc", user_id=user_id, org_id=org_id, role_name="CONTROLLER")
    db.add(role_assign)

    acc = GmailAccount(
        id="gacc_zc_1",
        org_id=org_id,
        mailbox_address="ap-inbox@zerocost.com",
        oauth_status="AUTHORIZED",
        encrypted_refresh_token="enc_token",
        last_history_id="123456",
    )
    db.add(acc)
    db.commit()

    mock_sync_result = {
        "status": "SUCCESS",
        "org_id": org_id,
        "mailbox": "ap-inbox@zerocost.com",
        "history_id": "123499",
        "messages_checked": 2,
        "ingested_count": 1,
        "quarantined_count": 0,
        "duplicates_skipped": 0,
        "invoices": [{"invoice_id": "inv_1", "filename": "test.pdf"}],
    }

    auth_header = f"test_token:CONTROLLER:{user_id}:controller@zerocost.com:{org_id}"

    with patch("backend.api.v1.integrations_gmail.sync_gmail_history", return_value=mock_sync_result) as mock_hist_sync, \
         patch("backend.api.v1.integrations_gmail.sync_gmail_mailbox") as mock_full_sync:

        resp = client.post(
            "/api/v1/integrations/gmail/sync",
            headers={"Authorization": f"Bearer {auth_header}"},
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["sync_mode"] == "INCREMENTAL_HISTORY"
        assert data["ingested_count"] == 1
        assert mock_hist_sync.called
        assert not mock_full_sync.called


def test_06_sync_mailbox_endpoint_force_full(zc_client):
    """Verify passing force_full=True routes to full reconciliation even if watermark exists."""
    from backend.models.domain import GmailAccount, Organisation, User, RoleAssignment

    client, db = zc_client

    org_id = "org_zerocost_test"
    user_id = "user_zc_controller"

    # Ensure records exist in this isolated session
    if not db.get(Organisation, org_id):
        db.add(Organisation(id=org_id, name="Zero Cost Test Corp"))
        db.add(User(id=user_id, org_id=org_id, email="controller@zerocost.com", full_name="Test Controller"))
        db.add(RoleAssignment(id="ra_zc_2", user_id=user_id, org_id=org_id, role_name="CONTROLLER"))
        db.add(GmailAccount(
            id="gacc_zc_2",
            org_id=org_id,
            mailbox_address="ap-inbox@zerocost.com",
            oauth_status="AUTHORIZED",
            encrypted_refresh_token="enc_token",
            last_history_id="123456",
        ))
        db.commit()

    auth_header = f"test_token:CONTROLLER:{user_id}:controller@zerocost.com:{org_id}"

    mock_full_result = {
        "status": "SUCCESS",
        "org_id": org_id,
        "mailbox": "ap-inbox@zerocost.com",
        "ingested_count": 3,
        "quarantined_count": 0,
        "duplicates_skipped": 1,
        "invoices": [],
    }

    with patch("backend.api.v1.integrations_gmail.sync_gmail_mailbox", return_value=mock_full_result) as mock_full_sync, \
         patch("backend.api.v1.integrations_gmail.sync_gmail_history") as mock_hist_sync:

        resp = client.post(
            "/api/v1/integrations/gmail/sync?force_full=true",
            headers={"Authorization": f"Bearer {auth_header}"},
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["sync_mode"] == "FULL_QUERY"
        assert data["ingested_count"] == 3
        assert mock_full_sync.called
        assert not mock_hist_sync.called


def test_07_sync_mailbox_lease_lock_contention(zc_client):
    """Verify that concurrent sync calls for the same mailbox return HTTP 409 Conflict."""
    from backend.core.gmail import MailboxSyncLockError
    from backend.models.domain import GmailAccount, Organisation, User, RoleAssignment

    client, db = zc_client

    org_id = "org_zerocost_test"
    user_id = "user_zc_controller"

    if not db.get(Organisation, org_id):
        db.add(Organisation(id=org_id, name="Zero Cost Test Corp"))
        db.add(User(id=user_id, org_id=org_id, email="controller@zerocost.com", full_name="Test Controller"))
        db.add(RoleAssignment(id="ra_zc_3", user_id=user_id, org_id=org_id, role_name="CONTROLLER"))
        db.add(GmailAccount(
            id="gacc_zc_3",
            org_id=org_id,
            mailbox_address="ap-inbox@zerocost.com",
            oauth_status="AUTHORIZED",
            encrypted_refresh_token="enc_token",
            last_history_id="123456",
        ))
        db.commit()

    auth_header = f"test_token:CONTROLLER:{user_id}:controller@zerocost.com:{org_id}"

    with patch("backend.api.v1.integrations_gmail.mailbox_sync_lease", side_effect=MailboxSyncLockError("Locked")):
        resp = client.post(
            "/api/v1/integrations/gmail/sync",
            headers={"Authorization": f"Bearer {auth_header}"},
        )
        assert resp.status_code == 409
        assert "already in progress" in resp.json()["detail"]


def test_08_initial_sync_runs_full_reconciliation_and_seeds_watermark(zc_client):
    """Verify newly connected mailbox (last_history_id=None) runs full query reconciliation and seeds watermark."""
    from backend.models.domain import GmailAccount, Organisation, User, RoleAssignment

    client, db = zc_client

    org_id = "org_zc_initial"
    user_id = "user_zc_initial"

    db.add(Organisation(id=org_id, name="Initial Sync Corp"))
    db.add(User(id=user_id, org_id=org_id, email="initial@corp.com", full_name="Initial User"))
    db.add(RoleAssignment(id="ra_zc_init", user_id=user_id, org_id=org_id, role_name="CONTROLLER"))
    
    # Mailbox connected without initial history ID
    acc = GmailAccount(
        id="gacc_zc_init",
        org_id=org_id,
        mailbox_address="inbox@corp.com",
        oauth_status="AUTHORIZED",
        encrypted_refresh_token="enc_token",
        last_history_id=None,
    )
    db.add(acc)
    db.commit()

    auth_header = f"test_token:CONTROLLER:{user_id}:initial@corp.com:{org_id}"

    mock_full_result = {
        "status": "SUCCESS",
        "org_id": org_id,
        "mailbox": "inbox@corp.com",
        "ingested_count": 5,
        "quarantined_count": 0,
        "duplicates_skipped": 0,
        "invoices": [{"invoice_id": f"inv_{i}", "filename": f"inv_{i}.pdf"} for i in range(5)],
    }

    with patch("backend.api.v1.integrations_gmail.sync_gmail_mailbox", return_value=mock_full_result) as mock_full, \
         patch("backend.api.v1.integrations_gmail.sync_gmail_history") as mock_hist:

        resp = client.post(
            "/api/v1/integrations/gmail/sync",
            headers={"Authorization": f"Bearer {auth_header}"},
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["sync_mode"] == "FULL_QUERY"
        assert data["ingested_count"] == 5
        assert mock_full.called
        assert not mock_hist.called


def test_09_full_reconciliation_idempotency_skips_duplicates(zc_client):
    """Verify that running full reconciliation repeatedly skips already-ingested invoices via SHA-256."""
    from backend.core.gmail import sync_gmail_mailbox
    from backend.models.domain import Document, GmailAccount, Organisation, User, RoleAssignment

    client, db = zc_client

    org_id = "org_zc_idemp"
    user_id = "user_zc_idemp"

    db.add(Organisation(id=org_id, name="Idempotency Corp"))
    db.add(User(id=user_id, org_id=org_id, email="idemp@corp.com", full_name="Idemp User"))
    db.add(RoleAssignment(id="ra_zc_idemp", user_id=user_id, org_id=org_id, role_name="CONTROLLER"))
    acc = GmailAccount(
        id="gacc_zc_idemp",
        org_id=org_id,
        mailbox_address="idemp@corp.com",
        oauth_status="AUTHORIZED",
        encrypted_refresh_token="enc_token",
        last_history_id=None,
    )
    db.add(acc)
    db.commit()

    pdf_bytes = b"%PDF-1.4 Mock invoice content for idempotency testing."

    with patch("backend.core.gmail.refresh_access_token", return_value="mock_access_token"), \
         patch("backend.core.gmail.list_mailbox_messages", return_value=[{"id": "msg_001"}]), \
         patch("backend.core.gmail.get_message_detail", return_value={
             "id": "msg_001",
             "payload": {
                 "headers": [
                     {"name": "From", "value": "Vendor Inc <billing@vendor.com>"},
                     {"name": "Subject", "value": "Invoice INV-2026-01"},
                 ],
                 "parts": [{
                     "filename": "invoice_001.pdf",
                     "mimeType": "application/pdf",
                     "body": {"attachmentId": "att_001", "size": len(pdf_bytes)},
                 }]
             }
         }), \
         patch("backend.core.gmail.get_attachment_bytes", return_value=pdf_bytes), \
         patch("backend.core.gmail.fetch_mailbox_profile", return_value={"historyId": "99999"}):

        # First sync: in-memory file storage mock
        with patch("backend.core.storage.storage_adapter.save_file", return_value={
            "storage_provider": "SUPABASE",
            "storage_key": "org_zc_idemp/invoices/doc_1/invoice_001.pdf",
        }):
            res1 = sync_gmail_mailbox(db, org_id, actor_id=user_id)
            assert res1["status"] == "SUCCESS"
            assert res1["ingested_count"] == 1
            assert res1["duplicates_skipped"] == 0

        # Verify document stored in DB
        doc_count = db.query(Document).filter_by(org_id=org_id).count()
        assert doc_count == 1

        # Second sync: same message, same attachment bytes
        res2 = sync_gmail_mailbox(db, org_id, actor_id=user_id)
        assert res2["status"] == "SUCCESS"
        assert res2["ingested_count"] == 0
        assert res2["duplicates_skipped"] == 1

        # Document count must remain strictly 1 (no duplicate document created)
        assert db.query(Document).filter_by(org_id=org_id).count() == 1


def test_10_history_api_404_expired_recovers_and_refreshes_watermark(zc_client):
    """Verify that when History API returns HTTP 404 (HistoryExpiredError), sync falls back to full reconciliation and refreshes watermark."""
    from backend.core.gmail import sync_gmail_history, HistoryExpiredError
    from backend.models.domain import GmailAccount, Organisation, User

    client, db = zc_client

    org_id = "org_zc_recovery"
    acc = GmailAccount(
        id="gacc_zc_rec",
        org_id=org_id,
        mailbox_address="recovery@corp.com",
        oauth_status="AUTHORIZED",
        encrypted_refresh_token="enc_token",
        last_history_id="111111",  # Expired on Gmail servers
    )
    db.add(acc)
    db.commit()

    with patch("backend.core.gmail.refresh_access_token", return_value="mock_access_token"), \
         patch("backend.core.gmail.get_history_messages", side_effect=HistoryExpiredError("historyId expired (HTTP 404)")), \
         patch("backend.core.gmail.sync_gmail_mailbox", return_value={
             "status": "SUCCESS",
             "org_id": org_id,
             "mailbox": acc.mailbox_address,
             "ingested_count": 2,
             "quarantined_count": 0,
             "duplicates_skipped": 0,
             "invoices": [],
         }), \
         patch("backend.core.gmail.fetch_mailbox_profile", return_value={"historyId": "555555"}):

        res = sync_gmail_history(
            db=db,
            account=acc,
            notification_history_id="111111",
            actor_id="test_actor",
        )

        assert res.get("fallback_full_sync") is True
        assert res["status"] == "SUCCESS"
        # The watermark must be refreshed to the fresh profile historyId (555555), not the expired one (111111)
        assert acc.last_history_id == "555555"


def test_11_sync_interruption_preserves_watermark(zc_client):
    """Verify that when incremental sync times out, processed items commit but watermark does NOT advance."""
    from backend.core.gmail import sync_gmail_history
    from backend.models.domain import GmailAccount, Organisation

    client, db = zc_client

    org_id = "org_zc_timeout"
    acc = GmailAccount(
        id="gacc_zc_tout",
        org_id=org_id,
        mailbox_address="timeout@corp.com",
        oauth_status="AUTHORIZED",
        encrypted_refresh_token="enc_token",
        last_history_id="200000",
    )
    db.add(acc)
    db.commit()

    with patch("backend.core.gmail.refresh_access_token", return_value="mock_access_token"), \
         patch("backend.core.gmail.get_history_messages", return_value=(["msg_1", "msg_2"], "200050")):

        # Set timeout_seconds=0.0 to simulate immediate deadline expiration
        res = sync_gmail_history(
            db=db,
            account=acc,
            notification_history_id="200050",
            actor_id="test_timeout",
            timeout_seconds=0.0,
        )

        assert res.get("timed_out") is True
        assert res["status"] == "TIMED_OUT"
        # Watermark must NOT advance to 200050 to ensure safe redelivery
        assert acc.last_history_id == "200000"


def test_12_concurrent_initial_sync_requests_mutually_exclusive(zc_client):
    """Verify concurrent requests on initial sync (last_history_id=None) are blocked by per-mailbox lock."""
    from backend.core.gmail import MailboxSyncLockError
    from backend.models.domain import GmailAccount, Organisation, User, RoleAssignment

    client, db = zc_client

    org_id = "org_zc_conc_init"
    user_id = "user_zc_conc_init"

    db.add(Organisation(id=org_id, name="Concurrent Init Corp"))
    db.add(User(id=user_id, org_id=org_id, email="conc@corp.com", full_name="Conc User"))
    db.add(RoleAssignment(id="ra_zc_conc", user_id=user_id, org_id=org_id, role_name="CONTROLLER"))
    acc = GmailAccount(
        id="gacc_zc_conc",
        org_id=org_id,
        mailbox_address="conc@corp.com",
        oauth_status="AUTHORIZED",
        encrypted_refresh_token="enc_token",
        last_history_id=None,
    )
    db.add(acc)
    db.commit()

    auth_header = f"test_token:CONTROLLER:{user_id}:conc@corp.com:{org_id}"

    with patch("backend.api.v1.integrations_gmail.mailbox_sync_lease", side_effect=MailboxSyncLockError("Locked")):
        resp = client.post(
            "/api/v1/integrations/gmail/sync",
            headers={"Authorization": f"Bearer {auth_header}"},
        )
        assert resp.status_code == 409
        assert "already in progress" in resp.json()["detail"]
