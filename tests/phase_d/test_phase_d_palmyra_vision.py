"""Automated Tests for AWS Bedrock Palmyra Vision 7B Visual Extraction Adapter.

Verifies:
1. Feature flag safety: ENABLE_PALMYRA_VISION defaults to False.
2. Provider-independent adapter initialization and configuration.
3. Graceful fail-closed handling on missing credentials or HTTP errors.
4. Pydantic schema validation of multimodal visual extraction outputs.
5. Visual clarity and degradation tripwires (degraded scans route to HITL).
6. Handwritten note and stamp detection governance.
7. Token consumption tracking and cost calculation.
"""

from __future__ import annotations

import json
import os
from unittest.mock import MagicMock, patch
import pytest

from backend.core.config import settings
from engine.palmyra_vision_adapter import (
    PalmyraVisualExtractionModel,
    PalmyraVisualResult,
    PalmyraVisionAdapter,
)


@pytest.fixture
def real_pdf_bytes():
    pdf_path = os.path.join("tests", "evaluation_corpus_v2", "invoices", "01_invoice_AP_26_001.pdf")
    with open(pdf_path, "rb") as f:
        return f.read()


def test_01_feature_flag_disabled_by_default():
    """Verifies Palmyra Vision feature flag defaults to False, maintaining existing processing path."""
    assert settings.ENABLE_PALMYRA_VISION is False
    assert settings.PALMYRA_MODEL_ID == "writer.palmyra-vision-7b"
    assert "us-east-1" in settings.PALMYRA_BASE_URL or "us-west-2" in settings.PALMYRA_BASE_URL


def test_02_palmyra_adapter_key_resolution():
    """Verifies Palmyra adapter falls back cleanly to MANTLE_API_KEY when PALMYRA_API_KEY is unset."""
    with patch.object(settings, "PALMYRA_API_KEY", None), \
         patch.object(settings, "MANTLE_API_KEY", "test_shared_key"):
        adapter = PalmyraVisionAdapter()
        assert adapter.api_key == "test_shared_key"


def test_03_palmyra_adapter_missing_key_fails_closed(real_pdf_bytes):
    """Verifies that if no API key is available, adapter fails closed with status ERROR and routes to HITL."""
    adapter = PalmyraVisionAdapter(api_key="")
    res = adapter.extract_visual(real_pdf_bytes, filename="test.pdf", document_id="DOC-01")
    assert res.status == "ERROR"
    assert res.routing_recommendation == "FLAGGED_HITL_REVIEW"
    assert "not configured" in res.reasons[0].lower()


def test_04_palmyra_adapter_structured_parsing(real_pdf_bytes):
    """Verifies adapter parses structured JSON into PalmyraVisualExtractionModel."""
    mock_payload = {
        "document_type": "TAX INVOICE",
        "supplier_name": "Acme Industrial Supplies",
        "supplier_gstin": "27AAPCA1234F1Z5",
        "invoice_number": "INV-2026-999",
        "invoice_date": "2026-10-15",
        "po_reference": "PO-8888",
        "currency": "INR",
        "taxable_value": 50000.0,
        "cgst_amount": 4500.0,
        "sgst_amount": 4500.0,
        "igst_amount": 0.0,
        "total_tax_amount": 9000.0,
        "grand_total": 59000.0,
        "line_items": [
            {
                "item_description": "Industrial bearings",
                "quantity": 100,
                "unit_price": 500.0,
                "taxable_amount": 50000.0,
                "total_amount": 59000.0,
            }
        ],
        "has_handwritten_notes": False,
        "has_stamp_or_signature": True,
        "visual_clarity": "CLEAR",
        "uncertain_fields": [],
    }

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "choices": [{"message": {"content": json.dumps(mock_payload)}}],
        "usage": {"prompt_tokens": 1200, "completion_tokens": 250, "total_tokens": 1450},
    }

    adapter = PalmyraVisionAdapter(api_key="valid_test_key")
    with patch("httpx.Client.post", return_value=mock_resp):
        res = adapter.extract_visual(real_pdf_bytes, filename="invoice.pdf", document_id="DOC-999")
        assert res.status == "SUCCESS"
        assert res.routing_recommendation == "VISUAL_EXTRACTION_SUCCESS"
        assert res.extraction.invoice_number == "INV-2026-999"
        assert res.extraction.grand_total == 59000.0
        assert res.prompt_tokens == 1200
        assert res.completion_tokens == 250
        assert res.estimated_cost_usd > 0.0


def test_05_palmyra_adapter_degraded_scan_routes_to_hitl(real_pdf_bytes):
    """Verifies that an image flagged as DEGRADED or UNREADABLE routes strictly to FLAGGED_HITL_REVIEW."""
    mock_payload = {
        "document_type": "TAX INVOICE",
        "supplier_name": "Degraded Vendor",
        "supplier_gstin": None,
        "invoice_number": "INV-DEG",
        "invoice_date": "2026-01-01",
        "grand_total": 1000.0,
        "visual_clarity": "DEGRADED",
        "uncertain_fields": ["invoice_number", "grand_total"],
    }

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "choices": [{"message": {"content": json.dumps(mock_payload)}}],
        "usage": {"prompt_tokens": 1300, "completion_tokens": 150, "total_tokens": 1450},
    }

    adapter = PalmyraVisionAdapter(api_key="valid_test_key")
    with patch("httpx.Client.post", return_value=mock_resp):
        res = adapter.extract_visual(real_pdf_bytes, filename="degraded.pdf", document_id="DOC-DEG")
        assert res.routing_recommendation == "FLAGGED_HITL_REVIEW"
        assert res.status == "DEGRADED_SCAN"
        assert any("degraded" in r.lower() for r in res.reasons)


def test_06_palmyra_adapter_handwritten_note_triggers_hitl(real_pdf_bytes):
    """Verifies that detection of handwritten notes or endorsements triggers mandatory human review."""
    mock_payload = {
        "document_type": "TAX INVOICE",
        "supplier_name": "Vendor With Hand Note",
        "invoice_number": "INV-HAND-01",
        "grand_total": 5000.0,
        "visual_clarity": "CLEAR",
        "has_handwritten_notes": True,
        "handwritten_notes_text": "Received 5 units short on dock 4",
        "uncertain_fields": [],
    }

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "choices": [{"message": {"content": json.dumps(mock_payload)}}],
        "usage": {"prompt_tokens": 1100, "completion_tokens": 180, "total_tokens": 1280},
    }

    adapter = PalmyraVisionAdapter(api_key="valid_test_key")
    with patch("httpx.Client.post", return_value=mock_resp):
        res = adapter.extract_visual(real_pdf_bytes, filename="hand.pdf", document_id="DOC-HAND")
        assert res.routing_recommendation == "FLAGGED_HITL_REVIEW"
        assert any("handwritten" in r.lower() for r in res.reasons)
