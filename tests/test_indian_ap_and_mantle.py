"""Unit and integration tests for Indian AP document intelligence, Mantle schemas, and duplicate detection."""

from __future__ import annotations

import os
import pytest

from engine.duplicate_detector import DuplicateDetector
from engine.grounding import verify_extracted_evidence
from engine.hybrid_extractor import HybridAPExtractor
from engine.indian_tax_rules import IndianAPRuleEngine
from engine.schemas import (
    CommercialDocumentType,
    ExtractedLineItem,
    FieldEvidence,
    MantleInvoiceExtraction,
)


def test_schema_validation_clean():
    inv = MantleInvoiceExtraction(
        document_type=CommercialDocumentType.INVOICE,
        is_payable_invoice=True,
        supplier_name="Asterion Precision Components Pvt Ltd",
        supplier_gstin="29SYNTH0001A1Z5",
        invoice_number="AP-26-001",
        invoice_date="2026-09-02",
        po_reference="PO-26-1001",
        currency="INR",
        taxable_value=22200.0,
        cgst_amount=1998.0,
        sgst_amount=1998.0,
        igst_amount=0.0,
        total_tax_amount=3996.0,
        grand_total=26196.0,
        line_items=[
            ExtractedLineItem(
                item_description="Precision turned steel shafts",
                quantity=120,
                unit_price=185.0,
                taxable_amount=22200.0,
                cgst_rate=9.0,
                cgst_amount=1998.0,
                sgst_rate=9.0,
                sgst_amount=1998.0,
                total_amount=26196.0,
            )
        ]
    )
    assert inv.invoice_number == "AP-26-001"
    assert inv.grand_total == 26196.0


def test_grounding_tripwires():
    inv = MantleInvoiceExtraction(
        document_type=CommercialDocumentType.INVOICE,
        is_payable_invoice=True,
        supplier_name="Asterion Precision Components Pvt Ltd",
        supplier_gstin="29SYNTH0001A1Z5",
        invoice_number="AP-26-001",
        invoice_date="2026-09-02",
        currency="INR",
        taxable_value=22200.0,
        grand_total=26196.0,
    )
    pages = [(1, "Supplier: Asterion Precision Components Pvt Ltd\nGSTIN: 29SYNTH0001A1Z5\nDocument number AP-26-001\nGrand total INR 26,196.00")]
    passed, unverified, _ = verify_extracted_evidence(inv, pages)
    assert passed is True
    assert len(unverified) == 0

    # Tripwire failure: hallucinated invoice number
    inv.invoice_number = "HALLUCINATED-999"
    passed_fail, unverified_fail, _ = verify_extracted_evidence(inv, pages)
    assert passed_fail is False
    assert "invoice_number" in unverified_fail


def test_semantic_duplicate_detection():
    detector = DuplicateDetector()
    file_bytes_1 = b"%PDF-1.4 file version 1 with notes"
    file_bytes_2 = b"%PDF-1.4 file version 2 with reissued stamp"

    # Register first file
    detector.register(
        document_id="APTC-001",
        filename="invoice_1.pdf",
        file_bytes=file_bytes_1,
        supplier_name="Asterion Precision",
        supplier_gstin="29SYNTH0001A1Z5",
        invoice_number="AP-26-001",
        invoice_date="2026-09-02",
        grand_total=26196.0,
    )

    # Check identical file bytes
    res_exact = detector.check_duplicate(
        file_bytes=file_bytes_1,
        supplier_name="Asterion Precision",
        supplier_gstin="29SYNTH0001A1Z5",
        invoice_number="AP-26-001",
        invoice_date="2026-09-02",
        grand_total=26196.0,
    )
    assert res_exact.is_duplicate is True
    assert res_exact.duplicate_type == "EXACT_HASH"

    # Check semantic duplicate with DIFFERENT bytes
    res_semantic = detector.check_duplicate(
        file_bytes=file_bytes_2,
        supplier_name="Asterion Precision",
        supplier_gstin="29SYNTH0001A1Z5",
        invoice_number="AP-26-001",
        invoice_date="2026-09-02",
        grand_total=26196.0,
    )
    assert res_semantic.is_duplicate is True
    assert res_semantic.duplicate_type == "SEMANTIC_COMMERCIAL"
    assert res_semantic.existing_document_id == "APTC-001"


def test_gst_arithmetic_rules():
    rules = IndianAPRuleEngine()
    clean_inv = MantleInvoiceExtraction(
        document_type=CommercialDocumentType.INVOICE,
        is_payable_invoice=True,
        supplier_name="Asterion",
        supplier_gstin="29SYNTH0001A1Z5",
        invoice_number="AP-26-001",
        invoice_date="2026-09-02",
        currency="INR",
        taxable_value=22200.0,
        cgst_amount=1998.0,
        sgst_amount=1998.0,
        igst_amount=0.0,
        total_tax_amount=3996.0,
        grand_total=26196.0,
    )
    res = rules.verify_tax_arithmetic(clean_inv)
    assert res.is_valid is True

    # Bad math invoice
    bad_inv = MantleInvoiceExtraction(
        document_type=CommercialDocumentType.INVOICE,
        is_payable_invoice=True,
        supplier_name="Asterion",
        supplier_gstin="29SYNTH0001A1Z5",
        invoice_number="AP-26-001",
        invoice_date="2026-09-02",
        currency="INR",
        taxable_value=22200.0,
        cgst_amount=1998.0,
        sgst_amount=1998.0,
        igst_amount=0.0,
        total_tax_amount=3996.0,
        grand_total=30000.0,  # Grand total does not match sum
    )
    res_bad = rules.verify_tax_arithmetic(bad_inv)
    assert res_bad.is_valid is False
