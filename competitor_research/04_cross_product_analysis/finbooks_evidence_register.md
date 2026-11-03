# FinBooks vs Zamp AP Command Center — Evidence Register & Traceability Ledger

**Target Competitor:** FinBooks (`https://app.finbooks.ai/`)  
**Our Product:** Zamp AP Command Center  
**Audit Standard:** REA Evidence Integrity Standard  
**Date:** November 03, 2026  

---

## 1. FinBooks Reverse-Engineering Evidence Ledger

Every observation regarding FinBooks is grounded in the empirical artifacts collected during REA Mission 01 (`competitor_research/01_finbooks/`):

| Evidence ID | Category | Component / Route | Verification Method | Artifact / Screenshot Reference | Verified Behavior & Notes |
|:---|:---|:---|:---|:---|:---|
| **FB-EV-01** | App Shell | Navigation Sidebar | CDP DOM & Network Inspection | `screenshots/navigation/01_sidebar_initial.png`, `02_sidebar_expanded.png` | 5 groups (`MAIN`, `AI & REPORTS`, `COMPLIANCE`, `ACCOUNTING`, `INTEGRATIONS`). Zero workload badges on nav items. |
| **FB-EV-02** | Dashboard | Executive Dashboard | CDP DOM Dump & Screenshot | `screenshots/dashboard/01_dashboard_full.png`, `02_dashboard_bank_statement_view.png` | Executive greeting, horizontal carousel hiding KPIs, 3-item Needs Attention widget, Accrual vs Cash toggle. |
| **FB-EV-03** | Intake | Dropzone & Upload Modal | DOM Inspection & Script Decompilation | `screenshots/invoice_workflow/01_vendor_bills_workspace.png`, `02_upload_modal.png` | Multi-format file dropzone (`#dropZone`), "Split merged PDF per vendor" checkbox, sample CSV template link. |
| **FB-EV-04** | Deduplication | Exception Handling Card | Live Duplicate Ingestion & Notice Trigger | `screenshots/exceptions/01_exception_handling.png`, `rea_findings.md` §5.1 | `dupCard` component renders definition list (vendor, date, total) with direct link `<a class="btn-primary-g">View Invoice</a>` and "Upload Anyway" override. |
| **FB-EV-05** | Review UX | Sliding PDF Drawer | CDP JS Evaluation & Screenshot | `screenshots/review_and_validation/02_source_doc_viewer.png` | `srcDocPanel` 560px sliding right drawer using iframe with Adobe PDF query parameters `#navpanes=0&view=FitH`. Read-only. |
| **FB-EV-06** | Review UX | Centered Edit Modal | Form DOM Inspection & Field Capture | `screenshots/review_and_validation/01_invoice_review_workspace.png`, `rea_findings.md` §4.1 | Centered modal `editForm` with dark backdrop covering screen. Mutually exclusive with `srcDocPanel`. Line items completely dropped from form. |
| **FB-EV-07** | Extraction | Synthetic Ingestion | Ingestion of `synthetic_vendor_invoice.pdf` | `evidence_log.md` Section 3, `billing_extracted.json` | OCR extracted full line items into backend JSON array, but frontend edit modal dropped line items completely. |
| **FB-EV-08** | PO Match | Order Relinking | Script Decompilation (`voRelinkPrompt`) | `rea_findings.md` §5.2, `evidence_log.md` EV-010 | Unmatched PO triggers native browser `prompt('Sales order number...')`, forcing full-page reload on submit. |
| **FB-EV-09** | Bulk Actions| Bills Queue Table | DOM Checkbox & Floating Bar Audit | `screenshots/invoice_workflow/07_bills_list_after_upload.png`, `workflow_analysis.md` | Row checkboxes + "Select All" reveals floating sticky bottom bar with 1-click "Approve Selected" action. |
| **FB-EV-10** | Commercial | Pricing & Quota Modal | Live Razorpay & Quota Inspection | `screenshots/other_features/13_billing.png`, `billing_extracted.json` | Starter ₹499/mo (50 docs), Pro ₹1,499/mo (200 docs), Advance ₹4,999/mo (1000 docs). General Ledger and PO matching gated behind Pro. |
| **FB-EV-11** | Defect | Table Header Collision | Visual Inspection on <1400px Viewport | `screenshots/other_features/01_vendor_master.png`, `ui_ux_analysis.md` §4.3 | Fixed column widths cause column title `GSTIN / PAN` to collide directly into `EMAIL / PHONE`. |
| **FB-EV-12** | Defect | Webfont Network Hang | Headless Automation Telemetry | `rea_findings.md` §2.1, `investigation_state.md` §4 | Unresolved external webfont CDN requests prevent `document.fonts.ready` from resolving in automation runners. |

---

## 2. Zamp AP Command Center Source Code Ledger

Every claim regarding Zamp AP Command Center is grounded in actual inspected source code:

| Source File Path | Line Range | Architectural Component | Observed Implementation & Behavior |
|:---|:---|:---|:---|
| `backend/main.py` | L20–34, L78–90 | FastAPI App Shell & API v1 Routers | Mounts all 12 operational v1 routers under `/api/v1` and static frontend SPA fallback. |
| `backend/core/config.py` | L1–80 | Environment Settings | Enforces strict environment typing (`AppEnv.DEVELOPMENT`), secret keys, and timezone (`Asia/Kolkata`). |
| `backend/core/database.py` | L1–120 | Database Engine & RLS | PostgreSQL engine with Supabase Pooler connectivity and tenant session context isolation. |
| `backend/api/v1/auth.py` | L81–125 | Dev Session Token Provider | Generates authentic cryptographically signed JWTs for verified SME evaluation roles on loopback. |
| `backend/api/v1/dashboard.py` | L26–115 | Live Dashboard Metrics | Strictly computes metrics from live database queries; honest representation with zero simulated activity. |
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

---

## 3. Live Runtime Observations & Captured Screenshot Register

During this mission, Zamp AP Command Center was executed live against local server `http://127.0.0.1:8000` via Chrome DevTools Protocol / Playwright. All captured evidence is stored inside `competitor_research/04_cross_product_analysis/screenshots/`:

| Screenshot File | Timestamp | Route Tested | Verified Live Visual Evidence |
|:---|:---:|:---|:---|
| `01_auth_screen.png` | 19:50:28 | `/` | Instant Evaluation Access cards for SME AP Lead, Financial Controller, Auditor, AP Associate; Supabase Google SSO container. |
| `02_dashboard_today.png` | 19:50:32 | `/today` | Executive AP Paradigm card; 3 Outcome Tiles (Needs Attention: 2 exceptions / ₹25,960 blocked, Ready to Approve: 1, Waiting Second Approval: 0); 6-point Readiness Checklist; Pipeline Velocity Strip; Prioritized Next-Up Queue. |
| `03_invoices_inbox.png` | 19:50:35 | `/invoices` | Invoices table showing 8 records, status badges, stage filters (`All`, `Exceptions`, `Ready`, `Approved`, `Quarantine`), drag-and-drop upload zone, and Gmail sync button. |
| `04_invoice_detail_matching.png` | 19:50:39 | `/invoices/inv_dbfcaf77ba9b` | 50/50 Synchronized Split Screen; original PDF preview on left with zoom toolbar; 4-node Procurement Verification Flow on right; Line-by-Line Procurement Match table showing rate variance (18.92%) and quantity match; Net Payable Waterfall. |
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
1. The FinBooks live telemetry dumps and screenshots in `competitor_research/01_finbooks/`.
2. The Zamp AP Command Center source code in `c:\Zamp Casse Study\backend\` and `frontend\`.
3. The live Playwright runtime session and screenshots in `competitor_research/04_cross_product_analysis/screenshots/`.
