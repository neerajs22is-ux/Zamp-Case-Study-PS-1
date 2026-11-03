# FinBooks vs Zamp AP Command Center — Comprehensive Feature Gap Matrix

**Target Competitor:** FinBooks (`https://app.finbooks.ai/`)  
**Our Product:** Zamp AP Command Center  
**Verification Standard:** REA Evidence Classification Standard  
**Date:** November 03, 2026  

---

## 1. Evidence Classification Taxonomy

Every capability in this matrix is strictly classified using the verification standard:
- `[V]` **Verified & Tested:** Directly exercised, triggered, or inspected via live runtime telemetry, DOM inspection, API response, or database query during this mission.
- `[P]` **Partially Implemented / Observed:** Visible in UI or API schema, but constrained by trial account limits, mock state, or partial frontend binding.
- `[M]` **Marketing / Documentation Claim:** Sourced from vendor documentation, help guides, or changelog; unverified at runtime.
- `[I]` **Inference:** Reasoned architectural or algorithmic deduction based on observed technical telemetry.
- `[U]` **Unknown / Inaccessible:** Gated behind commercial paywalls, missing live ERP endpoints, or inaccessible server logic.

---

## 2. Master Cross-Product Feature Matrix

### 2.1 Document Intake & Intake Channels

| Capability | FinBooks Status | FinBooks Observed Behavior | Zamp Status | Zamp Observed Behavior | Advantage / Gap |
|:---|:---:|:---|:---:|:---|:---|
| **Drag & Drop Dropzone** | `[V]` | Multi-file dropzone supporting PDF, PNG, JPG, XLSX, CSV (`#dropZone`). | `[V]` | Single-file dropzone and file-picker (`/invoices`) supporting PDF. | **FinBooks Advantage:** Multi-file drag and drop. |
| **Multi-Format Ingestion** | `[V]` | Ingests PDF, PNG, JPG, JPEG, XLSX, and CSV files natively. | `[P]` | Primarily handles PDF documents; images and CSV handled via backend conversion. | **FinBooks Advantage:** Native spreadsheet ingest. |
| **Batch Multi-Vendor PDF Splitting** | `[V]` | Checkbox: "Split merged PDF into separate bills per vendor"; automatically separates scanned batches. | `[U]` | Not implemented. Every PDF is treated as a single invoice entity. | **FinBooks Major Advantage:** Critical for corporate mailroom scanner batches. |
| **Downloadable CSV Template** | `[V]` | Provides sample CSV download link (`/imports/txn/vendor_bills/template.csv`). | `[U]` | Not implemented. | **FinBooks Advantage.** |
| **Email Inbox Ingestion** | `[M]` | Documentation claims auto-forwarding inbox address. | `[V]` | Production-grade Gmail OAuth 2.0 ingestion with encrypted credentials and webhook listener. | **Zamp Decisive Advantage:** Verified encrypted OAuth. |
| **Intake Quota & Limit Indicators** | `[V]` | Header pill: `AI Uploads: 1/50 this month`; hourly rate limits on POs. | `[P]` | Storage bucket quota not displayed in UI; system health shows storage readiness. | **FinBooks Advantage:** Visible user usage quota. |

### 2.2 OCR, Layout & Multimodal Extraction

| Capability | FinBooks Status | FinBooks Observed Behavior | Zamp Status | Zamp Observed Behavior | Advantage / Gap |
|:---|:---:|:---|:---:|:---|:---|
| **Header Data Extraction** | `[V]` | Extracts vendor name, invoice #, invoice date, currency (`INR`), taxable amount, and totals. | `[V]` | Extracts supplier name, GSTIN, invoice #, invoice date, currency (`INR`), taxable value, and totals. | **Tie.** Both extract standard header fields accurately. |
| **Indian GST Component Breakdown** | `[V]` | Isolates CGST, SGST, and IGST (`tax_data: {cgst:0, igst:1800, sgst:0}`). | `[V]` | Reconciles CGST, SGST, and IGST rates and amounts per line and header. | **Tie.** Both handle Indian dual GST structure. |
| **Line Item Extraction** | `[V]` | Extracts line items (description, quantity, unit rate, amount) into backend JSON array. | `[V]` | Extracts line items (line #, description, HSN/SAC, quantity, unit price, tax rates, line total). | **Tie in Extraction.** Zamp extracts HSN/SAC codes in addition. |
| **OCR Confidence Scoring** | `[I]` | Hidden in backend; no confidence percentages or pills in end-user UI. | `[V]` | Explicit confidence scores (0.00–1.00) mapped to "Verified" (≥0.90) or "Needs Review" (<0.90) badges. | **Zamp Major Advantage:** High confidence transparency. |
| **OCR Visual Bounding Boxes** | `[U]` | Not implemented. PDF drawer and data form are completely decoupled. | `[P]` | Schema supports `bounding_box: null`; frontend pan-to-coordinate not yet rendered. | **Tie (Both Lack Bounding Boxes).** |

### 2.3 Validation, Deduplication & Policy Gates

| Capability | FinBooks Status | FinBooks Observed Behavior | Zamp Status | Zamp Observed Behavior | Advantage / Gap |
|:---|:---:|:---|:---|:---:|:---|
| **Binary File Deduplication** | `[V]` | Computes SHA-256 `file_hash` to block identical binary file re-uploads. | `[V]` | Computes cryptographic SHA-256 hash on upload; blocks identical file uploads. | **Tie.** Both use SHA-256 binary hashing. |
| **Business Logic Deduplication** | `[V]` | Computes `business_invoice_hash` derived from `[vendor_id + invoice_# + date + total]`. | `[V]` | Gate 7 evaluates composite duplicate submission against previous vouchers. | **Tie.** Both enforce business duplicate checks. |
| **Duplicate Warning UX (`dupCard`)** | `[V]` | Renders dedicated `dupCard` component with metadata definition list and 1-click link to view existing bill. | `[P]` | Returns text error: `Duplicate detected: file.name has already been registered in the system.` | **FinBooks Decisive Advantage:** Zamp lacks deep link to existing invoice. |
| **Non-Blocking Duplicate Override** | `[V]` | "Continue / Upload Anyway" secondary button for legitimate recurring sequences. | `[U]` | Strictly barred by unique constraints. No override button. | **Trade-off.** FinBooks prioritizes user autonomy; Zamp prioritizes compliance integrity. |
| **Deterministic Policy Gates** | `[P]` | Coarse validation logic; checks are not separated into distinct audited gates. | `[V]` | 7 Explicit Deterministic Policy Gates grouped by 3 business questions with individual Pass/Fail logs. | **Zamp Decisive Advantage:** Fully transparent policy gate architecture. |
| **Commercial Price & Qty Tolerances**| `[I]` | Coarse or unconfigurable tolerances in backend. | `[V]` | Deterministic 0.00% quantity tolerance, ±1.50% unit price tolerance, and ₹20 rounding tolerance. | **Zamp Decisive Advantage:** Mathematically precise commercial controls. |
| **GSTIN Checksum Verification** | `[V]` | Stricter 15-char GSTIN checksum verification (state code + PAN + entity + checksum). | `[V]` | Gate 1 verifies supplier identity and valid GSTIN structure against supplier master. | **Tie.** Both validate Indian GSTIN format. |

### 2.4 Three-Way Matching & Procurement Verification

| Capability | FinBooks Status | FinBooks Observed Behavior | Zamp Status | Zamp Observed Behavior | Advantage / Gap |
|:---|:---:|:---|:---|:---:|:---|
| **Inbound PO Management** | `[V]` | Dedicated Inbound PO list with KPI summary (Ordered, Dispatched, Invoiced). | `[P]` | Procurement Records page displays evaluation PO snapshot tables. | **FinBooks Advantage:** Native PO CRUD management. |
| **3-Way Matching Scope** | `[P]` | 2-Way Match only (Bill to PO/SO). No native Goods Receipt (GRN) or Quality (QC) verification. | `[V]` | Full 4-Node 3-Way Match: Invoice Claim vs PO Contract vs GRN Receipt vs QC Inspection. | **Zamp Decisive Advantage:** Real enterprise 3-way matching. |
| **Automated PO Matching** | `[P]` | Matches bill to open PO; sets `match_status: ORDER_NOT_FOUND` if unlinked. | `[V]` | Matches bill PO reference against authoritative PO snapshots; evaluates price and quantity. | **Zamp Advantage:** Multi-node matching. |
| **Manual PO Relinking Prompt** | `[V]` | Native browser `window.prompt()` to input Sales Order / PO number (`SO-00003`). | `[U]` | Not implemented. If PO reference is unlinked, user cannot manually link it in UI. | **FinBooks Feature Advantage (Despite Clunky UX).** Zamp lacks relinking. |
| **Net Payable Waterfall** | `[I]` | Recomputes gross total via JS `recalcTotal()`. | `[V]` | Dedicated Net Payable Waterfall isolating billed base, reconciled tax, and authorizable net. | **Zamp Advantage:** Clear authorizable payout. |

### 2.5 Invoice Review Workspace & Editing

| Capability | FinBooks Status | FinBooks Observed Behavior | Zamp Status | Zamp Observed Behavior | Advantage / Gap |
|:---|:---:|:---|:---|:---:|:---|
| **Unified Split Screen** | `[U]` | Separated into 560px sliding right drawer (`srcDocPanel`) and centered modal (`editForm`). Mutually exclusive. | `[V]` | Integrated 50/50 Synchronized Split Screen: Document on left, analysis tabs on right. | **Zamp Decisive Advantage:** Eliminates modal context switching. |
| **Line-Item Grid Editing** | `[U]` | **Completely dropped from UI.** Review modal has zero line-item controls. | `[V]` | Authoritative Line-by-Line Match grid comparing Billed vs Contracted lines. *(Read-only in UI)*. | **Zamp Advantage:** Line items visible; neither allows cell editing. |
| **Header Field Editing** | `[V]` | Modal form with 14 editable input fields (invoice date, amounts, taxes). | `[U]` | Extracted fields table is 100% read-only in UI. | **FinBooks Advantage:** Allows fixing OCR misreads in UI. |
| **Workspace Layout Modes** | `[P]` | Drawer open or closed; pop-out new tab window. | `[V]` | Three layout modes: Split View (50/50), Expand Analysis (12-col), Document Focus. | **Zamp Advantage:** Flexible desktop density. |
| **Zero-Trust Document Security** | `[I]` | Static AWS S3 bucket URLs (`s3://ai-accountant-docs/...`). | `[V]` | Private Supabase Storage with dynamic 300s pre-signed URLs and refresh button. | **Zamp Major Advantage:** High document security. |

### 2.6 Exceptions, Triage & Governance Workflows

| Capability | FinBooks Status | FinBooks Observed Behavior | Zamp Status | Zamp Observed Behavior | Advantage / Gap |
|:---|:---:|:---|:---|:---:|:---|
| **Contextual Next Actions** | `[U]` | None. User must decide what to do on failed match. | `[V]` | Every failed gate explicitly provides required operational next action. | **Zamp Decisive Advantage:** Non-technical user guidance. |
| **Structured AP Triage Actions** | `[P]` | Only Edit, Delete, or Mark Paid. | `[V]` | 7 Consequence-Aware Actions: Hold for Evidence, Ask Supplier to Correct, Debit Note, Escalate, Quarantine, Reject, Approve. | **Zamp Decisive Advantage:** Models real enterprise AP operations. |
| **Mandatory Justification Reasons** | `[U]` | Not enforced. User can change status without justification. | `[V]` | Mandatory justification reason with built-in professional reason templates. | **Zamp Advantage:** Strict compliance accountability. |
| **Dual Approval Control (₹5,00,000)** | `[U]` | Single user can approve bills of any value. | `[V]` | Mandatory ₹5,00,000 threshold requiring secondary Financial Controller sign-off. Self-approval blocked. | **Zamp Decisive Advantage:** Fraud and embezzlement barrier. |
| **Role-Based Action Gating** | `[P]` | Roles exist per GSTIN, but basic approvals are open. | `[V]` | Strict RBAC: Auditor is strictly read-only; AP Lead approves < ₹5L; Controller approves ≥ ₹5L. | **Zamp Advantage:** Enterprise separation of duties. |
| **High-Volume Bulk Approval** | `[V]` | Checkbox row selection + sticky bottom bar to approve 20+ bills in 1 click. | `[U]` | Not implemented. Invoices must be reviewed and approved individually. | **FinBooks Decisive Advantage:** 100x faster for clean batches. |

### 2.7 Accounting, Ledgers & External Integrations

| Capability | FinBooks Status | FinBooks Observed Behavior | Zamp Status | Zamp Observed Behavior | Advantage / Gap |
|:---|:---:|:---|:---|:---|:---|
| **Double-Entry General Ledger** | `[U]` | Paywalled behind Pro Plan (₹1,499/mo). Chart of Accounts, Journal entries, Trial Balance. | `[U]` | Out of scope. Zamp is an AP verification engine, not an accounting suite. | **FinBooks Scope Advantage (for accounting).** |
| **Bank Statement Reconciliation** | `[V]` | Parses CSV/PDF statements; matches debits against bills net of TDS (30–60d window). | `[U]` | Out of scope. AP review is pre-payment verification, not cash clearance. | **FinBooks Scope Advantage.** |
| **TallyPrime XML DayBook Sync** | `[V]` | Generates Tally DayBook XML; supports direct push to `http://localhost:9000`. | `[U]` | Not implemented. | **FinBooks Major Advantage:** Universal Indian SME accounting format. |
| **Zoho Books CSV Export** | `[V]` | Formats transactions for direct Zoho Books import. | `[U]` | Not implemented. | **FinBooks Advantage.** |
| **GSTR-2B Portal Reconciliation** | `[V]` | Uploads government portal JSON to match Input Tax Credit (ITC) against vendor bills. | `[P]` | Gate 5 validates GST arithmetic, but does not connect to live GSTN portal. | **FinBooks Advantage:** Direct tax portal integration. |
| **MSMED Act Statutory Deadlines** | `[U]` | Standard bill due date only. | `[V]` | Calculates statutory MSMED §15 / §43B(h) 45-day payment deadlines for registered suppliers. | **Zamp Decisive Advantage:** Indian statutory compliance. |

### 2.8 Audit Trail, Traceability & System Health

| Capability | FinBooks Status | FinBooks Observed Behavior | Zamp Status | Zamp Observed Behavior | Advantage / Gap |
|:---|:---:|:---|:---|:---|:---|
| **Per-Invoice Audit Timeline** | `[U]` | Not available in UI. Bills table has no activity log drawer. | `[V]` | Embedded Tab 4 (`Audit Trail`) displays chronological activity ledger for every invoice. | **Zamp Decisive Advantage:** Instant proof of verification. |
| **Global Audit Trail** | `[M]` | Documented in `Settings -> Team / Audit`. | `[V]` | Dedicated `/audit` route displaying organization-wide immutable event ledger. | **Tie.** Both log global events. |
| **Subsystem Health Transparency** | `[U]` | Opaque. Subsystems surface only upon runtime failure. | `[V]` | Live `/api/v1/health` endpoint and dashboard checklist verifying DB, storage, IdP, Gmail, ERP. | **Zamp Decisive Advantage:** Truthful operational transparency. |
| **Guided Onboarding & Help** | `[V]` | Interactive drawer with 25+ guides and full changelog (v2.0–v2.13). | `[V]` | 6-Step Guided Coachmark Tour, AP Glossary Modal, and Case Summary Decision Guide. | **Tie.** FinBooks has broader guides; Zamp has better in-workflow tour. |
