# AP Command Center — Visual Redesign Priority & Implementation Matrix

**Date:** November 2026  
**Target User Persona:** Non-Technical Finance Manager, Accounts Payable Head, Executive Buyer, HR / Talent Evaluator  
**Core Guiding Rule:** *Show less. Explain better. Require fewer actions.* Non-technical comprehension in under 60 seconds.

---

## 1. Executive Prioritization Framework

To transform the AP Command Center from a developer-centric test harness into an intuitive commercial enterprise product, changes are tiered into three strict priority levels:

- **P0 (Critical / Day 1 Comprehension):** Changes that immediately remove visual chaos, prevent false cognitive alarms, eliminate developer leaks, and stop overwhelming the user with walls of text. Without P0, a non-technical buyer cannot understand the product within 60 seconds.
- **P1 (High-Impact Structural Restructure):** Architectural UI shifts that align our workspace with industry-leading commercial standards (e.g., Rossum's 50/50 split workspace and Flick AI's 4-way matching matrix).
- **P2 (Operational Polish & Advanced Velocity):** Keyboard shortcuts, quick-jump focus navigation, interactive bounding box highlighting, and executive time-savings metrics.

---

## 2. Redesign Priority Matrix

| Priority | Screen / Target Component | Current Observed Problem (Screenshot Ref) | Benchmark Reference Screenshot | Recommended UI Pattern | Expected Non-Technical Buyer Benefit | Architectural / Governance Risk & Mitigation |
|---|---|---|---|---|---|---|
| **P0** | **App Shell & Global Header** (`AppShell.tsx`, `Header.tsx`) | Global banner exposes developer evaluation scenario buttons ("Scenario 1–6", "Reset Fixtures") in the main buyer viewport (`SCR-DB-01`). | Flick AI (`SCR-DB-04`) | **Quarantine Developer Mode:** Relocate evaluation controls and test reset tools into a slide-over drawer triggered via keyboard shortcut (`Ctrl+Shift+D`) or a discreet footer link. | A clean commercial interface where first-time buyers are not confused by testing infrastructure. | **Risk:** Evaluation scenarios become hard for evaluators to trigger.<br>**Mitigation:** Provide an explicit discreet "Evaluator Tools" toggle in the bottom user profile avatar menu. |
| **P0** | **Invoice Review Workspace** (`InvoiceReviewWorkspace.tsx`) | Stacks 4 explanatory cards (`VerdictBanner`, `CaseSummaryCard`, `PolicyChecksGrouped`, `ProcurementFlow`) vertically, pushing line items 1,200px off-screen (`SCR-RW-01`). | Rossum (`SCR-RW-04`, `SCR-RW-06`) | **Collapse Explanations into a 48px Sticky Status Bar:** Consolidate status into a clean horizontal strip (*"Status: Ready for Approval — 3-Way Match Verified"*). Replace verbose text with clickable badge drawer. | User sees the original invoice PDF and line items immediately above the fold without scrolling. | **Risk:** Hiding audit policy details might impair compliance reviews.<br>**Mitigation:** Provide an on-demand slide-out "Policy Breakdown" drawer. |
| **P0** | **Approval Dialog** (`ApproveDialog.tsx`) | 600-word confirmation modal with 4 sections, multiple checkboxes, and yellow cautionary box (`SCR-AP-01`). | Rossum (`SCR-AP-05`) & Flick AI (`SCR-AP-07`) | **The 45-Word / 1-Click Confirmation:** Clean modal displaying: Vendor, Amount, Match Status, and 2 buttons: `[Cancel]` and `[Approve & Authorize Payment]`. | Eliminates decision anxiety; speeds up routine invoice approvals from 45 seconds to 3 seconds. | **Risk:** Approvers might authorize payments blindly.<br>**Mitigation:** Retain strict backend dual-approval checks for amounts $\ge ₹5,00,000$ and anti-self-approval enforcement. |
| **P0** | **Exception Engine on Scans** (`PolicyEngine.ts`, `InvoiceReviewWorkspace.tsx`) | Blurry or unreadable PDF scans cause policy engine to trigger 6 simultaneous red gate failures (missing PO, GRN, vendor, tax) (`SCR-EX-01`). | Rossum (`SCR-EX-04`) & FinBooks (`SCR-EX-07`) | **Root-Cause Triage Banner:** When OCR confidence $< 40\%$, display a single primary triage card: *"Document Unreadable: OCR could not read scan. [Upload Clearer Copy] or [Enter Details Manually]"*. Suppress downstream gate checks. | Stops alarming the user with 6 false gate failures when the only actual problem is a blurry scan. | **Risk:** Bypassing policy checks might mask true compliance issues.<br>**Mitigation:** Document cannot be approved while in unreadable triage state. |
| **P1** | **Operational Dashboard** (`TodayDashboard.tsx`) | 8 vertically stacked widgets spanning 1,450px vertical scroll; mixes test logs and exposure numbers (`SCR-DB-01`, `SCR-DB-02`). | Flick AI (`SCR-DB-03`) & Rossum (`SCR-DB-05`) | **The 3-Zone Daily Triad Dashboard:**<br>1. *Top KPI Bar:* 3 cards (*Needs Decision*, *Ready to Pay*, *Disputed*).<br>2. *Center:* High-priority action queue table.<br>3. *Right:* Straight-through automation rate. | Eliminates vertical sprawl; answers in 5 seconds: "What needs my attention right now?". | **Risk:** Loss of visibility into secondary metrics.<br>**Mitigation:** Move historical trends and secondary metrics to the Reports page (`/reports`). |
| **P1** | **Invoice Inbox Navigation** (`InvoiceInbox.tsx`) | Monolithic 10-column table with complex multi-select chips and technical status codes (`SCR-IB-01`, `SCR-IB-02`). | Flick AI (`SCR-IB-04`) & Rossum (`SCR-IB-06`) | **Pre-Filtered Operational Tabs:** Replace multi-select filters with 4 pre-computed tabs:<br>`[ ⚠️ Needs Attention (N) ]`<br>`[ ⏱️ Ready for Approval (N) ]`<br>`[ ⏳ Waiting on Others (N) ]`<br>`[ ✅ Completed (N) ]`. | Zero-click workload segmentation; users click only the queue they are responsible for. | **Risk:** Custom queries become harder to run.<br>**Mitigation:** Keep an "All Invoices" tab with standard keyword search. |
| **P1** | **Reconciliation Table** (`LineItemsTable.tsx`, `ProcurementVerificationFlow.tsx`) | Abstract 4-node pipeline flow is visually disconnected from line-item table below (`SCR-RC-01`, `SCR-RC-02`). | Flick AI (`SCR-RC-04`) & Rossum (`SCR-RC-07`) | **Consolidated 4-Way Reconciliation Table:** Consolidate PO, GRN, and Inspection directly into table columns:<br>`[ Item | Billed | Ordered | Delivered | Inspected | Variance | Action ]`. | Complete matching story in one row: *Billed 50, but warehouse received 45*. | **Risk:** Table width might exceed viewport on small laptop screens.<br>**Mitigation:** Use compact numerical format and responsive horizontal scroll. |
| **P1** | **Dual Approval Stepper** (`DualApprovalCard.tsx`, `ApproveDialog.tsx`) | High-value threshold ($\ge ₹5,00,000$) requirement is buried in modal text rather than visible as a workflow milestone (`SCR-AP-01`). | Flick AI (`SCR-AP-07`) & Rossum (`SCR-AP-06`) | **Visual Progressive Approval Stepper:** Display a 2-step badge for invoices $\ge ₹5,00,000$:<br>Step 1: *Primary Reviewer [Completed]*<br>Step 2: *Controller Sign-Off [Pending]*. | Makes dual-governance obvious and transparent before clicking approve. | **Risk:** Backend rejects unauthorized single approval.<br>**Mitigation:** Button explicitly states "Submit for Controller Review" on Step 1. |
| **P2** | **Exception Jump Navigation** (`InvoiceReviewWorkspace.tsx`) | Users must hunt through multiple tabs and cards to locate which line failed validation (`SCR-EX-01`). | Rossum (`SCR-EX-04`, `SCR-EX-05`) | **Sticky Jump-to-Fix Error Pill:** Sticky badge in workspace header (`⚠️ 1 Line Variance`). Clicking it smoothly scrolls and focuses the discrepant table cell. | Saves 30–60 seconds per exception; guides non-technical users directly to the fix. | **Risk:** Browser auto-scroll jumping too abruptly.<br>**Mitigation:** Use smooth CSS scrolling (`behavior: 'smooth'`) and brief gold highlight ring. |
| **P2** | **Human-Language Audit Ledger** (`AuditTrail.tsx`, `AuditLedger.tsx`) | Event timeline displays raw SHA-256 strings and technical constants like `INVOICE_STATE_TRANSITION_EVAL_RUN` (`SCR-RP-01`). | Flick AI (`SCR-RP-03`) | **Natural Language Activity Storytelling:** Translate technical diffs into plain sentences (*"Anita Sharma corrected Line 1 qty from 50 to 45"*). Cryptographic SHA hash collapsed into a "Proof [Copy]" pill. | Makes audit trail readable by business executives, external auditors, and controllers. | **Risk:** Loss of strict cryptographic evidence presentation.<br>**Mitigation:** Full raw JSON and SHA hash chain remain viewable in click-to-expand details drawer. |
| **P2** | **Executive Efficiency Metrics** (`Reports.tsx`, `TodayDashboard.tsx`) | System displays raw record counts but fails to quantify time and money saved (`SCR-RP-02`). | Rossum (`SCR-RP-06`) | **ROI & Turnaround Scorecard:** Display executive metric tile: *"Average Processing Velocity: 1.8 mins / invoice (Industry benchmark: 5 days)"*. | Direct business proof for CFOs and enterprise buyers evaluating software ROI. | **Risk:** Calculation methodology challenged by buyers.<br>**Mitigation:** Add tooltip detailing exact formula based on intake-to-approval timestamp deltas. |

---

## 3. Strict Architectural & Governance Invariants

Any UI implementation based on this priority matrix must preserve the following non-negotiable enterprise controls:

1. **Dual Approval Boundary ($\ge ₹5,00,000$):**
   - Invoices with total value equal to or exceeding ₹5,00,000 strictly require two independent approvals: Primary AP Specialist/Manager followed by Controller sign-off.
   - The UI simplification must never bypass or collapse this into a single click for high-value records.
2. **Anti-Self-Approval Enforcement:**
   - Any user who modifies, adjusts, or corrects a line item (e.g. altering quantity or unit price) is legally barred from executing final approval for that invoice.
   - The UI must visually reflect this by replacing the "Approve" button with *"Awaiting Secondary Sign-Off (You modified Line 1)"*.
3. **Deterministic Mathematical Tolerances:**
   - Quantity tolerance is strictly **0.00%** (zero tolerance for missing physical units).
   - Price tolerance is strictly $\le \mathbf{1.50\%}$.
   - These gates are evaluated deterministically in the backend engine; the UI only reflects their status.
4. **Auditor Read-Only Boundary:**
   - Users logged in under the `Auditor` role cannot edit cells, trigger approvals, or execute mutations (backend strictly enforces HTTP 403 Forbidden).
   - The UI must visually disable all editing and approval controls when an Auditor session is active.
5. **Cryptographic Append-Only Audit Integrity:**
   - Every mutation, correction, approval, and rejection must generate an immutable, SHA-256 hashed audit log event.
   - While the UI humanizes the presentation for readability, the underlying cryptographic hashes must remain intact and exportable.
6. **Zero Direct Disbursement:**
   - The AP Command Center is an accounts payable matching, verification, and governance command center. It reconciles, verifies, and authorizes invoices for payment. It does **not** disburse funds directly to bank rails or mutate external ERP general ledgers.

---

## 4. Implementation Phasing & Recommended Execution Order

```
+---------------------------------------------------------------------------------------------------+
| THREE-PHASE IMPLEMENTATION ROADMAP                                                                |
+---------------------------------------------------------------------------------------------------+
| PHASE 1: IMMEDIATE COMPREHENSION (P0)                                                             |
| - Relocate Developer Mode / Evaluation Runner to slide-over drawer (Ctrl+Shift+D).                |
| - Replace 4 stacked explanation banners in Review Workspace with 48px sticky verdict bar.         |
| - Replace 600-word approval modal with 45-word lean confirmation dialog.                          |
| - Add root-cause triage banner for unreadable scans (suppress 6 false red gate checks).            |
| -> Outcome: First-time non-technical buyer understands the product in under 60 seconds.          |
+---------------------------------------------------------------------------------------------------+
| PHASE 2: WORKSPACE & INBOX RESTRUCTURE (P1)                                                       |
| - Implement 3-card Daily Triad dashboard on `/` (Needs Decision, Ready to Pay, Blocked).          |
| - Implement 4 operational inbox tabs on `/inbox` (Needs Attention, Ready, Waiting, Completed).    |
| - Consolidate PO, GRN, and Inspection into 4-Way Reconciliation Table columns.                    |
| - Implement visual 2-step stepper for invoices >= ₹5,00,000.                                      |
| -> Outcome: Workspace matches Rossum & Flick AI best-in-class information density and flow.       |
+---------------------------------------------------------------------------------------------------+
| PHASE 3: ADVANCED VELOCITY & POLISH (P2)                                                          |
| - Add sticky Jump-to-Fix error navigation badge.                                                  |
| - Translate raw audit event timeline into human-language sentences with expandable SHA hashes.    |
| - Add Executive Processing Velocity ROI card to reporting views.                                  |
| -> Outcome: Enterprise-grade polish and delight for non-technical finance leaders.                |
+---------------------------------------------------------------------------------------------------+
```
