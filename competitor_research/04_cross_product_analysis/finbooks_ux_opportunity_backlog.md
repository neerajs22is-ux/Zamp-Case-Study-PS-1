# FinBooks vs Zamp AP Command Center — Prioritized UX & Workflow Opportunity Backlog

**Target Competitor:** FinBooks (`https://app.finbooks.ai/`)  
**Our Product:** Zamp AP Command Center  
**Methodology:** Evidence-Based Product Optimization & Ergonomic Backlog Formulation  
**Date:** November 03, 2026  

---

## 1. Classification Framework

Every opportunity is categorized under one of six strict analytical decisions:
- **IMPLEMENT:** A clear improvement directly supported by competitor evidence that fills an acute operational gap.
- **ADAPT:** A valuable competitor pattern that must be re-engineered to fit our deterministic AP compliance architecture.
- **SIMPLIFY:** An existing screen or interaction in our application that causes cognitive friction and should be streamlined.
- **REMOVE:** An unnecessary panel, redundant step, or clutter that adds friction without operational value.
- **KEEP:** An area where our application already outperforms the competitor and should be firmly preserved.
- **DO NOT IMPLEMENT:** Competitor features that are irrelevant, unsafe, violate compliance gates, or fall outside our AP product scope.

---

## 2. Master Prioritized Opportunity Backlog

---

### Item 1: In-Place Field & Line-Item Correction with Audit Trail
- **Classification:** **IMPLEMENT**
- **Priority:** **P0 (Critical)**
- **Complexity:** Medium
- **Current AP Command Center Behavior:** Extracted fields and line items in `InvoiceDetailPage.tsx` and `ProcurementVerificationFlow.tsx` are 100% read-only in the UI. If the OCR engine makes a trivial transcription error (e.g., misreading invoice date `2026-10-01` as `2026-10-10`, or reading `INV-001` as `INV-0O1`), the user has no way to fix the field. The invoice fails policy gates and must be rejected or put on hold.
- **FinBooks Observed Behavior:** Inside `editForm`, FinBooks exposes input fields for invoice date, amount, taxes, and totals (`screenshots/review_and_validation/01_invoice_review_workspace.png`). Users can fix typos and click "Save Changes". (However, FinBooks discards line-item editing).
- **Evidence Reference:** `evidence_log.md` EV-006, `ui_ux_analysis.md` §5.2, `InvoiceDetailPage.tsx` L973-1006.
- **User Problem:** Finance clerks are forced into dead-end exception triage for trivial 1-character OCR mistakes. They cannot approve legitimate invoices because of an uncorrectable transcription error.
- **Specific Proposed Change:**
  1. Add an "Edit Fields" toggle on the Extracted Information and Matching tabs.
  2. Allow editing invoice number, invoice date, supplier GSTIN, and line-item unit rate/quantity.
  3. When an edit is saved, re-trigger the 7 deterministic policy gates automatically.
  4. Record an append-only `FIELD_CORRECTED` audit event in the timeline capturing the previous value, new value, actor ID, and timestamp.
- **Expected User Benefit:** Eliminates 80% of unnecessary "Hold for Evidence" or "Ask Supplier to Correct" loops caused purely by minor OCR misreads.
- **Dependencies & Risks:** Backend endpoint `PUT /api/v1/invoices/{id}/corrections` must be created. Risk: clerks might tamper with amounts; mitigated by append-only audit logging and re-evaluating policy gates.

---

### Item 2: Rich Duplicate Resolution Modal (`dupCard` Pattern)
- **Classification:** **ADAPT**
- **Priority:** **P0 (Critical)**
- **Complexity:** Low
- **Current AP Command Center Behavior:** When a user uploads a duplicate file or identical voucher, the backend returns HTTP 409 and the UI displays a plain text banner: `Duplicate detected: file.name has already been registered in the system.` It does not tell the user *which* invoice is conflicting, when it was uploaded, or who approved it.
- **FinBooks Observed Behavior:** When duplicate hashes match, FinBooks renders a dedicated `dupCard` component (`screenshots/exceptions/01_exception_handling.png`). It displays a definition list with Conflicting Vendor, Invoice Date, Total Amount, and Upload Date, plus a primary action button: `<a class="btn-primary-g">View Invoice</a>` that immediately opens the existing bill.
- **Evidence Reference:** `evidence_log.md` EV-009, `screenshots/exceptions/01_exception_handling.png`, `InboxPage.tsx` L95-98.
- **User Problem:** The clerk knows an upload failed, but cannot find the conflicting invoice without manually searching the entire database by filename or voucher number.
- **Specific Proposed Change:**
  1. Update `backend/api/v1/documents.py` to return the conflicting `existing_invoice_id`, `invoice_number`, `vendor_name`, `total_amount`, and `created_at` in the 409 JSON body.
  2. In `InboxPage.tsx`, replace the text error with a structured modal alert displaying the conflicting metadata and a direct button: `View Existing Invoice (#INV-XXX)`.
  3. Clicking the button opens the existing invoice workspace directly.
- **Expected User Benefit:** Saves 3–5 minutes of searching per duplicate event. Allows instant verification of whether the duplicate is fraud or an accidental re-scan.
- **Dependencies & Risks:** Minor backend payload enhancement; zero risk to business rules.

---

### Item 3: Bulk Clean-Match Sign-Off for 100% Verified Invoices
- **Classification:** **ADAPT**
- **Priority:** **P0 (Critical)**
- **Complexity:** Medium
- **Current AP Command Center Behavior:** Invoices can only be reviewed and approved one by one. Approving 50 clean-match invoices (`MATCH_CANDIDATE` where all 7 checks passed cleanly) requires opening 50 detail pages, scrolling, clicking Approve, picking a reason, and returning to the queue (200 clicks total).
- **FinBooks Observed Behavior:** FinBooks provides row checkboxes, a "Select All" header checkbox, and a floating bottom action bar displaying "X bills selected" with a 1-click "Approve Selected" action (`screenshots/invoice_workflow/07_bills_list_after_upload.png`, `workflow_analysis.md` §2 Journey 5).
- **Evidence Reference:** `workflow_analysis.md` Journey 5 & Journey 10, `evidence_log.md` Section 4 (v2.10 release), `InboxPage.tsx`.
- **User Problem:** High-volume AP teams processing hundreds of clean, verified invoices suffer severe ergonomic fatigue from repetitive manual clicks.
- **Specific Proposed Change:**
  1. On `/invoices?decision=MATCH_CANDIDATE` (and only on clean matches where all 7 policy checks passed), introduce row checkboxes and a "Select All Clean Matches" header checkbox.
  2. Selecting rows surfaces a floating bottom bar: `X clean invoices selected (All 7 checks verified)`.
  3. Provide a single primary CTA: `Bulk Approve Selected`.
  4. For invoices < ₹5,00,000: records internal AP approval in batch. For invoices ≥ ₹5,00,000: moves them to `PENDING_SECOND_APPROVAL` in batch.
  5. Prompt for a single operational justification applied across the batch (e.g. `Batch verification: All 7 automated policy gates confirmed`).
- **Expected User Benefit:** Reduces interaction cost from 200 clicks to 3 clicks for 50 clean invoices (98.5% click reduction).
- **Dependencies & Risks:** Backend endpoint `POST /api/v1/invoices/bulk-actions`. Must strictly enforce that NO invoice with failing policy gates can be bulk-approved. Dual-approval thresholds must remain intact.

---

### Item 4: Contextual PO Search & Relinking Drawer
- **Classification:** **IMPLEMENT**
- **Priority:** **P1 (High)**
- **Complexity:** Medium
- **Current AP Command Center Behavior:** If an invoice arrives without a PO reference or with an OCR typo in the PO number, Gate 2 (`PO Authorization Valid`) fails immediately. The user has no way in the UI to search open POs for that supplier or link the invoice to the correct purchase order.
- **FinBooks Observed Behavior:** When unmatched, FinBooks displays a `No matching order` badge. Clicking the badge opens `prompt('Sales order number...')`, allowing the user to type in `SO-00003` to link the order (`evidence_log.md` EV-010).
- **Evidence Reference:** `evidence_log.md` EV-010, `workflow_analysis.md` Journey 4, `InvoiceDetailPage.tsx` L298-316.
- **User Problem:** Invoices with minor PO citation errors or missing PO numbers get permanently stuck in exception status.
- **Specific Proposed Change:**
  1. On Gate 2 (`PO Authorization Valid`) and on Node 2 of the Procurement Verification Flow, when status is FAIL or MISSING, display an action button: `Link Purchase Order`.
  2. Clicking opens a slide-over drawer displaying all active open POs for that vendor with PO number, authorized amount, remaining balance, and date.
  3. Include a search input to look up POs by number or item description.
  4. Clicking `Select & Link` attaches the PO snapshot, re-runs 3-way matching and 7 policy gates, and logs an audit event: `PO_RELINKED`.
- **Expected User Benefit:** Replaces FinBooks' clunky browser prompt with a smooth, contextual matching drawer that resolves unlinked PO exceptions in under 15 seconds.
- **Dependencies & Risks:** Backend endpoint `POST /api/v1/invoices/{id}/link-po`.

---

### Item 5: Multi-Vendor Batch Scanning & PDF Page Splitting
- **Classification:** **ADAPT**
- **Priority:** **P1 (High)**
- **Complexity:** Medium
- **Current AP Command Center Behavior:** Users upload files one by one. If a user uploads a 20-page PDF containing 5 different vendor invoices scanned together by the mailroom, Zamp treats the entire PDF as one single corrupt invoice.
- **FinBooks Observed Behavior:** In the upload modal, FinBooks includes a prominent checkbox: `Split merged PDF into separate bills per vendor` (`screenshots/invoice_workflow/02_upload_modal.png`, `workflow_maps/invoice_lifecycle.mermaid`).
- **Evidence Reference:** `screenshots/invoice_workflow/02_upload_modal.png`, `feature_inventory.md` §2.1.
- **User Problem:** Corporate accounting departments receive mailroom scanner batches where multiple supplier invoices are bundled into a single PDF. Manually splitting PDFs before uploading is a massive chore.
- **Specific Proposed Change:**
  1. Add a checkbox in the upload modal: `Split multi-invoice batch (1 bill per vendor)`.
  2. When checked, the ingestion pipeline splits the PDF on detected invoice header boundaries or vendor GSTIN shifts and spawns discrete ingestion jobs.
- **Expected User Benefit:** Eliminates external PDF splitting tools; aligns Zamp with corporate mailroom scanning operations.
- **Dependencies & Risks:** Ingestion pipeline splitting logic in `engine/pipeline.py`.

---

### Item 6: Click-to-Coordinate OCR Bounding Box Cross-Highlighting
- **Classification:** **IMPLEMENT**
- **Priority:** **P2 (Medium)**
- **Complexity:** High
- **Current AP Command Center Behavior:** `InvoiceDetailPage.tsx` displays the PDF iframe on the left and extracted fields on the right. However, clicking a field (e.g. `taxable_value: 22000.0`) does nothing to the PDF viewer. The schema holds `bounding_box: null`.
- **FinBooks Observed Behavior:** Completely absent in FinBooks.
- **Evidence Reference:** `InvoiceDetailPage.tsx` L780-816, `backend/models/domain.py`.
- **User Problem:** When checking a high-value amount or line item, the reviewer must manually scroll and hunt through the PDF to find where that number came from.
- **Specific Proposed Change:**
  1. Update hybrid extractor / OCR pipeline to return normalized bounding box coordinates `[ymin, xmin, ymax, xmax]` for header fields and line items.
  2. Replace raw `<iframe>` PDF preview with an interactive PDF viewer (e.g. PDF.js or SVG overlay).
  3. Clicking any extracted field or table row highlights the corresponding bounding box on the PDF canvas and smoothly scrolls it into view.
- **Expected User Benefit:** Reduces document verification dwell time by 50%; eliminates eye strain.
- **Dependencies & Risks:** Requires OCR bounding box extraction in `engine/ocr_engine.py` and client-side PDF canvas renderer.

---

### Item 7: Streamline Setup Checklist Dismissal & Dashboard Density
- **Classification:** **SIMPLIFY**
- **Priority:** **P2 (Medium)**
- **Complexity:** Low
- **Current AP Command Center Behavior:** `DashboardPage.tsx` displays an Operational Readiness Checklist card and an Executive Overview card that occupy nearly 350px of vertical height before the user reaches the actionable Next-Up Queue.
- **FinBooks Observed Behavior:** FinBooks places its onboarding guides in an unobtrusive sliding drawer on the right rail (`ui_ux_analysis.md` §2.1), leaving the primary page canvas clean.
- **Evidence Reference:** `DashboardPage.tsx` L160-380, `screenshots/02_dashboard_today.png`.
- **User Problem:** Experienced finance managers who use the dashboard daily do not need to see the 4-step linear explanation or subsystem checklist every time they log in.
- **Specific Proposed Change:**
  1. Collapse the Setup Checklist and Executive AP Paradigm into a compact 1-line dismissible banner or move it into a slide-over "Operational Health" drawer.
  2. Elevate the Prioritized Next-Up Queue higher on the page so clerks see actionable work without scrolling.
- **Expected User Benefit:** Immediate focus on exception triage; reduced vertical scrolling.
- **Dependencies & Risks:** Purely frontend layout simplification.

---

### Item 8: Remove Redundant Information Tabs in Analysis Pane
- **Classification:** **REMOVE**
- **Priority:** **P2 (Medium)**
- **Complexity:** Low
- **Current AP Command Center Behavior:** In `InvoiceDetailPage.tsx`, Tab 1 is `Matching & Lines` and Tab 3 is `Extracted Information`. The header subtotal, tax amount, and total are displayed in the header, again in the Net Payable Waterfall on Tab 1, and again in the table on Tab 3.
- **FinBooks Observed Behavior:** Consolidates header fields into a single view.
- **Evidence Reference:** `InvoiceDetailPage.tsx` L830-875, `screenshots/04_invoice_detail_matching.png` and `06_invoice_detail_extracted.png`.
- **User Problem:** Redundant tabs create unnecessary navigation clicks. Users flip between Tab 1 and Tab 3 to see the same data.
- **Specific Proposed Change:**
  1. Merge Tab 3 (`Extracted Information`) into a compact header sidebar card or fold it directly into the top of Tab 1.
  2. Reduce tabs from 4 to 3: `1. Matching & Verification`, `2. Policy Gates`, `3. Audit Trail`.
- **Expected User Benefit:** Reduces tab flipping by 33%; keeps all relevant invoice figures on a single screen.
- **Dependencies & Risks:** Frontend tab consolidation.

---

### Item 9: Preserve 50/50 Synchronized Split Screen & Authoritative 3-Way Match
- **Classification:** **KEEP**
- **Priority:** **P0 (Foundational Standard)**
- **Complexity:** N/A (Existing Strength)
- **Current AP Command Center Behavior:** Zamp's 50/50 Synchronized Split Screen with PDF zoom/pan on the left and 3-way matching on the right, coupled with 7 deterministic policy gates, dual-approval controls (≥ ₹5,00,000), and append-only audit trail.
- **FinBooks Observed Behavior:** Decoupled PDF drawer and edit modal; complete omission of line-item editing; coarse status flags; absence of dual control; no per-invoice audit timeline.
- **Evidence Reference:** `finbooks_vs_ap_command_center.md` §5, `ui_ux_analysis.md` §5.1, `workflow_analysis.md`.
- **Rationale for Keeping:** This is Zamp's core competitive moat. Under no circumstances should Zamp adopt FinBooks' fragmented modal-over-drawer pattern or drop line-item inspection.

---

### Item 10: Do NOT Implement Full General Ledger, Payroll, or Sales Invoicing
- **Classification:** **DO NOT IMPLEMENT**
- **Priority:** **Boundary Rule**
- **Complexity:** N/A (Out of Scope)
- **FinBooks Observed Behavior:** FinBooks incorporates CRM sales invoices, quotations, payroll processing, fixed asset depreciation, and double-entry general ledger posting (`screenshots/other_features/04_payroll.png`, `07_accounting_ledger.png`, `08_assets.png`).
- **Rationale:** Zamp is an Autonomous AP Operations and Pre-Payment Verification Command Center. Expanding into sales CRM, payroll, and general ledger accounting would dilute engineering focus, compromise audit specialization, and violate the non-negotiable business boundary: *"This is an AP review and validation product, not a complete accounting suite."*

---

### Item 11: Do NOT Implement Native Browser `window.prompt()`
- **Classification:** **DO NOT IMPLEMENT**
- **Priority:** **Anti-Pattern Rejection**
- **Complexity:** N/A
- **FinBooks Observed Behavior:** FinBooks uses `window.prompt()` to link purchase orders (`evidence_log.md` EV-010).
- **Rationale:** Native browser prompts block JavaScript execution, cannot be styled, cannot provide autocomplete or search, provide zero validation before server submission, and create severe cognitive friction.

---

## 3. Summary Backlog Matrix

| ID | Title | Category | Priority | Complexity | Expected ROI / Impact |
|:---:|:---|:---:|:---:|:---:|:---|
| **REC-01** | In-Place Field & Line-Item Correction with Audit Trail | **IMPLEMENT** | **P0** | Medium | Eliminates 80% of unnecessary rejection loops due to OCR typos |
| **REC-02** | Rich Duplicate Resolution Modal (`dupCard` Deep Link) | **ADAPT** | **P0** | Low | Saves 3–5 min per duplicate; enables instant conflict inspection |
| **REC-03** | Bulk Clean-Match Sign-Off for 100% Verified Invoices | **ADAPT** | **P0** | Medium | Reduces click cost by 98.5% (200 clicks → 3 clicks for 50 bills) |
| **REC-04** | Contextual PO Search & Relinking Drawer | **IMPLEMENT** | **P1** | Medium | Resolves missing/typo PO exceptions in < 15 seconds |
| **REC-05** | Multi-Vendor Batch Scanning & PDF Page Splitting | **ADAPT** | **P1** | Medium | Accommodates corporate mailroom batch scanning operations |
| **REC-06** | Click-to-Coordinate OCR Bounding Box Highlighting | **IMPLEMENT** | **P2** | High | Halves document verification dwell time |
| **REC-07** | Streamline Setup Checklist Dismissal & Dashboard Density | **SIMPLIFY** | **P2** | Low | Places actionable exception work immediately above the fold |
| **REC-08** | Merge Redundant Information Tabs in Analysis Pane | **REMOVE** | **P2** | Low | Reduces tab switching by 33% |
| **REC-09** | Preserve 50/50 Split Screen & 3-Way Match Rigor | **KEEP** | **P0** | N/A | Preserves Zamp's primary architectural and competitive moat |
| **REC-10** | Do NOT Build General Ledger, Payroll, or Sales Modules | **DO NOT IMPLEMENT** | **Boundary** | N/A | Prevents scope creep; maintains enterprise AP focus |
| **REC-11** | Do NOT Use Native `window.prompt()` Dialogs | **DO NOT IMPLEMENT** | **Anti-Pattern** | N/A | Prevents severe UX regression |
