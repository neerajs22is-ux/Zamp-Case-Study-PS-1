"""Phase D.5 Acceptance Tests ?" OCR Readiness & Fail-Closed Guardrails.

Verifies:
1. Local open-source rasterization via pypdfium2 preserving page boundaries and provenance.
2. Contrast and luminance pre-screening detects degraded scans (APTC-037).
3. Fail-closed routing when Tesseract binary is not installed or when OCR confidence is low (< 75%).
4. Bounding box coordinates and word-level provenance retention.
5. Zero dependency on expensive commercial cloud vision APIs.
"""

from __future__ import annotations

import os
import unittest.mock as mock
import pytest
from PIL import Image

from engine.ocr_engine import OCREngine, OCRDocumentResult, OCRPageResult, OCRWord


@pytest.fixture
def ocr_engine():
    return OCREngine(min_contrast_stddev=10.0, min_confidence_threshold=75.0)


@pytest.fixture
def aptc_036_bytes():
    path = os.path.join("tests", "evaluation_corpus_v2", "invoices", "36_invoice_POS_26_112.pdf")
    with open(path, "rb") as f:
        return f.read()


@pytest.fixture
def aptc_037_bytes():
    path = os.path.join("tests", "evaluation_corpus_v2", "invoices", "37_invoice_CP_26_025.pdf")
    with open(path, "rb") as f:
        return f.read()


def test_01_ocr_rasterization_preserves_page_boundaries(ocr_engine, aptc_036_bytes):
    """Verifies pypdfium2 rasterizes PDF and tracks page boundaries without data loss."""
    res = ocr_engine.process_pdf_bytes(aptc_036_bytes, filename="36_invoice_POS_26_112.pdf", document_id="APTC-036")
    assert res.total_pages == 1
    assert len(res.pages) == 1
    page0 = res.pages[0]
    assert page0.page_number == 1
    assert page0.mean_luminance > 200.0


def test_02_contrast_analysis_detects_degraded_scan_aptc_037(ocr_engine, aptc_037_bytes):
    """Verifies that APTC-037 is correctly identified as a low-contrast degraded scan."""
    res = ocr_engine.process_pdf_bytes(aptc_037_bytes, filename="37_invoice_CP_26_025.pdf", document_id="APTC-037")
    assert res.is_degraded is True
    assert res.routing_recommendation == "FLAGGED_HITL_REVIEW"
    assert res.pages[0].is_degraded_contrast is True
    assert res.pages[0].contrast_stddev < 10.0


def test_03_ocr_missing_binary_fails_closed(ocr_engine, aptc_036_bytes):
    """Verifies that missing Tesseract executable fails closed to FLAGGED_HITL_REVIEW."""
    with mock.patch("pytesseract.image_to_data") as mock_tess:
        import pytesseract
        mock_tess.side_effect = pytesseract.TesseractNotFoundError()
        res = ocr_engine.process_pdf_bytes(aptc_036_bytes, filename="36_invoice_POS_26_112.pdf", document_id="APTC-036")
        assert res.routing_recommendation == "FLAGGED_HITL_REVIEW"
        assert res.status == "TESSERACT_NOT_AVAILABLE"
        assert res.ocr_available is False
        assert any("Tesseract binary not installed" in r for r in res.reasons)


def test_04_ocr_low_confidence_routes_to_hitl_review(ocr_engine, aptc_036_bytes):
    """Verifies that an OCR scan with low average confidence (< 75%) strictly routes to HITL."""
    mock_data = {
        "text": ["Tax", "Invoice", "POS-26-112", "Rs", "23010"],
        "conf": ["50", "45", "60", "30", "55"],
        "left": [10, 20, 30, 40, 50],
        "top": [10, 10, 10, 20, 20],
        "width": [30, 35, 45, 15, 40],
        "height": [12, 12, 12, 12, 12],
    }
    with mock.patch("pytesseract.image_to_data", return_value=mock_data):
        res = ocr_engine.process_pdf_bytes(aptc_036_bytes, filename="36_invoice_POS_26_112.pdf", document_id="APTC-036")
        assert res.ocr_available is True
        assert res.mean_confidence < 75.0
        assert res.status == "LOW_CONFIDENCE_SCAN"
        assert res.routing_recommendation == "FLAGGED_HITL_REVIEW"
        assert any("below acceptable threshold" in r for r in res.reasons)


def test_05_ocr_high_confidence_retains_provenance_and_coordinates(ocr_engine, aptc_036_bytes):
    """Verifies that high-confidence OCR retains word bounding boxes and page provenance."""
    mock_data = {
        "text": ["Tax", "Invoice", "POS-26-112", "Amount", "23010.00"],
        "conf": ["92", "95", "96", "89", "94"],
        "left": [100, 150, 220, 100, 200],
        "top": [50, 50, 50, 100, 100],
        "width": [40, 60, 90, 80, 85],
        "height": [20, 20, 20, 20, 20],
    }
    with mock.patch("pytesseract.image_to_data", return_value=mock_data):
        res = ocr_engine.process_pdf_bytes(aptc_036_bytes, filename="36_invoice_POS_26_112.pdf", document_id="APTC-036")
        assert res.ocr_available is True
        assert res.mean_confidence >= 75.0
        assert res.status == "SUCCESS"
        assert res.routing_recommendation == "OCR_PARSING_CANDIDATE"
        assert len(res.pages[0].words) == 5
        w0 = res.pages[0].words[0]
        assert w0.text == "Tax"
        assert w0.confidence == 92.0
        assert w0.bbox == (100, 50, 40, 20)
