# AP Command Center — Product Capability Truth & Operational Boundaries

> **Status:** Authoritative Product Truth Reference  
> **Evaluation Environment:** Supabase Cloud PostgreSQL + Hybrid Python/TypeScript AP Engine  
> **Primary Audience:** Product Managers, Engineering, Demo Presenters, Evaluators  
> **Last Verified:** November 2026 (Phase 0 Verification Pass)

---

## Executive Overview

This document establishes the verified, factual baseline of the **Accounts Payable (AP) Command Center**. Every statement in this document is derived directly from inspected source code, database schemas, active API endpoints, and executed integration tests.

Its purpose is to eliminate discrepancies between documentation, user interface claims, and actual backend execution. When demonstrating, pitching, or extending the application, **no capability may be claimed unless it appears in Section A or Section E as verified**.

---

## Section A: What the System Actually Does (Verified Capabilities)

The AP Command Center is an intelligent pre-accounting validation and human exception-triage workbench for Indian enterprise Accounts Payable. It sits between document intake and ERP financial liability creation.

### 1. Document Ingestion
- **Manual PDF Intake (`POST /api/v1/documents/upload`):**
  - Accepts single or multi-page digital PDF files up to 50 MB.
  - Verifies PDF magic bytes (`%PDF-`) at header offset 0; immediately rejects non-PDFs or corrupted files with HTTP 400.
  - Computes SHA-256 byte hash and checks for identical documents in the current organisation partition. Rejects duplicate file submissions with HTTP 409 (`DUPLICATE_DETECTED`).
  - Persists valid documents to Supabase Object Storage under tenant-partitioned keys (`org_{org_id}/invoices/{doc_id}/{filename}`).
  - Creates database records in `documents`, `invoices` (initial stage: `RECEIVED`, decision: `NEEDS_REVIEW`), `ingestion_jobs` (status: `QUEUED`), and `audit_events` (`DOCUMENT_UPLOADED`).
  - Automatically claims the job and triggers background pipeline processing via FastAPI `BackgroundTasks` when `ENABLE_BACKGROUND_PIPELINE=true`.
- **Compensating Rollback:** If the database transaction fails after object upload, the storage adapter automatically deletes the orphaned file from object storage to prevent data leakage.

### 2. Document Extraction & Text Processing
- **Deterministic Extraction Fallback (`HybridAPExtractor.extract_deterministic`):**
  - Extracts text per page using `pypdf`, preserving page numbers.
  - Uses regex patterns to identify Indian PAN, GSTIN, invoice numbers, invoice dates, PO references, and line-item tables.
  - Scans full text for raster-only or degraded images (< 20 characters of extractable text); routes unscannable documents to `FLAGGED_HITL_REVIEW` (`SCANNED_IMAGE`).
- **AWS Bedrock Mantle Integration (`HybridAPExtractor.extract_hybrid`):**
  - Client implemented for AWS Bedrock Mantle running Qwen 235B (`qwen.qwen3-235b-a22b-2507-v1:0`).
  - Extracts structured invoice data: supplier name, supplier GSTIN, invoice number, date, PO reference, currency, line items, and tax breakdown.
  - Fails closed: if Mantle credentials are missing or API fails, throws `RuntimeError` rather than silently fabricating mock results.
- **Evidence Grounding Tripwires (`verify_extracted_evidence`):**
  - Cross-references every extracted field value against literal document page text.
  - If an extracted attribute cannot be located in the source text, marks the field as unverified and trips the grounding wire (`grounding_tripwire_passed = False`), forcing the invoice into `FLAGGED_HITL_REVIEW`.

### 3. Indian AP Rule Engine & Tax Arithmetic (`IndianAPRuleEngine`)
- **GST Mathematical Verification:**
  - Verifies that `taxable_value + (cgst + sgst + igst) == grand_total` within a strict ₹1.00 rounding tolerance.
  - Reconciles individual line-item tax rates against the invoice header tax totals.
- **GST State-Split Logic:**
  - Extracts the 2-digit state code from supplier GSTIN (e.g., `27` for Maharashtra, `29` for Karnataka) and recipient GSTIN.
  - Enforces that intra-state transactions (`supplier_state == recipient_state`) charge CGST + SGST in equal 50/50 splits.
  - Enforces that inter-state transactions (`supplier_state != recipient_state`) charge IGST only. Flags mixed or conflicting splits.
- **Statutory MSMED Compliance Calculation:**
  - Calculates statutory payment deadlines for registered Micro, Small, and Medium Enterprises (MSMED Act Section 15): 45 days from delivery/acceptance.
  - Monitors deadline proximity and flags invoices approaching statutory interest exposure (Section 16 compounding interest at 3x RBI bank rate).

### 4. 3-Way Reference Matching (`verify_three_way_match`)
- **Purchase Order (PO) Authorization:**
  - Queries `work_order_snapshots` for matching PO number within the tenant partition.
  - Validates vendor code alignment, active PO status (`APPROVED`), and remaining unbilled balance.
- **Goods Receipt Note (GRN) Confirmation:**
  - Matches billed lines against recorded warehouse receipts in `goods_receipt_snapshots`.
  - Verifies quantity delivered matches or exceeds billed line quantities (zero quantity overrun permitted: `0.00%` quantity tolerance).
- **Quality Inspection (QC) Acceptance:**
  - Checks `quality_control_snapshots` for inspection acceptance on received lots.
  - Flags invoices if goods are on QC hold, rejected, or pending inspection.
- **Price Variance Tolerance:**
  - Compares billed unit rates against contracted PO rates.
  - Enforces a strict **±1.50%** price tolerance limit (`RATE_TOLERANCE_PERCENT = 1.50`). Unit prices exceeding the contracted rate by > 1.50% fail Gate 6 and block approval.

### 5. Deterministic Validation Gates (Gates 1 through 7)
The pipeline computes seven explicit gate checks for every evaluated invoice, persisting individual results into `match_gate_checks`:
1. **Gate 1 — Vendor Identity Registered:** Validates supplier GSTIN format and presence in approved vendor master.
2. **Gate 2 — PO Authorization Valid:** Verifies authoritative PO reference exists, is approved, and has remaining balance.
3. **Gate 3 — GRN Receipt Confirmed:** Confirms matching goods receipt record in warehouse receipts.
4. **Gate 4 — QC Inspection Accepted:** Confirms formal quality acceptance of received inventory.
5. **Gate 5 — GST Arithmetic Reconciled:** Validates line-item math and header tax reconciliation within ₹1 tolerance.
6. **Gate 6 — PO Price & Quantity Tolerance:** Enforces 0.00% quantity overrun and contracted rate adherence within ±1.50%.
7. **Gate 7 — Duplicate Invoice Check:** Confirms no prior voucher exists with identical vendor, invoice number, and fiscal year.

### 6. Human Exception Triage & Review Actions
- When all 7 gates pass, the invoice reaches `PENDING_APPROVAL` (`MATCH_CANDIDATE`).
- When one or more gates fail, the invoice reaches `ACTION_REQUIRED` (`FLAGGED_EXCEPTION` or `FLAGGED_HITL_REVIEW`).
- Human AP operators can execute authorized triage actions: `HOLD_PENDING_EVIDENCE`, `REQUEST_SUPPLIER_CORRECTION`, `RAISE_DEBIT_NOTE`, `ESCALATE`, `REJECT_INVOICE`, or `QUARANTINE`.
- Every action requires a minimum 3-character operational justification, mutates state atomically, and writes an immutable audit record.
- **Failed-Gate Override Block (D-04 Deferred):** The backend and frontend strictly reject approval of any invoice with failing validation gates with HTTP 400 Bad Request.

### 7. Dual Approval Workflow (`ApprovalRequest`)
- Invoices with total amount **≥ ₹5,00,000** (`DUAL_APPROVAL_THRESHOLD_INR`) enforce mandatory two-person dual control.
- **Step 1:** An AP Reviewer or Lead approves. Invoice moves to `ACTION_REQUIRED` with `workflow_substatus = PENDING_SECOND_APPROVAL`.
- **Step 2:** A second approver signs off. The backend strictly enforces:
  1. **Anti-Self-Approval:** The second approver cannot be the same user ID as the first approver (`actor_id != first_approver_id`). Returns HTTP 400 if violated.
  2. **Role Authorization:** The second approver must possess `CONTROLLER` or `SYSTEM_ADMIN` role. Returns HTTP 403 if an `AP_CLERK` or `AP_LEAD` attempts second sign-off.
- Once both approvals are complete, the invoice reaches `INTERNAL_APPROVAL_COMPLETE` (`MANUALLY_APPROVED`).

### 8. Immutable Regulatory Audit Trail (`AuditEvent`)
- Every lifecycle mutation, upload, review, hold, escalation, approval, and CSV export is recorded as an `AuditEvent`.
- Enforced at the PostgreSQL database layer via trigger `trg_audit_events_immutable` (`BEFORE UPDATE OR DELETE ON audit_events EXECUTE FUNCTION prevent_audit_events_mutation()`), which raises a database exception prohibiting UPDATE or DELETE.
- Runtime database user `ap_app_user` has `UPDATE` and `DELETE` privileges permanently revoked on `audit_events`.
- Auditor role has dedicated read-only query access and CSV export capabilities (`GET /api/v1/audit/export`).

### 9. Multi-Tenant Security & Role-Based Access Control (RBAC)
- **Tenant Isolation:** Every table includes `org_id`. PostgreSQL Row-Level Security (RLS) policies isolate tenant records.
- **Storage Isolation:** Object storage paths enforce `org_{org_id}/...` prefixing; presigned URLs expire in 300 seconds.
- **Roles:**
  - `AP_CLERK`: Reviews invoices, executes triage actions, approves invoices < ₹5,00,000.
  - `AP_LEAD`: All Clerk privileges + can reject invoices and provide first dual-approval sign-off.
  - `CONTROLLER`: All Lead privileges + can provide second dual-approval sign-off and export compliance audit logs.
  - `SYSTEM_ADMIN`: Full administrative privileges, user management, and dual-approval sign-off.
  - `AUDITOR`: Strictly read-only oversight across all routes. All mutation endpoints (`POST`, `PUT`, `DELETE`, `/actions`) return HTTP 403 Forbidden.

---

## Section B: What is Evaluation-Only (Synthetic & Seeded Fixtures)

To enable self-contained evaluation, demonstration, and automated testing without external enterprise dependencies, the repository bundles synthetic evaluation fixtures.

### 1. Dedicated Evaluation Tenant (`org_sme_eval`)
- Created by `engine/sme_eval_setup.py`.
- Seeded with 4 pre-provisioned enterprise personas:
  - `user_lead_01` (SME AP Lead / Priya Sharma, `AP_LEAD`)
  - `user_ctrl_01` (Financial Controller / Rajesh Nair, `CONTROLLER`)
  - `user_clerk_01` (Senior AP Clerk / Sunita Rao, `AP_CLERK`)
  - `user_audit_01` (External Compliance Auditor / Vikram Mehta, `AUDITOR`)
- Quick-login tokens are provisioned on local loopback (`127.0.0.1` / `localhost`) for friction-free evaluation.

### 2. Synthetic Reference Datasets
The following CSV files in `tests/evaluation_corpus_v2/reference_data/` populate procurement snapshots:
- `fictional_supplier_master.csv`: 12 fictional Indian vendors with valid GSTIN checksums and MSME classifications.
- `purchase_orders.csv`: 20 synthetic purchase orders with line items, contracted rates, and quantities.
- `goods_receipts.csv`: 20 synthetic warehouse receipts linked to POs.
- `quality_inspections.csv`: Quality acceptance records and inspection certificates.
- `rate_contracts.csv` and `service_periods.csv`: Long-term rate agreement snapshots.

### 3. Seeded Invoice Scenarios in `org_sme_eval`
Six specific evaluation documents are seeded directly into `org_sme_eval` for instant demonstration:
1. `01_invoice_AP_26_001.pdf` (APTC-001): Apex Industrial Supplies — Clean 3-way match, all 7 gates PASS.
2. `09_invoice_AP_26_009.pdf` (APTC-009): Bharat Forge Tools — Clean manufacturing invoice, all 7 gates PASS.
3. `30_invoice_AP_26_011.pdf` (APTC-030): Apex Industrial Supplies — Rate & quantity variance, Gates 4 (QC) & 6 (Tolerance) FAIL.
4. `36_invoice_POS_26_112.pdf` (APTC-036): Precision Optical — Degraded scanned POS receipt, Gates 1-6 FAIL.
5. `37_invoice_CP_26_025.pdf` (APTC-037): ChemPharma Labs — Low-contrast skewed scan, Gates 1-6 FAIL.
6. `38_payment_receipt_RCPT_26_088.pdf` (APTC-038): Modern Components — Commercial payment receipt, quarantined in `quarantined_documents` (no payable liability created).
7. `inv_dual_eval_sec`: Synthetic high-value invoice (₹7,50,000) seeded to demonstrate the completed dual-approval state.

### 4. Seeded Confidence Scores
In synthetic evaluation seeding, `confidence_score` on `extracted_fields` is set to fixed constants (`0.99` for digital PDFs, `0.95` for complex layouts). They are deterministic fixtures, not live empirical log-probability measurements.

---

## Section C: What is Configured but Not Operational in This Environment

Several integrations are fully coded with architecture, models, migrations, and unit tests, but are not active in the local/evaluation runtime due to external cloud credentials.

### 1. SAP S/4HANA OData / RFC Live Connector
- **Current Status:** `NOT_CONFIGURED` (`is_erp_configured() == False`).
- **Implementation:** `backend/api/v1/source_records.py` and `backend/api/v1/connections.py` inspect `SAP_API_BASE_URL`, `SAP_CLIENT_ID`, and `SAP_COMPANY_CODE`.
- **Reality:** No live SAP gateway is provisioned in the evaluation environment. The application honestly discloses: `"provenance": "SYNTHETIC_EVALUATION_CORPUS"`. The system operates against synchronized PostgreSQL snapshots, not live OData calls.

### 2. Google Cloud Pub/Sub & Gmail Ingestion Watch
- **Current Status:** `PRODUCTION_GOOGLE_VERIFICATION_PENDING`.
- **Implementation:** Three-legged OAuth 2.0 flow, AES-128-CBC refresh token encryption, push webhook with OIDC token validation, 48-hour watch renewal, and history synchronization.
- **Reality:** Dedicated Google test mailbox credentials exist, but Google Cloud CASA Tier 2 assessment and live Pub/Sub topic subscription are deferred to production deployment. In this environment, Gmail ingestion is inactive unless live credentials are provided.

### 3. Live AWS Bedrock Mantle Inference
- **Current Status:** Client implemented; evaluation fixtures active.
- **Implementation:** `engine/mantle_client.py` and `engine/hybrid_extractor.py` connect to Bedrock endpoint `https://bedrock-mantle.ap-south-1.api.aws/v1`.
- **Reality:** When running locally without active AWS Bedrock credentials, the engine relies on pre-evaluated corpus benchmark results (`tests/evaluation_corpus_v2/benchmark_v1_results.json`) and deterministic regex extraction.

### 4. Automated Cloud Scheduler Background Workers
- **Current Status:** Endpoint-ready; scheduled cron triggers unconfigured.
- **Implementation:** Endpoints for watch renewal (`POST /api/v1/integrations/gmail/watch/renew`), history reconciliation (`POST /api/v1/integrations/gmail/reconcile`), and lease recovery (`recover_expired_jobs()`) exist.
- **Reality:** In local evaluation, these endpoints must be called manually or via tests; no external Cloud Scheduler daemon is running.

---

## Section D: What is Not Implemented (Explicit Non-Capabilities)

To ensure strict product truth and avoid misleading demo audiences or evaluators, the following capabilities are **explicitly NOT implemented**:

1. **NO ERP Posting or General Ledger Write-Back:**
   The AP Command Center does not post journal entries, write parking documents, or mutate records in SAP, Oracle, NetSuite, or Tally. Reaching `INTERNAL_APPROVAL_COMPLETE` signifies internal AP review sign-off only.
2. **NO Bank Payment Execution or Disbursement:**
   The application contains zero payment gateway integrations, banking APIs, NEFT/RTGS rails, or automated payout mechanisms. The headline "Approved for Payment Run" refers to approval for inclusion in an external disbursement batch, not payment transmission.
3. **NO Outbound Supplier Communications or Email Dispatch:**
   Clicking `Ask Supplier to Correct` (`REQUEST_SUPPLIER_CORRECTION`) or `Hold for Evidence` (`HOLD_PENDING_EVIDENCE`) does **NOT** dispatch an email, SMS, WhatsApp message, or vendor portal notification. It solely updates the internal database record and audit ledger.
4. **NO Automated Debit Note Document Generation:**
   Clicking `Raise Debit Note` (`RAISE_DEBIT_NOTE`) updates `workflow_substatus` to `DEBIT_NOTE_PENDING`. It does not generate a debit memo PDF or push a deduction notice to the vendor.
5. **NO Cryptographic Hash-Chain Linking:**
   The audit trail is protected by database triggers and privilege revocation, making it strictly append-only. However, there is no blockchain-style or Merkle-tree cryptographic hash chain linking each audit event's hash to the prior event.
6. **NO Vendor Self-Service Portal:**
   There is no external vendor login where suppliers can upload invoices, contest rejections, or track payment status.
7. **NO Dynamic Bounding-Box Overlay on Canvas:**
   While the database schema supports `bounding_box` coordinates on `extracted_fields`, the PDF viewer pane renders the authentic document via browser PDF embed without interactive bounding-box overlays.

---

## Section E: Business Rules and Policy Constants Truth Table

| Policy Parameter | Runtime Code Setting | Documentation Claim | UI Claim (Outdated) | Verified Truth |
| :--- | :--- | :--- | :--- | :--- |
| **Dual Approval Threshold** | `DUAL_APPROVAL_THRESHOLD_INR = 500000.00` (`backend/core/config.py`) | ₹5,00,000 (`docs/AP_BUSINESS_RULES.md`) | ₹1,00,000 (`InvoiceDetailPage.tsx` Tour Step 5) | **₹5,00,000** is strictly enforced at runtime. The tour step 5 text of ₹1,00,000 is an outdated copy error. |
| **Price Variance Tolerance** | `RATE_TOLERANCE_PERCENT = 1.50` (`backend/core/config.py`, `indian_tax_rules.py`) | ±1.50% (`docs/AP_BUSINESS_RULES.md`) | 2.50% (`InvoiceDetailPage.tsx` Tour Step 3) | **±1.50%** is strictly enforced at runtime. The tour step 3 text of 2.50% is an outdated copy error. |
| **Quantity Overrun Tolerance** | `0.00%` (`backend/core/pipeline.py`, `rules.py`) | 0.00% (`docs/AP_BUSINESS_RULES.md`) | 0.00% (`InvoiceDetailPage.tsx` Tour Step 3) | **0.00%** strictly enforced; zero quantity overruns permitted. |
| **GST Tax Arithmetic Rounding** | `₹1.00` (`engine/indian_tax_rules.py`) | ₹1.00 (`docs/AP_BUSINESS_RULES.md`) | "Reconciled within tolerance" | **₹1.00** strictly enforced in engine math. |
| **Second Approver Role** | `CONTROLLER` or `SYSTEM_ADMIN` (`backend/api/v1/invoices.py`, `approvals.py`) | Financial Controller (`docs/AP_BUSINESS_RULES.md`) | Financial Controller or System Admin | **CONTROLLER or SYSTEM_ADMIN** required by backend role check; first approver cannot self-approve. |
| **Duplicate Byte Detection** | SHA-256 byte match (`backend/api/v1/documents.py`) | SHA-256 hash match (`docs/AP_BUSINESS_RULES.md`) | Duplicate invoice check | **Immediate HTTP 409 rejection** at upload. |
| **Semantic Duplicate Detection** | Match on Supplier + Inv Number + Date + Amount (`engine/duplicate_detector.py`) | 4-point semantic match | Gate 7 check | **FLAGGED_HITL_REVIEW** in engine; fails Gate 7. |
| **Validation Gate Overrides (D-04)** | Strictly disabled; HTTP 400 returned | Overrides deferred (`IMPLEMENTATION_DECISIONS.md`) | "Approval Blocked" button | **Approval blocked** if any gate fails; zero overrides allowed. |

---

## Section F: Action Semantics Table

| Action Identifier | UI Label & Shortcut | Role Restrictions | Database State Mutations | External Effects | What Happens Next |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `APPROVE_AP_REVIEW` | **Approve Review** (`A`) | `AP_CLERK`, `AP_LEAD`, `CONTROLLER`, `SYSTEM_ADMIN` | If total < ₹5L: `stage = INTERNAL_APPROVAL_COMPLETE`, `decision = MANUALLY_APPROVED`. If total ≥ ₹5L (Step 1): `stage = ACTION_REQUIRED`, `workflow_substatus = PENDING_SECOND_APPROVAL`. If Step 2 (Controller): `stage = INTERNAL_APPROVAL_COMPLETE`, `decision = MANUALLY_APPROVED`. Exceptions set to `RESOLVED`. | **None.** No ERP posting, no disbursement. | If single approval: invoice is marked approved. If dual approval: moves to Controller approval queue. |
| `HOLD_PENDING_EVIDENCE` | **Hold for Evidence** (`H`) | `AP_CLERK`, `AP_LEAD`, `CONTROLLER`, `SYSTEM_ADMIN` | `stage = ACTION_REQUIRED`, `workflow_substatus = ON_HOLD`. Active exceptions kept in `IN_REVIEW`. | **None.** No vendor communication sent. | Invoice stays in inbox under Hold filter until clerk receives offline evidence and resumes review. |
| `REQUEST_SUPPLIER_CORRECTION` | **Ask Supplier to Correct** | `AP_CLERK`, `AP_LEAD`, `CONTROLLER`, `SYSTEM_ADMIN` | `stage = ACTION_REQUIRED`, `workflow_substatus = SUPPLIER_CORRECTION_REQUESTED`. Exceptions kept in `IN_REVIEW`. | **None.** No email dispatched to vendor. | Clerk communicates with supplier offline; invoice awaits revised document or credit note. |
| `RAISE_DEBIT_NOTE` | **Raise Debit Note** | `AP_CLERK`, `AP_LEAD`, `CONTROLLER`, `SYSTEM_ADMIN` | `stage = ACTION_REQUIRED`, `workflow_substatus = DEBIT_NOTE_PENDING`. Exceptions kept in `IN_REVIEW`. | **None.** No debit memo PDF created. | Internal accounting team must initiate debit note in external ERP. |
| `ESCALATE` | **Escalate** | `AP_CLERK`, `AP_LEAD`, `CONTROLLER`, `SYSTEM_ADMIN` | `stage = ACTION_REQUIRED`, `workflow_substatus = ESCALATED`. Exceptions kept in `IN_REVIEW`. | **None.** No notification sent. | Invoice flagged for senior management review in operational inbox. |
| `REJECT_INVOICE` | **Reject Invoice** (`R`) | `AP_LEAD`, `CONTROLLER`, `SYSTEM_ADMIN` (`AP_CLERK` receives HTTP 403) | `stage = ACTION_REQUIRED`, `decision = REJECTED`, `workflow_substatus = None`. Exceptions set to `RESOLVED`. | **None.** No rejection letter dispatched. | Invoice is formally closed as rejected; cannot be approved. |
| `QUARANTINE` | **Set Aside (Quarantine)** | `AP_CLERK`, `AP_LEAD`, `CONTROLLER`, `SYSTEM_ADMIN` | `stage = QUARANTINED`, `decision = QUARANTINED`, `workflow_substatus = None`. Exceptions kept in `IN_REVIEW`. | **None.** | Document segregated from payable invoice workflows into Quarantine view. |

---

## Section G: Demo Readiness & Scenario Inventory

To deliver a credible, non-fictional demonstration, presenters must use the verified seeded documents in the evaluation workspace.

| # | Scenario Concept | Seeded Invoice ID | Document Filename | Expected Verdict | Failing Gates | Demo Readiness |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 1 | **Clean 3-Way Match** | `inv_live_f18c8bb7` (or `inv_d76401c096d0`) | `01_invoice_AP_26_001.pdf` (or `09_...pdf`) | `PENDING_APPROVAL` / `MATCH_CANDIDATE` | None (All 7 PASS) | **Ready.** Perfect for demonstrating standard 1-click review approval. |
| 2 | **Price / Qty Discrepancy** | `inv_dbfcaf77ba9b` | `30_invoice_AP_26_011.pdf` | `ACTION_REQUIRED` / `FLAGGED_EXCEPTION` | Gate 4 (QC) & Gate 6 (Tolerance) FAIL | **Ready.** Perfect for showing blocked approval and triage actions (Hold / Correction). |
| 3 | **Missing GRN** | *In corpus: APTC-010* (`10_invoice_KF_26_015.pdf`) | `10_invoice_KF_26_015.pdf` | `GRN_QUANTITY_REVIEW` | Gate 3 (GRN) FAIL | **Corpus only.** Available in evaluation corpus; not seeded into `org_sme_eval` by default. |
| 4 | **Pending / Rejected QC** | *In corpus: APTC-011* (`11_invoice_MC_26_090.pdf`) | `11_invoice_MC_26_090.pdf` | `QC_HOLD` | Gate 4 (QC) FAIL | **Corpus only.** Available in evaluation corpus; Gate 4 failure can also be seen in APTC-030. |
| 5 | **Duplicate Invoice** | *Tested at upload API* | Any uploaded duplicate | `DUPLICATE_DETECTED` (HTTP 409) | Gate 7 FAIL | **Ready via Upload.** Re-uploading any existing PDF triggers immediate duplicate rejection. |
| 6 | **Incorrect GST Split** | *In corpus: APTC-032* (`32_invoice_MC_26_091.pdf`) | `32_invoice_MC_26_091.pdf` | `TAX_CALCULATION_EXCEPTION` | Gate 5 (GST) FAIL | **Corpus only.** Tested in unit suite; not seeded into `org_sme_eval` by default. |
| 7 | **High-Value Dual Approval** | `inv_dual_eval_sec` (Amount ₹7,50,000) | Synthetic high-value record | `INTERNAL_APPROVAL_COMPLETE` / `MANUALLY_APPROVED` | None | **Ready.** Proves dual control (First approved by Clerk/Lead, finalized by Controller). |
| 8 | **Non-Invoice Document** | `q_9b5ebabae921` | `38_payment_receipt_RCPT_26_088.pdf` | `QUARANTINED` / `COMMERCIAL_NON_PAYABLE_RECEIPT` | Quarantined before invoice creation | **Ready.** Demonstrates non-payable receipt quarantine in Connections / Quarantine queue. |

---

## Section H: Audit and Security Boundaries

1. **Tenant Segregation:** All SQL queries enforce `org_id == current_user.org_id`. Cross-tenant record access is blocked by PostgreSQL Row-Level Security.
2. **Audit Immutability:** Audit records cannot be altered or removed, even by System Administrators. Any attempt to execute `UPDATE` or `DELETE` on `audit_events` triggers a PostgreSQL exception.
3. **Dual Control Enforced in Database:** Dual approval is not a frontend visual gimmick. `backend/api/v1/invoices.py` enforces `first_approver_id != current_user.id` and validates that the second approver holds `CONTROLLER` or `SYSTEM_ADMIN` role.
4. **Read-Only Oversight:** The `AUDITOR` role cannot perform state mutations. Any mutation call from an Auditor receives HTTP 403 Forbidden.
5. **Presigned URL Expiry:** Document access URLs generated from Supabase Storage expire in 300 seconds (5 minutes), enforcing zero-trust document security.
