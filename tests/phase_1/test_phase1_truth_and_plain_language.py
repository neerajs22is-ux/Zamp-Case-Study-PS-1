"""Automated Verification Suite for Phase 1: Truth & Plain Language.

Verifies:
1. Backend runtime configuration and policy export (DUAL_APPROVAL_THRESHOLD_INR == 500000.00, RATE_TOLERANCE_PERCENT == 1.50).
2. GET /api/v1/invoices/{id} returns authoritative policy block.
3. Neither API nor frontend exposes internal developer governance terminology (D-04, Tier 2 gate overrides, production truth rules, tenant partition).
4. Truthful verdict headline 'Invoice Review Complete (Internal Sign-Off)' and explanatory decoupling text.
5. Truthful ERP provenance disclosure in frontend.
6. Straightforward AI extraction terminology ('Information Read by AI', 'Verified by automatic checks').
"""

import os
import re
import pytest
from fastapi.testclient import TestClient
from backend.main import app
from backend.core.config import settings
from backend.core.database import SessionLocal
from backend.models.domain import Invoice, Organisation, RoleAssignment, User
from engine.sme_eval_setup import SME_USERS, generate_sme_jwt, ensure_jwt_secret

client = TestClient(app)


@pytest.fixture(scope="module")
def sme_tokens():
    jwt_secret = ensure_jwt_secret()
    tokens = {
        u["role"]: generate_sme_jwt(u, jwt_secret)
        for u in SME_USERS
    }
    return tokens


def test_01_authoritative_backend_policy_configuration():
    """Verify runtime thresholds match certified business rules."""
    assert settings.DUAL_APPROVAL_THRESHOLD_INR == 500000.00, "Dual approval threshold must be 500,000 INR"
    assert settings.RATE_TOLERANCE_PERCENT == 1.50, "Price tolerance must be 1.50%"
    assert settings.ROUNDING_TOLERANCE_INR == 20.00, "Rounding tolerance must be 20.00 INR"


def test_02_invoice_detail_exposes_runtime_policy(sme_tokens):
    """Verify GET /api/v1/invoices/{id} provides the policy block for dynamic UI rendering."""
    headers = {"Authorization": f"Bearer {sme_tokens['AP_LEAD']}"}
    
    # Query any invoice in org_sme_eval
    with SessionLocal() as db:
        inv = db.query(Invoice).filter(Invoice.org_id == "org_sme_eval").first()
        assert inv is not None, "Evaluation tenant must have at least one invoice"
        inv_id = inv.id

    res = client.get(f"/api/v1/invoices/{inv_id}", headers=headers)
    assert res.status_code == 200
    data = res.json()

    assert "policy" in data, "Invoice detail must return policy block"
    assert data["policy"]["dual_approval_threshold_inr"] == 500000.00
    assert data["policy"]["rate_tolerance_percent"] == 1.50
    assert data["policy"]["rounding_tolerance_inr"] == 20.00


def test_03_approvals_api_exposes_threshold(sme_tokens):
    """Verify /api/v1/approvals returns the authoritative threshold."""
    headers = {"Authorization": f"Bearer {sme_tokens['CONTROLLER']}"}
    res = client.get("/api/v1/approvals", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["threshold_inr"] == 500000.00


def test_04_failed_gate_error_uses_plain_business_language(sme_tokens):
    """Verify failed gate rejection uses clean operator language without developer tags like D-04."""
    headers = {"Authorization": f"Bearer {sme_tokens['AP_LEAD']}"}

    # Find an invoice with failing gates in org_sme_eval
    with SessionLocal() as db:
        inv = db.query(Invoice).filter(
            Invoice.org_id == "org_sme_eval",
            Invoice.decision.in_(["FLAGGED_EXCEPTION", "FLAGGED_HITL_REVIEW"])
        ).first()
        assert inv is not None, "Need an exception invoice"
        exc_inv_id = inv.id

    res = client.post(
        f"/api/v1/invoices/{exc_inv_id}/actions",
        json={"action": "APPROVE_AP_REVIEW", "reason": "Attempting override"},
        headers=headers,
    )
    assert res.status_code == 400
    detail = res.json()["detail"]

    # Verify absence of developer tags
    assert "D-04" not in detail, "Error message must not expose internal D-04 tag"
    assert "Tier 2" not in detail, "Error message must not expose Tier 2 tag"
    assert "Policy overrides are disabled" in detail, "Error must use clear business language"


def test_05_frontend_source_has_zero_forbidden_engineering_strings():
    """Verify frontend code contains zero forbidden engineering terms."""
    forbidden_terms = [
        "D-04 Deferred",
        "Tier 2 gate overrides",
        "production truth rules",
        "Binding Production Engineering Specification",
        "tenant partition",
        "Invoice Approved for Payment Run",
        "Mantle Bedrock OCR",
        "computed strictly against synchronized SAP S/4HANA ERP records",
    ]

    frontend_dir = os.path.join("frontend", "src")
    violations = []

    for root, _, files in os.walk(frontend_dir):
        for f in files:
            if not f.endswith((".ts", ".tsx")):
                continue
            path = os.path.join(root, f)
            with open(path, "r", encoding="utf-8") as file_obj:
                content = file_obj.read()
                for term in forbidden_terms:
                    if term in content:
                        violations.append(f"{path}: Contains forbidden string '{term}'")

    assert len(violations) == 0, f"Found forbidden strings in frontend: {violations}"


def test_06_frontend_source_contains_phase1_truth_strings():
    """Verify frontend source files contain the required Phase 1 truthful replacements."""
    inv_detail_path = os.path.join("frontend", "src", "pages", "InvoiceDetailPage.tsx")
    with open(inv_detail_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Truth strings verified
    assert "Invoice Review Complete (Internal Sign-Off)" in content, "Must use truthful verdict headline"
    assert "Evaluated against authoritative procurement reference snapshots" in content, "Must use truthful ERP provenance"
    assert "Live SAP S/4HANA synchronization is not configured" in content, "Must disclose evaluation fixtures"
    assert "Approval blocked until the failed checks are resolved" in content, "Must use plain language banner badge"
    assert "Information Read by AI" in content, "Must use plain language extraction header"
    assert "Verified by automatic checks" in content, "Must use plain language verification badge"
    assert "Verification Status" in content, "Must label table column accurately"
    assert "DEFAULT_POLICY" in content, "Must read policy from central constants"
    assert "±${rateTolerancePercent.toFixed(2)}%" in content, "Tour must format rate tolerance dynamically"
