# HR & Executive Showcase Guide: AP Command Center
## Autonomous Accounts Payable Verification, Deterministic Policy Controls & Dual-Approval Governance

**Product:** Autonomous Accounts Payable (AP) Command Center  
**Target Audience:** HR Leaders, Executive Evaluators, Non-AP Technical Interviewers, and Financial Controllers  
**Estimated Walkthrough Time:** 10–15 minutes  
**Application URL:** `http://127.0.0.1:8000` (FastAPI backend + Vite React SPA)  
**Fast-Track Demo:** Click the **"Showcase Tour"** button in the top navigation bar at any time to launch any scenario in 1 click.

---

## 1. What to Say in the First 30 Seconds

> *"Welcome to the AP Command Center. At its core, this application solves a critical corporate risk: how enterprises verify that supplier invoices are authentic, authorized, physically delivered, and mathematically accurate before releasing funds.*  
> *It acts like an autonomous pre-payment security checkpoint. It extracts invoice data with multimodal AI, matches it against purchase orders and warehouse receiving slips across 7 strict deterministic policy checks, and enforces statutory Indian MSME deadlines and dual-approval governance.*  
> *Crucially, it is an internal review and governance system: it enforces rigorous sign-off, but never automatically executes wire disbursements or posts General Ledger entries without treasury control."*

---

## 2. 1-Click Evaluation Personas

On the initial login screen (`/`), evaluators can access any role with a single click:

| Evaluation Persona | Email | Permitted Authority | Primary Showcase Use |
| :--- | :--- | :--- | :--- |
| **SME AP Lead** *(Recommended)* | `sme_lead@company.internal` | Single-approver (< ₹5L), discrepancy triage, debit notes | Scenarios 1, 2, 4, 5 |
| **SME Financial Controller** | `sme_controller@company.internal` | Executive dual approval ($\ge$ ₹5L), policy overrides disabled | Scenario 3 |
| **SME Auditor** | `sme_auditor@company.internal` | Strictly read-only oversight across all organizations | Scenario 6 |
| **SME AP Associate** | `sme_associate@company.internal` | Queue intake, OCR parsing validation | Intake verification |

*Tip: You can also switch roles live at any time using the "Role" dropdown in the top header.*

---

## 3. The 6 Canonical Demonstration Scenarios

### Showcase Scenario 1: Straight-Through 3-Way Match (The "Golden Path")
**Objective:** Show how clean invoices pass all deterministic checks and require zero manual data entry.

1. **Launch:** Click **"Showcase Tour"** in header $\to$ Select **Scenario #1** (or navigate to `/invoices/inv_d76401c096d0`).
2. **Invoice:** `AP-26-009` (Supplier: Asterion Precision Components Pvt Ltd).
3. **Billed Amount:** `₹2,31,280.00` (Below the ₹5,00,000 dual-control threshold).
4. **Key Talking Points:**
   - **Procurement Verification Flow:** Show the 4 connected nodes (1. Billed Claim $\to$ 2. PO Contract $\to$ 3. Receiving GRN $\to$ 4. Quality QC). All nodes show green checks.
   - **Policy Checks Tab:** Show that all 7 deterministic gates (Vendor Identity, PO Authorization, GRN Receipt, QC Inspection, GST Arithmetic, Price Tolerance, Duplicate Check) passed 100%.
   - **Sticky Decision Bar:** Notice the full-width green **"Approve Review"** button. Clicking it opens the consequence-aware modal confirming internal review sign-off.

---

### Showcase Scenario 2: Exception Resolution & Failed-Gate Enforcement
**Objective:** Prove that the system blocks non-compliant invoices and prevents single-click overrides (Design Invariant D-04).

1. **Launch:** Click **"Showcase Tour"** in header $\to$ Select **Scenario #2** (or navigate to `/invoices/inv_dbfcaf77ba9b`).
2. **Invoice:** `AP-26-011` (Supplier: Asterion Precision Components Pvt Ltd).
3. **Billed Amount:** `₹25,960.00`.
4. **Observe:**
   - **Gate #6 Fails (PO Price Tolerance):** Billed unit rate is ₹2,850.00/unit vs contracted rate ₹2,450.00/unit (+16.33% variance, exceeding the strict ±1.50% tolerance).
   - **Strict Override Block:** The **"Approve Review"** button is permanently locked (`Approval Blocked - 1 Failing Check`). Overrides are mathematically disabled in the backend.
   - **Actionable Resolution:** Click **"Raise Debit Note"**. The modal pre-fills an exact recommended debit note amount of ₹500.00 to offset the overbilled delta.

---

### Showcase Scenario 3: High-Value Dual Approval Governance (≥ ₹5,00,000)
**Objective:** Demonstrate enterprise financial separation of duties for high-value invoices.

1. **Launch:** Click **"Showcase Tour"** in header $\to$ Select **Scenario #3** (or switch role to **Financial Controller** and open `/invoices/inv_dual_eval_sec`).
2. **Invoice:** `INV-DUAL-SEC-001`.
3. **Billed Amount:** `₹7,50,000.00` ($\ge$ ₹5,00,000 threshold).
4. **Key Talking Points:**
   - **Dual Control Badge:** Notice the purple `Dual Control Active` badge in the header.
   - **Two-Step Progression:** Step 1 (AP Lead Review Sign-Off) $\to$ Step 2 (Controller Secondary Approval).
   - **Separation of Duties:** The backend rejects self-approval (the same human cannot approve Step 1 and Step 2) and rejects AP Associate attempts.

---

### Showcase Scenario 4: Statutory MSMED Act 45-Day Deadline Prioritization
**Objective:** Show statutory Indian compliance protecting companies from compound penal interest.

1. **Launch:** Click **"Showcase Tour"** in header $\to$ Select **Scenario #4** (or navigate to `/invoices?stage=ACTION_REQUIRED`).
2. **Key Talking Points:**
   - **Executive Blocked Exposure KPI Strip:** Highlights total blocked working capital, critical statutory deadlines, and unassigned exceptions.
   - **Relative Statutory Countdown:** Shows `Due in 42d` or `Overdue by Xd` calculated from invoice receipt date under Section 15 of the MSMED Act.
   - **Statutory Invariant:** Snoozing or holding an exception never resets the statutory countdown. Reassigning an exception requires a mandatory business justification logged to PostgreSQL audit triggers.

---

### Showcase Scenario 5: Quarantine Security & Tamper Detection
**Objective:** Show how the system protects the organization from corrupt or non-invoice documents.

1. **Launch:** Click **"Showcase Tour"** in header $\to$ Select **Scenario #5** (or navigate to `/settings/connections`).
2. **Key Talking Points:**
   - **Zero-Trust Ingestion Vault:** Inspect recent quarantined documents.
   - **Cryptographic Fingerprints:** Displays 64-character SHA-256 digests.
   - **Tamper Rejection:** Non-invoices (payment receipts, account statements) and unreadable OCR scans are quarantined automatically before entering the matching engine.

---

### Showcase Scenario 6: Forensic Append-Only Audit Trail Ledger
**Objective:** Show complete compliance oversight and cryptographic traceability for external auditors.

1. **Launch:** Click **"Showcase Tour"** in header $\to$ Select **Scenario #6** (or switch role to **Auditor** and navigate to `/audit`).
2. **Key Talking Points:**
   - **Read-Only Enforcement:** When switched to Auditor, all mutation buttons disappear.
   - **21-Action Taxonomy:** Every user action (`APPROVE_AP_REVIEW`, `RAISE_DEBIT_NOTE`, `REASSIGN_EXCEPTION`, `LOGIN`) has semantic color-coded tracking.
   - **Actor & Role Attribution:** Explicitly ties events to authenticated emails and roles.
   - **Side-by-Side Visual Diff vs Raw JSON:** Click any event row to open the forensic slide-over drawer, inspect before/after state diffs, or copy raw JSON with 1 click.

---

## 4. Architectural & Financial Invariants Summary

1. **D-04 Failed-Gate Invariant:** Policy overrides are disabled by design. Failed gates permanently block review approval.
2. **Dual-Approval Threshold:** Invoices $\ge$ ₹5,00,000 mathematically enforce two distinct human signers.
3. **Multi-Tenant Isolation:** PostgreSQL Row-Level Security ensures tenant partitions remain strictly separated.
4. **Read-Only Procurement Master Records:** Reference data represents authoritative ERP snapshots; clerks cannot alter contracted rates or vendor GSTINs.
5. **No Direct Bank Disbursements:** Approvals represent internal review sign-off only; payment execution is downstream in treasury.
