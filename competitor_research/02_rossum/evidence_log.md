# Rossum Reverse Engineering Evidence Log

**Target Application:** `https://svit.rossum.app/` (Rossum Cloud Platform)  
**Trial Organization:** `SVIT` (User: `Neeraj S`)  
**Investigation Framework:** Chrome CDP Native Remote Debugging (`127.0.0.1:9222`) + Playwright Telemetry (REA MCP fallback)  
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
| **EV-000** | Infrastructure | Chrome CDP Remote Debugger & Login Portal | Native CDP HTTP Probe & Playwright Viewport Capture | `screenshots/navigation/00_login_page.png` | `[V]` |
| **EV-001** | Queues / IA | Sidebar Queue Hierarchy (8 Queues, 23 Docs) | DOM Tree Dump & Telemetry Extraction | `screenshots/document_queues/01_queue_credit_notes.png` | `[V]` |
| **EV-002** | Queue Mgmt | Global "All Documents" Multi-Queue View | Direct Navigation & DOM Row Extraction | `screenshots/document_queues/02_all_documents_queue.png` | `[V]` |
| **EV-003** | Filtering | Queue Search & Popover Filtering System | Interactive Click & MUI Popover Inspection | `screenshots/document_queues/03_queue_filter_menu.png` | `[V]` |
| **EV-004** | Queue Types | US Tax Invoices Specialized Queue | Direct Filter & Row Telemetry | `screenshots/document_queues/06_queue_tax_invoices_us.png` | `[V]` |
| **EV-005** | Workspace | Split-Pane Review Workspace (Credit Note) | 1920x1080 Viewport Capture & DOM Measurement | `screenshots/document_review/01_full_review_workspace_credit_note.png`, `02_review_workspace_1920x1080.png` | `[V]` |
| **EV-006** | Onboarding | Interactive New Reviewer Guidance Tour | Viewport Capture & Tour Modal Detection | `screenshots/other_features/01_onboarding_review_tour.png` | `[V]` |
| **EV-007** | Workspace | Clean Review Workspace (Unblocked Canvas) | DOM Dismissal & Viewport Capture | `screenshots/document_review/03_clean_review_workspace.png` | `[V]` |
| **EV-008** | Bounding Box | PDF Viewer SVG Highlighting: Issue Date | Field Click Telemetry & SVG `rect` Extraction (51 rects) | `screenshots/document_review/04_field_highlight_issue_date.png` | `[V]` |
| **EV-009** | Bounding Box | PDF Viewer SVG Highlighting: Vendor Name | Field Click Telemetry & SVG Coordinate Inspection | `screenshots/document_review/05_field_highlight_vendor_name.png` | `[V]` |
| **EV-010** | Bounding Box | PDF Viewer SVG Highlighting: Amount Due | Field Click Telemetry & SVG Coordinate Inspection | `screenshots/document_review/06_field_highlight_amount_due.png` | `[V]` |
| **EV-011** | Schema / Form | Extracted Form Sections (Basic, Totals, Vendor, Lines) | DOM Node Enumeration & Text Dump | `screenshots/document_review/08_us_tax_invoice_full_workspace.png` | `[V]` |
| **EV-012** | In-Doc Search | PDF Viewer "Find in document" Text Search | Button Trigger & Search Bar Capture | `screenshots/document_review/09_find_in_document.png` | `[V]` |
| **EV-013** | Metadata | Document Info Flyout Panel (`DetailDrawer.tsx`) | Button Click & Drawer DOM Telemetry | `screenshots/document_review/10_document_info_panel.png` | `[V]` |
| **EV-014** | Collaboration | Document Comments Side Drawer | Button Click & MUI Drawer Capture | `screenshots/document_review/11_document_comments_drawer.png` | `[V]` |
| **EV-015** | Ergonomics | Reviewer Sidebar Settings & Layout Controls | Button Trigger & Settings Capture | `screenshots/document_review/12_sidebar_settings_modal.png` | `[V]` |
| **EV-016** | Exceptions | Missing Required Field Flagging (`Document ID ?`) | DOM Error Class Extraction & Badge Telemetry | `screenshots/exceptions/01_missing_required_document_id.png` | `[V]` |
| **EV-017** | Correction | Inline Edit Floating Input Box (`editBoxInput`) | Field Click & Focus Trap Telemetry | `screenshots/exceptions/02_document_id_focused_input.png` | `[V]` |
| **EV-018** | Completion | Confirm Action & Quality Feedback Survey | Button Click & Survey Modal Interception | `screenshots/exceptions/03_confirm_blocked_or_modal.png` | `[V]` |
| **EV-019** | Correction | Human Resolution of Missing Field (`INV-2026-US-8841`) | Keyboard Typing & State Transition Capture | `screenshots/exceptions/04_document_id_corrected_resolved.png` | `[V]` |
| **EV-020** | Line Items | Multi-Row Line Items Expansion & Grid Structure | Section Click & Table Extraction (4 line items) | `screenshots/extraction_and_validation/03_us_invoice_line_items_grid.png` | `[V]` |
| **EV-021** | Productivity | Reviewer Keyboard Shortcuts Cheat Sheet | Shift+Slash (`?`) Trigger & Keyboard Map Extraction | `screenshots/navigation/04_keyboard_shortcuts_modal.png`, `06_keyboard_shortcuts_sheet.png` | `[V]` |
| **EV-022** | Settings | Administration & Governance Control Center | Navigation & Module Inventory | `screenshots/navigation/05_settings_overview.png` | `[V]` |
| **EV-023** | Analytics | Operational Dashboard & Performance Analytics | Direct Navigation & Chart Telemetry (160 SVG charts) | `screenshots/dashboard/01_statistics_dashboard_full.png` | `[V]` |
| **EV-024** | Automation | Workflow & AI Engine Rules Overview | Direct Navigation & Link Extraction | `screenshots/workflow_actions/02_automation_overview.png` | `[V]` |
| **EV-025** | Intake | Drag-and-Drop Ingestion Dropzone Modal | Upload Button Trigger & Modal Capture | `screenshots/workflow_actions/01_upload_modal.png` | `[V]` |
| **EV-026** | Ecosystem | Installed Extensions Hub (`My Extensions`) | Direct Navigation & Config Extraction | `screenshots/other_features/02_extensions_my_extensions.png` | `[V]` |
| **EV-027** | Marketplace | Rossum Store Integration Catalog (SAP, Coupa, Hub) | Direct Navigation & Card Parsing (20+ Integrations) | `screenshots/other_features/03_extensions_rossum_store.png`, `06_store_catalog_grid.png` | `[V]` |
| **EV-028** | RBAC | User Roles & Access Administration | Direct Navigation & User Telemetry (`Neeraj S`) | `screenshots/other_features/05_users_and_roles_settings.png` | `[V]` |
| **EV-029** | Field Mgmt | Cross-Queue Field Manager System | Text Telemetry from Settings Overview | Documented in `ui_ux_analysis.md` | `[V]` |
| **EV-030** | Auditability | Configuration Changelog & System Activity Logs | Text Telemetry from Settings Overview | Documented in `workflow_analysis.md` | `[V]` |

---

## 3. Account & Technical Telemetry
- **Host Endpoint:** `https://svit.rossum.app`
- **Internal API Base:** `https://api.elis.rossum.ai/v1/`
- **Frontend Stack:** React 18, Vite/Rolldown runtime, Material-UI (MUI v5/Emotion), Sentry monitoring, Freshchat/Freshworks support widget, Unleash feature toggling.
- **Trial Quotas & State:** 8 Queues active, 23 total sample documents across multiple jurisdictions (US, UK, EU), unlimited manual review access during trial.
