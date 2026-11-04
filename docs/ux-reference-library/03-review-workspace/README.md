# Category 03: Invoice Review Workspace & Document Extraction

## 1. Directory Inventory

| File | Source Product | Original Path | Visual Description & Scope |
|---|---|---|---|
| `ap_cc_04_invoice_review_unified_workspace.png` | AP Command Center | `competitor_research/03_flickai/screenshots/ui_evidence/04_invoice_review_unified_workspace.png` | Review workspace showing document viewer on left, and 4 stacked explanation banners/cards on right. |
| `ap_cc_doc_toolbar_zoom_sha.png` | AP Command Center | `test-artifacts/visual-ux-audit/doc_toolbar_zoom_sha.png` | PDF viewer toolbar with zoom controls, SHA checksum indicator, and download/fullscreen actions. |
| `ap_cc_scenario1_detail.png` | AP Command Center | `test-artifacts/visual-ux-audit/scenario1_detail.png` | Detailed invoice review for Scenario 1 showing policy checklist, verification steps, and verdict. |
| `finbooks_01_invoice_review_workspace.png` | FinBooks | `competitor_research/01_finbooks/screenshots/01_invoice_review_workspace.png` | Review screen with modal invoice form overlaying background; missing line-item verification. |
| `finbooks_02_source_doc_viewer.png` | FinBooks | `competitor_research/01_finbooks/screenshots/02_source_doc_viewer.png` | Slide-out right-hand drawer showing PDF source document, isolated from the bill entry form. |
| `flickai_01_invoice_builder_fields.png` | Flick AI | `competitor_research/03_flickai/screenshots/01_invoice_builder_fields.png` | Form field layout with vendor name, invoice date, currency, GSTIN, and tax rate dropdowns. |
| `flickai_03_create_new_invoice_builder.png` | Flick AI | `competitor_research/03_flickai/screenshots/03_create_new_invoice_builder.png` | Invoice builder showing reactive line-item calculation and total amount summary card. |
| `rossum_01_full_review_workspace_credit_note.png` | Rossum | `competitor_research/02_rossum/screenshots/01_full_review_workspace_credit_note.png` | 50/50 split workspace: interactive SVG bounding box on PDF (left), structured fields (right). |
| `rossum_04_field_highlight_issue_date.png` | Rossum | `competitor_research/02_rossum/screenshots/04_field_highlight_issue_date.png` | Coordinate-addressed bounding box highlighting exact text on PDF when field is clicked. |
| `rossum_08_us_tax_invoice_full_workspace.png` | Rossum | `competitor_research/02_rossum/screenshots/08_us_tax_invoice_full_workspace.png` | Multi-line tax invoice review with clear header, extraction confidence scores, and line grid. |
| `rossum_09_find_in_document.png` | Rossum | `competitor_research/02_rossum/screenshots/09_find_in_document.png` | Document search and highlight tool finding matching strings directly across scanned text. |

---

## 2. Visual Comparison: Competitor Benchmarks vs. AP Command Center

```
+----------------------------------------------------------------------------------------------------+
| INVOICE REVIEW WORKSPACE VISUAL COMPARISON                                                         |
+------------------------------------+---------------------------------------------------------------+
| AP Command Center (Current)        | Left: PDF viewer.                                             |
|                                    | Right: Stacks 4 components vertically (`VerdictBanner`,        |
|                                    | `CaseSummaryCard`, `PolicyChecksGrouped`, `ProcurementFlow`). |
|                                    | Line-item data table is pushed completely below the fold.     |
|                                    | User reads ~400 words of explanations before seeing items.    |
+------------------------------------+---------------------------------------------------------------+
| Rossum (Industry Gold Standard)    | Strict 50/50 split.                                           |
|                                    | Left: PDF with interactive SVG bounding boxes (`rect`).        |
|                                    | Right: Top header card -> Line Items Grid -> Footer total.    |
|                                    | Clicking any field instantly pans/zooms PDF to exact source.  |
|                                    | Primary action: Single green "Confirm" (or "Review Next").    |
+------------------------------------+---------------------------------------------------------------+
| Flick AI (Clean Builder Layout)    | Top-to-bottom structured cards: Vendor -> Header -> Line Grid.|
|                                    | Clean tabular display with automated tax summation.           |
+------------------------------------+---------------------------------------------------------------+
| FinBooks (Anti-Pattern to Avoid)   | Separates PDF into slide-out drawer (`srcDocPanel`) while      |
|                                    | editing happens in a popup modal (`editForm`).                |
|                                    | Forces user to switch tabs or squint at modal backdrop.       |
+------------------------------------+---------------------------------------------------------------+
```

### Visual Highlights & Lessons from Competitors
1. **Rossum Bounding Box Affinity (`rossum_04_field_highlight_issue_date.png`):**
   - High visual trust: A non-technical user immediately understands where numbers came from because clicking the "Invoice Total: ₹1,45,000" field highlights the identical box in neon orange on the original PDF.
   - Zero cognitive gap between document and data.
2. **Rossum Clean Right Pane Layout (`rossum_08_us_tax_invoice_full_workspace.png`):**
   - No excessive explanatory text. Instead of explaining *how* validation works, it simply shows the data fields, their status, and a sticky bottom footer with `Confirm [Space]` or `Reject`.
3. **FinBooks Major UI Flaw (`finbooks_01_invoice_review_workspace.png`):**
   - Opening an invoice puts the edit form in a modal overlay that hides the background screen, while the PDF document viewer is placed in a separate drawer that cannot be viewed side-by-side without overlapping. **We must avoid this modal-over-drawer trap.**

### Current AP Command Center Deficiencies (`ap_cc_04_invoice_review_unified_workspace.png`)
1. **Banner Fatigue:** 4 large colored boxes (`VerdictBanner` in yellow, `CaseSummaryCard` in white/gray, `PolicyChecksGrouped` in bordered box, `ProcurementVerificationFlow` in blue/gray) take up 85% of screen height before the user sees what was actually purchased.
2. **Disconnected Verification:** The 4-step procurement flow is displayed as abstract status cards rather than directly mapped to the line items.

---

## 3. Recommended Pattern Adaptations

### What to Adopt
- **True Side-by-Side Unified Workspace (Rossum Pattern):**
  - Left 48%: Embedded PDF document viewer with coordinate/page navigation.
  - Right 52%: Clean 3-tier review pane:
    1. **Invoice Summary Bar (Top):** Vendor, PO number, Date, Total Amount, and Reconciliation Status Badge.
    2. **Line-Item Verification Matrix (Center):** Direct comparison table (Invoice vs PO vs GRN vs Inspection) taking up the dominant visual area.
    3. **Sticky Action Footer (Bottom):** Primary action button (Approve / Confirm), Secondary action (Flag Discrepancy), and Overflow actions (Reassign, Download).
- **Collapse Explanations into Status Badges:** Replace the 4 verbose explanation cards with a compact 48px sticky verdict strip with expandable drawer on demand.

### What NOT to Copy
- Do not copy FinBooks' detached modal editor (`srcDocPanel` decoupled from `editForm`).
- Do not copy Rossum's complex formula configuration bars into buyer-facing views.
