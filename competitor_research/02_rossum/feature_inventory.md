# Rossum Comprehensive Feature Inventory

**Target Application:** `https://svit.rossum.app/` (Rossum Cloud Platform)  
**Verification Framework:** REA Telemetry + Chrome DevTools Protocol Native Remote Debugging  
**Audit Date:** November 03, 2026  
**Trial Organization:** `SVIT` (User: `Neeraj S`)  

---

## 1. Classification Methodology

- `[V]` **Verified:** Directly inspected, triggered, tested, and captured via live runtime telemetry, DOM dumps, or network interception.
- `[P]` **Partially Observed:** Visible in UI or API responses, but constrained by trial account limitations, paywalls, or mock states.
- `[M]` **Marketing Claim:** Stated in vendor marketing, changelog, or documentation, but unverified at runtime.
- `[I]` **Inference:** Reasoned architectural or design deduction based on technical telemetry and observed patterns.
- `[U]` **Unknown / Inaccessible:** Hidden behind enterprise paywalls, server-side unexposed logic, or missing permissions.

---

## 2. Master Feature Inventory Table

| Feature / Capability | Category | Description & Observed Behavior | Evidence ID & Artifact Reference | Status |
|:---|:---|:---|:---|:---:|
| **Specialized Queue Architecture** | Queue Mgmt | Discrete document queues per document type (Credit notes, Tax invoices EU/UK/US, POs) with independent schemas. | `EV-001`, `01_queue_credit_notes.png` | `[V]` |
| **All Documents Aggregated Queue** | Queue Mgmt | Global unified view displaying all documents across every queue with status, details, and filtering. | `EV-002`, `02_all_documents_queue.png` | `[V]` |
| **Status Tab Filters** | Queue Mgmt | Fast queue filtering by processing state: `Reviews` (count badge), `Postpone`, and `All`. | `EV-001`, `01_document_list_queue_initial.png` | `[V]` |
| **Advanced Attribute Filtering** | Queue Mgmt | Multi-condition filter builder with field selection, operators (`isAnyOf`, `equals`), and AND/OR logic. | `EV-003`, `03_queue_filter_menu.png` | `[V]` |
| **Drag & Drop Ingestion Modal** | Intake | In-browser file dropzone supporting batch file selection and automatic ingestion into active queue. | `EV-025`, `01_upload_modal.png` | `[V]` |
| **Split-Pane Review Workspace** | Review UI | Synchronized split layout: interactive document viewer on left, structured extraction form on right. | `EV-005`, `02_review_workspace_1920x1080.png` | `[V]` |
| **SVG Coordinate Bounding Boxes** | Review UI | Dynamic SVG overlay containing 50+ coordinate-mapped `rect` elements highlighting exact OCR source text. | `EV-008`-`010`, `04_field_highlight_issue_date.png` | `[V]` |
| **Two-Way Bounding Box Binding** | Review UI | Clicking form field highlights PDF canvas region; hovering/clicking canvas region highlights field. | `EV-008`-`010`, `05_field_highlight_vendor_name.png` | `[V]` |
| **Floating Edit Input (`editBoxInput`)**| Review UI | Dynamic floating input box rendering next to active field with instant keyboard capture. | `EV-017`, `02_document_id_focused_input.png` | `[V]` |
| **Live Document Translation (Ctrl+T)** | Review UI | Built-in real-time translation toggle for foreign language documents (e.g. EU invoices in French/German). | `EV-015`, `list_buttons.py` output | `[V]` |
| **In-Viewer Text Search** | Review UI | "Find in document" search bar allowing direct substring search across rendered OCR text layer. | `EV-012`, `09_find_in_document.png` | `[V]` |
| **Document Info Drawer (`DetailDrawer`)**| Review UI | Side drawer displaying document metadata (filename, import timestamp, source channel, format). | `EV-013`, `10_document_info_panel.png` | `[V]` |
| **Document Comments & Notes** | Collaboration | Side drawer for reviewer collaboration, internal notes, and audit remarks tied to document ID. | `EV-014`, `11_document_comments_drawer.png` | `[V]` |
| **Multi-File Attachment Support** | Review UI | "Files" counter indicator displaying linked attachments and supplementary pages for a transaction. | `EV-015`, `list_buttons.py` output | `[V]` |
| **Viewer Zoom & Pan Ergonomics** | Review UI | Full zoom toolbar: Zoom In, Zoom Out, Reset Zoom, Fit to Width, Fit to Height. | `EV-015`, `list_buttons.py` output | `[V]` |
| **Missing Field Validation (`?` flag)** | Exceptions | High-visibility warning badge `?` on required fields missing extracted values, blocking confirm. | `EV-016`, `01_missing_required_document_id.png` | `[V]` |
| **Error Counter Badges (Header)** | Exceptions | Action bar pill counter displaying active errors and warnings (e.g. `1 error / 0 warnings`). | `EV-016`, `01_missing_required_document_id.png` | `[V]` |
| **Inline Error Resolution** | Exceptions | Manual typing or canvas click immediately resolves error, decrements badge, and enables Confirm. | `EV-019`, `04_document_id_corrected_resolved.png` | `[V]` |
| **Document Postponement** | Exceptions | Action bar "Postpone" button parking documents requiring supplier clarification into Postponed tab. | `EV-015`, `list_buttons.py` output | `[V]` |
| **Document Rejection Modal** | Exceptions | Action bar "Reject" button allowing formal rejection of invalid, duplicate, or unprocessable bills. | `EV-015`, `list_buttons.py` output | `[V]` |
| **Queue Reassignment Flow** | Exceptions | "Move to another queue" modal allowing reclassification of misrouted documents without re-upload. | `EV-015`, `list_buttons.py` output | `[V]` |
| **Post-Confirmation Micro-Survey** | Quality / ML | Immediate feedback modal ("How satisfied are you with data extraction?") building RLHF training data. | `EV-018`, `03_confirm_blocked_or_modal.png` | `[V]` |
| **Line Items Extraction Grid** | Line Items | Hierarchical table extracting item description, quantity, unit price, tax rate, and line total. | `EV-020`, `03_us_invoice_line_items_grid.png` | `[V]` |
| **Keyboard Shortcuts Suite** | Productivity | Complete keyboard navigation system (Shift+Slash / `?`) for zero-mouse high-speed document review. | `EV-021`, `06_keyboard_shortcuts_sheet.png` | `[V]` |
| **Interactive Onboarding Tour** | Learnability | Step-by-step guided tour explaining document viewer, extraction fields, and confirmation workflow. | `EV-006`, `01_onboarding_review_tour.png` | `[V]` |
| **Cross-Queue Field Manager** | Governance | Administrative engine to standardize schemas and eliminate naming inconsistencies across queues. | `EV-029`, `05_settings_overview.png` | `[V]` |
| **Operational Analytics Dashboard** | Analytics | Executive/managerial dashboard tracking turnaround time, error rates, throughput, and reviewer metrics. | `EV-023`, `01_statistics_dashboard_full.png` | `[V]` |
| **Reviewer SLA & Late Tracking** | Analytics | Time-series tracking of "On time vs. late documents" measured against target turnaround deadlines. | `EV-023`, `01_statistics_dashboard_full.png` | `[V]` |
| **Automation Rules & AI Engines** | Automation | Queue-level automation configuration controlling confidence thresholds for straight-through processing. | `EV-024`, `02_automation_overview.png` | `[V]` |
| **Rossum Store App Catalog** | Integrations | Turnkey marketplace of certified enterprise connectors (SAP S/4HANA, Coupa, Master Data Hub). | `EV-027`, `03_extensions_rossum_store.png` | `[V]` |
| **Configuration Changelog** | Auditability | Historical audit log tracking every modification made to queue schemas, rules, and user roles. | `EV-030`, `05_settings_overview.png` | `[V]` |
| **Email Ingestion Inboxes** | Intake | Dedicated queue-specific email addresses for automated invoice ingestion from vendor emails. | `EV-022`, `05_settings_overview.png` | `[P]` |
| **2-Way & 3-Way PO Matching** | Matching | Automated line-item matching against ERP purchase orders and goods receipt notes via Master Data Hub. | `EV-027`, `06_store_catalog_grid.png` | `[P]` |
| **Custom Webhook Extensions** | Automation | Event-driven HTTP webhooks triggered on document state transitions (imported, confirmed, exported). | `EV-026`, `02_extensions_my_extensions.png` | `[V]` |
| **User Role Permissions (RBAC)** | Security | Granular role assignment (Admin, Manager, Annotator/Reviewer) controlling queue access and settings. | `EV-028`, `05_users_and_roles_settings.png` | `[V]` |
