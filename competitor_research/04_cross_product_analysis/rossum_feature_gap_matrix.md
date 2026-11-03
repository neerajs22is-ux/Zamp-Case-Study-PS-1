# Rossum vs Zamp AP Command Center — Comprehensive Feature Gap Matrix

**Target Competitor:** Rossum Cloud Platform (`https://svit.rossum.app/`)  
**Our Product:** Zamp AP Command Center  
**Verification Standard:** REA Evidence Classification Standard (`[V]`, `[P]`, `[M]`, `[I]`, `[U]`)  
**Date:** November 03, 2026  

---

## 1. Evidence Classification Taxonomy

- `[V]` **Verified & Tested:** Directly inspected, triggered, tested, and captured via live runtime telemetry, DOM dumps, or network interception during this mission.
- `[P]` **Partially Implemented / Observed:** Visible in UI or API schema, but constrained by trial account limits, mock state, or partial frontend binding.
- `[M]` **Marketing / Documentation Claim:** Sourced from vendor documentation, help guides, or changelog; unverified at runtime.
- `[I]` **Inference:** Reasoned architectural or algorithmic deduction based on observed technical telemetry.
- `[U]` **Unknown / Inaccessible:** Hidden behind commercial paywalls, missing live ERP endpoints, or inaccessible server logic.

---

## 2. Master Cross-Product Feature Matrix

### 2.1 Document Intake & Channels

| Capability | Rossum Status | Rossum Observed Behavior | Zamp Status | Zamp Observed Behavior | Advantage / Gap |
|:---|:---:|:---|:---:|:---|:---|
| **Drag & Drop Ingestion Modal** | `[V]` | Batch file dropzone supporting multi-file selection and automatic queue routing (`EV-025`). | `[V]` | Dropzone and file picker on `/invoices` supporting single PDF uploads. | **Rossum Advantage:** Batch file drag and drop. |
| **Email Inbox Ingestion** | `[P]` | Dedicated queue-specific email addresses for inbound bill forwarding. | `[V]` | Production-grade Gmail OAuth 2.0 ingestion with encrypted credentials and Pub/Sub listener. | **Zamp Decisive Win:** Verified encrypted enterprise OAuth. |
| **Multi-Format Document Parsing** | `[V]` | Ingests PDF, PNG, JPG, TIFF, and scanned images natively. | `[P]` | Handles PDF documents primarily; raster formats converted server-side. | **Rossum Advantage:** Native TIFF and multi-image parsing. |
| **Intake Quotas & Usage Tracking** | `[V]` | Unlimited manual review during trial; document limits tracked in organization settings. | `[P]` | Storage bucket status tracked via health API; quotas not displayed in end-user UI. | **Rossum Advantage:** In-app usage tracking. |

### 2.2 OCR, Document Viewer & Canvas Interactivity

| Capability | Rossum Status | Rossum Observed Behavior | Zamp Status | Zamp Observed Behavior | Advantage / Gap |
|:---|:---:|:---|:---:|:---|:---|
| **Multi-Resolution Tiled Canvas** | `[V]` | Tiled image rendering engine with smooth pan and zoom at 60 FPS (`EV-005`). | `[V]` | Standard browser `<iframe>` preview embedding private Supabase pre-signed URL. | **Rossum Decisive Win:** Vector rendering performance. |
| **SVG Coordinate Bounding Boxes** | `[V]` | Overlays 51+ coordinate-mapped `<rect>` elements matching OCR tokens (`EV-008`–`010`). | `[P]` | Schema supports `bounding_box: null`; frontend canvas does not render boxes. | **Rossum Decisive Win:** High-fidelity source location. |
| **Bidirectional Field-Canvas Binding**| `[V]` | Clicking field pulses SVG box on canvas; clicking canvas text populates field (`EV-008`). | `[U]` | Not implemented. Fields and PDF iframe are non-interactive. | **Rossum Benchmark Win.** Industry standard for IDP review. |
| **Point-and-Click Canvas Capture** | `[V]` | Clicking or dragging over text on PDF canvas immediately extracts text into active field. | `[U]` | Not implemented. | **Rossum Decisive Win.** Instant correction of missing values. |
| **In-Viewer Text Search (Ctrl+F)** | `[V]` | "Find in document" search bar highlights matching OCR text blocks in yellow (`EV-012`). | `[U]` | Not implemented in-canvas; relies on browser native search. | **Rossum Advantage:** Search across complex contracts. |
| **Live Document Translation (Ctrl+T)**| `[V]` | Translates foreign-language invoices (e.g. French, German) into English on screen (`EV-015`). | `[U]` | Not implemented. | **Rossum Advantage:** High value for global trade. |
| **Zero-Trust Document Pre-Signed URLs**| `[I]` | Persistent session token authentication to document assets. | `[V]` | Private Supabase Storage with dynamic 300s pre-signed URLs and manual refresh button. | **Zamp Decisive Win:** Zero-trust document security. |
| **Cryptographic SHA-256 Proof** | `[I]` | Standard internal document IDs. | `[V]` | Computes SHA-256 binary hash on upload; exposes 1-click copy button on toolbar. | **Zamp Decisive Win:** Tamper-evident document proof. |

### 2.3 Extraction, Line Items & Schema Management

| Capability | Rossum Status | Rossum Observed Behavior | Zamp Status | Zamp Observed Behavior | Advantage / Gap |
|:---|:---:|:---|:---|:---:|:---|
| **Header Data Extraction** | `[V]` | Extracts Document ID, Order Number, Issue Date, Due Date, Vendor, Customer, Amounts. | `[V]` | Extracts Supplier Name, GSTIN, Invoice #, Date, PO Ref, Subtotal, Taxes, Total. | **Tie.** Both extract standard header fields accurately. |
| **Confidence Scoring & Flags** | `[V]` | Low confidence flagged with amber badges; missing required fields flagged with red `?`. | `[V]` | Confidence scores (0.00–1.00) mapped to "Verified" (≥0.90) or "Needs Review" (<0.90). | **Tie.** Both provide clear confidence indicators. |
| **Floating Edit Input (`editBoxInput`)**| `[V]` | Dynamic floating textarea mounting over active field with instant keyboard capture (`EV-017`). | `[U]` | Not implemented. Extracted fields are 100% read-only in UI. | **Rossum Decisive Win:** Ergonomic data entry. |
| **Line-Item Extraction Grid** | `[V]` | Multi-row table extracting item description, quantity, unit price, tax rate, total (`EV-020`). | `[V]` | Line-by-line table extracting line #, description, HSN/SAC, quantity, unit price, tax, total. | **Tie in Extraction.** Zamp extracts HSN/SAC codes in addition. |
| **Cross-Queue Field Manager** | `[V]` | Administrative engine allowing standardization of field schemas across all queues (`EV-029`). | `[U]` | Single fixed AP schema. | **Rossum Scope Advantage.** Useful for multi-schema platforms. |

### 2.4 Three-Way Matching & Procurement Verification

| Capability | Rossum Status | Rossum Observed Behavior | Zamp Status | Zamp Observed Behavior | Advantage / Gap |
|:---|:---:|:---|:---|:---:|:---|
| **Authoritative 3-Way Match Scope** | `[P]` | Requires external Rossum Store connectors (SAP/Coupa) or custom Python extensions. | `[V]` | Native 4-Node 3-Way Match: Invoice Claim vs PO Contract vs GRN Receipt vs QC Inspection. | **Zamp Decisive Win.** Core native capability in Zamp; external add-on in Rossum. |
| **Commercial Price & Qty Tolerances**| `[U]` | Not implemented in core review UI. | `[V]` | Deterministic 0.00% quantity tolerance, ±1.50% unit price tolerance, and ₹20 rounding tolerance. | **Zamp Decisive Win.** Enforces strict commercial pricing governance. |
| **Net Payable Settlement Waterfall** | `[I]` | Displays gross "Amount Due" field. | `[V]` | Dedicated Net Payable Waterfall isolating billed base, reconciled tax, and net payable. | **Zamp Advantage:** Clear authorizable payout. |
| **Goods Receipt (GRN) Verification** | `[U]` | Not tracked in core platform. | `[V]` | Cross-verifies GRN number, receipt date, and accepted units delivered to warehouse dock. | **Zamp Decisive Win.** Prevents paying for undelivered goods. |
| **Quality Inspection (QC) Verification**| `[U]`| Not tracked in core platform. | `[V]` | Cross-verifies QC inspection certificate number and QA verdict (Accepted / Defective). | **Zamp Decisive Win.** Prevents paying for rejected parts. |

### 2.5 Validation, Policy Gates & Exception Handling

| Capability | Rossum Status | Rossum Observed Behavior | Zamp Status | Zamp Observed Behavior | Advantage / Gap |
|:---|:---:|:---|:---|:---:|:---|
| **Header Error Pill Counter** | `[V]` | Action bar pill badge displaying active error count (e.g. `1 error / 0 warnings`) (`EV-016`). | `[V]` | Header verdict banner displaying failing check count (`Blocked: 2 Checks Failed`). | **Tie.** Both clearly communicate blocking errors in header. |
| **Deterministic Policy Gates** | `[U]` | Rules evaluate extraction syntax and regex patterns. | `[V]` | 7 Immutable Policy Gates grouped by 3 business questions with Pass/Fail notes. | **Zamp Decisive Win.** Evaluates business legality, not just OCR syntax. |
| **Actionable Next Steps for Errors** | `[U]` | None. User must visually resolve field error. | `[V]` | Every failed gate explicitly provides required operational next action. | **Zamp Decisive Win.** Guides non-technical finance users. |
| **Structured AP Triage Actions** | `[P]` | Confirm, Postpone, Reject, Move to Queue (`EV-015`). | `[V]` | 7 Consequence-Aware Actions: Hold, Ask Supplier to Correct, Debit Note, Escalate, Quarantine, Reject, Approve. | **Zamp Decisive Win.** Models real enterprise AP operational decisions. |
| **Mandatory Justification Reasons** | `[U]` | Free-form comments optional on confirm. | `[V]` | Mandatory justification reason with built-in professional reason templates. | **Zamp Decisive Win.** Strict audit compliance and accountability. |
| **Policy Override Barrier** | `[P]` | Users can confirm with warnings if schema allows. | `[V]` | Policy overrides strictly disabled; approvals locked until checks clear. | **Zamp Decisive Win.** Fraud barrier. |

### 2.6 Document Queues & Workload Management

| Capability | Rossum Status | Rossum Observed Behavior | Zamp Status | Zamp Observed Behavior | Advantage / Gap |
|:---|:---:|:---|:---|:---|:---|
| **Queue Partitioning Architecture** | `[V]` | 8 Specialized Queues segregated by schema (`Tax invoices US`, `Credit notes`, etc.). | `[V]` | Single Invoices Inbox with stage tabs (`All`, `Exceptions`, `Ready`, `Approved`, `Quarantine`). | **Trade-off.** Rossum for multi-schema IDP; Zamp for unified AP pipeline. |
| **Queue Metadata Density** | `[P]` | Default table hides supplier names and amounts (only Status, Name, Details) (`EV-001`). | `[V]` | Displays Invoice #, Supplier, GSTIN, PO Ref, Billed INR, Stage Badge, and MSMED Deadline. | **Zamp Decisive Win.** Instant financial scanning above fold. |
| **Multi-Condition Attribute Filtering**| `[V]` | Popover filter builder supporting field operators (`isAnyOf`, `equals`) (`EV-003`). | `[V]` | Search input (filters vendor, inv#, PO, GSTIN) + quick-filter tabs + stage dropdowns. | **Tie.** Rossum has deeper operators; Zamp has faster quick tabs. |
| **Continuous Queue Auto-Advance** | `[V]` | Confirming an invoice automatically loads the next document in queue (`queue_to_completion.mmd`). | `[U]` | Not implemented. Reviewing an invoice leaves user on detail page; requires manual return. | **Rossum Decisive Win.** Assembly-line review speed. |
| **Queue Reassignment Flow** | `[V]` | "Move to another queue" modal allowing reclassification of misrouted documents (`EV-015`). | `[U]` | Not implemented. | **Rossum Advantage.** Handles misclassified documents cleanly. |

### 2.7 Reviewer Productivity & Keyboard Navigation

| Capability | Rossum Status | Rossum Observed Behavior | Zamp Status | Zamp Observed Behavior | Advantage / Gap |
|:---|:---:|:---|:---|:---|:---|
| **Keyboard Shortcuts Cheat Sheet** | `[V]` | Press `?` (Shift+Slash) opens comprehensive cheat sheet (`EV-021`). | `[V]` | Press `?` (Shift+Slash) opens Keyboard Shortcuts modal. | **Tie.** Both follow standard conventions. |
| **Field Traversal with Canvas Sync**| `[V]` | `Tab` / `Shift+Tab` advances through fields; auto-scrolls canvas to active field. | `[U]` | Not implemented (fields are read-only). | **Rossum Decisive Win.** Zero-mouse data entry. |
| **Global Route Sequences** | `[U]` | Mouse-only sidebar clicks. | `[V]` | `g` then `t/i/a/u/s/c/r/m` navigation sequences to any page. | **Zamp Decisive Win.** Rapid app navigation. |
| **Document Triage Hotkeys** | `[U]` | Mouse-only toolbar buttons. | `[V]` | `a` (Approve), `h` (Hold), `c` (Correction), `s` (Quarantine), `r` (Reject). | **Zamp Decisive Win.** Fast AP decisioning. |
| **Confirm & Advance Hotkey** | `[V]` | `Ctrl+Enter` confirms document and auto-advances. | `[V]` | `Ctrl+Enter` confirms active modal dialog. | **Rossum Win for Queue Advance; Zamp Win for Modal Safety.** |

### 2.8 Governance, Approvals & Statutory Compliance

| Capability | Rossum Status | Rossum Observed Behavior | Zamp Status | Zamp Observed Behavior | Advantage / Gap |
|:---|:---:|:---|:---|:---|:---|
| **Statutory Dual Approval (₹5,00,000)**| `[U]` | Single operator confirms invoices of arbitrary value. | `[V]` | Mandatory ₹5,00,000 threshold requiring secondary Financial Controller sign-off. | **Zamp Decisive Win.** Fraud barrier. |
| **Separation of Duties (No Self-Approve)**| `[U]`| Not enforced. | `[V]` | Strictly blocks first approver from rendering secondary sign-off. | **Zamp Decisive Win.** Internal controls standard. |
| **Auditor Read-Only Oversight Role** | `[P]` | Read-only permissions exist, but lack dedicated auditor UI. | `[V]` | Dedicated Auditor role with read-only badges and disabled action controls. | **Zamp Advantage.** Compliance governance. |
| **MSMED Act 45-Day Payment Deadlines**| `[U]`| Standard due date only. | `[V]` | Calculates statutory MSMED §15 / §43B(h) 45-day payment deadlines for registered suppliers. | **Zamp Decisive Win.** Indian statutory tax compliance. |
| **Indian GST Breakdown Verification** | `[P]` | Generic tax extraction without statutory rate schedules. | `[V]` | Gate 5 validates CGST/SGST/IGST arithmetic against statutory schedules. | **Zamp Advantage.** Indian tax localization. |

### 2.9 Collaboration, Audit Trail & Operational Analytics

| Capability | Rossum Status | Rossum Observed Behavior | Zamp Status | Zamp Observed Behavior | Advantage / Gap |
|:---|:---:|:---|:---|:---|:---|
| **Document Collaboration Comments** | `[V]` | Slide-out `DetailDrawer` for reviewer chat, notes, and tagging (`EV-014`). | `[V]` | Mandatory justification notes logged on triage actions. | **Rossum Advantage for Team Chat; Zamp Advantage for Formal Audit.** |
| **Per-Invoice Audit Timeline** | `[P]` | Basic document info panel; detailed event logs buried in settings. | `[V]` | Embedded Tab 4 (`Audit Trail`) displaying chronological event ledger on every invoice. | **Zamp Decisive Win.** Complete provenance at fingertips. |
| **Reviewer Velocity Analytics** | `[V]` | Tracks turnaround time in seconds, reviewer corrections per doc, and SLA compliance (`EV-023`). | `[U]` | Not tracked at individual reviewer level. | **Rossum Decisive Win.** Operator performance tracking. |
| **Financial Exposure & Risk Analytics**| `[U]`| Not tracked. | `[V]` | Blocked INR value in open exceptions (₹25,960), high-value dual-approval queue. | **Zamp Decisive Win.** Financial risk visibility. |
| **Subsystem Health Transparency** | `[U]` | Opaque. Subsystems surface only upon failure. | `[V]` | Live `/api/v1/health` endpoint and dashboard checklist verifying DB, storage, IdP, Gmail, ERP. | **Zamp Decisive Win.** Operational transparency. |
