# AP Command Center — Unverified Configuration Requirements & Assumptions

**Document Status:** Pending Customer / Authorised Owner Confirmation  
**Governing Standard:** Production Truth Rules (No Unverified Defaults)

The following operational and business parameters cannot be assumed or invented. Until authoritative configuration is supplied by the customer's designated owners (e.g., Zetwerk Finance, Tax, Procurement, and IT Security teams), these items are classified as **UNVERIFIED CONFIGURATION REQUIREMENTS** and remain in a setup-blocked or unconfigured state.

---

## 1. Mailbox & Email Ingestion Configuration
- **Mailbox Address:** Not configured (e.g., candidate `ap.invoices@zetwerk.com` or `ap-inward@zetwerk.com` requires formal IT security sign-off).
- **Mailbox Owner / Service Account:** Subject to Google Workspace / Microsoft 365 delegation approval.
- **Allowed Ingestion Domains / Inbound Whitelists:** Must be specified by corporate IT security.
- **Attachment Filtering Criteria:** Inline signature image threshold and non-PDF attachment policy must be defined by AP operations.

## 2. Legal Entities, Plant Locations & ERP Company Codes
- **Legal Entity Master:** Customer-specific entity IDs, registered names, and operating states must be imported from ERP.
- **GSTINs:** Exact registered GSTINs per operating state must be provisioned (example placeholder `29AAACZ1234F1Z5` is strictly unverified).
- **ERP Company Codes & Plants:** SAP S/4HANA company code (e.g., `1000`) and plant codes must be mapped to corporate tax registrations.

## 3. SAP S/4HANA Tenant & API Integration
- **Tenant Endpoint / Hostname:** SAP S/4HANA OData / RFC endpoint URL.
- **Authentication Method:** OAuth 2.0 / Client Credentials / Mutual TLS.
- **Service Account & Read-Only Scopes:** Exact authorization scopes for PO, GRN, Quality Certificate, Rate Contract, and Payment tables.
- **Sync Freshness SLA:** Maximum acceptable staleness for cached ERP snapshots before an exception gate evaluates to `UNKNOWN`.

## 4. Statutory Tax & MSME Policies (Indian Jurisdiction)
- **Customer Finance / Legal Tax Interpretation:**
  - Written confirmation of effective-dated tax provisions applicable to the customer's entities.
  - Confirmation of Income-tax Act, 2025 commencement provisions (e.g., Section 37(2)(g) vs legacy Section 43B(h)) for relevant financial years.
  - Approved Section 194Q TDS / Section 206C(1H) TCS thresholds, payee classifications, and exemptions.
- **MSMED Act 2006 Rule Interpretation:**
  - Standard policy on date of deemed acceptance (Section 2(b)) and handling of day-of-objection logs.
  - Section 16 penal interest rate schedule and compound calculation method approved by corporate legal.
  - Enterprise classification criteria (Micro and Small vs Medium enterprises).

## 5. Approval Matrix & Financial Thresholds
- **Dual-Approval Monetary Threshold:** Customer policy defining the exact amount requiring two distinct approvers (e.g., ₹5,00,000 is an unconfirmed default).
- **Authority Matrix:** Role-to-entity and role-to-amount authorization limits for AP Associates, AP Leads, Controllers, and Category Managers.
- **Matching Tolerances:** Exact acceptable variance percentages and absolute amounts for unit rates, line totals, and tax rounding.

## 6. Retention, Security & Deletion Policy
- **Document Retention Schedule:** Statutory retention period for invoice originals and extraction logs (e.g., 8 years under Indian Companies Act / GST Act).
- **Data Residency:** Storage region requirements (e.g., AWS `ap-south-1` / GCP `asia-south1` in Mumbai/Delhi).
- **Malware Scanning Provider:** Customer-mandated scanning engine (ClamAV / AWS GuardDuty / VirusTotal API).
