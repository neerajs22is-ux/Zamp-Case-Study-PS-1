# Accounts Payable (AP) Digital Employee — Case Study Operating Assumptions

This document outlines the core business rules, operational constraints, and technical assumptions governing the Zamp Problem Statement 1 (PS-1) AP Digital Employee. These assumptions reflect realistic enterprise finance workflows while maintaining a deterministic evaluation framework.

---

### 1. Currency & Precision
Invoices specify an explicit ISO currency code (USD in the standalone PS-1 demo, INR in enterprise deployment). All line item calculations, tax validations, and PO matches operate within the same currency. Cross-currency invoices require an authorized FX rate table and are routed to manual review.

### 2. Deterministic Arithmetic Gate (Gate 0)
Before PO matching occurs, invoice mathematics must balance:
- **Line Total:** `abs(quantity * unit_price - line_total) <= 0.01`
- **Subtotal:** `abs(sum(line_totals) - subtotal) <= 0.01`
- **Grand Total:** `abs(subtotal + tax_amount - total_amount) <= tax_rounding_tolerance_threshold` (default: $5.00 / ₹5.00)

Any mathematical discrepancy halts straight-through processing and routes the invoice to Human-in-the-Loop (`FLAGGED_HITL_REVIEW`).

### 3. Vendor Identification & Tax ID Precedence
Tax ID (EIN, GSTIN, VAT) is the authoritative vendor key. If a Tax ID is present on the invoice, it is strictly validated against the ERP Vendor Master. A Tax ID mismatch triggers an immediate HOLD/REJECT and **never** falls back to fuzzy name matching.

### 4. Normalized Vendor Name Matching
When Tax ID is absent, vendor matching utilizes normalized alphanumeric token matching (stripping suffixes like *Inc*, *LLC*, *Ltd*, *Pvt*, punctuation, and whitespace) with a minimum length threshold (≥ 3 characters). If no match or multiple ambiguous matches are found, the invoice is held for vendor onboarding.

### 5. PO Reference Inference Policy
When an invoice omits a PO reference, the system inspects open POs for the verified vendor:
- If **exactly one** open PO exists, the PO is inferred, but straight-through approval is disabled (`FLAGGED_HITL_REVIEW` with an `inferred_po` flag).
- If **zero or multiple** open POs exist, the invoice is held for PO assignment (`missing_po`).

### 6. Strict 2-Way Line Matching
Invoice line items match PO lines using item code or description token containment (minimum 2 overlapping semantic tokens). Unmatched lines are flagged as unapproved items (`unmatched_line`), preventing arbitrary line substitution even on single-line POs.

### 7. Multi-Line Quantity Aggregation
When an invoice contains multiple line items mapped to the same underlying PO line item, billed quantities are aggregated before evaluating against the PO line's remaining authorized quantity.

### 8. Cumulative Split-PO Budget Enforcement
Approved invoices draw down PO balances in real-time. Invoices with amounts exceeding the remaining authorized balance trigger a budget overrun exception (`split_po_overrun`), preserving the audit trail for cumulative commitments.

### 9. Multi-Tier Duplicate Detection
Duplicate detection operates across three tiers:
1. **Normalized Key:** Normalized invoice number (stripping delimiters and leading zeros) + vendor ID.
2. **Cryptographic Integrity:** Exact SHA-256 payload/text hash match.
3. **Fuzzy Temporal Window:** Same vendor + exact amount within a configurable date window (default 30 days) using invoice issue dates.

### 10. Remittance & Bank Account Validation
If bank remittance account numbers or routing details are present on the invoice, they are verified against the bank details in the ERP Vendor Master. Any discrepancy triggers an immediate security HOLD (`bank_details_mismatch`) to protect against invoice redirection fraud.
