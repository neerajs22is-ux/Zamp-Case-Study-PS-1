# Category 04: Procurement Reconciliation (3-Way & 4-Way Matching)

## 1. Directory Inventory

| File | Source Product | Original Path | Visual Description & Scope |
|---|---|---|---|
| `ap_cc_05_line_item_inline_editing.png` | AP Command Center | `competitor_research/03_flickai/screenshots/ui_evidence/05_line_item_inline_editing.png` | Inline editable line items table showing rate, quantity, tax, and variance calculation. |
| `ap_cc_06_line_item_corrected_gate.png` | AP Command Center | `competitor_research/03_flickai/screenshots/ui_evidence/06_line_item_corrected_gate_re-evaluated.png` | Post-correction state where modified line item triggers dynamic gate re-evaluation to `PASSED`. |
| `ap_cc_procurement_flow_fixed.png` | AP Command Center | `test-artifacts/visual-ux-audit/procurement_flow_fixed.png` | Visual pipeline showing 4 nodes: Invoice Billed -> PO Ordered -> GRN Delivered -> Quality Inspected. |
| `finbooks_01_vendor_master.png` | FinBooks | `competitor_research/01_finbooks/screenshots/01_vendor_master.png` | Vendor repository with GSTIN, default payment terms, bank details, and compliance history. |
| `finbooks_03_purchase_orders.png` | FinBooks | `competitor_research/01_finbooks/screenshots/03_purchase_orders.png` | PO master list showing order values, delivery dates, and linked vendor bill status. |
| `flickai_01_bank_statements_upload_tab.png` | Flick AI | `competitor_research/03_flickai/screenshots/01_bank_statements_upload_tab.png` | External statement ingestion for cash/payment matching against approved vendor invoices. |
| `flickai_03_gst_compliance_reconciliation.png` | Flick AI | `competitor_research/03_flickai/screenshots/03_gst_compliance_reconciliation.png` | Side-by-side tax reconciliation matching portal data against purchase register line items. |
| `flickai_04_invoice_builder_added_row.png` | Flick AI | `competitor_research/03_flickai/screenshots/04_invoice_builder_added_row.png` | Line item editor with dynamic row insertion, automatic subtotals, and column alignment. |
| `rossum_03_us_invoice_line_items_grid.png` | Rossum | `competitor_research/02_rossum/screenshots/03_us_invoice_line_items_grid.png` | Multi-line extraction grid mapping Description, Qty, Unit Price, Tax, and Amount directly to PDF. |
| `rossum_extensions_store.png` | Rossum | `competitor_research/02_rossum/screenshots/extensions_store.png` | 2-way/3-way ERP matching rules engine configuration and enterprise integration catalog. |

---

## 2. Visual Comparison: Competitor Benchmarks vs. AP Command Center

```
+----------------------------------------------------------------------------------------------------+
| 3-WAY & 4-WAY RECONCILIATION VISUAL COMPARISON                                                     |
+------------------------------------+---------------------------------------------------------------+
| AP Command Center (Current)        | Stacks 4 abstract pipeline cards (Invoice -> PO -> GRN ->     |
|                                    | Inspection), then presents a separate table for lines.        |
|                                    | Discrepancies are flagged in technical text badges, but the   |
|                                    | direct comparison of (Billed vs Ordered vs Delivered) is not  |
|                                    | consolidated into a single unified row view.                  |
+------------------------------------+---------------------------------------------------------------+
| Flick AI (Gold Standard: Matching) | Direct reconciliation grid with side-by-side column groups:   |
|                                    | [ Item | Billed | Ordered | Delivered | Passed | Variance ].  |
|                                    | Variances are highlighted with color-coded delta chips.        |
+------------------------------------+---------------------------------------------------------------+
| Rossum (Gold Standard: Lines Grid) | Dense, readable tabular grid with auto-sum verification.      |
|                                    | Clicking any line cell highlights the exact table row on the  |
|                                    | original PDF invoice.                                         |
+------------------------------------+---------------------------------------------------------------+
| FinBooks (Anti-Pattern: Prompt)    | Lacks native visual 3-way matching in the bill review screen.  |
|                                    | Relies on browser `window.prompt` or dropdown modal to link   |
|                                    | PO numbers, hiding line-level discrepancy proofs.             |
+------------------------------------+---------------------------------------------------------------+
```

### Key Insights from Competitor Screenshots
1. **Flick AI Multi-Source Alignment (`flickai_03_gst_compliance_reconciliation.png`):**
   - Renders 2 sources side-by-side with matched rows horizontally aligned.
   - Any difference (e.g., mismatch in rate or quantity) shows an amber/red difference tag right between the columns (e.g. `Δ +₹1,200`).
   - Non-technical buyers immediately see *why* an invoice cannot be paid.
2. **Rossum Line Table Alignment (`rossum_03_us_invoice_line_items_grid.png`):**
   - High data density without visual clutter: clean borders, right-aligned monetary values, and monospace font for numbers.
   - Automatic line subtotal validation against invoice header total.

### Current AP Command Center Deficiencies (`ap_cc_05_line_item_inline_editing.png` & `ap_cc_procurement_flow_fixed.png`)
1. **Cognitive Disconnect:** The 4-step pipeline shows abstract checkmarks ("PO Matched", "GRN Received", "Inspection Passed"), but when a quantity mismatch occurs (e.g., billed 50, delivered 45), the user must scroll down to find which item failed.
2. **Abstract Tolerance Messages:** Displays `QTY_TOLERANCE_EXCEEDED: 0.00%` instead of showing a plain statement: *"Supplier billed for 50 units, but only 45 units were received at the warehouse."*

---

## 3. Recommended Pattern Adaptations

### What to Adopt
- **The Consolidated 4-Way Reconciliation Table:**
  - Consolidate the 4 procurement stages directly into the columns of the line-item table:
    | Item Description | Billed (Inv) | Ordered (PO) | Delivered (GRN) | Inspected (QC) | Status / Delta | Action |
    |---|---|---|---|---|---|---|
    | Industrial Valve 2" | 50 @ ₹1,000 | 50 @ ₹1,000 | **45** @ ₹1,000 | 45 Passed | 🔴 **Missing 5 units** (₹5,000) | Adjust / Dispute |
  - A single glance tells the complete story: supplier billed for 50, but warehouse only received 45.
- **Inline Correction with Instant Feedback (`ap_cc_06_line_item_corrected_gate.png`):**
  - Keep the inline editing capability built in AP Command Center, but simplify the save interaction: immediately recalculate line total and turn the red status badge to green with a subtle toast.

### What NOT to Copy
- Do not copy FinBooks' hidden line items where the user is expected to approve an entire invoice without inspecting line-level quantities.
- Avoid Rossum's complex regex/Python rule builder in the reconciliation UI.
