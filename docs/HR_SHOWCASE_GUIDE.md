# HR & Executive Showcase Guide: AP Command Center

**Product:** Autonomous Accounts Payable (AP) Command Center  
**Target Audience:** HR Leaders, Executive Evaluators, Non-AP Technical Interviewers  
**Estimated Walkthrough Time:** 10–15 minutes  
**Application URL:** `http://127.0.0.1:8000` (FastAPI backend + Vite React SPA)

---

## What to Say in the First 30 Seconds

> *"Welcome to the AP Command Center. At its core, this application solves a critical corporate problem: how companies verify that supplier invoices are authentic, accurate, and authorized before paying them.*  
> *It acts like an autonomous pre-payment security checkpoint. It extracts invoice data with multimodal AI, matches it against purchase orders and warehouse delivery slips across 7 strict policy checks, and enforces organizational dual-approval controls.*  
> *Crucially, it is an internal review and audit system—it enforces internal sign-off, but never automatically executes wire disbursements or contacts vendors without human control."*

---

## Showcase Scenario 1: Straight-Through Processing (The "Happy Path")
**Objective:** Show how clean invoices require zero manual data entry or human intervention.

1. **Navigate to:** `http://127.0.0.1:8000/today`
   - **Point out:** The **Executive Overview Card** at the top explaining the 3-step AP workflow (1. Intake & AI Extraction $\to$ 2. Deterministic Matching $\to$ 3. Dual-Control Approval).
   - **Point out:** The **Operational Boundary Pill** in the header: `AP Sign-Off Only • No Bank Disbursements`.
2. **Click:** The **"Auto-Approved (Straight-Through)"** tile (or navigate to `/invoices?decision=AUTO_APPROVED`).
3. **Select Invoice:** `AP-26-001` (ID: `inv_be609a16676f`).
4. **Key Talking Points:**
   - **Procurement Verification Flow:** Show the 4 connected nodes (1. Supplier Invoice $\to$ 2. Purchase Order $\to$ 3. Warehouse GRN $\to$ 4. Quality Inspection QC). All nodes show green checks.
   - **Policy Checks Tab:** Show that all 7 deterministic gates (Vendor Identity, PO Authorization, GRN Receipt, QC Inspection, GST Arithmetic, Price Tolerance, Duplicate Check) passed 100%.
   - **Bottom Decision Bar:** Notice the green confirmation: *"Invoice review complete (Internal sign-off). Cleared for external payment batching; no disbursement or General Ledger posting has occurred."*

---

## Showcase Scenario 2: Exception Resolution & Failed-Gate Enforcement
**Objective:** Prove that the system blocks risky invoices and prevents single-click overrides (Design Invariant D-04).

1. **Navigate to:** `http://127.0.0.1:8000/invoices/inv_dbfcaf77ba9b` (`AP-26-011`).
2. **Observe:**
   - Top verdict banner shows **"Action Required: 1 check failed"** in amber/rose.
   - Look at the **Policy Checks Tab**: Gate 6 (**PO Price & Quantity Tolerance**) has failed because the invoice unit price exceeded the authorized PO price by more than the allowed $\pm 1.5\%$ tolerance.
3. **Attempt Approval:**
   - Scroll to the bottom sticky action bar.
   - **Notice:** The **Approve Review** button is replaced with a locked grey badge:  
     `Approval Blocked (1 Failing Check)`. Hovering shows: *"Approval blocked: 1 validation check failed. Policy overrides are disabled."*
4. **Explain to Interviewer:**
   - *"In legacy software, an employee could check a box to override this error and pay the bill, creating massive fraud risk. In this system, single-click overrides are mathematically impossible."*
5. **Execute an Authorized Triage Action:**
   - Click **"Ask Supplier to Correct"**.
   - A consequence-aware modal appears explaining the business outcome: *"Generates an internal correction request draft documenting the price discrepancy. Does NOT send an email to the supplier."*
   - Enter reason: *"Unit price exceeds approved PO rate by 4.2%."* and confirm.
   - A humanized toast confirms: *"Correction request logged for supplier successfully."*

---

## Showcase Scenario 3: High-Value Dual Approval Governance
**Objective:** Demonstrate enterprise financial governance for invoices exceeding ₹5,00,000.

1. **Navigate to:** `http://127.0.0.1:8000/approvals`
2. **Explain the Dual Control Policy:**
   - Invoices below ₹5,00,000 can be approved by an AP Lead.
   - Invoices at or above ₹5,00,000 require **two distinct human approvals**: Step 1 (AP Lead review) and Step 2 (Financial Controller or System Admin sign-off).
3. **Show Dual Control Enforcement:**
   - Step 1 records the initial review. The invoice transitions to `PENDING_SECOND_APPROVAL`.
   - The same user **cannot self-approve Step 2** (the system rejects this with HTTP 400: *"Dual control violation: Second approver must be a distinct authenticated user."*).
   - An AP Associate cannot approve Step 2 (rejected with HTTP 403: *"Dual control violation: Second approval requires CONTROLLER or SYSTEM_ADMIN role."*).

---

## Showcase Scenario 4: Duplicate Submission & Fraud Detection
**Objective:** Show how the system protects company cash from duplicate billing.

1. **Navigate to:** `http://127.0.0.1:8000/invoices`
2. **Point out:** The **MSME Statutory Due** column with dynamic badges (e.g. green for 30+ days remaining, amber for due within 7 days, and red only if overdue under Section 15 of the MSMED Act).
3. **Inspect Gate 7:**
   - On any invoice detail page, inspect Gate 7 (**Duplicate Submission Check**).
   - The system checks both the invoice number and the SHA-256 cryptographic hash of the uploaded PDF against all existing tenant records.
   - If a supplier accidentally re-bills the same invoice or sends a duplicate via both Gmail and portal upload, it is trapped and quarantined immediately.

---

## Showcase Scenario 5: Auditor Role & Tamper-Evident Audit Trail
**Objective:** Show read-only compliance oversight and complete audit traceability.

1. **Switch Role to Auditor:**
   - In the top navigation bar, use the role switcher pill to select **"Auditor"**.
2. **Observe Real-Time UI Adaptation:**
   - Notice that on `/invoices/inv_dbfcaf77ba9b`, all action buttons disappear and are replaced by a clear informational badge:  
     `Your role (Auditor) has read-only oversight permissions. Decision actions are disabled.`
   - Try to click or inspect: no mutation endpoints can be called.
3. **Navigate to:** `http://127.0.0.1:8000/audit`
4. **Key Talking Points:**
   - Every single event—from file upload to AI extraction, policy evaluation, triage reassignments, and approvals—is recorded in an append-only audit ledger with cryptographic SHA-256 hashes, timestamps, and actor IDs.
   - External auditors can verify every decision without risk of altering production data.

---

## Showcase Scenario 6: Reference Data & Integration Health
**Objective:** Prove product truth regarding ERP connections and evaluation data.

1. **Navigate to:** `http://127.0.0.1:8000/settings/reference-data`
2. **Point out:**
   - The provenance banner at the top clearly states:  
     `Reference Data Source: Static Evaluation Snapshots (Deterministic Master Data)`.
   - Distinguish that SAP S/4HANA is not connected in the local demo environment, and the application truthfully displays snapshot data rather than fabricating a fake live ERP connection.
3. **Navigate to:** `http://127.0.0.1:8000/connections`
   - Point out the 5 health pillars (Identity, Database, Object Storage, Gmail Ingestion, SAP ERP) reflecting genuine runtime connectivity status.

---

## Summary Checklist for Demonstrators

- [x] Clear opening value proposition delivered.
- [x] Operational boundary stated upfront (AP sign-off only; zero bank disbursements).
- [x] Straight-through clean invoice demonstrated (`inv_be609a16676f`).
- [x] Failed-gate override prevention demonstrated (`inv_dbfcaf77ba9b`).
- [x] Dual approval governance explained (>= ₹5,00,000 threshold).
- [x] Auditor read-only permissions shown via role switcher.
- [x] Audit trail immutability highlighted.
