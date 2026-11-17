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


def labeled_invoice_number(pages_text: List[Tuple[int, str]]) -> Optional[str]:
    """Return a unique explicitly labelled source identifier, never a fuzzy match."""
    pattern = re.compile(r'^\s*invoice\s+(?:number|no\.?)\s*:\s*([A-Za-z0-9][A-Za-z0-9/\-]{2,127})\s*$', re.I)
    values = {match.group(1).upper() for _, text in pages_text for line in text.splitlines()
              if (match := pattern.fullmatch(line))}
    return next(iter(values)) if len(values) == 1 else None


def verify_extracted_evidence(
    extraction: MantleInvoiceExtraction,
    pages_text: List[Tuple[int, str]],
) -> Tuple[bool, List[str], Dict[str, FieldEvidence]]:
    """Verify source occurrence, never model self-attestation or a guessed page.

    Occurrence is necessary evidence, not proof of semantic correctness. Ambiguous
    layouts and unsupported formats fail to human review rather than inventing data.
    """
    from decimal import Decimal, InvalidOperation
    unverified: List[str] = list(extraction.missing_fields)
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
            if name not in unverified:
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

    # A number elsewhere on the page (for example, a previous invoice's total)
    # is not evidence for the current invoice total. Accept an unambiguous
    # labelled amount only; unfamiliar layouts deliberately go to review.
    amount = r'[+-]?\d+(?:,\d{3})*(?:\.\d+)?'
    label = r'(?<![\w])(?:grand\s+total|invoice\s+total|amount\s+due|total\s+due|total)(?![\w])'
    pattern = re.compile(label + r'[ \t:=-]*(?:(?:INR|Rs\.?|₹)[ \t]*)?(' + amount + r')(?![\w.,])', re.I)
    candidates = []
    for page, text in pages_text:
        lines = text.splitlines()
        for index, line in enumerate(lines):
            # Some PDF extractors put a labelled amount on the following line.
            joined = line
            if index + 1 < len(lines) and re.fullmatch(r'\s*(?:(?:INR|Rs\.?|₹)\s*)?' + amount + r'\s*', lines[index + 1], re.I):
                joined += ' ' + lines[index + 1].strip()
            for match in pattern.finditer(joined):
                prefix = joined[:match.start()].lower()
                # A bare "total" embedded in a line may be a line-item total.
                if re.match(r'total\b', match.group(), re.I) and prefix.strip():
                    continue
                if re.search(r'\b(?:previous|prior|earlier|last|old|sub|tax|line|paid)(?:\s+invoice)?\s*[:#-]?\s*$', prefix):
                    continue
                if not prefix.strip() and index and re.search(r'\b(?:previous|prior|earlier|last|old)\s+invoice\b', lines[index - 1], re.I):
                    continue
                try:
                    candidates.append((Decimal(match.group(1).replace(',', '')), page, match.group()))
                except InvalidOperation:
                    continue
    try:
        requested_total = Decimal(str(extraction.grand_total))
        unique_totals = {candidate[0] for candidate in candidates}
        found_total = next((candidate for candidate in candidates if candidate[0] == requested_total), None) if unique_totals == {requested_total} else None
    except InvalidOperation:
        found_total = None
    if not found_total:
        unverified.append('grand_total')
    evidence['grand_total'] = FieldEvidence(field_name='grand_total', extracted_value=str(extraction.grand_total or ''),
        page_number=found_total[1] if found_total else 1,
        raw_snippet=found_total[2] if found_total else None, is_verified=bool(found_total))
    if not extraction.line_items:
        unverified.append('line_items')
    for idx, line in enumerate(extraction.line_items):
        locate(f'line_items.{idx}.item_description', line.item_description)
        for name in ('quantity', 'unit_price', 'taxable_amount', 'total_amount'):
            locate(f'line_items.{idx}.{name}', getattr(line, name), numeric=True)
    return not unverified, unverified, evidence
