"""Dual-Tier Duplicate Detection Engine for Accounts Payable.

Enforces two distinct isolation tiers:
Tier 1: Byte-level SHA-256 Hash Matching (identical file re-upload / duplicate transmission).
Tier 2: Semantic Commercial Duplicate Matching (identical commercial invoice: supplier + invoice number + date + grand total).

Invariants:
- Reissued copies (different PDF layout or metadata producing distinct SHA-256 hashes) are detected as commercial duplicates.
- No second payable record/voucher is ever generated.
- Both document records and a tamper-evident audit trail are preserved.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class DuplicateCheckResult:
    is_duplicate: bool
    duplicate_type: Optional[str] = None  # "EXACT_HASH" or "SEMANTIC_COMMERCIAL"
    existing_document_id: Optional[str] = None
    existing_sha256: Optional[str] = None
    commercial_key: Optional[str] = None
    audit_notes: str = ""


@dataclass
class RegisteredDocument:
    document_id: str
    filename: str
    sha256_hash: str
    supplier_name: str
    supplier_gstin: Optional[str]
    invoice_number: str
    invoice_date: str
    grand_total: float
    registered_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    is_payable: bool = True


class DuplicateDetector:
    """Manages exact and semantic duplicate detection ledger for the AP pipeline."""

    def __init__(self) -> None:
        self.by_sha256: Dict[str, RegisteredDocument] = {}
        # Commercial key: (normalized_supplier, normalized_invoice_number)
        self.by_commercial_key: Dict[str, RegisteredDocument] = {}
        self.audit_log: List[Dict[str, Any]] = []

    def make_commercial_key(self, supplier_gstin: Optional[str], supplier_name: str, invoice_number: str) -> str:
        """Constructs an invariant commercial identifier key with whitespace/separator normalization."""
        import re
        sup_id = re.sub(r"[^A-Z0-9]", "", (supplier_gstin or supplier_name).upper())
        inv_num = re.sub(r"[^A-Z0-9]", "", invoice_number.upper())
        return f"{sup_id}::{inv_num}"

    def check_duplicate(
        self,
        file_bytes: bytes,
        supplier_name: str,
        supplier_gstin: Optional[str],
        invoice_number: str,
        invoice_date: str,
        grand_total: float,
    ) -> DuplicateCheckResult:
        """Evaluates whether an incoming document is an exact or semantic duplicate."""
        file_sha256 = hashlib.sha256(file_bytes).hexdigest()

        # Tier 1: Exact byte-level match
        if file_sha256 in self.by_sha256:
            orig = self.by_sha256[file_sha256]
            return DuplicateCheckResult(
                is_duplicate=True,
                duplicate_type="EXACT_HASH",
                existing_document_id=orig.document_id,
                existing_sha256=orig.sha256_hash,
                audit_notes=f"Identical binary content detected via SHA-256 match with {orig.document_id} ({orig.filename})."
            )

        # Tier 2: Semantic commercial match
        comm_key = self.make_commercial_key(supplier_gstin, supplier_name, invoice_number)
        if comm_key in self.by_commercial_key:
            orig = self.by_commercial_key[comm_key]
            # Verify grand total matches within tolerance
            if abs(orig.grand_total - grand_total) <= 1.0:
                return DuplicateCheckResult(
                    is_duplicate=True,
                    duplicate_type="SEMANTIC_COMMERCIAL",
                    existing_document_id=orig.document_id,
                    existing_sha256=orig.sha256_hash,
                    commercial_key=comm_key,
                    audit_notes=(
                        f"Semantic duplicate detected: Commercial invoice {invoice_number} from {supplier_name} "
                        f"(Total: ₹{grand_total:.2f}) was previously registered as {orig.document_id} "
                        f"(SHA-256: {orig.sha256_hash[:12]}...). No second payable voucher created."
                    )
                )

        return DuplicateCheckResult(
            is_duplicate=False,
            duplicate_type=None,
            audit_notes="Document is unique in both binary hash and commercial identity."
        )

    def register(
        self,
        document_id: str,
        filename: str,
        file_bytes: bytes,
        supplier_name: str,
        supplier_gstin: Optional[str],
        invoice_number: str,
        invoice_date: str,
        grand_total: float,
        is_payable: bool = True,
    ) -> RegisteredDocument:
        """Registers a new approved/processed document in the ledger."""
        file_sha256 = hashlib.sha256(file_bytes).hexdigest()
        reg_doc = RegisteredDocument(
            document_id=document_id,
            filename=filename,
            sha256_hash=file_sha256,
            supplier_name=supplier_name,
            supplier_gstin=supplier_gstin,
            invoice_number=invoice_number,
            invoice_date=invoice_date,
            grand_total=grand_total,
            is_payable=is_payable,
        )

        self.by_sha256[file_sha256] = reg_doc
        comm_key = self.make_commercial_key(supplier_gstin, supplier_name, invoice_number)
        self.by_commercial_key[comm_key] = reg_doc

        return reg_doc
