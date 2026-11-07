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
from typing import Any, AsyncGenerator, Dict, Iterator, List, Optional, Union

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

    def process_iter(
        self,
        input_data: Union[str, bytes, Dict[str, Any], Invoice],
        filename: Optional[str] = None,
    ) -> Iterator[Dict[str, Any]]:
        """Incrementally execute each stage of the genuine 5-stage pipeline, yielding events live."""
        stage_timings: List[StageTiming] = []
        pipeline_start = time.perf_counter()

        # -------------------------------------------------------------
        # Stage 1: Document Ingestion & Classification
        # -------------------------------------------------------------
        yield {
            "event": "STAGE_START",
            "stage": 1,
            "name": "1. Ingestion & Classification",
            "details": {"filename": filename or "inline_payload"},
        }
        t0 = time.perf_counter()
        doc_type, raw_text, parsed_json = self._ingest(input_data, filename)
        st1 = StageTiming(
            stage_name="1. Ingestion & Classification",
            latency_ms=round((time.perf_counter() - t0) * 1000, 2),
            status="SUCCESS",
            details={"document_type": doc_type.value, "char_count": len(raw_text or "")},
        )
        stage_timings.append(st1)
        yield {
            "event": "STAGE_COMPLETE",
            "stage": 1,
            "name": st1.stage_name,
            "status": st1.status,
            "details": st1.details,
        }

        # -------------------------------------------------------------
        # Stage 2: Structured Entity Extraction & Sanity Verification
        # -------------------------------------------------------------
        yield {
            "event": "STAGE_START",
            "stage": 2,
            "name": "2. Structured Extraction",
            "details": {"document_type": doc_type.value},
        }
        t1 = time.perf_counter()
        try:
            invoice = self._extract(doc_type, raw_text, parsed_json)
        except ValueError as exc:
            st2 = StageTiming(
                stage_name="2. Structured Extraction",
                latency_ms=round((time.perf_counter() - t1) * 1000, 2),
                status="FAILED",
                details={"error": str(exc)[:300]},
            )
            stage_timings.append(st2)
            yield {
                "event": "STAGE_COMPLETE",
                "stage": 2,
                "name": st2.stage_name,
                "status": st2.status,
                "details": st2.details,
            }
            audit = self._extraction_failure_audit(doc_type, filename, exc, stage_timings)
            self.run_history.append(audit)
            yield {
                "event": "DECISION_FINAL",
                "stage": 5,
                "decision": audit.decision.value,
                "audit": audit,
            }
            return

        st2 = StageTiming(
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
        stage_timings.append(st2)
        yield {
            "event": "STAGE_COMPLETE",
            "stage": 2,
            "name": st2.stage_name,
            "status": st2.status,
            "details": st2.details,
        }

        # -------------------------------------------------------------
        # Stage 3: ERP Cross-Reference
        # -------------------------------------------------------------
        yield {
            "event": "STAGE_START",
            "stage": 3,
            "name": "3. ERP Cross-Reference",
            "details": {"vendor_query": invoice.vendor.tax_id or invoice.vendor.name},
        }
        t2 = time.perf_counter()
        vendor = None
        if invoice.vendor.tax_id and invoice.vendor.tax_id.strip():
            vendor = self.erp.get_vendor_by_tax_id(invoice.vendor.tax_id)
        else:
            vendor = self.erp.get_vendor_by_name(invoice.vendor.name)
        po = self.erp.get_po(invoice.po_reference) if invoice.po_reference else None

        stage_3_status = "SUCCESS"
        if not vendor:
            stage_3_status = "WARNING"
        elif invoice.po_reference and not po:
            stage_3_status = "WARNING"

        st3 = StageTiming(
            stage_name="3. ERP Cross-Reference",
            latency_ms=round((time.perf_counter() - t2) * 1000, 2),
            status=stage_3_status,
            details={
                "vendor_found": vendor is not None,
                "vendor_status": vendor.status if vendor else "NOT_FOUND",
                "po_found": po is not None,
                "po_balance": po.remaining_balance if po else 0.0,
            },
        )
        stage_timings.append(st3)
        yield {
            "event": "STAGE_COMPLETE",
            "stage": 3,
            "name": st3.stage_name,
            "status": st3.status,
            "details": st3.details,
        }

        # -------------------------------------------------------------
        # Stage 4: AOP Policy Matching & Tolerance Math
        # -------------------------------------------------------------
        yield {
            "event": "STAGE_START",
            "stage": 4,
            "name": "4. AOP Policy & Tolerance Match",
            "details": {"po_reference": invoice.po_reference, "tolerance_limit": "1.5%"},
        }
        t3 = time.perf_counter()
        audit = self.rule_engine.evaluate(invoice, self.erp, stage_timings=stage_timings)
        if audit.decision == DecisionState.AUTO_APPROVED:
            stage_4_status = "SUCCESS"
        elif audit.decision == DecisionState.FLAGGED_HITL_REVIEW:
            stage_4_status = "FLAGGED"
        else:
            stage_4_status = "FAILED"

        st4 = StageTiming(
            stage_name="4. AOP Policy & Tolerance Match",
            latency_ms=round((time.perf_counter() - t3) * 1000, 2),
            status=stage_4_status,
            details={"decision": audit.decision.value, "reasons_count": len(audit.reasons)},
        )
        stage_timings.append(st4)
        yield {
            "event": "STAGE_COMPLETE",
            "stage": 4,
            "name": st4.stage_name,
            "status": st4.status,
            "details": st4.details,
        }

        # -------------------------------------------------------------
        # Stage 5: Decision State & Audit Packaging
        # -------------------------------------------------------------
        yield {
            "event": "STAGE_START",
            "stage": 5,
            "name": "5. Decision State & Audit Packaging",
            "details": {"decision": audit.decision.value},
        }
        t4 = time.perf_counter()
        if audit.decision == DecisionState.AUTO_APPROVED:
            stage_5_status = "SUCCESS"
            stage_5_details = {
                "workflow_state": "POSTED_TO_ERP",
                "voucher_id": audit.erp_voucher_id,
                "action": "AUTOMATED_PAYMENT_SCHEDULED",
            }
        elif audit.decision == DecisionState.FLAGGED_HITL_REVIEW:
            stage_5_status = "FLAGGED"
            stage_5_details = {
                "workflow_state": "HELD_FOR_HITL_REVIEW",
                "action": "ROUTED_TO_AP_LEAD",
                "reasons_count": len(audit.reasons),
            }
        else:
            stage_5_status = "FAILED"
            stage_5_details = {
                "workflow_state": "REJECTED_FENCED",
                "action": "DISBURSAL_BLOCKED",
                "reasons_count": len(audit.reasons),
            }

        st5 = StageTiming(
            stage_name="5. Decision State & Audit Packaging",
            latency_ms=round((time.perf_counter() - t4) * 1000, 2),
            status=stage_5_status,
            details=stage_5_details,
        )
        stage_timings.append(st5)
        audit.stage_timings = stage_timings
        audit.total_latency_ms = round((time.perf_counter() - pipeline_start) * 1000, 2)

        yield {
            "event": "STAGE_COMPLETE",
            "stage": 5,
            "name": st5.stage_name,
            "status": st5.status,
            "details": st5.details,
        }

        # Append to historical audit ledger
        self.run_history.append(audit)

        yield {
            "event": "DECISION_FINAL",
            "stage": 5,
            "decision": audit.decision.value,
            "audit": audit,
        }

    def process(
        self,
        input_data: Union[str, bytes, Dict[str, Any], Invoice],
        filename: Optional[str] = None,
    ) -> DecisionAudit:
        """Synchronously execute the end-to-end 5-stage pipeline."""
        final_audit: Optional[DecisionAudit] = None
        for step in self.process_iter(input_data, filename):
            if step["event"] == "DECISION_FINAL":
                final_audit = step["audit"]
        if final_audit is None:
            raise RuntimeError("Pipeline failed to generate final DecisionAudit")
        return final_audit

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

            clean_text = extracted_text.strip()
            if len(clean_text) < 50:
                # Scanned raster image or low-density text -> run local OCR Engine
                try:
                    from engine.ocr_engine import OCREngine
                    ocr_res = OCREngine().process_pdf_bytes(file_bytes, filename=filename or "invoice.pdf")
                    if ocr_res.full_text and len(ocr_res.full_text.strip()) >= 20:
                        return DocumentType.SCANNED_IMAGE, ocr_res.full_text, None
                except Exception:
                    pass
                return DocumentType.SCANNED_IMAGE, clean_text, None
            return DocumentType.DIGITAL_PDF, clean_text, None
        except Exception:
            try:
                from engine.ocr_engine import OCREngine
                ocr_res = OCREngine().process_pdf_bytes(file_bytes, filename=filename or "invoice.pdf")
                if ocr_res.full_text and len(ocr_res.full_text.strip()) >= 20:
                    return DocumentType.SCANNED_IMAGE, ocr_res.full_text, None
            except Exception:
                pass
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
        inv_match = re.search(
            r"\bInvoice[ \t]*(?:#|Number\b|No\b|No\.\B|Num\b|Num\.\B|ID\b|Id\b|:)[ \t:#]*(?!Invoice\b|Date\b|Due\b|Notes?\b|Total\b|Summary\b|Subtotal\b|Details?\b|To\b|From\b|Amount\b)([A-Z0-9][A-Z0-9\-_]*)\b",
            text,
            re.IGNORECASE,
        )
        invoice_number = inv_match.group(1) if inv_match else None

        # Extract PO Reference
        po_match = re.search(
            r"\b(?:PO\b|Purchase\s+Order\b)[ \t]*(?:#|Number\b|No\b|No\.\B|Num\b|Num\.\B|Ref\b|Ref\.\B|Reference\b|:)[ \t:#]*(?!Box\b|Date\b|Due\b|Notes?\b|Total\b|Summary\b|Details?\b)([A-Z0-9][A-Z0-9\-_]*)\b",
            text,
            re.IGNORECASE,
        )
        po_reference = po_match.group(1) if po_match else None

        # Extract Date
        date_match = re.search(r"\bDate[:\s]*(\d{4}-\d{2}-\d{2})\b", text, re.IGNORECASE)
        inv_date = None
        if date_match:
            try:
                inv_date = datetime.strptime(date_match.group(1), "%Y-%m-%d").date()
            except ValueError:
                inv_date = None

        # Extract Vendor Name
        vendor_name = "Unknown Vendor"
        for l in lines[:5]:
            if "invoice" not in l.lower() and "date" not in l.lower() and len(l) > 3:
                vendor_name = l
                break

        # Extract Tax ID & Bank Remittance Details
        tax_id_match = re.search(r"Tax\s*ID[:\s]*([A-Z0-9\-_]+)", text, re.IGNORECASE)
        tax_id = tax_id_match.group(1) if tax_id_match else None

        bank_match = re.search(r"(?:Bank\s*Account|Account\s*#|Remit\s*Account)[:\s]*([A-Z0-9\-]+)", text, re.IGNORECASE)
        bank_account = bank_match.group(1) if bank_match else None

        # Extract labeled amounts (Subtotal / Tax / Grand Total) and the line-item table
        amounts = self._parse_labeled_amounts(lines)
        subtotal_val = next(
            (
                amounts[k]
                for k in ("subtotal", "sub-total", "sub total", "taxable amount", "net amount")
                if k in amounts
            ),
            None,
        )
        tax_val = next(
            (
                amounts[k]
                for k in ("tax", "sales tax", "vat", "gst", "cgst", "sgst", "igst", "tax amount", "taxes")
                if k in amounts
            ),
            0.0,
        )
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
            vendor=VendorInfo(name=vendor_name, tax_id=tax_id, bank_account_number=bank_account),
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
        stage_timings.append(
            StageTiming(
                stage_name="5. Decision State & Audit Packaging",
                latency_ms=0.0,
                status="FAILED",
                details={"workflow_state": "EXTRACTION_HALTED", "action": "ROUTED_TO_AP_LEAD"},
            )
        )
        return DecisionAudit(
            run_id=f"RUN-{uuid.uuid4().hex[:8].upper()}",
            invoice_number=None,
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
