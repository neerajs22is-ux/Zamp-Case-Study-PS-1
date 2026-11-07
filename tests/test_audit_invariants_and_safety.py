"""Comprehensive Invariants and Approval Safety Test Suite.

Verifies the critical safety controls mandated by the Second Audit Report:
1. F02: ExtractedLineItem flags arithmetic discrepancy when qty * unit_price != taxable_amount.
2. F08: High-value approval requests strictly enforce dual control and cannot bypass Step 1 after reset.
3. F09: Held invoices (workflow_substatus == "ON_HOLD") strictly block approval with HTTP 409.
4. F10: Human REJECT_INVOICE sets stage="REJECTED" and decision="REJECTED".
5. F11: resolve_po_line resolves lines unambiguously and refuses ambiguous lines without positional fallback.
6. F97: Inbox "waiting" queue includes invoices held with workflow_substatus == "ON_HOLD".
"""

from decimal import Decimal
import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.core.database import SessionLocal
from backend.models.domain import (
    Invoice, ApprovalRequest, InvoiceLine, WorkOrderLineSnapshot,
    WorkOrderSnapshot, GoodsReceiptSnapshot, GoodsReceiptLineSnapshot, QualityControlSnapshot
)
from backend.api.v1.invoices import resolve_po_line
from engine.schemas import ExtractedLineItem

client = TestClient(app)


def test_f02_schema_line_arithmetic_flag():
    """F02: ExtractedLineItem detects math discrepancy and records line_arithmetic_valid=False."""
    # Discrepant line: 10 * 50 = 500, but reported taxable is 800
    line = ExtractedLineItem(
        item_description="Precision Milling Tools",
        quantity=10.0,
        unit_price=50.0,
        taxable_amount=800.0,
    )
    assert line.line_arithmetic_valid is False
    assert line.line_discrepancy == 300.0

    # Valid line: 10 * 50 = 500, reported taxable is 500
    valid_line = ExtractedLineItem(
        item_description="Precision Milling Tools",
        quantity=10.0,
        unit_price=50.0,
        taxable_amount=500.0,
    )
    assert valid_line.line_arithmetic_valid is True
    assert valid_line.line_discrepancy == 0.0


def test_f11_resolve_po_line_no_positional_fallback():
    """F11: resolve_po_line matches unambiguously and returns None on unmatched/ambiguous lines."""
    po_lines = [
        WorkOrderLineSnapshot(id="wol_1", po_id="po_1", org_id="org_test", line_number=1, description="Industrial Bearing 20mm", contracted_unit_rate=500.0, authorized_quantity=10.0),
        WorkOrderLineSnapshot(id="wol_2", po_id="po_1", org_id="org_test", line_number=2, description="Hydraulic Fluid 5L", contracted_unit_rate=1200.0, authorized_quantity=5.0),
    ]

    # Exact match by line number and description
    inv_line1 = InvoiceLine(id="il_1", invoice_id="inv_1", org_id="org_test", line_number=1, description="Industrial Bearing 20mm", billed_quantity=10.0, billed_unit_rate=500.0, billed_line_total=5000.0)
    matched = resolve_po_line(inv_line1, po_lines)
    assert matched is not None
    assert matched.line_number == 1

    # Exact match by description only (reordered line number)
    inv_line2 = InvoiceLine(id="il_2", invoice_id="inv_1", org_id="org_test", line_number=99, description="Hydraulic Fluid 5L", billed_quantity=5.0, billed_unit_rate=1200.0, billed_line_total=6000.0)
    matched = resolve_po_line(inv_line2, po_lines)
    assert matched is not None
    assert matched.line_number == 2

    # Completely unrelated item must NOT fall back to po_lines[0] positionally!
    inv_line_unrelated = InvoiceLine(id="il_3", invoice_id="inv_1", org_id="org_test", line_number=99, description="Executive Office Furniture", billed_quantity=1.0, billed_unit_rate=25000.0, billed_line_total=25000.0)
    matched = resolve_po_line(inv_line_unrelated, po_lines)
    assert matched is None, "Must return None without positional fallback on unrelated line"


def test_f09_hold_blocks_approval(sme_tokens):
    """F09: Invoice with workflow_substatus == 'ON_HOLD' strictly blocks approval."""
    headers = {"Authorization": f"Bearer {sme_tokens['AP_LEAD']}"}

    # Find a clean candidate invoice under org_sme_eval
    with SessionLocal() as db:
        inv = db.query(Invoice).filter(Invoice.org_id == "org_sme_eval", Invoice.invoice_number == "AP-26-009").first()
        assert inv is not None
        inv_id = inv.id

        # Place hold on invoice
        inv.stage = "ACTION_REQUIRED"
        inv.workflow_substatus = "ON_HOLD"
        inv.decision_reason = "Test hold pending vendor bank proof"
        db.commit()

    # Attempt to approve held invoice
    payload = {
        "action": "APPROVE_AP_REVIEW",
        "reason": "Attempting approval while hold is active",
    }
    res = client.post(f"/api/v1/invoices/{inv_id}/actions", json=payload, headers=headers)
    assert res.status_code == 409
    assert "ON_HOLD" in res.json()["detail"]

    # Clear hold
    with SessionLocal() as db:
        inv = db.query(Invoice).filter(Invoice.id == inv_id).first()
        inv.workflow_substatus = None
        inv.stage = "PENDING_APPROVAL"
        db.commit()


def test_f10_reject_invoice_stage_consistency(sme_tokens):
    """F10: REJECT_INVOICE action sets stage='REJECTED' and decision='REJECTED' consistently."""
    headers = {"Authorization": f"Bearer {sme_tokens['AP_LEAD']}"}

    with SessionLocal() as db:
        inv = db.query(Invoice).filter(Invoice.org_id == "org_sme_eval", Invoice.stage != "REJECTED").first()
        assert inv is not None
        inv_id = inv.id

    payload = {
        "action": "REJECT_INVOICE",
        "reason": "Commercial terms disputed with supplier",
    }
    res = client.post(f"/api/v1/invoices/{inv_id}/actions", json=payload, headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["new_stage"] == "REJECTED"
    assert data["new_decision"] == "REJECTED"

    with SessionLocal() as db:
        inv = db.query(Invoice).filter(Invoice.id == inv_id).first()
        assert inv.stage == "REJECTED"
        assert inv.decision == "REJECTED"
        assert inv.workflow_substatus is None


def test_f08_dual_approval_state_safety_after_reset(sme_tokens):
    """F08: High-value approval request in RESET_TO_BASELINE state cannot jump directly to Step 2."""
    headers_lead = {"Authorization": f"Bearer {sme_tokens['AP_LEAD']}"}
    headers_controller = {"Authorization": f"Bearer {sme_tokens['CONTROLLER']}"}

    with SessionLocal() as db:
        # Seed a high-value invoice (> 5,00,000 INR) with valid matching PO, GRN, and QC
        inv = db.query(Invoice).filter(Invoice.org_id == "org_sme_eval", Invoice.invoice_number == "AP-26-009").first()
        assert inv is not None
        inv_id = inv.id
        
        # Update PO & Line items to match high value 6,00,000 INR
        wo = db.query(WorkOrderSnapshot).filter(WorkOrderSnapshot.po_number == inv.po_reference, WorkOrderSnapshot.org_id == "org_sme_eval").first()
        assert wo is not None
        wo.total_authorized_amount = 1000000.0
        wo.remaining_balance = 1000000.0

        wol = db.query(WorkOrderLineSnapshot).filter(WorkOrderLineSnapshot.po_id == wo.id, WorkOrderLineSnapshot.org_id == "org_sme_eval").first()
        assert wol is not None
        wol.contracted_unit_rate = 7500.0
        wol.authorized_quantity = 100.0

        grnl = db.query(GoodsReceiptLineSnapshot).filter(GoodsReceiptLineSnapshot.org_id == "org_sme_eval").first()
        if grnl:
            grnl.accepted_quantity = 100.0

        inv_line = db.query(InvoiceLine).filter(InvoiceLine.invoice_id == inv_id, InvoiceLine.org_id == "org_sme_eval").first()
        assert inv_line is not None
        inv_line.billed_quantity = 80.0
        inv_line.billed_unit_rate = 7500.0
        inv_line.billed_line_total = 600000.0
        inv_line.is_corrected = False

        inv.subtotal_amount = 600000.0
        inv.tax_amount = 0.0
        inv.total_amount = 600000.0
        inv.net_payable_amount = 600000.0
        inv.stage = "PENDING_APPROVAL"
        inv.decision = "MATCH_CANDIDATE"
        inv.workflow_substatus = None

        # Existing approval request in RESET_TO_BASELINE state with no first_approver_id
        req = db.query(ApprovalRequest).filter(ApprovalRequest.invoice_id == inv_id).first()
        if not req:
            req = ApprovalRequest(
                id="app_test_reset",
                org_id=inv.org_id,
                invoice_id=inv_id,
                requires_dual_approval=True,
                status="RESET_TO_BASELINE",
                first_approver_id=None,
            )
            db.add(req)
        else:
            req.status = "RESET_TO_BASELINE"
            req.first_approver_id = None
            req.second_approver_id = None
        db.commit()

    # Step 1: AP Lead approves -> establishes first approval and sets status to PENDING_SECOND_APPROVAL
    res1 = client.post(f"/api/v1/invoices/{inv_id}/actions", json={"action": "APPROVE_AP_REVIEW", "reason": "First level AP Lead approval"}, headers=headers_lead)
    assert res1.status_code == 200

    with SessionLocal() as db:
        req = db.query(ApprovalRequest).filter(ApprovalRequest.invoice_id == inv_id).first()
        assert req.status == "PENDING_SECOND_APPROVAL"
        assert req.first_approver_id is not None

    # Same AP Lead cannot grant second approval (distinct user required)
    res_same = client.post(f"/api/v1/invoices/{inv_id}/actions", json={"action": "APPROVE_AP_REVIEW", "reason": "Attempting second approval with same user"}, headers=headers_lead)
    assert res_same.status_code in (400, 403)
    assert "distinct" in res_same.json()["detail"].lower() or "role" in res_same.json()["detail"].lower()

    # Controller grants Step 2 approval
    res2 = client.post(f"/api/v1/invoices/{inv_id}/actions", json={"action": "APPROVE_AP_REVIEW", "reason": "Controller final secondary sign-off"}, headers=headers_controller)
    assert res2.status_code == 200

    with SessionLocal() as db:
        req = db.query(ApprovalRequest).filter(ApprovalRequest.invoice_id == inv_id).first()
        assert req.status == "APPROVED"
        assert req.second_approver_id is not None
        assert req.first_approver_id != req.second_approver_id
        inv = db.query(Invoice).filter(Invoice.id == inv_id).first()
        assert inv.stage == "INTERNAL_APPROVAL_COMPLETE"
        assert inv.decision == "MANUALLY_APPROVED"


def test_f97_inbox_waiting_filter_matches_holds(sme_tokens):
    """F97: Querying /api/v1/inbox?decision=HOLD_PENDING_EVIDENCE includes invoices with workflow_substatus == 'ON_HOLD'."""
    headers = {"Authorization": f"Bearer {sme_tokens['AP_LEAD']}"}

    with SessionLocal() as db:
        inv = db.query(Invoice).filter(Invoice.org_id == "org_sme_eval").first()
        assert inv is not None
        target_id = inv.id
        inv.workflow_substatus = "ON_HOLD"
        inv.decision = "FLAGGED_EXCEPTION"
        db.commit()

    res = client.get("/api/v1/inbox?decision=HOLD_PENDING_EVIDENCE", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["total_count"] > 0
    item_ids = [item["id"] for item in data["items"]]
    assert target_id in item_ids
