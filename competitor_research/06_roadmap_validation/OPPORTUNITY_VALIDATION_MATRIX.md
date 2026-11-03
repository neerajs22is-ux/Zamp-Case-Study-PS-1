# Complete Opportunity Validation Matrix
## Rigorous Empirical Validation of 15 Consolidated Product Opportunities

**Artifact ID:** `OPPORTUNITY_VALIDATION_MATRIX.md`  
**Target Repository:** `C:\Zamp Casse Study`  
**Date of Validation:** November 03, 2026  
**Status:** Certified Validation Matrix  

---

## 1. Validation Classification Standard

Every opportunity from the [UNIFIED_UX_OPPORTUNITY_REGISTER.md](file:///c:/Zamp%20Casse%20Study/competitor_research/05_consolidated_strategy/UNIFIED_UX_OPPORTUNITY_REGISTER.md) has been audited against the actual source code and live runtime:

- **VALIDATED:** Supported by current source-code, database schema, and runtime evidence; ready for execution.
- **PARTIALLY VALIDATED:** Technically sound and desirable, but requires unblocking a missing prerequisite before implementation.
- **NOT VALIDATED:** Contradicted by actual application behavior or based on inaccurate competitor research assumptions.
- **BLOCKED:** Cannot safely proceed until a named architectural dependency is resolved.
- **DEFERRED:** Valid enterprise capability, but sequenced into a later roadmap phase due to dependencies or scope discipline.

---

## 2. Master Validation Summary Table

| Opp ID | Capability Name | Validation Status | Verified Target Phase | Implementation Readiness | Key Blocker or Prerequisite |
|:---:|:---|:---:|:---:|:---:|:---|
| **OPP-01** | **Audited In-Place Data Correction** | **VALIDATED** | **Phase A** | **Ready for Spec** | Requires `PATCH /invoices/:id/lines/:line_id` API route. |
| **OPP-10** | **Workspace Tab Consolidation** | **VALIDATED** | **Phase A** | **Ready for Spec** | Pure frontend refactoring in `InvoiceDetailPage.tsx`. |
| **OPP-04** | **Temporal Period (Year/Month) Filtering** | **VALIDATED** | **Phase A** | **Ready for Spec** | Requires adding B-tree index on `invoices.invoice_date`. |
| **OPP-12** | **Evaluation Mode Watermark & Reset** | **VALIDATED** | **Phase A** | **Ready for Spec** | Frontend header banner + database fixture reset endpoint. |
| **OPP-06** | **Executive AP Capital Exposure Scorecard** | **VALIDATED** | **Phase A** | **Ready for Spec** | Requires `GET /api/v1/dashboard/exposure` aggregation. |
| **OPP-03** | **Continuous Review Loop Navigation** | **VALIDATED** | **Phase B** | Ready for Sprint 3 | Needs cursor metadata in invoice detail response. |
| **OPP-02** | **PDF-to-Field Coordinate Highlighting** | **BLOCKED** | **Phase B** | Blocked | Blocked by iframe replacement with `pdfjs-dist` and OCR coordinates. |
| **OPP-09** | **Contextual PO Search & Line Linker** | **PARTIALLY VALIDATED**| **Phase B** | Ready for Sprint 3 | Needs `PATCH /invoices/:id/link-po` endpoint. |
| **OPP-05** | **Downloadable Batch Ingestion Templates** | **VALIDATED** | **Phase B** | Ready for Sprint 4 | Static asset placement in `/public/templates/`. |
| **OPP-07** | **Indian GST Interstate Auto-Split Preview** | **PARTIALLY VALIDATED**| **Phase B** | Ready for Sprint 4 | Requires Place of Supply (PoS) validation; cannot rely on GSTIN prefix alone. |
| **OPP-15** | **In-Viewer Full-Text Search ("Find")** | **BLOCKED** | **Phase B** | Blocked | Blocked by iframe replacement with `pdfjs-dist`. |
| **OPP-11** | **Ingestion Volume & License Quota Gauge** | **VALIDATED** | **Phase C** | Ready for Sprint 5 | Administrative indicator reading monthly row count. |
| **OPP-13** | **One-Click ERP Payload Preview Drawer** | **VALIDATED** | **Phase C** | Ready for Sprint 5 | Read-only slide-out drawer reading `/api/v1/invoices/:id/erp-payload`. |
| **OPP-08** | **Ambient "Ask Zamp" AP Copilot Drawer** | **DEFERRED** | **Phase D** | Deferred | Requires schema-grounded LLM inference pipeline. |
| **OPP-14** | **Pre-Payment Gateway Fee Reconciliation** | **DEFERRED** | **Phase D** | Deferred | Requires new table `settlement_reconciliations`. |

---

## 3. Granular Opportunity Validation Deep-Dives

---

### OPP-01: Audited In-Place Data Correction with Automatic Revalidation

1. **Validation Status:** **VALIDATED (Target: Phase A)**
2. **User Problem:** Reviewers cannot correct minor OCR misreads (e.g., rate read as ₹1,850 instead of ₹1,050) without full backend re-extraction.
3. **Current Application Behaviour:** `frontend/src/pages/InvoiceDetailPage.tsx` renders all lines as read-only text spans. Backend has zero `PATCH` or `PUT` endpoints for invoice lines.
4. **Exact Source Files Inspected:**
   - `backend/models/domain.py` lines 486–505 (`InvoiceLine` model).
   - `backend/api/v1/invoices.py` lines 1–544 (No correction route exists).
   - `frontend/src/pages/InvoiceDetailPage.tsx` lines 880–940 (Read-only rendering).
5. **Evidence & Verification Method:** Live AST scan of `backend/api/v1/` confirmed only one patch route exists (`/users/{id}/role`).
6. **Missing Prerequisites:** Need new endpoint `PATCH /api/v1/invoices/:id/lines/:line_id` and synchronous gate re-evaluation logic.
7. **Security & Governance Implications:** Must preserve original raw OCR in `extracted_fields`. Must log old value, new value, actor ID, and justification to `audit_events`. Must invalidate existing approval if in progress.
8. **Dependencies:** `MatchRun` re-evaluation function.
9. **Recommended Priority:** **P0 (Immediate Blocker)**.
10. **Belongs in Phase A:** **YES**.

---

### OPP-02: Bidirectional PDF-to-Field Source Linking & Coordinate Highlighting

1. **Validation Status:** **BLOCKED (Target: Phase B)**
2. **User Problem:** Reviewers must manually hunt between table numbers and the PDF.
3. **Current Application Behaviour:** PDF viewer is an HTML `<iframe src={previewUrl} />` (`InvoiceDetailPage.tsx` line 786). `ExtractedField.bounding_box` is `null` in the database because `backend/core/pipeline.py` (lines 285–296) never populates coordinates.
4. **Exact Source Files Inspected:**
   - `backend/core/pipeline.py` lines 285–296 (Bounding box ignored).
   - `frontend/src/pages/InvoiceDetailPage.tsx` lines 780–791 (Iframe viewer).
5. **Evidence & Verification Method:** Inspecting DOM in browser and reviewing `pipeline.py` proves coordinates are absent and iframe bars overlays.
6. **Missing Prerequisites:**
   - Must update OCR pipeline to emit normalized percentage bounding boxes.
   - Must replace `<iframe />` with `pdfjs-dist` HTML5 canvas renderer.
7. **Security & Governance Implications:** Read-only visual utility. Low security risk.
8. **Dependencies:** `pdfjs-dist` integration.
9. **Recommended Priority:** **P1 (Deferred to Phase B)**.
10. **Belongs in Phase A:** **NO**.

---

### OPP-03: Continuous Review Loop Navigation & Keyboard Shortcuts

1. **Validation Status:** **VALIDATED (Target: Phase B)**
2. **User Problem:** Confirming an invoice leaves the user on the detail page, requiring 3–4 clicks to return to the inbox and select the next item.
3. **Current Application Behaviour:** Detail page has no awareness of queue position or next invoice ID.
4. **Exact Source Files Inspected:**
   - `backend/api/v1/invoices.py` lines 50–270 (`get_invoice_detail` lacks cursor).
   - `frontend/src/pages/InvoiceDetailPage.tsx` lines 120–200.
5. **Evidence & Verification Method:** Code inspection confirms invoice detail response returns no queue metadata.
6. **Missing Prerequisites:** Add `next_invoice_id` and `remaining_in_queue` to invoice detail endpoint.
7. **Security & Governance Implications:** `Ctrl+Enter` must be strictly barred if any policy gate fails or if invoice requires dual approval.
8. **Dependencies:** Queue cursor in API.
9. **Recommended Priority:** **P1**.
10. **Belongs in Phase A:** **NO (Sequenced to Phase B to ensure Phase A in-place editing is solid first)**.

---

### OPP-04: Temporal Accounting Period (Year/Month) Filtering in Inbox

1. **Validation Status:** **VALIDATED (Target: Phase A)**
2. **User Problem:** Inbox is an unsegmented flat list mixing current closing bills with multi-year archives.
3. **Current Application Behaviour:** `backend/api/v1/inbox.py` supports `stage`, `decision`, `vendor`, but no year or month filter.
4. **Exact Source Files Inspected:**
   - `backend/api/v1/inbox.py` lines 24–65.
   - `frontend/src/pages/InboxPage.tsx` lines 40–120.
5. **Evidence & Verification Method:** Live REST test against `/api/v1/inbox` confirmed only standard query params are accepted.
6. **Missing Prerequisites:** Add B-tree index on `invoices.invoice_date` and add `fy` and `month` query parameters.
7. **Security & Governance Implications:** Purely view-layer filtering. All records remain intact.
8. **Dependencies:** Database index.
9. **Recommended Priority:** **P1**.
10. **Belongs in Phase A:** **YES**.

---

### OPP-05: Downloadable Vendor Batch Ingestion Templates

1. **Validation Status:** **VALIDATED (Target: Phase B)**
2. **User Problem:** Suppliers upload spreadsheets with arbitrary headers, triggering format errors.
3. **Current Application Behaviour:** Upload modal accepts single PDF drag-and-drop; no batch spreadsheet templates.
4. **Exact Source Files Inspected:**
   - `frontend/src/components/UploadModal.tsx` (or `InboxPage.tsx` upload dropzone).
5. **Evidence & Verification Method:** Inspected upload dialog in live UI.
6. **Missing Prerequisites:** Host CSV template file in `/public/templates/`.
7. **Security & Governance Implications:** None.
8. **Dependencies:** Static file asset.
9. **Recommended Priority:** **P1**.
10. **Belongs in Phase A:** **NO (Phase B)**.

---

### OPP-06: Executive AP Capital Exposure & Aging Scorecard

1. **Validation Status:** **VALIDATED (Target: Phase A)**
2. **User Problem:** Dashboard shows volume counts (`Total Invoices: 7`) but conceals financial capital risk.
3. **Current Application Behaviour:** `backend/api/v1/dashboard.py` computes count aggregates (`pending_review_count`, `msme_exposure_count`), but lacks aggregated INR capital sums for blocked vs cleared payables.
4. **Exact Source Files Inspected:**
   - `backend/api/v1/dashboard.py` lines 40–110.
   - `frontend/src/pages/DashboardPage.tsx` lines 400–460.
5. **Evidence & Verification Method:** Live REST call to `/api/v1/dashboard/metrics` confirmed missing INR capital sums.
6. **Missing Prerequisites:** Add `GET /api/v1/dashboard/exposure` endpoint.
7. **Security & Governance Implications:** Read-only aggregation. Crucial constraint: MSMED deadlines must only be displayed as statutory when supplier Udyam registration is verified; otherwise, label as operational aging!
8. **Dependencies:** Aggregation queries on `invoices`.
9. **Recommended Priority:** **P1**.
10. **Belongs in Phase A:** **YES**.

---

### OPP-07: Dynamic Indian GST Interstate/Intrastate Auto-Split Preview

1. **Validation Status:** **PARTIALLY VALIDATED (Target: Phase B)**
2. **User Problem:** Tax is displayed as a single lumped figure without statutory PoS split verification.
3. **Current Application Behaviour:** Validates total tax arithmetic via Gate 5, but displays tax as a single number.
4. **Mandatory Constraint:** GST treatment must NOT be inferred from GSTIN prefix alone. Any interstate/intrastate calculation requires relevant Place of Supply (PoS) and transaction context.
5. **Missing Prerequisites:** Add Place of Supply (PoS) extraction field to pipeline before implementing auto-split preview.
6. **Recommended Priority:** **P2**.
7. **Belongs in Phase A:** **NO (Phase B)**.

---

### OPP-10: Redundant Tab Consolidation & Workspace Polish

1. **Validation Status:** **VALIDATED (Target: Phase A)**
2. **User Problem:** Reviewers must click across 4 tabs (`Matching & Lines`, `Policy Checks`, `Extracted Info`, `Audit Trail`) to evaluate an invoice.
3. **Current Application Behaviour:** `InvoiceDetailPage.tsx` detaches policy checks from matching lines into separate tabs.
4. **Exact Source Files Inspected:**
   - `frontend/src/pages/InvoiceDetailPage.tsx` lines 820–1209.
5. **Evidence & Verification Method:** Verified live UI layout in browser; tab switching creates unnecessary context loss.
6. **Missing Prerequisites:** Refactor tab layout to merge lines and policy checks into unified primary view.
7. **Security & Governance Implications:** Pure frontend layout enhancement.
8. **Dependencies:** None.
9. **Recommended Priority:** **P0 (Immediate Blocker)**.
10. **Belongs in Phase A:** **YES**.

---

### OPP-12: Explicit Sample Data Watermark & Evaluation Reset Control

1. **Validation Status:** **VALIDATED (Target: Phase A)**
2. **User Problem:** Prospective enterprise buyers confuse mock test fixtures with live SAP connections.
3. **Current Application Behaviour:** In evaluation mode (`org_sme_eval`), mock fixtures load without a permanent watermark.
4. **Exact Source Files Inspected:**
   - `frontend/src/components/AppShell.tsx` lines 20–80.
   - `frontend/src/components/AuthScreen.tsx` lines 208–260.
5. **Evidence & Verification Method:** Verified live session header lacks evaluation mode banner.
6. **Missing Prerequisites:** Add top header pill in `AppShell.tsx` and reset trigger.
7. **Security & Governance Implications:** Strengthens trust and buyer confidence.
8. **Dependencies:** None.
9. **Recommended Priority:** **P1**.
10. **Belongs in Phase A:** **YES**.
