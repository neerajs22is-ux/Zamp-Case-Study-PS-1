# Zamp PS-1 — Evaluator Quick Start Guide

Welcome to the **Autonomous Accounts Payable (AP) Command Center** (Zamp Problem Statement 1). This 1-page document provides evaluators with direct links to the live deployment, authentication instructions, a 5-minute recommended evaluation sequence, scenario guides, and video demonstration specifications.

---

## 1. Live Deployment & Links

| Experience / Surface | Hosted URL / Target | Description |
| :--- | :--- | :--- |
| **Flagship AP Command Center** | **[zamp-case-study-ps-1-1.onrender.com](https://zamp-case-study-ps-1-1.onrender.com)** | Primary enterprise multi-tenant application with 2-column review workspace, operational metrics, and dual-control sign-offs. |
| **Interactive Sandbox 2.0** | **[zamp-case-study-ps-1-1.onrender.com/sandbox](https://zamp-case-study-ps-1-1.onrender.com/sandbox)** | Guided 7-chapter walkthrough ("The Invoice Journey") featuring 6 pre-seeded authentic scenarios and custom PDF upload. |
| **Liveness Health Check** | `GET /healthz` or `GET /` | Returns `{"status": "ok", "app": "zamp-ap-command-center"}`. |
| **Dependency Readiness** | `GET /api/v1/system/status` or `GET /health/ready` | Verifies PostgreSQL connectivity, pooler health, migrations, and tenant status. |
| **Interactive API Docs** | **[...onrender.com/docs](https://zamp-case-study-ps-1-1.onrender.com/docs)** | Interactive Swagger / OpenAPI documentation for all REST endpoints. |
| **GitHub Repository** | `https://github.com/neerajs22is-ux/Zamp-Case-Study-PS-1-.git` | Authoritative source repository on `master`. |

---

## 2. Core Architecture: *"Models Read, Rules Decide"*

The AP Command Center strictly decouples **probabilistic document interpretation** from **deterministic financial adjudication**:

- **Multimodal AI Pipeline:** Combines local **RapidOCR (ONNX)** character detection, **AWS Bedrock Palmyra Vision 7B** visual analysis, and **AWS Bedrock Mantle (Qwen 235B)** structured extraction. Every extracted field retains token coordinates and page-level provenance.
- **Grounding Tripwires:** An Ask4i-inspired verification gate checks every financial value against extracted OCR tokens and raw document bytes. If an LLM hallucinates an ungrounded total or rate, the tripwire trips fail-closed to human review.
- **Deterministic 3-Way Match Engine:** Evaluates exact line-by-line procurement agreement against purchase orders (`PO`), goods receipt notes (`GRN`), and quality control (`QC`) inspection records using Decimal INR arithmetic.
- **Seven Sequential Policy Gates:** Enforces vendor master registration, PO authorization, GRN quantity receipt, QC acceptance, Indian GST tax arithmetic, price variance limits ($\le 1.5\%$), and two-tier duplicate detection (SHA-256 byte collision + Gate 7 commercial invoice deduplication).
- **Database-Level Audit Immutability:** Every decision, state transition, and human override writes an append-only event to PostgreSQL, protected against tampering by PL/pgSQL database triggers (`prevent_audit_events_mutation()`).

---

## 3. Evaluator Authentication & Access

### A. Live Hosted Environment (Render)
1. Navigate to **[https://zamp-case-study-ps-1-1.onrender.com](https://zamp-case-study-ps-1-1.onrender.com)**.
2. Sign in using **Google OAuth (SSO)**. Evaluators included in the server-side allowlist (`EVALUATOR_ALLOWLIST_EMAILS`) receive privileged `AP_LEAD` access to the pre-seeded evaluation tenant `org_sme_eval`.
3. Alternatively, evaluators with an authorized evaluator token can expand the **"Authorized evaluator token"** drawer on the login screen.
4. *Note on Security:* In production, development-session bypasses and one-click demo logins are strictly barred (`ENABLE_DEV_SESSION=false`) to protect tenant isolation.

### B. Local Development Environment (`http://127.0.0.1:8001`)
1. Clone the repository and run `python run.py`.
2. With `ENABLE_DEV_SESSION=true` in local `.env`, the login screen provides 1-click persona quick-logins:
   - **Priya Sharma (AP Lead):** Full inbox triage, 2-column review, single approval ($< ₹5,00,000$), query holds, and rejections.
   - **Rajesh Nair (Financial Controller):** Secondary sign-off on high-value invoices ($\ge ₹5,00,000$) and financial dashboards.
   - **Vikram Malhotra (Auditor):** Read-only inspection of immutable audit ledgers (all mutations return HTTP 403).
   - **Ananya Iyer (AP Associate):** Line-item discrepancy verification and initial document ingestion.

---

## 4. Recommended 5-Minute Evaluation Walkthrough

Follow this sequence to test all key aspects of the engine in under five minutes:

1. **Step 1: Inspect the Operations Dashboard & Inbox**
   - Log into the Flagship app. Review the live metrics: Total Invoices Ingested, Exceptions Requiring Action, Blocked Exposure Value (INR), and Clean Match Candidates.
2. **Step 2: Clean 3-Way Match & Single Approval (`SCN-01`)**
   - Open invoice **`01_invoice_AP_26_001.pdf`** in the Inbox.
   - Observe the 2-column review workspace: original PDF on the left, 7 deterministic gates on the right.
   - All 7 gates pass with 0.00% variance. Pipeline status: `MATCH_CANDIDATE`.
   - Click **Approve Invoice**. The invoice transitions to `INTERNAL_APPROVAL_COMPLETE` (`MANUALLY_APPROVED`), and an immutable audit event is committed to PostgreSQL.
3. **Step 3: Price Variance & Operational Query Hold (`SCN-02`)**
   - Open invoice **`30_invoice_AP_26_011.pdf`**.
   - Gate 6 fails: Supplier billed unit price ₹220.00 vs contracted PO rate ₹185.00 (+18.92% variance vs 1.5% tolerance limit).
   - Gate 3 fails: Billed 100 units vs 80 units accepted on GRN-26-621.
   - Click **Place on Query Hold**. Enter reason *"Vendor rate discrepancy under commercial dispute with procurement"*. The status updates to `HOLD_PENDING_EVIDENCE`.
4. **Step 4: Non-Payable Document Quarantine (`SCN-05`)**
   - View document **`38_payment_receipt_RCPT_26_088.pdf`**.
   - The multimodal classifier identified the document as `PAYMENT_RECEIPT`.
   - The system autonomously routed it to `QUARANTINED` with zero AP liability registered.
5. **Step 5: High-Value Dual Control ($\ge ₹5,00,000$) & Anti-Self-Approval**
   - Ingest or open an invoice with net payable $\ge ₹5,00,000$ (e.g. ₹7,50,000).
   - First approval by AP Lead transitions the stage to `ACTION_REQUIRED` (`PENDING_SECOND_APPROVAL`).
   - Log in as Financial Controller (`Rajesh Nair`). Controller approves the secondary sign-off to complete approval.
   - Attempting to approve both steps with the same user ID is blocked by the anti-self-approval rule (`actor_id != first_approver_id`).

---

## 5. The Six Golden Evaluation Scenarios

Pre-seeded and verified in tenant `org_sme_eval` and accessible via both Flagship and Sandbox:

| # | Scenario ID | Document Reference | Expected Decision | Target Stage | Key Operational & Policy Mechanism |
|---|---|---|---|---|---|
| **1** | `SCN-01` | `01_invoice_AP_26_001.pdf` | `MATCH_CANDIDATE` | `PENDING_APPROVAL` | **Clean 3-Way Match:** Perfectly matches PO-26-1001, GRN-26-501, and accepted QC certificate with 0.00% variance. All 7 deterministic policy gates pass. Ready for AP Lead sign-off. |
| **2** | `SCN-02` | `30_invoice_AP_26_011.pdf` | `FLAGGED_EXCEPTION` | `ACTION_REQUIRED` | **Price & Qty Variance:** Supplier bills unit price ₹220.00 vs contracted PO rate ₹185.00 (+18.92% variance vs 1.5% limit) and bills 100 units vs 80 accepted on GRN-26-621. Fails Gate 6 & Gate 3. |
| **3** | `SCN-03` | `36_invoice_POS_26_112.pdf` | `FLAGGED_EXCEPTION` | `ACTION_REQUIRED` | **Degraded Scan Safety & Grounding Tripwire:** Scanned document testing optical character detection and evidence grounding tripwires, preventing ungrounded hallucinations from advancing to payment. |
| **4** | `SCN-04` | `11_invoice_MC_26_090.pdf` | `FLAGGED_EXCEPTION` | `ACTION_REQUIRED` | **Quarantined Inspection:** Factory goods receipt GRN-26-603 has inspection status HOLD. Fails Gate 4 deterministically; blocks payment on defective materials. |
| **5** | `SCN-05` | `38_payment_receipt_RCPT_26_088.pdf` | `REJECTED` | `QUARANTINED` | **Non-Payable Commercial Doc:** Document classified as `PAYMENT_RECEIPT`; `is_payable_invoice` evaluates to False. Autonomously rejected without generating an open liability. |
| **6** | `SCN-06` | `01_invoice_AP_26_001.pdf` | `REJECTED` | `ACTION_REQUIRED` | **Duplicate Resubmission:** Identical voucher number or SHA-256 hash collision with active ledger record. Gate 7 fails deterministically; prevents duplicate payment disbursements. |

---

## 6. 5-Minute Video Walkthrough Specification

For evaluators reviewing candidate video submissions, the accompanying video should adhere to these standards:
- **Format:** Continuous unedited screen capture with live narration (no slides, no marketing animations).
- **Duration:** 4 to 6 minutes.
- **Narrative Structure:**
  1. *Minute 1 — Architecture:* Live system running on Render; brief explanation of *"Models Read, Rules Decide"* and the 7-gate deterministic pipeline.
  2. *Minute 2 — Happy Path:* SCN-01 straight-through match, review workspace inspection, and single AP Lead approval.
  3. *Minute 3 — Exceptions:* SCN-02 price variance failure and operational query hold; SCN-04 QC quarantine.
  4. *Minute 4 — Safety & Grounding:* SCN-03 degraded scan grounding tripwire and SCN-05 non-payable receipt quarantine.
  5. *Minute 5 — Dual Control & Audit Ledger:* $\ge ₹5,00,000$ dual approval workflow, anti-self-approval enforcement, and PostgreSQL immutable audit log verification.

---

## 7. Key Documentation Links

- **[README.md](./README.md):** Repository overview, visual showcase, and installation guide.
- **[PROJECT_STATUS.md](./PROJECT_STATUS.md):** Complete milestone scorecard, live verification ledger, and authoritative test counts (520 passed, 0 failed, 43 skipped; 20 frontend tests).
- **[docs/AP_BUSINESS_RULES.md](./docs/AP_BUSINESS_RULES.md):** Complete specification of 7 match gates, Indian GST arithmetic, and state transitions.
- **[docs/LOCAL_SETUP.md](./docs/LOCAL_SETUP.md):** Local installation instructions, migrations, and developer personas.
- **[OPERATIONS_RUNBOOK.md](./OPERATIONS_RUNBOOK.md):** Production runbook, monitoring probes, and incident triage.
- **[SECURITY_NOTES.md](./SECURITY_NOTES.md):** Database RLS, token security, and trigger immutability.
