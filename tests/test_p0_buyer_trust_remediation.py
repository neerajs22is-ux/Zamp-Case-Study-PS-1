"""Regression and Verification Suite for P0 Buyer-Trust Remediation.

Validates the 6 P0 fixes mandated by INDEPENDENT_BUYER_UX_AUDIT.md and BUYER_FIRST_UX_REDESIGN_BLUEPRINT.md:
1. P0-1: No invoice verdict contradicts underlying evidence (AP-26-009 has real DB-backed GRN & QC).
2. P0-2: Unreadable degraded scans do not cascade into false downstream failures or price renegotiation advice.
3. P0-3 & P0-5: Ingestion job status & error messages are exposed in inbox and invoice detail endpoints.
4. P0-4: "Ready to approve" decision filter returns matching candidates and never hits a 0-row dead end.
5. P0-6: Real-time scenario execution stream emits genuine pipeline stage outcomes without fake success ticks.
"""

import json
import pytest
from fastapi.testclient import TestClient
from backend.main import app
from backend.core.database import SessionLocal
from backend.models.domain import Invoice, MatchRun, MatchGateCheck
from engine.server import app as engine_app

client = TestClient(app)
engine_client = TestClient(engine_app)



def test_p0_1_clean_invoice_has_db_backed_grn_and_qc(sme_tokens):
    """P0-1: Clean invoice AP-26-009 must return real DB-backed GRN & QC snapshots, eliminating contradictions."""
    headers = {"Authorization": f"Bearer {sme_tokens['AP_LEAD']}"}

    # AP-26-009 is seeded under org_sme_eval
    with SessionLocal() as db:
        inv = db.query(Invoice).filter(Invoice.invoice_number == "AP-26-009", Invoice.org_id == "org_sme_eval").first()
        assert inv is not None, "AP-26-009 must exist in seeded test database"
        inv_id = inv.id

    res = client.get(f"/api/v1/invoices/{inv_id}", headers=headers)
    assert res.status_code == 200
    data = res.json()

    po_snapshot = data.get("po_snapshot")
    assert po_snapshot is not None
    assert po_snapshot["po_number"] == "PO-26-2001"

    # Verify genuine GRN snapshot from erp_grns
    grn = po_snapshot.get("grn")
    assert grn is not None, "Clean invoice must return populated GRN snapshot from database"
    assert grn["grn_number"] == "GRN-26-601"
    assert len(grn["lines"]) > 0
    assert grn["lines"][0]["accepted_quantity"] == 80.0

    # Verify genuine QC inspection snapshot from erp_qc_records
    qc = po_snapshot.get("qc")
    assert qc is not None, "Clean invoice must return populated QC snapshot from database"
    assert "QC-GRN-26-601" in qc["qc_certificate_number"]
    assert qc["status"] == "ACCEPTED"


def test_p0_2_degraded_scan_does_not_cascade_false_failures(sme_tokens):
    """P0-2: Degraded unreadable scan must mark downstream gates as NOT_EVALUATED instead of 6 false failures."""
    headers = {"Authorization": f"Bearer {sme_tokens['AP_LEAD']}"}

    with SessionLocal() as db:
        # APTC-036: 36_invoice_POS_26_112.pdf
        inv = db.query(Invoice).filter(
            Invoice.org_id == "org_sme_eval",
            Invoice.invoice_number.in_(["SCAN-APTC-036", "POS-26-112", "UNKNOWN"])
        ).first()
        if not inv:
            # Fallback to query by filename
            inv = db.query(Invoice).filter(Invoice.org_id == "org_sme_eval", Invoice.stage == "ACTION_REQUIRED").first()
        assert inv is not None
        inv_id = inv.id

    res = client.get(f"/api/v1/invoices/{inv_id}", headers=headers)
    assert res.status_code == 200
    data = res.json()

    gates = data.get("match_gates", [])
    assert len(gates) == 7

    # Gate 1 should fail due to document unreadability or supplier gstin
    gate1 = next(g for g in gates if g["gate_number"] == 1)
    assert gate1["status"] in ("FAIL", "FLAGGED_HITL_REVIEW")

    # Downstream gates 2 through 6 must be NOT_EVALUATED for degraded scan
    downstream_not_eval = [g for g in gates if g["gate_number"] in (2, 3, 4, 5, 6) and g["status"] == "NOT_EVALUATED"]
    assert len(downstream_not_eval) >= 5, "Downstream gates on unreadable scan must be NOT_EVALUATED, not FAIL"


def test_p0_4_ready_to_approve_decision_filter_returns_items(sme_tokens):
    """P0-4: Filtering inbox by MATCH_CANDIDATE or AUTO_APPROVED must return ready rows, not 0 rows."""
    headers = {"Authorization": f"Bearer {sme_tokens['AP_LEAD']}"}

    res_match = client.get("/api/v1/inbox?decision=MATCH_CANDIDATE", headers=headers)
    assert res_match.status_code == 200
    data_match = res_match.json()
    assert data_match["total_count"] > 0, "MATCH_CANDIDATE filter must return ready-to-approve items"

    res_auto = client.get("/api/v1/inbox?decision=AUTO_APPROVED", headers=headers)
    assert res_auto.status_code == 200
    data_auto = res_auto.json()
    assert data_auto["total_count"] > 0, "AUTO_APPROVED filter alias must return ready items without 0-row dead end"


def test_p0_5_inbox_and_detail_expose_job_status(sme_tokens):
    """P0-5: Inbox items and invoice detail must expose job_status and job_error for truthful UI progress."""
    headers = {"Authorization": f"Bearer {sme_tokens['AP_LEAD']}"}

    res_inbox = client.get("/api/v1/inbox", headers=headers)
    assert res_inbox.status_code == 200
    inbox_items = res_inbox.json()["items"]
    assert len(inbox_items) > 0
    first_item = inbox_items[0]
    assert "job_status" in first_item, "inbox item must expose job_status"
    assert "job_error" in first_item, "inbox item must expose job_error"

    res_detail = client.get(f"/api/v1/invoices/{first_item['id']}", headers=headers)
    assert res_detail.status_code == 200
    detail_invoice = res_detail.json()["invoice"]
    assert "job_status" in detail_invoice, "invoice detail must expose job_status"
    assert "job_error" in detail_invoice, "invoice detail must expose job_error"


def test_p0_6_stream_scenario_duplicate_does_not_emit_false_success():
    """P0-6: SSE stream on duplicate scenario must not emit hardcoded SUCCESS on rejection."""
    res = engine_client.get("/api/stream-scenario/EC-02-Duplicate-Submission")
    assert res.status_code == 200
    events = []
    for line in res.iter_lines():
        if line.startswith("data: "):
            payload = json.loads(line[6:])
            events.append(payload)

    final_event = next((e for e in events if e.get("event") == "DECISION_FINAL"), None)
    assert final_event is not None
    assert final_event["decision"] == "REJECTED"

    # Stage 4 must NOT be marked SUCCESS on a rejected duplicate
    stage_4_event = next((e for e in events if e.get("event") == "STAGE_COMPLETE" and e.get("stage") == 4), None)
    if stage_4_event:
        assert stage_4_event["status"] != "SUCCESS", "Rejected duplicate invoice must not emit SUCCESS for policy match"
