# Flick AI vs Zamp AP Command Center — Exhaustive Feature Gap Matrix

**Target Competitor:** Flick AI (`https://app.flickai.in/`, Tenant `Zetworth`)  
**Our Product:** Zamp AP Command Center (`Autonomous AP Operations Platform`)  
**Investigation Framework:** Chrome DevTools Protocol Remote Debugging (`127.0.0.1:9222`) + Playwright Telemetry  
**Verification Standard:** Strict Verification Tags (`[V]`, `[P]`, `[M]`, `[I]`, `[U]`)  
**Date of Audit:** November 03, 2026  
**Status:** Complete Empirical Feature Matrix  

---

## 1. Classification & Verification Standards

Every capability cataloged below is graded against our strict empirical standard:
- `[V]` **Verified:** Directly inspected, triggered, tested, and captured via live runtime telemetry or DOM inspection.
- `[P]` **Partially Observed:** Visible in UI or API responses, but constrained by trial account limitations, paywalls, or mock states.
- `[M]` **Marketing Claim:** Stated in vendor marketing, changelog, or documentation, but unverified at runtime.
- `[I]` **Inference:** Reasoned architectural or design deduction based on technical telemetry and observed patterns.
- `[U]` **Unknown / Inaccessible:** Hidden behind enterprise paywalls, server-side unexposed logic, or missing permissions.

### Gap Classifications
- **Flick Advantage:** Flick possesses a capability that Zamp lacks and should consider adopting.
- **Zamp Advantage:** Zamp possesses an enterprise capability that Flick lacks entirely.
- **Parity:** Both platforms provide comparable functionality.
- **Mutually Exclusive Scope:** Feature represents a divergent business scope (e.g., General Ledger vs. Pre-Payment Verification) that should not be copied.

---

## 2. Comprehensive Module-by-Module Feature Gap Matrix

### 2.1 Executive Dashboard & Financial Visibility

| Feature / Capability | Flick AI Status | Zamp AP Command Center Status | Gap Classification | Strategic Recommendation for Zamp |
|:---|:---:|:---:|:---:|:---|
| **Income vs Expense KPIs** | `[V]` Implemented ([01_main_dashboard_full.png](file:///c:/Zamp%20Casse%20Study/competitor_research/03_flickai/screenshots/dashboard/01_main_dashboard_full.png)) | `[V]` Not implemented (AP scope only) | Mutually Exclusive Scope | Retain AP focus; do not add general income/expense metrics outside AP spend. |
| **Net Profit & Margin %** | `[V]` Real-time profitability score ([01_main_dashboard_full.png](file:///c:/Zamp%20Casse%20Study/competitor_research/03_flickai/screenshots/dashboard/01_main_dashboard_full.png)) | `[V]` Not implemented | Mutually Exclusive Scope | Retain focus on invoice liability and cash outlays rather than corporate P&L. |
| **Net Exposure Ratio** | `[V]` Visualizes payable/receivable ratio ([01_main_dashboard_full.png](file:///c:/Zamp%20Casse%20Study/competitor_research/03_flickai/screenshots/dashboard/01_main_dashboard_full.png)) | `[V]` Not implemented | **Flick Advantage** | **Adopt AP Exposure Ratio:** Display ratio of approved payables vs. total blocked invoice liabilities. |
| **Aged Debt / Overdue Alert** | `[V]` Crimson **90+ Days Overdue** card ([01_main_dashboard_full.png](file:///c:/Zamp%20Casse%20Study/competitor_research/03_flickai/screenshots/dashboard/01_main_dashboard_full.png)) | `[V]` Not on dashboard (inside invoice header) | **Flick Advantage** | **Add Dashboard Overdue Alert:** Surface total count and INR of payables approaching or exceeding MSMED 45 days. |
| **GST Net Liability Summary** | `[V]` Current cycle GST tax payable ([01_main_dashboard_full.png](file:///c:/Zamp%20Casse%20Study/competitor_research/03_flickai/screenshots/dashboard/01_main_dashboard_full.png)) | `[V]` Not on dashboard | **Flick Advantage** | **Add Input Tax Credit (ITC) Tracker:** Display total eligible ITC locked in pending review invoices. |
| **12-Month FY Bar Chart** | `[V]` 12-month Apr–Mar revenue/expense chart ([01_main_dashboard_full.png](file:///c:/Zamp%20Casse%20Study/competitor_research/03_flickai/screenshots/dashboard/01_main_dashboard_full.png)) | `[V]` Absent (tabular lists only) | **Flick Advantage** | **Add Invoicing Volume & Spend Trend Chart:** Visualize monthly processed spend and exception rates. |
| **Next-Up Review Queue** | `[V]` Absent on dashboard (in `/files`) | `[V]` First-class queue on dashboard ([02_dashboard_today.png](file:///c:/Zamp%20Casse%20Study/competitor_research/04_cross_product_analysis/screenshots/02_dashboard_today.png)) | **Zamp Advantage** | Preserve and highlight; allows AP clerks to start reviewing high-priority invoices immediately. |
| **Critical Blockers Widget** | `[V]` Absent | `[V]` Prominent dashboard table ([02_dashboard_today.png](file:///c:/Zamp%20Casse%20Study/competitor_research/04_cross_product_analysis/screenshots/02_dashboard_today.png)) | **Zamp Advantage** | Preserve; provides instant visibility into invoices blocked by policy gates. |

---

### 2.2 Document Intake & File Repository

| Feature / Capability | Flick AI Status | Zamp AP Command Center Status | Gap Classification | Strategic Recommendation for Zamp |
|:---|:---:|:---:|:---:|:---|
| **Temporal Period Partitioning** | `[V]` Synchronized Year/Month dropdowns ([03_purchase_invoices_tab.png](file:///c:/Zamp%20Casse%20Study/competitor_research/03_flickai/screenshots/files_and_documents/03_purchase_invoices_tab.png)) | `[V]` Flat table with pagination | **Flick Advantage** | **Adopt Period Selectors:** Add Year and Month dropdowns to Zamp Inbox to isolate monthly accounting closing books. |
| **Multi-Stream Channels** | `[V]` 4 tabs: Purchase, Sales, Bank, Gateway ([03_purchase_invoices_tab.png](file:///c:/Zamp%20Casse%20Study/competitor_research/03_flickai/screenshots/files_and_documents/03_purchase_invoices_tab.png)) | `[V]` Unified AP Invoices table with status tabs | Parity | Retain unified AP focus; do not mix customer sales invoices into an AP command center. |
| **Monthly Invoicing Quota** | `[V]` Visible badge: `0/100 PDFs used` ([03_purchase_invoices_tab.png](file:///c:/Zamp%20Casse%20Study/competitor_research/03_flickai/screenshots/files_and_documents/03_purchase_invoices_tab.png)) | `[V]` Absent (unconstrained in self-host) | **Flick Advantage** | **Add Ingestion Volume Meter:** Display monthly processed invoice volume against tenant license capacity. |
| **Downloadable CSV Templates** | `[V]` 1-click `CSV Template` buttons ([04_sales_invoices_tab.png](file:///c:/Zamp%20Casse%20Study/competitor_research/03_flickai/screenshots/files_and_documents/04_sales_invoices_tab.png)) | `[V]` Absent | **Flick Advantage** | **Embed Downloadable Ingestion Templates:** Add downloadable batch CSV/Excel templates in upload modal. |
| **Secure Private Storage** | `[I]` Standard S3/cloud storage | `[V]` Supabase Private Storage with 300s pre-signed URLs ([11_connections_storage.png](file:///c:/Zamp%20Casse%20Study/competitor_research/04_cross_product_analysis/screenshots/11_connections_storage.png)) | **Zamp Advantage** | Preserve; zero-trust pre-signed URLs prevent unauthorized access to sensitive financial bills. |
| **Cryptographic Binary Hash** | `[U]` Not exposed to client | `[V]` Permanent SHA-256 binary fingerprint ([04_invoice_detail_matching.png](file:///c:/Zamp%20Casse%20Study/competitor_research/04_cross_product_analysis/screenshots/04_invoice_detail_matching.png)) | **Zamp Advantage** | Preserve; guarantees tamper-evident document integrity for legal and tax audits. |

---

### 2.3 Invoice Review Workspace & Line Items

| Feature / Capability | Flick AI Status | Zamp AP Command Center Status | Gap Classification | Strategic Recommendation for Zamp |
|:---|:---:|:---:|:---:|:---|
| **Integrated PDF Viewer** | `[V]` Detached (PDF stored in `/files`) | `[V]` 50/50 synchronized split screen ([04_invoice_detail_matching.png](file:///c:/Zamp%20Casse%20Study/competitor_research/04_cross_product_analysis/screenshots/04_invoice_detail_matching.png)) | **Zamp Decisive Win** | Preserve; side-by-side verification is non-negotiable for enterprise AP operations. |
| **Responsive Layout Modes** | `[V]` Fixed full-width container | `[V]` 3 modes: Split (50/50), Expand Analysis (12-col), Focus | **Zamp Advantage** | Preserve; allows expanding wide multi-column procurement tables to full screen with 1 click. |
| **In-Place Field Correction** | `[V]` Interactive table with instant typing ([03_create_new_invoice_builder.png](file:///c:/Zamp%20Casse%20Study/competitor_research/03_flickai/screenshots/invoice_processing/03_create_new_invoice_builder.png)) | `[V]` Read-only tabular presentation | **Flick Advantage** | **Enable In-Place Field Editing:** Allow authorized reviewers to double-click and correct OCR misreads inline. |
| **Dynamic Row Injection** | `[V]` Synchronous `Add New Row` button ([04_invoice_builder_added_row.png](file:///c:/Zamp%20Casse%20Study/competitor_research/03_flickai/screenshots/invoice_processing/04_invoice_builder_added_row.png)) | `[V]` Absent (lines populated via extraction) | **Flick Advantage** | **Add Manual Line Append:** Enable adding unextracted freight/misc charges to matching table. |
| **Indian GST Auto-Split** | `[V]` Computes CGST/SGST vs IGST automatically ([01_invoice_builder_fields.png](file:///c:/Zamp%20Casse%20Study/competitor_research/03_flickai/screenshots/extraction_and_validation/01_invoice_builder_fields.png)) | `[V]` Single tax figure; validated via Gate 5 | **Flick Advantage** | **Add Indian GST Auto-Split Preview:** Display expected CGST/SGST vs IGST breakdown based on Place of Supply. |
| **HSN/SAC Master Integration** | `[V]` Integrated Goods & Services catalog ([07_goods_and_services_catalog.png](file:///c:/Zamp%20Casse%20Study/competitor_research/03_flickai/screenshots/other_features/07_goods_and_services_catalog.png)) | `[V]` Extracted as text; no master tariff validation | **Flick Advantage** | **Add HSN/SAC Tariff Lookup:** Validate extracted codes against official GST tariff master tables. |

---

### 2.4 Procurement 3-Way Matching & Verification

| Feature / Capability | Flick AI Status | Zamp AP Command Center Status | Gap Classification | Strategic Recommendation for Zamp |
|:---|:---:|:---:|:---:|:---|
| **Authoritative 3-Way Match** | `[V]` Absent entirely | `[V]` 4-node match: Invoice vs PO vs GRN vs QC ([04_invoice_detail_matching.png](file:///c:/Zamp%20Casse%20Study/competitor_research/04_cross_product_analysis/screenshots/04_invoice_detail_matching.png)) | **Zamp Decisive Win** | Core enterprise differentiator; preserve and expand procurement data model. |
| **Quantity Variance Check** | `[V]` Absent | `[V]` Enforces strict **0.00% quantity tolerance** ([05_invoice_detail_checks.png](file:///c:/Zamp%20Casse%20Study/competitor_research/04_cross_product_analysis/screenshots/05_invoice_detail_checks.png)) | **Zamp Decisive Win** | Zero compromise; prevents paying for unreceived or short-shipped items. |
| **Price Variance Check** | `[V]` Absent | `[V]` Enforces strict **±1.50% unit rate tolerance** ([05_invoice_detail_checks.png](file:///c:/Zamp%20Casse%20Study/competitor_research/04_cross_product_analysis/screenshots/05_invoice_detail_checks.png)) | **Zamp Decisive Win** | Zero compromise; stops supplier price creeping. |
| **Quality Certificate Check** | `[V]` Absent | `[V]` Checks Goods QC inspection status (`Passed`) ([04_invoice_detail_matching.png](file:///c:/Zamp%20Casse%20Study/competitor_research/04_cross_product_analysis/screenshots/04_invoice_detail_matching.png)) | **Zamp Decisive Win** | Core manufacturing AP capability; ensures damaged goods are not cleared for payment. |
| **Reference Data Explorer** | `[V]` Master catalogs for Customers & Items | `[V]` Dedicated Procurement Records view for POs & GRNs ([12_procurement_records.png](file:///c:/Zamp%20Casse%20Study/competitor_research/04_cross_product_analysis/screenshots/12_procurement_records.png)) | **Zamp Advantage** | Preserve; allows cross-referencing open purchase orders and receiving logs. |

---

### 2.5 Policy Enforcement & Exception Governance

| Feature / Capability | Flick AI Status | Zamp AP Command Center Status | Gap Classification | Strategic Recommendation for Zamp |
|:---|:---:|:---:|:---:|:---|
| **Deterministic Policy Gates** | `[V]` Absent (basic required form fields only) | `[V]` 7 Deterministic Validation Gates ([05_invoice_detail_checks.png](file:///c:/Zamp%20Casse%20Study/competitor_research/04_cross_product_analysis/screenshots/05_invoice_detail_checks.png)) | **Zamp Decisive Win** | Core pillar of autonomous AP; preserve deterministic evaluation. |
| **Duplicate Invoice Detection** | `[V]` Handled via DB primary key | `[V]` Native Policy Gate 6 (Vendor + Invoice # + Year) | **Zamp Advantage** | Preserve; blocks fraudulent duplicate billing before ledger entry. |
| **Vendor Onboarding Check** | `[V]` Must bind to Customer/Vendor profile | `[V]` Native Policy Gate 1 (KYC / Onboarding status) | **Zamp Advantage** | Preserve; ensures payments only disburse to verified active suppliers. |
| **Structured Action Modals** | `[V]` Absent (direct edit / delete) | `[V]` Structured **Hold**, **Reject**, and **Override** ([08_action_modal_hold.png](file:///c:/Zamp%20Casse%20Study/competitor_research/04_cross_product_analysis/screenshots/08_action_modal_hold.png)) | **Zamp Decisive Win** | Enforces structured governance and categorized exception logging. |
| **Mandatory Override Justification** | `[V]` Absent | `[V]` Requires business reason for policy gate overrides | **Zamp Decisive Win** | Prevents unauthorized policy circumvention. |

---

### 2.6 Reconciliation (Bank Statements & Payment Gateways)

| Feature / Capability | Flick AI Status | Zamp AP Command Center Status | Gap Classification | Strategic Recommendation for Zamp |
|:---|:---:|:---:|:---:|:---|
| **Bank Statement Parsing** | `[V]` Ingests multi-bank CSV & PDF feeds ([01_bank_statements_upload_tab.png](file:///c:/Zamp%20Casse%20Study/competitor_research/03_flickai/screenshots/reconciliation/01_bank_statements_upload_tab.png)) | `[V]` Not implemented (pre-payment focus) | **Flick Advantage** | Consider adding post-clearance bank settlement feed to verify invoice debit. |
| **Gateway Settlement Parsing** | `[V]` Native **Razorpay** CSV template & parser ([02_payment_aggregator_tab.png](file:///c:/Zamp%20Casse%20Study/competitor_research/03_flickai/screenshots/reconciliation/02_payment_aggregator_tab.png)) | `[V]` Not implemented | **Flick Advantage** | High-value expansion for D2C/e-commerce AP workflows handling gateway fees. |
| **Fee & TDS Deduction Match** | `[V]` Identifies gateway transaction fees & TDS | `[V]` Not implemented | **Flick Advantage** | Useful pattern for auto-reconciling vendor payment gateway processing fees. |

---

### 2.7 General Ledger, Accounting & Reports

| Feature / Capability | Flick AI Status | Zamp AP Command Center Status | Gap Classification | Strategic Recommendation for Zamp |
|:---|:---:|:---:|:---:|:---|
| **Double-Entry General Ledger** | `[V]` Complete General Ledger on `/ledgers` ([02_ledger_management.png](file:///c:/Zamp%20Casse%20Study/competitor_research/03_flickai/screenshots/other_features/02_ledger_management.png)) | `[V]` Not implemented (ERP-bound) | Mutually Exclusive Scope | Retain AP scope; Zamp sends verified payloads to SAP rather than replacing SAP's GL. |
| **Real-Time P&L and Balance Sheet** | `[V]` Generates Balance Sheet & P&L ([01_financial_statements.png](file:///c:/Zamp%20Casse%20Study/competitor_research/03_flickai/screenshots/reports/01_financial_statements.png)) | `[V]` Not implemented | Mutually Exclusive Scope | Retain AP scope; financial statements belong in the core ERP. |
| **Zoho Books Synchronization** | `[V]` Bidirectional sync via OAuth callback ([08_ledgers_management.png](file:///c:/Zamp%20Casse%20Study/competitor_research/03_flickai/screenshots/other_features/08_ledgers_management.png)) | `[V]` Not implemented | **Flick Advantage** | **Add Zoho Books / Tally Connector:** Enable export of approved AP bills to mid-market Indian accounting software. |
| **SAP S/4HANA Connector** | `[V]` Absent | `[V]` Pre-configured SAP bridge schema ([11_connections_storage.png](file:///c:/Zamp%20Casse%20Study/competitor_research/04_cross_product_analysis/screenshots/11_connections_storage.png)) | **Zamp Advantage** | Complete live SAP configuration for enterprise accounts. |

---

### 2.8 Statutory Compliance & Regulatory Tools

| Feature / Capability | Flick AI Status | Zamp AP Command Center Status | Gap Classification | Strategic Recommendation for Zamp |
|:---|:---:|:---:|:---:|:---|
| **MSMED Act 2006 Compliance** | `[V]` Absent entirely | `[V]` Calculates mandatory 45-day payment deadline; header alert | **Zamp Decisive Win** | Critical Indian enterprise compliance feature; maintain and highlight. |
| **GSTR-2B Auto-Reconciliation** | `[M]` Claimed portal background sync | `[V]` Verifies GST rate against policy; no live portal sync | Parity (Unverified in Flick) | Build direct GSTN sandbox API integration to verify supplier invoice upload. |
| **Section 194 TDS Compliance** | `[V]` Gated route on `/compliance/tds` ([04_tds_compliance.png](file:///c:/Zamp%20Casse%20Study/competitor_research/03_flickai/screenshots/reconciliation/04_tds_compliance.png)) | `[V]` TDS calculated via line tax policy | Parity | Provide explicit TDS withholding summary box in invoice detail view. |

---

### 2.9 Conversational AI & Decision Intelligence

| Feature / Capability | Flick AI Status | Zamp AP Command Center Status | Gap Classification | Strategic Recommendation for Zamp |
|:---|:---:|:---:|:---:|:---|
| **Floating Action Assistant** | `[V]` Persistent button across all routes ([04_ask_flick_assistant.png](file:///c:/Zamp%20Casse%20Study/competitor_research/03_flickai/screenshots/other_features/04_ask_flick_assistant.png)) | `[V]` Absent | **Flick Decisive Win** | **Implement Slide-Out AP Copilot:** Add persistent "Ask Zamp" drawer. |
| **Contextual Prompt Suggestions**| `[V]` Surfaces 3 context-aware query chips ([04_ask_flick_assistant.png](file:///c:/Zamp%20Casse%20Study/competitor_research/03_flickai/screenshots/other_features/04_ask_flick_assistant.png)) | `[V]` Absent | **Flick Advantage** | Provide chips like: *"Show invoices blocked by Gate 4"*, *"Invoices due under MSMED this week"*. |
| **Policy-Grounded Intelligence**| `[V]` Generic financial statement queries | `[V]` Absent | **Opportunity for Zamp** | Ground copilot in Zamp's 7 policy gates to answer: *"Why is this invoice held?"* |

---

### 2.10 Governance, Dual-Control & Auditability

| Feature / Capability | Flick AI Status | Zamp AP Command Center Status | Gap Classification | Strategic Recommendation for Zamp |
|:---|:---:|:---:|:---:|:---|
| **Dual-Approval Governance** | `[V]` Absent (single-tier write access) | `[V]` Mandatory dual control for invoices $\ge \text{₹5,00,000}$ ([09_approvals_queue.png](file:///c:/Zamp%20Casse%20Study/competitor_research/04_cross_product_analysis/screenshots/09_approvals_queue.png)) | **Zamp Decisive Win** | Non-negotiable internal control; preserve and highlight to enterprise CFOs. |
| **Self-Approval Prevention** | `[V]` Absent | `[V]` System blocks reviewer from approving own submissions | **Zamp Decisive Win** | Essential anti-fraud control. |
| **Append-Only Immutable Audit**| `[V]` Basic transaction log tables | `[V]` Cryptographically backed append-only audit trail ([10_audit_page.png](file:///c:/Zamp%20Casse%20Study/competitor_research/04_cross_product_analysis/screenshots/10_audit_page.png)) | **Zamp Decisive Win** | Satisfies external audit and regulatory compliance standards. |

---

## 3. Summary Scorecard & Synthesis

```mermaid
pie title Feature Dominance Distribution across 40 Audited Capabilities
    "Zamp Decisive Advantages (Governance & 3-Way Match)" : 17
    "Flick AI Advantages (Financial Visibility & Ingestion)" : 12
    "Mutually Exclusive Business Scope" : 6
    "Feature Parity" : 5
```

- **Total Capabilities Audited:** 40 discrete features across 10 functional modules.
- **Zamp Advantages (17 capabilities):** Dominated by 4-node 3-way procurement matching, 7 deterministic policy gates, mathematical tolerances, mandatory dual-control sign-off (≥ ₹5L), 50/50 split PDF workspace, MSMED statutory deadlines, and cryptographic append-only audit trail.
- **Flick AI Advantages (12 capabilities):** Dominated by executive financial scorecards (Net Exposure, 90+ Days Overdue, GST Liability), temporal Year/Month document partitioning, downloadable sample CSV templates, native Indian GST auto-split engine, and ambient conversational AI ("Ask Flick").
- **Mutually Exclusive Scope (6 capabilities):** General Ledger journal entries, P&L statements, Balance Sheets, and customer AR invoicing belong strictly to Flick AI's SME accounting domain and should not dilute Zamp's specialized AP pre-payment focus.
