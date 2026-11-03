# Rossum vs Zamp AP Command Center — Evidence Register & Traceability Ledger

**Target Competitor:** Rossum Cloud Platform (`https://svit.rossum.app/`)  
**Our Product:** Zamp AP Command Center  
**Audit Standard:** REA Evidence Integrity Standard  
**Date:** November 03, 2026  

---

## 1. Rossum Reverse-Engineering Evidence Ledger

Every observation regarding Rossum is grounded in the empirical artifacts collected during REA Mission 02 (`competitor_research/02_rossum/`):

| Evidence ID | Category | Component / Route | Verification Method | Raw Artifact / Screenshot Reference | Verified Behavior & Notes |
|:---|:---|:---|:---|:---|:---|
| **R-EV-00** | Infrastructure | CDP Debugger & Login Portal | Native CDP HTTP Probe & Viewport Capture | `screenshots/navigation/00_login_page.png` | Google Chrome remote debugging on port 9222. Standalone REA MCP daemon unavailable; CDP/Playwright used as alternative. |
| **R-EV-01** | Queue Mgmt | Sidebar Queue Hierarchy | DOM Tree Dump & Telemetry Extraction | `screenshots/document_queues/01_queue_credit_notes.png` | 8 preconfigured queues (`Credit notes`, `Debit notes`, `Delivery notes`, `PO`, `Tax invoices EU/UK/US`). Total 23 sample docs. |
| **R-EV-02** | Queue Mgmt | Aggregated Queue View | Direct Navigation & DOM Row Extraction | `screenshots/document_queues/02_all_documents_queue.png` | Global unified queue displaying all 23 documents across organization with status filters (`Reviews`, `Postpone`, `All`). |
| **R-EV-03** | Filtering | Attribute Filter Popover | Interactive Click & MUI Popover Inspection | `screenshots/document_queues/03_queue_filter_menu.png` | Multi-condition filter builder with field selection and operators (`isAnyOf`, `equals`). |
| **R-EV-05** | Review UX | Split-Pane Review Workspace | 1920x1080 Viewport Capture & DOM Measurement | `screenshots/document_review/01_full_review_workspace_credit_note.png`, `02_review_workspace_1920x1080.png` | Calibrated 50/50 horizontal split between document canvas and structured extraction panel. |
| **R-EV-06** | Onboarding | Interactive Guidance Tour | Viewport Capture & Tour Modal Detection | `screenshots/other_features/01_onboarding_review_tour.png` | 3-step interactive onboarding walkthrough explaining viewer, extraction fields, and confirm action. |
| **R-EV-08** | Bounding Box | PDF Viewer SVG Highlighting: Issue Date | Field Click Telemetry & SVG `rect` Extraction | `screenshots/document_review/04_field_highlight_issue_date.png` | 51 discrete `<rect>` vector bounding boxes pre-rendered. Clicking `Issue Date` highlights `x="690" y="152"`. |
| **R-EV-09** | Bounding Box | PDF Viewer SVG Highlighting: Vendor Name | Field Click Telemetry & SVG Coordinate Inspection | `screenshots/document_review/05_field_highlight_vendor_name.png` | Clicking `Vendor Name` smoothly auto-scrolls canvas and highlights `x="189" y="295"`. |
| **R-EV-10** | Bounding Box | PDF Viewer SVG Highlighting: Amount Due | Field Click Telemetry & SVG Coordinate Inspection | `screenshots/document_review/06_field_highlight_amount_due.png` | Clicking `Amount Due` centers canvas on `x="935" y="247"`. |
| **R-EV-11** | Schema / Form | Extracted Form Sections | DOM Node Enumeration & Text Dump | `screenshots/document_review/08_us_tax_invoice_full_workspace.png` | Form sections: Basic Information, Totals and Subtotals, Vendor & Customer, Line Items. |
| **R-EV-12** | In-Doc Search | "Find in document" Text Search | Button Trigger & Search Bar Capture | `screenshots/document_review/09_find_in_document.png` | In-viewer search bar highlights matching OCR text blocks on canvas in yellow. |
| **R-EV-13** | Metadata | Document Info Flyout Panel | Button Click & Drawer DOM Telemetry | `screenshots/document_review/10_document_info_panel.png` | `DetailDrawer.tsx` displaying filename, import timestamp, source channel, format. |
| **R-EV-14** | Collaboration | Document Comments Side Drawer | Button Click & MUI Drawer Capture | `screenshots/document_review/11_document_comments_drawer.png` | Slide-out drawer for reviewer chat, notes, and tagging tied to document ID. |
| **R-EV-15** | Review Tools | Reviewer Toolbar Controls | Button Trigger & Settings Capture | `screenshots/document_review/12_sidebar_settings_modal.png` | Toolbar buttons: Zoom In/Out, Reset Zoom, Fit to Width/Height, Translation (`Ctrl+T`), Postpone, Reject, Move to Queue. |
| **R-EV-16** | Exceptions | Missing Required Field Flagging | DOM Error Class Extraction & Badge Telemetry | `screenshots/exceptions/01_missing_required_document_id.png` | Missing `Document ID` flagged with high-visibility red `?` badge; action bar displays `1 error / 0 warnings`. |
| **R-EV-17** | Correction | Floating Input Overlay (`editBoxInput`) | Field Click & Focus Trap Telemetry | `screenshots/exceptions/02_document_id_focused_input.png` | Dynamic floating textarea mounting adjacent to focused field capturing keyboard strokes instantly. |
| **R-EV-18** | Completion | Confirm Action & Quality Survey | Button Click & Survey Modal Interception | `screenshots/exceptions/03_confirm_blocked_or_modal.png` | Clicking Confirm triggers satisfaction survey ("How satisfied are you with data extraction?"). |
| **R-EV-19** | Correction | Human Resolution of Missing Field | Keyboard Typing & State Transition Capture | `screenshots/exceptions/04_document_id_corrected_resolved.png` | Entering value clears error, error counter decrements `1 → 0`, and Confirm button activates. |
| **R-EV-20** | Line Items | Multi-Row Line Items Expansion | Section Click & Table Extraction | `screenshots/extraction_and_validation/03_us_invoice_line_items_grid.png` | Line items grid extracting item description, quantity, unit rate, tax rate, and total (4 lines). |
| **R-EV-21** | Productivity | Reviewer Keyboard Shortcuts Sheet | Shift+Slash (`?`) Trigger & Keyboard Map Extraction | `screenshots/navigation/04_keyboard_shortcuts_modal.png`, `06_keyboard_shortcuts_sheet.png` | Keyboard map: Tab navigation, `Ctrl+Enter` confirm, `Ctrl+T` translate, `Ctrl+D` move queue, `Ctrl+Backspace` reject. |
| **R-EV-23** | Analytics | Operational Performance Dashboard | Direct Navigation & Chart Telemetry | `screenshots/dashboard/01_statistics_dashboard_full.png` | Executive `/statistics` dashboard tracking turnaround time (seconds), reviewer corrections per doc, SLA compliance. |
| **R-EV-25** | Intake | Drag-and-Drop Ingestion Dropzone | Upload Button Trigger & Modal Capture | `screenshots/workflow_actions/01_upload_modal.png` | Modal drag-and-drop file dropzone supporting batch file selection. |
| **R-EV-27** | Ecosystem | Rossum Store Integration Catalog | Direct Navigation & Card Parsing | `screenshots/other_features/03_extensions_rossum_store.png`, `06_store_catalog_grid.png` | Marketplace of 20+ enterprise connectors (SAP S/4HANA Suite, Coupa Master Data Import, Master Data Hub). |
| **R-EV-29** | Field Mgmt | Cross-Queue Field Manager System | Text Telemetry from Settings Overview | Documented in `ui_ux_analysis.md` | Administrative engine allowing AP directors to standardize schemas across queues. |

---

## 2. Zamp AP Command Center Source Code Ledger

Every claim regarding Zamp AP Command Center is grounded in actual inspected source code:

| Source File Path | Line Range | Architectural Component | Observed Implementation & Behavior |
|:---|:---|:---|:---|
| `backend/main.py` | L20–34, L78–90 | FastAPI App Shell & API v1 Routers | Mounts all 12 operational v1 routers under `/api/v1` and static frontend SPA fallback. |
| `backend/core/database.py` | L1–120 | Database Engine & RLS | PostgreSQL engine with Supabase Pooler connectivity and tenant session context isolation. |
| `backend/api/v1/auth.py` | L81–125 | Dev Session Token Provider | Generates authentic cryptographically signed JWTs for verified SME evaluation roles on loopback. |
| `backend/api/v1/dashboard.py` | L26–115 | Live Dashboard Metrics | Strictly computes metrics from live database queries; truthful representation with zero simulated activity. |
| `backend/api/v1/inbox.py` | L25–85 | Invoices Inbox Endpoint | Returns paginated invoice items with stage, decision, job status, and statutory deadline filters. |
| `backend/api/v1/invoices.py` | L41–180 | Invoice Detail API | Returns invoice, document, extracted fields, lines, supporting records, 7 match gates, timeline, and policy. |
| `backend/api/v1/invoices.py` | L272–360 | Action Execution API | Enforces operational justification reason, blocks approval on failing gates, logs append-only audit events. |
| `backend/api/v1/health.py` | L20–110 | Subsystem Health API | Verifies connectivity across database, object storage, identity provider, Gmail OAuth, and ERP. |
| `backend/models/domain.py` | L1–350 | Relational Domain Models | Enforces relations: Invoice, InvoiceLine, ExtractedField, MatchGateResult, ApprovalRequest, AuditEvent. |
| `frontend/src/App.tsx` | L1–120 | React App Root | Routes: `/today`, `/invoices`, `/invoices/:id`, `/approvals`, `/audit`, `/setup`, `/settings/*`. |
| `frontend/src/components/Sidebar.tsx` | L45–58, L190–205 | Navigation Rail | Displays numeric workload badges on `Invoices` (`invoiceCount`) and `Approvals` (`approvalCount`). |
| `frontend/src/pages/DashboardPage.tsx` | L205–287 | Dashboard Outcome Tiles | Needs Attention (Amber), Ready to Approve (Emerald), Waiting Second Approval (Purple). |
| `frontend/src/pages/DashboardPage.tsx` | L289–380 | Operational Readiness Checklist | 6-point live verification checklist checking tenant, team, mailbox, records, ingest, and decisions. |
| `frontend/src/pages/InboxPage.tsx` | L79–103 | Document Upload & Deduplication | Handles single file upload; returns 409 text notice on duplicate file without deep-linking to existing bill. |
| `frontend/src/pages/InvoiceDetailPage.tsx`| L687–817 | Left Pane Document Viewer | 50/50 split view; embeds PDF with zoom/pan, SHA-256 copy, 300s presigned URL refresh, and download. |
| `frontend/src/pages/InvoiceDetailPage.tsx`| L827–1060 | Right Pane Analysis Tabs | 4 tabs: Matching & Lines, Policy Checks, Extracted Information, Audit Trail. |
| `frontend/src/pages/InvoiceDetailPage.tsx`| L1063–1175 | Sticky Decision Bar | Consequence-aware action buttons; approval blocked when checks fail; dual approval enforcement. |
| `frontend/src/components/ProcurementVerificationFlow.tsx` | L100–350 | 4-Node 3-Way Match Grid | Nodes: 1. Billed Claim, 2. PO Contract, 3. GRN Receipt, 4. QC Inspection + Line-by-Line Match. |
| `frontend/src/components/PolicyChecksGrouped.tsx` | L1–200 | 7 Deterministic Policy Gates | Grouped by 3 business questions with explicit Pass/Fail reasons and required operational next actions. |
| `frontend/src/components/ConsequenceAwareActionModal.tsx` | L1–180 | Action Triage Dialog | Requires minimum 3-character justification; provides pre-drafted operational reason templates. |
| `frontend/src/hooks/useKeyboardShortcuts.ts` | L1–137 | Reviewer Keyboard Shortcuts | `?` for help, `/` for search, `g` sequences for navigation (`g t/i/a/u/s/c/r/m`), `Esc` to close. |

---

## 3. Live Runtime Observations & Captured Screenshot Register

Captured during live Playwright execution on `http://127.0.0.1:8000` (stored in [`competitor_research/04_cross_product_analysis/screenshots/`](file:///c:/Zamp%20Casse%20Study/competitor_research/04_cross_product_analysis/screenshots/)):

| Screenshot File | Timestamp | Route Tested | Verified Live Visual Evidence |
|:---|:---:|:---|:---|
| `01_auth_screen.png` | 19:50:28 | `/` | Instant Evaluation Access cards for SME AP Lead, Controller, Auditor, AP Associate; Supabase Google SSO. |
| `02_dashboard_today.png` | 19:50:32 | `/today` | Executive AP Paradigm card; 3 Outcome Tiles (Needs Attention: 2 / ₹25,960 blocked, Ready to Approve: 1, Waiting Second Approval: 0); 6-point Readiness Checklist; Velocity Strip; Next-Up Queue. |
| `03_invoices_inbox.png` | 19:50:35 | `/invoices` | Invoices table showing 8 records, status badges, stage filters (`All`, `Exceptions`, `Ready`, `Approved`, `Quarantine`), drag-and-drop upload zone, and Gmail sync button. |
| `04_invoice_detail_matching.png` | 19:50:39 | `/invoices/inv_dbfcaf77ba9b` | 50/50 Split Screen; original PDF preview on left with zoom toolbar; 4-node Procurement Verification Flow on right; Line-by-Line Match table showing rate variance (18.92%) and quantity match; Net Payable Waterfall. |
| `05_invoice_detail_checks.png` | 19:50:41 | `/invoices/inv_dbfcaf77ba9b` (Tab 2) | 7 Grouped Policy Checks showing 5 PASS, 2 FAIL (QC Inspection Accepted: FAIL, PO Price & Quantity Tolerance: FAIL); required next action explicitly displayed; verdict banner showing "Approval Blocked". |
| `06_invoice_detail_extracted.png` | 19:50:43 | `/invoices/inv_dbfcaf77ba9b` (Tab 3) | Extracted header fields table showing supplier name, GSTIN, invoice date, amounts, confidence scores (0.95–0.99) mapped to "Verified" badges, and source pages. Read-only. |
| `07_invoice_detail_history.png` | 19:50:44 | `/invoices/inv_dbfcaf77ba9b` (Tab 4) | Append-only audit trail displaying 3 chronological events: `INVOICE_INGESTED` by AP Associate, `HOLD_PENDING_EVIDENCE` by AP Lead (Unit rate variance), `HOLD_PENDING_EVIDENCE` (Awaiting GRN) with exact actor IDs and timestamps. |
| `08_action_modal_hold.png` | 19:50:46 | `/invoices/inv_dbfcaf77ba9b` (Modal) | ConsequenceAwareActionModal for "Hold for Evidence", displaying operational consequences, policy thresholds, reason templates, and mandatory justification textarea. |
| `09_approvals_queue.png` | 19:50:49 | `/approvals` | Operational Approvals queue with tabs: "Ready for AP Sign-Off (< ₹5,00,000)" and "Pending Second Approval (≥ ₹5,00,000 / Controller)", displaying clean match invoice `inv_d76401c096d0` (₹2,31,280.00). |
| `10_audit_page.png` | 19:50:52 | `/audit` | Organization-wide immutable audit ledger showing chronological events, actor IDs, roles, actions, and cryptographically verified timestamps. |
| `11_connections_storage.png` | 19:50:55 | `/settings/connections` | Storage and integration health status verifying Supabase Storage bucket `invoices`, Gmail OAuth credentials, and unconfigured SAP S/4HANA ERP status. |
| `12_procurement_records.png` | 19:50:58 | `/settings/reference-data` | Procurement reference tables showing purchase orders, goods receipt notes (GRN), and quality inspection (QC) records used for 3-way matching. |
| `13_setup_checklist.png` | 19:51:01 | `/setup` | Comprehensive 6-stage setup wizard verifying environment configuration, tenant onboarding, mailbox integration, reference data seeding, and test invoice processing. |

---

## 4. Traceability & Verification Guarantee

All empirical comparisons, interaction measurements, and architectural conclusions in this report are 100% cross-referenced against:
1. The Rossum live telemetry dumps and screenshots in `competitor_research/02_rossum/`.
2. The Zamp AP Command Center source code in `c:\Zamp Casse Study\backend\` and `frontend\`.
3. The live Playwright runtime session and screenshots in `competitor_research/04_cross_product_analysis/screenshots/`.
