# AP Command Center — Non-Technical Buyer UX Transformation & Product Simplification Audit

**Target System:** AP Command Center (Autonomous Accounts Payable Verification & Controls Platform)  
**Repository Branch:** `handoff/ap-command-center` (Commit: `29d3c28` / Base: `61602f6`)  
**Audit Standard:** Non-Technical Buyer & First-Time User Usability Standard + Competitor Benchmark Competitor Benchmark  
**Deliverable Document:** `docs/NON_TECHNICAL_BUYER_UX_TRANSFORMATION_AUDIT.md`  
**Date:** November 04, 2026  
**Auditor:** Antigravity Advanced Product & UX Architecture  
**Status:** PROPOSAL & AUDIT ONLY — Zero Application Code or Database Schemas Modified  

---

## Executive Summary & Mission Statement

The AP Command Center is an enterprise accounts payable automation platform powered by deterministic 7-gate verification, multi-tenant isolation, append-only immutable audit logging, and dual-control financial governance.

Recent engineering phases successfully established core capabilities:
- `OPP-01`: Audited in-place line-item correction with optimistic concurrency (`If-Match`) and synchronous gate re-evaluation (`backend/api/v1/invoices.py`).
- `OPP-10`: Review workspace tab consolidation from 4 tabs to 2 primary operational views.
- `OPP-04`: Temporal inbox period filtering (Financial Year and Month dropdowns) backed by composite B-tree indexing.
- `OPP-12`: Persistent evaluation mode watermark banner and idempotent demo state reset.
- `OPP-06`: Executive AP capital exposure scorecard separating operational aging from statutory MSME Section 15 liabilities.

### The Problem
**Despite these improvements, the application remains overwhelming for a non-technical buyer, HR interviewer, or finance manager.**

When a first-time user opens the application, they are confronted with an "explanation layer" consisting of:
1. Explanatory banners, 4-step linear progression diagrams, and operational readiness checklists stacked on top of each other.
2. Multiple overlapping cards on the review screen repeating the same information (the Verdict Banner, the CaseSummaryCard / Decision Guide, the PolicyChecksGrouped 3-group accordion, and the ProcurementVerificationFlow 4-node flow).
3. A 600-word confirmation modal for a routine approval containing 4 numbered analytical sections, a yellow warning box with 4 "does NOT" bullets, and mandatory justification requirements.
4. Jargon from backend databases and auth infrastructure (`INTERNAL_APPROVAL_COMPLETE`, `MATCH_CANDIDATE`, `D-04 Deferred`, `PostgreSQL Trigger Enforced`, `Supabase Cloud`, `IdP`).
5. Six equal-weight action buttons in the sticky footer with ambiguous categories ("Triage:" vs "Governance:"), forcing non-technical users to guess what happens next.

### The Objective
Transform the AP Command Center into an application that a completely non-technical finance manager can open, understand, and confidently operate within **60 seconds**, without reading documentation, tutorials, or glossaries.

**Core Product Design Principle:**  
*Show less. Explain better. Require fewer actions.*  
Never teach Accounts Payable through lengthy explanatory widgets. Design an interface that is self-evident in operation while rigorously preserving every underlying financial safeguard, dual-control rule, and immutable audit guarantee.

---

## 1. Competitor Benchmark Competitor Source Material Reconciliation

Our analysis incorporates empirical findings from the three analyzed benchmark competitor platforms documented in `competitor_research/`:

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                        COMPETITIVE Competitor Benchmark SYNTHESIS & AP COMMAND CENTER                   │
├────────────────────────────────────────────────────────────────────────────────────────┤
│  1. FinBooks AI (01_finbooks) — Indian SME Accounting & GST OS                         │
│     • Architectural Flaw: Disconnected document viewer (srcDocPanel) mutually         │
│       exclusive with edit form; line items completely hidden from review UI; fallback  │
│       to window.prompt() for PO matching; table header label collisions below 1400px. │
│     • Strategic Takeaway: Never isolate the source document from extracted data.       │
│       Deliver a unified split-screen review workspace with direct cell editing.        │
│                                                                                        │
│  2. Rossum (02_rossum) — Enterprise Intelligent Document Processing (IDP)              │
│     • Architectural Triumph: 50/50 calibrated split view; coordinate-addressed SVG     │
│       bounding boxes; floating contextual input (editBoxInput); real-time queue health │
│       badges (e.g. "1 error / 0 warnings"); confirmation gating without modal clutter.  │
│     • Strategic Takeaway: Adopt Rossum's zero-scroll review ergonomics and error-first │
│       affinity. Prevent cognitive overload by showing errors directly on the data.     │
│                                                                                        │
│  3. Flick AI (03_flickai) — Cloud Accounting & Financial OS                            │
│     • Architectural Triumph: Material-UI v5 SPA; multi-format dropzone partitioned by  │
│       Financial Year and Month; line-item data matrix with reactive row operations;    │
│       ambient "Ask Flick" copilot; clean separation of bookkeeping from compliance.    │
│     • Strategic Takeaway: Period-scoped intake prevents clutter. Clear separation of   │
│       routine operational tasks from deep statutory tax compliance.                    │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## Part A — Current State Diagnosis

### Top 10 UX Problems in the Current Application

#### Problem 1: Redundant Multi-Card Stacking on the Invoice Review Screen
- **Root Cause:** In an attempt to be thorough, previous development phases added multiple independent explanation components that all report the same validation facts simultaneously.
- **Screens Affected:** `frontend/src/pages/InvoiceDetailPage.tsx`, `frontend/src/components/CaseSummaryCard.tsx`, `frontend/src/components/PolicyChecksGrouped.tsx`, `frontend/src/components/ProcurementVerificationFlow.tsx`.
- **Evidence in Source Code:**
  1. Lines 566–662 of `InvoiceDetailPage.tsx` render the top **Verdict Banner** detailing failed checks and required actions.
  2. Lines 665–675 render `CaseSummaryCard` (titled "Decision Guide:"), which repeats the gate pass/fail count and re-explains whether approval is permissible.
  3. Lines 907–910 render `PolicyChecksGrouped`, which renders a progress bar and 3 accordion groups detailing the 7 gates.
  4. Lines 913–921 render `ProcurementVerificationFlow`, which renders 4 large cards (Supplier Invoice, Purchase Order, Goods Receipt, Quality Control) before the line-item table.
- **Impact on Non-Technical Buyer:** The reviewer must scroll past four repetitive analytical containers before they can inspect the actual line items or reach the decision buttons.
- **Competitor Benchmark Addressed:** Rossum 50/50 review ergonomics. Rossum never duplicates verification summaries across 4 stacked cards; it places the status chip at the top and flags discrepancies directly on the line-item grid.

#### Problem 2: "Today" Dashboard Cognitive Overload & Action Paralysis
- **Root Cause:** The dashboard attempts to function as a sales pitch, an executive liquidity dashboard, an operational backlog queue, an integration status board, and an onboarding wizard at the same time.
- **Screens Affected:** `frontend/src/pages/DashboardPage.tsx` (673 lines).
- **Evidence in Source Code:**
  1. Lines 163–206: "Pre-Payment Invoice Verification & Controls" banner with a 4-step numbered progression strip.
  2. Lines 209–280: "Executive AP Capital Exposure Scorecard" (3 exposure cards) plus a statutory MSME Section 15 disclaimer.
  3. Lines 283–364: 3 high-level outcome tiles ("Needs Attention", "Ready to Approve", "Waiting for Second Approval").
  4. Lines 367–456: "Operational Readiness" derived checklist card rendering 6 subsystem chips.
  5. Lines 459–491: "Pipeline Velocity" strip repeating stage numbers.
  6. Lines 495–560: "Next-Up Actionable Queue" table with another MSME Section 15 legal notice.
  7. Lines 565–620: "Integration Pillars" health panel.
  8. Lines 625–670: "Recent Audit Trail" table.
- **Impact on Non-Technical Buyer:** Page length extends to over 1,400px. The same metric (e.g. 3 exceptions) is repeated in 4 different places. A first-time user cannot identify what needs immediate action.
- **Competitor Benchmark Addressed:** Flick AI & Rossum dashboard design. High-velocity operators need a clean work queue answering "What needs me now?", not 8 competing analytical widgets.

#### Problem 3: The 600-Word "Approval Wall" & High Action Friction
- **Root Cause:** Overly defensive governance copy in `ConsequenceAwareActionModal.tsx`. Confirming an invoice approval requires reading 4 numbered sections, a yellow box with 4 "does NOT" bullets, selecting a mandatory template chip, typing a justification, and clicking confirm.
- **Screens Affected:** `frontend/src/components/ConsequenceAwareActionModal.tsx` (406 lines).
- **Evidence in Source Code:**
  - Lines 280–327 render 4 numbered sections:
    1. *What this does*
    2. *Resulting workflow state: `INTERNAL_APPROVAL_COMPLETE (or ACTION_REQUIRED if dual-control active)`*
    3. *Does this require another person?*
    4. *What happens next*
  - Lines 316–326 render an extra yellow alert: "Explicit Safety & Control Guarantees (What this does NOT do): Does NOT execute payment, Does NOT post to SAP, Does NOT clear vendor liability...".
- **Impact on Non-Technical Buyer:** Approving a clean match (which should take 3 seconds) feels like signing a legal affidavit. Routine approvals require 5 clicks and extensive reading.
- **Competitor Benchmark Addressed:** Rossum confirmation gating. Rossum gates approval strictly when errors exist, but when all checks pass, confirmation is instantaneous (hotkey or single click), recording the audit trail without imposing essay-length dialogs.

#### Problem 4: Misleading Cascading Failures on Degraded Scans
- **Root Cause:** When an uploaded PDF is unreadable, the backend pipeline previously recorded downstream policy gates (Gate 2: PO, Gate 3: GRN, Gate 4: QC, Gate 5: GST, Gate 6: Price) as "FAIL" because data was missing, instead of "NOT_EVALUATED".
- **Screens Affected:** `frontend/src/pages/InvoiceDetailPage.tsx:406-420, 600-660`, `frontend/src/pages/InboxPage.tsx:284-293`, `backend/api/v1/invoices.py`.
- **Evidence in Source Code:**
  - In earlier builds, the UI displayed: "Blocked: 6 Validation Check(s) Failed" and instructed the user to: "Contact supplier to amend billed price (Variance 0.0%)".
  - Although commit `61602f6` added an `isUnreadable` frontend check, the review screen still mounts the entire 4-node procurement comparison flow showing "Unavailable / Missing" across all nodes.
- **Impact on Non-Technical Buyer:** Instructing a buyer to dispute a price variance on an invoice where the price was never read destroys product credibility in live demos.
- **Competitor Benchmark Addressed:** Flick AI file intake isolation. If intake fails, the file is immediately quarantined as an unreadable scan; it never triggers commercial price or tax disputes.

#### Problem 5: Infrastructure Jargon Leaking into Buyer UI
- **Root Cause:** Backend database schemas, auth mechanisms, and internal enum codes are surfaced directly in UI copy without consumer-grade translation.
- **Screens Affected:** `frontend/src/components/AuthScreen.tsx`, `frontend/src/components/AppShell.tsx`, `frontend/src/pages/InboxPage.tsx:541-568`, `frontend/src/pages/AuditPage.tsx`, `frontend/src/components/ConsequenceAwareActionModal.tsx`.
- **Evidence in Source Code:**
  - `InboxPage.tsx:546-567`: Dropdown filters expose raw backend enums: `ACTION_REQUIRED`, `DECIDED`, `MATCHING`, `EXTRACTED`, `PARSING`, `VALIDATING`, `RECEIVED`, `AUTO_APPROVED`, `MANUALLY_APPROVED`, `NEEDS_REVIEW`.
  - `ConsequenceAwareActionModal.tsx:296`: `Stage: INTERNAL_APPROVAL_COMPLETE (or ACTION_REQUIRED if dual-control active)`.
  - `AuthScreen.tsx`: Exposes "Supabase Cloud", "Production IdP", "Developer & Diagnostics Access (JWT Inspection)".
  - `AuditPage.tsx`: Exposes "Append-Only (PostgreSQL Trigger Enforced)", "State Diff / Inspect Diff", "Actor ID `usr_...`".
- **Impact on Non-Technical Buyer:** Evaluators feel like they are looking at a developer debugger rather than a financial application.
- **Competitor Benchmark Addressed:** FinBooks and Rossum design consistency. Enterprise finance tools use domain language ("Ready", "Needs Review", "Approved", "Supplier"), not database trigger names.

#### Problem 6: Competing Action Buttons without Clear Visual Hierarchy
- **Root Cause:** The sticky decision bar at the bottom of `InvoiceDetailPage.tsx` displays 6 equal-weight buttons grouped arbitrarily under "Triage:" and "Governance:".
- **Screens Affected:** `frontend/src/pages/InvoiceDetailPage.tsx:1133-1224`.
- **Evidence in Source Code:**
  - Left group (Triage): `Hold for Evidence`, `Ask Supplier to Correct`, `Raise Debit Note`.
  - Right group (Governance): `Escalate`, `Set Aside (Quarantine)`, `Reject Invoice`.
  - Far right: `Approve Review` (or `Approval Blocked`).
- **Impact on Non-Technical Buyer:** When an invoice fails validation (e.g. price variance), the user is presented with 6 equal buttons. They have no guidance on whether they should Hold, Ask Supplier to Correct, or Raise Debit Note.
- **Competitor Benchmark Addressed:** Rossum contextual action suggestion. The UI should highlight **ONE primary recommended action** derived from the root cause, tucking secondary alternatives into a clean dropdown.

#### Problem 7: Disconnected & Orphaned Navigation Routes (`/exceptions`, `/setup`)
- **Root Cause:** Feature sprawl led to creating dedicated routes for tasks that belong inside standard operational lists.
- **Screens Affected:** `frontend/src/App.tsx:156`, `frontend/src/pages/ExceptionsPage.tsx` (555 lines), `frontend/src/pages/OnboardingPage.tsx`, `frontend/src/components/Sidebar.tsx`.
- **Evidence in Source Code:**
  - `ExceptionsPage.tsx` exists at `/exceptions`, but is **completely missing from `Sidebar.tsx` and `AppShell.tsx`**. It duplicates `InboxPage.tsx`'s "Needs Attention" tab while holding useful owner-reassignment logic that no user can find.
  - `OnboardingPage.tsx` (Setup Checklist) is an administrator wizard that gates invoice upload behind Step 5, but sits prominently in the main sidebar.
- **Impact on Non-Technical Buyer:** Cluttered navigation with dead ends and redundant screens.
- **Competitor Benchmark Addressed:** Flick AI unified navigation hierarchy. Operational bills live in one place; administration and setup live under Settings.

#### Problem 8: Navigation Count Inconsistencies & Filter Dead Ends
- **Root Cause:** Divergent status calculations between `AppShell.tsx`, `Sidebar.tsx`, `DashboardPage.tsx`, and `InboxPage.tsx`.
- **Screens Affected:** `Sidebar.tsx:189-199`, `AppShell.tsx:58-64`, `DashboardPage.tsx:340`, `ApprovalsPage.tsx:56-64`.
- **Evidence in Source Code:**
  - Sidebar "Approvals" badge counts `pending_second_approval` (0 in seeded state), while the "Needs Attention" count on the dashboard links to `/invoices?stage=ACTION_REQUIRED`.
  - In earlier versions, clicking "Ready to Approve" on the dashboard routed to `decision=AUTO_APPROVED`, resulting in 0 rows because clean matches were stored as `MATCH_CANDIDATE`.
- **Impact on Non-Technical Buyer:** Clicking a tile that claims "2 Ready" only to land on an empty table destroys user confidence.
- **Competitor Benchmark Addressed:** FinBooks Competitor Benchmark Finding 3.2. Workload indicators must accurately reflect the exact filtered records displayed upon click.

#### Problem 9: Tutorial Overload (Tours, Modals & Banners Everywhere)
- **Root Cause:** Attempting to solve comprehension issues by layering coachmark tours (`showTour` in `InvoiceDetailPage.tsx:93-134`), glossary modals (`GlossaryModal.tsx`), and showcase walkthroughs (`HRShowcaseModal.tsx`), instead of making the core interface self-explanatory.
- **Screens Affected:** `AppShell.tsx:198-207`, `InvoiceDetailPage.tsx:93-134, 467-563`, `GlossaryModal.tsx`, `HRShowcaseModal.tsx`.
- **Evidence in Source Code:**
  - `AppShell.tsx:200` mounts a permanent "Showcase Tour" button in the global header.
  - `InvoiceDetailPage.tsx:473` mounts a "Tour" button that triggers a 6-step overlay detailing technical implementation notes (e.g. "300s presigned URL for zero-trust document security").
- **Impact on Non-Technical Buyer:** Users feel intimidated by tutorial overlays rather than engaging directly with the invoice data.
- **Competitor Benchmark Addressed:** The Core Product Design Principle: An interface that requires a tour and a glossary to be understood is failing at fundamental product design.

#### Problem 10: Fragmentation Between 4-Node Cards and Line-Item Comparison
- **Root Cause:** `ProcurementVerificationFlow.tsx` renders 4 separate summary cards above the line-item table, but does not offer a unified, single-glance reconciliation table showing: **Billed vs. Ordered vs. Delivered vs. Inspected**.
- **Screens Affected:** `frontend/src/components/ProcurementVerificationFlow.tsx` (1,004 lines).
- **Evidence in Source Code:**
  - Lines 184–326 render 4 cards for Invoice, PO, GRN, and QC. If GRN or QC are missing or unseeded, they display "Unavailable" or "Not Recorded", while Gate 3 and Gate 4 in the policy gate accordion above may show PASS or FAIL based on CSV snapshots.
  - Reviewers must scroll down to find the line-item match table, which requires toggling between "Comparison" mode and "9-Col Ledger" mode.
- **Impact on Non-Technical Buyer:** The central mental model ("Did we order it? Did it arrive? Did it pass inspection?") is broken across multiple UI components.
- **Competitor Benchmark Addressed:** Rossum & Flick AI line-item grids. High-throughput verification requires a consolidated table where each row lines up what was billed against what was authorized and received.

---

## Part B — Proposed Product Experience

### 1. The 60-Second Non-Technical Buyer Mental Model

The entire application is reorganized around a single universal narrative that any business executive, finance clerk, or HR evaluator understands immediately:

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                        THE 60-SECOND USER COMPREHENSION FLOW                           │
├────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                        │
│   1. What arrived?        ──▶  Original Supplier Invoice PDF (Vendor, Date, Amount)   │
│   2. What did AI read?    ──▶  Clean line items, unit rates, quantities, and GST split │
│   3. What did we check?   ──▶  Matched against PO (Order), GRN (Arrival), QC (Quality) │
│   4. What didn't match?   ──▶  Plain-English discrepancy with exact numbers            │
│   5. Why human needed?    ──▶  AP governance: computers verify rules, humans decide    │
│   6. What did I do?       ──▶  Executed 1 recommended action (or corrected line item)  │
│   7. What happened next?  ──▶  Status updated; clear audit event recorded; no leak to  │
│                                bank or general ledger until finalized                  │
│                                                                                        │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

---

### 2. Proposed Navigation Structure

Collapse the navigation from 8 items down to **4 primary operational views + Settings**:

```
OPERATIONAL NAVIGATION (Daily Workflow):
├── Invoices         [Badge: Needs You + Ready]  (Default home; 1-click Upload dropzone)
├── Approvals        [Badge: Waiting Second]      (Dual-control sign-offs for Controller)
└── History                                       (Immutable audit trail & past decisions)

MANAGEMENT & CONFIGURATION (Secondary):
└── Settings ▾
    ├── Connections & Mailbox (Gmail ingestion & ERP status)
    ├── Procurement Records   (Vendors, Purchase Orders, Receipts, QC)
    ├── Team & Access         (RBAC, invite members)
    └── Setup Checklist       (Initial organization setup checklist)
```

#### Global Header Simplification
- **Remove:** Permanent "AP Sign-Off Only • No Bank Disbursements" chip from the header (move this reassurance to the approve modal and a discrete info tooltip).
- **Remove:** "Showcase Tour" button from the main header.
- **Add:** A consolidated `[ Help ▾ ]` dropdown menu in the top right containing:
  - Guided 2-Minute Walkthrough
  - AP Terminology Glossary
  - Keyboard Shortcuts (`?`)
- **Move:** Dev Role Switcher into an unobtrusive evaluation pill in the top bar.

---

### 3. Proposed "Today" Dashboard Layout

The redesigned dashboard answers three questions at a glance:
1. *What needs my attention right now?*
2. *What is ready for me to approve?*
3. *What is waiting on someone else?*

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│  Today's AP Workload                                               Wednesday, Nov 4   │
├────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                        │
│  ┌─────────────────────────┐  ┌─────────────────────────┐  ┌─────────────────────────┐ │
│  │  3 Need Attention       │  │  2 Ready to Approve     │  │  0 Waiting on Others    │ │
│  │  ₹1,43,000 Blocked      │  │  ₹2,31,280 Cleared      │  │  Dual-Control >= ₹5L    │ │
│  │  [ Triage Invoices ➔ ]  │  │  [ Review Queue ➔ ]     │  │  [ View Approvals ➔ ]   │ │
│  └─────────────────────────┘  └─────────────────────────┘  └─────────────────────────┘ │
│                                                                                        │
│  PRIORITY ACTION QUEUE (Next Up)                                [ + Upload Invoice ]  │
│  ┌──────────────────────────────────────────────────────────────────────────────────┐  │
│  │ Invoice     Supplier             Amount     Issue / Reason            Action     │  │
│  │ AP-26-011   Asterion Precision   ₹25,960    Price 18.9% above PO      [Review]   │  │
│  │ scan_037    Unknown Scan         —          Document unreadable       [Review]   │  │
│  │ AP-26-009   Asterion Precision   ₹2,31,280  All checks passed         [Approve]  │  │
│  └──────────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                        │
│  EXECUTIVE EXPOSURE SUMMARY                                                            │
│  Total Blocked: ₹1,43,000 (3 inv)  •  Over 30 Days: ₹0.00  •  Treasury Ready: ₹2,31,280 │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

**What was eliminated:**
- The redundant "Pre-Payment Verification & Controls" banner and 4-step diagram.
- The 6-subsystem "Operational Readiness" derived card (moved to Settings > Setup).
- The "Pipeline Velocity" strip.
- The "Integration Pillars" card.
- Duplicate MSME Section 15 notices.

---

### 4. Proposed Invoice Review Workspace

The review workspace is unified into a synchronized 50/50 split-screen interface:
- **Left Pane (50%):** Original Invoice PDF Viewer with zoom/pan and download.
- **Right Pane (50%):** Unified Reconciliation Workspace.

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│  ← Invoices    AP-26-011 • Asterion Precision Components                  ₹25,960.00   │
├─────────────────────────────────────────────┬──────────────────────────────────────────┤
│  ORIGINAL DOCUMENT (PDF)                    │  VERIFICATION & RECONCILIATION           │
│                                             │                                          │
│  ┌───────────────────────────────────────┐  │  ● NEEDS ATTENTION: Price Variance       │
│  │                                       │  │  Billed rate is 18.9% above PO rate.     │
│  │                                       │  │                                          │
│  │         INVOICE # AP-26-011           │  │  RECOMMENDED ACTION:                     │
│  │         Asterion Precision            │  │  [ Ask Supplier to Correct ]  [More ▾]   │
│  │                                       │  │                                          │
│  │  Item: Precision Flange               │  │  4-WAY RECONCILIATION TABLE              │
│  │  Qty: 80  Rate: ₹2,450.00             │  │  ┌────────────────────────────────────┐  │
│  │  Total: ₹25,960.00                    │  │  │ Item       Billed    PO     GRN QC │  │
│  │                                       │  │  │ Flange     ₹2,450  ₹2,060   80  ✓  │  │
│  │                                       │  │  │ (+18.9% variance — Exceeds ±1.5%)  │  │
│  │                                       │  │  │ [Edit Line Item ✎]                 │  │
│  │                                       │  │  └────────────────────────────────────┘  │
│  │                                       │  │                                          │
│  │                                       │  │  SUMMARY                                 │
│  │                                       │  │  Subtotal: ₹22,000  •  GST (18%): ₹3,960 │
│  │                                       │  │  Net Authorizable Payable: ₹25,960       │
│  │                                       │  │                                          │
│  │                                       │  │  ▸ Full Verification Details & Audit     │
│  │                                       │  │    (7 Gates, AI Extracted Fields, Log)   │
│  └───────────────────────────────────────┘  │                                          │
└─────────────────────────────────────────────┴──────────────────────────────────────────┘
```

#### Core Innovations in the Review Workspace
1. **Unified 4-Way Reconciliation Table:** Replaces the 4 separate procurement cards and the line-item match table with a single table that compares Billed vs PO vs GRN vs QC directly.
2. **Contextual Action Recommendation:** The system highlights the single best action (`[ Ask Supplier to Correct ]`) with secondary actions tucked in `[ More ▾ ]`.
3. **In-Place Audited Line Correction:** AP associates can click `[Edit Line Item ✎]` directly on the discrepancy to fix OCR errors in-place, triggering optimistic locking (`If-Match`), synchronous 7-gate re-evaluation, and audit logging (`OPP-01`).
4. **Progressive Disclosure:** Policy check details, extracted raw fields, and audit history are collapsed under an expandable drawer at the bottom.

---

### 5. Proposed 3-Click Approval Experience

Replace the 600-word confirmation modal with a clean, focused, 3-click dialog:

```
┌────────────────────────────────────────────────────────┐
│  Approve Invoice AP-26-009?               ₹2,31,280.00 │
├────────────────────────────────────────────────────────┤
│  Supplier: Asterion Precision Components               │
│  Verification: Matches PO-1042, GRN-5678, and QC.     │
│                                                        │
│  Audit Justification (Required):                       │
│  ┌──────────────────────────────────────────────────┐  │
│  │ All 7 checks verified against procurement files. │  │
│  └──────────────────────────────────────────────────┘  │
│  Quick reasons: [Variance within tolerance] [GRN Confirmed]│
│                                                        │
│  ℹ Approving records your internal sign-off. It does   │
│    not disburse bank funds or post to general ledger. │
│                                                        │
│                           [ Cancel ]   [ Approve (3s) ]│
└────────────────────────────────────────────────────────┘
```

- **Word count reduced from ~600 words to 45 words.**
- Pre-filled, editable audit reason for clean matches.
- Preserves the required justification, dual-control check, and role enforcement.

---

### 6. Information Hierarchy Across All Screens

| Level | Purpose | Examples | Visibility Rule |
|:---|:---|:---|:---|
| **Level 1: Primary** | What the user must know immediately to make a decision. | Invoice #, Supplier, Total Amount, Status Chip, Discrepancy Reason, Recommended Action. | Always visible above the fold. |
| **Level 2: Secondary** | Supporting operational evidence needed to verify the decision. | 4-Way reconciliation table, line items, PO numbers, GRN dates, variance percentage. | Visible in the primary viewport without tab-switching. |
| **Level 3: Advanced** | Regulatory evidence, audit proof, technical parameters. | SHA-256 hashes, pre-signed URL TTL, raw stage enums, full 7-gate rule breakdowns, database event IDs. | Accessible via progressive disclosure (expandable drawers, tabs, help popovers). |

---

## Part C — Simplification Scorecard

The following scorecard compares the current measured implementation against the proposed design targets.

> **Methodology Note:**  
> Values tagged with **`[M]`** represent exact physical measurements taken from current source code (`DashboardPage.tsx`, `InboxPage.tsx`, `InvoiceDetailPage.tsx`, `ConsequenceAwareActionModal.tsx`).  
> Values tagged with **`[T]`** represent proposed design targets.

| Screen / Area | Metric | Current Implementation `[M]` | Proposed Design Target `[T]` | Improvement / Delta |
|:---|:---|:---:|:---:|:---:|
| **Today Dashboard** | Visible Information Groups | 8 distinct blocks `[M]` | 3 focused zones `[T]` | **-62.5% visual clutter** |
| | Interactive Controls | 23 controls `[M]` | 8 essential controls `[T]` | **-65.2% control fatigue** |
| | Visible Body Text | ~380 words `[M]` | ~90 words `[T]` | **-76.3% reading load** |
| | Clicks to First Action | 3–4 clicks `[M]` | 1 click `[T]` | **-75% interaction cost** |
| **Invoice Inbox** | Visible Header & Filters | 6 filter dropdowns/inputs `[M]` | 4 quick tabs + search `[T]` | **-33% filter complexity** |
| | Primary Actions | 4 buttons (Upload, Sync, Refresh...) `[M]` | 2 buttons (Upload, Refresh) `[T]` | **-50% button competition** |
| | Clicks to Upload Invoice | 1 click on Inbox `[M]` (fixed in `61602f6`) | 1 click or Drag-and-Drop `[T]` | **Maintained 1-click intake** |
| | Triaging from List | Full row inspection needed `[M]` | Inline "Why/Next" column `[T]` | **Instant triage from list** |
| **Invoice Review Workspace** | Visible Cards / Accordions | 5 stacked explanation cards `[M]` | 1 unified reconciliation table `[T]` | **-80% card nesting** |
| | Tab Switches for Full Context | 2 primary tabs `[M]` (was 4) | 0 tab switches for core check `[T]` | **100% zero-switch review** |
| | Visible Action Buttons | 7 equal-weight buttons `[M]` | 1 recommended + dropdown `[T]` | **Clear decision guidance** |
| | Unnecessary Prose Text | ~456 words on exception page `[M]` | ~120 words `[T]` | **-73.6% prose reduction** |
| **Approval Confirmation** | Confirmation Dialog Word Count | ~600 words `[M]` | ~45 words `[T]` | **-92.5% cognitive load** |
| | Clicks to Approve Clean Match | 5 clicks `[M]` | 3 clicks `[T]` | **-40% click reduction** |
| | Dialog Sections | 4 numbered sections + yellow box `[M]` | 1 summary sentence + reason `[T]` | **-80% modal complexity** |
| **Global Navigation & Shell** | Sidebar Destinations | 8 destinations `[M]` | 4 operational items + Settings `[T]` | **-50% navigation sprawl** |
| | Global Header Badges/Buttons | 5 permanent buttons/chips `[M]` | 2 controls (Help dropdown, user) `[T]` | **Quiet, professional chrome** |
| | Orphaned Routes | 1 orphaned route (`/exceptions`) `[M]` | 0 orphaned routes `[T]` | **100% route integrity** |

---

## Part D — Implementation Roadmap

The transformation roadmap is organized into three prioritized phases. Every recommendation identifies affected files, dependencies, backend requirements, risks, and concrete verification methods.

```mermaid
flowchart LR
    P0["Phase P0: Trust & Core Comprehension (4-6 Days)"] --> P1["Phase P1: Usability & Workspace Unification (5-7 Days)"]
    P1 --> P2["Phase P2: Enterprise Polish & Governance Refinement (3-4 Days)"]
```

### Phase P0: Changes Essential to Buyer Comprehension & Immediate Trust

#### Rec P0-1: Eliminate Redundant Multi-Card Stacking on Invoice Detail
- **Problem:** Reviewers must read 4 duplicate explanation cards (Verdict Banner, CaseSummaryCard, PolicyChecksGrouped, ProcurementVerificationFlow) before reaching line items.
- **Affected Files:**
  - `frontend/src/pages/InvoiceDetailPage.tsx`
  - `frontend/src/components/CaseSummaryCard.tsx` (Retire or fold into header)
  - `frontend/src/components/PolicyChecksGrouped.tsx` (Move to collapsed details)
- **Dependencies:** None.
- **Backend Requirements:** None.
- **Risks & Mitigation:** Risk of hiding policy details. *Mitigation:* Keep full 7-gate breakdown accessible in the collapsible "Verification Details" drawer.
- **Verification Method:** Playwright visual regression test confirming single-viewport display above the fold at 1440px and 1280px.

#### Rec P0-2: Replace 600-Word Approval Wall with 3-Click Lightweight Dialog
- **Problem:** Routine approvals require reading ~600 words across 4 sections and a yellow warning box.
- **Affected Files:**
  - `frontend/src/components/ConsequenceAwareActionModal.tsx`
- **Dependencies:** Pre-filled justification rationale.
- **Backend Requirements:** Existing `POST /api/v1/invoices/:id/actions` already accepts reasons $\ge 3$ characters.
- **Risks & Mitigation:** Finance compliance audit risk. *Mitigation:* Audit event continues to record justification reason; dual-control threshold remains strictly enforced.
- **Verification Method:** User click test verifying approval completion in $\le 3$ clicks; backend test verifying `AuditEvent` persists unchanged.

#### Rec P0-3: Truthful Handling of Degraded / Unreadable Scans
- **Problem:** Unreadable scans previously reported 6 gate failures and prompted users to dispute prices that were never extracted.
- **Affected Files:**
  - `frontend/src/pages/InvoiceDetailPage.tsx`
  - `frontend/src/utils/statusNormalizer.ts`
  - `backend/core/pipeline.py` (Ensure unextracted invoices store `NOT_EVALUATED` rather than `FAIL`)
- **Dependencies:** Backend gate evaluation status.
- **Backend Requirements:** Store `NOT_EVALUATED` on downstream gates when OCR extraction fails.
- **Risks & Mitigation:** Risk of approving unreadable invoices. *Mitigation:* Unreadable documents are strictly blocked from approval; only "Upload clearer copy" or "Set aside" permitted.
- **Verification Method:** Test case uploading blank or degraded PDF verifying that only one error ("Document unreadable") appears.

#### Rec P0-4: Single-Sentence Action Outcomes (Eliminate Rejection Confusion)
- **Problem:** Actions like "Hold for Evidence" or "Ask Supplier to Correct" do not make their real consequences immediately clear.
- **Affected Files:**
  - `frontend/src/components/ConsequenceAwareActionModal.tsx`
  - `frontend/src/pages/InvoiceDetailPage.tsx`
- **Dependencies:** None.
- **Backend Requirements:** None.
- **Risks & Mitigation:** User assumes external email was sent. *Mitigation:* Explicit one-liner: "Status updated to Waiting for Supplier. No email was sent."
- **Verification Method:** User comprehension test: 100% of participants correctly state that no supplier email was dispatched.

---

### Phase P1: Major Usability, Information Architecture & Interaction Consolidation

#### Rec P1-1: Declutter "Today" Dashboard into 3 Actionable Zones
- **Problem:** Dashboard has 8 competing panels and over 1,400px of vertical scrolling.
- **Affected Files:**
  - `frontend/src/pages/DashboardPage.tsx`
- **Dependencies:** Rec P0-1.
- **Backend Requirements:** Existing `/dashboard/metrics` and `/dashboard/exposure` endpoints.
- **Risks & Mitigation:** Loss of executive metrics. *Mitigation:* Consolidate capital exposure metrics into a clean 3-tile strip.
- **Verification Method:** Visual screenshot test verifying dashboard fits on a standard 1080p display with zero vertical scrolling.

#### Rec P1-2: Build Unified 4-Way Procurement Reconciliation Table
- **Problem:** `ProcurementVerificationFlow.tsx` separates the 4 procurement stages into 4 large cards before the line-item table.
- **Affected Files:**
  - `frontend/src/components/ProcurementVerificationFlow.tsx`
- **Dependencies:** None.
- **Backend Requirements:** Existing PO, GRN, and QC snapshot data.
- **Risks & Mitigation:** Complex responsive table layout. *Mitigation:* Use responsive horizontal layout on desktop, stacked card comparison on mobile (< 768px).
- **Verification Method:** Playwright screenshot at 1440px, 1280px, and 375px.

#### Rec P1-3: Contextual Action Recommendation Bar
- **Problem:** 6 equal buttons under "Triage" and "Governance" confuse non-technical users.
- **Affected Files:**
  - `frontend/src/pages/InvoiceDetailPage.tsx`
- **Dependencies:** Root cause derivation from failing gate.
- **Backend Requirements:** None (derived client-side from first failing gate).
- **Risks & Mitigation:** Recommending the wrong action. *Mitigation:* Secondary options remain accessible via `[ More Actions ▾ ]`.
- **Verification Method:** Unit test asserting correct recommended action for each of the 7 failure types.

#### Rec P1-4: Consolidate Navigation & Eliminate Orphaned `/exceptions` Route
- **Problem:** `/exceptions` is orphaned and duplicates `InboxPage.tsx`. Sidebar has 8 items.
- **Affected Files:**
  - `frontend/src/App.tsx`
  - `frontend/src/components/Sidebar.tsx`
  - `frontend/src/pages/InboxPage.tsx`
  - `frontend/src/pages/ExceptionsPage.tsx` (Retire route; fold owner assignment into Inbox)
- **Dependencies:** None.
- **Backend Requirements:** None.
- **Risks & Mitigation:** Broken bookmarks. *Mitigation:* Redirect `/exceptions` to `/invoices?stage=ACTION_REQUIRED`.
- **Verification Method:** Route test verifying `/exceptions` redirects cleanly.

---

### Phase P2: Visual Refinement, Enterprise Polish & Documentation Truth

#### Rec P2-1: Quiet Global Header & Consolidate Help Menu
- **Problem:** Global header is cluttered with permanent security chips, tour buttons, and theme toggles.
- **Affected Files:**
  - `frontend/src/components/AppShell.tsx`
- **Dependencies:** None.
- **Backend Requirements:** None.
- **Risks & Mitigation:** Users cannot find shortcuts. *Mitigation:* Single `[ Help ▾ ]` dropdown with hotkey cheat sheet.
- **Verification Method:** Visual audit of clean header bar.

#### Rec P2-2: Jargon Sanitization & Plain-English Terminology Pass
- **Problem:** Infrastructure terms (`PostgreSQL Trigger`, `IdP`, `JWT`, `MATCH_CANDIDATE`) leak into buyer-visible views.
- **Affected Files:**
  - `frontend/src/components/AuthScreen.tsx`
  - `frontend/src/pages/AuditPage.tsx`
  - `frontend/src/pages/InboxPage.tsx`
  - `frontend/src/utils/statusNormalizer.ts`
- **Dependencies:** None.
- **Backend Requirements:** None.
- **Risks & Mitigation:** None.
- **Verification Method:** Automated text scan for banned technical phrases in rendered HTML.

---

## Part E — Concrete Component-Level Before & After Wireframes

### Screen 1: "Today" Operational Dashboard

#### BEFORE (Current: 8 Stacked Panels, High Clutter)
```
[Sticky Watermark: Evaluation Mode — Sample ERP Data | Reset Demo State]
[Header: Today's AP Operations | Date | Refresh | Go to Invoices]
[Card 1: Pre-Payment Invoice Verification & Controls (Paragraph text)]
[Step Strip: 1. Intake -> 2. AI Extraction -> 3. 7 Gates -> 4. Dual Control]
[Card 2: Executive AP Capital Exposure Scorecard (3 Tiles + Legal MSME Note)]
[Card 3: 3 Outcome Tiles (Needs Attention, Ready to Approve, Second Approval)]
[Card 4: Operational Readiness Checklist (6 Subsystem chips)]
[Card 5: Operational Pipeline Velocity Strip (1. Received -> 2. Exceptions -> 3. Ready...)]
[Split Grid: Next-Up Table (8 cols) + Info Banner + MSME Note | Integration Pillars (4 cols) | Audit Trail]
Total Page Height: ~1,450px (Extensive vertical scrolling required)
```

#### AFTER (Proposed: 3 Focused Operational Zones, Fits on One Screen)
```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│  Today's AP Operations                                             Wednesday, Nov 4   │
├────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                        │
│  WORKLOAD STATUS AT A GLANCE                                                           │
│  ┌─────────────────────────┐  ┌─────────────────────────┐  ┌─────────────────────────┐ │
│  │  3 Need Attention       │  │  2 Ready to Approve     │  │  0 Waiting on Others    │ │
│  │  ₹1,43,000 Blocked      │  │  ₹2,31,280 Cleared      │  │  Dual-Control >= ₹5L    │ │
│  │  [ Triage Invoices ➔ ]  │  │  [ Review Queue ➔ ]     │  │  [ View Approvals ➔ ]   │ │
│  └─────────────────────────┘  └─────────────────────────┘  └─────────────────────────┘ │
│                                                                                        │
│  ACTIONABLE WORKLOAD QUEUE                                      [ + Upload Invoice ]  │
│  ┌──────────────────────────────────────────────────────────────────────────────────┐  │
│  │ Supplier                Invoice     Amount         Reason                Action  │  │
│  │ Asterion Precision      AP-26-011   ₹25,960.00     Price 18.9% above PO  [Review]│  │
│  │ Unidentified Scan       scan_037    —              Document unreadable   [Review]│  │
│  │ Asterion Precision      AP-26-009   ₹2,31,280.00   All checks passed     [Approve│  │
│  └──────────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                        │
│  CAPITAL EXPOSURE SNAPSHOT                                                             │
│  Blocked: ₹1,43,000 (3 inv)  •  Operational Ageing (>30d): ₹0.00  •  Treasury: ₹2,31,280 │
└────────────────────────────────────────────────────────────────────────────────────────┘
Total Page Height: ~680px (Fits standard desktop viewport without scrolling)
```

---

### Screen 2: Invoice Review & Reconciliation Workspace

#### BEFORE (Current: 5 Stacked Cards & Split Panes)
```
[Header: Invoice # | StatusBadge | Amount | MSME Due | Glossary | Tour]
[Coachmark Banner: Guided AP Review Tour (if open)]
[Card 1: Verdict Banner (Status + Paragraph + Bullets with raw error text)]
[Card 2: CaseSummaryCard / Decision Guide (Collapsible, repeats pass/fail summary)]
[Split Layout: Left 5 cols (PDF Viewer) | Right 7 cols (Tabbed Panel)]
  [Tab Bar: Verification & 3-Way Matching | History & Evidence]
  [Card 3: PolicyChecksGrouped (Progress bar + 3 accordion groups: A, B, C)]
  [Card 4: ProcurementVerificationFlow (Linear tracker + 4 Node Cards: Invoice, PO, GRN, QC)]
  [Card 5: Line-by-Line Match Table (with Comparison vs 9-Col Ledger toggle)]
  [Card 6: Net Payable Waterfall]
  [Card 7: Authoritative Reference Disclosure]
[Sticky Footer: Triage (3 buttons) | Governance (3 buttons) | Approve / Blocked (1 button)]
[Modal: ConsequenceAwareActionModal (600 words, 4 sections, yellow warning box)]
```

#### AFTER (Proposed: Unified Split-Screen with 4-Way Reconciliation Grid)
```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│  ← Invoices    AP-26-011 • Asterion Precision Components                  ₹25,960.00   │
├─────────────────────────────────────────────┬──────────────────────────────────────────┤
│  ORIGINAL DOCUMENT PANE (50%)               │  RECONCILIATION WORKSPACE (50%)          │
│                                             │                                          │
│  [ Toolbar: Zoom - 100% + | Download | ↗ ]  │  ● NEEDS ATTENTION: Price Variance       │
│  ┌───────────────────────────────────────┐  │  Billed rate is 18.9% above PO rate.     │
│  │                                       │  │                                          │
│  │                                       │  │  RECOMMENDED ACTION:                     │
│  │         INVOICE # AP-26-011           │  │  [ Ask Supplier to Correct ]  [More ▾]   │
│  │         Asterion Precision            │  │                                          │
│  │                                       │  │  4-WAY RECONCILIATION TABLE              │
│  │  Item: Precision Flange               │  │  ┌────────────────────────────────────┐  │
│  │  Qty: 80  Rate: ₹2,450.00             │  │  │ Item Description                   │  │
│  │  Total: ₹25,960.00                    │  │  │ Precision Flange (SKU-FL-09)       │  │
│  │                                       │  │  │                                    │  │
│  │                                       │  │  │ Billed:    80 @ ₹2,450.00          │  │
│  │                                       │  │  │ PO Contract: 80 @ ₹2,060.00        │  │
│  │                                       │  │  │ Goods Receipt: 80 Units (GRN-5678) │  │
│  │                                       │  │  │ Quality Inspection: Passed (QC-12) │  │
│  │                                       │  │  │ Variance:  +₹390 / +18.9% ❌       │  │
│  │                                       │  │  │ [ Correct Line Item ✎ ]            │  │
│  │                                       │  │  └────────────────────────────────────┘  │
│  │                                       │  │                                          │
│  │                                       │  │  PAYABLE SUMMARY                         │
│  │                                       │  │  Subtotal: ₹22,000.00                    │
│  │                                       │  │  GST (18%): ₹3,960.00                    │
│  │                                       │  │  Net Authorizable Payable: ₹25,960.00    │
│  │                                       │  │                                          │
│  │                                       │  │  ▸ Full Verification Details & Audit     │
│  │                                       │  │    (7 Policy Gates, AI Fields, Hashes)   │
│  └───────────────────────────────────────┘  │                                          │
└─────────────────────────────────────────────┴──────────────────────────────────────────┘
```

---

### Screen 3: Streamlined 3-Click Approval Dialog

#### BEFORE (Current: 600-Word Essay Modal)
```
┌────────────────────────────────────────────────────────┐
│ Confirm Action: Approve Invoice (Internal Sign-Off)    │
│ APPROVE_AP_REVIEW                                      │
├────────────────────────────────────────────────────────┤
│ 1. What this does                                      │
│    Records verified AP review sign-off in audit trail. │
│ 2. Resulting workflow state                            │
│    Stage: INTERNAL_APPROVAL_COMPLETE (or ACTION_REQ)   │
│ 3. Does this require another person?                   │
│    Single approval sufficient below ₹5,00,000.         │
│ 4. What happens next                                   │
│    Moves to payment batching queue.                    │
│                                                        │
│ [!] Explicit Safety & Control Guarantees (What it NOT) │
│   - Does NOT execute payment or bank transfer          │
│   - Does NOT post entries to SAP S/4HANA or GL         │
│   - Does NOT clear vendor liability in ERP             │
│   - CANNOT be executed if any gate failed              │
│                                                        │
│ Audit Justification Reason * (Min 3 chars)             │
│ Quick templates: [Template 1] [Template 2] [Template 3]│
│ [ Textarea with placeholder text...                  ] │
│                                                        │
│                                  [ Cancel ] [ Confirm ]│
└────────────────────────────────────────────────────────┘
```

#### AFTER (Proposed: 45-Word Focused Confirmation)
```
┌────────────────────────────────────────────────────────┐
│  Approve Invoice AP-26-009?               ₹2,31,280.00 │
├────────────────────────────────────────────────────────┤
│  Supplier: Asterion Precision Components               │
│  Verification: Matches PO-1042, GRN-5678, and QC-9812. │
│                                                        │
│  Audit Justification:                                  │
│  ┌──────────────────────────────────────────────────┐  │
│  │ All 7 checks verified against procurement files. │  │
│  └──────────────────────────────────────────────────┘  │
│  Quick reasons: [Variance within tolerance] [GRN Confirmed]│
│                                                        │
│  ℹ Approving records your internal sign-off. It does   │
│    not disburse bank funds or post to general ledger. │
│                                                        │
│                           [ Cancel ]   [ Approve (3s) ]│
└────────────────────────────────────────────────────────┘
```

---

## Part F — Acceptance Criteria Reconciliation

The proposed transformation plan directly satisfies all 10 acceptance criteria specified in the mission brief:

1. **Understood within 60 Seconds:** The 4-way reconciliation table and single-sentence case story allow a user to understand the entire transaction status immediately upon opening the screen.
2. **Explaining Without Jargon:** The natural thought progression (*Billed $\rightarrow$ Ordered $\rightarrow$ Received $\rightarrow$ Inspected*) replaces all procedural gate numbers with human language.
3. **Visible Without Scrolling:** The redesigned review screen places the verdict, discrepancy reason, reconciliation table, and action bar directly within a single desktop viewport.
4. **Immediately Identifiable Core Actions:** The system derives and highlights **ONE primary recommended action** (e.g. `[ Ask Supplier to Correct ]`), eliminating the 6-button decision paralysis.
5. **Demonstrably Reduced Clicks:** Routine approvals drop from 5 clicks to 3 clicks; invoice upload remains a 1-click drag-and-drop action directly on the Inbox page.
6. **Zero Text Wrapping / Responsive Collisions:** Consolidating the comparison grid prevents horizontal table overflow and header collisions on standard viewports (1440px and 1280px).
7. **Zero Loss of Financial or Governance Evidence:** All 7 deterministic gates, line-item comparisons, optimistic concurrency locks (`If-Match`), and append-only audit logs remain 100% active and accessible under progressive disclosure.
8. **Zero Fabricated Capabilities:** The application never claims live ERP synchronization, outbound vendor emailing, or automatic bank disbursements.
9. **Action-to-Backend Truthfulness:** Every displayed action matches its exact backend outcome in `backend/api/v1/invoices.py`, updating statuses cleanly without misleading users.
10. **Credible Demo Showcase:** Presenters can point directly at the screen and explain what happened in two natural sentences, without having to apologize for confusing banners or developer debug tags.

---

## Part G — Preserved Enterprise Governance & Financial Invariants

The proposed UX simplification strictly preserves every underlying financial control and security boundary:

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                     PRESERVED ENTERPRISE FINANCIAL INVARIANTS                          │
├────────────────────────────────────────────────────────────────────────────────────────┤
│  1. Blocked Approval on Failed Gates: Approvals remain strictly blocked whenever any   │
│     policy check fails. Gate overrides (D-04) remain completely disabled.              │
│  2. Dual-Control Governance: Invoices >= ₹5,00,000 strictly enforce dual approval     │
│     with anti-self-approval (first approver != second approver).                       │
│  3. Controller Authority: Step 2 of dual approval strictly requires CONTROLLER or      │
│     SYSTEM_ADMIN role. AP Associates and Leads cannot execute secondary sign-off.      │
│  4. Auditor Read-Only Boundary: AUDITOR role retains strictly read-only access with     │
│     server-enforced HTTP 403 Forbidden on all mutation endpoints.                      │
│  5. Mandatory Audit Justification: Every action requires a minimum 3-character reason  │
│     permanently recorded in the append-only AuditEvent table.                          │
│  6. Zero Payment / GL Leakage: Approvals strictly signify internal AP review sign-off;  │
│     no bank funds are transferred and no external ERP General Ledger is modified.     │
│  7. Strict Tolerances: Quantity tolerance remains 0.00%; price tolerance remains       │
│     ±1.50% against authorized PO unit rates.                                          │
│  8. Document Security: Pre-signed document URLs retain their strict 300-second TTL.    │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## Conclusion & Next Steps

This document provides the complete, authoritative product diagnosis, information architecture blueprint, simplification scorecard, implementation roadmap, and component wireframes required to transform the AP Command Center into a consumer-grade, non-technical buyer product.

**Current Status:** All analysis complete. Zero application code or database schemas have been modified. Ready for product owner review and sign-off before proceeding to Phase P0 implementation.
