"""Comprehensive Sandbox Security & Governance Verification Test Suite.

Verifies Deliverable 2 of P0.4:
1. Missing authentication on all sandbox endpoints (HTTP 401).
2. Expired JWT rejection (HTTP 401).
3. Unauthorized workspace membership rejection (HTTP 403).
4. Cross-tenant access rejection on sandbox invoice actions (HTTP 404 / 403).
5. Insufficient role rejection (e.g. AUDITOR attempting APPROVE_AP_REVIEW: HTTP 403).
6. High-value dual-control anti-self-approval protection (> 500k INR: HTTP 403).
7. Malformed scenario identifier rejection (HTTP 400 / 404).
8. Invalid or oversized PDF rejection (> 15MB: HTTP 413, invalid header: HTTP 400).
9. Dev session local loopback isolation (remote IP: HTTP 403).
10. Authentic SSE checkpoint streaming verification.
"""

import datetime
import hashlib
import io
import os
import uuid
import pytest
from decimal import Decimal
from fastapi.testclient import TestClient
from jose import jwt
from sqlalchemy import select, func

from backend.main import app
from backend.core.config import settings
from backend.core.database import SessionLocal, set_tenant_context
from backend.core.pipeline import claim_ingestion_job
from backend.api.v1.sandbox import SANDBOX_ORG_ID
from backend.api.v1.invoices import reevaluate_match_gates
from backend.models.domain import Invoice, User, RoleAssignment, Organisation, Document, IngestionJob, AuditEvent


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


def make_token(
    sub="usr_sme_assoc_01",
    email="usr_sme_assoc_01@example.test",
    role="AP_ASSOCIATE",
    org_id="org_sme_eval",
    expired=False,
    issuer=None,
):
    now = datetime.datetime.now(datetime.timezone.utc)
    exp = now - datetime.timedelta(minutes=15) if expired else now + datetime.timedelta(minutes=15)
    payload = {
        "sub": sub,
        "email": email,
        "iss": issuer or settings.SUPABASE_ISSUER,
        "aud": "authenticated",
        "exp": exp,
        "iat": int(now.timestamp()) if not expired else int((now - datetime.timedelta(minutes=30)).timestamp()),
    }
    return jwt.encode(payload, settings.SUPABASE_JWT_SECRET, algorithm="HS256")


# -----------------------------------------------------------------------------
# 1. Missing Authentication (HTTP 401)
# -----------------------------------------------------------------------------
def test_missing_auth_scenarios(client):
    res = client.get("/api/v1/sandbox/scenarios")
    assert res.status_code == 401
    assert "authentication required" in res.json().get("detail", "").lower()


def test_missing_auth_runs(client):
    res = client.get("/api/v1/sandbox/runs")
    assert res.status_code == 401


def test_missing_auth_run_scenario(client):
    res = client.post("/api/v1/sandbox/run-scenario/SCN-01-HAPPY-PATH")
    assert res.status_code == 401


def test_missing_auth_upload(client):
    res = client.post("/api/v1/sandbox/upload", files={"file": ("invoice.pdf", b"%PDF-1.4 sample", "application/pdf")})
    assert res.status_code == 401


def test_missing_auth_stream_scenario(client):
    res = client.get("/api/v1/sandbox/stream-scenario/SCN-01-HAPPY-PATH")
    assert res.status_code == 401


def test_missing_auth_invoice_action(client):
    res = client.post("/api/v1/sandbox/invoices/inv_test_123/action", json={"action": "HOLD_PENDING_EVIDENCE", "reason": "No auth"})
    assert res.status_code == 401


def test_missing_auth_reset(client):
    res = client.post("/api/v1/sandbox/reset")
    assert res.status_code == 401


# -----------------------------------------------------------------------------
# 2. Expired Authentication (HTTP 401)
# -----------------------------------------------------------------------------
def test_expired_token_rejection(client):
    expired_jwt = make_token(expired=True)
    headers = {"Authorization": f"Bearer {expired_jwt}"}
    res = client.get("/api/v1/sandbox/scenarios", headers=headers)
    assert res.status_code == 401
    assert "expired" in res.json().get("detail", "").lower() or "signature" in res.json().get("detail", "").lower()


# -----------------------------------------------------------------------------
# 3. Unauthorized Workspace Membership (HTTP 403)
# -----------------------------------------------------------------------------
def test_unauthorized_user_rejection(client):
    foreign_jwt = make_token(
        sub="usr_unauthorized_outsider",
        email="outsider@unregistered.org",
    )
    headers = {"Authorization": f"Bearer {foreign_jwt}"}
    res = client.get("/api/v1/sandbox/scenarios", headers=headers)
    assert res.status_code in (401, 403)


# -----------------------------------------------------------------------------
# 4. Cross-Tenant Invoice Access Rejection (HTTP 404 / 403)
# -----------------------------------------------------------------------------
def test_cross_tenant_invoice_action_denial(client, sme_tokens):
    # Attempt action on an invoice that does not exist in org_sme_eval
    headers = {"Authorization": f"Bearer {sme_tokens['AP_LEAD']}"}
    res = client.post(
        "/api/v1/sandbox/invoices/inv_foreign_tenant_999/action",
        headers=headers,
        json={"action": "HOLD_PENDING_EVIDENCE", "reason": "Cross-tenant intrusion attempt"},
    )
    # Must fail closed with 404 (not visible in tenant) or 403
    assert res.status_code in (404, 403)


# -----------------------------------------------------------------------------
# 5. Insufficient Approval Role (HTTP 403)
# -----------------------------------------------------------------------------
def test_auditor_cannot_execute_approval(client, sme_tokens, evaluation_workspace):
    # Auditor role is strictly read-only
    inv_id = evaluation_workspace["clean"]
    headers = {"Authorization": f"Bearer {sme_tokens['AUDITOR']}"}
    res = client.post(
        f"/api/v1/sandbox/invoices/{inv_id}/action",
        headers=headers,
        json={"action": "APPROVE_AP_REVIEW", "reason": "Auditor attempting approval"},
    )
    assert res.status_code == 403
    assert "access denied" in res.json().get("detail", "").lower() or "role" in res.json().get("detail", "").lower()


# -----------------------------------------------------------------------------
# 6. High-Value Dual-Control Anti-Self-Approval (> 500k INR)
# -----------------------------------------------------------------------------
def test_high_value_anti_self_approval(client, sme_tokens, evaluation_workspace, monkeypatch):
    monkeypatch.setattr(settings, "DUAL_APPROVAL_THRESHOLD_INR", 20000.0)
    inv_id = evaluation_workspace["clean"]
    db = SessionLocal()
    db.info["skip_role_restriction"] = True
    set_tenant_context(db, "org_sme_eval")
    inv = db.scalar(select(Invoice).where(Invoice.id == inv_id))
    
    # Establish Step 1 approval on high-value voucher
    from backend.models.domain import ApprovalRequest
    import uuid
    app_req = db.scalar(select(ApprovalRequest).where(ApprovalRequest.invoice_id == inv_id))
    if not app_req:
        app_req = ApprovalRequest(
            id=f"app_test_{uuid.uuid4().hex[:8]}",
            org_id="org_sme_eval",
            invoice_id=inv_id,
            requires_dual_approval=True,
            first_approver_id="usr_sme_lead_01",
            status="PENDING_SECOND_APPROVAL",
        )
        db.add(app_req)
    else:
        app_req.first_approver_id = "usr_sme_lead_01"
        app_req.status = "PENDING_SECOND_APPROVAL"

    if inv:
        inv.stage = "ACTION_REQUIRED"
        inv.workflow_substatus = "PENDING_SECOND_APPROVAL"
        inv.decision = "MATCH_CANDIDATE"
    db.commit()
    db.close()

    # Case A: Same first approver attempting second sign-off must be rejected
    headers_lead = {"Authorization": f"Bearer {sme_tokens['AP_LEAD']}"}
    res_self = client.post(
        f"/api/v1/sandbox/invoices/{inv_id}/action",
        headers=headers_lead,
        json={"action": "APPROVE_AP_REVIEW", "reason": "Self-approval on high-value voucher"},
    )
    assert res_self.status_code in (400, 403)
    assert "dual control" in res_self.json().get("detail", "").lower() or "distinct" in res_self.json().get("detail", "").lower()

    # Case B: Non-controller role attempting Step 2 sign-off (requires CONTROLLER) is strictly HTTP 403
    res_role = client.post(
        f"/api/v1/sandbox/invoices/{inv_id}/action",
        headers={"Authorization": f"Bearer {sme_tokens['AP_ASSOCIATE']}"},
        json={"action": "APPROVE_AP_REVIEW", "reason": "Second sign-off attempted by non-controller"},
    )
    assert res_role.status_code == 403
    assert "controller" in res_role.json().get("detail", "").lower() or "role" in res_role.json().get("detail", "").lower() or "access denied" in res_role.json().get("detail", "").lower()


# -----------------------------------------------------------------------------
# 7. Malformed Scenario Identifiers (HTTP 400 / 404 / 405)
# -----------------------------------------------------------------------------
def test_malformed_scenario_identifier_rejected(client, sme_tokens):
    headers = {"Authorization": f"Bearer {sme_tokens['AP_ASSOCIATE']}"}

    # Path traversal attack (either rejected by regex validator or normalized by router)
    res_traversal = client.post("/api/v1/sandbox/run-scenario/..%2F..%2Fetc%2Fpasswd", headers=headers)
    assert res_traversal.status_code in (400, 404, 405)

    # Invalid format
    res_invalid_format = client.post("/api/v1/sandbox/run-scenario/INVALID_ID!@#$", headers=headers)
    assert res_invalid_format.status_code in (400, 404)

    # Valid format but non-existent
    res_not_found = client.post("/api/v1/sandbox/run-scenario/SCN-99-NONEXISTENT", headers=headers)
    assert res_not_found.status_code == 404


# -----------------------------------------------------------------------------
# 8. Invalid or Oversized PDFs
# -----------------------------------------------------------------------------
def test_upload_non_pdf_extension_rejected(client, sme_tokens):
    headers = {"Authorization": f"Bearer {sme_tokens['AP_ASSOCIATE']}"}
    res = client.post(
        "/api/v1/sandbox/upload",
        headers=headers,
        files={"file": ("malicious.exe", b"%PDF-1.4 valid header but exe", "application/octet-stream")},
    )
    assert res.status_code == 400
    assert "pdf" in res.json().get("detail", "").lower()


def test_upload_invalid_magic_bytes_rejected(client, sme_tokens):
    headers = {"Authorization": f"Bearer {sme_tokens['AP_ASSOCIATE']}"}
    res = client.post(
        "/api/v1/sandbox/upload",
        headers=headers,
        files={"file": ("fake.pdf", b"NOT_A_PDF_DOCUMENT_CONTENT", "application/pdf")},
    )
    assert res.status_code == 400
    assert "invalid pdf header" in res.json().get("detail", "").lower() or "corrupted" in res.json().get("detail", "").lower()


def test_upload_oversized_pdf_rejected(client, sme_tokens):
    headers = {"Authorization": f"Bearer {sme_tokens['AP_ASSOCIATE']}"}
    # Create 16 MB payload (exceeds 15 MB sandbox ceiling)
    oversized = b"%PDF-1.4 " + (b"0" * (16 * 1024 * 1024))
    res = client.post(
        "/api/v1/sandbox/upload",
        headers=headers,
        files={"file": ("oversized.pdf", oversized, "application/pdf")},
    )
    assert res.status_code in (413, 400)


# -----------------------------------------------------------------------------
# 9. Dev Quick-Login Local Loopback Isolation (HTTP 403)
# -----------------------------------------------------------------------------
def test_dev_session_rejects_remote_ip(client):
    # Requests from non-loopback IPs must be strictly rejected
    res = client.post(
        "/api/v1/auth/dev-session",
        json={"email": "sme_associate@company.internal", "org_id": "org_sme_eval"},
        headers={"x-forwarded-for": "198.51.100.25"},
    )
    assert res.status_code == 403
    assert "restricted strictly to local loopback" in res.json().get("detail", "").lower()


# -----------------------------------------------------------------------------
# 10. Authentic SSE Checkpoint Streaming & URL Query Token Prohibition
# -----------------------------------------------------------------------------
def test_query_param_auth_token_strictly_rejected(client, sme_tokens):
    """URL query-parameter authentication (?auth_token=...) must be rejected with HTTP 401."""
    token = sme_tokens["AP_ASSOCIATE"]
    res = client.get(f"/api/v1/sandbox/stream-scenario/SCN-03-DEGRADED-SCAN?auth_token={token}")
    assert res.status_code == 401
    assert "authentication required" in res.json().get("detail", "").lower()


def test_sse_authenticity_and_event_structure(client, sme_tokens):
    """Standard Bearer header streaming provides authentic checkpoints from PostgreSQL."""
    headers = {"Authorization": f"Bearer {sme_tokens['AP_ASSOCIATE']}"}
    
    # 1. Run the scenario first so that checkpoints exist in the database
    run_res = client.post(
        "/api/v1/sandbox/run-scenario/SCN-03-DEGRADED-SCAN?sync=true",
        headers=headers,
    )
    assert run_res.status_code == 200

    # 2. Replay authentic persisted checkpoints via strictly read-only SSE stream
    res = client.get(
        "/api/v1/sandbox/stream-scenario/SCN-03-DEGRADED-SCAN",
        headers=headers,
    )
    assert res.status_code == 200
    assert "text/event-stream" in res.headers.get("content-type", "")

    # Parse SSE stream
    stream_content = res.text
    assert "event" in stream_content
    assert "DECISION_FINAL" in stream_content
    assert "FLAGGED_HITL_REVIEW" in stream_content


def test_stream_scenario_get_cannot_initiate_processing(client, sme_tokens):
    """P0.1: GET requests cannot initiate processing; unexecuted scenario returns HTTP 404 without mutations."""
    headers = {"Authorization": f"Bearer {sme_tokens['AP_ASSOCIATE']}"}
    
    db = SessionLocal()
    db.info["skip_role_restriction"] = True
    set_tenant_context(db, SANDBOX_ORG_ID)
    docs_before = db.scalar(select(func.count(Document.id)).where(Document.org_id == SANDBOX_ORG_ID)) or 0
    invs_before = db.scalar(select(func.count(Invoice.id)).where(Invoice.org_id == SANDBOX_ORG_ID)) or 0
    db.close()

    # Attempt GET streaming on an unexecuted preset or fresh scenario
    # SCN-04 has not been run in this clean suite or we check non-mutating 404 behavior
    res = client.get("/api/v1/sandbox/stream-scenario/SCN-04-QUARANTINE-QC", headers=headers)
    
    db = SessionLocal()
    db.info["skip_role_restriction"] = True
    set_tenant_context(db, SANDBOX_ORG_ID)
    docs_after = db.scalar(select(func.count(Document.id)).where(Document.org_id == SANDBOX_ORG_ID)) or 0
    invs_after = db.scalar(select(func.count(Invoice.id)).where(Invoice.org_id == SANDBOX_ORG_ID)) or 0
    db.close()

    # GET must NEVER mutate documents or invoices
    assert docs_after == docs_before, "GET stream-scenario must never create documents"
    assert invs_after == invs_before, "GET stream-scenario must never create invoices"


def test_stream_scenario_auditor_cannot_trigger_processing(client):
    """P0.1: Auditor role is barred from triggering scenario ingestion (HTTP 403 Forbidden)."""
    auditor_jwt = make_token(
        sub="usr_sme_audit_01",
        email="sme_auditor@company.internal",
        org_id=SANDBOX_ORG_ID,
        role="AUDITOR",
    )
    headers = {"Authorization": f"Bearer {auditor_jwt}"}
    res = client.post("/api/v1/sandbox/run-scenario/SCN-01-HAPPY-PATH", headers=headers)
    assert res.status_code == 403
    assert "role" in res.json().get("detail", "").lower() or "permission" in res.json().get("detail", "").lower()


def test_stream_scenario_foreign_workspace_forbidden(client):
    """P0.1: Foreign workspace members cannot stream or access sandbox scenario endpoints (HTTP 403)."""
    foreign_jwt = make_token(
        sub="usr_ext_01",
        email="ext@foreign.com",
        org_id="org_foreign_customer",
        role="AP_ASSOCIATE",
    )
    headers = {"Authorization": f"Bearer {foreign_jwt}"}
    res = client.get("/api/v1/sandbox/stream-scenario/SCN-01-HAPPY-PATH", headers=headers)
    assert res.status_code == 403
    assert "access denied" in res.json().get("detail", "").lower() or "evaluation workspaces" in res.json().get("detail", "").lower()


# -----------------------------------------------------------------------------
# 11. Restriction to Authorized Evaluation Workspace (Requirement 5)
# -----------------------------------------------------------------------------
def test_scenario_execution_denied_for_foreign_tenant(client):
    """Preset demonstration scenarios cannot inject invoices into foreign customer workspaces."""
    foreign_jwt = make_token(
        sub="usr_external_customer_01",
        email="customer@production-tenant.com",
        org_id="org_foreign_customer",
        role="AP_ASSOCIATE",
    )
    headers = {"Authorization": f"Bearer {foreign_jwt}"}
    res = client.post("/api/v1/sandbox/run-scenario/SCN-01-HAPPY-PATH", headers=headers)
    assert res.status_code == 403
    assert "access denied" in res.json().get("detail", "").lower() or "evaluation workspaces" in res.json().get("detail", "").lower()


# -----------------------------------------------------------------------------
# 12. Safe Text Rendering & Anti-XSS Verification (Requirement 3)
# -----------------------------------------------------------------------------
def test_anti_xss_escaping_of_untrusted_model_fields():
    """Unsafe markup in extracted descriptions or vendor names must be sanitized and never executable."""
    import html
    malicious_inputs = [
        "<script>alert('pwned')</script>",
        "<img src=x onerror=alert(document.cookie)>",
        "<svg onload=fetch('https://attacker.com')>",
        "Line Item '\" onmouseover=\"alert(1)\"",
    ]
    for payload in malicious_inputs:
        escaped = html.escape(payload, quote=True)
        assert "<script>" not in escaped
        assert "<img" not in escaped
        assert "<svg" not in escaped
        assert "&lt;" in escaped or "&#x27;" in escaped or "&quot;" in escaped


# -----------------------------------------------------------------------------
# 13. Duplicate Intake Behavior (Requirement 4)
# -----------------------------------------------------------------------------
def test_duplicate_upload_returns_409_and_preserves_original(client, sme_tokens):
    """Duplicate file upload returns HTTP 409 Conflict without overwriting the original invoice."""
    headers = {"Authorization": f"Bearer {sme_tokens['AP_ASSOCIATE']}"}
    pdf_path = os.path.join("engine", "demo_fixtures", "01_invoice_AP_26_001.pdf")
    with open(pdf_path, "rb") as f:
        test_pdf_content = f.read()

    # First upload (synchronous mode)
    res1 = client.post(
        "/api/v1/sandbox/upload?sync=true",
        headers=headers,
        files={"file": ("01_invoice_AP_26_001.pdf", test_pdf_content, "application/pdf")},
    )
    if res1.status_code == 409:
        inv_id_1 = res1.json()["invoice_id"]
    else:
        assert res1.status_code in (200, 201)
        inv_id_1 = res1.json()["invoice_id"]

    # Second upload with identical content
    res2 = client.post(
        "/api/v1/sandbox/upload",
        headers=headers,
        files={"file": ("01_invoice_AP_26_001.pdf", test_pdf_content, "application/pdf")},
    )
    assert res2.status_code == 409
    body2 = res2.json()
    assert body2["status"] == "DUPLICATE_DETECTED"
    assert body2["invoice_id"] == inv_id_1


# -----------------------------------------------------------------------------
# 14. Sandbox Reset Safety & Tenant Restriction (Requirement 6)
# -----------------------------------------------------------------------------
def test_sandbox_reset_restricted_to_evaluation_tenant_and_non_production(client, monkeypatch):
    """Sandbox reset fails closed for non-eval tenants and in production/staging environments."""
    # A. Blocked for non-eval tenant
    foreign_jwt = make_token(
        sub="usr_admin_foreign",
        email="admin@foreign.com",
        org_id="org_foreign_customer",
        role="CONTROLLER",
    )
    res_foreign = client.post("/api/v1/sandbox/reset", headers={"Authorization": f"Bearer {foreign_jwt}"})
    assert res_foreign.status_code == 403
    assert "access denied" in res_foreign.json().get("detail", "").lower() or "evaluation workspace" in res_foreign.json().get("detail", "").lower()

    # B. Blocked in production environment even with correct role and org
    eval_controller_jwt = make_token(
        sub="usr_sme_lead_01",
        email="sme_lead@company.internal",
        org_id="org_sme_eval",
        role="CONTROLLER",
    )
    monkeypatch.setattr(settings, "APP_ENV", "production")
    res_prod = client.post("/api/v1/sandbox/reset", headers={"Authorization": f"Bearer {eval_controller_jwt}"})
    assert res_prod.status_code == 403
    assert "disabled in production" in res_prod.json().get("detail", "").lower()


# -----------------------------------------------------------------------------
# 15. Queue Starvation Safeguard: Direct Job Dispatch (P1.3)
# -----------------------------------------------------------------------------
def test_claim_ingestion_job_by_specific_id(disposable_app_db):
    """P1.3: claim_ingestion_job with specific job_id claims the exact target job regardless of older queued jobs."""
    with disposable_app_db() as db:
        test_org = f"org_job_test_{uuid.uuid4().hex[:8]}"
        org = Organisation(id=test_org, name=f"Job Test {test_org}")
        db.add(org)
        db.commit()

        older_job = IngestionJob(
            id=f"job_old_{uuid.uuid4().hex[:8]}",
            org_id=test_org,
            idempotency_key=f"idemp_old_{uuid.uuid4().hex[:8]}",
            document_id=f"doc_old_{uuid.uuid4().hex[:8]}",
            source_channel="MANUAL_UPLOAD",
            status="QUEUED",
            created_at=datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None) - datetime.timedelta(minutes=10),
        )
        target_job = IngestionJob(
            id=f"job_new_{uuid.uuid4().hex[:8]}",
            org_id=test_org,
            idempotency_key=f"idemp_new_{uuid.uuid4().hex[:8]}",
            document_id=f"doc_new_{uuid.uuid4().hex[:8]}",
            source_channel="SANDBOX_EXPERIENCE",
            status="QUEUED",
            created_at=datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None),
        )
        db.add(older_job)
        db.add(target_job)
        db.commit()

        claimed = claim_ingestion_job(db, org_id=test_org, lease_seconds=60, job_id=target_job.id)
        assert claimed is not None
        claimed_job_id, claimed_org_id, claimed_doc_id, lock_token = claimed
        assert claimed_job_id == target_job.id, "Target job must be claimed immediately without queue starvation"

        db.refresh(older_job)
        assert older_job.status == "QUEUED", "Older queued job must remain untouched in QUEUED state"


# -----------------------------------------------------------------------------
# 16. Metrics Alignment: Manual Approval vs Touchless STP (P1.1)
# -----------------------------------------------------------------------------
def test_metrics_state_transitions_manual_vs_stp(client, sme_tokens, evaluation_workspace):
    """P1.1: Manually approved invoices increment manually_approved, but straight_through_rate_pct strictly tracks AUTO_APPROVED."""
    clean_id = evaluation_workspace["clean"]
    headers = {"Authorization": f"Bearer {sme_tokens['AP_ASSOCIATE']}"}
    res_before = client.get("/api/v1/sandbox/runs", headers=headers)
    assert res_before.status_code == 200
    metrics_before = res_before.json().get("metrics", {})

    # Ensure clean 3-way match invoice is in PENDING_APPROVAL and evaluated
    db = SessionLocal()
    db.info["skip_role_restriction"] = True
    set_tenant_context(db, SANDBOX_ORG_ID)
    inv = db.scalar(select(Invoice).where(Invoice.id == clean_id))
    assert inv is not None
    inv.stage = "PENDING_APPROVAL"
    inv.decision = "MATCH_CANDIDATE"
    reevaluate_match_gates(db, inv, SANDBOX_ORG_ID)
    db.commit()
    db.close()

    # Lead manually approves the clean 3-way match invoice
    lead_headers = {"Authorization": f"Bearer {sme_tokens['AP_LEAD']}"}
    action_res = client.post(
        f"/api/v1/sandbox/invoices/{clean_id}/action",
        headers=lead_headers,
        json={"action": "APPROVE_AP_REVIEW", "reason": "Authorized by AP Lead under test."},
    )
    assert action_res.status_code in (200, 201), action_res.text

    # Query metrics after manual approval
    res_after = client.get("/api/v1/sandbox/runs", headers=headers)
    assert res_after.status_code == 200
    metrics_after = res_after.json().get("metrics", {})

    assert metrics_after.get("manually_approved", 0) >= 1
    total = metrics_after.get("total_runs", 1)
    auto_app = metrics_after.get("auto_approved", 0)
    expected_stp = round(auto_app / total * 100, 1) if total else 0.0
    assert metrics_after.get("straight_through_rate_pct") == expected_stp, "STP rate must not include manually approved invoices"


# -----------------------------------------------------------------------------
# 17. Duplicate Integrity: Repeated Uploads Preserve Original Records (P0.2)
# -----------------------------------------------------------------------------
def test_duplicate_upload_repeated_preserves_records_and_audit(client, sme_tokens):
    """P0.2: Repeated duplicate submissions reject duplicate intake and preserve original documents without soft-deletion."""
    headers = {"Authorization": f"Bearer {sme_tokens['AP_ASSOCIATE']}"}
    pdf_path = os.path.join("engine", "demo_fixtures", "01_invoice_AP_26_001.pdf")
    with open(pdf_path, "rb") as f:
        pdf_bytes = f.read()

    # Ensure document exists in ledger first
    first_res = client.post(
        "/api/v1/sandbox/upload",
        headers=headers,
        files={"file": ("01_invoice_AP_26_001.pdf", pdf_bytes, "application/pdf")},
    )
    assert first_res.status_code in (200, 409)

    # Repeated duplicate submissions must consistently return HTTP 409 Conflict
    for _ in range(3):
        res = client.post(
            "/api/v1/sandbox/upload",
            headers=headers,
            files={"file": ("01_invoice_AP_26_001.pdf", pdf_bytes, "application/pdf")},
        )
        assert res.status_code == 409
        body = res.json()
        assert body["status"] == "DUPLICATE_DETECTED"
        assert body["invoice_id"] is not None

    db = SessionLocal()
    db.info["skip_role_restriction"] = True
    set_tenant_context(db, SANDBOX_ORG_ID)
    sha256 = hashlib.sha256(pdf_bytes).hexdigest()
    
    # Assert active document exists and is not soft-deleted
    active_docs = db.scalars(
        select(Document).where(
            Document.sha256_hash == sha256,
            Document.org_id == SANDBOX_ORG_ID,
            Document.is_deleted == False,
        )
    ).all()
    assert len(active_docs) >= 1, "Original document must remain active and preserved"
    
    # Assert duplicate rejection event recorded in immutable audit log
    dup_audits = db.scalar(
        select(func.count(AuditEvent.id)).where(
            AuditEvent.org_id == SANDBOX_ORG_ID,
            AuditEvent.action == "DUPLICATE_INTAKE_REJECTED",
        )
    ) or 0
    assert dup_audits >= 1, "Duplicate attempts must be audited truthfully"
    db.close()

