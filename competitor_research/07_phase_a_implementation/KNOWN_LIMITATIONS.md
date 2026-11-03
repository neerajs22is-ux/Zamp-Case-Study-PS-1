# Phase A Known Limitations & Phase B Roadmap
## AP Command Center — Architecture Boundaries & Operational Constraints

**Date:** November 03, 2026  
**Status:** Authoritative Implementation Reference  

---

## 1. Intentional Scope Boundaries (Deferred to Phase B)

Phase A was strictly scoped to address high-friction reviewer ergonomics, trust transparency, and operational clarity without altering the underlying microservice architecture or introducing risky frontend dependencies. 

The following capabilities were analyzed during the competitor investigations (FinBooks, Rossum, Flick AI) and were **deliberately deferred to Phase B** in accordance with the validated Phase A Engineering Specification:

### 1. Client-Side SVG OCR Bounding-Box Overlays (`pdfjs-dist`)
- **Reason for Deferral:** Integrating `pdfjs-dist` to render OCR bounding boxes directly over PDF pages introduces significant bundle bloat (~4.5 MB uncompressed), complex canvas coordinate transformations across diverse client screen DPIs, and browser memory overhead when viewing multi-page invoices.
- **Phase A Implementation:** Retained the zero-trust native browser PDF iframe viewer with secure, on-demand 300-second pre-signed URLs (`GET /api/v1/documents/:id/signed-url`).
- **Phase B Roadmap:** Evaluate a lightweight, server-rendered SVG coordinate overlay or web worker-isolated PDF viewer.

### 2. Floating Field-Level Correction Popovers (Rossum-style)
- **Reason for Deferral:** Floating field popovers positioned dynamically relative to PDF coordinates require complex pointer tracking and collision detection. Implementing this prematurely risks layout breakages on mobile and tablet screens.
- **Phase A Implementation:** Implemented a clean, modal-based audited line-item correction dialog triggered from the 3-Way Match grid. This ensures 100% responsive behavior across all desktop and laptop resolutions.
- **Phase B Roadmap:** Introduce keyboard-driven floating inline inputs for high-velocity AP operators.

### 3. Continuous Processing Keyboard Queue Navigation (`Ctrl+Enter` Auto-Advance)
- **Reason for Deferral:** Continuous queue navigation requires background queue pre-fetching, optimistic cache management, and complex state synchronization across consecutive invoice approvals.
- **Phase A Implementation:** Reviewers approve or triage individual invoices with single-key shortcuts (`A` for Approve, `H` for Hold, `C` for Supplier Correction, `R` for Reject), returning cleanly to the inbox.
- **Phase B Roadmap:** Implement batch approval queues and instant next-document auto-advancement for Tier-1 AP processors.

### 4. Automated Supplier Correction Email Dispatch
- **Reason for Deferral:** Automatically emailing external suppliers upon invoice rejection requires customer-specific SMTP credentials, email template builders, deliverability monitoring, and vendor contact management.
- **Phase A Implementation:** The system generates structured, consequence-aware correction instructions that AP associates can copy into their existing corporate email or vendor portals.
- **Phase B Roadmap:** Add native transactional email routing and a self-service vendor dispute portal.

### 5. Live Two-Way ERP Write-Back (SAP S/4HANA / Oracle / Tally / Zoho)
- **Reason for Deferral:** Real-time bi-directional ERP ledger synchronization requires enterprise middleware (SAP RFC/BAPI connectors, Tally XML bridges), custom transaction rollback logic, and extensive ERP admin credentials.
- **Phase A Implementation:** Invoices marked `MANUALLY_APPROVED` or `AUTO_APPROVED` are stamped with `is_cleared_for_erp = True` and exportable via standard API endpoints and CSV manifests.
- **Phase B Roadmap:** Develop certified connectors for SAP S/4HANA and Zoho Books.

---

## 2. Runtime Constraints & Operational Assumptions

1. **Document Viewing Security Constraints:**
   - PDF viewing is executed via the browser's native PDF plugin inside an `<iframe>` sandbox.
   - Pre-signed document download URLs have a strict maximum Time-To-Live (TTL) of 300 seconds. If an operator leaves an invoice open for more than 5 minutes, clicking the `Refresh URL` button is required to generate a fresh cryptographic access token.
2. **Demo State Reset Safeguards:**
   - The reset endpoint (`POST /api/v1/system/reset-demo`) is strictly hardcoded to allow resets **only** for the designated evaluation organization (`org_id == "org_sme_eval"`).
   - Calling the reset endpoint in production or security audit organizations (`org_default`, `org_sec_audit`, `org_p1_test`) is strictly blocked with `HTTP 403 Forbidden`.
   - The reset endpoint is strictly forbidden for users with the `AUDITOR` role.
   - The reset endpoint resets mutable invoice lines and gate evaluations to baseline, but **never deletes** records from `audit_events`.
3. **Temporal Filtering Semantics:**
   - The Financial Year and Month dropdowns filter strictly by the invoice's stated issue date (`invoices.invoice_date`).
   - Invoices with missing or unreadable invoice dates default to their ingestion date (`invoices.created_at`).
   - The Indian Financial Year convention is observed: FY 2026-27 covers `2026-04-01` to `2027-03-31`.
4. **Statutory MSME Exposure Constraints:**
   - Under Section 15 of the Indian MSMED Act, buyers must settle payments within 45 days of physical acceptance of goods/services.
   - The AP Command Center strictly reports `statutory_msme_verified_due_inr` as `0.00` until a supplier's formal Udyam Registration Certificate is uploaded and verified by AP management. Operational aging (> 30 days) is reported separately to prevent false regulatory compliance certifications.

---

## 3. Operational Guidance for AP Reviewers

- **When to Use Line Item Correction:**
  - Use audited in-place line correction exclusively for obvious optical character recognition (OCR) transcription errors (e.g., decimal misplaced, quantity misread, or character misinterpretation where the underlying physical invoice document clearly shows the contracted figure).
  - Do NOT use line correction to negotiate unauthorized discounts or alter genuine commercial disputes. If the supplier intentionally billed a higher rate than authorized on the PO, place the invoice on Hold (`HOLD_PENDING_EVIDENCE`) or request supplier credit note (`REQUEST_SUPPLIER_CORRECTION`).
- **Mandatory Audit Justification:**
  - Every line item correction requires a substantive written justification (minimum 3 characters, recommended 15+ characters).
  - All corrections are permanently attributed to the logged-in user in the immutable audit trail and will be scrutinized during statutory financial audits.
- **Resolving Concurrency Conflicts (HTTP 412):**
  - If another reviewer updates an invoice line while you are inspecting it, saving will display: `"Document has been modified by another reviewer. Please refresh."`
  - Simply reload the invoice to view the latest modifications before submitting your changes.
