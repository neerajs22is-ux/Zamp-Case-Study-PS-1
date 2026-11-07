# Functional Specification & Process Blueprint: PS-1 Invoice Processing Digital Employee

> **Document Type:** End-to-End Operational Architecture & Process Blueprint  
> **Case Study:** Zamp AI Solutions Associate — Problem Statement 1 (Finance / AP)  
> **Status:** Final Candidate Specification  
> **Author:** Neeraj Shivkumar (AI Solutions Associate Candidate)  
> **Date:** October 2026  

---

## 1. Executive Problem Framing (AI Solutions Associate Perspective)

### 1.1 The Operational Bottleneck
Mid-size and enterprise companies receive hundreds of vendor invoices monthly across multiple channels (PDF email attachments, vendor portals, paper scans). Accounts Payable (AP) clerks spend hours manually:
1. Opening messy, heterogeneous invoice documents.
2. Manually keying line items into the ERP (NetSuite / SAP).
3. Cross-referencing purchase orders (POs) and goods receipts in spreadsheets.
4. Catching discrepancies (split orders, tax rounding differences, rate increases).

On a tired Friday afternoon, manual reviews fail. Over-billings slip through, duplicate invoices are paid twice, and vendor relationships sour due to approval latency.

### 1.2 The Digital Employee Solution
Rather than an ungrounded chat interface, we deploy an **autonomous AP Digital Employee** governed by a strict **Agent Operating Procedure (AOP)** with a **Plan-Execute-Validate (PEV)** loop:
* **Autonomously Approves** routine, clean invoices within pre-authorized financial tolerance limits.
* **Flags & Packages Exceptions** with crystal-clear mathematical reasoning, routing them to the right human approver with a pre-filled resolution draft.
* **Rejects Fraudulent or Duplicate Submissions** with zero manual intervention.

---

## 2. System Architecture & The 5-Stage Pipeline

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                        PS-1 INVOICE DIGITAL EMPLOYEE PIPELINE                          │
├────────────────────┬───────────────────────────────────────────────────────────────────┤
│ Stage 1: Ingestion │ Ingest PDF / Image ──► Auto-detect digital text vs scanned image  │
├────────────────────┼───────────────────────────────────────────────────────────────────┤
│ Stage 2: Extract   │ Multi-modal extraction ──► Typed InvoiceSchema + Field Confidence │
├────────────────────┼───────────────────────────────────────────────────────────────────┤
│ Stage 3: Cross-Ref │ Query Mock ERP ──► Check Vendor Status, Fetch Open PO & History   │
├────────────────────┼───────────────────────────────────────────────────────────────────┤
│ Stage 4: AOP Match │ Duplicate Check ──► 2-Way Line Match ──► Policy Tolerance Math    │
├────────────────────┼───────────────────────────────────────────────────────────────────┤
│ Stage 5: Decision  │ State Machine: AUTO_APPROVED | FLAGGED_HITL | REJECTED + Audit    │
└────────────────────┴───────────────────────────────────────────────────────────────────┘
```

---

## 3. Detailed Stage-by-Stage Operational Map

### Stage 1: Document Ingestion & Classification
* **Input:** Raw file upload (PDF or image).
* **Processing:**
  1. Inspect file header and metadata.
  2. Attempt digital text stream extraction.
  3. If text stream is empty or average word density is $< 5$ words/page, classify as **Scanned Image / Raster PDF**; otherwise classify as **Digital Machine-Readable PDF**.
* **Output:** Document Type (`DIGITAL_PDF` or `SCANNED_IMAGE`) and raw byte/text stream.

### Stage 2: Structured Entity Extraction
* **Input:** Document text / visual image.
* **Extraction Schema (Typed Contract):**
  ```json
  {
    "invoice_number": "INV-2026-089",
    "invoice_date": "2026-10-15",
    "due_date": "2026-11-14",
    "vendor": {
      "name": "Apex Cloud Technologies Inc.",
      "tax_id": "US-EIN-94-3829102",
      "remit_address": "100 California St, San Francisco, CA"
    },
    "po_reference": "PO-1042",
    "line_items": [
      {
        "line_number": 1,
        "description": "Enterprise API Compute Tier 3",
        "quantity": 10.0,
        "unit_price": 500.00,
        "total": 5000.00
      }
    ],
    "subtotal": 5000.00,
    "tax_amount": 425.00,
    "total_amount": 5425.00,
    "currency": "USD",
    "confidence_scores": {
      "overall": 0.98,
      "invoice_number": 0.99,
      "total_amount": 0.99,
      "po_reference": 0.95
    }
  }
  ```
* **Deterministic Sanity Check:**
  $$\left| \sum (\text{line\_item totals}) - \text{subtotal} \right| < 0.01$$
  $$\left| \text{subtotal} + \text{tax\_amount} - \text{total\_amount} \right| < 0.01$$
  *If internal arithmetic fails, extraction confidence is downgraded to trigger human verification.*

### Stage 3: System-of-Record Cross-Reference (ERP Lookup)
* **Input:** Extracted `vendor.name`, `vendor.tax_id`, and `po_reference`.
* **Actions:**
  1. **Vendor Verification:** Check if `vendor.name` matches an active, approved vendor in the Vendor Master Table.
  2. **PO Lookup:** Fetch open PO record matching `po_reference`.
     - Read: Total Authorized Amount, Total Previously Invoiced, Remaining Balance, and Authorized Line Items.
  3. **Duplicate Submission Check:** Search submitted invoices ledger for any match where:
     $$\text{vendor\_id} == \text{current} \quad \text{AND} \quad \text{invoice\_number} == \text{current}$$
     OR
     $$\text{sha256\_hash} == \text{current}$$
     OR
     $$\text{vendor\_id} == \text{current} \quad \text{AND} \quad \text{total\_amount} == \text{current} \quad \text{AND} \quad |\Delta \text{date}| \le \text{duplicate\_window\_days}$$
     *(Note: `duplicate_window_days` defaults to 0 / same-day window in `AOPPolicyConfig` to protect valid recurring monthly SaaS subscriptions with identical totals from false-positive rejections).*

### Stage 4: Agent Operating Procedure (AOP) Matching & Policy Rules
* **AOP Policy Rules Defined:**
  1. **Duplicate Policy:** Absolute $0$ tolerance on duplicate invoice number or identical content hash. Amount-only collisions require same-day submission (0-day window) so recurring monthly subscription billings with identical dollar amounts are not falsely rejected.
  2. **Vendor Policy:** Unapproved vendor or tax ID mismatch $\rightarrow$ Immediate Rejection.
  3. **Split PO Balance Policy:** Current invoice total must be $\le$ Remaining PO Balance. If $\text{Total} > \text{Remaining Balance}$, flag for PO Line Increase.
  4. **Line-Item 2-Way Match Policy:**
     - For each invoice line, find matching PO line by item code/description.
     - Quantity Check: Billed quantity $\le$ open PO line quantity.
     - Unit Price Check: Unit price must match contracted PO rate within **$\pm 1.5\%$ or $\le \$20$** (whichever is lower) for minor freight/fuel variances.
  5. **Tax & Rounding Tolerance:** Minor rounding variance $\le \$5.00$ auto-absorbed.

### Stage 5: Decision State Machine & Audit Packaging
The engine assigns one of three terminal states:

```
                          ┌──────────────────────────┐
                          │   AOP Decision Engine    │
                          └────────────┬─────────────┘
                                       │
        ┌──────────────────────────────┼──────────────────────────────┐
        ▼                              ▼                              ▼
 ┌───────────────┐              ┌───────────────┐              ┌───────────────┐
 │ AUTO_APPROVED │              │ FLAGGED_HITL  │              │   REJECTED    │
 └──────┬────────┘              └──────┬────────┘              └──────┬────────┘
        │                              │                              │
        ▼                              ▼                              ▼
  Posts voucher to               Routes to AP Lead              Sends rejection
  ERP for payment                with variance breakdown        notice to vendor
```

1. **`AUTO_APPROVED`**:
   - Vendor active, PO open, duplicate check passed, line items match, amounts within tolerance.
   - Generates ERP posting payload with transaction ID.
2. **`FLAGGED_HITL_REVIEW`**:
   - Non-fatal discrepancy (e.g., price variance outside tolerance, split PO budget exceeded, low scan confidence).
   - Packages an executive audit breakdown highlighting the exact discrepancy delta ($\Delta$) and generates a pre-filled draft email to the vendor or procurement manager.
3. **`REJECTED`**:
   - Fatal compliance violation (unapproved vendor, duplicate invoice number, fraudulent tax ID).

---

## 4. Test Scenarios: Happy Path & The 4 Non-Trivial Edge Cases

To prove deliberate engineering judgment in the 5-minute Loom demo and interview:

| Scenario ID | Test Name | Simulated Real-World Input | Pipeline Behavior | Expected Output & Decision |
| :--- | :--- | :--- | :--- | :--- |
| **HP-01** | **Happy Path** | Clean PDF from *Apex Cloud Inc.* for **\$5,425.00** matching PO #1042. | All lines match; tax variance is \$0.00; remaining balance is \$10,000. | **`AUTO_APPROVED`**<br>Reasoning: *"Matched PO-1042 (Line 1: 10 units @ \$500.00). Total \$5,425.00 within budget (\$10,000 balance). Ready for ERP voucher."* |
| **EC-01** | **Split PO Overrun** | Second invoice from *Apex Cloud Inc.* for **\$6,500.00** referencing PO #1042. | System recalls earlier \$5,425.00 payment. Remaining balance is only \$4,575.00. Current bill creates a **\$1,925.00 deficit**. | **`FLAGGED_HITL_REVIEW`**<br>Reasoning: *"PO-1042 budget exceeded by \$1,925.00 (\$11,925 cumulative vs \$10,000 cap). Routed to Procurement Manager for PO amendment."* |
| **EC-02** | **Duplicate Submission** | Exact re-submission of *Apex Cloud Inc.* invoice #INV-2026-089 12 days later. | Hash/Invoice# collision detected against submitted ledger. | **`REJECTED`**<br>Reasoning: *"Duplicate submission detected. Invoice #INV-2026-089 was previously processed on 2026-10-15 (Batch #B-9182). Flagged to prevent double payment."* |
| **EC-03** | **Price Spike Variance** | Invoice from *Global Logistics Partners* billing **\$135.00/hr** instead of PO rate **\$100.00/hr** (35% increase). | Quantity matches (40 hrs), but unit price variance (\$35/hr, \$1,400 delta) exceeds the \$20 / 1.5% tolerance threshold. | **`FLAGGED_HITL_REVIEW`**<br>Reasoning: *"Unit price variance (+35.0%) exceeds authorized policy tolerance ($\pm 1.5\%$). Contracted rate: \$100.00; Billed: \$135.00. Action: Verify rate change addendum."* |
| **EC-04** | **Low-Res Scan / Missing PO** | Distorted scanned receipt from *Valley Hardware* with smudged PO number and 62% OCR confidence. | Low confidence trigger (<75%); PO field missing; vendor is active. | **`FLAGGED_HITL_REVIEW`**<br>Reasoning: *"Low OCR confidence (62%) and missing PO reference. Extracted \$1,280.00. Pre-drafted clarification email generated for supplier."* |

---

## 5. User Interface Blueprint (Deliverable 1 Specification)

The UI must satisfy the candidate guide mandate: *"an intuitive, well-designed interface with a live run view (showing each stage as it executes) and a dashboard (showing history, status, and outputs across runs)."*

### 5.1 Screen 1: The Live Run View (Execution Inspector)
* **Top Bar:** Run status indicator, pipeline execution timer (e.g., `1.84s`), active document selector.
* **Pipeline Stepper Component (Visual Progression):**
  ```
  [1. Ingestion: Done (42ms)] ─► [2. Extraction: Done (420ms)] ─► [3. ERP Lookup: Done (110ms)] ─► [4. AOP Match: Done (85ms)] ─► [5. Decision: COMPLETE]
  ```
* **Split Inspection View:**
  - **Left Pane:** Document viewer / PDF preview with bounding box highlights or extracted JSON toggle.
  - **Right Pane:** Live Decision Card:
    - Status Badge: `AUTO_APPROVED` (Green), `FLAGGED_FOR_REVIEW` (Amber), `REJECTED` (Red).
    - CFO Narrative: Clear plain-English reasoning statement.
    - Tolerance Breakdown: Visual variance meter ($\Delta\%$, $\Delta\$$ vs policy threshold).
    - Action Toolbar: For flagged runs, includes a 1-click **"Send Clarification Email"** button displaying the auto-generated email draft.

### 5.2 Screen 2: Runs History Dashboard
* **Metrics Header:**
  - Total Processed (`5`) • Auto-Approval Rate (`20%`) • Exception Rate (`60%`) • Rejected (`20%`) • Total Value Processed (`$20,630.00`).
* **Runs Table:**
  - Columns: Timestamp, Invoice #, Vendor, Amount, PO Ref, Matching Result, Status, Action.
  - Clicking any row opens the full audit log modal showing the exact line-item comparison.

---

## 6. The 5-Minute Loom Video Script & Live Demo Strategy

### Minute-by-Minute Storyboard
* **0:00 – 0:45 | The Executive Problem & Framing:**  
  *"Hi, I'm Neeraj. At mid-size enterprises, AP teams waste hundreds of hours manually keying invoices and cross-checking spreadsheets. When a tired clerk works on a Friday afternoon, expensive errors happen. Here is an autonomous AP Digital Employee running an Agent Operating Procedure with a Plan-Execute-Validate loop."*
* **0:45 – 2:00 | The Happy Path Run Live:**  
  Ingest clean invoice `INV-2026-089`. Watch the live stepper transition across all 5 stages in ~1.8 seconds. Show the `AUTO_APPROVED` decision and explain why the tolerance policy passed.
* **2:00 – 3:30 | Running Edge Cases (The Real Judgment):**  
  - Run **Split PO Overrun**: Show the system catching the \$1,925 budget deficit and routing to procurement.
  - Run **Duplicate Submission**: Show instant rejection with prior batch reference.
  - Run **Price Spike**: Show line item highlighting the 35% unit cost jump.
* **3:30 – 4:30 | The Operational Dashboard & Audit Trail:**  
  Switch to the Dashboard view. Highlight cumulative processing metrics, exception rates, and the 1-click vendor email generator for unblocking AP bottlenecks.
* **4:30 – 5:00 | Solutions Wrap-Up & Production Readiness:**  
  Explain the zero-hallucination boundary (deterministic math + LLM extraction) and how AOP policies can be updated by non-technical controllers without code changes.

---
*End of Specification.*
