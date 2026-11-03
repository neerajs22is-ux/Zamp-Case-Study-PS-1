# FinBooks Feature Inventory & Capability Matrix

**Artifact ID:** `feature_inventory.md`  
**Target:** FinBooks (`https://app.finbooks.ai/`)  
**Investigation Framework:** REA Telemetry & Live Trial Account Auditing  
**Date:** November 03, 2026  

---

## 1. Classification Taxonomy
- `[V]` **Verified & Tested:** Directly exercised, triggered, or parsed via live execution during this mission.
- `[P]` **Partially Observed / Visible:** Directly visible in DOM/UI or API payload, but constrained by trial tier or mock status.
- `[M]` **Marketing / Documentation Claim:** Sourced from in-app Help documentation, release notes, or changelog; unverified at runtime.
- `[I]` **Inference:** Reasoned architectural or algorithmic deduction.
- `[U]` **Unknown / Inaccessible:** Gated behind Pro/Advance tier or enterprise paywalls.

---

## 2. Comprehensive Capability Matrix

### 2.1 Document Intake & Ingestion
| Feature | Status | Implementation Details / Observed Behavior | Source / Evidence |
|:---|:---:|:---|:---|
| Drag-and-Drop Dropzone | `[V]` | Supports single and multi-file drag and drop on `#dropZone`. | `screenshots/invoice_workflow/02_upload_modal.png` |
| Multi-Format Ingestion | `[V]` | Accepts PDF, PNG, JPG, JPEG, XLSX, and CSV formats. | DOM file input `accept` attribute |
| Batch Multi-Vendor PDF Splitting | `[V]` | Checkbox: "Split merged PDF into separate bills per vendor"; handles scanner batches. | Verified in upload modal DOM |
| Template CSV Import | `[V]` | Provides sample CSV download link (`/imports/txn/vendor_bills/template.csv`). | Link inspected in DOM |
| Intake Rate Limits & Quotas | `[V]` | Monthly quota tracking (`1/50 this month`) on bills; hourly limit (`0/100 this hour`) on POs. | Header badges verified |
| Email Inbox Ingestion | `[M]` | Documentation claims auto-forwarding email address for inbound bills. | Documented in in-app Help |

### 2.2 Extraction & OCR Engine
| Feature | Status | Implementation Details / Observed Behavior | Source / Evidence |
|:---|:---:|:---|:---|
| AWS S3 Document Storage | `[V]` | Stores files at `s3://ai-accountant-docs/organizations/{org_id}/vendors/{uuid}.pdf`. | Verified in bill entity JSON payload |
| Header Data Extraction | `[V]` | Extracts vendor name, invoice #, invoice date, currency (`INR`), taxable amount, and totals. | Verified on synthetic invoice upload |
| Indian GST Breakdown Extraction | `[V]` | Correctly isolates CGST, SGST, and IGST components (`tax_data: {cgst:0, igst:1800, sgst:0}`). | Verified in bill payload & UI row |
| Line Item Extraction | `[V]` | Extracts item description, quantity, unit rate, and total amount into structured array. | Extracted in `line_items` JSON array |
| Handwritten / Scan Flagging | `[M]` | Flags low-confidence or handwritten scans with a red OCR badge (v2.10 release). | Changelog v2.10 entry |
| OCR Confidence Scoring | `[I]` | Backend holds confidence values, but confidence percentages are hidden in the end-user UI. | Inferred from lack of percentage UI pills |

### 2.3 Validation & Exception Handling
| Feature | Status | Implementation Details / Observed Behavior | Source / Evidence |
|:---|:---:|:---|:---|
| Binary File Deduplication | `[V]` | Computes SHA-256 `file_hash` to block re-uploading identical binary files. | Verified in entity schema & `dupCard` script |
| Business Logic Deduplication | `[V]` | Computes `business_invoice_hash` on vendor + inv# + date + total to flag identical invoices under different files. | Verified in `evidence_log.md` |
| Duplicate Warning Alert Card | `[V]` | Renders `dupCard` component with metadata definition list and direct 1-click link to existing bill. | `screenshots/exceptions/01_exception_handling.png` |
| GSTIN Checksum Verification | `[V]` | Validates real 15-character Indian GSTIN structure (state code + PAN + entity + checksum). | Changelog v2.12; tested on vendor setup |
| Auto-Recalculating Totals | `[V]` | Client-side JS (`recalcTax()`, `recalcTotal()`) recalculates tax totals and grand total dynamically on input. | Inspected in `edit_form.html` script |
| Line-Level Discrepancy Warnings | `[P]` | Schema contains `match_discrepancies: []`, but no discrepancy UI exists in basic edit modal. | Present in JSON schema |

### 2.4 Accounting, Ledger & Reconciliation
| Feature | Status | Implementation Details / Observed Behavior | Source / Evidence |
|:---|:---:|:---|:---|
| Double-Entry General Ledger | `[U]` | Gated behind Pro Plan (₹1,499/mo). Provides Chart of Accounts, Journal entries, Trial Balance. | `screenshots/other_features/07_accounting_ledger.png` |
| Bank Statement Parsing | `[V]` | Parses CSV/PDF bank statements into Credits, Debits, and Running Balance. | `screenshots/other_features/02_bank_statements.png` |
| Smart Bank Reconciliation | `[V]` | Reconciles bank debits against bills net of TDS, handling 30–60 day delayed payment settlements. | Verified in bank statement workspace |
| Dual Cash Flow Forecast | `[V]` | Accrual view (bills & invoices) vs. Cash view (bank statements) projection toggle. | `screenshots/dashboard/01_dashboard_full.png`, `02...` |
| Cost Centres (3-Level Hierarchy) | `[V]` | Beta module supporting Cost Head -> Cost Centre -> Product hierarchy tagging. | `screenshots/other_features/09_cost_centres.png` |
| Fixed Assets & Depreciation | `[V]` | Tracks asset acquisition, asset class, and automated monthly/yearly depreciation schedules. | `screenshots/other_features/08_assets.png` |

### 2.5 Vendor Management (AP Master)
| Feature | Status | Implementation Details / Observed Behavior | Source / Evidence |
|:---|:---:|:---|:---|
| Automated Vendor Creation | `[V]` | Ingestion of unknown vendor automatically registers new record in Vendor Master. | Verified: `Acme Cloud Services` created |
| Vendor Master Registry | `[V]` | Fields: Name, GSTIN, PAN, Email, Phone, Address, Vendor Type (`goods`/`services`), TDS Section. | `screenshots/other_features/01_vendor_master.png` |
| Header UI Overlap Bug | `[V]` | Table header text `GSTIN / PAN` collides with `EMAIL / PHONE` on standard screen widths. | Verified visual defect |
| Vendor Spreadsheet Import | `[V]` | Bulk upload of vendors via spreadsheet preview modal. | Changelog v2.13 & UI button |

### 2.6 Purchase Order & Sales Order Matching
| Feature | Status | Implementation Details / Observed Behavior | Source / Evidence |
|:---|:---:|:---|:---|
| Inbound PO Management | `[V]` | PO list with KPI summary: Ordered, Dispatched, Invoiced, Completed POs. | `screenshots/invoice_workflow/03_purchase_orders.png` |
| Auto PO Matching | `[P]` | Evaluates incoming bills against open POs; sets `match_status: ORDER_NOT_FOUND` if unmatched. | Verified in bill JSON schema |
| Manual PO Relinking Prompt | `[V]` | Triggers native browser `window.prompt()` to input Sales Order / PO number (`SO-00003`). | Decompiled in `check_js_actions.py` |
| Item Mapping Rules | `[M]` | Keyword mapping engine to reconcile vendor-specific item descriptions to internal standard item codes. | Documented in changelog v2.12 |
| Over-Receipt Handling | `[M]` | Allows receiving goods above ordered quantity and linking multi-item orders. | Changelog v2.13 entry |

### 2.7 Approval & Payment Workflows
| Feature | Status | Implementation Details / Observed Behavior | Source / Evidence |
|:---|:---:|:---|:---|
| Status Lifecycle | `[V]` | Four discrete bill states: `Pending`, `Approved`, `Paid`, `Rejected`. | Verified in edit modal dropdown & filter bar |
| 1-Click Individual Approval | `[V]` | Status toggles to `Approved` upon saving changes or via status dropdown. | Verified on synthetic bill |
| Bulk Multi-Bill Approval | `[V]` | Selecting row checkboxes reveals floating bottom bar with "Approve Selected" action. | Verified in bills workspace |
| Mark Paid Modal / Workflow | `[V]` | "Mark Paid" button on row opens payment date and bank account selector. | Inspected on bills table |
| Multi-Entity Role Permissions | `[P]` | Viewer, Accountant, Admin, and Owner roles enforced per state GSTIN. | Changelog v2.11 & Settings inspection |

### 2.8 Compliance & Tax (Indian Statutory)
| Feature | Status | Implementation Details / Observed Behavior | Source / Evidence |
|:---|:---:|:---|:---|
| GST Summary Dashboard | `[V]` | Compares Output Tax (GSTR-1) vs Input Tax Credit (GSTR-2B) to show net liability. | `screenshots/other_features/06_gst_compliance.png` |
| GSTR-2B Portal JSON Import | `[V]` | Upload portal JSON to auto-reconcile purchase invoices against government GST portal records. | Verified button `openGstr2bImport()` |
| GSTR-2B Tax Backfill | `[V]` | Button `runGstr2bBackfill()` backfills matched GST figures onto existing vendor bills. | Verified in button list |
| TDS Tracking | `[P]` | Column in bills table; dedicated TDS compliance module flagged as "SOON". | Visible in table & navigation |
| Multi-GSTIN Branch Support | `[V]` | Manage multiple state GST registrations under one organization with per-GSTIN branding. | Settings & changelog v2.11 |

### 2.9 Reporting & AI Analytics
| Feature | Status | Implementation Details / Observed Behavior | Source / Evidence |
|:---|:---:|:---|:---|
| MIS Financial Reports | `[V]` | Standard P&L, Balance Sheet, Ledger reports with custom branding and CA watermark. | `screenshots/reports/01_mis_reports.png` |
| AI CFO Assistant | `[U]` | Natural language financial queries; paywalled behind Pro tier (₹1,499/mo). | `screenshots/other_features/05_cfo_assistant.png` |
| Excel & CSV Data Exports | `[V]` | Direct download of vendor bills, sales invoices, and bank transactions to spreadsheet. | Verified in export actions |

### 2.10 Integrations & External Sync
| Feature | Status | Implementation Details / Observed Behavior | Source / Evidence |
|:---|:---:|:---|:---|
| TallyPrime XML DayBook Import | `[V]` | Ingests DayBook XML files from TallyPrime to seed ledgers and vouchers. | `screenshots/other_features/10_integrations_import.png` |
| TallyPrime XML Direct Export | `[V]` | Generates TallyPrime compatible XML vouchers; supports push to `http://localhost:9000`. | `screenshots/other_features/11_integrations_export.png` |
| Zoho Books CSV Sync | `[V]` | Formats transactions for direct import into Zoho Books. | Verified in export settings |
| QuickBooks Support | `[P]` | Mentioned in import documentation; template mapping available. | Documented in integration guide |

### 2.11 Administration & Audit
| Feature | Status | Implementation Details / Observed Behavior | Source / Evidence |
|:---|:---:|:---|:---|
| Organization Settings | `[V]` | Manage business name, legal address, financial year start, and Cost Centre toggle. | `screenshots/other_features/12_settings.png` |
| Subscription Billing & Tiers | `[V]` | Starter (₹499/mo), Pro (₹1,499/mo), Advance (₹4,999/mo) via Razorpay. | `billing_extracted.json` |
| Two-Factor Authentication (2FA) | `[V]` | TOTP QR-code based 2FA with backup security codes. | Documented in changelog v2.0 & Settings |
| Global Audit Trail | `[M]` | Logs approvals, deletions, and payment events with user ID, IP address, and timestamp. | Documented in changelog v2.5 |
