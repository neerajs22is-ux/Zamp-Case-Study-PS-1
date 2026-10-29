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
import pytest

from engine.mock_erp import MockERPDatabase
from engine.models import DecisionState, LineMatchStatus
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
