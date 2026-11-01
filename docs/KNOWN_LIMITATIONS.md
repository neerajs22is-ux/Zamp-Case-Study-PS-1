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

### B. Lack of Keyboard Navigation & AP Power-User Shortcuts
- **Current Behavior:** All invoice triage, pagination, pane switching, and action submissions require manual mouse clicks.
- **Identified Usability Friction:** High-volume AP clerks process dozens of invoices per hour. The absence of keyboard shortcuts (e.g., `J`/`K` for next/previous invoice, `A` for approve, `H` for hold, `R` for reject, `Esc` to close modal) significantly slows down review velocity.

### C. Action Justification Friction
- **Current Behavior:** When an AP Lead or Controller clicks `APPROVE_AP_REVIEW`, `HOLD_PENDING_EVIDENCE`, or `REJECT_INVOICE`, an action modal opens requiring mandatory text justification before the submit button becomes active.
- **Identified Usability Friction:** While mandatory justification is essential for audit compliance, there are no quick-select templates or pre-populated macro reasons (e.g., *"Unit price exceeds PO rate by >1.5%"*, *"PO balance exhausted"*), requiring operators to type repetitive explanations manually.

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
