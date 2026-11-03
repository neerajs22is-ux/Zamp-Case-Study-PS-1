# FinBooks Reverse Engineering Evidence Log

**Target Application:** `https://app.finbooks.ai/`  
**Trial Organization:** `Svit` (User: `SUBRAMANIAN`)  
**Investigation Framework:** REA (Reverse Engineer Anything) + Chrome CDP Native Inspection  
**Date of Investigation:** November 03, 2026  

---

## 1. Evidence Classification Standard
Every claim and observation in this investigation is labeled according to the strict verification standard:
- `[V]` **Verified:** Directly inspected, triggered, tested, and captured via live runtime telemetry, DOM dumps, or network interception.
- `[P]` **Partially Observed:** Visible in UI or API responses, but constrained by trial account limitations, paywalls, or mock states.
- `[M]` **Marketing Claim:** Stated in vendor marketing, changelog, or documentation, but unverified at runtime.
- `[I]` **Inference:** Reasoned architectural or design deduction based on technical telemetry and observed patterns.
- `[U]` **Unknown / Inaccessible:** Hidden behind enterprise paywalls, server-side unexposed logic, or missing permissions.

---

## 2. Master Telemetry & Evidence Ledger

| Evidence ID | Category | Component / Route | Verification Method | Raw Artifact / Screenshot Reference | Status |
|:---|:---|:---|:---|:---|:---:|
| **EV-001** | Architecture | Root Layout / App Shell | CDP DOM & Network Inspection | `screenshots/navigation/01_sidebar_initial.png`, `02_sidebar_expanded.png` | `[V]` |
| **EV-002** | Dashboard | Executive Financial Dashboard | CDP DOM Dump & Screenshot | `screenshots/dashboard/01_dashboard_full.png`, `02_dashboard_bank_statement_view.png` | `[V]` |
| **EV-003** | AP / Intake | Vendor Bills Queue & Dropzone | DOM Analysis & Script Extraction | `screenshots/invoice_workflow/01_vendor_bills_workspace.png`, `02_upload_modal.png` | `[V]` |
| **EV-004** | Commercial | Pricing, Limits & Billing Model | Live DOM Modal Parsing & Razorpay Config | `screenshots/other_features/13_billing.png`, `billing_extracted.json` | `[V]` |
| **EV-005** | Document Review | Slide-out PDF Viewer (`srcDocPanel`) | CDP JS Evaluation & Screenshot | `screenshots/review_and_validation/02_source_doc_viewer.png` | `[V]` |
| **EV-006** | Document Review | Invoice Edit Modal (`editForm`) | Form DOM Inspection & Field Capture | `screenshots/review_and_validation/01_invoice_review_workspace.png`, `scratch/edit_form.html` | `[V]` |
| **EV-007** | OCR / Extraction | Synthetic Invoice Ingestion & OCR | File Upload via Playwright + CDP Monitor | `screenshots/invoice_workflow/07_bills_list_after_upload.png`, Ingest JSON payload | `[V]` |
| **EV-008** | Schema / Data | Bill Entity & Line Items Structure | Captured `openEditModal` JSON Argument | Raw JSON dump in `evidence_log.md` Section 3 | `[V]` |
| **EV-009** | Exception / Fraud | Duplicate Invoice Detection (`dupCard`) | Script Decompilation & Notice Trigger | `screenshots/exceptions/01_exception_handling.png`, Script dump | `[V]` |
| **EV-010** | PO Matching | Purchase Order Relinking (`voRelinkPrompt`) | Runtime Function Decompilation | `scratch/check_js_actions.py` output (`window.prompt`) | `[V]` |
| **EV-011** | Accounting | Double-Entry General Ledger | UI Route Navigation & Paywall Check | `screenshots/other_features/07_accounting_ledger.png` | `[P]` |
| **EV-012** | AI Assistant | CFO Assistant Query Interface | Paywall Inspection (Pro Plan required) | `screenshots/other_features/05_cfo_assistant.png` | `[P]` |
| **EV-013** | Compliance | GSTR-1, GSTR-2B & ITC Reconciliation | DOM Inspection & Settings Check | `screenshots/other_features/06_gst_compliance.png` | `[V]` |
| **EV-014** | Integrations | TallyPrime XML & Zoho Books Engine | UI Modal & Endpoint Audit | `screenshots/other_features/10_integrations_import.png`, `11_integrations_export.png` | `[V]` |
| **EV-015** | Product History | In-App Interactive Help & Changelog | Full HTML Changelog Extraction (v2.0 - v2.13) | DOM extraction in Section 4 | `[V]` |

---

## 3. Verified Backend Entity Schema (Observed Payload)

During the synthetic invoice upload test (`INV-2026-9042`, ₹11,800.00), the backend response and embedded frontend bill payload was captured in its raw form:

```json
{
  "_id": "6ae9c8092cc937b7118e8798",
  "organization_id": "6ae9b769883aba2968f8a62c",
  "created_by": "6ae9b769883aba2968f8a62d",
  "created_at": "2026-11-03T11:39:53.956000",
  "updated_at": "2026-11-03T11:39:53.995000",
  "source_filename": "synthetic_vendor_invoice.pdf",
  "source_page": 1,
  "file_url": "s3://ai-accountant-docs/organizations/6ae9b769883aba2968f8a62c/vendors/87ecc16e9c534e42bf2f01aadb32bfbd.pdf",
  "file_hash": "a86e91bcb3ee0f3cf3cb701d1b5f55b2a53d267d25c662a1c595e5033a7ee166",
  "business_invoice_hash": "901c52685e6b5bd9f000cec074753e00d1948f3443e1c6f1cba3379a4d168754",
  "ai_extracted": true,
  "vendor_id": "6ae9c8092cc937b7118e8797",
  "vendor_name": "Acme Cloud Services India Pvt Ltd",
  "gstin": "29AABCA1234F1Z5",
  "gstin_id": null,
  "invoice_number": "INV-2026-9042",
  "invoice_date": "2026-11-01T00:00:00",
  "currency": "INR",
  "amount": 10000.0,
  "discount": null,
  "round_off": null,
  "tax_amount": 1800.0,
  "tax_data": {
    "cgst": 0.0,
    "sgst": 0.0,
    "igst": 1800.0
  },
  "total_amount": 11800.0,
  "status": "approved",
  "match_status": "ORDER_NOT_FOUND",
  "match_discrepancies": [],
  "match_line_items": [],
  "match_locked": false,
  "vendor_order_id": null,
  "vendor_order_number": null,
  "cost_centre_code": "",
  "cost_centre_name": "",
  "line_items": [
    {
      "amount": 6000.0,
      "description": "Cloud Compute Virtual Instances (CPU/RAM)",
      "item_code": null,
      "quantity": 2,
      "rate": 3000.0
    },
    {
      "amount": 4000.0,
      "description": "Managed SSD Storage Volume (1 TB NVMe)",
      "item_code": null,
      "quantity": 1,
      "rate": 4000.0
    }
  ],
  "_vendor_master": {
    "_id": "6ae9c8092cc937b7118e8797",
    "organization_id": "6ae9b769883aba2968f8a62c",
    "name": "Acme Cloud Services India Pvt Ltd",
    "gstin": "29AABCA1234F1Z5",
    "pan": "",
    "email": "",
    "phone": "",
    "address": "",
    "vendor_type": "goods",
    "tds_applicable": false,
    "tds_rate": 0.0,
    "tds_section": "",
    "created_at": "2026-11-03T11:39:53.970000",
    "updated_at": "2026-11-03T11:39:53.970000"
  }
}
```

### Critical Architectural Observations from Entity Payload:
1. **Cloud Architecture:** Stored in AWS S3 under bucket `ai-accountant-docs` with path `organizations/{org_id}/vendors/{uuid}.pdf`.
2. **Dual Deduplication Keys:**
   - `file_hash`: SHA-256 binary hash of the uploaded asset to prevent re-uploading identical files.
   - `business_invoice_hash`: SHA-256 hash derived from `[vendor_id + invoice_number + invoice_date + total_amount]` to block duplicate invoices uploaded under different filenames or scans.
3. **Automated Vendor Master Creation:** If a vendor GSTIN is encountered during OCR that does not exist in the database, the backend automatically provisions a new `_vendor_master` entry with `vendor_type: "goods"`.
4. **Line Item Extraction vs. UI Exposure Gap:** The OCR model extracted structured line items with quantity, unit rate, and total amount. However, the frontend editing workspace (`editForm`) completely discards line-item UI rendering, permitting edits only at the header total level.

---

## 4. Reverse-Engineered Changelog & Architectural Roadmap

Extracted from the active DOM Help & Documentation component (`table tr` entries):

- **v2.13 (Sept 2026):**
  - Import Vendors, Customers & Supplier Item Names via spreadsheet preview.
  - Smarter Vendor Invoice Matching (fuzzy vendor name recognition, item code matching).
  - Sales Orders: Receive extra goods over PO quantity, link invoices side-by-side.
  - Dashboard: Toggle between Finances and Inventory tabs.
- **v2.12 (Sept 2026):**
  - PO Item Mapping Rules: Keyword rules to map vendor names to internal item codes; backfills automatically onto existing POs.
  - Stricter 15-char GSTIN checksum verification.
- **v2.11 (Aug 2026):**
  - Multi-Entity & Multi-GSTIN Support.
  - Quotations module with 1-click conversion to invoice.
  - Per-GSTIN branding, bank accounts, and addresses.
  - Role-based team access (Viewer, Accountant, Admin, Owner) per GSTIN.
  - Bank reconciliation net of TDS with 30–60 day late payment windows.
- **v2.10 (June 2026):**
  - Mobile UI for Vendor Bills.
  - OCR Review Flag & 1-click Bulk Approve.
  - Backend search + per-page pagination (10, 25, 50, 100).
- **v2.6 – v2.9 (May 2026):**
  - Cost Centres 3-level hierarchy (Cost Head, Cost Centre, Product).
  - GSTR-1 & GSTR-2B JSON import and ITC portal reconciliation.
  - CA multi-organization portal.
- **v2.0 – v2.5 (March – April 2026):**
  - Double-entry ledger, Trial Balance, Balance Sheet.
  - AI CFO Assistant.
  - TOTP Two-Factor Authentication.
  - TallyPrime XML & Zoho Books export.
