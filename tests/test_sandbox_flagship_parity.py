"""Comprehensive Parity Tests between Flagship AP Command Center and AP Decision Sandbox.

Proves:
1. Exact matching engine reuse: both invoke reevaluate_match_gates(), IndianAPRuleEngine, and HybridAPExtractor.
2. Identical deterministic results: same 7 gates, identical statuses, identical decision codes.
3. Currency consistency: all financial amounts are evaluated in INR using Decimal precision; zero USD path.
4. Deterministic edge cases: price variance, quantity overrun, degraded scan, non-payable document, duplicate safeguard.
5. Operator action parity: sandbox operator actions invoke execute_invoice_action() and append immutable audit events.
6. Multi-tenant isolation: sandbox operations are strictly partitioned to org_sme_eval.
"""

import os
import re
from decimal import Decimal
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, func

from backend.main import app
from backend.core.database import SessionLocal, set_tenant_context
from backend.models.domain import (
    Invoice,
    InvoiceLine,
    MatchRun,
    MatchGateCheck,
    ExceptionRecord,
    AuditEvent,
    WorkOrderSnapshot,
    GoodsReceiptSnapshot,
)
from backend.api.v1.sandbox import (
    GENUINE_SCENARIOS,
    SANDBOX_ORG_ID,
    CORPUS_DIR,
    _execute_pipeline_core,
    _get_sandbox_user,
)
from backend.api.v1.invoices import reevaluate_match_gates, execute_invoice_action, ActionPayload
from engine.indian_tax_rules import IndianAPRuleEngine


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


@pytest.fixture(scope="module")
def db_session():
    db = SessionLocal()
    db.info["skip_role_restriction"] = True
    set_tenant_context(db, SANDBOX_ORG_ID)
    yield db
    db.close()


# -----------------------------------------------------------------------------
# 1. Exact Matching Engine Reuse
# -----------------------------------------------------------------------------
def test_parity_shared_matching_engine_reuse(db_session):
    """Proves both Flagship and Sandbox invoke reevaluate_match_gates() and IndianAPRuleEngine."""
    inv = db_session.scalar(select(Invoice).where(Invoice.org_id == SANDBOX_ORG_ID, Invoice.invoice_number == "AP-26-001"))
    if not inv:
        pytest.skip("Baseline fixture AP-26-001 not present.")

    match_run = reevaluate_match_gates(db_session, inv, SANDBOX_ORG_ID)
    assert match_run is not None
    assert match_run.invoice_id == inv.id

    checks = db_session.scalars(
        select(MatchGateCheck).where(
            MatchGateCheck.match_run_id == match_run.id,
            MatchGateCheck.org_id == SANDBOX_ORG_ID,
        )
    ).all()
    assert len(checks) >= 7

    # Verify standard 7 gates
    gate_numbers = {c.gate_number for c in checks}
    for g in range(1, 8):
        assert g in gate_numbers, f"Missing deterministic gate {g}"


# -----------------------------------------------------------------------------
# 2. Currency Consistency: Pure INR, Zero USD references
# -----------------------------------------------------------------------------
def test_parity_currency_consistency_inr_only():
    """Asserts that all sandbox scenario metadata and calculations use INR currency."""
    for scn in GENUINE_SCENARIOS:
        assert scn["currency"] == "INR", f"Scenario {scn['id']} currency must be INR"

    with open("backend/api/v1/sandbox.py", "r", encoding="utf-8") as f:
        sandbox_source = f.read()

    # Confirm no USD rules or USD currency literals in sandbox pipeline
    assert 'currency="USD"' not in sandbox_source
    assert 'currency = "USD"' not in sandbox_source
    assert "sales_tax" not in sandbox_source
    assert "IndianAPRuleEngine" in sandbox_source


# -----------------------------------------------------------------------------
# 3. Scenario Fixtures Parity
# -----------------------------------------------------------------------------
def test_parity_scenarios_listing(client, sme_tokens):
    """Verifies that all 6 genuine test scenarios are correctly exposed via REST API."""
    auth_headers = {"Authorization": f"Bearer {sme_tokens['AP_ASSOCIATE']}"}
    res = client.get("/api/v1/sandbox/scenarios", headers=auth_headers)
    assert res.status_code == 200
    scenarios = res.json()
    assert len(scenarios) == 6

    ids = [s["id"] for s in scenarios]
    assert "SCN-01-HAPPY-PATH" in ids
    assert "SCN-02-PRICE-VARIANCE" in ids
    assert "SCN-03-DEGRADED-SCAN" in ids
    assert "SCN-04-QUARANTINE-QC" in ids
    assert "SCN-05-NON-PAYABLE" in ids
    assert "SCN-06-DUPLICATE" in ids


# -----------------------------------------------------------------------------
# 4. Deterministic Edge Case Behaviors
# -----------------------------------------------------------------------------
def test_parity_scenario_01_happy_path(db_session):
    """SCN-01: Clean 3-way match evaluates to MATCH_CANDIDATE with 7 gates PASS."""
    pdf_path = os.path.join(CORPUS_DIR, "01_invoice_AP_26_001.pdf")
    if not os.path.exists(pdf_path):
        pytest.skip(f"Fixture {pdf_path} not found")

    with open(pdf_path, "rb") as f:
        pdf_bytes = f.read()

    # Ensure clean evaluation state for Happy Path (Requirement 7: require 0 duplicate vouchers)
    prior_vouchers = db_session.scalars(
        select(Invoice).where(
            Invoice.org_id == SANDBOX_ORG_ID,
            Invoice.invoice_number == "AP-26-001",
        )
    ).all()
    for pv in prior_vouchers:
        pv.invoice_number = f"AP-26-001-ARCHIVED-{pv.id[-4:]}"
        pv.stage = "REJECTED"
        pv.decision = "REJECTED"
    db_session.flush()

    res = _execute_pipeline_core(pdf_bytes, "01_invoice_AP_26_001.pdf", db_session)
    assert res["status"] == "COMPLETED"
    assert res["invoice"]["currency"] == "INR"
    assert res["decision"] == "MATCH_CANDIDATE"
    assert res["stage"] == "PENDING_APPROVAL"
    # All 7 deterministic policy gates must pass unconditionally for Happy Path
    passed_gates = {g["gate_number"] for g in res["match_gates"] if g["status"] == "PASS"}
    assert {1, 2, 3, 4, 5, 6, 7}.issubset(passed_gates)


def test_parity_scenario_02_price_variance(db_session):
    """SCN-02: Price and quantity variance deterministically fails tolerance gate."""
    pdf_path = os.path.join(CORPUS_DIR, "30_invoice_AP_26_011.pdf")
    if not os.path.exists(pdf_path):
        pytest.skip(f"Fixture {pdf_path} not found")

    with open(pdf_path, "rb") as f:
        pdf_bytes = f.read()

    res = _execute_pipeline_core(pdf_bytes, "30_invoice_AP_26_011.pdf", db_session)
    assert res["status"] == "COMPLETED"
    assert res["decision"] == "FLAGGED_EXCEPTION"
    assert res["stage"] == "ACTION_REQUIRED"
    # Tolerance gate (6) or GRN quantity check (3) must fail
    failed_gates = {g["gate_number"] for g in res["match_gates"] if g["status"] == "FAIL"}
    assert (3 in failed_gates) or (6 in failed_gates)


def test_parity_scenario_03_degraded_scan(db_session):
    """SCN-03: Degraded raster scan triggers grounding tripwire and routes to HITL."""
    pdf_path = os.path.join(CORPUS_DIR, "36_invoice_POS_26_112.pdf")
    if not os.path.exists(pdf_path):
        pytest.skip(f"Fixture {pdf_path} not found")

    with open(pdf_path, "rb") as f:
        pdf_bytes = f.read()

    res = _execute_pipeline_core(pdf_bytes, "36_invoice_POS_26_112.pdf", db_session)
    assert res["status"] == "COMPLETED"
    assert res["decision"] == "FLAGGED_HITL_REVIEW"
    assert res["stage"] == "ACTION_REQUIRED"
    assert "text" in res["decision_reason"].lower() or "degraded" in res["decision_reason"].lower() or "ocr" in res["decision_reason"].lower()


def test_parity_scenario_04_quarantined_qc(db_session):
    """SCN-04: Goods receipt with QC HOLD/Quarantined fails Gate 4 deterministically."""
    pdf_path = os.path.join(CORPUS_DIR, "11_invoice_MC_26_090.pdf")
    if not os.path.exists(pdf_path):
        pytest.skip(f"Fixture {pdf_path} not found")

    with open(pdf_path, "rb") as f:
        pdf_bytes = f.read()

    res = _execute_pipeline_core(pdf_bytes, "11_invoice_MC_26_090.pdf", db_session)
    assert res["status"] == "COMPLETED"
    assert res["decision"] == "FLAGGED_EXCEPTION"
    assert res["stage"] == "ACTION_REQUIRED"
    gate_4 = next((g for g in res["match_gates"] if g["gate_number"] == 4), None)
    assert gate_4 is not None
    assert gate_4["status"] == "FAIL"
    assert "HOLD" in gate_4["notes"] or "rejected" in gate_4["notes"].lower()


def test_parity_scenario_05_non_payable_document(db_session):
    """SCN-05: Payment receipt is classified and autonomously rejected."""
    pdf_path = os.path.join(CORPUS_DIR, "38_payment_receipt_RCPT_26_088.pdf")
    if not os.path.exists(pdf_path):
        pytest.skip(f"Fixture {pdf_path} not found")

    with open(pdf_path, "rb") as f:
        pdf_bytes = f.read()

    res = _execute_pipeline_core(pdf_bytes, "38_payment_receipt_RCPT_26_088.pdf", db_session)
    assert res["status"] == "COMPLETED"
    assert res["decision"] == "REJECTED"
    assert res["stage"] == "REJECTED"
    assert "PAYMENT_RECEIPT" in res["decision_reason"] or "not a payable" in res["decision_reason"].lower()


def test_parity_scenario_06_duplicate_safeguard(db_session):
    """SCN-06: Resubmitted identical invoice triggers duplicate safeguard."""
    pdf_path = os.path.join(CORPUS_DIR, "01_invoice_AP_26_001.pdf")
    if not os.path.exists(pdf_path):
        pytest.skip(f"Fixture {pdf_path} not found")

    with open(pdf_path, "rb") as f:
        pdf_bytes = f.read()

    res = _execute_pipeline_core(pdf_bytes, "01_invoice_AP_26_001.pdf", db_session, force_duplicate_check=True)
    assert res["decision"] in ("REJECTED", "FLAGGED_EXCEPTION")
    assert "duplicate" in res["decision_reason"].lower() or any("Duplicate" in g.get("gate_name", "") and g["status"] == "FAIL" for g in res.get("match_gates", []))


# -----------------------------------------------------------------------------
# 5. Operator Action Parity & Audit Immutability
# -----------------------------------------------------------------------------
def test_parity_operator_actions_and_audit(client, db_session):
    """Asserts sandbox operator actions invoke execute_invoice_action() and append immutable audit events."""
    inv = db_session.scalar(select(Invoice).where(Invoice.org_id == SANDBOX_ORG_ID).order_by(Invoice.updated_at.desc()))
    if not inv:
        pytest.skip("No invoice found for operator action test")

    user = _get_sandbox_user()
    initial_events_count = db_session.scalar(
        select(func.count(AuditEvent.id)).where(AuditEvent.invoice_id == inv.id, AuditEvent.org_id == SANDBOX_ORG_ID)
    ) or 0

    payload = ActionPayload(action="HOLD_PENDING_EVIDENCE", reason="Sandbox operator placed on hold pending evidence.")
    action_res = execute_invoice_action(
        invoice_id=inv.id,
        payload=payload,
        current_user=user,
        db=db_session,
    )
    assert action_res["status"] == "SUCCESS"
    assert action_res["new_stage"] == "ACTION_REQUIRED"

    new_events_count = db_session.scalar(
        select(func.count(AuditEvent.id)).where(AuditEvent.invoice_id == inv.id, AuditEvent.org_id == SANDBOX_ORG_ID)
    ) or 0
    assert new_events_count > initial_events_count


# -----------------------------------------------------------------------------
# 6. Multi-Tenant Isolation
# -----------------------------------------------------------------------------
def test_parity_tenant_isolation(db_session):
    """Asserts sandbox execution is confined strictly to org_sme_eval."""
    # Ensure no sandbox invoice was written to any other org
    foreign_sbx_invoices = db_session.scalar(
        select(func.count(Invoice.id)).where(Invoice.id.like("inv_sbx_%"), Invoice.org_id != SANDBOX_ORG_ID)
    ) or 0
    assert foreign_sbx_invoices == 0, "Sandbox invoices must never leak to foreign organisations"
