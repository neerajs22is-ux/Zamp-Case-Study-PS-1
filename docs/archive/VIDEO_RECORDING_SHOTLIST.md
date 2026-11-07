# AP Command Center — 5-Minute Video Recording Director's Shotlist
## Precise Screen-by-Screen & Click-by-Click Choreography

**Target Total Duration:** 4 minutes 35 seconds to 4 minutes 45 seconds (Strictly ≤ 5:00)  
**Browser Window:** 1440x900 or 1920x1080 at 100% zoom  
**Starting URL:** `http://localhost:5173/` (Logged in as `SME AP Lead`, Dashboard visible)  
**Presenter:** Screen capture with cursor highlight enabled (webcam optional in bottom corner or audio-only)

---

## Shot-by-Shot Director's Guide

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│ TIMELINE BREAKDOWN (TOTAL: 4m 38s)                                                     │
│                                                                                        │
│ [0:00 - 0:25] Shot 1: The Operational Problem (Dashboard Overview)               25s   │
│ [0:25 - 0:55] Shot 2: Solution Architecture & Inbox Ledger                        30s   │
│ [0:55 - 2:20] Shot 3: Live Execution — The Happy Path (AP-26-009)                 85s   │
│ [2:20 - 3:30] Shot 4: Live Execution — The High-Stakes Edge Case (AP-26-011)      70s   │
│ [3:30 - 4:15] Shot 5: Engineering Architecture & Forensic Audit Ledger            45s   │
│ [4:15 - 4:40] Shot 6: Business Value & Confident Closing                          25s   │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

---

### SHOT 1: The Operational Problem & The Stakes
- **Time:** `0:00 – 0:25` (Duration: 25 seconds)
- **URL:** `http://localhost:5173/`
- **Page Displayed:** **"Today's AP Operations"** (Dashboard)
- **Starting Setup:** Logged in as `SME AP Lead` (`sme_lead@company.internal`).
- **Visual Action:**
  1. Cursor starts centered on the header: *"Today's AP Operations"*.
  2. Slowly glide the mouse across the 4 Executive KPI cards:
     - `Blocked Working Capital (₹3.42L)`
     - `Needs Your Review (4)`
     - `Ready for Sign-Off (1)`
     - `Statutory MSMED Exposure (1)`
  3. Pause briefly on the **"Urgent Exceptions"** queue showing prioritized items.
- **Presenter Focus:** Ground the evaluator in the business reality. Hundreds of invoices arrive every month; tired humans cross-referencing messy PDFs against spreadsheets make costly mistakes.
- **Transition to Next Shot:** At `0:23`, move mouse cursor to the left sidebar and hover over **"Invoices"**.

---

### SHOT 2: What I Built — Solution Architecture & Inbox
- **Time:** `0:25 – 0:55` (Duration: 30 seconds)
- **URL:** `http://localhost:5173/invoices`
- **Click Action:** Click **"Invoices"** in the left sidebar.
- **Page Displayed:** **"Invoice Inbox Ledger"**
- **Visual Action:**
  1. The invoice table displays 8 active documents.
  2. Point cursor to the faceted status tabs: `All`, `Needs Review`, `Pending Approval`, `Approved`.
  3. Highlight the status tags: `PENDING_APPROVAL`, `ACTION_REQUIRED`, `INTERNAL_APPROVAL_COMPLETE`.
  4. Move cursor down to row #2: **`AP-26-009`** (Vendor: *Asterion Precision Components Pvt Ltd*, Amount: *₹2,31,280.00*, Status: *PENDING_APPROVAL*).
- **Presenter Focus:** Explain the three-part architecture:
  1. **Multimodal AI** extracts structured line items from messy PDFs.
  2. **Deterministic Engine** validates 7 strict procurement and statutory policy gates.
  3. **Human-in-the-Loop Workbench** empowers AP professionals to review, triage, and sign off.
- **Transition to Next Shot:** At `0:53`, click directly on invoice **`AP-26-009`** (or the blue **"Review"** button).

---

### SHOT 3: Live Happy Path — Clean 3-Way Match (`AP-26-009`)
- **Time:** `0:55 – 2:20` (Duration: 85 seconds)
- **URL:** `http://localhost:5173/invoices/inv_d76401c096d0`
- **Page Displayed:** **Invoice Detail Workspace — `AP-26-009`**
- **Visual Action:**
  1. **Dual-Pane Layout (0:55–1:15):**
     - Point cursor to the left pane: Authentic original invoice PDF rendered in browser embed.
     - Point cursor to the right pane: Structured extraction and matching workspace.
     - Highlight header details: Total `₹2,31,280.00`, Vendor `Asterion Precision Components`, PO Reference `PO-26-2001`.
  2. **Procurement Verification Lineage (1:15–1:40):**
     - Under the **"Matching & Lines"** tab, point cursor to the 4 connected lineage nodes:
       `1. Billed Claim` $\to$ `2. PO Contract` $\to$ `3. Receiving GRN` $\to$ `4. Quality Inspection (QC)`.
     - Emphasize that all 4 nodes display green checkmarks and confirmed quantities (80 units ordered, 80 units delivered, 100% QC accepted).
     - Scroll down to Line Items: show unit rate comparison (Billed ₹2,450.00 vs PO ₹2,450.00, `0.00%` variance).
  3. **Deterministic 7-Point Policy Checks (1:40–1:55):**
     - Click tab: **"Policy Checks (7/7)"**.
     - Point cursor to the 7 green passing cards:
       - Gate 1: Vendor Identity Registered (Valid GSTIN checksum)
       - Gate 2: PO Authorization Valid (`PO-26-2001`)
       - Gate 3: GRN Receipt Confirmed
       - Gate 4: QC Inspection Accepted
       - Gate 5: GST Arithmetic Reconciled (₹35,280.00 tax math exact to ₹0.00)
       - Gate 6: PO Price & Quantity Tolerance (0.00% variance vs ±1.50% limit)
       - Gate 7: Duplicate Invoice Check (0 prior vouchers)
  4. **Consequence-Aware Internal Sign-Off (1:55–2:18):**
     - Scroll down to the sticky bottom decision bar.
     - Point cursor to the green **"Approve Review"** button.
     - **Click "Approve Review"**.
     - The modal pops up: **"Confirm Action: Approve Invoice (Internal Sign-Off)"**.
     - Point to the **Explicit Safety & Control Guarantees**:
       *"Does NOT execute payment or transfer bank funds. Does NOT post to SAP General Ledger. Completes internal review sign-off."*
     - Select a quick justification template: *"All 7 policy checks verified against original PDF document."*
     - **Click "Cancel"** (to preserve the clean state for repeated runs, or click Confirm if doing final take).
- **Presenter Focus:** Demonstrate how clean, legitimate invoices achieve straight-through verification with zero manual data entry, while maintaining strict financial control boundaries.
- **Transition to Next Shot:** At `2:18`, move cursor to the top header and click **"Showcase Tour"** (or click "Invoices" in sidebar and open `AP-26-011`).

---

### SHOT 4: Live Edge Case — Price Variance & Failed-Gate Enforcement (`AP-26-011`)
- **Time:** `2:20 – 3:30` (Duration: 70 seconds)
- **URL:** `http://localhost:5173/invoices/inv_dbfcaf77ba9b`
- **Click Action:** In Showcase Tour modal, click **"Launch Scenario →"** on Scenario #2 (or navigate to `/invoices/inv_dbfcaf77ba9b`).
- **Page Displayed:** **Invoice Detail Workspace — `AP-26-011`**
- **Visual Action:**
  1. **The Discrepancy (2:20–2:45):**
     - Point cursor to the orange banner: `ACTION_REQUIRED — FLAGGED_EXCEPTION`.
     - Point cursor to the Line Items table:
       - Billed Unit Rate: **₹2,850.00 / unit**.
       - Contracted PO Rate: **₹2,450.00 / unit**.
       - Variance: **+18.92% markup**! Contracted tolerance is strictly **±1.50%**.
  2. **The Broken Policy Gates (2:45–3:05):**
     - Click tab: **"Policy Checks (5/7)"**.
     - Point cursor to the two RED failing gates:
       - **Gate 4 (QC Inspection):** Red badge `FAIL` — goods lot failed quality inspection.
       - **Gate 6 (PO Price Tolerance):** Red badge `FAIL` — 18.92% variance exceeds ±1.50% threshold.
  3. **Strict Override Block & Human Exception Triage (3:05–3:28):**
     - Scroll to the sticky bottom decision bar.
     - Point cursor to the primary button: **`Approval Blocked (2 Failing)`**.
     - Show that the button is permanently disabled.
     - **Click "Raise Debit Note"** in the secondary triage options.
     - Modal pops up: **"Confirm Action: Raise Debit Note"**.
     - Highlight: It flags the invoice for commercial deduction of the overbilled delta, updates internal audit records, and requires mandatory justification.
     - **Click "Cancel"**.
- **Presenter Focus:** Prove that the system does not blindly approve invoices just because it can read them. When vendors overbill or goods fail inspection, the system physically halts approval, blocks clerk overrides, and gives the operator actionable commercial remedies.
- **Transition to Next Shot:** At `3:28`, move mouse to the left sidebar and click **"Audit"**.

---

### SHOT 5: Engineering Judgment & Immutable Forensic Ledger
- **Time:** `3:30 – 4:15` (Duration: 45 seconds)
- **URL:** `http://localhost:5173/audit`
- **Click Action:** Click **"Audit"** in the left sidebar.
- **Page Displayed:** **"Immutable Audit Ledger"**
- **Visual Action:**
  1. Point cursor to the event table showing sequential actions:
     `INVOICE_INGESTED`, `APPROVE_AP_REVIEW`, `RAISE_DEBIT_NOTE`, `ROLE_SWITCH`.
  2. Highlight the metadata columns: exact UTC timestamp, authenticated user email (`sme_lead@company.internal`), assigned role, and document SHA-256 fingerprint.
  3. **Click on the top event row**:
     - The forensic slide-over drawer smoothly slides out from the right.
     - Point cursor to the **Side-by-Side Visual Diff** showing previous state vs new state.
     - Point cursor to the **Raw JSON Event Payload** with 1-click clipboard copy.
- **Presenter Focus:** Address the core architectural philosophy:
  - **Why not let an LLM decide approvals?** LLMs are probabilistic text predictors. Accounts Payable requires deterministic arithmetic, legal contracts, and statutory compliance.
  - LLMs extract text; deterministic rule engines enforce policy; human operators retain sovereign authority.
  - The audit log is protected by database triggers that physically reject `UPDATE` and `DELETE` commands, creating an immutable regulatory trail.
- **Transition to Next Shot:** At `4:13`, close drawer and click **"Dashboard"** in the left sidebar.

---

### SHOT 6: Business Value & Confident Closing
- **Time:** `4:15 – 4:40` (Duration: 25 seconds)
- **URL:** `http://localhost:5173/`
- **Page Displayed:** **"Today's AP Operations"** (Dashboard)
- **Visual Action:**
  1. Cursor rests smoothly over the central KPI strip.
  2. Point cursor briefly to the **MSMED Statutory Compliance** counter.
  3. Bring mouse to rest calmly in the center of the viewport as you deliver the closing sentence.
- **Presenter Focus:** Summarize the strategic transformation:
  - From tedious manual data entry to exception-only triage.
  - 100% protection against duplicate payments, pricing leakage, and MSME interest penalties.
  - Complete compliance peace of mind.
- **End of Recording:** Finish speaking cleanly at `4:38`, wait 2 seconds, stop recording at `4:40`.
