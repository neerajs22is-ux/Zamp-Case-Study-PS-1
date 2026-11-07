"""Automated Test Suite for PS-1 Invoice Processing Digital Employee.

Tests:
1. HP-01: Happy Path -> AUTO_APPROVED with ERP voucher
2. EC-01: Split PO Overrun -> FLAGGED_HITL_REVIEW with budget deficit calculation
3. EC-02: Duplicate Submission -> REJECTED with prior batch audit
4. EC-03: Price Spike (+35%) -> FLAGGED_HITL_REVIEW with exact variance %
5. EC-04: Low-Res Scan / Missing PO -> FLAGGED_HITL_REVIEW with auto-draft email
6. End-to-End PDF binary extraction test
"""

import json
import os
from datetime import date
import pytest

from engine.mock_erp import MockERPDatabase
from engine.models import DecisionState, DocumentType, Invoice, InvoiceLineItem, LineMatchStatus, VendorInfo
from engine.pipeline import InvoiceProcessingPipeline


FIXTURES_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "fixtures", "data")


@pytest.fixture
def fresh_pipeline():
    """Create a clean pipeline and ERP instance for each test."""
    erp = MockERPDatabase()
    return InvoiceProcessingPipeline(erp=erp)


def load_fixture(filename: str):
    path = os.path.join(FIXTURES_DIR, filename)
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def test_happy_path_auto_approved(fresh_pipeline):
    """HP-01: Clean invoice matching open PO within tolerance -> AUTO_APPROVED."""
    data = load_fixture("HP-01-Happy-Path.json")
    audit = fresh_pipeline.process(data)

    assert audit.decision == DecisionState.AUTO_APPROVED
    assert audit.overall_confidence >= 0.95
    assert audit.erp_voucher_id is not None
    assert audit.erp_voucher_id.startswith("VCHR-")
    assert len(audit.line_results) == 1
    assert audit.line_results[0].status == LineMatchStatus.MATCHED
    assert audit.line_results[0].price_variance_amount == 0.0
    assert audit.vendor_email_draft is None
    assert len(audit.stage_timings) >= 4
    assert audit.total_latency_ms > 0.0


def test_edge_case_1_split_po_overrun(fresh_pipeline):
    """EC-01: Split invoice exceeding remaining PO balance -> FLAGGED_HITL_REVIEW."""
    data = load_fixture("EC-01-Split-PO-Overrun.json")
    audit = fresh_pipeline.process(data)

    assert audit.decision == DecisionState.FLAGGED_HITL_REVIEW
    assert "split_po_overrun" in audit.discrepancy_details
    details = audit.discrepancy_details["split_po_overrun"]

    # Authorized: $10,000, Previously billed: $8,000, Remaining: $2,000, Current bill: $6,500
    assert details["remaining_balance"] == 2000.00
    assert details["invoice_amount"] == 6500.00
    assert details["deficit"] == 4500.00
    assert audit.erp_voucher_id is None
    assert audit.vendor_email_draft is not None
    assert "PO Budget Overrun" in audit.reasons[0]


def test_edge_case_2_duplicate_submission(fresh_pipeline):
    """EC-02: Resubmission of identical invoice number within 30 days -> REJECTED."""
    data = load_fixture("EC-02-Duplicate-Submission.json")
    audit = fresh_pipeline.process(data)

    assert audit.decision == DecisionState.REJECTED
    assert "duplicate" in audit.discrepancy_details
    assert audit.discrepancy_details["duplicate"]["prior_invoice_id"] == "HIST-INV-9102"
    assert audit.erp_voucher_id is None
    assert audit.vendor_email_draft is not None
    assert "REJECTED: Invoice #INV-2026-089" in audit.vendor_email_draft


def test_edge_case_3_price_variance_spike(fresh_pipeline):
    """EC-03: Line-item billed unit price exceeds contract by 35% -> FLAGGED_HITL_REVIEW."""
    data = load_fixture("EC-03-Price-Spike-Variance.json")
    audit = fresh_pipeline.process(data)

    assert audit.decision == DecisionState.FLAGGED_HITL_REVIEW
    assert "price_variance" in audit.discrepancy_details
    assert len(audit.line_results) == 1
    line = audit.line_results[0]
    assert line.status == LineMatchStatus.PRICE_VARIANCE
    assert line.billed_unit_price == 135.00
    assert line.contracted_unit_price == 100.00
    assert line.price_variance_pct == 35.00
    assert line.price_variance_amount == 35.00
    assert audit.vendor_email_draft is not None


def test_edge_case_4_low_res_scan_missing_po(fresh_pipeline):
    """EC-04: Scanned receipt with missing PO and low OCR confidence -> FLAGGED_HITL_REVIEW."""
    data = load_fixture("EC-04-Low-Res-Missing-PO.json")
    audit = fresh_pipeline.process(data)

    assert audit.decision == DecisionState.FLAGGED_HITL_REVIEW
    assert audit.overall_confidence < 0.75
    assert "low_confidence" in audit.discrepancy_details
    assert audit.vendor_email_draft is not None
    assert "Clarification for Invoice #INV-2026-404" in audit.vendor_email_draft


def test_pdf_binary_ingestion_end_to_end(fresh_pipeline):
    """Validate end-to-end extraction from generated PDF on disk."""
    pdf_path = os.path.join(FIXTURES_DIR, "HP-01-Happy-Path.pdf")
    audit = fresh_pipeline.process(pdf_path)

    assert audit.invoice_number == "INV-2026-101"
    assert audit.po_number == "PO-1042"
    assert audit.decision == DecisionState.AUTO_APPROVED
    assert len(audit.line_match_results) == 1
    assert len(audit.stage_timings) >= 4


# ---------------------------------------------------------------------------
# Additional Deterministic Regression Tests for Engine Hardening (Items 37-38)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "fixture_name,expected_decision",
    [
        ("HP-01-Happy-Path.json", DecisionState.AUTO_APPROVED),
        ("EC-01-Split-PO-Overrun.json", DecisionState.FLAGGED_HITL_REVIEW),
        ("EC-02-Duplicate-Submission.json", DecisionState.REJECTED),
        ("EC-03-Price-Spike-Variance.json", DecisionState.FLAGGED_HITL_REVIEW),
        ("EC-04-Low-Res-Missing-PO.json", DecisionState.FLAGGED_HITL_REVIEW),
    ],
)
def test_all_five_ps1_scenarios_deterministic(fresh_pipeline, fixture_name, expected_decision):
    """Item 38: Parametrised test proving exact deterministic decision outcomes across all 5 PS-1 scenarios."""
    data = load_fixture(fixture_name)
    audit = fresh_pipeline.process(data)
    assert audit.decision == expected_decision


def test_tax_id_mismatch_strictly_rejected(fresh_pipeline):
    """Item 1: Wrong tax ID + right vendor name must REJECT and never fall through to name lookup."""
    data = load_fixture("HP-01-Happy-Path.json")
    data["vendor"]["tax_id"] = "US-EIN-99-9999999"  # Deliberately invalid tax ID
    audit = fresh_pipeline.process(data)

    assert audit.decision == DecisionState.REJECTED
    assert "tax_id_mismatch" in audit.discrepancy_details
    assert audit.discrepancy_details["tax_id_mismatch"]["provided_tax_id"] == "US-EIN-99-9999999"
    assert "Tax ID" in audit.reasons[0]


def test_short_vendor_name_rejected_or_held(fresh_pipeline):
    """Item 2: Vendor name 'A' with omitted tax ID must not match Apex Cloud Technologies."""
    data = load_fixture("HP-01-Happy-Path.json")
    data["vendor"]["name"] = "A"
    data["vendor"]["tax_id"] = None
    audit = fresh_pipeline.process(data)

    assert audit.decision == DecisionState.FLAGGED_HITL_REVIEW
    assert "vendor_unapproved" in audit.discrepancy_details
    assert "Unapproved or unknown vendor: 'A'" in audit.reasons[0]


def test_arithmetic_subtotal_mismatch_flagged(fresh_pipeline):
    """Item 3 & 16: Total 9999 on lines summing to 5000 must be FLAGGED for arithmetic mismatch."""
    data = load_fixture("HP-01-Happy-Path.json")
    # Line total is 5000, but stated subtotal is 9999
    data["subtotal"] = 9999.00
    data["total_amount"] = 10424.00
    audit = fresh_pipeline.process(data)

    assert audit.decision == DecisionState.FLAGGED_HITL_REVIEW
    assert "subtotal_mismatch" in audit.discrepancy_details
    assert "Subtotal mismatch" in audit.reasons[0]


def test_arithmetic_line_math_mismatch_flagged(fresh_pipeline):
    """Item 3: Quantity * unit_price != stated line total must be FLAGGED."""
    data = load_fixture("HP-01-Happy-Path.json")
    # 10.0 * 500.0 = 5000.0, but stated total is 6000.0
    data["line_items"][0]["total"] = 6000.0
    data["subtotal"] = 6000.0
    data["total_amount"] = 6425.0
    audit = fresh_pipeline.process(data)

    assert audit.decision == DecisionState.FLAGGED_HITL_REVIEW
    assert "line_math_mismatch" in audit.discrepancy_details


def test_arithmetic_tax_rounding_tolerance_exceeded(fresh_pipeline):
    """Item 16: Grand total difference exceeding policy tax rounding tolerance (default $5.00) is FLAGGED."""
    data = load_fixture("HP-01-Happy-Path.json")
    # Subtotal 5000 + Tax 425 = 5425, stated total is 5450 (diff $25 > $5.00)
    data["total_amount"] = 5450.00
    audit = fresh_pipeline.process(data)

    assert audit.decision == DecisionState.FLAGGED_HITL_REVIEW
    assert "grand_total_mismatch" in audit.discrepancy_details


def test_reformatted_duplicate_invoice_number_detected(fresh_pipeline):
    """Item 8: Near-duplicate invoice number (dashes/spaces stripped) is caught as duplicate."""
    # First submit the original
    data1 = load_fixture("HP-01-Happy-Path.json")
    audit1 = fresh_pipeline.process(data1)
    assert audit1.decision == DecisionState.AUTO_APPROVED

    # Now submit reformatted invoice number INV2026101 without dashes
    data2 = load_fixture("HP-01-Happy-Path.json")
    data2["invoice_number"] = "INV2026101"
    audit2 = fresh_pipeline.process(data2)

    assert audit2.decision == DecisionState.REJECTED
    assert "duplicate" in audit2.discrepancy_details


def test_unmatched_line_on_single_line_po_does_not_fallback(fresh_pipeline):
    """Item 9: Single-line PO must not match completely unrelated invoice line description."""
    data = load_fixture("HP-01-Happy-Path.json")
    data["line_items"][0]["description"] = "Executive Office Furniture and Desk Chairs"
    audit = fresh_pipeline.process(data)

    assert audit.decision == DecisionState.FLAGGED_HITL_REVIEW
    assert "unmatched_line" in audit.discrepancy_details
    assert audit.line_results[0].status == LineMatchStatus.UNMATCHED


def test_inferred_po_requires_hitl_review(fresh_pipeline):
    """Item 10: Inferred PO when PO reference is missing must NOT auto-approve."""
    data = load_fixture("HP-01-Happy-Path.json")
    data["po_reference"] = None  # Vendor VEND-001 has open PO-1042
    # Reset ERP to have only 1 open PO for VEND-001
    fresh_pipeline.erp.purchase_orders.pop("PO-1042-SPLIT", None)

    audit = fresh_pipeline.process(data)
    assert audit.decision == DecisionState.FLAGGED_HITL_REVIEW
    assert "inferred_po" in audit.discrepancy_details
    assert audit.discrepancy_details["inferred_po"] == "PO-1042"


def test_bank_details_mismatch_held_for_fraud_review(fresh_pipeline):
    """Item 21: Bank account mismatch against vendor master must trigger compliance HOLD."""
    data = load_fixture("HP-01-Happy-Path.json")
    # Registered account is 123456789012, provided account is fraudulent redirection
    data["vendor"]["bank_account_number"] = "99998888777766"
    audit = fresh_pipeline.process(data)

    assert audit.decision == DecisionState.FLAGGED_HITL_REVIEW
    assert "bank_details_mismatch" in audit.discrepancy_details
    assert audit.discrepancy_details["bank_details_mismatch"]["registered_account_last4"] == "9012"


def test_line_item_quantity_aggregation(fresh_pipeline):
    """Item 17: Multiple invoice lines hitting the same PO line must aggregate quantities."""
    data = load_fixture("HP-01-Happy-Path.json")
    # PO-1042 has authorized 20.0 units. Split into two invoice lines of 12.0 each (total 24.0 > 20.0)
    data["line_items"] = [
        {
            "line_number": 1,
            "description": "Enterprise API Compute Tier 3",
            "quantity": 12.0,
            "unit_price": 500.0,
            "total": 6000.0,
        },
        {
            "line_number": 2,
            "description": "Enterprise API Compute Tier 3",
            "quantity": 12.0,
            "unit_price": 500.0,
            "total": 6000.0,
        },
    ]
    data["subtotal"] = 12000.0
    data["total_amount"] = 12000.0
    audit = fresh_pipeline.process(data)

    assert audit.decision == DecisionState.FLAGGED_HITL_REVIEW
    assert "qty_exceeded" in audit.discrepancy_details


def test_currency_formatting_inr_supported(fresh_pipeline):
    """Item 11: Currency INR is formatted with ₹ symbol and not hardcoded $."""
    data = load_fixture("HP-01-Happy-Path.json")
    data["currency"] = "INR"
    # Create price spike
    data["line_items"][0]["unit_price"] = 700.0
    data["line_items"][0]["total"] = 7000.0
    data["subtotal"] = 7000.0
    data["total_amount"] = 7425.0
    audit = fresh_pipeline.process(data)

    assert audit.decision == DecisionState.FLAGGED_HITL_REVIEW
    assert audit.vendor_email_draft is not None
    assert "₹" in audit.vendor_email_draft


def test_no_data_fabrication_on_missing_invoice_number_and_date(fresh_pipeline):
    """F-09: Extractor must not fabricate INV-{time} or date.today() when fields missing."""
    text = (
        "Acme Supplies Corp\n"
        "PO: PO-1042\n"
        "Description\n"
        "1 Widget Model A 10 500.00 5000.00\n"
        "Subtotal: $5,000.00\n"
        "Tax: $0.00\n"
        "Grand Total: $5,000.00\n"
    )
    invoice = fresh_pipeline._extract(DocumentType.DIGITAL_PDF, text, parsed_json=None)
    assert invoice.invoice_number is None
    assert invoice.invoice_date is None

    audit = fresh_pipeline.rule_engine.evaluate(invoice, fresh_pipeline.erp)
    assert audit.decision == DecisionState.FLAGGED_HITL_REVIEW
    assert audit.discrepancy_details.get("missing_invoice_number") is True
    assert audit.discrepancy_details.get("missing_invoice_date") is True


def test_po_vendor_ownership_rejection(fresh_pipeline):
    """F-18: Invoices citing a PO belonging to a different vendor must be immediately REJECTED."""
    data = load_fixture("HP-01-Happy-Path.json")
    # PO-1042 belongs to VEND-001 (Acme Supplies Corp). Change vendor to VEND-002 (Logistics Pro).
    data["vendor"]["name"] = "Global Logistics Partners LLC"
    data["vendor"]["tax_id"] = "US-EIN-12-8492019"
    audit = fresh_pipeline.process(data)

    assert audit.decision == DecisionState.REJECTED
    assert "po_vendor_mismatch" in audit.discrepancy_details
    assert audit.discrepancy_details["po_vendor_mismatch"]["po_vendor_id"] == "VEND-001"
    assert audit.discrepancy_details["po_vendor_mismatch"]["billing_vendor_id"] == "VEND-002"


def test_multiline_price_variance_recorded_as_list(fresh_pipeline):
    """F-20: Multiple price spike lines must all be preserved in price_variances list."""
    data = load_fixture("HP-01-Happy-Path.json")
    data["line_items"] = [
        {
            "line_number": 1,
            "description": "Enterprise API Compute Tier 3",
            "quantity": 5.0,
            "unit_price": 550.0,
            "total": 2750.0,
        },
        {
            "line_number": 2,
            "description": "Enterprise API Compute Tier 3",
            "quantity": 5.0,
            "unit_price": 600.0,
            "total": 3000.0,
        },
    ]
    data["subtotal"] = 5750.0
    data["tax_amount"] = 431.25
    data["total_amount"] = 6181.25

    audit = fresh_pipeline.process(data)
    assert audit.decision == DecisionState.FLAGGED_HITL_REVIEW
    assert "price_variances" in audit.discrepancy_details
    assert len(audit.discrepancy_details["price_variances"]) == 2
    assert audit.discrepancy_details["price_variances"][0]["line_number"] == 1
    assert audit.discrepancy_details["price_variances"][1]["line_number"] == 2


def test_genuine_5_stages_executed_honestly(fresh_pipeline):
    """F-01/F-02: Pipeline executes exactly 5 honest stages with valid timings and status."""
    data = load_fixture("HP-01-Happy-Path.json")
    audit = fresh_pipeline.process(data)

    assert len(audit.stage_timings) == 5
    stage_names = [st.stage_name for st in audit.stage_timings]
    assert "1. Ingestion & Classification" in stage_names[0]
    assert "2. Structured Extraction" in stage_names[1]
    assert "3. ERP Cross-Reference" in stage_names[2]
    assert "4. AOP Policy & Tolerance Match" in stage_names[3]
    assert "5. Decision State & Audit Packaging" in stage_names[4]

    for st in audit.stage_timings:
        assert st.status == "SUCCESS"
