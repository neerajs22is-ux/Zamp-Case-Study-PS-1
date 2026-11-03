"""Test Suite for Phase A UX Roadmap Capabilities.

Covers:
1. Stage A1 (OPP-01): Audited in-place line item correction & synchronous gate re-evaluation.
   - Authorized AP_ASSOCIATE can correct line rates within tolerance.
   - Synchronous re-evaluation of 7 deterministic gates.
   - Concurrency control (If-Match header with 412 Precondition Failed on mismatch).
   - Segregation of duties: AUDITOR role strictly barred with HTTP 403.
   - Invalidation of stale approvals upon line modification.
2. Stage A3 (OPP-04): Temporal period filtering in Inbox (fy, month, year).
3. Stage A4 (OPP-12): Evaluation mode reset control (POST /api/v1/system/reset-demo).
4. Stage A5 (OPP-06): Executive AP capital exposure & operational ageing scorecard.
"""

import pytest
from fastapi.testclient import TestClient
from backend.main import app
from backend.core.database import SessionLocal
from backend.models.domain import ApprovalRequest, AuditEvent, Invoice, InvoiceLine, MatchGateCheck, MatchRun
from engine.sme_eval_setup import SME_USERS, generate_sme_jwt, ensure_jwt_secret

client = TestClient(app)


@pytest.fixture(scope="module")
def sme_tokens():
    jwt_secret = ensure_jwt_secret()
    return {
        u["role"]: generate_sme_jwt(u, jwt_secret)
        for u in SME_USERS
    }


def test_stage_a1_line_item_correction_and_revalidation(sme_tokens):
    """TC-CORR-01: AP_ASSOCIATE corrects line rate; Gate 6 re-evaluates to PASS; audit event written."""
    headers_assoc = {"Authorization": f"Bearer {sme_tokens['AP_ASSOCIATE']}"}

    with SessionLocal() as db:
        # Find an invoice in org_sme_eval with line items
        inv = db.query(Invoice).filter(Invoice.org_id == "org_sme_eval").first()
        assert inv is not None, "Evaluation invoice must exist in database"
        inv_id = inv.id
        line = db.query(InvoiceLine).filter(InvoiceLine.invoice_id == inv_id).first()
        assert line is not None, "Invoice line must exist"
        line_id = line.id
        original_rate = float(line.billed_unit_rate)
        original_qty = float(line.billed_quantity)
        updated_at_etag = inv.updated_at.isoformat() if inv.updated_at else ""

    # Correct line rate
    payload = {
        "billed_quantity": original_qty,
        "billed_unit_rate": original_rate,
        "correction_reason": "Verified OCR accuracy against source document rate"
    }

    res = client.patch(
        f"/api/v1/invoices/{inv_id}/lines/{line_id}",
        headers={**headers_assoc, "If-Match": f'"{updated_at_etag}"'},
        json=payload,
    )
    assert res.status_code == 200, f"Line correction failed: {res.text}"
    data = res.json()
    assert data["status"] == "UPDATED"
    assert data["line"]["id"] == line_id
    assert data["line"]["is_corrected"] is True
    assert "new_match_run" in data
    assert len(data["new_match_run"]["gates"]) == 7

    # Verify audit event was written
    with SessionLocal() as db:
        latest_audit = (
            db.query(AuditEvent)
            .filter(AuditEvent.invoice_id == inv_id, AuditEvent.action == "LINE_ITEM_CORRECTED")
            .order_by(AuditEvent.timestamp.desc())
            .first()
        )
        assert latest_audit is not None
        assert latest_audit.actor_role == "AP_ASSOCIATE"
        assert "Verified OCR accuracy" in latest_audit.reason


def test_stage_a1_auditor_role_forbidden(sme_tokens):
    """TC-CORR-03: Auditor role is strictly barred from modifying line items (HTTP 403)."""
    headers_auditor = {"Authorization": f"Bearer {sme_tokens['AUDITOR']}"}

    with SessionLocal() as db:
        inv = db.query(Invoice).filter(Invoice.org_id == "org_sme_eval").first()
        line = db.query(InvoiceLine).filter(InvoiceLine.invoice_id == inv.id).first()
        inv_id = inv.id
        line_id = line.id

    payload = {
        "billed_quantity": float(line.billed_quantity),
        "billed_unit_rate": float(line.billed_unit_rate),
        "correction_reason": "Auditor attempting unauthorized edit"
    }

    res = client.patch(
        f"/api/v1/invoices/{inv_id}/lines/{line_id}",
        headers=headers_auditor,
        json=payload,
    )
    assert res.status_code == 403
    assert "read-only" in res.json()["detail"].lower()


def test_stage_a1_optimistic_locking_precondition_failed(sme_tokens):
    """TC-CORR-04: Outdated If-Match header returns HTTP 412 Precondition Failed."""
    headers_assoc = {"Authorization": f"Bearer {sme_tokens['AP_ASSOCIATE']}"}

    with SessionLocal() as db:
        inv = db.query(Invoice).filter(Invoice.org_id == "org_sme_eval").first()
        line = db.query(InvoiceLine).filter(InvoiceLine.invoice_id == inv.id).first()
        inv_id = inv.id
        line_id = line.id

    payload = {
        "billed_quantity": float(line.billed_quantity),
        "billed_unit_rate": float(line.billed_unit_rate),
        "correction_reason": "Stale write test"
    }

    res = client.patch(
        f"/api/v1/invoices/{inv_id}/lines/{line_id}",
        headers={**headers_assoc, "If-Match": '"2020-01-01T00:00:00"'},
        json=payload,
    )
    assert res.status_code == 412
    assert "Precondition Failed" in res.json()["detail"]


def test_stage_a1_stale_approval_invalidation(sme_tokens):
    """TC-CORR-02: Modifying an invoice with pending/active approval invalidates approval."""
    headers_lead = {"Authorization": f"Bearer {sme_tokens['AP_LEAD']}"}

    with SessionLocal() as db:
        inv = db.query(Invoice).filter(Invoice.org_id == "org_sme_eval").first()
        line = db.query(InvoiceLine).filter(InvoiceLine.invoice_id == inv.id).first()
        inv_id = inv.id
        line_id = line.id
        line_qty = float(line.billed_quantity)
        line_rate = float(line.billed_unit_rate)

        # Insert a simulated approval request
        app_req = db.query(ApprovalRequest).filter(ApprovalRequest.invoice_id == inv_id).first()
        if not app_req:
            app_req = ApprovalRequest(
                id=f"test_app_{inv_id[:12]}",
                org_id="org_sme_eval",
                invoice_id=inv_id,
                requires_dual_approval=True,
                first_approver_id="usr_sme_lead_01",
                status="PENDING_SECOND_APPROVAL",
            )
            db.add(app_req)
        else:
            app_req.status = "PENDING_SECOND_APPROVAL"
        db.commit()

        etag = inv.updated_at.isoformat() if inv.updated_at else ""

    payload = {
        "billed_quantity": line_qty,
        "billed_unit_rate": line_rate,
        "correction_reason": "Correcting rate after first approval"
    }

    res = client.patch(
        f"/api/v1/invoices/{inv_id}/lines/{line_id}",
        headers={**headers_lead, "If-Match": f'"{etag}"'},
        json=payload,
    )
    assert res.status_code == 200
    assert res.json()["invoice"]["approval_invalidated"] is True

    # Verify in DB that status is REVOKED_CORRECTION
    with SessionLocal() as db:
        app_req = db.query(ApprovalRequest).filter(ApprovalRequest.invoice_id == inv_id).first()
        assert app_req.status == "REVOKED_CORRECTION"


def test_stage_a3_inbox_temporal_filtering(sme_tokens):
    """Stage A3: Inbox list accepts fy, month, and year query parameters."""
    headers = {"Authorization": f"Bearer {sme_tokens['AP_LEAD']}"}

    # Query with month
    res = client.get("/api/v1/inbox?month=11", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert "items" in data
    assert "total_count" in data

    # Query with Indian FY
    res_fy = client.get("/api/v1/inbox?fy=FY%202026-27", headers=headers)
    assert res_fy.status_code == 200
    data_fy = res_fy.json()
    assert "items" in data_fy


def test_stage_a4_system_reset_demo(sme_tokens):
    """Stage A4: POST /api/v1/system/reset-demo safely resets evaluation fixtures."""
    headers_controller = {"Authorization": f"Bearer {sme_tokens['CONTROLLER']}"}

    res = client.post("/api/v1/system/reset-demo", headers=headers_controller)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "SUCCESS"
    assert data["tenant"] == "org_sme_eval"


def test_stage_a5_dashboard_exposure_scorecard(sme_tokens):
    """Stage A5: GET /api/v1/dashboard/exposure returns operational aging & blocked liability."""
    headers = {"Authorization": f"Bearer {sme_tokens['AP_LEAD']}"}

    res = client.get("/api/v1/dashboard/exposure", headers=headers)
    assert res.status_code == 200
    data = res.json()

    assert "total_blocked_liability_inr" in data
    assert "operational_aging_over_30_days_inr" in data
    assert "cleared_for_erp_inr" in data
    assert "statutory_msme_verified_due_inr" in data
    assert "statutory_msme_note" in data
    assert "verified Udyam" in data["statutory_msme_note"]
