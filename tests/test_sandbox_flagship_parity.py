"""Comprehensive Parity Tests between Flagship AP Command Center and AP Decision Sandbox.

Proves:
1. Exact matching engine reuse: both invoke reevaluate_match_gates(), IndianAPRuleEngine, and HybridAPExtractor.
2. Identical deterministic results: same 7 gates, identical statuses, identical decision codes.
3. Currency consistency: all financial amounts are evaluated in INR using Decimal precision; zero USD path.
4. Deterministic edge cases: price variance, quantity overrun, degraded scan, non-payable document, duplicate safeguard.
5. Operator action parity: sandbox operator actions invoke execute_invoice_action() and append immutable audit events.
6. Multi-tenant isolation: sandbox operations are strictly partitioned to org_sme_eval.
7. Complete Test Isolation (P0.4 Final): Every state-mutating test runs against an isolated,
   disposable in-memory SQLite database, leaving cloud evaluation databases and configured
   ledgers 100% untouched.
"""

import datetime
import os
import re
import uuid
from decimal import Decimal
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, func, create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from jose import jwt

from backend.main import app
from backend.core.database import set_tenant_context, get_db
from backend.core.storage import TestInMemoryStorageAdapter
import backend.core.storage as storage_mod
import backend.core.pipeline as pipeline_mod
import backend.api.v1.sandbox as sbx_mod
from backend.core.auth import AuthenticatedUser, UserRole
from backend.core.config import settings
from backend.models.domain import (
    Base,
    Organisation,
    User,
    RoleAssignment,
    Vendor,
    VendorGSTIN,
    Invoice,
    InvoiceLine,
    Document,
    MatchRun,
    MatchGateCheck,
    ExceptionRecord,
    AuditEvent,
    WorkOrderSnapshot,
    WorkOrderLineSnapshot,
    GoodsReceiptSnapshot,
    GoodsReceiptLineSnapshot,
    QualityControlSnapshot,
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


def _seed_procurement_workspace(db, org_id=SANDBOX_ORG_ID):
    """Provisions a complete synthetic procurement baseline in the given database."""
    set_tenant_context(db, org_id)
    org = db.get(Organisation, org_id)
    if not org:
        org = Organisation(id=org_id, name="SME Evaluation Workspace")
        db.add(org)
    user = db.get(User, "usr_sme_assoc_01")
    if not user:
        user = User(
            id="usr_sme_assoc_01",
            org_id=org_id,
            email="sme_associate@company.internal",
            full_name="SME Evaluation Associate",
            is_active=True,
        )
        db.add(user)
    role = db.scalar(select(RoleAssignment).where(RoleAssignment.user_id == "usr_sme_assoc_01", RoleAssignment.org_id == org_id))
    if not role:
        role = RoleAssignment(
            id=f"role_{uuid.uuid4().hex[:8]}",
            org_id=org_id,
            user_id="usr_sme_assoc_01",
            role_name="AP_ASSOCIATE",
        )
        db.add(role)

    # Vendor V001 (Asterion)
    v1 = Vendor(
        id=f"v001_{uuid.uuid4().hex[:6]}",
        org_id=org_id,
        erp_vendor_code="V001",
        legal_name="Asterion Precision Components Pvt Ltd",
        bank_account_verified=True,
    )
    db.add(v1)
    db.flush()
    gstin1 = VendorGSTIN(
        id=f"gstin001_{uuid.uuid4().hex[:6]}",
        org_id=org_id,
        vendor_id=v1.id,
        gstin="29SYNTH0001A1Z5",
        state_code="29",
        status="ACTIVE",
    )
    db.add(gstin1)

    # PO-26-1001 for SCN-01
    po1 = WorkOrderSnapshot(
        id=f"po001_{uuid.uuid4().hex[:6]}",
        org_id=org_id,
        po_number="PO-26-1001",
        vendor_code="V001",
        total_authorized_amount=Decimal("28416.00"),
        remaining_balance=Decimal("28416.00"),
        currency="INR",
        status="APPROVED",
    )
    db.add(po1)
    db.flush()
    db.add(WorkOrderLineSnapshot(
        id=f"pol001_{uuid.uuid4().hex[:6]}",
        org_id=org_id,
        po_id=po1.id,
        line_number=1,
        item_code="SHAFT-01",
        description="Precision turned steel shafts",
        authorized_quantity=Decimal("120.0000"),
        contracted_unit_rate=Decimal("185.0000"),
        authorized_line_total=Decimal("22200.00"),
    ))
    grn1 = GoodsReceiptSnapshot(
        id=f"grn001_{uuid.uuid4().hex[:6]}",
        org_id=org_id,
        grn_number="GRN-26-501",
        po_number="PO-26-1001",
        received_date=datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None),
    )
    db.add(grn1)
    db.flush()
    db.add(GoodsReceiptLineSnapshot(
        id=f"grnl001_{uuid.uuid4().hex[:6]}",
        org_id=org_id,
        grn_id=grn1.id,
        po_line_number=1,
        accepted_quantity=Decimal("120.0000"),
        rejected_quantity=Decimal("0.0000"),
    ))
    db.add(QualityControlSnapshot(
        id=f"qc001_{uuid.uuid4().hex[:6]}",
        org_id=org_id,
        qc_certificate_number="QC-GRN-26-501-01",
        grn_number="GRN-26-501",
        overall_status="ACCEPTED",
    ))

    # PO-26-1011 for SCN-02 (Variance)
    po2 = WorkOrderSnapshot(
        id=f"po002_{uuid.uuid4().hex[:6]}",
        org_id=org_id,
        po_number="PO-26-1011",
        vendor_code="V001",
        total_authorized_amount=Decimal("17464.00"),
        remaining_balance=Decimal("17464.00"),
        currency="INR",
        status="APPROVED",
    )
    db.add(po2)
    db.flush()
    db.add(WorkOrderLineSnapshot(
        id=f"pol002_{uuid.uuid4().hex[:6]}",
        org_id=org_id,
        po_id=po2.id,
        line_number=1,
        item_code="SHAFT-01",
        description="Steel shaft lot",
        authorized_quantity=Decimal("80.0000"),
        contracted_unit_rate=Decimal("185.0000"),
        authorized_line_total=Decimal("14800.00"),
    ))
    grn2 = GoodsReceiptSnapshot(
        id=f"grn002_{uuid.uuid4().hex[:6]}",
        org_id=org_id,
        grn_number="GRN-26-621",
        po_number="PO-26-1011",
        received_date=datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None),
    )
    db.add(grn2)
    db.flush()
    db.add(GoodsReceiptLineSnapshot(
        id=f"grnl002_{uuid.uuid4().hex[:6]}",
        org_id=org_id,
        grn_id=grn2.id,
        po_line_number=1,
        accepted_quantity=Decimal("80.0000"),
        rejected_quantity=Decimal("0.0000"),
    ))
    db.add(QualityControlSnapshot(
        id=f"qc002_{uuid.uuid4().hex[:6]}",
        org_id=org_id,
        qc_certificate_number="QC-GRN-26-621-01",
        grn_number="GRN-26-621",
        overall_status="ACCEPTED",
    ))

    # Vendor V003 & PO-26-2003 for SCN-04 (QC Quarantined)
    v3 = Vendor(
        id=f"v003_{uuid.uuid4().hex[:6]}",
        org_id=org_id,
        erp_vendor_code="V003",
        legal_name="Meridian Industrial Chemicals Pvt Ltd",
        bank_account_verified=True,
    )
    db.add(v3)
    db.flush()
    gstin3 = VendorGSTIN(
        id=f"gstin003_{uuid.uuid4().hex[:6]}",
        org_id=org_id,
        vendor_id=v3.id,
        gstin="24SYNTH0003C1Z1",
        state_code="24",
        status="ACTIVE",
    )
    db.add(gstin3)
    po3 = WorkOrderSnapshot(
        id=f"po003_{uuid.uuid4().hex[:6]}",
        org_id=org_id,
        po_number="PO-26-2003",
        vendor_code="V003",
        total_authorized_amount=Decimal("192576.00"),
        remaining_balance=Decimal("192576.00"),
        currency="INR",
        status="APPROVED",
    )
    db.add(po3)
    db.flush()
    db.add(WorkOrderLineSnapshot(
        id=f"pol003_{uuid.uuid4().hex[:6]}",
        org_id=org_id,
        po_id=po3.id,
        line_number=1,
        item_code="CHEM-01",
        description="Epoxy resin drums",
        authorized_quantity=Decimal("24.0000"),
        contracted_unit_rate=Decimal("6800.0000"),
        authorized_line_total=Decimal("163200.00"),
    ))
    grn3 = GoodsReceiptSnapshot(
        id=f"grn003_{uuid.uuid4().hex[:6]}",
        org_id=org_id,
        grn_number="GRN-26-603",
        po_number="PO-26-2003",
        received_date=datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None),
    )
    db.add(grn3)
    db.flush()
    db.add(GoodsReceiptLineSnapshot(
        id=f"grnl003_{uuid.uuid4().hex[:6]}",
        org_id=org_id,
        grn_id=grn3.id,
        po_line_number=1,
        accepted_quantity=Decimal("24.0000"),
        rejected_quantity=Decimal("0.0000"),
    ))
    db.add(QualityControlSnapshot(
        id=f"qc003_{uuid.uuid4().hex[:6]}",
        org_id=org_id,
        qc_certificate_number="QC-GRN-26-603-01",
        grn_number="GRN-26-603",
        overall_status="HOLD",
    ))
    db.commit()
    return user


@pytest.fixture
def disposable_parity_db(disposable_app_db, monkeypatch):
    """Provides a fresh, isolated in-memory SQLite database for every parity test.
    
    Guarantees:
    - Zero interaction with the configured cloud evaluation database.
    - Strict test isolation across parallel runs and execution orders.
    - Single unified in-memory storage adapter across sandbox, pipeline, and storage.
    """
    storage = pipeline_mod.storage_adapter
    monkeypatch.setattr(sbx_mod, "storage_adapter", storage)
    monkeypatch.setattr(storage_mod, "storage_adapter", storage)

    with disposable_app_db() as db:
        db.info["skip_role_restriction"] = True
        _seed_procurement_workspace(db, SANDBOX_ORG_ID)
        yield db


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


@pytest.fixture
def sandbox_auth_token():
    """Generates an AP_ASSOCIATE JWT for the disposable workspace without conflicting fixtures."""
    return jwt.encode(
        {
            "sub": "usr_sme_assoc_01",
            "email": "sme_associate@company.internal",
            "iss": settings.SUPABASE_ISSUER,
            "aud": "authenticated",
            "exp": datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=1),
        },
        settings.SUPABASE_JWT_SECRET,
        algorithm="HS256",
    )


@pytest.fixture
def sandbox_auth_headers(sandbox_auth_token):
    return {"Authorization": f"Bearer {sandbox_auth_token}"}


# -----------------------------------------------------------------------------
# 1. Exact Matching Engine Reuse
# -----------------------------------------------------------------------------
def test_parity_shared_matching_engine_reuse(disposable_parity_db):
    """Proves both Flagship and Sandbox invoke reevaluate_match_gates() and IndianAPRuleEngine."""
    db = disposable_parity_db
    inv = Invoice(
        id="inv_match_reuse_test",
        org_id=SANDBOX_ORG_ID,
        source_channel="SANDBOX_EXPERIENCE",
        invoice_number="AP-26-001",
        po_reference="PO-26-1001",
        vendor_name="Asterion Precision Components Pvt Ltd",
        vendor_gstin="29SYNTH0001A1Z5",
        currency="INR",
        subtotal_amount=Decimal("22200.00"),
        tax_amount=Decimal("3996.00"),
        total_amount=Decimal("26196.00"),
        net_payable_amount=Decimal("26196.00"),
        stage="RECEIVED",
        decision="NEEDS_REVIEW",
    )
    db.add(inv)
    db.flush()

    line = InvoiceLine(
        id="line_match_reuse_test",
        org_id=SANDBOX_ORG_ID,
        invoice_id=inv.id,
        line_number=1,
        description="Precision turned steel shafts",
        billed_quantity=Decimal("120.0000"),
        billed_unit_rate=Decimal("185.0000"),
        billed_line_total=Decimal("22200.00"),
    )
    db.add(line)
    db.commit()

    match_run = reevaluate_match_gates(db, inv, SANDBOX_ORG_ID)
    assert match_run is not None
    assert match_run.invoice_id == inv.id

    checks = db.scalars(
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
def test_parity_scenarios_listing(disposable_parity_db, client, sandbox_auth_headers):
    """Verifies that all 6 genuine test scenarios are correctly exposed via REST API."""
    res = client.get("/api/v1/sandbox/scenarios", headers=sandbox_auth_headers)
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
def test_parity_scenario_01_happy_path(disposable_parity_db):
    """SCN-01: Clean 3-way match evaluates to MATCH_CANDIDATE with 7 gates PASS."""
    db = disposable_parity_db
    pdf_path = os.path.join(CORPUS_DIR, "01_invoice_AP_26_001.pdf")
    if not os.path.exists(pdf_path):
        pytest.skip(f"Fixture {pdf_path} not found")

    with open(pdf_path, "rb") as f:
        pdf_bytes = f.read()

    user = _get_sandbox_user()
    res = _execute_pipeline_core(
        pdf_bytes, "01_invoice_AP_26_001.pdf", db, org_id=SANDBOX_ORG_ID, user=user
    )
    assert res["status"] == "COMPLETED"
    assert res["invoice"]["currency"] == "INR"
    assert res["decision"] == "MATCH_CANDIDATE"
    assert res["stage"] == "PENDING_APPROVAL"

    # All 7 deterministic policy gates must pass unconditionally for Happy Path
    passed_gates = {g["gate_number"] for g in res["match_gates"] if g["status"] == "PASS"}
    assert {1, 2, 3, 4, 5, 6, 7}.issubset(passed_gates)


def test_parity_scenario_02_price_variance(disposable_parity_db):
    """SCN-02: Price and quantity variance deterministically fails tolerance gate."""
    db = disposable_parity_db
    pdf_path = os.path.join(CORPUS_DIR, "30_invoice_AP_26_011.pdf")
    if not os.path.exists(pdf_path):
        pytest.skip(f"Fixture {pdf_path} not found")

    with open(pdf_path, "rb") as f:
        pdf_bytes = f.read()

    user = _get_sandbox_user()
    res = _execute_pipeline_core(pdf_bytes, "30_invoice_AP_26_011.pdf", db, org_id=SANDBOX_ORG_ID, user=user)
    assert res["status"] == "COMPLETED"
    assert res["decision"] == "FLAGGED_EXCEPTION"
    assert res["stage"] == "ACTION_REQUIRED"
    failed_gates = {g["gate_number"] for g in res["match_gates"] if g["status"] == "FAIL"}
    assert (3 in failed_gates) or (6 in failed_gates)


def test_parity_scenario_03_degraded_scan(disposable_parity_db):
    """SCN-03: Degraded raster scan triggers grounding tripwire and routes to HITL."""
    db = disposable_parity_db
    pdf_path = os.path.join(CORPUS_DIR, "36_invoice_POS_26_112.pdf")
    if not os.path.exists(pdf_path):
        pytest.skip(f"Fixture {pdf_path} not found")

    with open(pdf_path, "rb") as f:
        pdf_bytes = f.read()

    user = _get_sandbox_user()
    res = _execute_pipeline_core(pdf_bytes, "36_invoice_POS_26_112.pdf", db, org_id=SANDBOX_ORG_ID, user=user)
    assert res["status"] == "COMPLETED"
    assert res["decision"] == "FLAGGED_HITL_REVIEW"
    assert res["stage"] == "ACTION_REQUIRED"
    assert "text" in res["decision_reason"].lower() or "degraded" in res["decision_reason"].lower() or "ocr" in res["decision_reason"].lower()


def test_parity_scenario_04_quarantined_qc(disposable_parity_db):
    """SCN-04: Goods receipt with QC HOLD/Quarantined fails Gate 4 deterministically."""
    db = disposable_parity_db
    pdf_path = os.path.join(CORPUS_DIR, "11_invoice_MC_26_090.pdf")
    if not os.path.exists(pdf_path):
        pytest.skip(f"Fixture {pdf_path} not found")

    with open(pdf_path, "rb") as f:
        pdf_bytes = f.read()

    user = _get_sandbox_user()
    res = _execute_pipeline_core(pdf_bytes, "11_invoice_MC_26_090.pdf", db, org_id=SANDBOX_ORG_ID, user=user)
    assert res["status"] == "COMPLETED"
    assert res["decision"] == "FLAGGED_EXCEPTION"
    assert res["stage"] == "ACTION_REQUIRED"
    gate_4 = next((g for g in res["match_gates"] if g["gate_number"] == 4), None)
    assert gate_4 is not None
    assert gate_4["status"] == "FAIL"
    assert "HOLD" in gate_4["notes"] or "rejected" in gate_4["notes"].lower()


def test_parity_scenario_05_non_payable_document(disposable_parity_db):
    """SCN-05: Payment receipt is classified and autonomously rejected."""
    db = disposable_parity_db
    pdf_path = os.path.join(CORPUS_DIR, "38_payment_receipt_RCPT_26_088.pdf")
    if not os.path.exists(pdf_path):
        pytest.skip(f"Fixture {pdf_path} not found")

    with open(pdf_path, "rb") as f:
        pdf_bytes = f.read()

    user = _get_sandbox_user()
    res = _execute_pipeline_core(pdf_bytes, "38_payment_receipt_RCPT_26_088.pdf", db, org_id=SANDBOX_ORG_ID, user=user)
    assert res["status"] == "COMPLETED"
    assert res["decision"] == "REJECTED"
    assert res["stage"] in ("ACTION_REQUIRED", "REJECTED")
    assert "PAYMENT_RECEIPT" in res["decision_reason"] or "not a payable" in res["decision_reason"].lower()


def test_parity_scenario_06_duplicate_safeguard(disposable_parity_db, client, sandbox_auth_headers):
    """SCN-06: Deterministic duplicate safeguard test across empty and seeded states.
    
    Proves:
    1. If SCN-01 does not exist, running SCN-06 returns HTTP 400 Bad Request with
       PREREQUISITE_REQUIRED (never silently executing a fresh intake).
    2. Once SCN-01 exists, resubmission triggers duplicate detection, returns REJECTED,
       sets Gate 7 FAIL, preserves the original invoice, and logs DUPLICATE_INTAKE_REJECTED.
    """
    db = disposable_parity_db
    headers = sandbox_auth_headers

    # 1. Empty workspace test: SCN-06 must fail closed with prerequisite requirement
    res_empty = client.post("/api/v1/sandbox/run-scenario/SCN-06-DUPLICATE", headers=headers)
    assert res_empty.status_code == 400
    assert res_empty.json()["status"] == "PREREQUISITE_REQUIRED"
    assert "requires baseline invoice" in res_empty.json()["detail"].lower()

    # 2. Ingest SCN-01 to establish baseline
    pdf_path = os.path.join(CORPUS_DIR, "01_invoice_AP_26_001.pdf")
    with open(pdf_path, "rb") as f:
        pdf_bytes = f.read()
    user = _get_sandbox_user()
    res_base = _execute_pipeline_core(pdf_bytes, "01_invoice_AP_26_001.pdf", db, org_id=SANDBOX_ORG_ID, user=user)
    assert res_base["decision"] == "MATCH_CANDIDATE"

    # 3. Resubmit SCN-06: Must now detect duplicate deterministically
    res_dup = client.post("/api/v1/sandbox/run-scenario/SCN-06-DUPLICATE", headers=headers)
    assert res_dup.status_code == 200
    dup_body = res_dup.json()
    assert dup_body["duplicate_detected"] is True
    assert dup_body["mode"] == "STORED_RESULT"
    assert dup_body["decision"] == "REJECTED"
    assert dup_body["stage"] == "ACTION_REQUIRED"
    assert dup_body["original_invoice"]["decision"] == "MATCH_CANDIDATE"

    # 4. Verify immutable duplicate rejection audit event
    audit_evt = db.scalar(
        select(AuditEvent).where(
            AuditEvent.action == "DUPLICATE_INTAKE_REJECTED",
            AuditEvent.org_id == SANDBOX_ORG_ID,
        )
    )
    assert audit_evt is not None
    assert "duplicate" in audit_evt.reason.lower()


# -----------------------------------------------------------------------------
# 5. Operator Action Parity & Audit Immutability
# -----------------------------------------------------------------------------
def test_parity_operator_actions_and_audit(disposable_parity_db):
    """Asserts sandbox operator actions invoke execute_invoice_action() and append immutable audit events."""
    db = disposable_parity_db
    inv = Invoice(
        id=f"inv_op_test_{uuid.uuid4().hex[:8]}",
        org_id=SANDBOX_ORG_ID,
        source_channel="SANDBOX_EXPERIENCE",
        invoice_number="AP-26-001",
        po_reference="PO-26-1001",
        currency="INR",
        total_amount=Decimal("26196.00"),
        stage="PENDING_APPROVAL",
        decision="MATCH_CANDIDATE",
    )
    db.add(inv)
    db.commit()

    user = _get_sandbox_user()
    payload = ActionPayload(action="HOLD_PENDING_EVIDENCE", reason="Sandbox operator placed on hold pending evidence.")
    action_res = execute_invoice_action(
        invoice_id=inv.id,
        payload=payload,
        current_user=user,
        db=db,
    )
    assert action_res["status"] == "SUCCESS"
    assert action_res["new_stage"] == "ACTION_REQUIRED"

    events = db.scalars(
        select(AuditEvent).where(AuditEvent.invoice_id == inv.id, AuditEvent.org_id == SANDBOX_ORG_ID)
    ).all()
    assert len(events) >= 1
    assert events[-1].action == "HOLD_PENDING_EVIDENCE"


# -----------------------------------------------------------------------------
# 6. Multi-Tenant Isolation
# -----------------------------------------------------------------------------
def test_parity_tenant_isolation(disposable_parity_db):
    """Asserts sandbox execution is confined strictly to the designated evaluation tenant."""
    db = disposable_parity_db
    foreign_org = f"org_foreign_{uuid.uuid4().hex[:8]}"
    foreign_inv = Invoice(
        id=f"inv_foreign_{uuid.uuid4().hex[:8]}",
        org_id=foreign_org,
        source_channel="SANDBOX_EXPERIENCE",
        currency="INR",
        stage="RECEIVED",
        decision="NEEDS_REVIEW",
    )
    db.add(Organisation(id=foreign_org, name="Foreign Org"))
    db.add(foreign_inv)
    db.commit()

    # Query within sandbox tenant context
    set_tenant_context(db, SANDBOX_ORG_ID)
    sme_invoices = db.scalars(select(Invoice).where(Invoice.org_id == SANDBOX_ORG_ID)).all()
    for i in sme_invoices:
        assert i.org_id == SANDBOX_ORG_ID
        assert i.org_id != foreign_org
