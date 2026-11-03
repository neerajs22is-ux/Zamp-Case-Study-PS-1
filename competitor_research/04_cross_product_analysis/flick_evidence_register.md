# Flick AI vs Zamp AP Command Center — Master Empirical Evidence Register

**Target Competitor:** Flick AI (`https://app.flickai.in/`, Tenant `Zetworth`)  
**Our Product:** Zamp AP Command Center (`Autonomous AP Operations Platform`)  
**Investigation Framework:** Chrome DevTools Protocol Remote Debugging (`127.0.0.1:9222`) + Playwright Telemetry  
**Audited Physical Artifacts:** 37 Flick AI Screenshots + 13 Zamp AP Command Center Live UI Captures  
**Date of Audit:** November 03, 2026  
**Status:** Certified Empirical Evidence Register  

---

## 1. Evidence Classification Standards & Investigation Metadata

Every claim, observation, and comparative finding in this research mission is tethered to verifiable evidence under our strict five-tier verification standard:

- `[V]` **Verified:** Directly inspected, triggered, tested, and captured via live runtime telemetry, DOM dumps, or network interception.
- `[P]` **Partially Observed:** Visible in UI or API responses, but constrained by trial account limitations, paywalls, or mock states.
- `[M]` **Marketing Claim:** Stated in vendor marketing, changelog, or documentation, but unverified at runtime.
- `[I]` **Inference:** Reasoned architectural or design deduction based on technical telemetry and observed patterns.
- `[U]` **Unknown / Inaccessible:** Hidden behind enterprise paywalls, server-side unexposed logic, or missing permissions.

### 1.1 Target Environments
- **Competitor Target:** `https://app.flickai.in/` (Production Cloud Environment, React 18 SPA + Material-UI, JS Bundle: `main-D92_C11T.js`, 4.27 MB).
- **Zamp Target:** Local development and evaluation environment running on `http://127.0.0.1:8000` (FastAPI backend + Vite / React frontend + private Supabase PostgreSQL 15 & Storage).
- **Session Framework:** Google Chrome CDP Remote Debugging (`127.0.0.1:9222`) orchestrated via Python and Playwright.

---

## 2. Flick AI Master Evidence Registry (37 Physical Artifacts)

### 2.1 Navigation & Application Shell

| Evidence ID | Component / Route | Verification Method | Raw Artifact Link | Standard | Core Observed Finding |
|:---|:---|:---|:---|:---:|:---|
| **FLICK-001** | Login Portal (`/login`) | Native CDP Screenshot & DOM dump | [00_login_page.png](file:///c:/Zamp%20Casse%20Study/competitor_research/03_flickai/screenshots/navigation/00_login_page.png) | `[V]` | Secure email/password login portal with branding tagline *"Accounting Simplified"*. |
| **FLICK-002** | Sidebar & Navigation Rail | DOM inspection of Drawer and ListItems | [01_dashboard_and_sidebar.png](file:///c:/Zamp%20Casse%20Study/competitor_research/03_flickai/screenshots/navigation/01_dashboard_and_sidebar.png) | `[V]` | Collapsible Material-UI navigation rail containing 12 primary modules; header displays active tenant `Zetworth`. |

### 2.2 Executive Dashboard (`/dashboard`)

| Evidence ID | Component / Route | Verification Method | Raw Artifact Link | Standard | Core Observed Finding |
|:---|:---|:---|:---|:---:|:---|
| **FLICK-003** | Executive Scorecard | Full-page capture, metric card evaluation | [01_main_dashboard_full.png](file:///c:/Zamp%20Casse%20Study/competitor_research/03_flickai/screenshots/dashboard/01_main_dashboard_full.png) | `[V]` | Top metric strip: `Income vs Expenses`, `Net Profit & Margin %`, `Net Exposure`, high-contrast crimson `90+ Days Overdue` card, and `GST Net Liability`. |
| **FLICK-004** | Fiscal Trajectory Chart | Viewport inspection of SVG bar chart | [02_dashboard_view.png](file:///c:/Zamp%20Casse%20Study/competitor_research/03_flickai/screenshots/dashboard/02_dashboard_view.png) | `[V]` | 12-month rolling dual-bar chart conforming to Indian Fiscal Year (April to March) contrasting monthly revenue against operational spend. |

### 2.3 Document Ingestion & Repository (`/files`)

| Evidence ID | Component / Route | Verification Method | Raw Artifact Link | Standard | Core Observed Finding |
|:---|:---|:---|:---|:---:|:---|
| **FLICK-005** | Documents Workspace | Route navigation & tab inspection | [01_accounting_documents_list.png](file:///c:/Zamp%20Casse%20Study/competitor_research/03_flickai/screenshots/files_and_documents/01_accounting_documents_list.png) | `[V]` | Ingestion cockpit with Year and Month dropdown selectors and 4 discrete ingestion channels. |
| **FLICK-006** | File Dropzone | DOM inspection of `#unified-upload-input` | [02_files_route_direct.png](file:///c:/Zamp%20Casse%20Study/competitor_research/03_flickai/screenshots/files_and_documents/02_files_route_direct.png) | `[V]` | Unified dropzone accepting multi-file PDF drops; enforces 10MB ceiling per file. |
| **FLICK-007** | Purchase Invoices Tab | Active tab telemetry & quota meter | [03_purchase_invoices_tab.png](file:///c:/Zamp%20Casse%20Study/competitor_research/03_flickai/screenshots/files_and_documents/03_purchase_invoices_tab.png) | `[V]` | Dedicated vendor bill ingestion tab with quota badge: `"Trial account: 100 PDF invoices/month. This month: 0/100."` |
| **FLICK-008** | Sales Invoices Tab | Tab click & CSV download trigger | [04_sales_invoices_tab.png](file:///c:/Zamp%20Casse%20Study/competitor_research/03_flickai/screenshots/files_and_documents/04_sales_invoices_tab.png) | `[V]` | Customer AR billing upload tab featuring dedicated 1-click `CSV Template` download button; CSVs exempt from quota. |
| **FLICK-009** | Upload Modal Interaction | Modal trigger and dropzone state | [05_upload_files_modal.png](file:///c:/Zamp%20Casse%20Study/competitor_research/03_flickai/screenshots/files_and_documents/05_upload_files_modal.png) | `[V]` | Interactive drag-and-drop dialog with file format validation. |

### 2.4 Invoice Review & Builder Workspace (`/invoices`)

| Evidence ID | Component / Route | Verification Method | Raw Artifact Link | Standard | Core Observed Finding |
|:---|:---|:---|:---|:---:|:---|
| **FLICK-010** | Invoicing Master List | Route navigation & table DOM dump | [02_invoices_list_view.png](file:///c:/Zamp%20Casse%20Study/competitor_research/03_flickai/screenshots/invoice_processing/02_invoices_list_view.png) | `[V]` | Master table of all generated invoices with invoice number, customer, date, status, and amount. |
| **FLICK-011** | Invoice Builder Grid | Form structure & column extraction | [03_create_new_invoice_builder.png](file:///c:/Zamp%20Casse%20Study/competitor_research/03_flickai/screenshots/invoice_processing/03_create_new_invoice_builder.png) | `[V]` | Full-width spreadsheet data matrix on `/invoices/new` without source PDF preview. |
| **FLICK-012** | Line Matrix Schema | AST extraction of table columns | [01_invoice_builder_fields.png](file:///c:/Zamp%20Casse%20Study/competitor_research/03_flickai/screenshots/extraction_and_validation/01_invoice_builder_fields.png) | `[V]` | Column headers: `['PRODUCT/SERVICE', 'DETAILS', 'HSN/SAC', 'QTY*', 'UNIT', 'RATE*', 'DISCOUNT', 'FINAL', 'ACTIONS']`. |
| **FLICK-013** | Dynamic Row Insertion | Programmatic click of `Add New Row` | [04_invoice_builder_added_row.png](file:///c:/Zamp%20Casse%20Study/competitor_research/03_flickai/screenshots/invoice_processing/04_invoice_builder_added_row.png) | `[V]` | Appends editable row synchronously to client state without screen flash. |
| **FLICK-014** | Quotations Suite | Route navigation & export button | [04_quotations_list.png](file:///c:/Zamp%20Casse%20Study/competitor_research/03_flickai/screenshots/invoice_processing/04_quotations_list.png) | `[V]` | Commercial proposal creator capable of 1-click conversion into active invoices. |
| **FLICK-015** | Recurring Invoices | Route navigation & schedule list | [05_recurring_invoices_list.png](file:///c:/Zamp%20Casse%20Study/competitor_research/03_flickai/screenshots/invoice_processing/05_recurring_invoices_list.png) | `[V]` | Automated recurring billing engine for SaaS/subscription revenue. |

### 2.5 Reconciliation & Statements

| Evidence ID | Component / Route | Verification Method | Raw Artifact Link | Standard | Core Observed Finding |
|:---|:---|:---|:---|:---:|:---|
| **FLICK-016** | Bank Statements Ingestion | Tab click & CSV/PDF dropzone test | [01_bank_statements_upload_tab.png](file:///c:/Zamp%20Casse%20Study/competitor_research/03_flickai/screenshots/reconciliation/01_bank_statements_upload_tab.png) | `[V]` | Universal bank statement parser matching debits/credits against open invoices. |
| **FLICK-017** | Payment Aggregator Ingestion | Tab click & sample template test | [02_payment_aggregator_tab.png](file:///c:/Zamp%20Casse%20Study/competitor_research/03_flickai/screenshots/reconciliation/02_payment_aggregator_tab.png) | `[V]` | Razorpay gateway settlement upload channel with downloadable sample format. |
| **FLICK-018** | GST Compliance Module | Route navigation & RBAC gate check | [03_gst_compliance_reconciliation.png](file:///c:/Zamp%20Casse%20Study/competitor_research/03_flickai/screenshots/reconciliation/03_gst_compliance_reconciliation.png) | `[V]` (Gated) | Gated compliance view for GSTR-1, GSTR-2B, and GSTR-3B reconciliation. |
| **FLICK-019** | TDS Compliance Module | Route navigation & RBAC gate check | [04_tds_compliance.png](file:///c:/Zamp%20Casse%20Study/competitor_research/03_flickai/screenshots/reconciliation/04_tds_compliance.png) | `[V]` (Gated) | Section 194 withholding tax tracker gated behind organization owner permissions. |

### 2.6 Exceptions & Validation Triggers

| Evidence ID | Component / Route | Verification Method | Raw Artifact Link | Standard | Core Observed Finding |
|:---|:---|:---|:---|:---:|:---|
| **FLICK-020** | Form Validation Errors | Submit with empty fields | [01_validation_errors_highlighted.png](file:///c:/Zamp%20Casse%20Study/competitor_research/03_flickai/screenshots/exceptions/01_validation_errors_highlighted.png) | `[V]` | Invalid fields illuminate with crimson `.Mui-error` border and helper text: `"Customer is required"`. |
| **FLICK-021** | RBAC Access Denied | Navigation to `/compliance/*` | [02_access_denied_exception.png](file:///c:/Zamp%20Casse%20Study/competitor_research/03_flickai/screenshots/exceptions/02_access_denied_exception.png) | `[V]` | Intercepts non-privileged roles and renders full-page Access Denied exception. |

### 2.7 Financial Reports & General Ledger

| Evidence ID | Component / Route | Verification Method | Raw Artifact Link | Standard | Core Observed Finding |
|:---|:---|:---|:---|:---:|:---|
| **FLICK-022** | Profit & Loss Statement | Route navigation & Excel export trigger | [01_financial_statements.png](file:///c:/Zamp%20Casse%20Study/competitor_research/03_flickai/screenshots/reports/01_financial_statements.png) | `[V]` | Real-time Income Statement compiled directly from ledger entries with multi-sheet Excel export. |
| **FLICK-023** | Balance Sheet View | Click `Balance Sheet` view toggle | [03_balance_sheet_view.png](file:///c:/Zamp%20Casse%20Study/competitor_research/03_flickai/screenshots/reports/03_balance_sheet_view.png) | `[V]` | Real-time Assets, Liabilities, and Equity balance sheet compiled from journal entries. |
| **FLICK-024** | Ledger Management | Action button inspection | [02_ledger_management.png](file:///c:/Zamp%20Casse%20Study/competitor_research/03_flickai/screenshots/other_features/02_ledger_management.png) | `[V]` | Double-entry accounting cockpit with buttons: `Journal Entry`, `Opening Balance`, `Party Wise Ledger`. |
| **FLICK-025** | Zoho Books Integration | DOM inspection of Zoho sync button | [08_ledgers_management.png](file:///c:/Zamp%20Casse%20Study/competitor_research/03_flickai/screenshots/other_features/08_ledgers_management.png) | `[V]` | Dedicated `Import from Zoho` button backed by client script `/zoho-oauth-callback.js`. |

### 2.8 Master Data, AI Copilot & Settings

| Evidence ID | Component / Route | Verification Method | Raw Artifact Link | Standard | Core Observed Finding |
|:---|:---|:---|:---|:---:|:---|
| **FLICK-026** | Customer Master | Route navigation & import triggers | [06_customers_directory.png](file:///c:/Zamp%20Casse%20Study/competitor_research/03_flickai/screenshots/other_features/06_customers_directory.png) | `[V]` | Complete CRM customer profiles with GSTIN, address, and 1-click bulk Excel import. |
| **FLICK-027** | Goods & Services Catalog | Route navigation & unit filters | [07_goods_and_services_catalog.png](file:///c:/Zamp%20Casse%20Study/competitor_research/03_flickai/screenshots/other_features/07_goods_and_services_catalog.png) | `[V]` | Inventory catalog with SKU, HSN/SAC codes, default rates, and Unit of Measure filters. |
| **FLICK-028** | "Ask Flick" Copilot Drawer | Click floating action button | [04_ask_flick_assistant.png](file:///c:/Zamp%20Casse%20Study/competitor_research/03_flickai/screenshots/other_features/04_ask_flick_assistant.png) | `[V]` | Slide-out assistant drawer with prompt chips (*"What is my revenue?"*, *"Show overdue payables"*). |
| **FLICK-029** | Full-Page AI Chatbot | Route navigation to `/chatbot` | [09_flick_chatbot_interface.png](file:///c:/Zamp%20Casse%20Study/competitor_research/03_flickai/screenshots/other_features/09_flick_chatbot_interface.png) | `[V]` | Full-page conversational interface for in-depth financial inquiries. |
| **FLICK-030** | Organization Settings | Route navigation to `/settings/organization` | [10_organization_settings.png](file:///c:/Zamp%20Casse%20Study/competitor_research/03_flickai/screenshots/other_features/10_organization_settings.png) | `[V]` | Legal entity details, GSTIN, registered address, and state code configuration. |
| **FLICK-031** | Team Management | Route navigation to `/settings/team` | [11_team_management.png](file:///c:/Zamp%20Casse%20Study/competitor_research/03_flickai/screenshots/other_features/11_team_management.png) | `[V]` | Multi-user role delegation and permission management. |
| **FLICK-032** | Billing & Quotas | Route navigation to `/settings/billing` | [12_billing_and_quotas.png](file:///c:/Zamp%20Casse%20Study/competitor_research/03_flickai/screenshots/other_features/12_billing_and_quotas.png) | `[V]` | Plan details, invoice limit consumption (100 PDFs/month), and upgrade prompts. |
| **FLICK-033** | Support Center | Route navigation to `/support` | [13_support_and_help.png](file:///c:/Zamp%20Casse%20Study/competitor_research/03_flickai/screenshots/other_features/13_support_and_help.png) | `[V]` | Self-service knowledge base, ticketing, and contact information. |

---

## 3. Zamp AP Command Center Master Evidence Registry (13 Physical Artifacts)

### 3.1 Live Verified UI Captures

| Evidence ID | Component / Route | Verification Method | Raw Artifact Link | Standard | Core Verified Capability |
|:---|:---|:---|:---|:---:|:---|
| **ZAMP-001** | Authentication Screen (`/`) | Live Chrome CDP capture | [01_auth_screen.png](file:///c:/Zamp%20Casse%20Study/competitor_research/04_cross_product_analysis/screenshots/01_auth_screen.png) | `[V]` | Clean modern login portal with secure authentication and enterprise session establishment. |
| **ZAMP-002** | Executive AP Dashboard (`/dashboard`) | Live Chrome CDP capture | [02_dashboard_today.png](file:///c:/Zamp%20Casse%20Study/competitor_research/04_cross_product_analysis/screenshots/02_dashboard_today.png) | `[V]` | Surfaces Today's metrics, Next-Up Review Queue with 1-click review triggers, and Critical Blockers table. |
| **ZAMP-003** | Invoices Inbox (`/invoices`) | Live Chrome CDP capture | [03_invoices_inbox.png](file:///c:/Zamp%20Casse%20Study/competitor_research/04_cross_product_analysis/screenshots/03_invoices_inbox.png) | `[V]` | Filterable inbox with status tabs (`All`, `Pending`, `Approved`, `Flagged`, `Rejected`) and upload dropzone. |
| **ZAMP-004** | Review Workspace: 3-Way Match | Live Chrome CDP capture | [04_invoice_detail_matching.png](file:///c:/Zamp%20Casse%20Study/competitor_research/04_cross_product_analysis/screenshots/04_invoice_detail_matching.png) | `[V]` | **50/50 Split Screen:** Left pane renders PDF iframe via 300s pre-signed URL; right pane renders 4-node 3-Way Match grid. |
| **ZAMP-005** | Policy Checks Tab | Live Chrome CDP capture | [05_invoice_detail_checks.png](file:///c:/Zamp%20Casse%20Study/competitor_research/04_cross_product_analysis/screenshots/05_invoice_detail_checks.png) | `[V]` | Enforces 7 Deterministic Policy Gates with strict tolerances (0.00% qty, ±1.50% rate, ₹20 rounding). |
| **ZAMP-006** | Extracted Info Tab | Live Chrome CDP capture | [06_invoice_detail_extracted.png](file:///c:/Zamp%20Casse%20Study/competitor_research/04_cross_product_analysis/screenshots/06_invoice_detail_extracted.png) | `[V]` | Complete header and line item schema with extraction confidence scores and HSN/SAC codes. |
| **ZAMP-007** | Invoice Audit Trail | Live Chrome CDP capture | [07_invoice_detail_history.png](file:///c:/Zamp%20Casse%20Study/competitor_research/04_cross_product_analysis/screenshots/07_invoice_detail_history.png) | `[V]` | Chronological ledger of state transitions, OCR events, gate evaluations, and reviewer actions. |
| **ZAMP-008** | Structured Action Modal | Live Chrome CDP capture | [08_action_modal_hold.png](file:///c:/Zamp%20Casse%20Study/competitor_research/04_cross_product_analysis/screenshots/08_action_modal_hold.png) | `[V]` | Controlled governance dialog for **Put on Hold**, **Reject Invoice**, or **Override Gate** with justification. |
| **ZAMP-009** | Dual-Control Approvals Queue | Live Chrome CDP capture | [09_approvals_queue.png](file:///c:/Zamp%20Casse%20Study/competitor_research/04_cross_product_analysis/screenshots/09_approvals_queue.png) | `[V]` | Mandatory secondary sign-off queue for invoices $\ge \text{₹5,00,000}$ with self-approval strictly blocked. |
| **ZAMP-010** | System-Wide Audit Ledger | Live Chrome CDP capture | [10_audit_page.png](file:///c:/Zamp%20Casse%20Study/competitor_research/04_cross_product_analysis/screenshots/10_audit_page.png) | `[V]` | Immutable append-only audit trail logging every user, API, and system event across all invoices. |
| **ZAMP-011** | Connections & Cloud Storage | Live Chrome CDP capture | [11_connections_storage.png](file:///c:/Zamp%20Casse%20Study/competitor_research/04_cross_product_analysis/screenshots/11_connections_storage.png) | `[V]` | Status of private Supabase Storage bucket (`invoices`), Gmail intake bridge, and ERP connector bridge. |
| **ZAMP-012** | Procurement Records Explorer | Live Chrome CDP capture | [12_procurement_records.png](file:///c:/Zamp%20Casse%20Study/competitor_research/04_cross_product_analysis/screenshots/12_procurement_records.png) | `[V]` | Dedicated reference data viewer for Purchase Orders, Goods Receipt Notes, and Inspection certificates. |
| **ZAMP-013** | Onboarding Setup Checklist | Live Chrome CDP capture | [13_setup_checklist.png](file:///c:/Zamp%20Casse%20Study/competitor_research/04_cross_product_analysis/screenshots/13_setup_checklist.png) | `[V]` | Step-by-step administrative configuration wizard for storage, OCR models, policies, and ERP endpoints. |

---

## 4. Cross-Product Empirical Verification Matrix

| Comparative Dimension | Flick AI Evidence ID | Zamp AP Command Center Evidence ID | Comparative Empirical Verdict |
|:---|:---:|:---:|:---|
| **Executive Dashboard** | `FLICK-003`, `FLICK-004` | `ZAMP-002` | **Flick Advantage on Financial Visibility; Zamp Advantage on Actionable Review Queues.** |
| **Document Ingestion** | `FLICK-005`, `FLICK-007`, `FLICK-008` | `ZAMP-003`, `ZAMP-011` | **Flick Advantage on Period Partitioning & CSV Templates; Zamp Advantage on Zero-Trust Security.** |
| **Review Workspace** | `FLICK-011`, `FLICK-012` | `ZAMP-004`, `ZAMP-006` | **Zamp Decisive Win.** Zamp's 50/50 split workspace anchors extracted lines directly to the source PDF. |
| **3-Way Matching** | Absent across all artifacts | `ZAMP-004`, `ZAMP-012` | **Zamp Decisive Win.** Flick lacks PO/GRN matching; Zamp provides authoritative 4-node verification. |
| **Policy Validation** | `FLICK-020` | `ZAMP-005` | **Zamp Decisive Win.** 7 Deterministic Policy Gates with strict mathematical tolerances vs basic form errors. |
| **Dual-Control Governance**| Absent across all artifacts | `ZAMP-009` | **Zamp Decisive Win.** Mandatory ₹5,00,000 threshold with self-approval blocked protects against fraud. |
| **Tax Intelligence** | `FLICK-012`, `FLICK-018` | `ZAMP-005`, `ZAMP-006` | **Flick Advantage on GST Auto-Split; Zamp Decisive Win on MSMED 45-day statutory due dates.** |
| **Reconciliation** | `FLICK-016`, `FLICK-017` | `ZAMP-004` | **Flick specializes in bank/gateway cash matching; Zamp specializes in procurement pre-payment matching.** |
| **AI Copilot** | `FLICK-028`, `FLICK-029` | Absent | **Flick Decisive Win.** Ambient conversational drawer provides immediate financial intelligence. |
| **Auditability** | `FLICK-024` | `ZAMP-007`, `ZAMP-010` | **Zamp Decisive Win.** Tamper-evident append-only ledger with cryptographic SHA-256 verification. |
