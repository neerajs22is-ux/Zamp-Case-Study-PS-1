# Rossum UI/UX & Frontend Architecture Analysis

**Target Application:** `https://svit.rossum.app/` (Rossum Cloud Platform)  
**Verification Framework:** Chrome DevTools Protocol Telemetry & Playwright DOM Inspection  
**Audit Date:** November 03, 2026  
**Trial Organization:** `SVIT` (User: `Neeraj S`)  

---

## 1. Frontend Technology Stack & Foundation

Through DOM inspection and runtime script bundle analysis, Rossum's frontend architecture was directly verified:

- **Component Framework:** React 18 with modern hook-based state management.
- **UI Component Library:** Material-UI (MUI v5) utilizing `@emotion/styled` and `@emotion/react` for scoped CSS-in-JS styling. Clean prefix classes observed across all components (`MuiBox-root`, `MuiStack-root`, `MuiTypography-root`, `MuiButtonBase-root`, `MuiPopover-root`, `MuiDrawer-root`).
- **Build & Module Bundling:** Vite with Rolldown runtime (observed via bundle manifests `rolldown-runtime-2vkpuf-H.js` and `vendor-ace-V1Uwnp2Z.js`).
- **Telemetry & Monitoring:** Sentry React SDK (`v8.34.0`, observed via active ingest endpoints and DOM `data-sentry-component` / `data-sentry-source-file` attributes on key elements like `AddFilterButton.tsx` and `DetailDrawer.tsx`).
- **Feature Flagging:** Unleash Proxy API (`/unleash/proxy?sessionId=...&appName=elis-frontend`).
- **Customer Engagement:** Freshworks / Freshchat embedded live widget (`euc-widget.freshworks.com`).

---

## 2. Design System & Visual Hierarchy

### Typography System
- **Primary Typeface:** `Inter` (licensed via custom woff2 webfonts: `Inter-Regular-COLGFB3M.woff2` and `Inter-SemiBold-BAEEcJ4E.woff2`).
- **Type Scale:**
  - Page Titles / Headings: 20px–24px SemiBold (MUI `h6` / `h5`).
  - Section Headers: 14px–16px Medium with uppercase letter-spacing (e.g., `BASIC INFORMATION`, `TOTALS AND SUBTOTALS`).
  - Data Labels: 12px Regular with secondary text color (`#64748B` Slate), providing strong distinction from values.
  - Data Values / Inputs: 14px Regular with primary high-contrast text (`#0F172A`).
  - Metadata / Help text: 11px–12px Regular in helper text wrappers (`MuiFormHelperText-root`).

### Color Palette & Semantic System
- **Backgrounds:**
  - Workspace Base: Clean off-white canvas (`#F8FAFC` / Slate 50).
  - Review Panels: Pure white (`#FFFFFF`) cards with subtle 1px border dividers (`#E2E8F0`).
  - Document Viewer Background: Neutral dark gray / medium slate (`#334155`), providing high visual contrast behind scanned document pages.
- **Primary Brand Color:** Deep Royal Blue / Indigo (`#2563EB` to `#1D4ED8`), used for primary CTA buttons (`Confirm`), active navigation tabs, and field selection borders.
- **Semantic Signals:**
  - **Required / Error State:** High-arousal crimson (`#DC2626` / Red 600), marked by high-contrast question-mark badges (`?`) and red borders around missing mandatory fields.
  - **Valid / Confirmed State:** Forest Emerald (`#16A34A` / Green 600), applied to verified badges and confirmed queue rows.
  - **Warning / Review Needed:** Amber (`#D97706`), applied to low-confidence OCR predictions.
  - **Bounding Box Highlights:** Translucent cyan/blue SVG bounding rectangles (`rgba(37, 99, 235, 0.2)` with `2px solid #2563EB` stroke), giving instantaneous visual confirmation without obscuring underlying text.

---

## 3. Top-Level Navigation & Layout Architecture

Rossum employs a persistent top-navigation header paired with a contextual left-hand sidebar for queue management:

```text
┌────────────────────────────────────────────────────────────────────────────────────────┐
│  Rossum Logo   [Documents]  [Automation]  [Extensions]  [Statistics]  [Settings]   [NS]│
├─────────────────────────┬──────────────────────────────────────────────────────────────┤
│  SVIT Workspace         │  Active Queue: Credit Notes (1 doc)           [Upload Files] │
│  - All documents (23)   ├──────────────────────────────────────────────────────────────┤
│  - Credit notes (1)     │  [Reviews (1)]  [Postpone]  [All]    [Filter] [Clear]        │
│  - Debit notes (2)      ├──────────────────────────────────────────────────────────────┤
│  - Delivery notes (1)   │  [ ] Status    Document Name           Details               │
│  - Pro forma (2)        │  [ ] To review [SAMPLE]_credit-note.pdf                      │
│  - Purchase orders (5)  │                                                              │
│  - Tax invoices EU (4)  │                                                              │
│  - Tax invoices UK (3)  │                                                              │
│  - Tax invoices US (5)  │  Showing 1 of 1 documents                   [100 per page]   │
└─────────────────────────┴──────────────────────────────────────────────────────────────┘
```

### Navigation Hierarchy
1. **Primary App Tabs (Top Bar):**
   - `Documents` (`/documents`): Operational reviewer workbench and queue manager.
   - `Automation` (`/automation`): Automation rules, AI engine tuning, and queue routing logic.
   - `Extensions` (`/extensions`): Extension hub and Rossum Store integration marketplace.
   - `Statistics` (`/statistics`): Executive reporting, turnaround metrics, and reviewer productivity graphs.
   - `Settings` (`/settings`): Organization admin, Queue manager, Field manager, User RBAC, and audit logs.
2. **Contextual Sidebar (Left Drawer):**
   - Displays workspace name (`SVIT`) and total document workload (`23`).
   - Lists preconfigured queues with live unread/pending document badges.
   - Includes a global `All documents` entry allowing cross-queue document triage.

---

## 4. Document Queue Experience & Workload Management

### Strengths
1. **Queue Categorization by Schema:** Documents are segregated by operational type (`Credit notes`, `Tax invoices US`, `Purchase orders`). Each queue possesses an independent extraction schema, avoiding messy multi-schema forms.
2. **Global Aggregation (`All documents`):** Supervisors and team leads can click `All documents` to view the entire organization's ingestion queue across all 8 queues simultaneously (`EV-002`).
3. **Pill-Style Status Filters:** Instant toggle between documents needing review (`Reviews (1)`), delayed/blocked documents (`Postpone`), and total history (`All`).
4. **Non-Intrusive Ingestion:** The `Upload` CTA opens a clean modal drag-and-drop zone with zero page reloads (`EV-025`).

### Weaknesses & Ergonomic Friction
1. **Sparse Queue Columns by Default:** The default queue table renders only 3 columns: `Status`, `Document name`, and `Details`. Crucial financial metadata (Supplier name, Total Amount, Due Date, Ingestion timestamp) is hidden from the queue view until the document is opened.
2. **Popover Backdrop Interception:** The "Add Filter" button spawns a modal backdrop that intercepts clicks on other table controls if dismissed improperly (`EV-003`).

---

## 5. Review Workspace Layout & Ergonomics

The document review workspace (`/document/<id>`) is Rossum's flagship screen:

### Layout Allocation
- **Viewport Utilization:** Fixed 50/50 horizontal split (at 1920x1080 resolution):
  - Left 50% (~960px): Document Viewer Canvas (SVG text layer, zoom controls, rotation).
  - Right 50% (~960px): Structured Data Extraction Panel (collapsible sections, fields, line items).
- **Persistent Header:** Contains Document Name, Page Counter (`1/1`), Error Counter Badge (`1 error / 0 warnings`), and the primary action button (`Confirm`).
- **Auxiliary Drawers:** Top-right icon buttons toggle slide-out flyout panels (`DetailDrawer.tsx`) for `Find in Document`, `Document Info`, and `Document Comments`.

### Document Viewer Ergonomics
- The viewer renders scanned invoices at crisp vector/bitmap resolutions.
- Floating toolbar on bottom-left offers `Zoom In`, `Zoom Out`, `Reset Zoom`, and `Fit to Width`.
- **Keyboard Translation:** Real-time translation toggle via `Ctrl + T` allows non-native reviewers to translate European or Japanese invoices on the fly.
- **In-Viewer Text Search:** Reviewers can search any text string directly on the canvas without relying on browser native search (`Ctrl+F`).

---

## 6. Usability Evaluation: First-Time Finance Operator

**Could a finance operator unfamiliar with Rossum understand the document queue, review an invoice, and complete the task without another person explaining the interface?**

### Verdict: YES (With High Learnability)
- **Guided Tour:** On first load, Rossum presents an automatic 3-step interactive walkthrough (`01_onboarding_review_tour.png`) explaining how fields map to the PDF.
- **Unambiguous Error Indicators:** Missing required values are flagged with high-visibility red `?` badges. A prominent error counter (`1`) in the header immediately signals that the document is blocked from completion.
- **Point-and-Click Field Correction:** Even if a reviewer has no technical background, clicking an empty field and clicking the corresponding number on the invoice instantly populates the value.
- **Confirmation Feedback Loop:** The immediate post-confirmation feedback prompt gives the user immediate closure and validates that their correction was submitted.
