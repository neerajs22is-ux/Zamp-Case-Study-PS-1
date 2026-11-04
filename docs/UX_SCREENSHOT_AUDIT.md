# AP Command Center — Visual UX Audit & Competitor Screenshot Reference Library

**Date:** November 2026  
**Auditor:** Principal UX Product Architect & Applied AI Engineering Pair  
**Repository State:** `handoff/ap-command-center` (Base commit `29d3c28`)  
**Scope:** Non-invasive visual UX audit, competitor screenshot benchmarking, and curated reference library. Zero application code or database mutations.

---

## 1. Executive Summary

### 1.1 The Problem & Transformation Mandate
Despite previous functional enhancements, the **AP Command Center** suffers from severe visual overcrowding and cognitive friction. A first-time, non-technical buyer—such as a Finance Controller, Head of Accounts Payable, or CFO—is confronted with:
1. **Stacked Explanations:** Up to four stacked analytical cards (`VerdictBanner`, `CaseSummaryCard`, `PolicyChecksGrouped`, `ProcurementVerificationFlow`) pushing the actual invoice line items 1,200px below the fold.
2. **Technical Leaks:** Direct exposure of test-harness buttons ("Run Scenario 1–6", "Reset Demo Fixtures"), SHA-256 raw strings, and database state enums (`EVAL_RUN_COMPLETED`, `GATE_FAILED: QTY_TOLERANCE_EXCEEDED`).
3. **Modal Friction:** A 600-word confirmation modal with multiple legalistic checkboxes for standard, 100% matched invoice approvals.

### 1.2 The Benchmarking Lens
To solve this, we conducted a visual and architectural audit comparing our application against three benchmark AP and invoice automation platforms:
- **Rossum (`competitor_research/02_rossum`):** The global benchmark for split-screen invoice extraction, coordinate-addressed SVG bounding boxes, and high-velocity 1-click confirmation gating.
- **Flick AI (`competitor_research/03_flickai`):** The modern benchmark for clean information architecture, 3-card executive KPI dashboards, period-scoped accounting inboxes, and frictionless line-item reconciliation.
- **FinBooks (`competitor_research/01_finbooks`):** A traditional Indian GST compliance system offering valuable patterns in fiscal year navigation and duplicate hash prevention, alongside cautionary anti-patterns (detached modal forms and browser prompts).

### 1.3 Key Audit Finding & Strategic Direction
**"Show less. Explain better. Require fewer actions."**  
Non-technical buyers do not want software that lectures them on how matching algorithms work. They want software that:
1. Answers in 5 seconds: **What needs my attention right now?**
2. Presents a 50/50 side-by-side workspace: **Original PDF on the left, 4-Way Reconciliation Table on the right.**
3. Reduces approval friction: **From a 600-word modal to a 45-word, 1-click confirmation dialog.**

---

## 2. Master Screenshot Inventory

Below is the complete catalogue of curated screenshot evidence organized across FinBooks, Rossum, Flick AI, and our AP Command Center baseline.

| Screenshot ID | Product | Original Filename | Curated Reference Path | Screen Category | Visible UI Component | Relevant UX Problem | Quality | Benchmark Evidence Ref |
|---|---|---|---|---|---|---|---|---|
| `SCR-DB-01` | AP Command Center | `today_light.png` | `docs/ux-reference-library/01-dashboard/` | Dashboard | 8-panel widget stack | Vertical sprawl; technical test runner leaks | High | Baseline Capture |
| `SCR-DB-02` | AP Command Center | `02_dashboard_exposure_scorecard.png` | `docs/ux-reference-library/01-dashboard/` | Dashboard | Financial exposure scorecard | High density of unprioritized risk numbers | High | UI Evidence #02 |
| `SCR-DB-03` | Flick AI | `01_main_dashboard_full.png` | `docs/ux-reference-library/01-dashboard/` | Dashboard | 3-card KPI bar & period picker | Eliminates cognitive clutter; clean 3-zone layout | High | Flick AI EV-01 |
| `SCR-DB-04` | Flick AI | `02_dashboard_and_sidebar.png` | `docs/ux-reference-library/01-dashboard/` | Dashboard | Sidebar navigation drawer | Streamlined IA with badge counters | High | Flick AI EV-02 |
| `SCR-DB-05` | Rossum | `01_statistics_dashboard_full.png` | `docs/ux-reference-library/01-dashboard/` | Dashboard | Queue throughput & automation rate | Proves business ROI (straight-through rate) | High | Rossum EV-01 |
| `SCR-DB-06` | FinBooks | `01_dashboard_full.png` | `docs/ux-reference-library/01-dashboard/` | Dashboard | Fiscal year selector & cards | Quick financial period context switching | Medium | FinBooks EV-01 |
| `SCR-DB-07` | FinBooks | `02_dashboard_bank_statement_view.png` | `docs/ux-reference-library/01-dashboard/` | Dashboard | Bank matching summary | Separation of cash flow from bill review | Medium | FinBooks EV-02 |
| `SCR-IB-01` | AP Command Center | `inbox_table.png` | `docs/ux-reference-library/02-invoice-inbox/` | Invoice Inbox | Monolithic 10-column table | Cryptic enum badges; excessive action buttons | High | Baseline Capture |
| `SCR-IB-02` | AP Command Center | `03_inbox_temporal_filtering.png` | `docs/ux-reference-library/02-invoice-inbox/` | Invoice Inbox | Date range & multi-select chips | Over-complex filter builder for non-tech buyers | High | UI Evidence #03 |
| `SCR-IB-03` | Flick AI | `02_invoices_list_view.png` | `docs/ux-reference-library/02-invoice-inbox/` | Invoice Inbox | Vendor bill master list | Scannable typography; clear status badges | High | Flick AI EV-02 |
| `SCR-IB-04` | Flick AI | `03_purchase_invoices_tab.png` | `docs/ux-reference-library/02-invoice-inbox/` | Invoice Inbox | Segmented operational tabs | Replaces complex filters with 4 work queues | High | Flick AI EV-03 |
| `SCR-IB-05` | Flick AI | `05_upload_files_modal.png` | `docs/ux-reference-library/02-invoice-inbox/` | Invoice Inbox | Minimalist upload dialog | Zero-friction drag-and-drop ingestion | High | Flick AI EV-05 |
| `SCR-IB-06` | Rossum | `01_document_list_queue_initial.png` | `docs/ux-reference-library/02-invoice-inbox/` | Invoice Inbox | Document queue with error pills | Error count badge (`1 error`) visible in row | High | Rossum EV-01 |
| `SCR-IB-07` | Rossum | `02_all_documents_queue.png` | `docs/ux-reference-library/02-invoice-inbox/` | Invoice Inbox | Paginated document table | High-density data grid with batch actions | High | Rossum EV-02 |
| `SCR-IB-08` | Rossum | `03_queue_filter_menu.png` | `docs/ux-reference-library/02-invoice-inbox/` | Invoice Inbox | Fast queue filter popover | Contextual search by error category | High | Rossum EV-03 |
| `SCR-IB-09` | Rossum | `upload_modal.png` | `docs/ux-reference-library/02-invoice-inbox/` | Invoice Inbox | Multi-queue ingest modal | Multi-format drop zone (PDF, TIFF, PNG) | High | Rossum EV-Upload |
| `SCR-IB-10` | FinBooks | `01_vendor_bills_workspace.png` | `docs/ux-reference-library/02-invoice-inbox/` | Invoice Inbox | Bills queue with batch action bar | Period-scoped bills table | Medium | FinBooks EV-01 |
| `SCR-IB-11` | FinBooks | `02_upload_modal.png` | `docs/ux-reference-library/02-invoice-inbox/` | Invoice Inbox | Bulk bill upload modal | File format guidelines and progress bar | Medium | FinBooks EV-02 |
| `SCR-IB-12` | FinBooks | `07_bills_list_after_upload.png` | `docs/ux-reference-library/02-invoice-inbox/` | Invoice Inbox | Instant post-upload list update | Shows OCR processing state cleanly | Medium | FinBooks EV-07 |
| `SCR-RW-01` | AP Command Center | `04_invoice_review_unified_workspace.png` | `docs/ux-reference-library/03-review-workspace/` | Review Workspace | Stacked 4-card explanation pane | Pushes line items below fold; 400 words | High | UI Evidence #04 |
| `SCR-RW-02` | AP Command Center | `doc_toolbar_zoom_sha.png` | `docs/ux-reference-library/03-review-workspace/` | Review Workspace | PDF viewer toolbar | Technical SHA strings cluttering top header | High | Baseline Capture |
| `SCR-RW-03` | AP Command Center | `scenario1_detail.png` | `docs/ux-reference-library/03-review-workspace/` | Review Workspace | Scenario 1 review workspace | Explanatory banners overpower document data | High | Baseline Capture |
| `SCR-RW-04` | Rossum | `01_full_review_workspace_credit_note.png` | `docs/ux-reference-library/03-review-workspace/` | Review Workspace | Calibrated 50/50 split workspace | Perfect visual balance; document next to fields | High | Rossum EV-01 |
| `SCR-RW-05` | Rossum | `04_field_highlight_issue_date.png` | `docs/ux-reference-library/03-review-workspace/` | Review Workspace | Coordinate SVG bounding box | Visual trust: clicking field shows source box | High | Rossum EV-04 |
| `SCR-RW-06` | Rossum | `08_us_tax_invoice_full_workspace.png` | `docs/ux-reference-library/03-review-workspace/` | Review Workspace | Tax invoice multi-line grid | Clean right pane: Header -> Lines -> Total | High | Rossum EV-08 |
| `SCR-RW-07` | Rossum | `09_find_in_document.png` | `docs/ux-reference-library/03-review-workspace/` | Review Workspace | In-document text finder | Fast keyword search on scan canvas | High | Rossum EV-09 |
| `SCR-RW-08` | Flick AI | `01_invoice_builder_fields.png` | `docs/ux-reference-library/03-review-workspace/` | Review Workspace | Form fields & tax breakdown | Logical field grouping without clutter | High | Flick AI EV-01 |
| `SCR-RW-09` | Flick AI | `03_create_new_invoice_builder.png` | `docs/ux-reference-library/03-review-workspace/` | Review Workspace | Invoice builder layout | Clean separation of vendor & line data | High | Flick AI EV-03 |
| `SCR-RW-10` | FinBooks | `01_invoice_review_workspace.png` | `docs/ux-reference-library/03-review-workspace/` | Review Workspace | Popup modal invoice form | **Anti-Pattern:** Modal hides background | Low | FinBooks EV-01 |
| `SCR-RW-11` | FinBooks | `02_source_doc_viewer.png` | `docs/ux-reference-library/03-review-workspace/` | Review Workspace | Slide-out PDF drawer | **Anti-Pattern:** Decoupled from form editor | Low | FinBooks EV-02 |
| `SCR-RC-01` | AP Command Center | `procurement_flow_fixed.png` | `docs/ux-reference-library/04-reconciliation/` | Reconciliation | 4-node pipeline flow cards | Abstract nodes disconnected from lines | High | Baseline Capture |
| `SCR-RC-02` | AP Command Center | `05_line_item_inline_editing.png` | `docs/ux-reference-library/04-reconciliation/` | Reconciliation | Editable line-item table | Good inline editing; high cognitive density | High | UI Evidence #05 |
| `SCR-RC-03` | AP Command Center | `06_line_item_corrected_gate.png` | `docs/ux-reference-library/04-reconciliation/` | Reconciliation | Dynamic gate re-evaluation | Reactive status update upon row change | High | UI Evidence #06 |
| `SCR-RC-04` | Flick AI | `03_gst_compliance_reconciliation.png` | `docs/ux-reference-library/04-reconciliation/` | Reconciliation | Side-by-side reconciliation grid | Side-by-side comparative column matching | High | Flick AI EV-03 |
| `SCR-RC-05` | Flick AI | `04_invoice_builder_added_row.png` | `docs/ux-reference-library/04-reconciliation/` | Reconciliation | Dynamic line row addition | Frictionless row entry & auto subtotals | High | Flick AI EV-04 |
| `SCR-RC-06` | Flick AI | `01_bank_statements_upload_tab.png` | `docs/ux-reference-library/04-reconciliation/` | Reconciliation | Statement matching tab | Clean external reference matching | Medium | Flick AI EV-01 |
| `SCR-RC-07` | Rossum | `03_us_invoice_line_items_grid.png` | `docs/ux-reference-library/04-reconciliation/` | Reconciliation | Line items extraction table | Dense, readable tabular data alignment | High | Rossum EV-03 |
| `SCR-RC-08` | Rossum | `extensions_store.png` | `docs/ux-reference-library/04-reconciliation/` | Reconciliation | 3-way matching rules engine | Integration catalog for ERP matching | Medium | Rossum EV-Store |
| `SCR-RC-09` | FinBooks | `03_purchase_orders.png` | `docs/ux-reference-library/04-reconciliation/` | Reconciliation | Purchase orders master table | PO linking; missing visual 3-way line diff | Medium | FinBooks EV-03 |
| `SCR-RC-10` | FinBooks | `01_vendor_master.png` | `docs/ux-reference-library/04-reconciliation/` | Reconciliation | Vendor master repository | Vendor compliance & default terms | Medium | FinBooks EV-01 |
| `SCR-EX-01` | AP Command Center | `blocked_checks_tab.png` | `docs/ux-reference-library/05-exceptions/` | Exceptions | Blocked policy gates tab | Cascading false failures on bad scans | High | Baseline Capture |
| `SCR-EX-02` | AP Command Center | `blocked_no_override.png` | `docs/ux-reference-library/05-exceptions/` | Exceptions | Governance lock without CTA | Dead-end red badge; no guidance on next step | High | Baseline Capture |
| `SCR-EX-03` | AP Command Center | `reassign_modal.png` | `docs/ux-reference-library/05-exceptions/` | Exceptions | Task reassignment dialog | Functional but visually austere dialog | High | Baseline Capture |
| `SCR-EX-04` | Rossum | `01_missing_required_document_id.png` | `docs/ux-reference-library/05-exceptions/` | Exceptions | Validation error counter (`1 error`) | Clear badge indicating missing document ID | High | Rossum EV-01 |
| `SCR-EX-05` | Rossum | `02_document_id_focused_input.png` | `docs/ux-reference-library/05-exceptions/` | Exceptions | Auto-focused missing field | Clicking error badge jumps directly to field | High | Rossum EV-02 |
| `SCR-EX-06` | Rossum | `04_document_id_corrected_resolved.png` | `docs/ux-reference-library/05-exceptions/` | Exceptions | Real-time resolved state | Error turns to green checkmark instantly | High | Rossum EV-04 |
| `SCR-EX-07` | FinBooks | `01_exception_handling.png` | `docs/ux-reference-library/05-exceptions/` | Exceptions | Duplicate invoice card (`dupCard`) | Displays duplicate bill collision clearly | High | FinBooks EV-01 |
| `SCR-EX-08` | Flick AI | `01_validation_errors_highlighted.png` | `docs/ux-reference-library/05-exceptions/` | Exceptions | In-field validation tooltips | Human-readable validation error messages | High | Flick AI EV-01 |
| `SCR-EX-09` | Flick AI | `02_access_denied_exception.png` | `docs/ux-reference-library/05-exceptions/` | Exceptions | Permission exception banner | Clear boundary with administrator contact | Medium | Flick AI EV-02 |
| `SCR-AP-01` | AP Command Center | `approve_modal_standard.png` | `docs/ux-reference-library/06-approvals/` | Approvals | 600-word confirmation modal | Wall of legalistic text; high hesitation | High | Baseline Capture |
| `SCR-AP-02` | AP Command Center | `approvals_queue.png` | `docs/ux-reference-library/06-approvals/` | Approvals | Filtered approvals queue | Clear list, but lacks dual-control badges | High | Baseline Capture |
| `SCR-AP-03` | AP Command Center | `approved_state.png` | `docs/ux-reference-library/06-approvals/` | Approvals | Approved invoice review state | Clean stamp badge; clear sign-off stamp | High | Baseline Capture |
| `SCR-AP-04` | AP Command Center | `auditor_read_only.png` | `docs/ux-reference-library/06-approvals/` | Approvals | Auditor role view | Enforces read-only compliance cleanly | High | Baseline Capture |
| `SCR-AP-05` | Rossum | `03_confirm_blocked_modal.png` | `docs/ux-reference-library/06-approvals/` | Approvals | Lean confirmation warning dialog | 25 words: fast, unambiguous override | High | Rossum EV-03 |
| `SCR-AP-06` | Rossum | `users_and_roles.png` | `docs/ux-reference-library/06-approvals/` | Approvals | User role governance table | Clear hierarchy: reviewer vs supervisor | Medium | Rossum EV-Roles |
| `SCR-AP-07` | Flick AI | `11_team_management.png` | `docs/ux-reference-library/06-approvals/` | Approvals | Role-based permission matrix | Scannable Admin/Approver permissions | High | Flick AI EV-11 |
| `SCR-AP-08` | FinBooks | `bills_approval_badges.png` | `docs/ux-reference-library/06-approvals/` | Approvals | Bill workflow status badges | Simple Draft -> Approved status flow | Medium | FinBooks EV-Approve |
| `SCR-RP-01` | AP Command Center | `07_audit_trail_timeline_event.png` | `docs/ux-reference-library/07-reports-history/` | Reports & Audit | Chronological event timeline | Prominent SHA-256 strings confuse buyers | High | UI Evidence #07 |
| `SCR-RP-02` | AP Command Center | `audit_ledger.png` | `docs/ux-reference-library/07-reports-history/` | Reports & Audit | Formal audit ledger table | Robust audit record; technical jargon | High | Baseline Capture |
| `SCR-RP-03` | Flick AI | `02_ledger_management.png` | `docs/ux-reference-library/07-reports-history/` | Reports & Audit | Vendor AP ledger timeline | Human-first activity narrative | High | Flick AI EV-02 |
| `SCR-RP-04` | Flick AI | `01_financial_statements.png` | `docs/ux-reference-library/07-reports-history/` | Reports & Audit | Automated financial reports | Immediate P&L and balance sheet output | High | Flick AI EV-01 |
| `SCR-RP-05` | Flick AI | `03_balance_sheet_view.png` | `docs/ux-reference-library/07-reports-history/` | Reports & Audit | Balance sheet liability drill-down | Connects AP liabilities to balance sheet | Medium | Flick AI EV-03 |
| `SCR-RP-06` | Rossum | `statistics_reporting.png` | `docs/ux-reference-library/07-reports-history/` | Reports & Audit | Operational throughput analytics | Proves velocity and operator performance | High | Rossum EV-Stats |
| `SCR-RP-07` | FinBooks | `01_mis_reports.png` | `docs/ux-reference-library/07-reports-history/` | Reports & Audit | MIS executive reporting | Vendor spending breakdowns & aging | Medium | FinBooks EV-01 |
| `SCR-RP-08` | FinBooks | `07_accounting_ledger.png` | `docs/ux-reference-library/07-reports-history/` | Reports & Audit | Double-entry general ledger | Traditional voucher audit matching | Medium | FinBooks EV-07 |

---

## 3. Visual Comparison Analysis by Category (A–G)

Each category is evaluated against the **10 Non-Technical Buyer Evaluation Criteria**:
1. *Understood within 5 seconds?*
2. *Primary action immediately obvious?*
3. *Most important info visually dominant?*
4. *Appropriate information density?*
5. *Communicates business outcomes over technical processes?*
6. *Statuses & discrepancies understandable without jargon?*
7. *Minimizes unnecessary clicks?*
8. *Related pieces of information presented together?*
9. *Consistent visual hierarchy?*
10. *Inspires confidence in the financial decision?*

---

### Category A: Dashboard & Operational Overview

#### Competitor Benchmarks:
- **Flick AI (`SCR-DB-03`):** Presents exactly three prominent metric cards (*Needs Action: 4*, *Ready to Pay: 12*, *Disputed: 2*) and a prominent "Upload Invoice" button. The top header features a universal Fiscal Year and Month selector. Zero technical jargon is visible.
- **Rossum (`SCR-DB-05`):** Focuses on straight-through automation rate (e.g., 82%) and unassigned queue volume. High visual contrast between urgent queues and completed items.
- **FinBooks (`SCR-DB-06`):** Features sticky fiscal year selector (`FY 2024-25`) and vendor liability overview, but clutters the view with multiple banking and tax tabs.

#### Current AP Command Center Implementation (`SCR-DB-01`, `SCR-DB-02`):
- Displays 8 vertically stacked card widgets requiring 1,450px of vertical scrolling.
- Leaks developer test-runner controls ("Run Scenario 1–6", "Reset Demo Fixtures") directly above the operational cards.
- Presents raw financial risk numbers without clear categorization of *what needs action today* versus *what is already completed*.

#### Category A Scorecard & Evidence:
| Evaluation Criterion | Competitor Benchmark (Flick AI / Rossum) | AP Command Center (Current) | Visible Evidence Reference |
|---|---|---|---|
| 1. Understood in 5s | **5 / 5** (Flick AI: 3 clear cards) | **2 / 5** (8 stacked containers, dev banner) | `SCR-DB-03` vs `SCR-DB-01` |
| 2. Primary action obvious | **5 / 5** (Single "Upload" / "Review Next") | **2 / 5** (4 competing buttons across headers) | `SCR-DB-03` vs `SCR-DB-01` |
| 3. Info dominance | **5 / 5** (Large 32px metrics, clear labels) | **3 / 5** (Equal visual weight given to all 8 blocks) | `SCR-DB-03` vs `SCR-DB-02` |
| 4. Information density | **4 / 5** (Balanced, airy whitespace) | **2 / 5** (Dense, scrolling required) | `SCR-DB-03` vs `SCR-DB-01` |
| 5. Business outcomes | **5 / 5** (Pending payments, invoice counts) | **2 / 5** (Test scenario status, token health) | `SCR-DB-05` vs `SCR-DB-01` |
| 6. Jargon-free | **5 / 5** ("Needs Action", "Approved") | **2 / 5** ("EVAL_RUN", "FIXTURE_RESET") | `SCR-DB-03` vs `SCR-DB-01` |
| 7. Minimized clicks | **5 / 5** (1 click from KPI card to filtered list)| **3 / 5** (Requires manual navigation) | `SCR-DB-03` vs `SCR-DB-01` |
| 8. Related info grouped | **4 / 5** (Queue and action in single block) | **3 / 5** (Spread across 8 separate containers) | `SCR-DB-04` vs `SCR-DB-01` |
| 9. Visual hierarchy | **5 / 5** (Clean Material-UI typography) | **3 / 5** (Multiple competing header sizes) | `SCR-DB-03` vs `SCR-DB-01` |
| 10. Buyer confidence | **5 / 5** (Professional, calm, trustworthy) | **2 / 5** (Looks like an internal test harness) | `SCR-DB-03` vs `SCR-DB-01` |
| **Category Score** | **4.8 / 5.0 (PASS)** | **2.4 / 5.0 (NEEDS OVERHAUL)** | |

---

### Category B: Invoice Inbox & Document Intake Management

#### Competitor Benchmarks:
- **Flick AI (`SCR-IB-04`):** Replaces complex search filter forms with four pre-computed operational tabs: `[ Needs Action (4) ]`, `[ In Review (2) ]`, `[ Ready for Payment (12) ]`, `[ Completed (48) ]`. Workload is instantly apparent.
- **Rossum (`SCR-IB-06`):** Highlights real-time validation error counts directly in the table row (`To review (1 error)`). Hovering over the error badge exposes the exact reason (*"Missing PO reference"*).
- **FinBooks (`SCR-IB-10`):** Fast fiscal period scoping, but suffers from an intrusive batch-action bar that takes up vertical space even when no bills are selected.

#### Current AP Command Center Implementation (`SCR-IB-01`, `SCR-IB-02`):
- Monolithic 10-column table displaying internal database keys (`ID`, `UUID`, `SHA`).
- Status chips display internal engine constants: `DISCREPANCY_FLAGGED`, `MANUAL_REVIEW_REQUIRED`, `GATE_FAILED`.
- Multi-facet filter panel requires 4 clicks to filter by status and date range.

#### Category B Scorecard & Evidence:
| Evaluation Criterion | Competitor Benchmark (Flick AI / Rossum) | AP Command Center (Current) | Visible Evidence Reference |
|---|---|---|---|
| 1. Understood in 5s | **5 / 5** (Tabs tell user what to do) | **2 / 5** (Monolithic raw table) | `SCR-IB-04` vs `SCR-IB-01` |
| 2. Primary action obvious | **5 / 5** ("Review Invoice" on row hover) | **2 / 5** (3 buttons per row: View, Eval, Audit)| `SCR-IB-06` vs `SCR-IB-01` |
| 3. Info dominance | **5 / 5** (Vendor, Amount, Status badge) | **3 / 5** (Equal weight across 10 columns) | `SCR-IB-03` vs `SCR-IB-01` |
| 4. Information density | **4 / 5** (Optimal row height 56px) | **2 / 5** (Overcrowded columns, text clipping) | `SCR-IB-03` vs `SCR-IB-01` |
| 5. Business outcomes | **5 / 5** ("Ready for payment") | **2 / 5** ("EVAL_RUN_COMPLETED") | `SCR-IB-04` vs `SCR-IB-01` |
| 6. Jargon-free | **5 / 5** (Plain human labels) | **2 / 5** (Code enum constants) | `SCR-IB-04` vs `SCR-IB-01` |
| 7. Minimized clicks | **5 / 5** (1-click tab switching) | **2 / 5** (Multi-select dropdown filters) | `SCR-IB-04` vs `SCR-IB-02` |
| 8. Related info grouped | **4 / 5** (Vendor + Logo + PO # grouped) | **3 / 5** (Separated across far columns) | `SCR-IB-03` vs `SCR-IB-01` |
| 9. Visual hierarchy | **5 / 5** (Bold amounts, muted dates) | **3 / 5** (Uniform font sizes) | `SCR-IB-03` vs `SCR-IB-01` |
| 10. Buyer confidence | **5 / 5** (Scannable, enterprise-grade) | **2 / 5** (Database viewer aesthetic) | `SCR-IB-04` vs `SCR-IB-01` |
| **Category Score** | **4.8 / 5.0 (PASS)** | **2.3 / 5.0 (NEEDS OVERHAUL)** | |

---

### Category C: Invoice Review Workspace & Document Extraction

#### Competitor Benchmarks:
- **Rossum (`SCR-RW-04`, `SCR-RW-05`, `SCR-RW-06`):** The undisputed gold standard. Exact 50/50 split layout. The original document lives on the left with coordinate-addressed SVG bounding boxes (`rect`). Clicking any field on the right (e.g. *Issue Date* or *Line Item 2*) instantly pans and highlights the exact bounding box in neon amber on the PDF. Right pane is strictly structured: Header Card -> Line Items Grid -> Sticky Action Footer.
- **Flick AI (`SCR-RW-08`, `SCR-RW-09`):** Clean top-down hierarchy: Vendor Details -> Invoice Metadata -> Tabular Line Items -> Grand Total.
- **FinBooks (`SCR-RW-10`, `SCR-RW-11`):** **Critical Anti-Pattern:** FinBooks separates the source PDF into a slide-out drawer (`srcDocPanel`) while editing takes place in an overlay modal (`editForm`). The user cannot see both simultaneously without visual clipping.

#### Current AP Command Center Implementation (`SCR-RW-01`, `SCR-RW-02`, `SCR-RW-03`):
- Stacks four verbose explanation cards on the right: `VerdictBanner`, `CaseSummaryCard`, `PolicyChecksGrouped`, and `ProcurementVerificationFlow`.
- The user must scroll through ~450 words of explanatory text before they can see the invoice line items.
- The document viewer toolbar leaks cryptographic SHA-256 strings in the top title bar.

#### Category C Scorecard & Evidence:
| Evaluation Criterion | Competitor Benchmark (Rossum) | AP Command Center (Current) | Visible Evidence Reference |
|---|---|---|---|
| 1. Understood in 5s | **5 / 5** (Doc on left, data on right) | **2 / 5** (Drowned in 4 explanation cards) | `SCR-RW-04` vs `SCR-RW-01` |
| 2. Primary action obvious | **5 / 5** (Green "Confirm" in sticky footer) | **2 / 5** (Buried at bottom of 4 stacked cards) | `SCR-RW-04` vs `SCR-RW-01` |
| 3. Info dominance | **5 / 5** (Original PDF + Line table) | **2 / 5** (Abstract explanation banners dominate) | `SCR-RW-06` vs `SCR-RW-01` |
| 4. Information density | **5 / 5** (Zero wasted space; no scroll) | **1 / 5** (Extreme vertical scroll on right pane) | `SCR-RW-04` vs `SCR-RW-01` |
| 5. Business outcomes | **5 / 5** ("Approved" / "Discrepant Line") | **2 / 5** (Displays rule execution engine) | `SCR-RW-04` vs `SCR-RW-03` |
| 6. Jargon-free | **5 / 5** (Clear field names) | **2 / 5** ("TOLERANCE_0_PERCENT", "SHA-256") | `SCR-RW-06` vs `SCR-RW-02` |
| 7. Minimized clicks | **5 / 5** (Bounding box click auto-scrolls) | **3 / 5** (Requires multiple manual scrolls) | `SCR-RW-05` vs `SCR-RW-01` |
| 8. Related info grouped | **5 / 5** (Field tied to PDF box) | **2 / 5** (Matching status divorced from lines) | `SCR-RW-05` vs `SCR-RW-01` |
| 9. Visual hierarchy | **5 / 5** (Header -> Lines -> Totals) | **2 / 5** (Banners -> Policy -> Verification -> Table)| `SCR-RW-06` vs `SCR-RW-01` |
| 10. Buyer confidence | **5 / 5** (Visual proof via bounding box) | **2 / 5** (User questions why there's so much text) | `SCR-RW-05` vs `SCR-RW-01` |
| **Category Score** | **5.0 / 5.0 (GOLD STANDARD)** | **2.0 / 5.0 (NEEDS COMPLETE RESTRUCTURE)** | |

---

### Category D: Procurement Reconciliation (3-Way & 4-Way Matching)

#### Competitor Benchmarks:
- **Flick AI (`SCR-RC-04`):** Renders a direct comparative matrix: Billed vs Ordered vs Delivered vs Inspected. If a difference exists, an amber delta chip (`Δ -5 units`) appears directly between the columns. A non-technical person immediately grasps the shortage without reading policy manuals.
- **Rossum (`SCR-RC-07`):** High-density, aligned tabular grid with monospace figures, right-aligned currency, and automatic line-sum verification against invoice total.
- **FinBooks (`SCR-RC-09`):** **Anti-Pattern:** FinBooks lacks line-level 3-way matching in the bill review UI; it falls back to a browser `window.prompt` to enter PO numbers, completely concealing line quantity variances.

#### Current AP Command Center Implementation (`SCR-RC-01`, `SCR-RC-02`, `SCR-RC-03`):
- Features an abstract 4-node pipeline at the top (`Invoice Billed` -> `PO Ordered` -> `GRN Delivered` -> `Quality Inspected`).
- While functionally powerful, it separates the pipeline status from the actual line items below.
- Line-item table allows inline corrections (`SCR-RC-02`) and dynamic gate re-evaluation (`SCR-RC-03`), which is a great architectural strength, but the columns are crowded and display technical tolerance codes.

#### Category D Scorecard & Evidence:
| Evaluation Criterion | Competitor Benchmark (Flick AI / Rossum) | AP Command Center (Current) | Visible Evidence Reference |
|---|---|---|---|
| 1. Understood in 5s | **5 / 5** (Direct comparison table) | **3 / 5** (Abstract cards + separate table) | `SCR-RC-04` vs `SCR-RC-01` |
| 2. Primary action obvious | **4 / 5** ("Resolve Variance") | **3 / 5** ("Edit Row" / "Re-evaluate") | `SCR-RC-04` vs `SCR-RC-02` |
| 3. Info dominance | **5 / 5** (Discrepant line highlighted in red) | **3 / 5** (Pipeline nodes distract from lines) | `SCR-RC-04` vs `SCR-RC-01` |
| 4. Information density | **4 / 5** (Structured columns) | **3 / 5** (Table has 9 dense columns) | `SCR-RC-07` vs `SCR-RC-02` |
| 5. Business outcomes | **5 / 5** ("Billed 50, Warehouse got 45") | **3 / 5** ("QTY_TOLERANCE_EXCEEDED: 0.00%") | `SCR-RC-04` vs `SCR-RC-01` |
| 6. Jargon-free | **5 / 5** ("Missing 5 units") | **2 / 5** ("GATE_4_FAIL_STRICT_MATCH") | `SCR-RC-04` vs `SCR-RC-01` |
| 7. Minimized clicks | **4 / 5** (Inline edit or click discrepancy) | **4 / 5** (Inline editing is responsive) | `SCR-RC-04` vs `SCR-RC-02` |
| 8. Related info grouped | **5 / 5** (All 4 sources in single line row) | **2 / 5** (PO/GRN status in cards, line in table)| `SCR-RC-04` vs `SCR-RC-01` |
| 9. Visual hierarchy | **5 / 5** (Clear row borders & variance tags) | **3 / 5** (Too many competing visual badges) | `SCR-RC-04` vs `SCR-RC-02` |
| 10. Buyer confidence | **5 / 5** (Math & physical proof is obvious) | **3 / 5** (User must cross-reference two areas) | `SCR-RC-04` vs `SCR-RC-01` |
| **Category Score** | **4.7 / 5.0 (PASS)** | **2.8 / 5.0 (NEEDS RESTRUCTURING)** | |

---

### Category E: Exceptions, Discrepancies & Resolution Workflows

#### Competitor Benchmarks:
- **Rossum (`SCR-EX-04`, `SCR-EX-05`, `SCR-EX-06`):** When an extraction or validation error occurs, an error badge appears in the top header (`1 error`). Clicking it immediately scrolls and focuses the cursor into the exact missing field (`SCR-EX-05`). Once entered, the error badge turns into a green checkmark (`SCR-EX-06`), enabling the primary confirm button.
- **FinBooks (`SCR-EX-07`):** Displays a dedicated duplicate detection card (`dupCard`) showing the matching SHA hash and linking directly to the previously paid invoice (`INV-2024-089`).
- **Flick AI (`SCR-EX-08`):** Human-readable in-field validation tooltips (*"GSTIN format invalid: expected 15 alphanumeric characters"*).

#### Current AP Command Center Implementation (`SCR-EX-01`, `SCR-EX-02`, `SCR-EX-03`):
- **Cascading False Failures on Unreadable Scans:** When a scanned PDF is blurry or unreadable, the policy engine runs all 6 governance checks and fails every single one. The user sees 6 alarming red X's (missing PO, missing GRN, vendor unverified, tax mismatch) instead of one simple root cause: *"This invoice scan is unreadable."*
- **Dead-End Banners:** Displays `HARD_BLOCK: NO_OVERRIDE_PERMITTED` without giving the user a 1-click action to resolve it (e.g., *Reassign to Buyer*, *Request Credit Note*).

#### Category E Scorecard & Evidence:
| Evaluation Criterion | Competitor Benchmark (Rossum / FinBooks) | AP Command Center (Current) | Visible Evidence Reference |
|---|---|---|---|
| 1. Understood in 5s | **5 / 5** (Rossum: 1 clear error pill) | **2 / 5** (6 false red blocks on unreadable scan) | `SCR-EX-04` vs `SCR-EX-01` |
| 2. Primary action obvious | **5 / 5** (Click error pill to jump to fix) | **2 / 5** (Dead-end block banner with no CTA) | `SCR-EX-05` vs `SCR-EX-02` |
| 3. Info dominance | **5 / 5** (Error field highlighted in amber) | **3 / 5** (Screen flooded with red warning cards) | `SCR-EX-05` vs `SCR-EX-01` |
| 4. Information density | **4 / 5** (Concise error micro-copy) | **2 / 5** (Lengthy policy exception explanations) | `SCR-EX-08` vs `SCR-EX-01` |
| 5. Business outcomes | **5 / 5** ("Duplicate invoice detected") | **2 / 5** ("GATE_FAILURE_HASH_COLLISION") | `SCR-EX-07` vs `SCR-EX-01` |
| 6. Jargon-free | **5 / 5** ("Please enter Invoice Date") | **2 / 5** ("MUTATION_REJECTED_GOVERNANCE_LOCK") | `SCR-EX-04` vs `SCR-EX-02` |
| 7. Minimized clicks | **5 / 5** (1 click from error to focused field) | **2 / 5** (Manual search across tabs to find error)| `SCR-EX-05` vs `SCR-EX-01` |
| 8. Related info grouped | **4 / 5** (Error attached directly to input) | **2 / 5** (Error in top banner, input at bottom) | `SCR-EX-05` vs `SCR-EX-01` |
| 9. Visual hierarchy | **5 / 5** (Red border on field + top pill) | **3 / 5** (Repeated warning icons in every panel) | `SCR-EX-04` vs `SCR-EX-01` |
| 10. Buyer confidence | **5 / 5** (Clear path to resolution) | **2 / 5** (User panics seeing 6 simultaneous failures)| `SCR-EX-06` vs `SCR-EX-01` |
| **Category Score** | **4.8 / 5.0 (PASS)** | **2.2 / 5.0 (NEEDS OVERHAUL)** | |

---

### Category F: Approval Workflows & Governance Controls

#### Competitor Benchmarks:
- **Rossum (`SCR-AP-05`):** High decision velocity. For clean invoices, clicking `Confirm` takes exactly 1 click. If warnings exist, a concise 25-word confirmation alert confirms intent (*"There are 2 unverified fields. Do you want to confirm anyway?"*).
- **Flick AI (`SCR-AP-07`):** Clean role administration separating Approvers, Viewers, and Admins.
- **FinBooks (`SCR-AP-08`):** Color-coded status badges, but lacks strict dual-control authorization gates for large financial disbursements.

#### Current AP Command Center Implementation (`SCR-AP-01`, `SCR-AP-02`, `SCR-AP-03`, `SCR-AP-04`):
- **The 600-Word Approval Modal (`SCR-AP-01`):** Clicking "Approve" triggers an overwhelming dialog with 4 sections: "Governance Attestation", "Tolerance Summary", "Audit Note", and a yellow cautionary box.
- Non-technical managers hesitate and re-read the entire screen, slowing throughput.
- On the positive side, our backend governance invariants (anti-self-approval, Controller sign-off for $\ge ₹5,00,000$, and Auditor read-only 403) are rock-solid; the problem is purely the visual delivery.

#### Category F Scorecard & Evidence:
| Evaluation Criterion | Competitor Benchmark (Rossum) | AP Command Center (Current) | Visible Evidence Reference |
|---|---|---|---|
| 1. Understood in 5s | **5 / 5** (1-click confirm or 25-word alert) | **1 / 5** (600-word legalistic wall of text) | `SCR-AP-05` vs `SCR-AP-01` |
| 2. Primary action obvious | **5 / 5** (Green "Confirm [Space]" button) | **3 / 5** (Checkboxes must be checked to enable) | `SCR-AP-05` vs `SCR-AP-01` |
| 3. Info dominance | **5 / 5** (Amount & Vendor highlighted) | **2 / 5** (Lengthy policy declarations dominate) | `SCR-AP-05` vs `SCR-AP-01` |
| 4. Information density | **5 / 5** (Minimalist modal) | **1 / 5** (Overwhelming density; 600 words) | `SCR-AP-05` vs `SCR-AP-01` |
| 5. Business outcomes | **5 / 5** ("Approve ₹1,45,000 to Vendor") | **3 / 5** ("Certify compliance with Policy 4.2") | `SCR-AP-05` vs `SCR-AP-01` |
| 6. Jargon-free | **5 / 5** (Plain English) | **2 / 5** ("Dual-control cryptographic attestation")| `SCR-AP-05` vs `SCR-AP-01` |
| 7. Minimized clicks | **5 / 5** (1 click for clean invoices) | **2 / 5** (3 checkboxes + note + confirm click) | `SCR-AP-05` vs `SCR-AP-01` |
| 8. Related info grouped | **4 / 5** (Summary in dialog body) | **3 / 5** (Repeats review screen info redundantly) | `SCR-AP-05` vs `SCR-AP-01` |
| 9. Visual hierarchy | **5 / 5** (Dialog title -> text -> 2 buttons) | **2 / 5** (Nested accordions and warning boxes) | `SCR-AP-05` vs `SCR-AP-01` |
| 10. Buyer confidence | **5 / 5** (Fast, decisive, professional) | **3 / 5** (Inspires anxiety rather than confidence) | `SCR-AP-05` vs `SCR-AP-01` |
| **Category Score** | **4.9 / 5.0 (GOLD STANDARD)** | **2.2 / 5.0 (NEEDS STREAMLINING)** | |

---

### Category G: Reports, Audit Trails & Activity History

#### Competitor Benchmarks:
- **Flick AI (`SCR-RP-03`, `SCR-RP-04`):** Activity feeds written in natural human language: *"Rahul Sharma approved invoice INV-2024-001 (₹1,45,000)"* and *"Automated 3-way match passed against PO #PO-1029"*. Clean user avatars and time stamps.
- **Rossum (`SCR-RP-06`):** Proves executive ROI with velocity charts showing throughput per hour and error trends over 30 days.
- **FinBooks (`SCR-RP-07`, `SCR-RP-08`):** Traditional double-entry general ledger view with exportable Excel/PDF reports.

#### Current AP Command Center Implementation (`SCR-RP-01`, `SCR-RP-02`):
- Timeline displays raw cryptographic SHA-256 strings and system event names (`INVOICE_STATE_TRANSITION_EVAL_RUN`).
- The audit ledger (`SCR-RP-02`) resembles a raw database inspection grid rather than an executive audit trail.

#### Category G Scorecard & Evidence:
| Evaluation Criterion | Competitor Benchmark (Flick AI / Rossum) | AP Command Center (Current) | Visible Evidence Reference |
|---|---|---|---|
| 1. Understood in 5s | **5 / 5** (Human sentences: Who did what) | **2 / 5** (Raw hashes and technical event codes)| `SCR-RP-03` vs `SCR-RP-01` |
| 2. Primary action obvious | **4 / 5** ("Export Report" / "Filter User") | **3 / 5** ("Filter Events" / "Copy SHA") | `SCR-RP-04` vs `SCR-RP-02` |
| 3. Info dominance | **5 / 5** (Actor + Action + Amount) | **2 / 5** (SHA-256 strings dominate visually) | `SCR-RP-03` vs `SCR-RP-01` |
| 4. Information density | **4 / 5** (Balanced timeline feed) | **2 / 5** (Monolithic JSON payload inspection) | `SCR-RP-03` vs `SCR-RP-02` |
| 5. Business outcomes | **5 / 5** ("Audit completed for FY24") | **3 / 5** ("IMMUTABLE_LOG_VERIFIED") | `SCR-RP-04` vs `SCR-RP-01` |
| 6. Jargon-free | **5 / 5** (Zero technical enums) | **2 / 5** ("PAYLOAD_DIFF_HASH_MATCH") | `SCR-RP-03` vs `SCR-RP-01` |
| 7. Minimized clicks | **4 / 5** (Instant search and export) | **3 / 5** (Multi-click timeline expansion) | `SCR-RP-04` vs `SCR-RP-01` |
| 8. Related info grouped | **5 / 5** (Action + Actor avatar + Date) | **3 / 5** (Split into table columns) | `SCR-RP-03` vs `SCR-RP-02` |
| 9. Visual hierarchy | **5 / 5** (Clear timeline connector lines) | **3 / 5** (Flat row table layout) | `SCR-RP-03` vs `SCR-RP-02` |
| 10. Buyer confidence | **5 / 5** (Clear accountability for CFOs) | **3 / 5** (Feels like a backend logging tool) | `SCR-RP-03` vs `SCR-RP-01` |
| **Category Score** | **4.7 / 5.0 (PASS)** | **2.5 / 5.0 (NEEDS REFINEMENT)** | |

---

## 4. Overall Audit Summary Scorecard

```
+----------------------------------------------------------------------------------------------------+
| OVERALL BUYER UX AUDIT SCORECARD (1.0 to 5.0 Scale)                                                |
+------------------------------------------+---------------------+--------------------+--------------+
| Category                                 | AP Command Center   | Competitor Top Ref | Gap / Status |
+------------------------------------------+---------------------+--------------------+--------------+
| A. Dashboard & Overview                  | 2.4 / 5.0           | 4.8 / 5.0 (Flick)  | -2.4 (ALERT) |
| B. Invoice Inbox & Intake                | 2.3 / 5.0           | 4.8 / 5.0 (Flick)  | -2.5 (ALERT) |
| C. Invoice Review Workspace              | 2.0 / 5.0           | 5.0 / 5.0 (Rossum) | -3.0 (CRIT)  |
| D. Procurement Reconciliation            | 2.8 / 5.0           | 4.7 / 5.0 (Flick)  | -1.9 (WARN)  |
| E. Exceptions & Resolution               | 2.2 / 5.0           | 4.8 / 5.0 (Rossum) | -2.6 (ALERT) |
| F. Approval & Governance                 | 2.2 / 5.0           | 4.9 / 5.0 (Rossum) | -2.7 (ALERT) |
| G. Reports, Audit & History              | 2.5 / 5.0           | 4.7 / 5.0 (Flick)  | -2.2 (WARN)  |
+------------------------------------------+---------------------+--------------------+--------------+
| COMPOSITE SYSTEM SCORE                   | 2.34 / 5.0          | 4.81 / 5.0         | -2.47        |
+------------------------------------------+---------------------+--------------------+--------------+
```

---

## 5. Reusable UI Patterns to Adopt

### Pattern 1: True 50/50 Split Workspace with Dynamic Focus (from Rossum)
- **Visual Mechanism:** Left 48% holds the original PDF viewer; right 52% displays the structured review pane.
- **Problem Solved:** Solves the 1,200px vertical scroll in AP Command Center where line items are pushed off-screen.
- **How to Adapt:** Replace the 4 stacked cards (`VerdictBanner`, `CaseSummaryCard`, `PolicyChecksGrouped`, `ProcurementVerificationFlow`) with a 3-tier vertical hierarchy on the right: (1) Invoice Summary Bar (48px), (2) Consolidated 4-Way Line Table (dominant), (3) Sticky Action Footer (56px).

### Pattern 2: Pre-Filtered Operational Inbox Tabs (from Flick AI)
- **Visual Mechanism:** Horizontal pill tabs at the top of the inbox:
  `[ ⚠️ Needs Attention (4) ]  [ ⏱️ Ready for Approval (12) ]  [ ⏳ Waiting on Others (2) ]  [ ✅ Completed (48) ]`
- **Problem Solved:** Eliminates the cognitive burden of configuring multi-column SQL-style filters. Non-technical users immediately click the queue they own.
- **How to Adapt:** Map backend state filters directly into these four tabs on `/inbox`.

### Pattern 3: The 3-Card Daily Triad Dashboard (from Flick AI & Rossum)
- **Visual Mechanism:** Three prominent 32px metric tiles above the fold:
  1. *Needs Action Today* (Count + Value at Risk, Amber)
  2. *Ready to Pay* (Count + Total Approved Amount, Green)
  3. *Exceptions / Blocked* (Count + Disputed Amount, Red)
- **Problem Solved:** Replaces the 8 vertically stacked widgets on `/` that currently require scrolling through 1,450px of charts, health bars, and developer logs.

### Pattern 4: Consolidated 4-Way Reconciliation Table (Synthesis of Flick AI & AP CC)
- **Visual Mechanism:** Consolidates the four procurement verification stages directly into table columns:
  `[ Line Description | Billed (Inv) | Ordered (PO) | Delivered (GRN) | Inspected (QC) | Variance / Status | Actions ]`
- **Problem Solved:** Bridges the gap between the abstract 4-node pipeline cards and the line-item table. Non-technical users immediately see: *Supplier billed 50, but warehouse only received 45*.

### Pattern 5: Jump-to-Fix Exception Workflow (from Rossum)
- **Visual Mechanism:** A sticky pill in the workspace header: `⚠️ 1 Error`. Clicking the pill smoothly scrolls and places cursor focus on the exact cell or field that needs correction.
- **Problem Solved:** Stops users from hunting across long tabs to find why an invoice failed validation.

### Pattern 6: The 45-Word / 1-Click Lean Approval Dialog (from Rossum & Flick AI)
- **Visual Mechanism:** Clean modal dialog displaying exactly 3 lines of summary (Vendor, Total Amount, Match Status) and two buttons: `[Cancel]` and `[Approve & Authorize Payment]`.
- **Problem Solved:** Eliminates the current 600-word, 4-section legalistic modal while strictly preserving backend dual-approval and anti-self-approval enforcement.

### Pattern 7: Root-Cause Triage for Unreadable Scans
- **Visual Mechanism:** When document scan confidence is low, present a single root-cause triage banner: *"Scanned Document Unreadable: OCR could not extract text. [Upload Clearer Copy] or [Enter Details Manually]"*.
- **Problem Solved:** Prevents the policy engine from showing 6 false red gate failures (missing PO, missing GRN, tax mismatch) when the only real problem is a blurry image.

---

## 6. Anti-Patterns to Strictly Avoid (From Competitors & Our Baseline)

| Anti-Pattern | Source Where Observed | Negative UX Consequence | How We Will Avoid It |
|---|---|---|---|
| **Decoupled Modal over Drawer** | FinBooks (`SCR-RW-10`, `SCR-RW-11`) | Opening a bill form creates a modal that hides the background screen; opening the PDF opens a separate drawer that conflicts with the modal. | Strictly use a unified 50/50 side-by-side workspace without overlapping modals. |
| **Browser `window.prompt` for Linking** | FinBooks (`SCR-RC-09`) | Prompts user with native browser dialog to type PO number, concealing line items. | Implement integrated typeahead search and visual PO matching cards. |
| **Stacked Explanatory Card Fatigue** | AP Command Center (`SCR-RW-01`) | Stacking 4 explanatory banners vertically before displaying table data forces 1,200px scroll. | Collapse policy checks and status into a 48px sticky banner with an expandable drawer. |
| **600-Word Legalistic Approval Modal** | AP Command Center (`SCR-AP-01`) | Piles paragraphs of compliance attestation onto routine approvals, creating user hesitation. | Replace with a 45-word lean confirmation dialog; keep legal compliance in immutable audit logs. |
| **Cascading False Failures on Bad Scans**| AP Command Center (`SCR-EX-01`) | Blurry scans trigger 6 false red gate failures, panicking the user. | Implement root-cause triage that halts downstream gate checks when OCR extraction fails. |
| **Developer Controls in User Viewport** | AP Command Center (`SCR-DB-01`) | Exposing "Run Scenario 1–6" and "Reset Fixtures" makes software look like an unpolished test harness. | Quarantine all demo and evaluation controls into a hidden keyboard-triggered developer drawer. |
| **Cryptic Database Enums in Badges** | AP Command Center (`SCR-IB-01`) | Badges show `EVAL_RUN_COMPLETED` and `QTY_TOLERANCE_EXCEEDED: 0.00%`. | Translate all engine constants into human language: *"Qty Discrepancy: +5 units"*. |

---

## 7. Strategic Recommendations for UI Simplification

1. **Quarantine Developer Mode:** Immediately relocate the evaluation scenario runner ("Scenario 1–6") and demo reset triggers from the main app header and dashboard into a collapsible slide-over developer drawer (or trigger via `Ctrl+Shift+D`). The primary UI must look like a shipping commercial product.
2. **Execute the Review Workspace Restructure:** Rebuild `InvoiceReviewWorkspace.tsx` so the PDF viewer occupies the left 48% permanently, and the right 52% presents the Consolidated 4-Way Reconciliation Table above the fold.
3. **Streamline Approval Interactions:** Replace `ApproveDialog.tsx` with the 45-word lean dialog. Provide an unmistakable visual dual-approval stepper for invoices $\ge ₹5,00,000$.
4. **Clean the Inbox Navigation:** Replace complex multi-select filters on `/inbox` with the 4 pre-computed tabs (`Needs Attention`, `Ready for Approval`, `Waiting on Others`, `Completed`).
5. **Humanize the Audit Ledger:** Translate raw event payload diffs into human-readable sentences, moving raw SHA-256 hashes into a secondary "Copy Proof" click-to-expand chip.
