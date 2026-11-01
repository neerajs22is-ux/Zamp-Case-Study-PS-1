"""Evidence Grounding, Untrusted Data Fencing, and Tripwires for AP Document Intelligence.

Adapted from RAG-4i grounding principles:
1. Treat all PDF text streams as untrusted third-party inputs.
2. Explicitly fence all document evidence in LLM prompts.
3. Enforce deterministic tripwires: every extracted scalar must be verifiable
   against the raw source text without relying on model self-attestation.
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional, Tuple
from engine.schemas import FieldEvidence, MantleInvoiceExtraction


def fence_document_pages(pages_text: List[Tuple[int, str]]) -> str:
    """Fences extracted PDF page text inside structured, untrusted delimiters."""
    fenced_blocks: List[str] = []
    for page_num, text in pages_text:
        clean_text = text.strip()
        fenced_blocks.append(
            f"--- BEGIN UNTRUSTED DOCUMENT EVIDENCE (PAGE {page_num}) ---\n"
            f"{clean_text}\n"
            f"--- END UNTRUSTED DOCUMENT EVIDENCE (PAGE {page_num}) ---"
        )
    return "\n\n".join(fenced_blocks)


def normalize_numeric_string(s: str) -> str:
    """Strip currency symbols, commas, and whitespace for invariant matching."""
    return re.sub(r"[^\d.]", "", s).strip()


def verify_extracted_evidence(
    extraction: MantleInvoiceExtraction,
    pages_text: List[Tuple[int, str]],
) -> Tuple[bool, List[str], Dict[str, FieldEvidence]]:
    """Runs deterministic grounding tripwires across all extracted entities.
    
    Returns:
        (all_passed, unverified_fields, updated_evidence_dict)
    """
    unverified: List[str] = []
    evidence_dict: Dict[str, FieldEvidence] = dict(extraction.evidence)

    # Combine all pages with line indexing
    full_text_lower = " ".join([text.lower() for _, text in pages_text])
    normalized_full_text = re.sub(r"[\s,₹$]+", " ", full_text_lower)

    # 1. Invoice Number Verification
    inv_num_clean = extraction.invoice_number.strip().lower()
    if inv_num_clean and inv_num_clean not in full_text_lower:
        unverified.append("invoice_number")
        if "invoice_number" in evidence_dict:
            evidence_dict["invoice_number"].is_verified = False
    else:
        if "invoice_number" not in evidence_dict:
            evidence_dict["invoice_number"] = FieldEvidence(
                field_name="invoice_number",
                extracted_value=extraction.invoice_number,
                page_number=1,
                is_verified=True
            )
        else:
            evidence_dict["invoice_number"].is_verified = True

    # 2. Supplier GSTIN Verification (if provided)
    if extraction.supplier_gstin:
        gstin_clean = extraction.supplier_gstin.strip().lower()
        if gstin_clean not in full_text_lower:
            unverified.append("supplier_gstin")
        else:
            if "supplier_gstin" in evidence_dict:
                evidence_dict["supplier_gstin"].is_verified = True

    # 3. PO Reference Verification (if provided)
    if extraction.po_reference:
        po_clean = extraction.po_reference.strip().lower()
        if po_clean not in full_text_lower:
            unverified.append("po_reference")
        else:
            if "po_reference" in evidence_dict:
                evidence_dict["po_reference"].is_verified = True

    # 4. Grand Total Verification
    # Check variations: 26,196.00, 26196.00, 26,196, 26196
    gt_val = extraction.grand_total
    gt_str_cents = f"{gt_val:,.2f}".lower()
    gt_str_nocoma = f"{gt_val:.2f}".lower()
    gt_str_int = f"{int(gt_val):,}".lower()
    gt_str_raw = str(int(gt_val))

    matched_gt = False
    for candidate in [gt_str_cents, gt_str_nocoma, gt_str_int, gt_str_raw]:
        if candidate in full_text_lower or candidate in normalized_full_text:
            matched_gt = True
            break

    if not matched_gt:
        unverified.append("grand_total")
        if "grand_total" in evidence_dict:
            evidence_dict["grand_total"].is_verified = False
    else:
        if "grand_total" not in evidence_dict:
            evidence_dict["grand_total"] = FieldEvidence(
                field_name="grand_total",
                extracted_value=str(gt_val),
                page_number=1,
                is_verified=True
            )
        else:
            evidence_dict["grand_total"].is_verified = True

    all_passed = len(unverified) == 0
    return all_passed, unverified, evidence_dict
