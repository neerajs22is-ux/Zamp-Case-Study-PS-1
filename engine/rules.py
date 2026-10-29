"""Agent Operating Procedure (AOP) Policy and Rules Engine for Zamp PS-1.

Implements deterministic financial matching logic, tolerance thresholds,
duplicate detection, and automated human-in-the-loop exception packaging.
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import date
from typing import Any, Dict, List, Optional, Tuple

from engine.mock_erp import MockERPDatabase
from engine.models import (
    DecisionAudit,
    DecisionState,
    DocumentType,
    HistoricalInvoiceRecord,
    Invoice,
    LineMatchResult,
    LineMatchStatus,
    PurchaseOrder,
    VendorRecord,
)


class AOPPolicyConfig:
    """Enterprise policy thresholds defined in the Agent Operating Procedure (AOP).

    Can be maintained or re-configured by non-technical Controllers/AP Managers
    without modifying underlying application code.
    """

    def __init__(
        self,
        unit_price_variance_pct_threshold: float = 1.5,
        unit_price_variance_amount_threshold: float = 20.00,
        tax_rounding_tolerance_threshold: float = 5.00,
        low_confidence_threshold: float = 0.75,
        # Amount-only duplicate matches require the same invoice date (0-day window):
        # recurring invoices from one vendor legitimately share amounts.
        duplicate_window_days: int = 0,
    ) -> None:
        self.unit_price_variance_pct_threshold = unit_price_variance_pct_threshold
        self.unit_price_variance_amount_threshold = unit_price_variance_amount_threshold
        self.tax_rounding_tolerance_threshold = tax_rounding_tolerance_threshold
        self.low_confidence_threshold = low_confidence_threshold
        self.duplicate_window_days = duplicate_window_days


class AOPRuleEngine:
    """Evaluates an extracted Invoice against ERP systems of record and AOP policies."""

    def __init__(self, config: Optional[AOPPolicyConfig] = None) -> None:
        self.config = config or AOPPolicyConfig()

    def evaluate(
        self,
        invoice: Invoice,
        erp: MockERPDatabase,
        stage_timings: Optional[List[Any]] = None,
    ) -> DecisionAudit:
        """Execute the Plan-Execute-Validate evaluation loop against the invoice."""
        run_id = f"RUN-{uuid.uuid4().hex[:8].upper()}"
        reasons: List[str] = []
        discrepancies: Dict[str, Any] = {}
        line_results: List[LineMatchResult] = []
        overall_confidence = invoice.confidence_scores.get("overall", 1.0)
        po_reference = invoice.po_reference

        # -------------------------------------------------------------
        # Gate 1: Extraction Confidence & Document Integrity Check
        # -------------------------------------------------------------
        if overall_confidence < self.config.low_confidence_threshold:
            reasons.append(
                f"Low extraction confidence score ({overall_confidence:.1%}) below policy threshold "
                f"({self.config.low_confidence_threshold:.1%}). Scanned document requires human review."
            )
            discrepancies["low_confidence"] = {
                "score": overall_confidence,
                "threshold": self.config.low_confidence_threshold,
                "document_type": invoice.document_type.value,
            }

        # -------------------------------------------------------------
        # Gate 2: Vendor Verification
        # -------------------------------------------------------------
        vendor: Optional[VendorRecord] = None
        if invoice.vendor.tax_id:
            vendor = erp.get_vendor_by_tax_id(invoice.vendor.tax_id)
        if not vendor:
            vendor = erp.get_vendor_by_name(invoice.vendor.name)

        if not vendor:
            reasons.append(
                f"Unapproved or unknown vendor: '{invoice.vendor.name}' (Tax ID: {invoice.vendor.tax_id or 'N/A'}). "
                "Vendor record does not exist in ERP Vendor Master."
            )
            discrepancies["vendor_unapproved"] = invoice.vendor.name
            return self._build_audit(
                run_id=run_id,
                invoice=invoice,
                decision=DecisionState.REJECTED,
                overall_confidence=overall_confidence,
                reasons=reasons,
                discrepancies=discrepancies,
                line_results=line_results,
                stage_timings=stage_timings or [],
            )

        if vendor.status == "SUSPENDED":
            reasons.append(
                f"Compliance Hold: Vendor '{vendor.name}' (ID: {vendor.vendor_id}) is currently SUSPENDED "
                "in ERP Master. Payments are blocked."
            )
            discrepancies["vendor_suspended"] = vendor.vendor_id
            return self._build_audit(
                run_id=run_id,
                invoice=invoice,
                decision=DecisionState.REJECTED,
                overall_confidence=overall_confidence,
                reasons=reasons,
                discrepancies=discrepancies,
                line_results=line_results,
                stage_timings=stage_timings or [],
            )

        # -------------------------------------------------------------
        # Gate 3: Duplicate Submission Check
        # -------------------------------------------------------------
        invoice_hash = hashlib.sha256(
            f"{vendor.vendor_id}:{invoice.invoice_number}:{invoice.total_amount:.2f}".encode("utf-8")
        ).hexdigest()

        is_dup, dup_record = erp.check_duplicate(
            vendor_id=vendor.vendor_id,
            invoice_number=invoice.invoice_number,
            amount=invoice.total_amount,
            sha256_hash=invoice_hash,
            invoice_date=invoice.invoice_date,
            window_days=self.config.duplicate_window_days,
        )

        if is_dup and dup_record:
            reasons.append(
                f"Duplicate submission detected. Invoice #{invoice.invoice_number} from '{vendor.name}' "
                f"for ${invoice.total_amount:,.2f} was previously processed on {dup_record.processed_date} "
                f"(Batch: {dup_record.batch_id}, Ref: {dup_record.invoice_id}). Auto-rejected to prevent double payment."
            )
            discrepancies["duplicate"] = {
                "prior_invoice_id": dup_record.invoice_id,
                "prior_processed_date": str(dup_record.processed_date),
                "prior_batch_id": dup_record.batch_id,
            }
            return self._build_audit(
                run_id=run_id,
                invoice=invoice,
                decision=DecisionState.REJECTED,
                overall_confidence=overall_confidence,
                reasons=reasons,
                discrepancies=discrepancies,
                line_results=line_results,
                stage_timings=stage_timings or [],
            )

        # -------------------------------------------------------------
        # Gate 4: PO Lookup & Split-PO Budget Allocation Check
        # -------------------------------------------------------------
        po: Optional[PurchaseOrder] = None
        if po_reference:
            po = erp.get_po(po_reference)

        if not po and not po_reference:
            # Check if there is an unambiguous open PO for this vendor
            open_pos = erp.find_open_pos_for_vendor(vendor.vendor_id)
            if len(open_pos) == 1:
                po = open_pos[0]
                po_reference = po.po_number
                reasons.append(
                    f"PO reference was omitted on invoice, but automatically inferred unique active PO #{po.po_number} "
                    f"for vendor '{vendor.name}'."
                )
            else:
                reasons.append(
                    f"Missing Purchase Order reference. Vendor '{vendor.name}' has {len(open_pos)} active POs. "
                    "Cannot assign payment without explicit PO authorization."
                )
                discrepancies["missing_po"] = True

        elif not po and po_reference:
            reasons.append(
                f"Invalid Purchase Order reference: '{po_reference}' does not exist in ERP."
            )
            discrepancies["invalid_po"] = po_reference

        # If PO is verified, check cumulative budget allocation (Split PO over-billing)
        if po:
            if invoice.total_amount > po.remaining_balance:
                overrun = round(invoice.total_amount - po.remaining_balance, 2)
                cumulative_total = round(po.invoiced_amount + invoice.total_amount, 2)
                reasons.append(
                    f"PO Budget Overrun on #{po.po_number}: Billed amount (${invoice.total_amount:,.2f}) "
                    f"exceeds remaining balance (${po.remaining_balance:,.2f}) by ${overrun:,.2f}. "
                    f"(Total cumulative billing would be ${cumulative_total:,.2f} vs authorized cap of ${po.authorized_amount:,.2f})."
                )
                discrepancies["split_po_overrun"] = {
                    "po_number": po.po_number,
                    "authorized_amount": po.authorized_amount,
                    "previously_invoiced": po.invoiced_amount,
                    "remaining_balance": po.remaining_balance,
                    "invoice_amount": invoice.total_amount,
                    "deficit": overrun,
                }

        # -------------------------------------------------------------
        # Gate 5: Line-Item 2-Way Matching & Tolerance Analysis
        # -------------------------------------------------------------
        if po and not invoice.line_items:
            reasons.append(
                f"Invoice #{invoice.invoice_number} carries no line-item detail, so the billed amount cannot be "
                f"verified against PO #{po.po_number} lines. Routed for human verification."
            )
            discrepancies["missing_line_items"] = {
                "po_number": po.po_number,
                "invoice_total": invoice.total_amount,
            }

        if po and invoice.line_items:
            has_price_variance = False
            has_qty_exceeded = False

            for inv_line in invoice.line_items:
                matched_po_line = self._find_matching_po_line(inv_line.description, po.line_items)

                if not matched_po_line:
                    line_results.append(
                        LineMatchResult(
                            line_number=inv_line.line_number,
                            matched_po_line=None,
                            description=inv_line.description,
                            billed_quantity=inv_line.quantity,
                            po_quantity=None,
                            billed_unit_price=inv_line.unit_price,
                            contracted_unit_price=None,
                            price_variance_pct=0.0,
                            price_variance_amount=0.0,
                            status=LineMatchStatus.UNMATCHED,
                            notes="No matching line item found on PO.",
                        )
                    )
                    reasons.append(
                        f"Line {inv_line.line_number} ('{inv_line.description}') does not match any approved line item on PO #{po.po_number}."
                    )
                    discrepancies["unmatched_line"] = inv_line.line_number
                    continue

                # Check quantity
                qty_diff = round(inv_line.quantity - matched_po_line.remaining_quantity, 2)
                if qty_diff > 0:
                    has_qty_exceeded = True
                    notes = f"Quantity ({inv_line.quantity}) exceeds PO remaining quantity ({matched_po_line.remaining_quantity})."
                    line_status = LineMatchStatus.QTY_EXCEEDED
                    reasons.append(f"Line {inv_line.line_number}: {notes}")
                    discrepancies.setdefault("qty_exceeded", []).append(
                        {
                            "line_number": inv_line.line_number,
                            "billed_quantity": inv_line.quantity,
                            "remaining_quantity": matched_po_line.remaining_quantity,
                        }
                    )
                else:
                    line_status = LineMatchStatus.MATCHED
                    notes = "Matched authorized line."

                # Check unit price variance
                contracted_price = matched_po_line.contracted_unit_price
                price_diff = round(inv_line.unit_price - contracted_price, 2)
                price_variance_pct = round((price_diff / contracted_price) * 100, 2) if contracted_price > 0 else 0.0

                if price_diff > 0:
                    # Policy tolerance: variance is absorbed only while inside BOTH limits
                    exceeds_pct = price_variance_pct > self.config.unit_price_variance_pct_threshold
                    exceeds_amt = price_diff > self.config.unit_price_variance_amount_threshold

                    if exceeds_pct or exceeds_amt:
                        has_price_variance = True
                        line_status = LineMatchStatus.PRICE_VARIANCE
                        notes = (
                            f"Price spike: Billed unit price ${inv_line.unit_price:,.2f} exceeds contracted rate "
                            f"${contracted_price:,.2f} by +{price_variance_pct}% (+${price_diff:,.2f}/unit), "
                            f"exceeding policy tolerance (allowed: ≤{self.config.unit_price_variance_pct_threshold}% "
                            f"and ≤${self.config.unit_price_variance_amount_threshold:,.2f} per unit)."
                        )
                        reasons.append(f"Line {inv_line.line_number}: {notes}")
                        discrepancies["price_variance"] = {
                            "line_number": inv_line.line_number,
                            "billed_unit_price": inv_line.unit_price,
                            "contracted_unit_price": contracted_price,
                            "variance_pct": price_variance_pct,
                            "variance_amount_per_unit": price_diff,
                        }
                    else:
                        notes += (
                            f" (Minor price variance of +{price_variance_pct}% absorbed within AOP tolerance limit)."
                        )

                line_results.append(
                    LineMatchResult(
                        line_number=inv_line.line_number,
                        matched_po_line=matched_po_line.line_number,
                        description=inv_line.description,
                        billed_quantity=inv_line.quantity,
                        po_quantity=matched_po_line.authorized_quantity,
                        billed_unit_price=inv_line.unit_price,
                        contracted_unit_price=contracted_price,
                        price_variance_pct=price_variance_pct,
                        price_variance_amount=price_diff,
                        status=line_status,
                        notes=notes,
                    )
                )

        # -------------------------------------------------------------
        # Decision Synthesis
        # -------------------------------------------------------------
        if not discrepancies:
            decision = DecisionState.AUTO_APPROVED
            voucher_id = f"VCHR-{uuid.uuid4().hex[:6].upper()}"
            reasons.append(
                f"All AOP checks passed. Vendor '{vendor.name}' verified active. "
                f"Line items and total (${invoice.total_amount:,.2f}) matched PO #{po.po_number if po else 'N/A'} "
                f"within allowable variance. Generated ERP Voucher #{voucher_id} for automated payment."
            )
            # Record drawdown in mock ERP and append to the historical ledger
            if po:
                for result in line_results:
                    if result.matched_po_line is not None:
                        erp.record_po_line_usage(
                            po.po_number,
                            result.matched_po_line,
                            result.billed_quantity,
                            round(result.billed_quantity * result.billed_unit_price, 2),
                        )
                erp.record_po_drawdown(po.po_number, invoice.total_amount)
            erp.record_processed_invoice(
                HistoricalInvoiceRecord(
                    invoice_id=f"PROC-{uuid.uuid4().hex[:8].upper()}",
                    vendor_id=vendor.vendor_id,
                    invoice_number=invoice.invoice_number,
                    amount=invoice.total_amount,
                    processed_date=date.today(),
                    sha256_hash=invoice_hash,
                    batch_id=f"BATCH-{date.today().isoformat()}",
                    status=DecisionState.AUTO_APPROVED,
                )
            )
        else:
            decision = DecisionState.FLAGGED_HITL_REVIEW
            voucher_id = None

        return self._build_audit(
            run_id=run_id,
            invoice=invoice,
            decision=decision,
            overall_confidence=overall_confidence,
            reasons=reasons,
            discrepancies=discrepancies,
            line_results=line_results,
            stage_timings=stage_timings or [],
            voucher_id=voucher_id,
            vendor=vendor,
            po=po,
        )

    def _find_matching_po_line(self, description: str, po_lines: List[Any]) -> Optional[Any]:
        """Match invoice line item to PO line item using token containment."""
        clean_desc = description.strip().lower()
        for po_line in po_lines:
            po_desc = po_line.description.strip().lower()
            po_code = po_line.item_code.strip().lower()
            if po_desc in clean_desc or clean_desc in po_desc or po_code in clean_desc:
                return po_line
            # Token overlap check
            desc_tokens = set(clean_desc.split())
            po_tokens = set(po_desc.split())
            overlap = desc_tokens.intersection(po_tokens)
            if len(overlap) >= 2:
                return po_line
        # Fallback to single line PO if available
        if len(po_lines) == 1:
            return po_lines[0]
        return None

    def _build_audit(
        self,
        run_id: str,
        invoice: Invoice,
        decision: DecisionState,
        overall_confidence: float,
        reasons: List[str],
        discrepancies: Dict[str, Any],
        line_results: List[LineMatchResult],
        stage_timings: List[Any],
        voucher_id: Optional[str] = None,
        vendor: Optional[VendorRecord] = None,
        po: Optional[PurchaseOrder] = None,
    ) -> DecisionAudit:
        """Construct the immutable decision audit record."""
        email_draft: Optional[str] = None
        if decision in (DecisionState.FLAGGED_HITL_REVIEW, DecisionState.REJECTED):
            email_draft = self._generate_vendor_email(
                invoice=invoice,
                vendor=vendor,
                decision=decision,
                reasons=reasons,
                discrepancies=discrepancies,
                po=po,
            )

        return DecisionAudit(
            run_id=run_id,
            invoice_number=invoice.invoice_number,
            vendor_name=invoice.vendor.name,
            po_number=invoice.po_reference or (po.po_number if po else None),
            decision=decision,
            overall_confidence=overall_confidence,
            reasons=reasons,
            discrepancy_details=discrepancies,
            line_match_results=line_results,
            vendor_email_draft=email_draft,
            erp_voucher_id=voucher_id,
            stage_timings=stage_timings,
            total_latency_ms=sum(getattr(t, "latency_ms", 0.0) for t in stage_timings),
        )

    def _generate_vendor_email(
        self,
        invoice: Invoice,
        vendor: Optional[VendorRecord],
        decision: DecisionState,
        reasons: List[str],
        discrepancies: Dict[str, Any],
        po: Optional[PurchaseOrder],
    ) -> str:
        """Auto-draft professional enterprise email for human approver to send with 1 click."""
        recipient = vendor.contact_email if vendor else (invoice.vendor.contact_email or "accounts@vendor.com")
        vendor_name = vendor.name if vendor else invoice.vendor.name

        if decision == DecisionState.REJECTED:
            subject = f"REJECTED: Invoice #{invoice.invoice_number} from {vendor_name}"
            greeting = f"Dear Accounts Receivable Team at {vendor_name},"
            action_line = "Please review the issues noted below and submit a corrected invoice for re-processing."
        else:
            subject = f"Action Required: Clarification for Invoice #{invoice.invoice_number} ({vendor_name})"
            greeting = f"Dear {vendor_name} Finance Team,"
            action_line = "Your invoice is currently on hold pending confirmation of the following item(s):"

        bullet_points = "\n".join(f"  • {r}" for r in reasons)

        return f"""To: {recipient}
Subject: {subject}

{greeting}

We are processing Invoice #{invoice.invoice_number} (dated {invoice.invoice_date}) in the amount of ${invoice.total_amount:,.2f} submitted to our Accounts Payable department.

{action_line}

{bullet_points}

To expedite approval and release of payment:
  1. Reply to this email with reference to PO #{po.po_number if po else 'N/A'}.
  2. If a rate addendum or contract revision applies, please attach the authorized documentation.
  3. For technical questions, reach our AP desk at accounts-payable@company.com.

Sincerely,
Accounts Payable Automation Desk
Founder's Office Operations
"""
