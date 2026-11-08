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
        "vendor": {"name": "Apex Cloud Technologies Inc.", "tax_id": "US-EIN-94-3829102"},
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
    assert "arithmetic_mismatch" in audit.discrepancy_details or "extraction_failed" in audit.discrepancy_details
    assert audit.stage_timings[1].status == "FAILED"


def test_arithmetic_mismatch_flags_instead_of_crashing(fresh_pipeline):
    payload = invoice_payload(subtotal=100.0, tax_amount=5.0, total_amount=999.0)

    audit = fresh_pipeline.process(payload)

    assert audit.decision == DecisionState.FLAGGED_HITL_REVIEW
    assert "arithmetic_mismatch" in audit.discrepancy_details or "extraction_failed" in audit.discrepancy_details


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

    assert audit.decision in (DecisionState.FLAGGED_HITL_REVIEW, DecisionState.REJECTED)
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


# -


# ---------------------------------------------------------------------------
# 7. Tier 1-4 Inspector Audit Remediation Invariants
# ---------------------------------------------------------------------------

def test_barcode_scanner_not_misclassified_as_scan(fresh_pipeline):
    """An invoice with 'Wireless Barcode Scanner' should not be misclassified as SCANNED_IMAGE."""
    import io
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas
    
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    c.drawString(50, 700, "INVOICE: INV-SCANNER-99")
    c.drawString(50, 680, "Date: 2026-10-29")
    c.drawString(50, 660, "Vendor: Apex Cloud Technologies Inc.")
    c.drawString(50, 640, "Tax ID: US-EIN-94-3829102")
    c.drawString(50, 620, "PO: PO-1042")
    c.drawString(50, 600, "Item: Wireless Barcode Scanner Model X-200")
    c.drawString(50, 580, "Subtotal: $5,000.00")
    c.drawString(50, 560, "Tax: $425.00")
    c.drawString(50, 540, "Grand Total: $5,425.00")
    c.save()
    pdf_bytes = buf.getvalue()
    
    doc_type, raw_text, _ = fresh_pipeline._ingest(pdf_bytes, filename="scanner_inv.pdf")
    assert doc_type == DocumentType.DIGITAL_PDF


def test_vendor_name_mismatch_held_when_tax_id_matches(fresh_pipeline):
    """When Tax ID matches master but entity name differs, Gate 2 must flag FLAGGED_HITL_REVIEW."""
    payload = invoice_payload(
        vendor={"name": "Impersonator Shell LLC", "tax_id": "US-EIN-94-3829102"},
    )
    audit = fresh_pipeline.process(payload)
    assert audit.decision == DecisionState.FLAGGED_HITL_REVIEW
    assert "vendor_name_mismatch" in audit.discrepancy_details


def test_tax_id_mismatch_downgraded_to_hold_on_low_confidence(fresh_pipeline):
    """Tax ID mismatch on low-confidence extraction (< 0.75) must downgrade hard rejection to FLAGGED_HITL_REVIEW."""
    payload = invoice_payload(
        vendor={"name": "Apex Cloud Technologies Inc.", "tax_id": "US-EIN-99-9999999"},
        confidence_scores={"overall": 0.65, "tax_id": 0.60},
    )
    audit = fresh_pipeline.process(payload)
    assert audit.decision == DecisionState.FLAGGED_HITL_REVIEW
    assert "tax_id_unverified_scan" in audit.discrepancy_details


def test_empty_description_does_not_match_po_line(fresh_pipeline):
    """Invoice line with degenerate punctuation-only description must not match PO lines via substring."""
    payload = invoice_payload(
        line_items=[
            {"line_number": 1, "description": "--", "quantity": 10.0, "unit_price": 500.0, "total": 5000.0}
        ]
    )
    audit = fresh_pipeline.process(payload)
    assert len(audit.line_match_results) == 1
    assert audit.line_match_results[0].status == LineMatchStatus.UNMATCHED


def test_in_flight_duplicate_detected(fresh_pipeline):
    """An invoice held for HITL review must prevent duplicate re-submission in-flight."""
    payload1 = invoice_payload(
        invoice_number="INV-INFLIGHT-01",
        line_items=[
            {"line_number": 1, "description": "Enterprise API Compute Tier 3", "quantity": 10.0,
             "unit_price": 600.0, "total": 6000.0}
        ],
        subtotal=6000.0,
        total_amount=6000.0,
    )
    audit1 = fresh_pipeline.process(payload1)
    assert audit1.decision == DecisionState.FLAGGED_HITL_REVIEW

    # Resubmit exact same invoice while first is still pending in-flight
    audit2 = fresh_pipeline.process(payload1)
    assert audit2.decision == DecisionState.FLAGGED_HITL_REVIEW
    assert "duplicate_in_review" in audit2.discrepancy_details
    assert audit2.discrepancy_details["duplicate_in_review"]["amount"] == 6000.0


def test_recurring_billing_vendor_exempt_from_fuzzy_duplicate(fresh_pipeline):
    """Recurring billing vendors should not be blocked by fuzzy amount duplicate checks for distinct invoice numbers."""
    from datetime import date
    from engine.models import HistoricalInvoiceRecord
    
    vendor = fresh_pipeline.erp.vendors["VEND-001"]
    vendor.is_recurring_billing = True

    fresh_pipeline.erp.record_processed_invoice(
        HistoricalInvoiceRecord(
            invoice_id="REC-INV-01",
            vendor_id="VEND-001",
            invoice_number="INV-JAN-2026",
            amount=5000.00,
            invoice_date=date(2026, 1, 15),
            processed_date=date(2026, 1, 15),
            sha256_hash="HASH_JAN_2026",
            batch_id="BATCH-01",
            status=DecisionState.AUTO_APPROVED,
        )
    )

    payload = invoice_payload(
        invoice_number="INV-FEB-2026",
        invoice_date="2026-02-15",
        subtotal=5000.0,
        total_amount=5000.0,
        line_items=[
            {"line_number": 1, "description": "Enterprise API Compute Tier 3", "quantity": 10.0,
             "unit_price": 500.0, "total": 5000.0}
        ],
    )
    audit = fresh_pipeline.process(payload)
    assert "duplicate_submission" not in audit.discrepancy_details


def test_bank_mismatch_approval_blocked_without_callback_notes(fresh_pipeline):
    """Manual approval of bank details mismatch must fail without telephone callback confirmation."""
    from engine.server import pipeline as server_pipeline
    
    payload = invoice_payload(
        invoice_number="INV-BANK-01",
        vendor={
            "name": "Apex Cloud Technologies Inc.",
            "tax_id": "US-EIN-94-3829102",
            "bank_account_number": "FR7630006000011234567890189"
        }
    )
    audit = server_pipeline.process(payload)
    assert audit.decision == DecisionState.FLAGGED_HITL_REVIEW
    assert "bank_details_mismatch" in audit.discrepancy_details

    # Blocked without callback notes (route is /api/invoices/{run_id}/action)
    res = client.post(
        f"/api/invoices/{audit.run_id}/action",
        json={"action": "APPROVE", "notes": "Approved by AP Clerk without details"}
    )
    assert res.status_code == 403
    assert "Fraud Risk Gate" in res.json()["detail"]

    # Allowed with telephone callback verification notes
    res_ok = client.post(
        f"/api/invoices/{audit.run_id}/action",
        json={"action": "APPROVE", "notes": "Telephone callback verified with Vendor Treasury Lead Jane Doe"}
    )
    assert res_ok.status_code == 200
    assert res_ok.json()["decision"] == "MANUALLY_APPROVED"


def test_po_line_and_header_drawdown_unified_balance(fresh_pipeline):
    """Header remaining balance and line remaining balance must draw down deterministically."""
    po = fresh_pipeline.erp.get_po("PO-1042")
    assert po.remaining_balance == 10000.00
    assert po.line_items[0].invoiced_amount == 0.0

    payload = invoice_payload(
        invoice_number="INV-BAL-TEST",
        line_items=[
            {"line_number": 1, "description": "Enterprise API Compute Tier 3", "quantity": 5.0,
             "unit_price": 500.0, "total": 2500.0}
        ],
        subtotal=2500.0,
        tax_amount=0.0,
        total_amount=2500.0,
    )
    audit = fresh_pipeline.process(payload)
    assert audit.decision == DecisionState.AUTO_APPROVED

    po_after = fresh_pipeline.erp.get_po("PO-1042")
    assert po_after.remaining_balance == 7500.00
    assert po_after.line_items[0].invoiced_amount == 2500.00
    assert (po_after.line_items[0].total_amount - po_after.line_items[0].invoiced_amount) == 7500.00

