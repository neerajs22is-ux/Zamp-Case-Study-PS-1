# Flick AI Reverse Engineering Evidence Log

**Target Application:** `https://app.flickai.in/login` (Flick AI - Accounting Simplified)  
**Investigation Framework:** Chrome CDP Native Remote Debugging (`127.0.0.1:9222`) + Playwright CDP Telemetry  
**Authenticated Organization:** `Zetworth`  
**Authenticated User:** `SUBRAMANIAN SHIVKUMAR SUBRAMANIAN INDIRA` (`NEERAJ2016YEAR@GMAIL.COM`)  
**Date of Audit:** November 03, 2026  

---

## 1. Evidence Classification Standard
Every claim and observation in this investigation is labeled according to the strict verification standard:
- `[V]` **Verified:** Directly inspected, triggered, tested, and captured via live runtime telemetry, DOM dumps, or network interception.
- `[P]` **Partially Observed:** Visible in UI or API responses, but constrained by trial account limitations, paywalls, or mock states.
- `[M]` **Marketing Claim:** Stated in vendor marketing, changelog, or documentation, but unverified at runtime.
- `[I]` **Inference:** Reasoned architectural or design deduction based on technical telemetry and observed patterns.
- `[U]` **Unknown / Inaccessible:** Hidden behind enterprise paywalls, server-side unexposed logic, or missing permissions.

---

## 2. Master Telemetry & Evidence Ledger

| Evidence ID | Category | Component / Route | Verification Method | Raw Artifact / Screenshot Reference | Standard |
|:---|:---|:---|:---|:---|:---:|
| **EV-001** | Navigation | Login Portal (`/login`) | Native CDP Screenshot & DOM inspection | [00_login_page.png](file:///c:/REA/competitor_research/03_flickai/screenshots/navigation/00_login_page.png) | `[V]` |
| **EV-002** | Dashboard | Financial Overview (`/dashboard`) | Full-page CDP capture, metric card evaluation | [01_main_dashboard_full.png](file:///c:/REA/competitor_research/03_flickai/screenshots/dashboard/01_main_dashboard_full.png) | `[V]` |
| **EV-003** | Navigation | Sidebar Menu Hierarchy | DOM inspection of Drawer and ListItem components | [01_dashboard_and_sidebar.png](file:///c:/REA/competitor_research/03_flickai/screenshots/navigation/01_dashboard_and_sidebar.png) | `[V]` |
| **EV-004** | Document Intake | Accounting Documents (`/files`) | Route navigation, tab inspection, period dropdowns | [01_accounting_documents_list.png](file:///c:/REA/competitor_research/03_flickai/screenshots/files_and_documents/01_accounting_documents_list.png) | `[V]` |
| **EV-005** | AP Ingestion | Purchase Invoices Tab | Active tab telemetry, trial quota extraction | [03_purchase_invoices_tab.png](file:///c:/REA/competitor_research/03_flickai/screenshots/files_and_documents/03_purchase_invoices_tab.png) | `[V]` |
| **EV-006** | AR Ingestion | Sales Invoices Tab | Tab click, CSV template download verification | [04_sales_invoices_tab.png](file:///c:/REA/competitor_research/03_flickai/screenshots/files_and_documents/04_sales_invoices_tab.png) | `[V]` |
| **EV-007** | Reconciliation | Bank Statements Tab | Tab click, CSV/PDF upload zone detection | [01_bank_statements_upload_tab.png](file:///c:/REA/competitor_research/03_flickai/screenshots/reconciliation/01_bank_statements_upload_tab.png) | `[V]` |
| **EV-008** | Reconciliation | Payment Aggregator Tab | Tab click, Razorpay sample template trigger | [02_payment_aggregator_tab.png](file:///c:/REA/competitor_research/03_flickai/screenshots/reconciliation/02_payment_aggregator_tab.png) | `[V]` |
| **EV-009** | Document Intake | Upload Dropzone & Input | Inspection of `#unified-upload-input` (.pdf, multiple) | [05_upload_files_modal.png](file:///c:/REA/competitor_research/03_flickai/screenshots/files_and_documents/05_upload_files_modal.png) | `[V]` |
| **EV-010** | Invoicing | Invoices Master List (`/invoices`) | Client-side route navigation and DOM dump | [02_invoices_list_view.png](file:///c:/REA/competitor_research/03_flickai/screenshots/invoice_processing/02_invoices_list_view.png) | `[V]` |
| **EV-011** | Invoicing | Invoice Creation Engine (`/invoices/new`) | Form structure and table column schema extraction | [03_create_new_invoice_builder.png](file:///c:/REA/competitor_research/03_flickai/screenshots/invoice_processing/03_create_new_invoice_builder.png) | `[V]` |
| **EV-012** | Invoicing | Dynamic Row Insertion | Programmatic click of `Add New Row` button | [04_invoice_builder_added_row.png](file:///c:/REA/competitor_research/03_flickai/screenshots/invoice_processing/04_invoice_builder_added_row.png) | `[V]` |
| **EV-013** | Validation | Form Error Triggers | Submit click with empty fields, inspection of `.Mui-error` | [01_validation_errors_highlighted.png](file:///c:/REA/competitor_research/03_flickai/screenshots/exceptions/01_validation_errors_highlighted.png) | `[V]` |
| **EV-014** | Invoicing | Quotations Management (`/quotations`) | Route navigation, Excel export and builder trigger | [04_quotations_list.png](file:///c:/REA/competitor_research/03_flickai/screenshots/invoice_processing/04_quotations_list.png) | `[V]` |
| **EV-015** | Invoicing | Recurring Invoices (`/recurring-invoices`) | Route navigation, schedule list inspection | [05_recurring_invoices_list.png](file:///c:/REA/competitor_research/03_flickai/screenshots/invoice_processing/05_recurring_invoices_list.png) | `[V]` |
| **EV-016** | Master Data | Customer Directory (`/customers`) | Route navigation, Bulk Import and Add Customer triggers | [06_customers_directory.png](file:///c:/REA/competitor_research/03_flickai/screenshots/other_features/06_customers_directory.png) | `[V]` |
| **EV-017** | Master Data | Goods & Services Catalog (`/goods-services`) | Route navigation, inventory list and unit filter | [07_goods_and_services_catalog.png](file:///c:/REA/competitor_research/03_flickai/screenshots/other_features/07_goods_and_services_catalog.png) | `[V]` |
| **EV-018** | Accounting | General Ledger (`/ledgers`) | Action buttons: Journal Entry, Opening Balance, Party Ledger | [02_ledger_management.png](file:///c:/REA/competitor_research/03_flickai/screenshots/other_features/02_ledger_management.png) | `[V]` |
| **EV-019** | Integration | Zoho Books Connector | Button: `Import from Zoho`, script `/zoho-oauth-callback.js` | [08_ledgers_management.png](file:///c:/REA/competitor_research/03_flickai/screenshots/other_features/08_ledgers_management.png) | `[V]` |
| **EV-020** | Reporting | Financial Statements (`/financial-statements`) | Route navigation, P&L view and Excel download | [01_financial_statements.png](file:///c:/REA/competitor_research/03_flickai/screenshots/reports/01_financial_statements.png) | `[V]` |
| **EV-021** | Reporting | Balance Sheet View | Click `Balance Sheet` toggle, capture equity/liabilities | [03_balance_sheet_view.png](file:///c:/REA/competitor_research/03_flickai/screenshots/reports/03_balance_sheet_view.png) | `[V]` |
| **EV-022** | Security / RBAC | GST Compliance Gate (`/compliance/gst`) | Route navigation, full page "Access Denied" trigger | [03_gst_compliance_reconciliation.png](file:///c:/REA/competitor_research/03_flickai/screenshots/reconciliation/03_gst_compliance_reconciliation.png) | `[V]` |
| **EV-023** | Security / RBAC | TDS Compliance Gate (`/compliance/tds`) | Route navigation, full page "Access Denied" trigger | [04_tds_compliance.png](file:///c:/REA/competitor_research/03_flickai/screenshots/reconciliation/04_tds_compliance.png) | `[V]` |
| **EV-024** | AI Copilot | Ask Flick Floating Assistant | Click floating button, inspect AI chat drawer & chips | [04_ask_flick_assistant.png](file:///c:/REA/competitor_research/03_flickai/screenshots/other_features/04_ask_flick_assistant.png) | `[V]` |
| **EV-025** | Organization | Organization Settings (`/settings/organization`) | Profile & Organization configuration inspection | [10_organization_settings.png](file:///c:/REA/competitor_research/03_flickai/screenshots/other_features/10_organization_settings.png) | `[V]` |
| **EV-026** | User RBAC | Team Management (`/settings/team`) | Team members list and role assignment options | [11_team_management.png](file:///c:/REA/competitor_research/03_flickai/screenshots/other_features/11_team_management.png) | `[V]` |
| **EV-027** | Quotas | Billing & Quotas (`/settings/billing`) | Trial account quota inspection (100 PDFs/month) | [12_billing_and_quotas.png](file:///c:/REA/competitor_research/03_flickai/screenshots/other_features/12_billing_and_quotas.png) | `[V]` |
| **EV-028** | Support | Support Center (`/support`) | Help center search and documentation review | [13_support_and_help.png](file:///c:/REA/competitor_research/03_flickai/screenshots/other_features/13_support_and_help.png) | `[V]` |
| **EV-029** | Architecture | Client Bundle AST & Route Graph | Reverse engineering of `main-D92_C11T.js` (4.27 MB) | `route_telemetry.json` | `[V]` |
| **EV-030** | Processing | Extraction States | Regex extraction of states: `PENDING`, `COMPLETED`, etc. | AST decompilation | `[V]` |
| **EV-031** | Automation | GST Portal Auto-Fetch | Marketing claims of automatic GSTR-2B sync | Vendor documentation | `[M]` |
| **EV-032** | AI / Vision | Deep Learning OCR Architecture | Inference of cloud-based multimodal transformer | Architecture telemetry | `[I]` |
| **EV-033** | Backend | Server-Side Matching Algorithms | Private backend matching rules between invoices & bank lines | Server-side execution | `[U]` |

---

## 3. Session Diagnostics
- Remote Debugging Endpoint: `http://127.0.0.1:9222/json`
- Target URL: `https://app.flickai.in/`
- Tooling verification: Native Chrome DevTools Protocol + Playwright CDP session.
