# Known Limitations & UI/UX Audit Baseline

This document catalogues known functional constraints, system boundaries, and current user interface (UI/UX) usability bottlenecks in the Autonomous Accounts Payable (AP) Command Center.

> [!IMPORTANT]
> **Context for Reviewing AI Model:** This document provides baseline context for your independent UI/UX audit and redesign. The interface has been preserved exactly as tested so that you can evaluate real operator workflows objectively.

---

## 1. UI/UX & Operator Experience Bottlenecks

### A. 3-Pane Review Workspace Density & Responsive Scaling
- **Current Behavior:** The review workspace ([`frontend/src/pages/InvoiceDetailPage.tsx`](../frontend/src/pages/InvoiceDetailPage.tsx)) splits the screen into 3 simultaneous panes:
  - **Pane 1 (Left):** Document Evidence (PDF viewer with signed URL).
  - **Pane 2 (Center):** Line-item reconciliation, tax breakdown, and variance calculation.
  - **Pane 3 (Right):** Match decision gates, exception summaries, and human action form.
- **Identified Usability Friction:** On standard laptop displays ($\le 1440\text{px}$ width), the 3-pane split becomes crowded. Operators must horizontally scroll or zoom out their browser to read line-item descriptions and match gate notes simultaneously.
- **Target Improvement:** Adaptive or collapsible pane layout (e.g. toggleable document evidence drawer, floating action bar, or full-width tabbed view).

### B. Keyboard Navigation & AP Power-User Shortcuts (Resolved in Phase 5)
- **Status:** **Implemented & Verified in Phase 5.**
- **Resolved Functionality:** Operators can navigate tabs via number keys (`1` for Matching, `2` for Checks, `3` for Extracted Information, `4` for Audit Trail), trigger triage actions (`A` for Approve, `H` for Hold, `R` for Reject, `Esc` to dismiss confirmation drawer), and press `?` to open the Keyboard Shortcuts modal.

### C. Pre-Populated Justification Templates & Triage Macros (Resolved in Phase 5)
- **Status:** **Implemented & Verified in Phase 5.**
- **Resolved Functionality:** Context-sensitive, clickable reason template chips are provided for all triage actions (e.g., *"Unit price exceeds contracted PO rate by >1.5%"*, *"PO balance exhausted"*, *"QC inspection pending"*), allowing clerks to populate audit justifications with one click while retaining the mandatory 3-character minimum.

### D. Single-Invoice Triage Only (No Bulk Actions)
- **Current Behavior:** The main Inbox ([`frontend/src/pages/InboxPage.tsx`](../frontend/src/pages/InboxPage.tsx)) displays invoices in a tabular list, but each invoice must be clicked and opened individually to be reviewed or approved.
- **Identified Usability Friction:** Routine low-risk invoices with status `MATCH_CANDIDATE` (where all 7 gates passed and amount $< ₹50,000$) cannot be bulk-selected or batch-approved.

### E. Table Line-Item Truncation & Detail Expansion
- **Current Behavior:** Line items with lengthy commercial descriptions are truncated with CSS ellipses (`truncate`).
- **Identified Usability Friction:** Operators cannot inspect full item descriptions without opening browser developer tools or zooming in on the original PDF in Pane 1. There is no inline row expander or hover tooltip.

### F. Inbox Search Scope
- **Current Behavior:** The search bar in the Inbox table filters across `invoice_number` and `vendor_name`.
- **Identified Usability Friction:** Operators cannot search by PO number, line item description, HSN/SAC code, or amount range directly from the main filter bar.

---

## 2. Functional & Architectural Boundaries

### A. Strict Decoupling from Banking & ERP Mutations
- **Design Decision:** The AP Command Center is an operational decision and review platform. It intentionally contains zero direct integration with banking payment rails (NEFT, RTGS, IMPS, ACH) and does not automatically write debit/credit journal entries to SAP S/4HANA ledgers.
- **Operational Reality:** Approved invoices (`INTERNAL_APPROVAL_COMPLETE`) must be exported via batch voucher API for ERP posting and payment scheduling by the treasury team.

### B. Degraded Raster Scan Limitations & Palmyra Vision
- **Current Behavior:** Highly degraded scans ($\sigma < 10.0$ contrast, distorted fax receipts) fail closed to `FLAGGED_HITL_REVIEW`.
- **Palmyra Vision Assessment:** The multimodal Palmyra Vision 7B adapter exhibited OCR substitution errors on alphanumeric tax strings and conflated line totals with grand totals. It is intentionally feature-flagged `OFF` (`ENABLE_PALMYRA_VISION=false`).

### C. Currency Scope: Indian Rupee (INR) Optimization
- **Current Scope:** The deterministic math engine is tailored for Indian GST statutory rules (18% / 12% / 5% / 28% CGST, SGST, IGST) and INR currency.
- **Foreign Currency Handling:** Foreign currency invoices (USD, EUR, GBP) involving customs duty or import IGST are routed to manual HITL review rather than auto-matched.


---

## 3. Explicitly Deferred Operational & Security Risks

The following four items represent deliberate deferred architectural and security risk items formally tracked across development phases:

### R-01: MSMED Statutory Deadline Edge-Case Verification
- **Risk Scope:** Verification of statutory interest calculations and 45-day payment deadlines under Section 15 & 16 of the Micro, Small and Medium Enterprises Development (MSMED) Act, 2006.
- **Current Behavior:** Invoices calculate statutory payment due dates based on vendor MSME classification (`msme_statutory_deadline`), surfacing countdowns and warning badges on the dashboard and detail workspace.
- **Deferred Complexity:** Edge-case statutory scenarios including leap years, fiscal year transitions, compounding monthly interest calculations at 3x bank rate for disputed invoices, and retroactive credit adjustments under Section 16 remain deferred for specialized legal/treasury verification.
- **Mitigation:** The system flags all MSME invoices with urgent priority banners and highlights statutory due dates for manual AP controller sign-off.

### R-02: Concurrent Invitation Acceptance Race Condition Testing
- **Risk Scope:** High-concurrency automated stress-testing for simultaneous acceptance of identical single-use invitation tokens across distributed threads.
- **Current Behavior:** Single-use invitation tokens are hashed (SHA-256), stored with expiry timestamps, bound to specific invited email addresses, and marked `is_accepted = True` within transactional database operations.
- **Deferred Complexity:** High-load distributed race-condition testing (simultaneous HTTP requests attempting to consume the same cryptographic token within sub-millisecond windows across multiple server instances) remains deferred.
- **Mitigation:** Database transactions and atomic row-level status checks reject replay attempts sequentially with HTTP 400.

### R-03: Upstream Database Credential Rotation Confirmation
- **Risk Scope:** Confirmation of upstream hosted Supabase database credential rotation following initial repository setup exposure.
- **Current Status:** All application code and configuration strictly consume `DATABASE_URL` and `MIGRATION_DATABASE_URL` via local environment variables. Zero credentials are committed to version control, tracked in git history, or displayed in application logs/reports.
- **Deferred Action:** Formal confirmation that the underlying Supabase database password was rotated on the hosted Supabase management console is pending infrastructure administrator action.
- **Mitigation:** The application strictly enforces separate pooler (port 6543) and migration (port 5432) connection strings, role-based database privileges, and zero-trust connection isolation.

### R-04: Durable Backup Encryption Key Escrow & Cross-Region Recovery Validation
- **Risk Scope:** Enterprise Key Management Service (KMS) integration for automated escrow of the Fernet 32-byte encryption key (`BACKUP_ENCRYPTION_KEY`) and automated disaster recovery failover drill on an alternate cloud infrastructure host.
- **Current Behavior:** Cryptographically signed, AES-CBC/Fernet-encrypted, gzip-compressed database backups with SHA-256 checksum validation and PostgreSQL sandbox restoration are fully implemented and verified via automated tests.
- **Deferred Complexity:** Cloud KMS (AWS KMS or GCP Cloud KMS) envelope encryption, external key escrow, automated key rotation policies, and continuous cross-region multi-cloud standby failover drills remain deferred.
- **Mitigation:** Backups fail closed if the encryption key is missing or corrupted. Cryptographic keys are managed via isolated environment configuration outside application code.
