"""Regression tests for the P0 hardening pass.

Covers:
1. PDF text extraction (grand total vs subtotal, line-item table parsing).
2. Fail-soft handling of unreadable / inconsistent documents (no crash).
3. Duplicate detection against invoices approved in the same session.
4. PO line quantity tracking after approval.
5. Quantity-exceeded, zero-line-item, and tolerance edge cases.
6. Idempotent scenario re-runs and upload error handling.
"""

import json
import os

import pytest
from fastapi.testclient import TestClient
from pypdf import PdfReader

from engine.mock_erp import MockERPDatabase
from engine.models import DecisionState, DocumentType, LineMatchStatus
from engine.pipeline import InvoiceProcessingPipeline
from engine.server import app

FIXTURES_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "fixtures", "data")


@pytest.fixture
def fresh_pipeline():
    return InvoiceProcessingPipeline(erp=MockERPDatabase())


def fixture_path(name: str) -> str:
    return os.path.join(FIXTURES_DIR, name)


def load_json(name: str) -> dict:
    with open(fixture_path(name), "r", encoding="utf-8") as f:
        return json.load(f)


def pdf_text(name: str) -> str:
    reader = PdfReader(fixture_path(name))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def invoice_payload(**overrides):
    """Minimal structured-JSON invoice for the Apex vendor on PO-1042."""
    payload = {
        "invoice_number": "INV-TEST-001",
        "invoice_date": "2026-10-29",
        "vendor": {"name": "Apex Cloud Technologies Inc."},
        "po_reference": "PO-1042",
        "line_items": [],
        "subtotal": 100.0,
        "tax_amount": 0.0,
        "total_amount": 100.0,
        "confidence_scores": {"overall": 0.98},
    }
    payload.update(overrides)
    return payload


# ---------------------------------------------------------------------------
# 1. PDF extraction
# ---------------------------------------------------------------------------


def test_pdf_text_extraction_uses_grand_total_not_subtotal(fresh_pipeline):
    invoice = fresh_pipeline._extract(DocumentType.DIGITAL_PDF, pdf_text("HP-01-Happy-Path.pdf"), None)

    assert invoice.subtotal == 5000.00
    assert invoice.tax_amount == 425.00
    assert invoice.total_amount == 5425.00


def test_pdf_text_extraction_parses_line_item_table(fresh_pipeline):
    invoice = fresh_pipeline._extract(DocumentType.DIGITAL_PDF, pdf_text("HP-01-Happy-Path.pdf"), None)

    assert len(invoice.line_items) == 1
    line = invoice.line_items[0]
    assert line.description == "Enterprise API Compute Tier 3"
    assert line.quantity == 10.0
    assert line.unit_price == 500.00
    assert line.total == 5000.00


def test_pdf_invoice_reaches_two_way_line_match(fresh_pipeline):
    audit = fresh_pipeline.process(fixture_path("HP-01-Happy-Path.pdf"))

    assert audit.decision == DecisionState.AUTO_APPROVED
    assert len(audit.line_match_results) == 1
    assert audit.line_match_results[0].status == LineMatchStatus.MATCHED
    assert "$5,425.00" in audit.reasons[-1]


def test_scanned_pdf_ocr_confidence_flagged(fresh_pipeline):
    audit = fresh_pipeline.process(fixture_path("EC-04-Low-Res-Missing-PO.pdf"))

    assert audit.decision == DecisionState.FLAGGED_HITL_REVIEW
    assert audit.overall_confidence < 0.75
    assert "low_confidence" in audit.discrepancy_details


# ---------------------------------------------------------------------------
# 2. Fail-soft on unreadable / inconsistent documents
# ---------------------------------------------------------------------------


def test_unreadable_document_flags_instead_of_crashing(fresh_pipeline):
    audit = fresh_pipeline.process(b"not a pdf at all")

    assert audit.decision == DecisionState.FLAGGED_HITL_REVIEW
    assert "extraction_failed" in audit.discrepancy_details
    assert audit.stage_timings[1].status == "FAILED"


def test_arithmetic_mismatch_flags_instead_of_crashing(fresh_pipeline):
    payload = invoice_payload(subtotal=100.0, tax_amount=5.0, total_amount=999.0)

    audit = fresh_pipeline.process(payload)

    assert audit.decision == DecisionState.FLAGGED_HITL_REVIEW
    assert "extraction_failed" in audit.discrepancy_details


# ---------------------------------------------------------------------------
# 3. Duplicate detection across live runs
# ---------------------------------------------------------------------------


def test_approved_invoice_is_recorded_in_historical_ledger(fresh_pipeline):
    fresh_pipeline.process(load_json("HP-01-Happy-Path.json"))

    numbers = [r.invoice_number for r in fresh_pipeline.erp.historical_invoices]
    assert len(numbers) == 2  # seeded EC-02 record + this approval
    assert "INV-2026-101" in numbers


def test_same_invoice_submitted_twice_is_rejected(fresh_pipeline):
    payload = invoice_payload(
        line_items=[
            {"line_number": 1, "description": "Enterprise API Compute Tier 3", "quantity": 1.0,
             "unit_price": 100.0, "total": 100.0}
        ]
    )

    first = fresh_pipeline.process(payload)
    second = fresh_pipeline.process(payload)

    assert first.decision == DecisionState.AUTO_APPROVED
    assert second.decision == DecisionState.REJECTED
    assert "duplicate" in second.discrepancy_details


# ---------------------------------------------------------------------------
# 4. PO drawdown accounting
# ---------------------------------------------------------------------------


def test_approved_invoice_advances_po_line_quantity(fresh_pipeline):
    fresh_pipeline.process(load_json("HP-01-Happy-Path.json"))

    po = fresh_pipeline.erp.get_po("PO-1042")
    assert po.line_items[0].invoiced_quantity == 10.0
    assert po.line_items[0].invoiced_amount == 5000.00


# ---------------------------------------------------------------------------
# 5. Matching edge cases
# ---------------------------------------------------------------------------


def test_invoice_without_line_items_is_flagged(fresh_pipeline):
    audit = fresh_pipeline.process(invoice_payload(line_items=[]))

    assert audit.decision == DecisionState.FLAGGED_HITL_REVIEW
    assert "missing_line_items" in audit.discrepancy_details


def test_quantity_above_po_line_is_flagged(fresh_pipeline):
    payload = invoice_payload(
        invoice_number="INV-QTY-1",
        line_items=[
            {"line_number": 1, "description": "Enterprise API Compute Tier 3", "quantity": 25.0,
             "unit_price": 500.0, "total": 12500.0}
        ],
        subtotal=12500.0,
        total_amount=12500.0,
    )

    audit = fresh_pipeline.process(payload)

    assert audit.decision == DecisionState.FLAGGED_HITL_REVIEW
    assert "qty_exceeded" in audit.discrepancy_details


def test_price_variance_within_both_thresholds_is_absorbed(fresh_pipeline):
    payload = invoice_payload(
        invoice_number="INV-MINOR-1",
        line_items=[
            {"line_number": 1, "description": "Enterprise API Compute Tier 3", "quantity": 10.0,
             "unit_price": 501.0, "total": 5010.0}
        ],
        subtotal=5010.0,
        total_amount=5010.0,
    )

    audit = fresh_pipeline.process(payload)

    assert audit.decision == DecisionState.AUTO_APPROVED


def test_price_variance_flagged_when_only_percentage_exceeds(fresh_pipeline):
    payload = {
        "invoice_number": "INV-PCT-1",
        "invoice_date": "2026-10-29",
        "vendor": {"name": "Global Logistics Partners LLC"},
        "po_reference": "PO-2090",
        "line_items": [
            {"line_number": 1, "description": "Dedicated Freight Coordination", "quantity": 10.0,
             "unit_price": 119.0, "total": 1190.0}
        ],
        "subtotal": 1190.0,
        "tax_amount": 0.0,
        "total_amount": 1190.0,
        "confidence_scores": {"overall": 0.96},
    }

    audit = fresh_pipeline.process(payload)

    assert audit.decision == DecisionState.FLAGGED_HITL_REVIEW
    assert "price_variance" in audit.discrepancy_details


def test_unknown_vendor_rejected(fresh_pipeline):
    payload = invoice_payload(vendor={"name": "Totally Unknown Supplier LLC"})

    audit = fresh_pipeline.process(payload)

    assert audit.decision == DecisionState.REJECTED
    assert "vendor_unapproved" in audit.discrepancy_details


def test_suspended_vendor_rejected(fresh_pipeline):
    payload = invoice_payload(vendor={"name": "Suspended Logistics Inc."})

    audit = fresh_pipeline.process(payload)

    assert audit.decision == DecisionState.REJECTED
    assert "vendor_suspended" in audit.discrepancy_details


# ---------------------------------------------------------------------------
# 6. API behaviour
# ---------------------------------------------------------------------------

client = TestClient(app)


def test_scenario_rerun_is_idempotent():
    first = client.post("/api/run-scenario/HP-01-Happy-Path")
    second = client.post("/api/run-scenario/HP-01-Happy-Path")

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["decision"] == "AUTO_APPROVED"
    assert second.json()["decision"] == "AUTO_APPROVED"


def test_upload_unreadable_pdf_returns_flagged_audit():
    res = client.post(
        "/api/upload-invoice",
        files={"file": ("broken.pdf", b"not a pdf at all", "application/pdf")},
    )

    assert res.status_code == 200
    assert res.json()["decision"] == "FLAGGED_HITL_REVIEW"


def test_upload_invalid_json_returns_400():
    res = client.post(
        "/api/upload-invoice",
        files={"file": ("broken.json", b"{not valid json", "application/json")},
    )

    assert res.status_code == 400


def test_stream_scenario_emits_final_decision():
    with client.stream("GET", "/api/stream-scenario/HP-01-Happy-Path") as res:
        body = "".join(res.iter_text())

    assert res.status_code == 200
    assert "DECISION_FINAL" in body
    assert "AUTO_APPROVED" in body
