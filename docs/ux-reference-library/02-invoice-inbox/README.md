# Category 02: Invoice Inbox & Document Intake Management

## 1. Directory Inventory

| File | Source Product | Original Path | Visual Description & Scope |
|---|---|---|---|
| `ap_cc_inbox_table.png` | AP Command Center | `test-artifacts/visual-ux-audit/inbox_table.png` | Current table view of ingested invoices with status badges, vendor names, amounts, and action buttons. |
| `ap_cc_03_inbox_temporal_filtering.png` | AP Command Center | `competitor_research/03_flickai/screenshots/ui_evidence/03_inbox_temporal_filtering.png` | Temporal and status filtering interface with multi-select chips and search inputs. |
| `finbooks_01_vendor_bills_workspace.png` | FinBooks | `competitor_research/01_finbooks/screenshots/01_vendor_bills_workspace.png` | Tabular vendor bill queue with batch action bar, document status chips, and date ranges. |
| `finbooks_02_upload_modal.png` | FinBooks | `competitor_research/01_finbooks/screenshots/02_upload_modal.png` | Multi-file drag-and-drop modal with file format requirements and progress indicators. |
| `finbooks_07_bills_list_after_upload.png` | FinBooks | `competitor_research/01_finbooks/screenshots/07_bills_list_after_upload.png` | Instant list update post-intake showing OCR processing state and newly created bill rows. |
| `flickai_02_invoices_list_view.png` | Flick AI | `competitor_research/03_flickai/screenshots/02_invoices_list_view.png` | Purchase invoice master list with financial summary banner, vendor logos, and status tags. |
| `flickai_03_purchase_invoices_tab.png` | Flick AI | `competitor_research/03_flickai/screenshots/03_purchase_invoices_tab.png` | Tabbed queue view separating "Draft", "Approved", "Paid", and "Disputed" categories. |
| `flickai_05_upload_files_modal.png` | Flick AI | `competitor_research/03_flickai/screenshots/05_upload_files_modal.png` | Minimalist single-step upload dialog with immediate background OCR extraction preview. |
| `rossum_01_document_list_queue_initial.png` | Rossum | `competitor_research/02_rossum/screenshots/01_document_list_queue_initial.png` | Standard queue table showing document status pills, issue dates, amounts, and validation score. |
| `rossum_02_all_documents_queue.png` | Rossum | `competitor_research/02_rossum/screenshots/02_all_documents_queue.png` | Queue view with pagination, column visibility toggles, and instant status filtering. |
| `rossum_03_queue_filter_menu.png` | Rossum | `competitor_research/02_rossum/screenshots/03_queue_filter_menu.png` | Dropdown filter interface allowing filtering by validation error, vendor, and amount threshold. |
| `rossum_upload_modal.png` | Rossum | `competitor_research/02_rossum/screenshots/upload_modal.png` | Bulk document ingestion dialog supporting PDF, TIFF, PNG with real-time queue destination picker. |

---

## 2. Visual Comparison: Competitor Benchmarks vs. AP Command Center

```
+----------------------------------------------------------------------------------------------------+
| INVOICE INBOX DESIGN BENCHMARK                                                                     |
+------------------------------------+---------------------------------------------------------------+
| AP Command Center (Current)        | Monolithic table with 10+ columns. Status labels use technical|
|                                    | policy jargon ("MANUAL_REVIEW_REQUIRED", "GATE_FAILED").      |
|                                    | Action buttons crowd each row ("View", "Re-evaluate", "Audit")|
+------------------------------------+---------------------------------------------------------------+
| Flick AI (Gold Standard: Clarity)  | Pre-filtered tabs: [ Needs Action (4) ] [ In Review (2) ]     |
|                                    | [ Verified / Ready (12) ] [ Paid / Closed (48) ].             |
|                                    | Status badges use plain human language: "Needs Receipt", etc. |
+------------------------------------+---------------------------------------------------------------+
| Rossum (Gold Standard: Batching)   | Real-time validation badges (`1 error`). Split queue folders. |
|                                    | Multi-document batch action bar appears only on row select.   |
+------------------------------------+---------------------------------------------------------------+
| FinBooks (Reference: Accounting)   | Vendor bills segregated cleanly by fiscal year. Batch upload  |
|                                    | modal is simple, but row actions trigger disruptive popups.   |
+------------------------------------+---------------------------------------------------------------+
```

### Key Visual Strengths from Competitors
1. **Flick AI Stage Tabs (`flickai_03_purchase_invoices_tab.png`):**
   - Eliminates need for non-technical users to build compound SQL-like filters.
   - Tabs segment work into distinct operational states: *Needs Action*, *Pending Approval*, *All Invoices*.
   - Counts inside each tab header show workload volume at a glance.
2. **Rossum Status & Error Badges (`rossum_01_document_list_queue_initial.png`):**
   - High visual contrast: Green checkmark icon for `Postponed` or `Confirmed`, red exclamation icon for `To review (1 error)`.
   - Hover reveals the exact validation issue ("Missing Purchase Order reference") before clicking into workspace.

### Current AP Command Center Deficiencies (`ap_cc_inbox_table.png`)
1. **Column Overcrowding:** Shows raw IDs, technical flags, and multiple action icons on small viewports.
2. **Cryptic Status Terminology:** Status chips display internal engine constants (`DISCREPANCY_FLAGGED`, `EVAL_RUN_COMPLETED`) instead of business states.
3. **Missing High-Level Summary:** Lacks an immediate total exposure counter across the selected tab.

---

## 3. Recommended Pattern Adaptations

### What to Adopt
- **4 Standard Operational Tabs:**
  1. `⚠️ Needs Attention (N)` — Invoices with discrepancies, missing documents, or unassigned owners.
  2. `⏱️ Ready for Approval (N)` — 3-way/4-way matched invoices awaiting manager sign-off.
  3. `⏳ Waiting on Others (N)` — Invoices dispatched to vendors or warehouse for receipts.
  4. `✅ Completed / Approved (N)` — Settled or exported invoices.
- **Human-Readable Status Pills:**
  - Replace `GATE_FAILED: QTY_TOLERANCE_EXCEEDED` with `Qty Discrepancy: +5 units`.
  - Replace `MANUAL_REVIEW_REQUIRED` with `Needs Line Review`.
- **Streamlined Row Actions:**
  - Single primary action per row: `Review Invoice` (or `Approve` if clean). Secondary actions placed in a subtle `...` overflow menu.

### What NOT to Copy
- Do not copy FinBooks' cluttered multi-select toolbar that permanently occupies vertical height when 0 rows are selected.
- Do not adopt Rossum's raw schema configuration toggles in the inbox view.
