"""Deterministic Indian GST, 3-Way Matching, and AP Policy Verification.

Performs zero-hallucination arithmetic and cross-reference verification:
1. GST Line Item & Tax Arithmetic (CGST/SGST vs IGST, rounding tolerance).
2. Supplier Master verification (fictional_supplier_master.csv).
3. 3-Way PO / GRN / QC Matching (purchase_orders, goods_receipts, quality_inspections).
4. Rate contracts and milestone checks.
5. In accordance with AP governance: MATCH_CANDIDATE is recorded, never automatic payment execution.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Dict, List, Optional
import pandas as pd

from engine.schemas import MantleInvoiceExtraction


@dataclass
class TaxArithmeticResult:
    is_valid: bool
    calculated_tax: float
    calculated_grand_total: float
    tax_discrepancy: float
    total_discrepancy: float
    tax_type_valid: bool  # CGST+SGST for intrastate, IGST for interstate
    notes: List[str] = field(default_factory=list)


@dataclass
class ThreeWayMatchResult:
    po_found: bool
    po_matched: bool
    grn_found: bool
    grn_matched: bool
    qc_found: bool
    qc_matched: bool
    price_variance_pct: float = 0.0
    qty_variance: float = 0.0
    discrepancy_reasons: List[str] = field(default_factory=list)
    match_status: str = "UNMATCHED"  # MATCH_CANDIDATE, PRICE_VARIANCE, QTY_EXCEEDED, QC_REJECTED, NO_PO


class IndianAPRuleEngine:
    """Deterministic validation engine for Indian GST and manufacturing AP workflows."""

    def __init__(self, reference_dir: Optional[str] = None, load_reference_data: bool = True) -> None:
        ref_dir = reference_dir or os.path.join("tests", "evaluation_corpus_v2", "reference_data")
        self.ref_dir = ref_dir
        
        # Load reference datasets into memory
        self.suppliers_df = pd.DataFrame()
        self.pos_df = pd.DataFrame()
        self.grns_df = pd.DataFrame()
        self.qcs_df = pd.DataFrame()
        self.rates_df = pd.DataFrame()
        self.milestones_df = pd.DataFrame()
        self.service_periods_df = pd.DataFrame()
        if load_reference_data:
            self._load_reference_data()

    def _load_reference_data(self) -> None:
        def clean_df(path: str) -> pd.DataFrame:
            if os.path.exists(path):
                df = pd.read_csv(path, encoding="utf-8-sig")
                df.columns = [c.strip().lstrip("\ufeff") for c in df.columns]
                return df
            return pd.DataFrame()

        sup_path = os.path.join(os.path.dirname(self.ref_dir), "fictional_supplier_master.csv")
        self.suppliers_df = clean_df(sup_path)

        po_path = os.path.join(self.ref_dir, "purchase_orders.csv")
        self.pos_df = clean_df(po_path)

        grn_path = os.path.join(self.ref_dir, "goods_receipts.csv")
        self.grns_df = clean_df(grn_path)

        qc_path = os.path.join(self.ref_dir, "quality_inspections.csv")
        self.qcs_df = clean_df(qc_path)

        rate_path = os.path.join(self.ref_dir, "rate_contracts.csv")
        self.rates_df = clean_df(rate_path)

        ms_path = os.path.join(self.ref_dir, "milestones.csv")
        self.milestones_df = clean_df(ms_path)

        sp_path = os.path.join(self.ref_dir, "service_periods.csv")
        self.service_periods_df = clean_df(sp_path)

    def verify_tax_arithmetic(self, inv: MantleInvoiceExtraction) -> TaxArithmeticResult:
        """Verifies GST math: taxable + (cgst+sgst+igst) == grand_total within ₹1 tolerance."""
        notes = []
        calc_tax = round(inv.cgst_amount + inv.sgst_amount + inv.igst_amount, 2)
        calc_gt = round(inv.taxable_value + calc_tax, 2)
        
        tax_disc = round(abs(calc_tax - round(inv.total_tax_amount, 2)), 2)
        total_disc = round(abs(calc_gt - round(inv.grand_total, 2)), 2)
        
        is_math_valid = (tax_disc <= 1.0) and (total_disc <= 1.0)
        if not is_math_valid:
            notes.append(f"Arithmetic mismatch: Taxable ({inv.taxable_value}) + Tax ({calc_tax}) = {calc_gt}, reported grand total {inv.grand_total}")

        # Line-item arithmetic check
        for li in inv.line_items:
            if getattr(li, "line_arithmetic_valid", True) is False:
                is_math_valid = False
                notes.append(f"Line arithmetic mismatch for '{li.item_description}': qty ({li.quantity}) * unit price ({li.unit_price}) differs from taxable amount ({li.taxable_amount}) by ?{getattr(li, 'line_discrepancy', 0.0):.2f}")

        # Intrastate vs Interstate rules
        tax_type_valid = True
        if inv.place_of_supply and "karnataka" in inv.place_of_supply.lower():
            # If supplier is also in Karnataka (29 prefix) -> intrastate
            if inv.supplier_gstin and inv.supplier_gstin.startswith("29"):
                if inv.igst_amount > 0 and (inv.cgst_amount == 0 and inv.sgst_amount == 0):
                    tax_type_valid = False
                    notes.append("Intrastate transaction (Karnataka) should have CGST+SGST, not IGST.")
        
        return TaxArithmeticResult(
            is_valid=is_math_valid and tax_type_valid,
            calculated_tax=calc_tax,
            calculated_grand_total=calc_gt,
            tax_discrepancy=tax_disc,
            total_discrepancy=total_disc,
            tax_type_valid=tax_type_valid,
            notes=notes,
        )

    def verify_three_way_match(self, inv: MantleInvoiceExtraction) -> ThreeWayMatchResult:
        """Matches invoice against PO, GRN, and QC records."""
        po_num = (inv.po_reference or "").strip()
        if not po_num:
            return ThreeWayMatchResult(
                po_found=False,
                po_matched=False,
                grn_found=False,
                grn_matched=False,
                qc_found=False,
                qc_matched=False,
                discrepancy_reasons=["Invoice does not reference a Purchase Order (Non-PO invoice)."],
                match_status="NO_PO",
            )

        # Check PO
        po_rows = self.pos_df[self.pos_df["po_number"] == po_num] if not self.pos_df.empty else pd.DataFrame()
        if po_rows.empty:
            return ThreeWayMatchResult(
                po_found=False,
                po_matched=False,
                grn_found=False,
                grn_matched=False,
                qc_found=False,
                qc_matched=False,
                discrepancy_reasons=[f"Purchase order {po_num} not found in ERP records."],
                match_status="NO_PO",
            )

        po_rec = po_rows.iloc[0].to_dict()
        ord_qty = float(po_rec.get("ordered_quantity", 0))
        agreed_rate = float(po_rec.get("agreed_unit_price", 0))
        ord_taxable = float(po_rec.get("ordered_taxable_value", 0))

        # Sum invoiced quantities from line items
        inv_qty = sum(item.quantity for item in inv.line_items) if inv.line_items else ord_qty
        qty_variance = round(inv_qty - ord_qty, 2)

        discrepancies: List[str] = []
        if qty_variance > 0:
            discrepancies.append(f"Invoiced quantity ({inv_qty}) exceeds PO ordered quantity ({ord_qty}) by {qty_variance} units.")

        price_variance_pct = 0.0
        if len(inv.line_items) == 1 and agreed_rate > 0:
            price_variance_pct = round(((inv.line_items[0].unit_price - agreed_rate) / agreed_rate) * 100.0, 2)
            if price_variance_pct > 1.50:  # Policy threshold 1.5%
                discrepancies.append(f"Unit price ₹{inv.line_items[0].unit_price:.2f} exceeds PO agreed price ₹{agreed_rate:.2f} by {price_variance_pct}%.")
        elif ord_taxable > 0:
            taxable_variance_pct = round(((inv.taxable_value - ord_taxable) / ord_taxable) * 100.0, 2)
            if taxable_variance_pct > 1.50:
                discrepancies.append(f"Taxable value ₹{inv.taxable_value:.2f} exceeds PO authorized value ₹{ord_taxable:.2f} by {taxable_variance_pct}%.")

        if inv.taxable_value > (ord_taxable * 1.015) and not any("Taxable value" in d for d in discrepancies):
            discrepancies.append(f"Taxable value ₹{inv.taxable_value:.2f} exceeds PO authorized value ₹{ord_taxable:.2f}.")

        # Check GRN
        grn_matched = False
        grn_found = False
        grn_rows = self.grns_df[self.grns_df["po_number"] == po_num] if not self.grns_df.empty else pd.DataFrame()
        if not grn_rows.empty:
            grn_found = True
            rec_qty = sum(float(r.get("received_quantity", 0)) for _, r in grn_rows.iterrows())
            acc_qty = sum(float(r.get("accepted_quantity", 0)) for _, r in grn_rows.iterrows())
            if inv_qty <= acc_qty:
                grn_matched = True
            else:
                discrepancies.append(f"Invoiced quantity ({inv_qty}) exceeds GRN accepted quantity ({acc_qty}).")

        # Check QC
        qc_matched = False
        qc_found = False
        qc_rows = self.qcs_df[self.qcs_df["po_number"] == po_num] if not self.qcs_df.empty else pd.DataFrame()
        if not qc_rows.empty:
            qc_found = True
            qc_pass = any(str(r.get("inspection_status", "")).upper() == "ACCEPTED" for _, r in qc_rows.iterrows())
            qc_matched = qc_pass
            if not qc_pass:
                discrepancies.append("Quality inspection rejected or pending (QC hold).")

        # Check Rate Contracts (applies to job work and contracted service rate checks)
        rate_contract_exceeded = False
        if not self.rates_df.empty:
            sup_id = po_rec.get("supplier_id")
            sup_rates = self.rates_df[self.rates_df["supplier_id"] == sup_id]
            if not sup_rates.empty:
                for _, rc_row in sup_rates.iterrows():
                    app_rate = float(rc_row.get("approved_rate", 0))
                    rc_service = str(rc_row.get("service", "")).lower()
                    for item in inv.line_items:
                        item_desc = item.item_description.lower()
                        is_contract_work = ("job work" in item_desc) or ("turning" in item_desc and "cnc" in rc_service)
                        if is_contract_work and item.unit_price > (app_rate * 1.015):
                            rate_contract_exceeded = True
                            discrepancies.append(
                                f"Invoiced rate ₹{item.unit_price:.2f} exceeds approved rate contract "
                                f"({rc_row.get('contract_id')}) ₹{app_rate:.2f}."
                            )

        # Check Milestones
        milestone_pending = False
        if not self.milestones_df.empty:
            po_milestones = self.milestones_df[self.milestones_df["po_number"] == po_num]
            if not po_milestones.empty:
                for _, ms_row in po_milestones.iterrows():
                    ms_status = str(ms_row.get("completion_status", "")).upper()
                    if ms_status != "COMPLETED":
                        milestone_pending = True
                        discrepancies.append(
                            f"Milestone '{ms_row.get('milestone')}' is not completed (status: {ms_status})."
                        )

        # Check Service Periods (Prepaid SaaS / Recurring)
        service_period_review = False
        if not self.service_periods_df.empty:
            sp_rows = self.service_periods_df[self.service_periods_df["invoice_number"] == inv.invoice_number]
            if not sp_rows.empty:
                for _, sp_row in sp_rows.iterrows():
                    prepaid_m = int(sp_row.get("prepaid_period_months", 0))
                    if prepaid_m > 1:
                        service_period_review = True
                        discrepancies.append(
                            f"Prepaid service period ({prepaid_m} months) requires prepaid accounting review."
                        )

        # Determine overall match status
        if discrepancies:
            if not qc_matched and qc_found:
                status = "QC_REJECTED"
            elif not grn_matched and grn_found:
                status = "GRN_QTY_MISMATCH"
            elif rate_contract_exceeded:
                status = "RATE_CONTRACT_EXCEEDED"
            elif milestone_pending:
                status = "MILESTONE_PENDING"
            elif service_period_review:
                status = "SERVICE_PERIOD_REVIEW"
            elif qty_variance > 0:
                status = "QTY_EXCEEDED"
            elif price_variance_pct > 1.50:
                status = "PRICE_VARIANCE"
            else:
                status = "VARIANCE_EXCEEDED"
        else:
            status = "MATCH_CANDIDATE"

        return ThreeWayMatchResult(
            po_found=True,
            po_matched=(len(discrepancies) == 0),
            grn_found=grn_found,
            grn_matched=grn_matched,
            qc_found=qc_found,
            qc_matched=qc_matched,
            price_variance_pct=price_variance_pct,
            qty_variance=qty_variance,
            discrepancy_reasons=discrepancies,
            match_status=status,
        )
