# Autonomous AP Command Center (Zetwerk Edition) — Complete Build Prompt for Emergent

> **SYSTEM INSTRUCTION FOR EMERGENT**:
> You are building an enterprise-grade, production-ready **Autonomous Accounts Payable Command Center** from scratch. 
> This application is built for **Zetwerk Manufacturing Businesses Pvt Ltd** (₹15,913 Cr FY26 GMV, 6,979 suppliers, ~45,000 invoices/month, SAP S/4HANA ERP, Bengaluru AP operations).
>
> **Core Mandate**:
> Build a fully functional, highly interactive, production-shaped web application from scratch. 
> Do **NOT** create a static wireframe, toy prototype, or fake simulation.
> Every number, status, countdown, and audit log must be powered by a real in-memory state engine. 
> 
> **Zero Simulation Mandate**:
> - Never hardcode "Expected: AUTO_APPROVED" or predetermined outcome tags anywhere. The engine must evaluate each invoice live.
> - Never use fake `setTimeout` progress bars or fake client delays. Stage latencies must be computed dynamically.
> - The words `"mock"`, `"demo"`, `"sample"`, `"fixture"`, and `"dummy"` are strictly banned from all user-facing copy and HTML.

---

## 1. Enterprise Profile & Financial Domain Truth

### Operating Context: Zetwerk Manufacturing Businesses Pvt Ltd
* **Enterprise Profile**: High-growth precision manufacturing unicorn (aerospace, defense, infrastructure, consumer electronics).
* **Scale**: 6,979 third-party suppliers, 26 owned plants, 45,000 invoices/month.
* **AP Hub**: Centralized Shared Services AP Team in Bengaluru, Karnataka (GSTIN: `29AAACZ1234F1Z5`).
* **Connected Ingestion Mailbox**: `ap-inward@zetwerk.com` (Google Workspace OAuth 2.0).
* **Core ERP**: SAP S/4HANA (Company Code: `1000` — Zetwerk India, Chart of Accounts: `INT1`).
* **Approval Threshold**: Invoices or disbursements exceeding `₹5,00,000` require dual-control Controller review.

### Statutory & Regulatory Levers (The True Value Driver)
In Indian manufacturing, AP is not a data entry function—it is a high-stakes statutory compliance operation:
1. **MSMED Act 2006 (Sections 15 & 16)**:
   * **45-Day Payment Clock**: Mandatory payment within 45 days of goods acceptance for registered MSME suppliers.
   * **Penal Interest**: Section 16 mandates compounded monthly interest at **3× the RBI Bank Rate** for any late payment.
   * *UI Requirement*: Every invoice row and detail view must show a live statutory countdown (`due in 4 days`, `due in 33 days`, `overdue by 1 day — penal interest accruing`).
2. **Income Tax Act §43B(h)**:
   * Any outstanding payable to an MSME vendor not settled within 45 days is **disallowed as a business deduction** for corporate tax, creating direct working capital leakage.
   * *UI Requirement*: The Controller KPI strip must track total INR trapped in "MSME Critical Exposure ($\le$ 7 Days)".
3. **GST & TDS Compliance**:
   * **Section 194Q TDS**: 0.1% tax deducted at source on purchase value exceeding ₹50 Lakhs.
   * **GSTR-2B Matching**: Every supplier invoice must cross-reference active GSTIN registration and matching state codes.
4. **5-Way Manufacturing Reconciliation**:
   * Standard 2-way/3-way matching fails in custom manufacturing. Zetwerk requires **5-Way Matching**:
     `Purchase Order (PO) → Project Milestone → Goods Receipt Note (GRN) → Quality Inspection (QC) → Tax Invoice`.

---

## 2. The 10 Non-Negotiable System Invariants

If any of these 10 invariants is violated, the build is rejected:

1. **Blind Engine Invariant**: The UI and ingestion engine must NEVER know the decision before the pipeline executes. No predetermined answer badges.
2. **Deterministic Real Timings**: All stage latencies displayed (`Extraction: 12ms`, `Reconciliation: 18ms`, `Rules: 8ms`) must be dynamically computed and streamed. No artificial `setTimeout` loops.
3. **Banned Terminology**: Zero occurrences of `"mock"`, `"demo"`, `"sample"`, `"fixture"`, or `"dummy"` in any user-facing label, button, badge, or empty state.
4. **Inspectable Evidence Trail**: Every badge, delta calculation, or tax computation must be clickable to open its underlying evidence (PO line, GRN voucher, or QC defect log).
5. **Visible MSME Statutory Countdown**: The MSMED 45-day countdown is a first-class citizen displayed on every invoice row and in the KPI summary.
6. **State-Mutating Action Hub**: Actions (`Approve Full`, `Approve Undisputed Portion + Generate Debit Note`, `Hold for GRN/QC`, `Request Vendor Revision`, `Route to Quarantine`) must mutate backend state, update net payable, and record to the audit log.
7. **Append-Only Immutable Audit Log**: Every state transition captures `{ event_id, invoice_id, timestamp, actor, action, before_status, after_status, note, payload }`.
8. **Fail-Soft Document Quarantine**: Corrupted PDFs, unreadable scans, or non-invoice attachments never throw 500 errors. They route cleanly to `QUARANTINE` with human-readable triage reasons.
9. **Dual-Control Payment Gate**: Any invoice total or payment release exceeding `₹5,00,000` requires secondary controller sign-off.
10. **Full State Resilience**: Explicit loading, empty, and error states for all 6 core navigation views.

---

## 3. Recommended Technical Stack for Emergent

Build the application as a single self-contained project:

* **Frontend**: Next.js / React (or modern HTML5 + Tailwind CSS + Lucide Icons) with responsive, dense enterprise styling.
* **State Management**: Reactive in-memory state store with persistent local storage or SQLite backing to ensure all mutations survive browser reloads.
* **Streaming Protocol**: Server-Sent Events (SSE) or reactive event streams to stream live stage execution events with measured millisecond latencies.
* **Document Ingestion**: Multi-format ingestion handler supporting:
  * Direct drag-and-drop file upload (PDF and JSON).
  * Autonomous Gmail Ingestion trigger simulating the `ap-inward@zetwerk.com` inbound pipeline.
* **Visual Direction**: High-density dark canvas (zinc/slate background `bg-slate-950`, emerald brand accent `#059669`, amber for warnings, rose for rejections, tabular numerals `font-mono`, 8pt grid). All currency in Indian notation (`₹12,34,567.00`).

---

## 4. Information Architecture & Navigation Structure

The command center features a persistent top enterprise bar and a collapsible left navigation rail:

### Top Navigation Bar
* **Enterprise Identity**: `Zamp Pace — Zetwerk Autonomous AP Command Center` (Bengaluru Plant 1).
* **Live Ingestion Mailbox Pill**: `ap-inward@zetwerk.com (Google Workspace OAuth 2.0 · Live)`.
* **Statutory Compliance Badge**: `MSMED §15/16 Clock Active · Section 43B(h) Protection`.
* **Primary Header Actions**:
  * `[Sync Inward Mail]` (Triggers autonomous Gmail scan, ingests new invoices, updates counters).
  * `[Ingest Document]` (Opens file picker / drag-and-drop modal).

### Executive KPI Strip (Always Visible)
1. **Touchless Rate (%)**: Real % of invoices auto-approved without human intervention (Target: 85%).
2. **Open Exceptions**: Total count of pending exceptions + Total INR value trapped in dispute.
3. **MSME Critical Exposure ($\le$ 7 Days)**: Total INR at risk of breaching the statutory 45-day window under §43B(h).
4. **Duplicate Leakage Blocked**: Cumulative INR prevented from double-payment by the engine.
5. **Median Processing Latency**: Real-time computed millisecond processing speed per invoice.

### Left Navigation Views
1. 🚨 **Exceptions Queue (Default View)**: Priority matrix sorted by risk score:
   $$R = \frac{\text{Amount in INR}}{\max(1, \text{Days to MSME Deadline})}$$
2. 📥 **All Invoices (Inbox)**: Full inward invoice ledger with status filter tabs (`All`, `Exceptions`, `Auto-Approved`, `Rejected`, `Quarantine`).
3. ⚡ **Live Processing**: Real-time stage execution monitor streaming events with exact millisecond timings.
4. 🏢 **Supplier Master**: 6,979 vendor master directory with MSME Udyam registration, GSTIN, bank verification state, and exception rates.
5. 📋 **Compliance Audit Log**: Immutable append-only audit trail capturing all automated and human decisions.
6. 🔌 **Integrations & Mailbox**: Gmail connection card, SAP S/4HANA RFC status, and Quarantine Bin.

---

## 5. Core Screens & Feature Requirements

### Screen 1: Exceptions Queue (Default Landing Workspace)
* The operator opens this view to clear the daily backlog before statutory cutoffs.
* Each card/row displays:
  * Supplier Name + MSME Badge (`Micro`, `Small`, `Medium`).
  * Invoice Number, Date, and PO Reference.
  * Net Amount in INR (`₹4,72,000.00`).
  * **The Exact Discrepancy Reason**: (e.g., `Quantity Shortage: Billed 40 vs 38 received on GRN-8841. 2 units transit damaged`).
  * **Statutory Countdown Pill**:
    * Green: $>15$ days remaining.
    * Amber: $8-15$ days remaining.
    * Red (Urgent / Critical): $\le 7$ days remaining (`Due in 4 days — §43B(h) disallowance risk`).
  * `[Review & Resolve]` button that opens the 3-Pane Reconciliation Console.

### Screen 2: Three-Pane Reconciliation Console (Core Human-in-the-Loop Workspace)
Clicking any invoice opens a comprehensive full-screen 3-pane reconciliation workspace:

#### Pane 1 (Left - 30%): Document Canvas & Optical Inspection
* Renders the tax invoice document (or styled canvas representation).
* Extracted field ledger: Invoice Number, Supplier, GSTIN, Date, PO Reference, Bank Account & IFSC.
* Tax Calculation Breakdown: Goods Subtotal, CGST (9%), SGST (9%), IGST (18%), Grand Total.
* Extraction Confidence Meter: Optical extraction score (e.g., `98.4% Confidence`).

#### Pane 2 (Middle - 45%): 5-Way Reconciliation Matrix
* Line-by-line comparison table:
  `Line Item | Billed Qty/Rate | PO Qty/Rate | GRN Delivered | QC Status | Verdict`
* Highlights discrepancies clearly (e.g., billed 40 vs 38 received on GRN; rate billed ₹25 vs ₹22 contracted).
* **Financial Settlement Adjustments**:
  * Invoice Total Amount
  * Disputed Line Deductions / Debit Notes Applied
  * Section 194Q TDS (0.1%)
  * **Authorized Net Payable** (Dynamically recomputed).

#### Pane 3 (Right - 25%): Engine Gate Trace & Action Hub
* **Real Engine Gate Trace**:
  * Gate 1: SHA-256 Duplicate Check (`PASS` / `FAIL`)
  * Gate 2: GSTN Taxpayer Verification (`PASS` / `FAIL`)
  * Gate 3: 5-Way Milestone & Line Match (`PASS` / `FAIL`)
  * Gate 4: MSMED Statutory Timeline (`PASS` / `WARNING`)
  * Gate 5: Bank Account Validation (`PASS` / `FAIL`)
* **Associate Action Hub**:
  * `[Approve Undisputed Portion]`: Automatically generates a Debit Note for the shortage, updates net payable, writes to audit log, and resolves the exception.
  * `[Approve Full Payment]`: Allows manual override if authorized.
  * `[Hold - Awaiting GRN/QC]`: Transitions state to `HOLD` pending warehouse receiving update.
  * `[Request Vendor Revision]`: Opens a modal with a pre-filled email to the supplier specifying the exact line discrepancy.
  * `[Route to Quarantine]`: For corrupt or suspicious documents.
  * Immediate toast notification with a 5-second undo buffer on any state change.

### Screen 3: Autonomous Gmail Ingestion Hub
* Displays live connection card for `ap-inward@zetwerk.com`.
* Shows real sync counters: Mails scanned today, attachments ingested, quarantine count, last sync timestamp.
* Clicking `[Trigger Mail Sync Now]` scans the inbox and immediately ingests new attachments into the queue.
* Drag-and-drop zone allowing operators to upload sample invoice PDFs or JSON files, processing them through the exact same engine.

### Screen 4: Live Processing Engine Inspector
* Allows selecting any scenario or running custom uploads.
* Streams real stage events via Server-Sent Events (SSE):
  1. `Document Ingestion` (Digital stream classification)
  2. `Structured Extraction` (Pydantic schema validation)
  3. `ERP Cross-Reference` (Vendor master & open PO balance check)
  4. `AOP Policy & 5-Way Match` (Tolerance matching & statutory checks)
  5. `Autonomous ERP Posting` (SAP voucher generation)
* Displays real computed execution latencies (e.g. `2.4ms`, `1.8ms`, `38.2ms total`).

### Screen 5: Supplier Master Directory
* Master list of Zetwerk suppliers with:
  * Supplier Name & Legal Entity
  * GSTIN & State Code
  * MSME Classification (`Micro`, `Small`, `Medium`, `Non-MSME`) + Udyam Registration Number
  * Bank Account & Verification Status (HDFC, SBI, Canara, ICICI)
  * Payment Terms (`Net 45 (MSMED Statutory)`, `Milestone Terms`)
  * Historical Exception Rate (%)

### Screen 6: Compliance Audit Log
* Append-only immutable ledger.
* Columns: Event ID, Invoice ID, Timestamp, Actor (`Autonomous Agent` or `AP_Associate_BLR`), Action Taken, Before Status $\rightarrow$ After Status, Details, Payload.
* Filterable and exportable to CSV.

---

## 6. Pre-Seeded Dataset (7 Realistic Zetwerk Production Cases)

The application must be pre-populated with these 7 production manufacturing scenarios:

```json
[
  {
    "id": "INV-ZET-01",
    "invoice_number": "APT/26-27/0411",
    "supplier_name": "Apex Precision Tooling Pvt Ltd",
    "supplier_gstin": "29AAACA9921B1Z2",
    "is_msme": true,
    "msme_category": "MICRO",
    "msme_registration_no": "UDYAM-KR-03-0021981",
    "bank_verified": true,
    "bank_account_last4": "4402",
    "bank_name": "HDFC Bank Ltd",
    "invoice_date": "2026-10-18",
    "msme_due_date": "2026-12-02",
    "days_to_msme_deadline": 33,
    "po_reference": "PO-4501",
    "grn_reference": "GRN-9912",
    "qc_status": "QC_ACCEPTED_100",
    "goods_subtotal": 160000.00,
    "cgst": 0.0,
    "sgst": 0.0,
    "igst": 28800.00,
    "gross_amount": 188800.00,
    "net_payable": 188800.00,
    "debit_notes_applied": 0.0,
    "status": "AUTO_APPROVED",
    "status_reason": "3-Way Match Passed (PO-4501, GRN-9912, QC Accepted 100/100). MSMED §15 compliant.",
    "lines": [
      {
        "line_number": 1,
        "description": "CNC Machined Precision Flanges (En-8 Steel)",
        "hsn_sac": "8483",
        "billed_qty": 100.0,
        "billed_rate": 1600.00,
        "po_qty": 100.0,
        "po_rate": 1600.00,
        "grn_qty": 100.0,
        "qc_accepted_qty": 100.0,
        "verdict": "MATCH"
      }
    ]
  },
  {
    "id": "INV-ZET-02",
    "invoice_number": "BHF/26/1089",
    "supplier_name": "Bharath Heavy Fabricators",
    "supplier_gstin": "29AABCB3342C1Z4",
    "is_msme": true,
    "msme_category": "SMALL",
    "msme_registration_no": "UDYAM-KR-03-0084721",
    "bank_verified": true,
    "bank_account_last4": "1190",
    "bank_name": "State Bank of India",
    "invoice_date": "2026-09-19",
    "msme_due_date": "2026-11-03",
    "days_to_msme_deadline": 4,
    "po_reference": "PO-4502",
    "grn_reference": "GRN-8841",
    "qc_status": "QC_PARTIAL_38",
    "goods_subtotal": 400000.00,
    "cgst": 36000.00,
    "sgst": 36000.00,
    "igst": 0.0,
    "gross_amount": 472000.00,
    "net_payable": 472000.00,
    "debit_notes_applied": 0.0,
    "status": "EXCEPTION",
    "status_reason": "Quantity Shortage: Billed 40 structural brackets vs 38 received on GRN-8841. 2 units transit damaged.",
    "lines": [
      {
        "line_number": 1,
        "description": "Heavy Structural Support Brackets (Grade IS-2062)",
        "hsn_sac": "7308",
        "billed_qty": 40.0,
        "billed_rate": 10000.00,
        "po_qty": 40.0,
        "po_rate": 10000.00,
        "grn_qty": 38.0,
        "qc_accepted_qty": 38.0,
        "verdict": "QTY_SHORTAGE"
      }
    ]
  },
  {
    "id": "INV-ZET-03",
    "invoice_number": "DEP/MS-2/094",
    "supplier_name": "Deccan Electro-Plating Works",
    "supplier_gstin": "36AAACD5541D1Z8",
    "is_msme": true,
    "msme_category": "MICRO",
    "msme_registration_no": "UDYAM-TL-01-0019284",
    "bank_verified": true,
    "bank_account_last4": "8841",
    "bank_name": "Canara Bank",
    "invoice_date": "2026-10-24",
    "msme_due_date": "2026-12-08",
    "days_to_msme_deadline": 39,
    "po_reference": "PO-4503",
    "grn_reference": "MILESTONE-1",
    "qc_status": "N/A (SERVICE)",
    "goods_subtotal": 300000.00,
    "cgst": 0.0,
    "sgst": 0.0,
    "igst": 54000.00,
    "gross_amount": 354000.00,
    "net_payable": 354000.00,
    "debit_notes_applied": 0.0,
    "status": "EXCEPTION",
    "status_reason": "Duplicate Milestone Claim: Milestone 1 (30% Advance) was already settled on Voucher VCH-2026-0891.",
    "lines": [
      {
        "line_number": 1,
        "description": "Hard Chrome Plating Services - Milestone 1 (30% Mobilization)",
        "hsn_sac": "9988",
        "billed_qty": 1.0,
        "billed_rate": 300000.00,
        "po_qty": 1.0,
        "po_rate": 300000.00,
        "grn_qty": 1.0,
        "qc_accepted_qty": 1.0,
        "verdict": "DUPLICATE_MILESTONE"
      }
    ]
  },
  {
    "id": "INV-ZET-04",
    "invoice_number": "SBL/OCT/441",
    "supplier_name": "Sri Balaji Industrial Transport",
    "supplier_gstin": "29AABCS8823K1ZT",
    "is_msme": false,
    "bank_verified": true,
    "bank_account_last4": "5521",
    "bank_name": "Kotak Mahindra Bank",
    "invoice_date": "2026-10-08",
    "msme_due_date": "2026-11-22",
    "days_to_msme_deadline": 23,
    "po_reference": "PO-4504",
    "grn_reference": "LR-449102",
    "qc_status": "DELIVERED",
    "goods_subtotal": 75000.00,
    "cgst": 6750.00,
    "sgst": 6750.00,
    "igst": 0.0,
    "gross_amount": 88500.00,
    "net_payable": 88500.00,
    "debit_notes_applied": 0.0,
    "status": "EXCEPTION",
    "status_reason": "Rate Variance Exceeded: Billed freight @ ₹25/km vs contracted PO rate ₹22/km (+13.6% variance; limit ±1.0%).",
    "lines": [
      {
        "line_number": 1,
        "description": "Inter-facility Heavy Freight (Bengaluru Plant 1 to Hosur Yard)",
        "hsn_sac": "9965",
        "billed_qty": 3000.0,
        "billed_rate": 25.00,
        "po_qty": 3000.0,
        "po_rate": 22.00,
        "grn_qty": 3000.0,
        "qc_accepted_qty": 3000.0,
        "verdict": "PRICE_MISMATCH"
      }
    ]
  },
  {
    "id": "INV-ZET-05",
    "invoice_number": "DF/2026/8821",
    "supplier_name": "Delta Forgings India Ltd",
    "supplier_gstin": "27AAACD9182L1Z9",
    "is_msme": false,
    "bank_verified": true,
    "bank_account_last4": "3319",
    "bank_name": "Axis Bank Ltd",
    "invoice_date": "2026-10-15",
    "msme_due_date": "2026-11-29",
    "days_to_msme_deadline": 30,
    "po_reference": "PO-4091",
    "grn_reference": "GRN-7719",
    "qc_status": "QC_ACCEPTED",
    "goods_subtotal": 1200000.00,
    "cgst": 0.0,
    "sgst": 0.0,
    "igst": 216000.00,
    "gross_amount": 1416000.00,
    "net_payable": 0.0,
    "debit_notes_applied": 0.0,
    "status": "REJECTED",
    "status_reason": "Duplicate Submission Blocked: Matches settled voucher VCH-2026-0412 with identical IRN & amount.",
    "lines": [
      {
        "line_number": 1,
        "description": "Forged Transmission Shafts (Alloy 20MnCr5)",
        "hsn_sac": "8483",
        "billed_qty": 500.0,
        "billed_rate": 2400.00,
        "po_qty": 500.0,
        "po_rate": 2400.00,
        "grn_qty": 500.0,
        "qc_accepted_qty": 500.0,
        "verdict": "DUPLICATE_COLLISION"
      }
    ]
  },
  {
    "id": "INV-ZET-06",
    "invoice_number": "KC/26-27/5502",
    "supplier_name": "Kaveri Castings Pvt Ltd",
    "supplier_gstin": "29AAACK1102P1Z3",
    "is_msme": true,
    "msme_category": "MEDIUM",
    "msme_registration_no": "UDYAM-KR-03-0044129",
    "bank_verified": false,
    "bank_account_last4": "9011",
    "bank_name": "ICICI Bank Ltd (Unverified - Master has HDFC ...3319)",
    "invoice_date": "2026-10-26",
    "msme_due_date": "2026-12-10",
    "days_to_msme_deadline": 41,
    "po_reference": "PO-4505",
    "grn_reference": "GRN-9801",
    "qc_status": "QC_ACCEPTED_200",
    "goods_subtotal": 1100000.00,
    "cgst": 99000.00,
    "sgst": 99000.00,
    "igst": 0.0,
    "gross_amount": 1298000.00,
    "net_payable": 1298000.00,
    "debit_notes_applied": 0.0,
    "status": "EXCEPTION",
    "status_reason": "Dual Control & Bank Mismatch Alert: Bank account changed on invoice PDF (ICICI ...9011 vs Master HDFC ...3319) and amount >₹5,00,000.",
    "lines": [
      {
        "line_number": 1,
        "description": "High Precision Valve Castings (Ductile Iron GGG-40)",
        "hsn_sac": "8481",
        "billed_qty": 200.0,
        "billed_rate": 5500.00,
        "po_qty": 200.0,
        "po_rate": 5500.00,
        "grn_qty": 200.0,
        "qc_accepted_qty": 200.0,
        "verdict": "BANK_MISMATCH"
      }
    ]
  },
  {
    "id": "INV-ZET-07",
    "invoice_number": "CHL-BLR-0091",
    "supplier_name": "Unclassified Inbound Document",
    "supplier_gstin": "UNKNOWN",
    "is_msme": false,
    "bank_verified": false,
    "bank_account_last4": "----",
    "bank_name": "Unknown",
    "invoice_date": "2026-10-30",
    "msme_due_date": "2026-12-14",
    "days_to_msme_deadline": 45,
    "po_reference": "UNKNOWN",
    "grn_reference": "UNKNOWN",
    "qc_status": "UNKNOWN",
    "goods_subtotal": 0.0,
    "cgst": 0.0,
    "sgst": 0.0,
    "igst": 0.0,
    "gross_amount": 0.0,
    "net_payable": 0.0,
    "debit_notes_applied": 0.0,
    "status": "QUARANTINED",
    "status_reason": "Document Unclassifiable: No extractable text layer, missing vendor GSTIN, and illegible challan scan.",
    "lines": []
  }
]
```

---

## 7. State Machine & Action Logic

### Permitted Invoice Lifecycle States
`RECEIVED` $\rightarrow$ `PARSING` $\rightarrow$ `MATCHING` $\rightarrow$ `AUTO_APPROVED` | `EXCEPTION` | `REJECTED` | `QUARANTINED` $\rightarrow$ `ACTIONED` $\rightarrow$ `POSTED_ERP`

### Action Execution Rules:
1. **Approve Undisputed Portion (Case 2 Demonstration)**:
   * Net Payable is updated to `₹4,48,400.00`.
   * Debit Note `DN-2026-004` of `₹23,600.00` is recorded.
   * State transitions from `EXCEPTION` $\rightarrow$ `ACTIONED`.
   * An immutable audit log entry is created:
     `{ actor: "AP_Associate_BLR", action: "APPROVE_PARTIAL", note: "Undisputed portion approved. Debit note DN-2026-004 issued." }`.
   * The Open Exceptions count and MSME Critical Exposure in the KPI strip decrease immediately.
2. **Autonomous Gmail Sync**:
   * Clicking `[Sync Inward Mail]` scans `ap-inward@zetwerk.com`.
   * Ingests a new clean batch invoice from Apex Precision (`APT/26-27/0412`, ₹94,400.00).
   * Streams a processing notification and appends it to the inbox in real time.
3. **Document Ingestion (Upload)**:
   * Dropping a PDF or JSON invoice computes its hash, evaluates the 5 gates, and transitions it to the appropriate state.

---

## 8. Acceptance & Verification Criteria for Emergent

Before concluding the build, Emergent must verify that:
1. **Fresh Start**: The app builds cleanly from scratch with zero dependency on pre-existing local files.
2. **Zero Fake Text**: No occurrences of "mock", "demo", "sample", or "Expected: AUTO_APPROVED" in the DOM.
3. **Real Interactivity**: Clicking "Review & Resolve" opens the 3-pane reconciliation console for that exact invoice.
4. **State Persistence**: Resolving Case 2 (Bharath Heavy Fabricators) mutates state to `ACTIONED`, applies the debit note, updates KPIs, and persists through page reloads.
5. **MSME Countdown**: Case 2 clearly warns with a red/amber pill: `Due in 4 days (MSMED Statutory Deadline · §43B(h) Risk)`.
6. **Live Gmail Ingestion**: Clicking "Sync Inward Mail" adds a new invoice and updates the attachments ingested counter.
7. **Design Polish**: Clean, calm, dense enterprise aesthetics adhering to the dark slate palette and emerald accent.
