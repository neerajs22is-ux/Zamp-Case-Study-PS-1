# Zamp AI Solutions Associate — 5-Minute Demo Video Story Strategy
## Case Study PS-1: Accounts Payable Command Center

**Target Role:** AI Solutions Associate (Zamp, 2026)  
**Deliverable:** 5-Minute Demonstration Screen Recording (Loom / Screen Capture)  
**Application:** AP Command Center (`http://127.0.0.1:8000` / `http://localhost:5173`)  
**Target Duration:** 4 minutes 35 seconds to 4 minutes 45 seconds (Strictly ≤ 5:00)  
**Primary Evaluator:** AI Solutions Lead, Hiring Manager, and Non-Technical Enterprise Buyer (VP AP / Finance Director)

---

## 1. Evaluation Context & What "Winning" Looks Like

According to the official **Candidate Guide (`asa-case-study-candidate.pdf`)**, Zamp evaluates candidates on three specific pillars:
1. **Actual Working Process:** Does the system actually run end-to-end, accept real inputs, and produce structured outputs—or is it a fake mockup?
2. **Engineering & Product Judgment:** Why was AI used where it was used? Why were deterministic rules chosen for financial validation? Did the candidate build deliberate edge cases that demonstrate real business understanding?
3. **Clarity for a Non-Technical Buyer:** Can the candidate explain complex operational mechanics in language a Finance Director or CFO understands, without slipping into AI buzzword fluff or defensive technical jargon?

### Common Mistakes That Disqualify Submissions:
- **Slide Presentations:** The candidate guide explicitly forbids slides (`"No slides. The process runs in real time."`).
- **Generic AI Hype:** Talking vaguely about "agents reasoning autonomously" without showing exact verification gates.
- **Over-Promising / False Claims:** Claiming the system automatically wires bank funds or updates SAP General Ledgers when it actually serves as a pre-accounting review checkpoint.
- **Running Out of Time:** Exceeding 5:00 minutes or spending 2 minutes introducing oneself before showing the product.

---

## 2. Communication Principles (Alex Hormozi Framework Adapted for Enterprise AI)

To deliver maximum persuasion and clarity within 300 seconds, we apply proven communication principles adapted for B2B enterprise software:

1. **The Urgent Hook (First 20 Seconds):**
   - Start immediately with the expensive real-world problem: tired humans manually cross-referencing messy PDFs against spreadsheets on Friday afternoons, causing duplicate payments, rate overruns, and statutory penalty risks.
   - Zero personal biography, zero slides, zero fluff.
2. **The Mechanism in 30 Seconds:**
   - Frame the solution in plain English: *"An intelligent pre-payment verification checkpoint."*
   - Clear distinction of roles: Multimodal AI reads unstructured invoices; deterministic code validates strict business math and contracts; authorized humans make the final decisions.
3. **Evidence Before Claims (The Live Walkthrough):**
   - Don't talk about what the system *could* do. Show it executing live on screen.
   - Show the 4-stage procurement lineage: **Billed Claim $\to$ Purchase Order $\to$ Receiving GRN $\to$ Quality Inspection (QC)**.
4. **The High-Stakes Edge Case:**
   - Anyone can build a happy path that prints JSON. The true test of an AI Solutions Associate is handling edge cases.
   - We demonstrate an invoice with an unapproved price hike (+18.9% rate markup over contracted PO rate) and failing QC inspection.
   - We prove the **Failed-Gate Override Invariant (D-04)**: the system mathematically blocks approval and guides the user to raise a commercial Debit Note.
5. **Concrete Engineering Trade-Offs (Showcasing Solutions Architecture):**
   - Explicitly address the prompt's core question: *Why not let an LLM decide whether to approve?*
   - Answer: Generative AI is probabilistic; financial liabilities require deterministic guarantees. LLMs extract; deterministic policy engines validate; humans retain sovereign approval.
6. **The Confident Close:**
   - Summarize the business transformation: from manual data entry to exception-only triage, complete compliance protection (MSMED Act 45-day statutory rules), and an immutable forensic audit ledger.

---

## 3. Narrative Architecture & Timed Storyboard

| Time | Phase | Focus | Core Message |
| :---: | :---: | :---: | :--- |
| **0:00–0:25** (25s) | **The Hook & Problem** | Live Dashboard | Accounts Payable teams spend hours manually cross-checking messy vendor PDFs against spreadsheets. A tired human on Friday afternoon makes costly mistakes. |
| **0:25–0:55** (30s) | **The Solution Architecture** | Invoices Inbox | AP Command Center acts as an intelligent pre-payment checkpoint: Multimodal AI extracts data, a deterministic engine checks 7 strict policy gates, and humans retain review authority. |
| **0:55–2:20** (85s) | **Live Happy Path** | `AP-26-009` Workspace | Real invoice processing: 4-stage procurement lineage, line-item tax and rate reconciliation, 7-of-7 gates passing, consequence-aware internal approval. |
| **2:20–3:30** (70s) | **Live Edge Case** | `AP-26-011` Exception | Unapproved price variance (+18.9% markup) & failed QC. Show strict failed-gate override prevention and 1-click commercial Debit Note resolution. |
| **3:30–4:15** (45s) | **Engineering Judgment** | Policy & Audit Ledger | Why LLMs must never approve payments; AI extraction vs deterministic math; multi-tenant isolation and append-only regulatory audit triggers. |
| **4:15–4:40** (25s) | **Business Value & Close** | Executive KPI Header | 100% auditability, zero over-billing leakage, statutory MSMED penalty protection, and operational peace of mind. |

**Total Estimated Duration:** **4 minutes 35 seconds** (~620 spoken words at a comfortable conversational pace of 135 words/minute).

---

## 4. Scenario Selection & Technical Fact-Checking

### Happy Path: Invoice `AP-26-009` (`inv_d76401c096d0`)
- **Vendor:** Asterion Precision Components Pvt Ltd
- **Billed Amount:** ₹2,31,280.00 (Single approval role < ₹5,00,000 threshold)
- **Contracted PO:** `PO-26-2001` (80 CNC machined steel housings @ ₹2,450.00/unit)
- **Line Matching:** Billed 80 units @ ₹2,450.00 $\to$ 0.00% price variance, 0.00% quantity overrun.
- **QC Inspection:** 100% accepted in warehouse records.
- **7 Policy Gates:** All 7 pass (Vendor Identity, PO Authorization, GRN Receipt, QC Inspection, GST Arithmetic, Price/Qty Tolerance, Duplicate Check).
- **Action:** Click **"Approve Review"** $\to$ Consequence-aware modal confirms internal sign-off (with explicit warning that funds are not yet wired).

### Edge Case: Invoice `AP-26-011` (`inv_dbfcaf77ba9b`)
- **Vendor:** Asterion Precision Components Pvt Ltd
- **Billed Amount:** ₹25,960.00
- **Contracted PO:** `PO-26-1011` (Contracted rate: ₹2,450.00/unit)
- **Billed Rate:** ₹2,850.00/unit (+18.92% markup vs contracted rate; exceeds strict ±1.50% tolerance).
- **QC Status:** Quality inspection failed in receiving lot.
- **Failing Gates:** Gate 4 (QC Inspection) and Gate 6 (PO Price Tolerance) FAIL.
- **System Invariant:** **"Approval Blocked (2 Failing)"** button is permanently locked. The system refuses to allow a clerk or lead to override broken policy.
- **Action:** Click **"Raise Debit Note"** $\to$ Shows consequence breakdown and logs commercial deduction intent.

---

## 5. Strict Product Truth Boundaries (What NEVER to Say)

To ensure zero risk of exaggeration or factual disqualification:
1. **Never claim automatic payment or bank wire transfers:** Always state *"Internal review sign-off for external payment batching."*
2. **Never claim live SAP S/4HANA synchronization:** Always state *"Authoritative ERP procurement master data snapshots."*
3. **Never claim automated emails to vendors:** Clicking *"Ask Supplier to Correct"* or *"Raise Debit Note"* updates internal database records and audit trails; it does not dispatch automated external emails in this evaluation runtime.
4. **Never claim 100% autonomous approvals:** The application is an intelligent pre-accounting human-in-the-loop copilot; the human remains responsible for sign-off.
