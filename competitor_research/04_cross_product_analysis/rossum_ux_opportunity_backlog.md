# Rossum vs Zamp AP Command Center — Prioritized UX & Workflow Opportunity Backlog

**Target Competitor:** Rossum Cloud Platform (`https://svit.rossum.app/`)  
**Our Product:** Zamp AP Command Center  
**Methodology:** Evidence-Based Product Optimization & Reviewer Ergonomics Backlog Formulation  
**Date:** November 03, 2026  

---

## 1. Classification Taxonomy

- **IMPLEMENT:** A clear improvement directly supported by Rossum evidence that fills an acute operational gap.
- **ADAPT:** A valuable Rossum pattern that must be re-engineered to fit our AP policy validation and 3-way matching architecture.
- **SIMPLIFY:** An existing screen or interaction in our application that causes reviewer fatigue and should be streamlined.
- **REMOVE:** An unnecessary step, redundant tab, or interaction that adds friction without operational value.
- **KEEP:** An area where Zamp already outperforms Rossum and should be firmly preserved.
- **DO NOT IMPLEMENT:** Competitor features that are irrelevant, unsafe, violate compliance gates, or fall outside our AP product scope.

---

## 2. Master Prioritized Opportunity Backlog

---

### Item 1: Bidirectional SVG Bounding Box Mesh & Coordinate Auto-Centering
- **Classification:** **IMPLEMENT**
- **Priority:** **P0 (Critical)**
- **Complexity:** High
- **Current Zamp Behavior:** `InvoiceDetailPage.tsx` displays an embedded PDF preview `<iframe>` on the left and extracted data on the right. Clicking an extracted field does nothing to the PDF viewer. The database schema holds `bounding_box: null`. Reviewers must visually scan the entire document to locate numbers.
- **Rossum Observed Behavior:** Rossum pre-renders 51+ vector SVG `<rect>` elements (`basepageContainerLayout`) over the document canvas (`evidence_log.md` EV-008–010, `review_workspace_analysis.md` §2). Clicking any field instantly auto-scrolls the canvas to center the target bounding box and highlights it with a pulsing translucent blue rectangle (`rgba(37, 99, 235, 0.2)` with `2px solid #2563EB` stroke).
- **Evidence Reference:** `review_workspace_analysis.md` §2, `screenshots/document_review/04_field_highlight_issue_date.png`, `05_field_highlight_vendor_name.png`.
- **User Problem:** When verifying high-value amounts, tax numbers, or line items, AP clerks suffer severe eye fatigue hunting across dense, multi-page invoices to find where each number originated.
- **Specific Proposed Change:**
  1. Update `engine/hybrid_extractor.py` and `engine/ocr_engine.py` to persist normalized bounding box coordinates `[ymin, xmin, ymax, xmax]` for all extracted header fields and line items.
  2. Replace static `<iframe>` preview with an interactive PDF.js / SVG overlay component.
  3. Bind field click and focus events to dispatch coordinate centering: `canvas.scrollTo({ top: bbox.ymin - 100, behavior: 'smooth' })`.
  4. Render the active bounding box as an SVG `<rect>` with translucent fill.
- **Expected Benefit:** Halves document verification dwell time; provides instant visual verification proof for AP clerks and auditors.
- **Dependencies & Risks:** Requires OCR coordinate extraction in backend pipeline and SVG canvas renderer in frontend.

---

### Item 2: In-Place Field & Line Correction via Contextual Floating Input
- **Classification:** **ADAPT**
- **Priority:** **P0 (Critical)**
- **Complexity:** Medium
- **Current Zamp Behavior:** Extracted fields and line items in `InvoiceDetailPage.tsx` and `ProcurementVerificationFlow.tsx` are 100% read-only in the UI. If the OCR engine makes a trivial typo (e.g. `2026-10-01` misread as `2026-10-10`), the invoice fails policy gates and must be rejected or put on hold.
- **Rossum Observed Behavior:** Rossum mounts a dynamic floating input textarea (`editBoxInput`) over the active field (`evidence_log.md` EV-017, `review_workspace_analysis.md` §5). Reviewers can type corrections directly, press `Enter` to commit and advance, or click/drag across text on the PDF canvas to auto-populate the field.
- **Evidence Reference:** `review_workspace_analysis.md` §5, `screenshots/exceptions/02_document_id_focused_input.png`, `04_document_id_corrected_resolved.png`.
- **User Problem:** Clerks are trapped in administrative dead-ends for 1-character OCR errors that take 2 seconds to fix.
- **Specific Proposed Change:**
  1. Add an inline edit capability to the Extracted Information and Line-by-Line Match tables.
  2. When a field is edited, auto-recalculate the 7 policy validation gates.
  3. Create backend endpoint `PUT /api/v1/invoices/{id}/corrections` that logs an append-only `FIELD_CORRECTED` audit event with previous value, new value, actor ID, and timestamp.
  4. **Adaptation for AP Governance:** Unlike Rossum's free-form editing, Zamp must require that field corrections re-run the 7 deterministic policy gates immediately. If a correction causes a tolerance breach, approval remains blocked.
- **Expected Benefit:** Eliminates 80% of unnecessary rejection loops caused by minor OCR transcription errors.
- **Dependencies & Risks:** Backend correction endpoint and audit logging. Mitigated by re-running policy gates on save.

---

### Item 3: Continuous Assembly-Line Review Loop ("Confirm & Next")
- **Classification:** **ADAPT**
- **Priority:** **P1 (High)**
- **Complexity:** Low
- **Current Zamp Behavior:** When an AP clerk approves an invoice or executes a triage action in `InvoiceDetailPage.tsx`, the application updates the record and leaves the clerk sitting on the same detail page. The clerk must click `Return to Invoices`, wait for the inbox to load, find the next invoice row, and click to open it (2 clicks + 2 screen switches).
- **Rossum Observed Behavior:** Rossum is engineered for continuous queue processing (`workflow_analysis.md` §1, `queue_to_completion.mmd`). Confirming an invoice immediately loads the next pending document in the active queue without returning to the list view (0 clicks).
- **Evidence Reference:** `workflow_analysis.md` Journey 9, `workflow_maps/queue_to_completion.mmd`.
- **User Problem:** High-volume AP clerks reviewing 50–100 clean invoices daily waste significant time and mental energy navigating back and forth between list and detail views.
- **Specific Proposed Change:**
  1. Add an "Approve & Next" primary action button on `InvoiceDetailPage.tsx` for clean-match invoices.
  2. When executed, the server records internal AP approval and returns the ID of the next pending invoice in the active filtered queue.
  3. The frontend immediately updates URL to `/invoices/{next_id}` and loads the new document without a full inbox reload.
  4. Provide a toggle in the reviewer toolbar: `[✓] Auto-advance to next document`.
- **Expected Benefit:** Saves 2 clicks and 2 page transitions per invoice, saving ~15 minutes per 50 invoices reviewed.
- **Dependencies & Risks:** Purely frontend navigation enhancement; preserves all single-invoice audit logs and policy gates.

---

### Item 4: Field-to-Field Tab Navigation with Synchronized Canvas Scrolling
- **Classification:** **IMPLEMENT**
- **Priority:** **P1 (High)**
- **Complexity:** Medium
- **Current Zamp Behavior:** Users must use the mouse to switch between tabs and click individual rows in the line items grid. Keyboard shortcuts (`1-4`, `d`, `a`, `h`, `c`, `s`, `r`) exist for tabs and actions, but there is no keyboard way to traverse fields.
- **Rossum Observed Behavior:** Reviewers use `Tab` and `Shift+Tab` to advance sequentially through every extracted field in the schema (`review_workspace_analysis.md` §6). As focus moves from field to field, the document viewer automatically pans and scrolls to keep the active field's source bounding box in view.
- **Evidence Reference:** `review_workspace_analysis.md` §6, `screenshots/navigation/06_keyboard_shortcuts_sheet.png`.
- **User Problem:** Operators reviewing dozens of invoices per hour experience repetitive strain from switching between mouse clicking on fields and keyboard typing.
- **Specific Proposed Change:**
  1. Implement roving tabindex across extracted header fields and line-item cells.
  2. Pressing `Tab` focuses the next field and dispatches smooth scroll to the document canvas.
  3. Pressing `Shift+Tab` moves to the previous field.
  4. Pressing `Enter` opens the field for in-place correction.
- **Expected Benefit:** Enables true zero-mouse keyboard review for fast operators.
- **Dependencies & Risks:** Requires SVG bounding box coordinates (Item 1).

---

### Item 5: In-Viewer Full-Text Search ("Find in Document")
- **Classification:** **IMPLEMENT**
- **Priority:** **P2 (Medium)**
- **Complexity:** Medium
- **Current Zamp Behavior:** Zamp provides top-level invoice search in the Inbox (`/invoices`), but inside the review workspace (`InvoiceDetailPage.tsx`), there is no in-document text search. Reviewers must rely on browser native `Ctrl+F`, which does not highlight words inside embedded iframes reliably.
- **Rossum Observed Behavior:** Rossum provides an in-viewer "Find in document" search bar (`screenshots/document_review/09_find_in_document.png`, `EV-012`). Typing a query instantly highlights all matching OCR words on the document canvas in yellow and allows cycling through matches.
- **Evidence Reference:** `evidence_log.md` EV-012, `screenshots/document_review/09_find_in_document.png`.
- **User Problem:** Reviewers examining 10-page contracts or multi-page equipment bills struggle to find specific clauses, PO numbers, or line descriptions on the PDF.
- **Specific Proposed Change:**
  1. Add a search icon and input in the left pane document viewer toolbar.
  2. Leverage the OCR text token payload to perform substring matching.
  3. Highlight matching words on the canvas and provide `Prev / Next` result chevrons.
- **Expected Benefit:** Instant navigation across multi-page complex vendor invoices.
- **Dependencies & Risks:** Requires word-level OCR token coordinates from backend.

---

### Item 6: Turnaround Time & Operator Velocity Analytics
- **Classification:** **ADAPT**
- **Priority:** **P2 (Medium)**
- **Complexity:** Medium
- **Current Zamp Behavior:** `DashboardPage.tsx` tracks company-wide pipeline velocity (Received → Exceptions → Ready → Approved) and financial risk (blocked INR in exceptions). It does not track how long invoices spend in review or individual operator turnaround time.
- **Rossum Observed Behavior:** Rossum's `/statistics` dashboard tracks average turnaround time in seconds, on-time vs. late SLA compliance, and reviewer corrections per document (`evidence_log.md` EV-023, `screenshots/dashboard/01_statistics_dashboard_full.png`).
- **Evidence Reference:** `evidence_log.md` EV-023, `screenshots/dashboard/01_statistics_dashboard_full.png`, `ui_ux_analysis.md` §6.
- **User Problem:** AP managers have no data on how fast their team is processing invoices or which suppliers generate the most manual review friction.
- **Specific Proposed Change:**
  1. Track time elapsed between invoice ingestion and final sign-off.
  2. Add an "Operational Velocity" card to `/audit` or `/today` showing median review time (e.g., `Median Review Dwell: 42s`).
  3. Track exception frequency by supplier to identify repeat offenders who submit non-compliant invoices.
- **Expected Benefit:** Gives AP directors visibility into operational bottlenecks without spying on clerks.
- **Dependencies & Risks:** Minor backend metrics aggregation in `backend/api/v1/dashboard.py`.

---

### Item 7: Consolidate Redundant Analysis Tabs & Layout Clutter
- **Classification:** **SIMPLIFY**
- **Priority:** **P2 (Medium)**
- **Complexity:** Low
- **Current Zamp Behavior:** `InvoiceDetailPage.tsx` displays 4 tabs: `Matching & Lines`, `Policy Checks`, `Extracted Information`, and `Audit Trail`. Header amounts and taxes are repeated across three different views.
- **Rossum Observed Behavior:** Consolidates all extracted data into a single scrollable form with collapsible cards (`Basic Information`, `Totals`, `Line Items`), keeping everything in one place.
- **Evidence Reference:** `InvoiceDetailPage.tsx` L827–880, `review_workspace_analysis.md` §3.
- **User Problem:** Redundant tabs create unnecessary navigation clicks. Users flip between Tab 1 and Tab 3 to see the same data.
- **Specific Proposed Change:**
  1. Fold Tab 3 (`Extracted Information`) into a compact header summary inside Tab 1.
  2. Reduce tabs from 4 to 3: `1. 3-Way Match & Data`, `2. Policy Gates`, `3. Audit Trail`.
- **Expected Benefit:** Eliminates 33% of tab switching; keeps all relevant invoice figures on a single screen.
- **Dependencies & Risks:** Purely frontend layout consolidation.

---

### Item 8: Remove Post-Confirmation Feedback Survey Pattern
- **Classification:** **REMOVE / DO NOT IMPLEMENT**
- **Priority:** **Anti-Pattern Rejection**
- **Complexity:** N/A
- **Rossum Observed Behavior:** Every manual confirmation in Rossum triggers a micro-survey modal ("How satisfied are you with data extraction from your document? Angry/Neutral/In love") (`evidence_log.md` EV-018, `screenshots/exceptions/03_confirm_blocked_or_modal.png`).
- **Rationale for Rejection:** In high-volume enterprise AP environments where operators process 300+ invoices daily, adding a mandatory survey after every invoice imposes 300 unnecessary dismiss clicks. It causes severe reviewer frustration. Zamp must strictly reject this pattern.

---

### Item 9: Preserve Authoritative 3-Way Matching, 7 Policy Gates & Dual Control
- **Classification:** **KEEP**
- **Priority:** **P0 (Foundational Standard)**
- **Complexity:** N/A (Existing Core Strength)
- **Current Zamp Behavior:** Zamp's 4-node Procurement Verification Flow (Invoice Claim vs PO Contract vs GRN Receipt vs QC Certificate), 7 deterministic policy gates, and mandatory ₹5,00,000 dual-approval threshold.
- **Rossum Observed Behavior:** Rossum is purely an IDP document reader; it has zero native 3-way matching, no GRN verification, no QC inspection checks, and no dual-approval controls.
- **Evidence Reference:** `rossum_vs_ap_command_center.md` §5, `feature_inventory.md` §2.4, §2.8.
- **Rationale for Keeping:** This is Zamp's fundamental value proposition and primary competitive moat. Under no circumstances should Zamp dilute its AP governance or policy gates to mimic Rossum's generic document extraction.

---

### Item 10: Do NOT Implement Multi-Queue Document Silos
- **Classification:** **DO NOT IMPLEMENT**
- **Priority:** **Architectural Scope Boundary**
- **Complexity:** N/A
- **Rossum Observed Behavior:** Rossum splits workloads into 8 separate specialized queues (`Credit notes`, `Debit notes`, `Delivery notes`, `PO`, `Tax invoices US/UK/EU`), requiring supervisors to check 8 separate queues (`ui_ux_analysis.md` §4).
- **Rationale for Rejection:** Zamp is an AP Command Center, not an all-document capture hub. An AP clerk should not have to hunt across 8 queues to find invoices. Zamp's unified Inbox with quick-filter tabs (`Exceptions`, `Ready`, `Approved`, `Quarantine`) is far more efficient and intuitive for finance teams.

---

## 3. Summary Backlog Matrix

| ID | Title | Category | Priority | Complexity | Expected ROI / Impact |
|:---:|:---|:---:|:---:|:---:|:---|
| **REC-R01** | Bidirectional SVG Bounding Box Mesh & Coordinate Auto-Scroll | **IMPLEMENT** | **P0** | High | Halves document verification dwell time; provides instant visual proof |
| **REC-R02** | In-Place Field & Line Correction via Contextual Floating Input | **ADAPT** | **P0** | Medium | Eliminates 80% of unnecessary rejection loops due to minor OCR typos |
| **REC-R03** | Continuous Assembly-Line Review Loop ("Confirm & Next") | **ADAPT** | **P1** | Low | Saves 2 clicks and 2 page switches per invoice (~15 min / 50 invoices) |
| **REC-R04** | Field-to-Field Tab Navigation with Synchronized Canvas Scroll | **IMPLEMENT** | **P1** | Medium | Enables true zero-mouse keyboard review for high-speed operators |
| **REC-R05** | In-Viewer Full-Text Search ("Find in Document") | **IMPLEMENT** | **P2** | Medium | Instant navigation across complex multi-page vendor bills |
| **REC-R06** | Turnaround Time & Operator Velocity Analytics | **ADAPT** | **P2** | Medium | Identifies internal review bottlenecks and slow supplier documents |
| **REC-R07** | Consolidate Redundant Analysis Tabs & Layout Clutter | **SIMPLIFY** | **P2** | Low | Reduces tab flipping by 33% |
| **REC-R08** | Do NOT Introduce Post-Confirmation Feedback Surveys | **DO NOT IMPLEMENT** | **Anti-Pattern** | N/A | Prevents 300+ unnecessary survey dismiss clicks daily |
| **REC-R09** | Preserve Authoritative 3-Way Match & Dual-Control Rigor | **KEEP** | **P0** | N/A | Preserves Zamp's primary competitive moat and financial controls |
| **REC-R10** | Do NOT Fragment Invoices into Multi-Queue Silos | **DO NOT IMPLEMENT** | **Boundary** | N/A | Prevents workflow fragmentation; preserves unified AP pipeline |
