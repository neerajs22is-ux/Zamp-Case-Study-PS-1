"""End-to-End Orchestrator Pipeline for PS-1 Invoice Processing Digital Employee.

Executes the 5-stage Plan-Execute-Validate (PEV) loop with millisecond latency
tracking, multi-modal ingestion, and streaming event hooks for the live UI.
"""

from __future__ import annotations

import io
import json
import os
import re
import time
import uuid
from datetime import date, datetime
from typing import Any, AsyncGenerator, Dict, List, Optional, Union

from pypdf import PdfReader

from engine.mock_erp import MockERPDatabase
from engine.models import (
    DecisionAudit,
    DecisionState,
    DocumentType,
    Invoice,
    InvoiceLineItem,
    StageTiming,
    VendorInfo,
)
from engine.rules import AOPPolicyConfig, AOPRuleEngine

_MONEY_RE = re.compile(r"^\$?(?P<amount>[0-9,]+\.\d{2})$")
_QUANTITY_RE = re.compile(r"^[0-9]+(?:\.[0-9]+)?$")
_LABELED_AMOUNT_RE = re.compile(r"^(?P<label>[A-Za-z][A-Za-z ]*?):\s*\$?(?P<amount>[0-9,]+\.\d{2})$")
_LABEL_ONLY_RE = re.compile(r"^(?P<label>[A-Za-z][A-Za-z ]*?):$")
_OCR_CONFIDENCE_RE = re.compile(r"OCR\s*Confidence[:\s]*([0-9]{1,3})\s*%", re.IGNORECASE)


def _to_amount(token: str) -> float:
    return float(token.replace("$", "").replace(",", "").strip())


class InvoiceProcessingPipeline:
    """The enterprise execution engine coordinating the 5-stage processing loop."""

    def __init__(
        self,
        erp: Optional[MockERPDatabase] = None,
        policy_config: Optional[AOPPolicyConfig] = None,
    ) -> None:
        self.erp = erp or MockERPDatabase()
        self.rule_engine = AOPRuleEngine(config=policy_config)
        self.run_history: List[DecisionAudit] = []

    def process(
        self,
        input_data: Union[str, bytes, Dict[str, Any], Invoice],
        filename: Optional[str] = None,
    ) -> DecisionAudit:
        """Synchronously execute the end-to-end 5-stage pipeline."""
        stage_timings: List[StageTiming] = []
        pipeline_start = time.perf_counter()

        # -------------------------------------------------------------
        # Stage 1: Document Ingestion & Classification
        # -------------------------------------------------------------
        t0 = time.perf_counter()
        doc_type, raw_text, parsed_json = self._ingest(input_data, filename)
        stage_timings.append(
            StageTiming(
                stage_name="1. Ingestion & Classification",
                latency_ms=round((time.perf_counter() - t0) * 1000, 2),
                status="SUCCESS",
                details={"document_type": doc_type.value, "char_count": len(raw_text or "")},
            )
        )

        # -------------------------------------------------------------
        # Stage 2: Structured Entity Extraction & Sanity Verification
        # -------------------------------------------------------------
        t1 = time.perf_counter()
        try:
            invoice = self._extract(doc_type, raw_text, parsed_json)
        except ValueError as exc:
            stage_timings.append(
                StageTiming(
                    stage_name="2. Structured Extraction",
                    latency_ms=round((time.perf_counter() - t1) * 1000, 2),
                    status="FAILED",
                    details={"error": str(exc)[:300]},
                )
            )
            audit = self._extraction_failure_audit(doc_type, filename, exc, stage_timings)
            self.run_history.append(audit)
            return audit
        stage_timings.append(
            StageTiming(
                stage_name="2. Structured Extraction",
                latency_ms=round((time.perf_counter() - t1) * 1000, 2),
                status="SUCCESS",
                details={
                    "invoice_number": invoice.invoice_number,
                    "total_amount": invoice.total_amount,
                    "line_item_count": len(invoice.line_items),
                    "confidence": invoice.confidence_scores.get("overall", 1.0),
                },
            )
        )

        # -------------------------------------------------------------
        # Stage 3: ERP Cross-Reference
        # -------------------------------------------------------------
        t2 = time.perf_counter()
        vendor = None
        if invoice.vendor.tax_id:
            vendor = self.erp.get_vendor_by_tax_id(invoice.vendor.tax_id)
        if not vendor:
            vendor = self.erp.get_vendor_by_name(invoice.vendor.name)
        po = self.erp.get_po(invoice.po_reference) if invoice.po_reference else None

        stage_timings.append(
            StageTiming(
                stage_name="3. ERP Cross-Reference",
                latency_ms=round((time.perf_counter() - t2) * 1000, 2),
                status="SUCCESS",
                details={
                    "vendor_found": vendor is not None,
                    "vendor_status": vendor.status if vendor else "NOT_FOUND",
                    "po_found": po is not None,
                    "po_balance": po.remaining_balance if po else 0.0,
                },
            )
        )

        # -------------------------------------------------------------
        # Stage 4 & 5: AOP Matching, Tolerance Math & Decision Audit
        # -------------------------------------------------------------
        t3 = time.perf_counter()
        audit = self.rule_engine.evaluate(invoice, self.erp, stage_timings=stage_timings)
        stage_status = "FAILED" if audit.decision in (DecisionState.REJECTED, DecisionState.FLAGGED_HITL_REVIEW) else "SUCCESS"

        stage_timings.append(
            StageTiming(
                stage_name="4. AOP Policy & Tolerance Match",
                latency_ms=round((time.perf_counter() - t3) * 1000, 2),
                status=stage_status,
                details={"decision": audit.decision.value, "reasons_count": len(audit.reasons)},
            )
        )

        audit.stage_timings = stage_timings
        audit.total_latency_ms = round((time.perf_counter() - pipeline_start) * 1000, 2)

        # Append to historical audit ledger
        self.run_history.append(audit)
        return audit

    def _ingest(
        self,
        input_data: Union[str, bytes, Dict[str, Any], Invoice],
        filename: Optional[str] = None,
    ) -> tuple[DocumentType, Optional[str], Optional[Dict[str, Any]]]:
        """Ingest raw input and classify digital stream vs scanned image."""
        if isinstance(input_data, Invoice):
            return input_data.document_type, input_data.raw_text, input_data.model_dump()

        if isinstance(input_data, dict):
            doc_type = DocumentType(input_data.get("document_type", DocumentType.STRUCTURED_JSON.value))
            return doc_type, None, input_data

        # Check if file path
        if isinstance(input_data, str) and os.path.exists(input_data):
            with open(input_data, "rb") as f:
                file_bytes = f.read()
            filename = filename or os.path.basename(input_data)
        elif isinstance(input_data, str) and input_data.strip().startswith("{"):
            parsed = json.loads(input_data)
            return DocumentType.STRUCTURED_JSON, None, parsed
        elif isinstance(input_data, bytes):
            file_bytes = input_data
        else:
            raise ValueError("Unsupported input format for invoice ingestion")

        # Ingest PDF bytes
        try:
            reader = PdfReader(io.BytesIO(file_bytes))
            extracted_text = ""
            for page in reader.pages:
                extracted_text += (page.extract_text() or "") + "\n"

            # Check if text is dense or looks like a scanned raster
            clean_text = extracted_text.strip()
            if len(clean_text) < 50:
                return DocumentType.SCANNED_IMAGE, clean_text, None
            return DocumentType.DIGITAL_PDF, clean_text, None
        except Exception:
            # Fallback if corrupt or image
            return DocumentType.SCANNED_IMAGE, None, None

    def _extract(
        self,
        doc_type: DocumentType,
        raw_text: Optional[str],
        parsed_json: Optional[Dict[str, Any]],
    ) -> Invoice:
        """Extract typed invoice schema with fallback heuristics or JSON validation."""
        if parsed_json:
            # Direct structured JSON ingestion
            return Invoice(**parsed_json)

        # Extraction from PDF text stream using deterministic financial regex heuristics
        text = raw_text or ""
        lines = [line.strip() for line in text.split("\n") if line.strip()]
        if not lines:
            raise ValueError(
                "Document contains no machine-readable text; a clearer scan or manual entry is required."
            )

        # Extract Invoice Number
        inv_match = re.search(r"Invoice\s*(?:#|Number|No\.?)[:\s]*([A-Z0-9\-_]+)", text, re.IGNORECASE)
        invoice_number = inv_match.group(1) if inv_match else f"INV-{int(time.time())}"

        # Extract PO Reference
        po_match = re.search(r"(?:PO|Purchase Order)\s*(?:#|Number|No\.?|Ref\.?|Reference)?[:\s]*([A-Z0-9\-_]+)", text, re.IGNORECASE)
        po_reference = po_match.group(1) if po_match else None

        # Extract Date
        date_match = re.search(r"Date[:\s]*(\d{4}-\d{2}-\d{2})", text, re.IGNORECASE)
        if date_match:
            try:
                inv_date = datetime.strptime(date_match.group(1), "%Y-%m-%d").date()
            except ValueError:
                inv_date = date.today()
        else:
            inv_date = date.today()

        # Extract Vendor Name
        vendor_name = "Unknown Vendor"
        for l in lines[:5]:
            if "invoice" not in l.lower() and "date" not in l.lower() and len(l) > 3:
                vendor_name = l
                break

        # Extract labeled amounts (Subtotal / Tax / Grand Total) and the line-item table
        amounts = self._parse_labeled_amounts(lines)
        subtotal_val = amounts.get("subtotal")
        tax_val = amounts.get("tax", 0.0)
        total_val = next(
            (
                amounts[key]
                for key in ("grand total", "total amount", "amount due", "balance due", "total")
                if key in amounts
            ),
            None,
        )
        if total_val is None:
            raise ValueError("Invoice total could not be located in the document.")
        if subtotal_val is None:
            subtotal_val = round(total_val - tax_val, 2)

        line_items = self._parse_line_items(lines)

        # Check confidence
        confidence = 0.95 if doc_type == DocumentType.DIGITAL_PDF else 0.62
        ocr_match = _OCR_CONFIDENCE_RE.search(text)
        if ocr_match:
            confidence = min(confidence, int(ocr_match.group(1)) / 100)

        return Invoice(
            invoice_number=invoice_number,
            invoice_date=inv_date,
            vendor=VendorInfo(name=vendor_name),
            po_reference=po_reference,
            line_items=line_items,
            subtotal=subtotal_val,
            tax_amount=tax_val,
            total_amount=total_val,
            document_type=doc_type,
            raw_text=raw_text,
            confidence_scores={
                "overall": confidence,
                "invoice_number": 0.98 if inv_match else 0.50,
                "total_amount": 0.98 if total_val else 0.50,
                "po_reference": 0.95 if po_match else 0.20,
            },
        )

    @staticmethod
    def _parse_labeled_amounts(lines: List[str]) -> Dict[str, float]:
        """Collect 'Label: $1,234.56' pairs (subtotal, tax, grand total)."""
        amounts: Dict[str, float] = {}
        for index, line in enumerate(lines):
            match = _LABELED_AMOUNT_RE.match(line)
            if match:
                amounts[match.group("label").strip().lower()] = _to_amount(match.group("amount"))
                continue
            # ReportLab lays labels and values out on separate text lines
            label_match = _LABEL_ONLY_RE.match(line)
            if label_match and index + 1 < len(lines) and _MONEY_RE.match(lines[index + 1]):
                amounts[label_match.group("label").strip().lower()] = _to_amount(lines[index + 1])
        return amounts

    @staticmethod
    def _parse_line_items(lines: List[str]) -> List[InvoiceLineItem]:
        """Parse the invoice table: line number, description, qty, unit price, line total."""
        items: List[InvoiceLineItem] = []
        start = next((i for i, line in enumerate(lines) if line.lower() == "description"), None)
        if start is None:
            return items

        index = start + 1
        while index < len(lines) - 2:
            token = lines[index]
            if not token.isdigit():
                index += 1
                continue

            for qty_index in range(index + 1, min(index + 6, len(lines) - 2)):
                if not (
                    _QUANTITY_RE.match(lines[qty_index])
                    and _MONEY_RE.match(lines[qty_index + 1])
                    and _MONEY_RE.match(lines[qty_index + 2])
                ):
                    continue
                description = " ".join(lines[index + 1:qty_index]).strip()
                if not description:
                    break
                items.append(
                    InvoiceLineItem(
                        line_number=int(token),
                        description=description,
                        quantity=float(lines[qty_index]),
                        unit_price=_to_amount(lines[qty_index + 1]),
                        total=_to_amount(lines[qty_index + 2]),
                    )
                )
                index = qty_index + 3
                break
            else:
                index += 1
        return items

    def _extraction_failure_audit(
        self,
        doc_type: DocumentType,
        filename: Optional[str],
        error: ValueError,
        stage_timings: List[StageTiming],
    ) -> DecisionAudit:
        """Fail closed: an unreadable document goes to a human, never to an automated payment."""
        return DecisionAudit(
            run_id=f"RUN-{uuid.uuid4().hex[:8].upper()}",
            invoice_number="UNKNOWN",
            vendor_name="UNKNOWN",
            decision=DecisionState.FLAGGED_HITL_REVIEW,
            overall_confidence=0.0,
            reasons=[
                "Document could not be converted into a valid invoice record, so no automated "
                f"decision was made. {error} Routed for human review."
            ],
            discrepancy_details={
                "extraction_failed": {
                    "document_type": doc_type.value,
                    "filename": filename or "inline_payload",
                    "error": str(error)[:300],
                }
            },
            stage_timings=stage_timings,
            total_latency_ms=round(sum(t.latency_ms for t in stage_timings), 2),
        )
