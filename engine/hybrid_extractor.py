"""Hybrid AP Document Intelligence Extractor (Deterministic + AWS Bedrock Mantle).

Implements the 3-tier architecture:
1. Ingestion, PDF Integrity, & Deterministic Extraction (Python).
2. Semantic Intelligence & Complex Line-Item Parsing (AWS Mantle Qwen3 235B).
3. Deterministic Evidence Grounding, GST Arithmetic, 3-Way Matching & Duplicate Detection (Python/SQL).
"""

from __future__ import annotations

import hashlib
import io
import logging
import re
import time
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

import pypdf
from engine.pdf_safety import extract_pdf_pages

from backend.core.config import settings
from engine.duplicate_detector import DuplicateCheckResult, DuplicateDetector
from engine.grounding import verify_extracted_evidence
from engine.indian_tax_rules import IndianAPRuleEngine, TaxArithmeticResult, ThreeWayMatchResult
from engine.mantle_client import BedrockMantleClient, MantleAuthError, MantleClientError
from engine.schemas import (
    CommercialDocumentType,
    ExtractedLineItem,
    FieldEvidence,
    MantleInvoiceExtraction,
)

logger = logging.getLogger("engine.hybrid")


@dataclass
class HybridProcessingResult:
    document_id: str
    filename: str
    sha256_hash: str
    document_type: str
    is_payable_invoice: bool
    supplier_name: str
    supplier_gstin: Optional[str]
    invoice_number: str
    invoice_date: str
    po_reference: Optional[str]
    currency: str
    taxable_value: float
    cgst_amount: float
    sgst_amount: float
    igst_amount: float
    total_tax_amount: float
    grand_total: float
    line_items: List[Dict[str, Any]]
    
    # Validation & Matching
    grounding_tripwire_passed: bool
    unverified_fields: List[str]
    tax_arithmetic: TaxArithmeticResult
    three_way_match: ThreeWayMatchResult
    duplicate_check: DuplicateCheckResult
    
    # Final AP Decision & Audit
    final_decision: str  # MATCH_CANDIDATE, FLAGGED_HITL_REVIEW, REJECTED
    decision_reasons: List[str]
    audit_notes: str
    
    # Telemetry & Provider Verification
    pipeline_mode: str  # "deterministic", "mantle", or "hybrid"
    inference_provider: str = "AWS Bedrock Mantle (Qwen 235B)"
    model_id: Optional[str] = "qwen.qwen3-235b-a22b-2507-v1:0"
    http_status: Optional[int] = 200
    is_live_mantle: bool = True
    extraction_status: str = "EVALUATED"  # "EVALUATED", "NOT_EVALUATED", "FAILED"
    input_tokens: int = 0
    output_tokens: int = 0
    latency_ms: float = 0.0
    estimated_cost_usd: float = 0.0
    extraction_requires_review: bool = False
    evidence: Dict[str, FieldEvidence] = field(default_factory=dict)


class HybridAPExtractor:
    """Production orchestrator combining deterministic rules and AWS Bedrock Mantle."""

    def __init__(
        self,
        mantle_client: Optional[BedrockMantleClient] = None,
        rule_engine: Optional[IndianAPRuleEngine] = None,
        duplicate_detector: Optional[DuplicateDetector] = None,
    ) -> None:
        self.mantle = mantle_client or BedrockMantleClient()
        self.rules = rule_engine or IndianAPRuleEngine()
        self.duplicate_detector = duplicate_detector or DuplicateDetector()

    def _extract_pages_text(self, pdf_bytes: bytes) -> List[Tuple[int, str]]:
        """Extracts text per page preserving page boundaries."""
        return extract_pdf_pages(pdf_bytes)

    def extract_deterministic(
        self,
        pdf_bytes: bytes,
        filename: str,
        document_id: str = "DOC",
    ) -> HybridProcessingResult:
        """Deterministic regex-based parsing without calling any LLM."""
        start_time = time.perf_counter()
        file_sha256 = hashlib.sha256(pdf_bytes).hexdigest()
        pages = self._extract_pages_text(pdf_bytes)
        full_text = "\n".join([text for _, text in pages]).strip()

        # Check for empty / scanned document
        if len(full_text) < 20:
            return HybridProcessingResult(
                document_id=document_id,
                filename=filename,
                sha256_hash=file_sha256,
                document_type="SCANNED_IMAGE",
                is_payable_invoice=False,
                supplier_name="Unknown",
                supplier_gstin=None,
                invoice_number="UNKNOWN",
                invoice_date="1970-01-01",
                po_reference=None,
                currency="INR",
                taxable_value=0.0,
                cgst_amount=0.0,
                sgst_amount=0.0,
                igst_amount=0.0,
                total_tax_amount=0.0,
                grand_total=0.0,
                line_items=[],
                grounding_tripwire_passed=False,
                unverified_fields=["scanned_document_no_text"],
                tax_arithmetic=TaxArithmeticResult(False, 0, 0, 0, 0, False, ["Degraded scan; no text found."]),
                three_way_match=ThreeWayMatchResult(False, False, False, False, False, False, match_status="NO_PO"),
                duplicate_check=DuplicateCheckResult(False),
                final_decision="FLAGGED_HITL_REVIEW",
                decision_reasons=["Degraded scanned document contains no machine-readable digital text. Requires OCR."],
                audit_notes="Ingestion routed to HITL review due to raster image content.",
                pipeline_mode="deterministic",
                inference_provider="NONE_ROUTED_HITL",
                model_id=None,
                http_status=None,
                is_live_mantle=False,
                extraction_status="NOT_EVALUATED",
                latency_ms=round((time.perf_counter() - start_time) * 1000, 2),
            )

        # Classification
        text_lower = full_text.lower()
        if "payment receipt" in text_lower or "acknowledges receipt of payment" in text_lower:
            doc_type = "PAYMENT_RECEIPT"
            is_payable = False
        elif "purchase order" in text_lower and "supplier:" not in text_lower:
            doc_type = "PURCHASE_ORDER"
            is_payable = False
        else:
            doc_type = "INVOICE"
            is_payable = True

        # Supplier Name & GSTIN
        sup_match = re.search(r"Supplier:\s*([^\n\r]+)", full_text)
        supplier_name = sup_match.group(1).strip() if sup_match else "Unknown Supplier"

        gstin_match = re.search(r"GSTIN:\s*([0-9]{2}[A-Z0-9]{13})", full_text)
        supplier_gstin = gstin_match.group(1).strip() if gstin_match else None

        # Document Number & Date
        doc_num_match = re.search(r"Document number[\s:]+([A-Z0-9\-]+)", full_text, re.IGNORECASE)
        inv_number = doc_num_match.group(1).strip() if doc_num_match else "INV-UNKNOWN"

        date_match = re.search(r"Document date[\s:]+(\d{4}-\d{2}-\d{2})", full_text, re.IGNORECASE)
        inv_date = date_match.group(1).strip() if date_match else "2026-01-01"

        # PO & GRN
        po_match = re.search(r"Purchase order[\s:]+([A-Z0-9\-]+)", full_text, re.IGNORECASE)
        po_reference = po_match.group(1).strip() if po_match else None

        # Place of supply
        pos_match = re.search(r"Place of supply:\s*([^\n\r]+)", full_text)
        place_of_supply = pos_match.group(1).strip() if pos_match else None

        # Amounts
        def _get_amount(pattern: str) -> float:
            m = re.search(pattern, full_text, re.IGNORECASE)
            return float(m.group(1).replace(",", "")) if m else 0.0

        taxable_val = _get_amount(r"Taxable value[\s:]+(?:INR|₹)?\s*([0-9,]+\.\d{2})")
        cgst = _get_amount(r"CGST[\s:]+(?:INR|₹)?\s*([0-9,]+\.\d{2})")
        sgst = _get_amount(r"SGST[\s:]+(?:INR|₹)?\s*([0-9,]+\.\d{2})")
        igst = _get_amount(r"IGST[\s:]+(?:INR|₹)?\s*([0-9,]+\.\d{2})")
        grand_total = _get_amount(r"Grand total[\s:]+(?:INR|₹)?\s*([0-9,]+\.\d{2})")
        total_tax = round(cgst + sgst + igst, 2)

        # Line item parsing (basic deterministic line parsing)
        line_items: List[Dict[str, Any]] = []
        table_match = re.search(
            r"Description\s*\n\s*Qty\s*\n\s*Unit rate\s*\n\s*GST %\s*\n\s*Taxable value\s*\n\s*([^\n]+)\s*\n\s*([0-9]+)\s*\n\s*([0-9,]+\.\d{2})\s*\n\s*([0-9]+)\s*\n\s*([0-9,]+\.\d{2})",
            full_text
        )
        if table_match:
            desc = table_match.group(1).strip()
            qty = float(table_match.group(2))
            rate = float(table_match.group(3).replace(",", ""))
            tax_rate = float(table_match.group(4))
            line_taxable = float(table_match.group(5).replace(",", ""))
            line_items.append({
                "item_description": desc,
                "quantity": qty,
                "unit_price": rate,
                "taxable_amount": line_taxable,
                "total_amount": round(line_taxable * (1 + tax_rate / 100), 2),
            })

        extraction = MantleInvoiceExtraction(
            document_type=CommercialDocumentType(doc_type),
            is_payable_invoice=is_payable,
            supplier_name=supplier_name,
            supplier_gstin=supplier_gstin,
            place_of_supply=place_of_supply,
            invoice_number=inv_number,
            invoice_date=inv_date,
            po_reference=po_reference,
            taxable_value=taxable_val,
            cgst_amount=cgst,
            sgst_amount=sgst,
            igst_amount=igst,
            total_tax_amount=total_tax,
            grand_total=grand_total,
            line_items=[
                ExtractedLineItem(
                    item_description=li["item_description"],
                    quantity=li["quantity"],
                    unit_price=li["unit_price"],
                    taxable_amount=li["taxable_amount"],
                    total_amount=li["total_amount"],
                ) for li in line_items
            ],
        )

        # Grounding & Verification
        tripwire_passed, unverified, source_evidence = verify_extracted_evidence(extraction, pages)
        tax_res = self.rules.verify_tax_arithmetic(extraction)
        match_res = self.rules.verify_three_way_match(extraction)

        # Duplicate Check
        dup_res = self.duplicate_detector.check_duplicate(
            file_bytes=pdf_bytes,
            supplier_name=supplier_name,
            supplier_gstin=supplier_gstin,
            invoice_number=inv_number,
            invoice_date=inv_date,
            grand_total=grand_total,
        )

        # Final AP Recommendation
        reasons: List[str] = []
        if not is_payable:
            decision = "REJECTED"
            reasons.append(f"Document type '{doc_type}' is not a payable invoice (acknowledges receipt/internal note).")
        elif dup_res.is_duplicate:
            decision = "FLAGGED_HITL_REVIEW"
            reasons.append(f"Duplicate detected: {dup_res.audit_notes}")
        elif not tripwire_passed:
            decision = "FLAGGED_HITL_REVIEW"
            reasons.append(f"Grounding tripwire failed for unverified fields: {unverified}")
        elif not tax_res.is_valid:
            decision = "FLAGGED_HITL_REVIEW"
            reasons.extend(tax_res.notes)
        elif match_res.match_status != "MATCH_CANDIDATE":
            decision = "FLAGGED_HITL_REVIEW"
            reasons.extend(match_res.discrepancy_reasons)
        else:
            # Per governance guardrails: MATCH_CANDIDATE is never auto-approved payment execution
            decision = "MATCH_CANDIDATE"
            reasons.append("3-Way match (PO, GRN, QC) and GST arithmetic verified.")

        latency = round((time.perf_counter() - start_time) * 1000, 2)
        return HybridProcessingResult(
            document_id=document_id,
            filename=filename,
            sha256_hash=file_sha256,
            document_type=doc_type,
            is_payable_invoice=is_payable,
            supplier_name=supplier_name,
            supplier_gstin=supplier_gstin,
            invoice_number=inv_number,
            invoice_date=inv_date,
            po_reference=po_reference,
            currency="INR",
            taxable_value=taxable_val,
            cgst_amount=cgst,
            sgst_amount=sgst,
            igst_amount=igst,
            total_tax_amount=total_tax,
            grand_total=grand_total,
            line_items=line_items,
            grounding_tripwire_passed=tripwire_passed,
            unverified_fields=unverified,
            tax_arithmetic=tax_res,
            three_way_match=match_res,
            duplicate_check=dup_res,
            final_decision=decision,
            decision_reasons=reasons,
            audit_notes="Deterministic pipeline executed.",
            pipeline_mode="deterministic",
            latency_ms=latency,
        )

    def extract_hybrid(
        self,
        pdf_bytes: bytes,
        filename: str,
        document_id: str = "DOC",
    ) -> HybridProcessingResult:
        """Runs the complete hybrid pipeline: deterministic grounding + Bedrock Mantle + rules."""
        start_time = time.perf_counter()
        file_sha256 = hashlib.sha256(pdf_bytes).hexdigest()
        pages = self._extract_pages_text(pdf_bytes)
        full_text = "\n".join([text for _, text in pages]).strip()

        # Check for empty / scanned document first
        if len(full_text) < 20:
            return HybridProcessingResult(
                document_id=document_id,
                filename=filename,
                sha256_hash=file_sha256,
                document_type="SCANNED_IMAGE",
                is_payable_invoice=False,
                supplier_name="Unknown",
                supplier_gstin=None,
                invoice_number="UNKNOWN",
                invoice_date="1970-01-01",
                po_reference=None,
                currency="INR",
                taxable_value=0.0,
                cgst_amount=0.0,
                sgst_amount=0.0,
                igst_amount=0.0,
                total_tax_amount=0.0,
                grand_total=0.0,
                line_items=[],
                grounding_tripwire_passed=False,
                unverified_fields=["scanned_document_no_text"],
                tax_arithmetic=TaxArithmeticResult(False, 0, 0, 0, 0, False, ["Degraded scan; no text found."]),
                three_way_match=ThreeWayMatchResult(False, False, False, False, False, False, match_status="NO_PO"),
                duplicate_check=DuplicateCheckResult(False),
                final_decision="FLAGGED_HITL_REVIEW",
                decision_reasons=["Degraded scanned document contains no machine-readable digital text. Requires OCR."],
                audit_notes="Ingestion routed to HITL review due to raster image content.",
                pipeline_mode="hybrid",
                inference_provider="NONE_ROUTED_HITL",
                model_id=None,
                http_status=None,
                is_live_mantle=False,
                extraction_status="NOT_EVALUATED",
                latency_ms=round((time.perf_counter() - start_time) * 1000, 2),
            )

        # Attempt Live Mantle Extraction (fails closed if Mantle error occurs)
        try:
            extraction = self.mantle.extract_document(pages, document_filename=filename)
        except (MantleAuthError, MantleClientError) as exc:
            logger.error("Mantle LLM invocation failed on %s: %s", filename, exc)
            # Invariant: Never silently fall back. Stop and report the failure.
            raise RuntimeError(f"Live Mantle inference failed on {document_id} ({filename}): {exc}") from exc

        # Run Grounding Tripwires on Mantle Extraction
        tripwire_passed, unverified, source_evidence = verify_extracted_evidence(extraction, pages)
        extraction.tripwire_passed = tripwire_passed
        extraction.unverified_fields = unverified

        # Run Deterministic GST Arithmetic & 3-Way Match
        tax_res = self.rules.verify_tax_arithmetic(extraction)
        match_res = self.rules.verify_three_way_match(extraction)

        # Run Semantic Duplicate Detection
        dup_res = self.duplicate_detector.check_duplicate(
            file_bytes=pdf_bytes,
            supplier_name=extraction.supplier_name,
            supplier_gstin=extraction.supplier_gstin,
            invoice_number=extraction.invoice_number,
            invoice_date=extraction.invoice_date,
            grand_total=extraction.grand_total,
        )

        # Indian AP Compliance Checks
        is_e_invoice = ("e invoice" in full_text.lower() or "irn" in full_text.lower()) and "IRN" in full_text
        is_rcm = "reverse charge" in full_text.lower()
        is_mixed_gst = "mixed gst" in full_text.lower()
        is_foreign = (extraction.currency != "INR") or ("$" in full_text and "usd" in full_text.lower())

        # Final AP Recommendation
        reasons: List[str] = []
        if not extraction.is_payable_invoice or extraction.document_type in (
            CommercialDocumentType.PAYMENT_RECEIPT,
            CommercialDocumentType.PURCHASE_ORDER,
            CommercialDocumentType.DELIVERY_CHALLAN,
            CommercialDocumentType.PROFORMA_INVOICE,
        ):
            decision = "REJECTED"
            reasons.append(f"Document classified as '{extraction.document_type.value}'; not a payable invoice.")
        elif dup_res.is_duplicate:
            decision = "FLAGGED_HITL_REVIEW"
            reasons.append(f"Duplicate detected: {dup_res.audit_notes}")
        elif not tripwire_passed:
            decision = "FLAGGED_HITL_REVIEW"
            reasons.append(f"Grounding tripwire failed for unverified fields: {unverified}")
        elif not tax_res.is_valid:
            decision = "FLAGGED_HITL_REVIEW"
            reasons.extend(tax_res.notes)
        elif is_e_invoice:
            decision = "FLAGGED_HITL_REVIEW"
            reasons.append("E-Invoice IRN requires GST portal validation (IRN_VALIDATION_REVIEW).")
        elif is_rcm:
            decision = "FLAGGED_HITL_REVIEW"
            reasons.append("Reverse charge claimed; requires recipient tax liability review (RCM_TAX_REVIEW).")
        elif is_mixed_gst:
            decision = "FLAGGED_HITL_REVIEW"
            reasons.append("Multiple GST rates detected; requires tax breakdown review (TAX_BREAKDOWN_REVIEW).")
        elif is_foreign:
            decision = "FLAGGED_HITL_REVIEW"
            reasons.append(f"Foreign currency invoice ({extraction.currency}); requires foreign trade review (FOREIGN_TRADE_REVIEW).")
        elif match_res.match_status != "MATCH_CANDIDATE":
            decision = "FLAGGED_HITL_REVIEW"
            reasons.extend(match_res.discrepancy_reasons)
        else:
            decision = "MATCH_CANDIDATE"
            reasons.append("3-Way match (PO, GRN, QC) and GST arithmetic verified.")

        latency = round((time.perf_counter() - start_time) * 1000, 2)
        return HybridProcessingResult(
            document_id=document_id,
            filename=filename,
            sha256_hash=file_sha256,
            document_type=extraction.document_type.value,
            is_payable_invoice=extraction.is_payable_invoice,
            supplier_name=extraction.supplier_name,
            supplier_gstin=extraction.supplier_gstin,
            invoice_number=extraction.invoice_number,
            invoice_date=extraction.invoice_date,
            po_reference=extraction.po_reference,
            currency=extraction.currency,
            taxable_value=extraction.taxable_value,
            cgst_amount=extraction.cgst_amount,
            sgst_amount=extraction.sgst_amount,
            igst_amount=extraction.igst_amount,
            total_tax_amount=extraction.total_tax_amount,
            grand_total=extraction.grand_total,
            line_items=[li.model_dump() for li in extraction.line_items],
            grounding_tripwire_passed=tripwire_passed,
            unverified_fields=unverified,
            tax_arithmetic=tax_res,
            three_way_match=match_res,
            duplicate_check=dup_res,
            final_decision=decision,
            decision_reasons=reasons,
            audit_notes="Hybrid pipeline executed with Bedrock Mantle and deterministic controls.",
            pipeline_mode="hybrid",
            inference_provider="AWS Bedrock Mantle (Qwen 235B)",
            model_id=extraction.model_id,
            http_status=extraction.http_status,
            is_live_mantle=True,
            extraction_status="EVALUATED",
            input_tokens=extraction.input_tokens,
            output_tokens=extraction.output_tokens,
            latency_ms=latency,
            estimated_cost_usd=extraction.estimated_cost_usd,
            evidence=source_evidence,
            extraction_requires_review=is_e_invoice or is_rcm or is_mixed_gst or is_foreign,
        )
