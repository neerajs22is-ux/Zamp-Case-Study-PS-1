# AP Command Center — End-to-End Acceptance Criteria & Quality Standards

| Metadata | Details |
|---|---|
| **Audited Spec** | [`FRONTEND_UX_IMPLEMENTATION_SPEC.md`](file:///c:/Zamp%20Casse%20Study/FRONTEND_UX_IMPLEMENTATION_SPEC.md) |
| **Roadmap Reference** | [`docs/UX_IMPLEMENTATION_ROADMAP.md`](file:///c:/Zamp%20Casse%20Study/docs/UX_IMPLEMENTATION_ROADMAP.md) |
| **Target Codebase** | `c:\Zamp Casse Study` @ commit `cda5c44` (Branch: `handoff/ap-command-center`) |
| **Craft Frameworks** | `stageshow` (authentic UI framing), `impeccable` (Operate mode, scannability, accessibility), `taste-skill` (anti-slop, clean typography). |

---

## 1. Acceptance Overview & Verification Philosophy

Every acceptance criterion defined below is **objective, measurable, and testable**. No feature is considered complete based on visual inspection alone; each requires verification through automated tests (`pytest`, unit tests) and interactive browser verification scripts.

---

## 2. Core Workflow Acceptance Criteria (E2E)

### AC-01: End-to-End Ingestion-to-Decision Pipeline (B-01)
- **Criterion:** An invoice uploaded via the web UI or received via Gmail synchronization must automatically trigger document extraction and deterministic matching, transitioning from `RECEIVED` to a terminal or actionable state (`Ready to approve` or `Needs attention`) without manual CLI intervention.
- **Verification Steps:**
  1. Authenticate as `sme_lead@company.internal`.
  2. Navigate to `/invoices` $\rightarrow$ click "Add invoices ▾" $\rightarrow$ select "Upload PDF".
  3. Upload `tests/evaluation_corpus_v2/invoices/01_invoice_AP_26_001.pdf`.
  4. Observe initial state: `Received — not yet extracted` with progress indicator.
  5. Within 20 seconds, poll returns updated status: `Ready to approve`.
  6. Open invoice review workspace $\rightarrow$ verify all 7 match gates have executed with status `PASS`.
  7. Click "Approve" $\rightarrow$ enter reason "Automated E2E ingestion verified" $\rightarrow$ confirm.
  8. Verify status updates to `Approved` with banner: *"Internal review complete. Not yet paid or posted."*
- **Pass Threshold:** 100% of valid uploaded PDFs transition out of `RECEIVED` automatically; `IngestionJob.status == "COMPLETED"`; 0 unhandled exceptions.

---

### AC-02: Exception Lifecycle Synchronization (B-02)
- **Criterion:** When an invoice with an active exception is approved, quarantined, or rejected, its associated `ExceptionRecord` must transition to `status = "RESOLVED"` in the database, and the invoice must immediately disappear from the "Needs attention" queue and dashboard open exception counts.
- **Verification Steps:**
  1. Inspect invoice `APTC-002` (seeded with price variance exception in `OPEN` status).
  2. Verify invoice appears in `/invoices?tab=needs-attention` and is counted in "Value waiting on you".
  3. Open invoice workspace $\rightarrow$ verify Gate 6 shows `FAIL` (Price & Quantity Tolerance).
  4. Click "Ask supplier to correct" $\rightarrow$ select reason template "Unit rate exceeds PO rate" $\rightarrow$ submit.
  5. Verify invoice moves to "Waiting" tab with substatus "Waiting for supplier".
  6. Execute `APPROVE_AP_REVIEW` (with override acknowledgement) or `QUARANTINE`.
  7. Query database: `SELECT status, resolution_notes FROM exception_records WHERE invoice_id = :id`.
- **Pass Threshold:** `ExceptionRecord.status == "RESOLVED"`; `GET /api/v1/exceptions` returns 0 rows for this invoice; dashboard `open_exceptions` count decrements by exactly 1.

---

### AC-03: Rejection Action Semantics (`REJECT_INVOICE`) (B-07)
- **Criterion:** The application must provide a dedicated "Reject invoice" action that permanently marks an invoice as rejected, closes exceptions, and prevents subsequent approvals.
- **Verification Steps:**
  1. Open an invoice in `Needs attention` status.
  2. In the decision bar, click "Reject invoice".
  3. Verify confirmation panel prompts for mandatory reason ($\ge 10$ chars).
  4. Select reason chip: "Duplicate invoice submission" $\rightarrow$ click "Confirm Rejection".
  5. Verify invoice status updates to `Rejected` (red chip).
  6. Verify decision bar is disabled (no further approvals permitted).
  7. Verify `audit_trail_events` records an event with `action="REJECT_INVOICE"`.
- **Pass Threshold:** HTTP status 200; `Invoice.decision == "REJECTED"`; subsequent approval attempts return HTTP 400.

---

## 3. Flagship Review Workspace Acceptance Criteria

### AC-04: Embedded Document Viewer (Pane 1)
- **Criterion:** The original invoice PDF must be rendered directly within the workspace layout without requiring external tabs or popups. Expired signed URLs must automatically refresh without breaking user focus.
- **Verification Steps:**
  1. Open `/invoices/:id` in browser.
  2. Verify left panel embeds PDF via `<object>` or `<iframe>` showing pages, zoom controls, and scrollable canvas.
  3. Verify file header renders: filename, human-readable size, truncated SHA-256 with copy button, and "Open original in new tab" link.
  4. Mock a 403 Forbidden response on the PDF signed URL $\rightarrow$ verify client silently calls `GET /api/v1/documents/{id}/signed-url` and refreshes the embed without page reload.
- **Pass Threshold:** PDF renders within 1.5 seconds of page load; zero broken embed icons.

---

### AC-05: Side-by-Side PO Line Comparison & Variance Evidence (Pane 2) (B-05)
- **Criterion:** Billed invoice lines must be displayed directly alongside PO contracted rates and quantities, highlighting variances in clear tabular layout.
- **Verification Steps:**
  1. Open invoice `APTC-002` (Scenario 2: Price Variance).
  2. In the Matching tab, inspect the line items table.
  3. Verify columns: `#`, `Description`, `Billed (Qty / Rate / Total)`, `PO (Qty / Rate)`, `Variance %`.
  4. Verify the line with ₹1,250 billed vs ₹1,200 PO rate displays a clear variance chip: `+4.17%` styled with amber/red warning tone.
  5. Verify Tax Summary displays Calculated GST vs Billed GST.
- **Pass Threshold:** Tabular numbers aligned to the right; variances exceeding $\pm 1.5\%$ visually highlighted; zero blank columns when PO data is present.

---

### AC-06: Match Gates Evidence & Notes Presentation
- **Criterion:** All 7 deterministic match gates must display plain-language names, pass/fail indicators, detailed explanation notes, and copyable evidence source references.
- **Verification Steps:**
  1. In Review Workspace, navigate to the **Checks** tab.
  2. Verify all 7 gates are present:
     - Check 1: Supplier is registered (Vendor Identity)
     - Check 2: Purchase order found and valid (PO Authorization)
     - Check 3: Goods receipt found (GRN Receipt)
     - Check 4: Quality check passed (QC Inspection)
     - Check 5: GST adds up (GST Arithmetic)
     - Check 6: Price and quantity match the PO (Tolerance)
     - Check 7: Not a duplicate (Duplicate Invoice)
  3. For Gate 6 on a variance invoice, verify note is rendered: `"Unit price ₹1,250 exceeds contracted rate ₹1,200 by 4.2% (tolerance: ±1.5%)"`.
  4. Verify `Source: PO-26-1002` chip includes one-click copy button.
- **Pass Threshold:** 100% of returned `match_gates` display their `notes` and `evidence_source_id`.

---

### AC-07: Failed-Gate Override Protection & Reason Templates
- **Criterion:** Approving an invoice with one or more failed gates must be blocked for AP Associates and must require explicit override acknowledgment and justification for AP Leads and Controllers.
- **Verification Steps:**
  1. Sign in as `sme_associate@company.internal` $\rightarrow$ open `APTC-002` (failed Gate 6).
  2. Verify "Approve" button is disabled with tooltip: *"Requires AP Lead or Controller override due to failed checks."*
  3. Sign in as `sme_lead@company.internal` $\rightarrow$ open `APTC-002`.
  4. Verify button reads "Approve anyway...".
  5. Click button $\rightarrow$ confirm modal appears with unchecked box: *"I have reviewed the failed check(s) [Price and quantity match PO] and authorize an operational override."*
  6. Attempt to submit without ticking box $\rightarrow$ submission blocked.
  7. Tick box $\rightarrow$ select reason chip "Variance within agreed tolerance; approved" $\rightarrow$ click Confirm.
  8. Verify action succeeds and `AuditTrailEvent` records `override_acknowledged: true`.
- **Pass Threshold:** Unauthorized users cannot submit overrides; authorized overrides require explicit checkbox and reason $\ge 10$ chars.

---

## 4. Navigation & Queue Acceptance Criteria

### AC-08: Consolidated Invoices Workspace & Pagination (F-06)
- **Criterion:** The Invoices page must provide complete pagination across all records and allow filtering by all active database statuses without purple fallback badges.
- **Verification Steps:**
  1. Navigate to `/invoices`.
  2. Verify tabs render with live counts: *Needs attention*, *Ready to approve*, *Waiting*, *Approved*, *Received*, *Not invoices*, *All*.
  3. Verify pagination controls render: First, Prev, "Page 1 of $N$", Next, Last, and Page Size dropdown.
  4. Click "Next" $\rightarrow$ URL updates to `/invoices?page=2` $\rightarrow$ table displays records 26 to 50.
  5. Click "Ready to approve" tab $\rightarrow$ table displays only match candidates; zero purple badges rendered.
  6. Enter search term `"Asterion"` $\rightarrow$ table filters rows matching vendor name in real time.
- **Pass Threshold:** All pages reachable; URL query params reflect current view; zero unhandled status badges.

---

### AC-09: Dedicated Approvals Queue & Dual-Control Segregation (B-08, B-10)
- **Criterion:** Invoices exceeding ₹5,00,000 must require two approvals by distinct users, with the queue separating invoices waiting for the current user vs waiting for others.
- **Verification Steps:**
  1. As `sme_lead@company.internal`, open invoice `APTC-009` (Value: ₹7,84,000).
  2. Approve the invoice $\rightarrow$ status becomes `Waiting for second approval`.
  3. Navigate to `/approvals`.
  4. Under "Waiting for others" tab, verify `APTC-009` appears with label: *"First approved by SME AP Lead. Waiting for second approver."* Row action is disabled.
  5. Sign out $\rightarrow$ sign in as `sme_controller@company.internal`.
  6. Navigate to `/approvals` $\rightarrow$ under "Waiting for me" tab, verify `APTC-009` appears with active "Review & Approve" action.
  7. Complete second approval $\rightarrow$ invoice moves to "Approved".
- **Pass Threshold:** First approver cannot provide second approval; second approver successfully completes workflow; status transitions to `INTERNAL_APPROVAL_COMPLETE`.

---

## 5. Enterprise Craft, Accessibility & Ergonomics Acceptance Criteria

### AC-10: Keyboard Operability & Hotkey Workflow (F-13)
- **Criterion:** An AP clerk must be able to triage and approve an invoice entirely via keyboard shortcuts without touching a mouse.
- **Verification Steps:**
  1. On `/invoices` table, press `J` and `K` $\rightarrow$ verify row selection indicator moves down and up.
  2. Press `Enter` $\rightarrow$ opens selected invoice in Review Workspace.
  3. Press `1`, `2`, `3`, `4` $\rightarrow$ switches between Matching, Checks, Details, and History tabs.
  4. Press `D` $\rightarrow$ toggles Document panel collapse/expand.
  5. Press `A` $\rightarrow$ opens Approve confirmation modal with focus inside reason input.
  6. Press `Ctrl+Enter` (or `Cmd+Enter`) $\rightarrow$ submits approval.
  7. Verify focus returns to next invoice in queue.
  8. Press `?` $\rightarrow$ opens keyboard shortcuts cheat-sheet dialog; `Esc` dismisses it.
- **Pass Threshold:** 100% of core actions operable via keyboard; shortcuts disabled when typing inside text inputs.

---

### AC-11: Typography, Contrast & Anti-Slop Standards (`impeccable` / `taste-skill`)
- **Criterion:** The application must adhere to the 14px typography hierarchy, strict tabular number alignments, and zero decorative AI fluff.
- **Verification Steps:**
  1. Inspect CSS styling across all screens:
     - Body font size is $\ge 14\text{px}$ (`text-sm` with $20\text{px}$ line height); zero $10\text{px}$ or $11\text{px}$ micro-copy.
     - Currency and numeric amounts use tabular figures (`font-variant-numeric: tabular-nums;` or `font-mono`), right-aligned.
     - Text contrast against background achieves WCAG AA standard $\ge 4.5:1$.
  2. Codebase inspection:
     - 0 instances of browser `alert()` or `window.confirm()`.
     - 0 gratuitous gradient text, purple sparkle icons, or marketing jargon.
     - 0 unhandled `console.error` calls.
- **Pass Threshold:** Lighthouse Accessibility Score $\ge 95/100$; 0 automated axe-core violations.

---

### AC-12: Role-Based Access Control & Negative Security Boundaries
- **Criterion:** Forbidden actions must be hidden from unauthorized roles in the UI, and the backend must return HTTP 403 if called directly.
- **Verification Steps:**
  1. Sign in as `sme_auditor@company.internal` (Role: `AUDITOR`).
  2. Navigate to `/invoices/:id`.
  3. Verify Decision Bar displays read-only notice: *"You have read-only access to this workspace."* All action buttons are completely hidden.
  4. Execute direct API call `POST /api/v1/invoices/:id/actions` with `APPROVE_AP_REVIEW`.
  5. Verify backend returns HTTP 403 Forbidden.
  6. Verify Auditor cannot access `/settings/team` or initiate Gmail connections.
- **Pass Threshold:** Complete parity between UI affordances and server authorization rules; 0 false 403 errors shown to standard users.

---

## 6. Acceptance Verification Matrix

| AC ID | Target Area | Automation Method | Manual Browser Check | Priority |
|---|---|---|---|---|
| **AC-01** | Ingestion-to-Decision Pipeline | `test_e2e_pipeline.py` | Upload PDF $\rightarrow$ verify status | **P0** |
| **AC-02** | Exception Lifecycle Closure | `test_exception_closure.py` | Approve variance $\rightarrow$ check queue | **P0** |
| **AC-03** | Rejection Action Semantics | `test_rejection_action.py` | Reject invoice $\rightarrow$ verify audit | **P0** |
| **AC-04** | Embedded Document Viewer | Cypress / Playwright test | Inspect inline PDF iframe | **P0** |
| **AC-05** | Side-by-Side PO Comparison | `test_po_comparison_api.py` | View variance line in Pane 2 | **P0** |
| **AC-06** | Match Gates Evidence & Notes | Component unit test | Inspect Checks tab notes | **P0** |
| **AC-07** | Failed-Gate Override Guard | `test_override_guard.py` | Attempt override as Associate vs Lead | **P0** |
| **AC-08** | Invoices Workspace & Pagination | React Testing Library | Navigate pages 1 to 3 | **P0** |
| **AC-09** | Dual-Control Approvals Queue | `test_dual_control.py` | Test 2-user approval flow | **P1** |
| **AC-10** | Keyboard Navigation | Playwright keyboard events | Test `J`/`K`/`A`/`Enter` flow | **P1** |
| **AC-11** | Typography & Anti-Slop Audit | Axe-core / ESLint rule | Visual design inspection | **P2** |
| **AC-12** | RBAC Enforcement | `test_rbac_negative.py` | Inspect Auditor view | **P0** |
