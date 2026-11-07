"""Agent Operating Procedure (AOP) Policy and Rules Engine for Zamp PS-1.

Implements deterministic financial matching logic, tolerance thresholds,
duplicate detection, arithmetic validation, and automated human-in-the-loop exception packaging.
"""

from __future__ import annotations

import hashlib
import re
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


def format_currency(amount: float, currency: str = "USD") -> str:
    """Format an amount with the appropriate currency symbol or prefix."""
    c = (currency or "USD").upper().strip()
    if c == "USD":
        return f"${amount:,.2f}"
    elif c == "INR":
        return f"₹{amount:,.2f}"
    elif c == "EUR":
        return f"€{amount:,.2f}"
    elif c == "GBP":
        return f"£{amount:,.2f}"
    return f"{c} {amount:,.2f}"


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
        curr = invoice.currency or "USD"

        # -------------------------------------------------------------
        # Gate 0: Deterministic Arithmetic Invariant Gate
        # -------------------------------------------------------------
        has_arithmetic_mismatch = False

        # 0a. Line math: quantity × unit_price = line_total
        if invoice.line_items:
            for item in invoice.line_items:
                calc_line_total = round(item.quantity * item.unit_price, 2)
                stated_line_total = round(item.total, 2)
                if abs(calc_line_total - stated_line_total) > 0.01:
                    has_arithmetic_mismatch = True
                    reasons.append(
                        f"Line {item.line_number} calculation mismatch: {item.quantity} × "
                        f"{format_currency(item.unit_price, curr)} = {format_currency(calc_line_total, curr)}, "
                        f"but line total is stated as {format_currency(stated_line_total, curr)}."
                    )
                    discrepancies.setdefault("line_math_mismatch", []).append({
                        "line_number": item.line_number,
                        "calculated": calc_line_total,
                        "stated": stated_line_total,
                    })

            # 0b. Subtotal: sum(line totals) == subtotal
            sum_line_totals = round(sum(item.total for item in invoice.line_items), 2)
            stated_subtotal = round(invoice.subtotal, 2)
            if abs(sum_line_totals - stated_subtotal) > 0.01:
                has_arithmetic_mismatch = True
                reasons.append(
                    f"Subtotal mismatch: Sum of line items ({format_currency(sum_line_totals, curr)}) "
                    f"does not match stated invoice subtotal ({format_currency(stated_subtotal, curr)})."
                )
                discrepancies["subtotal_mismatch"] = {
                    "sum_of_lines": sum_line_totals,
                    "stated_subtotal": stated_subtotal,
                    "difference": round(sum_line_totals - stated_subtotal, 2),
                }

        # 0c. Grand Total: subtotal + tax == total (within tax_rounding_tolerance_threshold)
        calc_grand_total = round(invoice.subtotal + invoice.tax_amount, 2)
        stated_grand_total = round(invoice.total_amount, 2)
        tax_diff = round(abs(calc_grand_total - stated_grand_total), 2)
        if tax_diff > self.config.tax_rounding_tolerance_threshold:
            has_arithmetic_mismatch = True
            reasons.append(
                f"Grand total calculation mismatch: Subtotal ({format_currency(invoice.subtotal, curr)}) + "
                f"Tax ({format_currency(invoice.tax_amount, curr)}) = {format_currency(calc_grand_total, curr)}, "
                f"which differs from stated grand total ({format_currency(stated_grand_total, curr)}) by "
                f"{format_currency(tax_diff, curr)} (exceeds policy tax rounding tolerance of {format_currency(self.config.tax_rounding_tolerance_threshold, curr)})."
            )
            discrepancies["grand_total_mismatch"] = {
                "calculated_total": calc_grand_total,
                "stated_total": stated_grand_total,
                "difference": tax_diff,
                "tolerance_threshold": self.config.tax_rounding_tolerance_threshold,
            }

        if has_arithmetic_mismatch:
            discrepancies["arithmetic_mismatch"] = True

        # -------------------------------------------------------------
        # Gate 1: Extraction Confidence & Date Integrity Check
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

        today = date.today()
        if invoice.invoice_date > today:
            reasons.append(
                f"Future-dated invoice detected: Invoice date ({invoice.invoice_date}) is in the future. "
                "Held for verification."
            )
            discrepancies["future_dated_invoice"] = str(invoice.invoice_date)
        elif (today - invoice.invoice_date).days > 365:
            reasons.append(
                f"Stale invoice detected: Invoice date ({invoice.invoice_date}) is older than 365 days. "
                "Held for accounting review."
            )
            discrepancies["stale_invoice"] = str(invoice.invoice_date)

        # -------------------------------------------------------------
        # Gate 2: Vendor Verification & Tax ID Precedence
        # -------------------------------------------------------------
        vendor: Optional[VendorRecord] = None
        tax_id_provided = bool(invoice.vendor.tax_id and invoice.vendor.tax_id.strip())

        if tax_id_provided:
            vendor = erp.get_vendor_by_tax_id(invoice.vendor.tax_id)
            if not vendor:
                # STRICT AUDIT RULE: Tax ID was provided, but is NOT found in ERP Master.
                # Never fall through to name lookup if tax ID mismatched.
                reasons.append(
                    f"Vendor Tax ID mismatch: Tax ID '{invoice.vendor.tax_id}' provided on invoice "
                    f"does not match any approved record in ERP Vendor Master for '{invoice.vendor.name}'."
                )
                discrepancies["tax_id_mismatch"] = {
                    "provided_tax_id": invoice.vendor.tax_id,
                    "vendor_name": invoice.vendor.name,
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
        else:
            # Tax ID not provided: Attempt normalized name match
            vendor = erp.get_vendor_by_name(invoice.vendor.name)
            if vendor:
                reasons.append(
                    f"Vendor matched by name '{vendor.name}' only (Tax ID omitted on invoice). "
                    "Flagged for human confirmation."
                )
                discrepancies["vendor_tax_id_omitted"] = True

        if not vendor:
            reasons.append(
                f"Unapproved or unknown vendor: '{invoice.vendor.name}' (Tax ID: {invoice.vendor.tax_id or 'N/A'}). "
                "Vendor record does not exist in ERP Vendor Master; requires supplier onboarding."
            )
            discrepancies["vendor_unapproved"] = invoice.vendor.name
            return self._build_audit(
                run_id=run_id,
                invoice=invoice,
                decision=DecisionState.FLAGGED_HITL_REVIEW,
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

        # Remittance / Bank Account Fraud Validation (Item 21)
        if invoice.vendor.bank_account_number and vendor.bank_account_number:
            inv_bank = re.sub(r"[^A-Za-z0-9]", "", invoice.vendor.bank_account_number)
            erp_bank = re.sub(r"[^A-Za-z0-9]", "", vendor.bank_account_number)
            if inv_bank != erp_bank:
                reasons.append(
                    f"Bank Account Mismatch: Remittance account '{invoice.vendor.bank_account_number}' "
                    f"does not match registered vendor bank account (ending in ...{erp_bank[-4:]}). "
                    "Payment held for fraud prevention verification."
                )
                discrepancies["bank_details_mismatch"] = {
                    "provided_account": invoice.vendor.bank_account_number,
                    "registered_account_last4": erp_bank[-4:],
                }

        # -------------------------------------------------------------
        # Gate 3: Duplicate Submission Check
        # -------------------------------------------------------------
        invoice_hash = hashlib.sha256(
            f"{vendor.vendor_id}:{invoice.invoice_number}:{invoice.total_amount:.2f}".encode("utf-8")
        ).hexdigest()

        is_dup, dup_record, dup_type = erp.check_duplicate(
            vendor_id=vendor.vendor_id,
            invoice_number=invoice.invoice_number,
            amount=invoice.total_amount,
            sha256_hash=invoice_hash,
            invoice_date=invoice.invoice_date,
            window_days=self.config.duplicate_window_days,
        )

        if is_dup and dup_record:
            if dup_type in ("EXACT_INVOICE_NUMBER", "EXACT_HASH"):
                reasons.append(
                    f"Duplicate submission detected. Invoice #{invoice.invoice_number} from '{vendor.name}' "
                    f"for {format_currency(invoice.total_amount, curr)} was previously processed on {dup_record.processed_date} "
                    f"(Batch: {dup_record.batch_id}, Ref: {dup_record.invoice_id}). Auto-rejected to prevent double payment."
                )
                discrepancies["duplicate"] = {
                    "prior_invoice_id": dup_record.invoice_id,
                    "prior_processed_date": str(dup_record.processed_date),
                    "prior_batch_id": dup_record.batch_id,
                    "duplicate_type": dup_type,
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
            else:
                # Fuzzy near-duplicate (same vendor + exact amount within window)
                reasons.append(
                    f"Possible duplicate submission detected: Invoice for {format_currency(invoice.total_amount, curr)} "
                    f"matches prior invoice #{dup_record.invoice_number} from '{vendor.name}' within duplicate window. "
                    "Held for human review."
                )
                discrepancies["possible_duplicate"] = {
                    "prior_invoice_id": dup_record.invoice_id,
                    "prior_invoice_number": dup_record.invoice_number,
                    "prior_processed_date": str(dup_record.processed_date),
                    "duplicate_type": dup_type,
                }

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
                    f"for vendor '{vendor.name}'. Flagged for human confirmation."
                )
                # Incur a discrepancy so that inferred PO invoices do NOT auto-approve silently
                discrepancies["inferred_po"] = po.po_number
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
                    f"PO Budget Overrun on #{po.po_number}: Billed amount ({format_currency(invoice.total_amount, curr)}) "
                    f"exceeds remaining balance ({format_currency(po.remaining_balance, curr)}) by {format_currency(overrun, curr)}. "
                    f"(Total cumulative billing would be {format_currency(cumulative_total, curr)} vs authorized cap of {format_currency(po.authorized_amount, curr)})."
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
            # Aggregate billed quantity per matched PO line to prevent multi-line circumvention (Item 17)
            billed_qty_by_po_line: Dict[int, float] = {}
            for inv_line in invoice.line_items:
                matched_line = self._find_matching_po_line(inv_line.description, po.line_items)
                if matched_line:
                    billed_qty_by_po_line[matched_line.line_number] = round(
                        billed_qty_by_po_line.get(matched_line.line_number, 0.0) + inv_line.quantity, 2
                    )

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

                # Check aggregated quantity against PO remaining quantity
                total_billed_qty = billed_qty_by_po_line.get(matched_po_line.line_number, inv_line.quantity)
                qty_diff = round(total_billed_qty - matched_po_line.remaining_quantity, 2)
                if qty_diff > 0:
                    notes = (
                        f"Aggregated billed quantity ({total_billed_qty}) exceeds PO remaining quantity "
                        f"({matched_po_line.remaining_quantity})."
                    )
                    line_status = LineMatchStatus.QTY_EXCEEDED
                    reasons.append(f"Line {inv_line.line_number}: {notes}")
                    discrepancies.setdefault("qty_exceeded", []).append(
                        {
                            "line_number": inv_line.line_number,
                            "billed_quantity": inv_line.quantity,
                            "total_billed_for_po_line": total_billed_qty,
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
                    exceeds_pct = price_variance_pct > self.config.unit_price_variance_pct_threshold
                    exceeds_amt = price_diff > self.config.unit_price_variance_amount_threshold

                    if exceeds_pct or exceeds_amt:
                        line_status = LineMatchStatus.PRICE_VARIANCE
                        notes = (
                            f"Price spike: Billed unit price {format_currency(inv_line.unit_price, curr)} exceeds contracted rate "
                            f"{format_currency(contracted_price, curr)} by +{price_variance_pct}% (+{format_currency(price_diff, curr)}/unit), "
                            f"exceeding policy tolerance (allowed: ≤{self.config.unit_price_variance_pct_threshold}% "
                            f"and ≤{format_currency(self.config.unit_price_variance_amount_threshold, curr)} per unit)."
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
                f"Line items and total ({format_currency(invoice.total_amount, curr)}) matched PO #{po.po_number if po else 'N/A'} "
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
                    invoice_date=invoice.invoice_date,
                    processed_date=today,
                    sha256_hash=invoice_hash,
                    batch_id=f"BATCH-{today.isoformat()}",
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
        """Match invoice line item to PO line item using semantic tokens."""
        clean_desc = description.strip().lower()
        for po_line in po_lines:
            po_desc = po_line.description.strip().lower()
            po_code = po_line.item_code.strip().lower()
            if po_desc in clean_desc or clean_desc in po_desc or po_code in clean_desc:
                return po_line
            # Token overlap check (require at least 2 common tokens)
            desc_tokens = set(clean_desc.split())
            po_tokens = set(po_desc.split())
            overlap = desc_tokens.intersection(po_tokens)
            if len(overlap) >= 2:
                return po_line
        # Strict matching: do not match arbitrary lines on single-line POs
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
        """Auto-draft professional enterprise email for human approver to dispatch with 1 click."""
        recipient = vendor.contact_email if vendor else (invoice.vendor.contact_email or "accounts@vendor.com")
        vendor_name = vendor.name if vendor else invoice.vendor.name
        curr = invoice.currency or "USD"

        # Construct vendor-facing reasons stripped of internal IDs and ERP internals
        vendor_bullets: List[str] = []

        if "duplicate" in discrepancies:
            dup = discrepancies["duplicate"]
            subject = f"REJECTED: Invoice #{invoice.invoice_number} (Duplicate Submission) from {vendor_name}"
            greeting = f"Dear Accounts Receivable Team at {vendor_name},"
            action_line = (
                f"Our systems show that Invoice #{invoice.invoice_number} in the amount of "
                f"{format_currency(invoice.total_amount, curr)} was previously processed on {dup.get('prior_processed_date', 'a prior date')}. "
                "No action is required from your team unless this was intended as an amended billing."
            )
            vendor_bullets.append(
                f"Invoice #{invoice.invoice_number} was already approved and registered for payment on {dup.get('prior_processed_date', 'earlier')}."
            )
        elif "tax_id_mismatch" in discrepancies:
            subject = f"REJECTED: Tax ID Verification Mismatch on Invoice #{invoice.invoice_number}"
            greeting = f"Dear {vendor_name} Finance Team,"
            action_line = "Your invoice could not be verified due to a statutory tax identification discrepancy:"
            vendor_bullets.append(
                f"Tax ID '{discrepancies['tax_id_mismatch'].get('provided_tax_id')}' stated on invoice does not match "
                "our registered Vendor Master tax record. Please submit a corrected invoice with your official Tax ID."
            )
        elif "vendor_unapproved" in discrepancies:
            subject = f"Onboarding Required: Invoice #{invoice.invoice_number} from {vendor_name}"
            greeting = f"Dear Accounts Payable Contact at {vendor_name},"
            action_line = "We received your invoice, but your organization is not yet onboarded in our ERP Vendor Master:"
            vendor_bullets.append(
                f"Vendor '{invoice.vendor.name}' requires formal onboarding before payments can be authorized. "
                "Please contact our vendor onboarding team to complete supplier registration."
            )
        elif decision == DecisionState.REJECTED:
            subject = f"REJECTED: Invoice #{invoice.invoice_number} from {vendor_name}"
            greeting = f"Dear Accounts Receivable Team at {vendor_name},"
            action_line = "Please review the issues noted below and submit a corrected invoice for re-processing:"
        else:
            subject = f"Action Required: Clarification for Invoice #{invoice.invoice_number} ({vendor_name})"
            greeting = f"Dear {vendor_name} Finance Team,"
            action_line = "Your invoice is currently on hold pending confirmation of the following item(s):"

        # Populate specific bullets if not already set above
        if not vendor_bullets:
            if "bank_details_mismatch" in discrepancies:
                vendor_bullets.append(
                    "Remittance bank details on invoice differ from registered vendor bank details on file. "
                    "For security compliance, please verify banking instructions via our supplier portal."
                )
            if "split_po_overrun" in discrepancies:
                over = discrepancies["split_po_overrun"]
                vendor_bullets.append(
                    f"Billed amount ({format_currency(invoice.total_amount, curr)}) exceeds authorized PO balance "
                    f"by {format_currency(over.get('deficit', 0.0), curr)}. An authorized PO amendment is needed."
                )
            if "price_variance" in discrepancies:
                pv = discrepancies["price_variance"]
                vendor_bullets.append(
                    f"Line {pv.get('line_number', 1)} unit price of {format_currency(pv.get('billed_unit_price', 0.0), curr)} "
                    f"exceeds contracted rate ({format_currency(pv.get('contracted_unit_price', 0.0), curr)}) on PO #{po.po_number if po else 'N/A'}."
                )
            if "missing_po" in discrepancies:
                vendor_bullets.append(
                    "Your invoice does not indicate an authorized Purchase Order reference. Please provide a valid PO number."
                )
            if "arithmetic_mismatch" in discrepancies:
                vendor_bullets.append(
                    "Invoice arithmetic check failed: Sum of line items or subtotal does not match the grand total."
                )
            if "low_confidence" in discrepancies:
                vendor_bullets.append(
                    "Document scan quality was insufficient for automated processing. A high-resolution digital copy is requested."
                )

        if not vendor_bullets:
            for r in reasons:
                clean_r = re.sub(r"\(Batch: [^)]+\)", "", r)
                clean_r = re.sub(r"\(Ref: [^)]+\)", "", clean_r)
                clean_r = clean_r.replace("Auto-rejected to prevent double payment.", "").strip()
                vendor_bullets.append(clean_r)

        bullet_points = "\n".join(f"  • {b}" for b in vendor_bullets)

        return f"""To: {recipient}
Subject: {subject}

{greeting}

We are processing Invoice #{invoice.invoice_number} (dated {invoice.invoice_date}) in the amount of {format_currency(invoice.total_amount, curr)} submitted to our Accounts Payable department.

{action_line}

{bullet_points}

To expedite approval and release of payment:
  1. Reply to this email with reference to PO #{po.po_number if po else 'N/A'}.
  2. If a rate addendum or contract revision applies, please attach the authorized documentation.
  3. For onboarding or invoice inquiries, reach our AP operations desk at ap-operations@company.internal.

Sincerely,
Accounts Payable Operations Team
Finance Shared Services Desk
Contact: ap-operations@company.internal
"""
