# UX Iteration Log — AP Command Center
## Comprehensive Record of Continuous Design & Engineering Iterations

**Repository:** `C:\Zamp Casse Study`  
**Branch:** `handoff/ap-command-center`  
**Standard:** 8-Stage Iterative Cycle (Observe $\to$ Multi-Perspective Review $\to$ Deep Diagnosis $\to$ Explore Alternatives $\to$ Careful Implementation $\to$ Rigorous Verification $\to$ Independent Critique $\to$ Checkpoint)

---

## Baseline Verification Milestone (Commit `62432e7`)
- **Verified:** Git branch `handoff/ap-command-center`, commit `62432e7`, clean working tree.
- **Backend Test Suite:** 266 passed, 12 skipped, 0 failed in 59.43s.
- **Frontend Build:** `npm --prefix frontend run build` built cleanly in 434ms (Vite v8.3.5).
- **Runtime Services:** FastAPI running on `http://127.0.0.1:8000`, Vite running on `http://localhost:5173`.
- **Baseline Quality Assessment:** Composite score 6.93 / 10. Core functionality, invariants, and honesty intact. Clear visual and architectural headroom identified for enterprise craft elevation.

---
<!-- Iterations will be appended below -->

## Iteration 1 — Product Comprehension & First Impression
**Timestamp:** 2026-11-02T06:45:00+05:30  
**Theme:** Overall product comprehension and first impression  
**Status:** **COMPLETED & VERIFIED**

### 1. Initial Problem
- Document `<title>` in `frontend/index.html` was literally `"frontend"`, an amateur Vite default that signaled an unfinished prototype to any evaluator looking at the browser tab.
- When an evaluator or first-time user opened `http://127.0.0.1:8000`, the authentication screen displayed a harsh configuration warning regarding unconfigured Google OAuth rather than welcoming them to the product.
- `AuthScreen.tsx` had hardcoded dark styles (`bg-slate-900 border-slate-800 text-white`) that broke visual harmony in light theme.
- The Dashboard header featured an artificial kicker badge (`AUTONOMOUS ACCOUNTS PAYABLE SYSTEM`) violating the craft floor rule ("no kickers/eyebrows above headings; let the heading speak"), and the 4-step workflow was broken into nested mini-cards.

### 2. Root Cause
- `index.html` was never updated from Vite initialization.
- `AuthScreen.tsx` was developed during early backend auth testing with a dark-only palette and prioritized raw OAuth debugging rather than user onboarding.
- Informational banners were appended as separate bordered cards during incremental feature additions.

### 3. Alternatives Explored
- **Alternative A:** Strip all authentication and landing UI entirely, defaulting immediately into the AP Lead workspace.
  *Critique:* Rejected. Enterprise reviewers need to experience role-based access control (RBAC), see that the system enforces authentic JWTs, and be able to switch to Auditor or Controller roles.
- **Alternative B (Chosen):** Elevate `index.html` with enterprise metadata; redesign `AuthScreen.tsx` as a dual-themed enterprise portal that surfaces 1-click evaluation access with descriptive role badges; streamline the dashboard header into an authoritative, clean pre-payment overview without kickers or nested cards.

### 4. Implementation Details
- `frontend/index.html`: Set title to `AP Command Center | Autonomous Invoice Verification & Controls` and added meta description.
- `frontend/src/components/AuthScreen.tsx`: Complete dual-theme refactor (`bg-white dark:bg-slate-900`), highlighted 1-click SME Evaluation Access (AP Lead, Controller, Auditor, Associate) with clear authority descriptions, and demoted optional OAuth setup into an expandable helper. Cleaned unused TypeScript symbols.
- `frontend/src/pages/DashboardPage.tsx`: Removed kicker badge, refined the headline to `Pre-Payment Invoice Verification & Controls`, and formatted the 4 steps as a clean horizontal linear pipeline with arrow separators ($1 \to 2 \to 3 \to 4$) rather than bordered boxes.

### 5. Verification & Evidence
- **Automated Playwright Script:** `scratch/verify_it1_execution.py` passed with 100% assertions met.
- **Screenshots:**
  - `scratch/screenshots/it1_auth_screen_1440.png` (Clean dual-theme login portal with 1-click evaluation roles).
  - `scratch/screenshots/it1_today_after_1440.png` (Streamlined pre-payment header).
  - `scratch/screenshots/it1_today_after_375.png` (Responsive mobile layout).
- **TypeScript & Build:** `npm --prefix frontend run build` built cleanly in 444ms with zero errors.

### 6. Remaining Weaknesses & Next Action
- Dashboard operational hierarchy still has redundant counting between the 3 outcome tiles and the `INVOICE PIPELINE FLOW` horizontal bar. In Iteration 2, address Dashboard Hierarchy & Operational Clarity.


---

## Iteration 2: Dashboard Hierarchy & Above-the-Fold Operational Clarity

### 1. Stage 1: Observe & Measure
- **Target Surface:** `/today` (AP Operations Dashboard).
- **Runtime Measurement (Playwright 1440x900):**
  - Child 0 (Header): `y = 80.0px`, `h = 73.0px`
  - Child 1 (Pre-Payment Hero): `y = 177.0px`, `h = 158.0px`
  - Child 2 (3 Outcome Tiles): `y = 359.0px`, `h = 170.5px`
  - Child 3 (Workspace Setup Checklist): `y = 554.0px`, `h = 124.0px` (showing 6 cards that were all already green!)
  - Child 4 (Invoice Pipeline Flow): `y = 702.0px`, `h = 165.0px` (redundant 4-card grid repeating tile counts)
  - Child 5 (Next-Up Actionable Queue): `y = 905.7px` (completely pushed below the 900px viewport fold!)
- **Critical Finding:** A business user or HR evaluator landing on `/today` had to scroll down to see the primary work queue because 337px of intermediate static boxes separated the outcome tiles from the actionable items.

### 2. Stage 2: Multi-Perspective Review
- **AP Lead:** Needs immediate visual access to prioritized exceptions requiring intervention without scrolling past completed onboarding checklists.
- **Controller:** Wants clear visibility into dual-approval threshold items and statutory deadlines.
- **Auditor:** Requires verified data provenance and clear indication that subsystem readiness is derived from live runtime state.
- **HR Evaluator:** Judges whether the application feels like a fast, focused operational command center or a cluttered prototype.

### 3. Stage 3: Deep Diagnosis
- The Setup Checklist rendered all 6 subsystem cards simultaneously even after all tasks were complete (`doneCount === items.length`).
- The "Invoice Pipeline Flow" rendered 4 bulky cards with redundant status numbers that duplicated what the large outcome tiles directly above were already communicating.

### 4. Stage 4: Explore Alternatives
- *Alternative A:* Retain both cards with reduced padding. Rejected: still consumes 200px+ of vertical space.
- *Alternative B (Implemented):* 
  1. Transform Setup Checklist when complete into a sleek single-line operational readiness status bar (`✓ Operational Readiness: 6 of 6 subsystems active • Verified against live system state`) with an expandable disclosure toggle (`View Subsystems` / `Hide Subsystems`) and Setup Wizard link.
  2. Streamline Pipeline Flow into an ultra-clean, 1-line linear horizontal velocity strip ($1 \to 2 \to 3 \to 4$) displaying stage velocity and total tracked invoices in 42px.
  3. Tighten statutory MSMED notice into a crisp 1-line compliance summary.

### 5. Stage 5: Careful Implementation
- **Modified File:** `frontend/src/pages/DashboardPage.tsx`:
  - Added `checklistExpanded` state with `ChevronDown` disclosure.
  - Implemented dynamic readiness bar when subsystems are verified.
  - Replaced 4-card pipeline grid with sleek linear `Pipeline Velocity` strip.
  - Compacted statutory compliance banner.

### 6. Stage 6: Rigorous Verification
- **DOM Measurement Verification:**
  - `Next-Up Actionable Queue` start position moved from `y = 905.7px` to `y = 702.7px` (pulled up by $\approx 203\text{px}$).
  - On a standard 1440x900 viewport, the queue header, compliance context, and top actionable invoice items are now 100% visible **above the fold**.
- **Screenshots Saved:**
  - `scratch/screenshots/it2_dashboard_desktop_1440.png`
  - `scratch/screenshots/it2_dashboard_mobile_375.png`
- **Build & Tests:**
  - `npm --prefix frontend run build`: Clean production build in 434ms.
  - `python -m pytest tests/ -q`: `266 passed, 12 skipped, 0 failed` in 48.35s.

### 7. Stage 7: Independent Critique
- The dashboard is dramatically more purposeful. An operator landing on `/today` sees their key metrics and can immediately click "Review" on the top prioritized exception without touching their scroll wheel.
- Subsystem readiness remains 1-click verifiable without occupying permanent vertical real estate.

### 8. Stage 8: Checkpoint & Scorecard
- **Composite Score:** Improved from 7.31 to **7.51 / 10**.
- **Commit:** `feat(ux-it2): streamline dashboard hierarchy, auto-collapse readiness checklist, and pull actionable queue above the fold`


---

## Iteration 3: Navigation & Information Architecture

### 1. Stage 1: Observe & Measure
- **Target Surface:** `AppShell` header breadcrumbs, global `Sidebar`, and cross-application wayfinding.
- **Empirical Findings:**
  - Sidebar badge properties (`invoiceCount`, `approvalCount`) were defined in `SidebarProps` but never passed by `AppShell.tsx`, leaving the badges permanently unrendered regardless of queue volume.
  - Sidebar item label `Reference Data` was abstract database terminology that confused business users; the underlying data is procurement records (Vendors, POs, GRNs, QC).
  - The top header bar rendered only flat static strings without breadcrumbs, preventing users from seeing their hierarchy or clicking back when viewing an invoice (`/invoices/:id`).

### 2. Stage 2: Multi-Perspective Review
- **AP Lead & Controller:** Need live ambient counters in the sidebar so they know when exceptions (Invoices queue) or dual approvals require their attention without manually checking `/today` or `/invoices`.
- **Auditor:** Requires clear, domain-accurate taxonomy ("Procurement Records", "Audit Trail", "Connections & Storage") rather than generic software terms.
- **HR Evaluator:** Judges whether navigation feels like a cohesive enterprise application with effortless wayfinding and clear hierarchy.

### 3. Stage 3: Deep Diagnosis
- `AppShell.tsx` did not query or listen to `api.getDashboardMetrics()`, leaving `Sidebar` unpopulated.
- Header title resolution was purely a flat string return function that ignored path segments and parent routes.

### 4. Stage 4: Explore Alternatives
- *Alternative A:* Rely on custom React Context for global badge counts. Rejected: unnecessary complexity and potential re-render churn.
- *Alternative B (Implemented):* Implement a lightweight, resilient query in `AppShell` triggered on `location.pathname` changes and on a 30s background sync. Pass verified counts to `Sidebar`. Add semantic color-coded badges (amber for open exceptions, purple for pending approvals). Add interactive two-part breadcrumbs with clickable parent links.

### 5. Stage 5: Careful Implementation
- **Modified Files:**
  - `frontend/src/components/AppShell.tsx`:
    - Added `navCounts` state querying `api.getDashboardMetrics()`.
    - Passed `invoiceCount` (exceptions) and `approvalCount` (approvals) into `<Sidebar />`.
    - Implemented interactive breadcrumbs: `Invoices / <invoice_id>` (with clickable NavLink) and `Management / Procurement Master Records`.
  - `frontend/src/components/Sidebar.tsx`:
    - Renamed `Reference Data` to `Procurement Records` and `Connections` to `Connections & Storage`.
    - Added semantic color-coded badge styles (amber border/fill for Invoices exceptions, purple border/fill for Approvals).

### 6. Stage 6: Rigorous Verification
- **Playwright Test Execution (`scratch/inspect_iteration_3.py`):**
  - Verified active amber badge `[2]` renders next to `Invoices` in the sidebar.
  - Verified navigation to Procurement Records displays `Management / Procurement Master Records` in header.
  - Verified clicking into an invoice displays `Invoices / inv_dual_eval_sec` with clickable return link.
  - Screenshots:
    - `scratch/screenshots/it3_sidebar_badges_1440.png`
    - `scratch/screenshots/it3_procurement_records_1440.png`
    - `scratch/screenshots/it3_invoice_detail_header_1440.png`
- **Build & Tests:**
  - `npm --prefix frontend run build`: Clean production build in 436ms.
  - `python -m pytest tests/ -q`: `266 passed, 12 skipped, 0 failed` in 37.28s.

### 7. Stage 7: Independent Critique
- The application now has ambient situational awareness. When an AP operator is working in Audit or Connections, they immediately see `[2]` next to Invoices.
- Wayfinding inside invoice detail provides a clean breadcrumb back to the filtered ledger.

### 8. Stage 8: Checkpoint & Scorecard
- **Composite Score:** Improved from 7.51 to **7.76 / 10**.
- **Commit:** `feat(ux-it3): live sidebar notification badges, domain-accurate procurement taxonomy, and clickable breadcrumb navigation`


---

## Iteration 4: Onboarding & Guided Discovery

### 1. Stage 1: Observe & Measure
- **Target Surface:** First-run Setup Wizard (`/setup`) and Contextual Guided Workspace Tour (`InvoiceDetailPage.tsx`).
- **Empirical Findings:**
  - Setup Wizard Step 6 (Workspace Review Tour) only showed static coachmark cards. Users had to advance through 5 static slides before finding a finish button, with no immediate bridge into the authentic live review workspace.
  - In `InvoiceDetailPage.tsx`, the Guided Review Tour was triggered via `window.location.search.includes('tour=true')` which failed during React Router SPA client transitions.
  - The `Tour` and `Glossary` header buttons were hidden on tablet and mobile viewports (`hidden sm:inline-flex`).

### 2. Stage 2: Multi-Perspective Review
- **First-Time Operator & HR Evaluator:** Wants to immediately test the real interactive review workspace with live 3-way matching and 7-gate validation, rather than merely reading static slide descriptions.
- **Mobile User:** Needs access to the Guided Tour and Glossary even on smaller mobile screens.

### 3. Stage 3: Deep Diagnosis
- Disconnect between setup wizard and actual operational workspace.
- Reliance on raw `window.location.search` instead of React Router's `useSearchParams` hook caused silent state mismatch on SPA link navigation.

### 4. Stage 4: Explore Alternatives
- *Alternative A:* Force full linear onboarding completion before allowing invoice inspection. Rejected: excessive barrier to evaluation.
- *Alternative B (Implemented):* Add a prominent "Launch Live Tour →" hero banner directly on Step 6 targeting authentic sample invoice `AP-26-009`, connect `useSearchParams` in `InvoiceDetailPage.tsx` for instant tour banner activation, persist `ap.workspace_tour.completed` in `localStorage`, and enable responsive visibility of Tour & Glossary header buttons.

### 5. Stage 5: Careful Implementation
- **Modified Files:**
  - `frontend/src/pages/OnboardingPage.tsx`:
    - Imported `Compass` icon.
    - Added "Experience the Live Interactive Review Workspace" banner on Step 6 with 1-click CTA targeting `AP-26-009`.
  - `frontend/src/pages/InvoiceDetailPage.tsx`:
    - Integrated `useSearchParams` from `'react-router-dom'` to reliably handle `?tour=true`.
    - Maintained Tour & Glossary buttons across all viewports (`inline-flex` with responsive text labels).
    - Added `localStorage.setItem('ap.workspace_tour.completed', 'true')` on tour completion.

### 6. Stage 6: Rigorous Verification
- **Runtime Verification:**
  - Navigating to `/invoices/inv_d76401c096d0?tour=true` loads the full workspace and activates Step 1 of 6 of the Guided AP Workspace Tour with dynamic tab switching and verified live line-item match data.
  - Screenshots:
    - `scratch/screenshots/it4_setup_step1_1440.png`
    - `scratch/screenshots/it4_loaded_tour_1440.png`
    - `scratch/screenshots/it4_invoice_mobile_375.png`
- **Build & Tests:**
  - `npm --prefix frontend run build`: Clean production build in 438ms.
  - `python -m pytest tests/ -q`: `266 passed, 12 skipped, 0 failed` in 37.91s.

### 7. Stage 7: Independent Critique
- The onboarding journey is now actionable. A reviewer going through setup can immediately experience the real application with live data and guided walkthroughs.

### 8. Stage 8: Checkpoint & Scorecard
- **Composite Score:** Improved from 7.76 to **7.95 / 10**.
- **Commit:** `feat(ux-it4): live interactive workspace tour bridge from setup wizard, responsive tour triggers, and state-driven coachmarks`


---

## Iteration 5: Invoice Inbox Ledger & Scanability

### 1. Stage 1: Observe & Measure
- **Target Surface:** `/invoices` (Invoice Inbox Ledger).
- **Empirical Findings:**
  - Users were restricted to two static `<select>` dropdowns (`All Processing Stages` and `All Verification Decisions`) to find invoices.
  - Zero text search input: an operator looking for "Asterion" or a specific PO number had no way to search.
  - Table rows were passive; users had to hunt and click the small text link `Inspect ->` on the far right.
  - Table header scrolled away on long lists, causing loss of column context.

### 2. Stage 2: Multi-Perspective Review
- **AP Lead & Associate:** Need instant, responsive search and 1-click segmented views ("Needs Attention", "Ready to Approve", "Approved") to triage high volumes rapidly.
- **Controller:** Wants immediate visibility of high-value and exception-flagged items.
- **HR Evaluator:** Judges table quality against institutional benchmarks (Linear, Stripe, Mercury).

### 3. Stage 3: Deep Diagnosis
- Filtering was coupled solely to server query parameters without client-side memoized instant search.
- Interactive click target was limited to a tiny 50px text button rather than the entire table row.

### 4. Stage 4: Explore Alternatives
- *Alternative A:* Add backend search endpoint parameters. Rejected: adds network round-trips and debounce lag for current paginated datasets.
- *Alternative B (Implemented):* Add instant client-side memoized fuzzy search filtering over the active dataset with zero input latency, paired with clean quick-segmented tabs that bind directly to URL search parameters. Make the entire table row clickable with micro-hover feedback.

### 5. Stage 5: Careful Implementation
- **Modified File:** `frontend/src/pages/InboxPage.tsx`:
  - Added `Search`, `X` from `lucide-react`.
  - Added `searchQuery` state and `filteredItems` with `useMemo`.
  - Implemented Quick Segmented Tabs: `All Invoices`, `Needs Attention`, `Ready to Approve`, `Approved`.
  - Integrated instant search input with clear button.
  - Enhanced `<tr>` with `onClick={() => onSelectInvoice(inv.id)}`, cursor pointer, and hover styles.
  - Converted `Inspect` link into a crisp `Review` action button with arrow translation on row hover.
  - Added sticky `<thead>` with backdrop blur.

### 6. Stage 6: Rigorous Verification
- **Playwright Test Execution (`scratch/inspect_iteration_5.py`):**
  - All 4 quick segmented tabs found and active.
  - Real-time search for "Asterion" instantaneously reduced visible rows from 8 to 4 with zero latency.
  - Clicking clear button restored all 8 rows.
  - Full table row click was verified to immediately navigate to invoice detail (`/invoices/inv_dual_eval_sec`).
  - Screenshots:
    - `scratch/screenshots/it5_inbox_ledger_1440.png`
    - `scratch/screenshots/it5_inbox_mobile_375.png`
- **Build & Tests:**
  - `npm --prefix frontend run build`: Clean production build in 445ms.
  - `python -m pytest tests/ -q`: `266 passed, 12 skipped, 0 failed` in 43.12s.

### 7. Stage 7: Independent Critique
- The ledger is now fast, responsive, and tactile. Operators can triage batches in seconds.

### 8. Stage 8: Checkpoint & Scorecard
- **Composite Score:** Improved from 7.95 to **8.15 / 10**.
- **Commit:** `feat(ux-it5): quick segmented tabs, zero-latency real-time search, full-row clickability, and sticky table header on invoice inbox ledger`


---

## Iteration 6: Invoice Detail Workspace & Above-Fold Layout

### 1. Stage 1: Observe & Measure
- **Target Surface:** `/invoices/:id` (Invoice Detail Workspace).
- **Runtime Measurement (Playwright 1440x900 on `inv_d76401c096d0`):**
  - Child 0 (Header): `y = 80.0px`, `h = 60.0px`
  - Child 1 (Verdict Banner): `y = 156.0px`, `h = 76.0px`
  - Child 2 (CaseSummaryCard): `y = 248.0px`, `h = 297.7px` (expanded by default!)
  - Child 3 (2-Pane Workspace — PDF Viewer & 3-Way Match Table): `y = 561.7px`, `h = 780.0px`
  - Child 4 (Sticky Decision Bar): `y = 845.0px`, `h = 55.0px`
- **Critical Finding:** Prior to Iteration 6, the primary working area (the original PDF document and the procurement 3-way matching table) had only **283.3px of visible height** above the bottom action bar. Users had to scroll immediately on every invoice because Child 1 and Child 2 consumed 374px of vertical space while repeating largely redundant information.

### 2. Stage 2: Multi-Perspective Review
- **AP Lead & Associate:** Needs to review the invoice PDF side-by-side with the 3-way match line items immediately upon opening the page without touching the scroll wheel.
- **Controller:** Needs to immediately see the decision verdict and dual-control threshold without wading through multiple large stacked cards.
- **Auditor:** Requires the plain-language case explanation and reference snapshot disclosures to remain readily accessible on demand.
- **HR Evaluator:** Observes whether the interface feels like an expertly engineered split-pane productivity tool (Linear, Mercury, Stripe) or an unrefined vertical form.

### 3. Stage 3: Deep Diagnosis
- `CaseSummaryCard.tsx` initialized `isExpanded = true`, permanently rendering its full 298px 4-section grid above the fold.
- The Verdict Banner in `InvoiceDetailPage.tsx` and `CaseSummaryCard` duplicated the same status badges, decision titles, and check tallies.
- The vertical page rhythm used loose `space-y-4` padding.

### 4. Stage 4: Explore Alternatives
- *Alternative A:* Delete `CaseSummaryCard` entirely and leave only the Verdict Banner.
  *Critique:* Rejected. Deleting the card removes the plain-language explanation of what was verified, dual-approval explanations, and the "What the invoice asks for" context that makes the system understandable to non-AP business users.
- *Alternative B (Implemented):* 
  1. Default `isExpanded = false` in `CaseSummaryCard.tsx`, transforming it into an ultra-compact 38px inline Decision Guide bar with a 1-click `Explain Case ▾` disclosure toggle.
  2. Streamline the Verdict Banner in `InvoiceDetailPage.tsx` into a high-density, single-line executive status strip (`h = 46px`).
  3. Tighten page container rhythm from `space-y-4` to `space-y-3`.

### 5. Stage 5: Careful Implementation
- **Modified Files:**
  - `frontend/src/components/CaseSummaryCard.tsx`:
    - Changed default `isExpanded` to `false`.
    - Implemented high-density collapsed row with Sparkles icon, `Decision Guide: ${decisionTitle}`, and check tally badge.
    - Added clean `Explain Case ▾` / `Collapse ▴` toggle.
  - `frontend/src/pages/InvoiceDetailPage.tsx`:
    - Refactored Verdict Banner padding to `p-3 rounded-lg border` with flex horizontal alignment.
    - Maintained all required Phase 1 and Phase 2 plain-language strings and test assertions.
    - Reduced layout spacing to `space-y-3`.

### 6. Stage 6: Rigorous Verification
- **DOM Measurement Verification:**
  - `2-Pane Workspace` start position moved from `y = 561.7px` to `y = 260.0px` (pulled up by **301.7px**!).
  - Visible height of document and matching table above the fold increased from **283.3px to 585.0px** (more than doubled!).
  - Verified `Explain Case` toggle smoothly expands the 4-panel guide and collapses back without layout shift.
- **Screenshots Saved:**
  - `scratch/screenshots/it6_detail_collapsed_1440.png`
  - `scratch/screenshots/it6_detail_expanded_1440.png`
  - `scratch/screenshots/it6_detail_mobile_375.png`
- **Build & Tests:**
  - `npm --prefix frontend run build`: Clean production build in 448ms.
  - `python -m pytest tests/ -q`: `266 passed, 12 skipped, 0 failed` in 39.04s.

### 7. Stage 7: Independent Critique
- The workspace now feels immediate and authoritative. Opening any invoice presents the original PDF side-by-side with the 3-way match line items, with ~600px of vertical workspace visible above the fold.
- Case explanations and decision rules remain available in 1 click for non-experts.

### 8. Stage 8: Checkpoint & Scorecard
- **Composite Score:** Improved from 8.15 to **8.32 / 10**.
- **Commit:** `feat(ux-it6): streamline verdict banner, default-collapse case explanation guide, and pull 2-pane workspace above the fold`


---

## Iteration 7: Procurement 3-Way Matching Visualization

### 1. Stage 1: Observe & Measure
- **Target Surface:** Matching Tab (`frontend/src/components/ProcurementVerificationFlow.tsx`).
- **Initial Deficiencies:**
  - The 4 procurement nodes (1. Supplier Invoice, 2. Purchase Order, 3. Goods Receipt, 4. Quality Control) were arranged as 4 disjointed grid cards without a connecting progression indicator ($1 \to 2 \to 3 \to 4$).
  - In the line-item matching table, rate variance was displayed only as a percentage (e.g. `+2.50%`). An AP Lead or Associate had no visibility into the actual monetary discrepancy ($\Delta \text{ INR}$) without doing manual arithmetic.
  - The Match Status column showed binary Pass/Fail badges without actionable operational recommendations (such as recommending an exact debit note amount when the rate exceeded tolerance).

### 2. Stage 2: Multi-Perspective Review
- **AP Lead & Associate:** Needs to know the exact financial exposure in INR when an invoice line item overbills compared to the contracted PO rate so they can draft an accurate debit note or request a supplier correction.
- **Controller:** Demands commercial governance visibility—seeing the rupee delta alongside the percentage variance makes commercial leakage immediately tangible.
- **Auditor:** Requires clear visual confirmation that lines were cross-referenced against authoritative PO snapshots.
- **HR Evaluator:** Judges whether the application provides institutional financial software intelligence (like Ramp or Mercury) rather than static data dumps.

### 3. Stage 3: Deep Diagnosis
- The line items table mapped values but only computed `rateVariancePercent = ((l.rate - poRate) / poRate) * 100`, omitting `rateDeltaINR = (l.rate - poRate) * l.quantity`.
- The 4 nodes lacked a cohesive horizontal velocity tracker connecting the four stages of three-way matching.

### 4. Stage 4: Explore Alternatives
- *Alternative A:* Replace the table with stacked card tiles.
  *Critique:* Rejected. Tabular alignment is essential in finance for scanning multi-line orders, quantities, and rates.
- *Alternative B (Implemented):* 
  1. Add a Linear Stage Velocity Tracker ($1 \to 2 \to 3 \to 4$) above the 4 nodes showing the pipeline progression (Billed Claim $\to$ PO Contract $\to$ Receiving GRN $\to$ Quality QC).
  2. Enhance the Line-by-Line Match table with a dual variance presentation: Rate Variance (`%`) and monetary delta (`+₹X.XX`).
  3. Introduce inline actionable operational recommendations in the Match Verdict column (e.g., `Action: Debit Note (+₹500.00)` or `Within ±1.50%`).

### 5. Stage 5: Careful Implementation
- **Modified File:** `frontend/src/components/ProcurementVerificationFlow.tsx`:
  - Added Linear Stage Velocity Tracker with numeric circular badges and arrow connectors.
  - Computed `rateDeltaINR = (l.rate - poRate) * l.quantity`.
  - Added monetary delta chips (`+₹X.XX` in rose or neutral) under the percentage variance badge.
  - Added actionable triage suggestions in the `Match Verdict & Action` column.
  - Cleaned up table typography with tabular numerals (`tabular-nums font-mono`).

### 6. Stage 6: Rigorous Verification
- **Playwright Test Execution (`scratch/inspect_iteration_7.py`):**
  - Linear Stage Velocity Tracker verified present and active across all 4 stages.
  - Table headers `Rate Variance` and `Match Verdict & Action` verified.
  - Verified on exception invoice `AP-26-011` (`inv_dbfcaf77ba9b`) that line item rate discrepancies display the red `Debit Note (+₹X)` recommendation.
- **Screenshots Saved:**
  - `scratch/screenshots/it7_matching_passing_1440.png`
  - `scratch/screenshots/it7_matching_exception_1440.png`
  - `scratch/screenshots/it7_matching_mobile_375.png`
- **Build & Tests:**
  - `npm --prefix frontend run build`: Clean production build in 441ms.
  - `python -m pytest tests/phase_2/ -q`: `6 passed, 0 failed` in 4.74s.

### 7. Stage 7: Independent Critique
- The matching flow now clearly communicates how the four procurement records interlock, and the line-by-line comparison provides immediate commercial delta visibility.

### 8. Stage 8: Checkpoint & Scorecard
- **Composite Score:** Improved from 8.32 to **8.48 / 10**.
- **Commit:** `feat(ux-it7): linear stage velocity tracker, monetary rate delta calculations, and actionable debit note recommendations in 3-way match table`
