"""Evidence Grounding, Untrusted Data Fencing, and Tripwires for AP Document Intelligence.

Deterministic Grounding Invariants:
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
    """Verify source occurrence, never model self-attestation or a guessed page.

    Occurrence is necessary evidence, not proof of semantic correctness. Ambiguous
    layouts and unsupported formats fail to human review rather than inventing data.
    """
    from decimal import Decimal, InvalidOperation
    unverified: List[str] = []
    evidence: Dict[str, FieldEvidence] = {}

    def locate(name, value, numeric=False, required=True):
        if not required and (value is None or value == 0):
            return
        rendered = str(value or '').strip()
        found = None
        if rendered and rendered.upper() not in ('UNKNOWN', 'INV-UNKNOWN', '1970-01-01'):
            for page, text in pages_text:
                if numeric:
                    # Keep the full signed numeric token, including all decimals.
                    # Removing punctuation from an entire page merges unrelated data.
                    for match in re.finditer(r'(?<![\w.])[+-]?\d+(?:,\d+)*(?:\.\d+)?(?![\w.])', text):
                        try:
                            if Decimal(match.group().replace(',', '')) == Decimal(rendered):
                                found = (page, match.group())
                                break
                        except InvalidOperation:
                            pass
                else:
                    match = re.search(r'(?<!\w)' + re.escape(rendered) + r'(?!\w)', text, re.IGNORECASE)
                    if match:
                        found = (page, match.group())
                if found:
                    break
        if not found:
            unverified.append(name)
        evidence[name] = FieldEvidence(field_name=name, extracted_value=rendered,
            page_number=found[0] if found else 1,
            raw_snippet=found[1] if found else None, is_verified=bool(found))

    for name in ('invoice_number', 'supplier_name', 'invoice_date'):
        locate(name, getattr(extraction, name))
    for name in ('supplier_gstin', 'po_reference', 'buyer_gstin', 'place_of_supply'):
        value = getattr(extraction, name)
        if value:
            locate(name, value)
    for name in ('taxable_value', 'cgst_amount', 'sgst_amount', 'igst_amount'):
        locate(name, getattr(extraction, name), numeric=True, required=False)

    # For total_tax_amount: verify either direct token occurrence or constituent GST breakdown grounding
    tax_val = getattr(extraction, 'total_tax_amount', None)
    if tax_val:
        locate('total_tax_amount', tax_val, numeric=True, required=False)
        if 'total_tax_amount' in unverified:
            # If the calculated tax matches verified CGST + SGST + IGST, it is mathematically grounded
            cgst_v = getattr(extraction, 'cgst_amount', None) or 0
            sgst_v = getattr(extraction, 'sgst_amount', None) or 0
            igst_v = getattr(extraction, 'igst_amount', None) or 0
            if (cgst_v or sgst_v or igst_v) and Decimal(str(tax_val)) == Decimal(str(cgst_v)) + Decimal(str(sgst_v)) + Decimal(str(igst_v)):
                if 'cgst_amount' not in unverified and 'sgst_amount' not in unverified and 'igst_amount' not in unverified:
                    unverified.remove('total_tax_amount')
                    evidence['total_tax_amount'].is_verified = True
                    evidence['total_tax_amount'].raw_snippet = f"Derived: CGST({cgst_v}) + SGST({sgst_v}) + IGST({igst_v})"

    # Grand total is always required and must match a complete numeric token.
    locate('grand_total', extraction.grand_total, numeric=True)
    if not extraction.line_items:
        unverified.append('line_items')
    for idx, line in enumerate(extraction.line_items):
        locate(f'line_items.{idx}.item_description', line.item_description)
        for name in ('quantity', 'unit_price', 'taxable_amount', 'total_amount'):
            locate(f'line_items.{idx}.{name}', getattr(line, name), numeric=True)
    return not unverified, unverified, evidence
