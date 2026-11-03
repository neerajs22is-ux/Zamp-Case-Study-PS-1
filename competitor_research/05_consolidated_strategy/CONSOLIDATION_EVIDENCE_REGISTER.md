# Master Consolidation Evidence Register
## Empirical Cross-Product Evidence & Telemetry Ledger

**Target Deliverable:** `competitor_research/05_consolidated_strategy/CONSOLIDATION_EVIDENCE_REGISTER.md`  
**Date of Synthesis:** November 03, 2026  
**Status:** Certified Empirical Evidence Register  

---

## 1. Investigation Framework & Standards

Every recommendation and architectural decision across our consolidated roadmap is tethered to verifiable empirical evidence under our strict five-tier verification standard:

- `[V]` **Verified:** Directly inspected, triggered, tested, and captured via live runtime telemetry, DOM dumps, or network interception.
- `[P]` **Partially Observed:** Visible in UI or API responses, but constrained by trial account limitations, paywalls, or mock states.
- `[M]` **Marketing Claim:** Stated in vendor marketing, changelog, or documentation, but unverified at runtime.
- `[I]` **Inference:** Reasoned architectural or design deduction based on technical telemetry and observed patterns.
- `[U]` **Unknown / Inaccessible:** Hidden behind enterprise paywalls, server-side unexposed logic, or missing permissions.

---

## 2. Master Opportunity-to-Evidence Traceability Matrix

| Opp ID | Short Name | Primary Competitor Evidence ID & Artifacts | Zamp Source Files Affected | Evidence Confidence |
|:---:|:---|:---|:---|:---:|
| **OPP-01** | **Audited In-Place Data Correction** | **FB-008** ([finbooks_vs_ap_command_center.md](file:///c:/Zamp%20Casse%20Study/competitor_research/04_cross_product_analysis/finbooks_vs_ap_command_center.md))<br/>**RO-004** ([rossum_vs_ap_command_center.md](file:///c:/Zamp%20Casse%20Study/competitor_research/04_cross_product_analysis/rossum_vs_ap_command_center.md))<br/>**FLICK-011, FLICK-013** ([03_create_new_invoice_builder.png](file:///c:/Zamp%20Casse%20Study/competitor_research/03_flickai/screenshots/invoice_processing/03_create_new_invoice_builder.png)) | `frontend/src/pages/InvoiceDetailPage.tsx`<br/>`backend/api/v1/invoices.py`<br/>`backend/models/domain.py` | `[V]` Verified across all 3 competitors |
| **OPP-02** | **PDF-to-Field Coordinate Highlighting** | **RO-003** (SVG vector mesh with 51+ rects in Rossum)<br/>**FB-005** (FinBooks OCR bounding boxes) | `frontend/src/pages/InvoiceDetailPage.tsx`<br/>`backend/models/domain.py` (`ExtractedField.bounding_box`) | `[V]` Verified in Rossum & FinBooks |
| **OPP-03** | **Continuous Review Loop Navigation** | **RO-005** (`Confirm & Next` queue advancement in Rossum)<br/>**FB-007** (`Next Invoice` button in FinBooks) | `frontend/src/pages/InvoiceDetailPage.tsx`<br/>`backend/api/v1/invoices.py` | `[V]` Verified in Rossum & FinBooks |
| **OPP-04** | **Temporal Period (Year/Month) Filtering** | **FLICK-005, FLICK-007** ([03_purchase_invoices_tab.png](file:///c:/Zamp%20Casse%20Study/competitor_research/03_flickai/screenshots/files_and_documents/03_purchase_invoices_tab.png)) | `frontend/src/pages/InboxPage.tsx`<br/>`backend/api/v1/inbox.py` | `[V]` Verified in Flick AI |
| **OPP-05** | **Downloadable Batch Ingestion Templates** | **FLICK-008, FLICK-017** ([04_sales_invoices_tab.png](file:///c:/Zamp%20Casse%20Study/competitor_research/03_flickai/screenshots/files_and_documents/04_sales_invoices_tab.png), [02_payment_aggregator_tab.png](file:///c:/Zamp%20Casse%20Study/competitor_research/03_flickai/screenshots/reconciliation/02_payment_aggregator_tab.png)) | `frontend/src/pages/InboxPage.tsx`<br/>`/public/templates/` | `[V]` Verified in Flick AI |
| **OPP-06** | **Executive AP Capital Exposure Scorecard** | **FLICK-003, FLICK-004** ([01_main_dashboard_full.png](file:///c:/Zamp%20Casse%20Study/competitor_research/03_flickai/screenshots/dashboard/01_main_dashboard_full.png))<br/>**FB-002** (FinBooks payable exposure) | `frontend/src/pages/DashboardPage.tsx`<br/>`backend/api/v1/dashboard.py` | `[V]` Verified in Flick AI & FinBooks |
| **OPP-07** | **Indian GST Interstate/Intrastate Auto-Split** | **FLICK-012** ([01_invoice_builder_fields.png](file:///c:/Zamp%20Casse%20Study/competitor_research/03_flickai/screenshots/extraction_and_validation/01_invoice_builder_fields.png)) | `frontend/src/utils/tax.ts`<br/>`frontend/src/pages/InvoiceDetailPage.tsx` | `[V]` Verified in Flick AI |
| **OPP-08** | **Ambient "Ask Zamp" AP Copilot Drawer** | **FLICK-028, FLICK-029** ([04_ask_flick_assistant.png](file:///c:/Zamp%20Casse%20Study/competitor_research/03_flickai/screenshots/other_features/04_ask_flick_assistant.png)) | `frontend/src/components/AskZampDrawer.tsx`<br/>`backend/api/v1/copilot.py` | `[V]` Verified in Flick AI |
| **OPP-09** | **Contextual PO Search & Line Re-association** | **FB-009** (FinBooks open PO search modal) | `frontend/src/pages/InvoiceDetailPage.tsx`<br/>`backend/api/v1/source_records.py` | `[V]` Verified in FinBooks |
| **OPP-10** | **Workspace Tab Consolidation** | **RO-001** (Unified scrollable panel in Rossum)<br/>**FB-004** (Integrated match table in FinBooks) | `frontend/src/pages/InvoiceDetailPage.tsx` | `[V]` Verified in Rossum & FinBooks |
| **OPP-11** | **Ingestion Volume & License Quota Gauge** | **FLICK-007** (`0/100 PDFs used` badge in Flick AI) | `frontend/src/components/AppShell.tsx`<br/>`backend/api/v1/system.py` | `[V]` Verified in Flick AI |
| **OPP-12** | **Evaluation Mode Watermark & Reset** | **FLICK-002** (Trial branding in Flick AI) | `frontend/src/components/AppShell.tsx`<br/>`backend/api/v1/system.py` | `[V]` Verified |
| **OPP-13** | **One-Click Contextual ERP Payload Drawer** | **FLICK-024** (Party ledger drill-down in Flick AI) | `frontend/src/pages/InboxPage.tsx`<br/>`backend/api/v1/invoices.py` | `[V]` Verified in Flick AI |
| **OPP-14** | **Gateway Settlement Variance Reconciliation** | **FLICK-017** ([02_payment_aggregator_tab.png](file:///c:/Zamp%20Casse%20Study/competitor_research/03_flickai/screenshots/reconciliation/02_payment_aggregator_tab.png)) | `frontend/src/pages/InvoiceDetailPage.tsx`<br/>`backend/models/domain.py` | `[V]` Verified in Flick AI |
| **OPP-15** | **In-Viewer Full-Text Document Search** | **RO-002** (`Find in document` toolbar in Rossum) | `frontend/src/pages/InvoiceDetailPage.tsx` | `[V]` Verified in Rossum |

---

## 3. Unverified Assumptions & Known Discrepancies

1. **GSTN Portal Direct Synchronization (Flick AI):**
   - *Claim:* Flick AI marketing documents claim automated GSTR-2B purchase register fetching from the government tax portal.
   - *Empirical Status:* `[M]` Marketing Claim. Could not be verified live at runtime as the route was gated behind organization owner permissions.
   - *Impact on Zamp:* Zamp verifies tax calculations against deterministic policy rules, rather than depending on external GSTN portal uptime.
2. **Server-Side Matching Heuristics (Flick AI & Rossum):**
   - *Claim:* Rossum and Flick claim proprietary neural matching between raw invoice narrations and bank/PO records.
   - *Empirical Status:* `[U]` Server-side private code.
   - *Impact on Zamp:* Zamp’s matching engine is deterministic and rules-based (0.00% qty, $\pm 1.50\%$ rate), which provides full transparency to auditors.
3. **Tally Prime XML Export (Flick AI):**
   - *Claim:* Flick AI claims direct offline XML synchronization with Tally Prime.
   - *Empirical Status:* `[M]` Unverified due to lack of a live local Tally desktop client.
4. **Approval Threshold Invariant Clarification:**
   - *Observation:* Previous research notes occasionally described ₹5,00,000 as a statutory requirement.
   - *Clarification:* The ₹5,00,000 dual-control threshold is a **Project Approval Control Policy**, not a government statute. MSMED Act 2006 §15 is a statutory 45-day payment deadline. This distinction is now strictly maintained across all deliverables.
