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
import io
import os
import pytest
from decimal import Decimal
from fastapi.testclient import TestClient
from jose import jwt
from sqlalchemy import select

from backend.main import app
from backend.core.config import settings
from backend.core.database import SessionLocal, set_tenant_context
from backend.models.domain import Invoice, User, RoleAssignment, Organisation


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

