# Phase 3 — AP Command Center Onboarding & Contextual Help Report

**Date:** November 2026  
**Status:** Completed & Production-Verified  
**Branch:** `handoff/ap-command-center`  
**Scope:** Beginner-friendly first-time onboarding, 8-step interactive guided tour, context-aware help drawer, and plain-language terminology  

---

## 1. Executive Summary & Objective

Phases 1 and 2 established the unified design system, enterprise application shell, and complete redesign of all 8 core AP Command Center screens. While the visual architecture is now streamlined and scannable, non-technical finance managers, HR interviewers, and prospective buyers still benefit from contextual guidance on their first visit.

In **Phase 3**, we implemented a comprehensive, native onboarding and contextual assistance suite that makes a first-time user confident and self-sufficient in under 60 seconds.

The experience is built directly into the live application without creating separate prototypes, mock chatbot widgets, or synthetic dependencies:
- **Compact First-Time Welcome Experience:** Explains the core 5-stage AP workflow visually with non-coercive entry points.
- **8-Step Interactive Guided Tour:** Contextually navigates through actual application routes (`/today`, `/invoices`, `/invoices/:id`, `/exceptions`, `/approvals`, `/audit`) with focus ring highlights and non-obscuring floating cards.
- **Persistent Contextual Help Drawer:** Discoverable from the header and sidebar, presenting dynamically generated guidance tailored to the user's current screen, along with a searchable terminology glossary and workflow FAQs.
- **Frontend-Only Persistence:** Remembers welcome dismissal and tour completion using `localStorage` without modifying backend databases or API contracts.

---

## 2. Core Components & Functionality

### A. First-Time Welcome Experience (`frontend/src/components/onboarding/WelcomeModal.tsx`)

On a user's first visit, a compact welcome dialog introduces the platform with zero friction:

1. **Clear Orientation Message:**  
   *"Welcome to AP Command Center. Your workspace for reviewing invoices, understanding discrepancies and managing AP approvals."*
2. **Visual 5-Stage AP Workflow:**
   $$\text{Invoice Received} \longrightarrow \text{Data Extracted} \longrightarrow \text{Records Checked} \longrightarrow \text{Issues Reviewed} \longrightarrow \text{Approval Decision}$$
   Each stage features a distinct icon, numerical counter, and concise explanation (e.g. Ingestion $\rightarrow$ OCR $\rightarrow$ 4-Way Match $\rightarrow$ Exception Triage $\rightarrow$ Dual Sign-Off).
3. **Transparent Operational Boundary:**  
   Highlights upfront: *"Internal AP review sign-off only • Does NOT disburse funds from bank accounts."*
4. **Three Frictionless Choices:**
   - **Start Guided Tour:** Launches the 8-step interactive tour starting at Today's AP Operations.
   - **Explore on My Own:** Dismisses the modal and permanently records user preference.
   - **Skip for Now:** Dismisses the modal for the current session without permanently suppressing future access.

---

### B. 8-Step Interactive Guided Tour (`frontend/src/components/onboarding/GuidedTour.tsx`)

The interactive tour walks the user through the real product surfaces, synchronizing browser navigation automatically:

| Step | Surface Route | Highlighted Element | Plain-Language Learning Outcome |
|---|---|---|---|
| **1** | `/today` | Top KPI Triad (`today-kpi-bar`) | How the Daily Triad prioritizes urgent discrepancies, verified bills ready for sign-off, and statutory MSME liabilities. |
| **2** | `/invoices` | Operational Queue Tabs (`inbox-queue-tabs`) | How invoices are segmented into *Needs Attention*, *Ready for Approval*, and *Waiting on Evidence*, plus FY/month filtering and drag-and-drop file ingestion. |
| **3** | `/invoices/:id` | 50/50 Workspace (`workspace-split`) | Side-by-side inspection comparing original PDF (pan/zoom, SHA-256 fingerprint) against extracted vendor records and the 48px sticky verdict strip. |
| **4** | `/invoices/:id` | Policy Gates Trigger (`policy-gates-trigger`) | Understanding automated governance checks (GSTIN matching, arithmetic sums, duplicate detection, statutory due dates). |
| **5** | `/invoices/:id` | 4-Way Match Grid (`reconciliation-flow`) | Comparing Invoice vs PO vs GRN vs QC with strict 0.00% quantity shortage and $\le 1.50\%$ rate tolerance badges and in-place correction. |
| **6** | `/exceptions` | Discrepancy Table (`exceptions-table`) | Triage of blocked bills, MSME 45-day countdown deadlines, and reassigning ownership to buyers or specialists. |
| **7** | `/approvals` | Dual Governance Table (`approvals-table`) | High-value ($\ge ₹5,00,000$) dual sign-offs, anti-self-approval enforcement, and Controller sign-off modal. Explains treasury decoupling. |
| **8** | `/audit` | Audit Event Table (`audit-table`) | Append-only immutable log, cryptographic correlation IDs, state diffs, and 1-click CSV export for external auditors. |

#### Tour Interaction Design:
- **Visual Focus Halo:** Highlights target elements with a glowing focus ring without masking or breaking DOM interactivity.
- **Docked Floating Card:** Anchored at the bottom-right viewport dock to guarantee that primary data tables, document viewers, and line items are never obscured.
- **Step Progress Bar:** Displays fractional progress (e.g., `Step 3 of 8 (38%)`) with clickable dot indicators allowing quick navigation across steps.
- **Operator Tips:** Every step provides a practical operator tip grounded in day-to-day accounting realities.
- **Keyboard Navigation:** Supports `ArrowRight` (Next), `ArrowLeft` (Back), and `Escape` (Exit Tour).

---

### C. Persistent Contextual Help Drawer (`frontend/src/components/onboarding/ContextualHelpDrawer.tsx`)

Accessible at any time via:
1. The **Help** button in the Top Header Bar (`HelpCircle` icon).
2. The **AP Assistant & Help** button in the Sidebar Footer.
3. The global keyboard shortcut (`?`).

#### Key Sections:
1. **On This Screen (Context-Aware):**  
   Reads `location.pathname` dynamically to explain the exact screen the user is viewing, key components, and recommended next actions.
2. **Workflow Overview:**  
   Detailed breakdown of the 5 automated stages of AP Command Center with operational mechanisms.
3. **Plain-Language Terminology (Searchable Glossary):**  
   Comprehensive definitions for:
   - **PO (Purchase Order):** Commercial document detailing items, quantities, and agreed contracted prices.
   - **GRN (Goods Receipt Note):** Warehouse proof of physical goods receipt.
   - **QC Record:** Inspection certificate validating materials passed physical quality standards.
   - **3-Way & 4-Way Match:** Verification comparing Invoice + PO + GRN (+ QC).
   - **Price Variance Tolerance:** Permitted fluctuation up to $\pm 1.50\%$ for statutory fuel/commodity adjustments.
   - **Quantity Shortage Tolerance:** Strict 0.00% shortage tolerance.
   - **Dual-Approval Invariant:** Mandatory two-person review for bills $\ge ₹5,00,000$.
   - **Statutory MSME (Section 15):** Indian legal requirement to settle micro/small enterprise bills within 45 days.
   - **Not Checked / Unavailable Status:** Explains that pending checks do not indicate failure.
   - **Debit Note:** Accounting adjustment issued for short deliveries or rate discrepancies.
4. **Frequently Asked Questions (Accordion):**  
   Answers high-friction questions (e.g., *"Does approving an invoice pay the supplier?"*, *"Why is an invoice marked Action Required?"*, *"Can I correct OCR misreads?"*).
5. **Quick Actions:**  
   1-click buttons to restart the 8-step interactive tour or reopen the initial Welcome Guide.

---

## 3. Persistence & State Management (`frontend/src/context/TourContext.tsx`)

The onboarding state is managed through `TourContext`:
- `ap_onboarding_welcome_dismissed`: Tracks whether the welcome modal has been seen or dismissed.
- `ap_onboarding_tour_completed`: Tracks whether the tour has been completed or exited.
- State persists across page refreshes and route changes in `localStorage`.
- Users can restart the tour or reopen the welcome dialog at any time through the Help Drawer.
- Zero backend dependencies: The entire onboarding state is client-managed.

---

## 4. Accessibility & Responsive Design

- **Viewport Adaptation:** The tour card auto-resizes across mobile (`w-[calc(100vw-2.5rem)]`) and desktop (`max-w-md`), positioning itself cleanly without covering screen headers or navigation bars.
- **Contrast & Dark Mode:** Designed with semantic theme tokens matching both high-contrast light and dark modes.
- **Scroll Synchronization:** `scrollIntoView({ behavior: 'smooth', block: 'center' })` ensures off-screen elements are smoothly scrolled into view when a tour step activates.
- **Keyboard Traps Prevented:** Full keyboard support (`Escape` to close, `Arrow` keys for step navigation).

---

## 5. Verification & Quality Gates

1. **Frontend Production Build:**
   ```bash
   npm --prefix frontend run build
   # tsc -b && vite build -> Exit code 0 (2,101 modules transformed, 0 TypeScript errors)
   ```
2. **Frontend Linter Check:**
   ```bash
   npm --prefix frontend run lint
   # oxlint -> Exit code 0 (0 errors)
   ```
3. **Automated Truth & Plain Language Suite:**
   ```bash
   python -m pytest tests/phase_1/test_phase1_truth_and_plain_language.py
   # 6/6 tests passing (100% PASS)
   ```

---

## 6. Files & Components Created/Modified

- `frontend/src/context/TourContext.tsx`: Core tour state machine, 8-step definitions, route synchronizer, and persistence.
- `frontend/src/components/onboarding/WelcomeModal.tsx`: Visual first-time welcome dialog with 5-step AP pipeline diagram.
- `frontend/src/components/onboarding/GuidedTour.tsx`: Floating step-by-step tour guide with element focus ring and keyboard controls.
- `frontend/src/components/onboarding/ContextualHelpDrawer.tsx`: Slide-over help drawer with context-aware screen guide, glossary, and FAQs.
- `frontend/src/components/onboarding/index.ts`: Clean export barrel for onboarding components.
- `frontend/src/components/AppShell.tsx`: Wired Help button in top header, keyboard shortcut `?`, and overlay mounts.
- `frontend/src/components/Sidebar.tsx`: Added persistent AP Assistant & Help entry point in sidebar footer.
- `frontend/src/App.tsx`: Wrapped application with `TourProvider` within the routing context.
- `frontend/src/pages/DashboardPage.tsx`: Added `data-tour="today-kpi-bar"`.
- `frontend/src/pages/InboxPage.tsx`: Added `data-tour="inbox-queue-tabs"`.
- `frontend/src/pages/InvoiceDetailPage.tsx`: Added `data-tour="workspace-split"`, `policy-gates-trigger`, and `reconciliation-flow`.
- `frontend/src/pages/ExceptionsPage.tsx`: Added `data-tour="exceptions-table"`.
- `frontend/src/pages/ApprovalsPage.tsx`: Added `data-tour="approvals-table"`.
- `frontend/src/pages/AuditPage.tsx`: Added `data-tour="audit-table"`.
