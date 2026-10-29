# Company & Case Study Dossier: Zamp (Zamp.ai)

> **Document Type:** Primary-Source Strategic Intelligence Dossier  
> **Target Role:** AI Solutions Analyst / Associate — Founder's Office  
> **Prepared For:** Case Study Preparation & Evaluation  
> **Date:** October 2026  

---

## 1. Company Executive Summary

| Attribute | Details |
| :--- | :--- |
| **Entity Name** | Zamp (Zamp.ai / Zamp Finance) |
| **Flagship Platform** | **Pace** (Autonomous Digital Employees) |
| **Mission** | "Building a Humanity Catalyst" — Enabling enterprises and knowledge workers to move at the speed of thought by automating cognitive back-office toil. |
| **Founders** | **Amit Jain** (CEO) & **Raghav Saraf** (Co-Founder) |
| **Founders' Background** | Amit Jain: IIT Delhi, Stanford MBA; ex-Managing Director at Peak XV Partners (formerly Sequoia Capital India); ex-Head of Asia Pacific at Uber; ex-President at CarDekho. |
| **Capital Raised** | **\$22M+ Seed / Early Round** (2022–present) |
| **Key Backers** | **Peak XV Partners** (Sequoia India), **Valor Equity Partners**; Angel backers: **Dara Khosrowshahi** (CEO, Uber), **Tony Xu** (CEO, DoorDash), **Gokul Rajaram** (Board Member, DoorDash/Pinterest). |
| **Enterprise Traction** | 50+ global organizations, financial institutions, and tech giants (including public references/associations with DoorDash, Uber, and Stripe). |
| **Primary Hubs** | Bengaluru (India), Gurugram (India), San Francisco (US). |

---

## 2. Core Corporate Thesis & Product Philosophy

### 2.1 The "Humanity Catalyst" Thesis
In their founding manifesto (*"Building a Humanity Catalyst"*), Amit Jain and Raghav Saraf articulate the core reason Zamp exists:
* **The Cognitive Friction Problem:** Humanity’s greatest bottleneck is not a lack of scientific insight or raw compute; it is that millions of capable minds are locked in operational "human duct tape" roles—keying data across disconnected tools, manually checking invoice line items against purchase orders, verifying tax registrations, and resolving banking reconciliation mismatches.
* **Speed of Thought vs. Speed of Coordination:** Enterprises operate at the speed of human coordination latency (waiting 3 days for an AP clerk's review or an approval chain). Zamp builds autonomous workers so operations execute instantly at the "speed of thought."

### 2.2 Shift from "Copilots" to "Autonomous Digital Employees"
Unlike 2023-era "AI assistants" or chat wrappers:
* Zamp rejects passive chatbots that require constant human prompting.
* Instead, Zamp builds **"Digital Employees"** defined by an end-to-end **Job Description (JD)** and **Agent Operating Procedures (AOPs)**.
* A digital employee owns a process from input ingestion (email, portal, webhook) through system-of-record updates (NetSuite, SAP, Salesforce, Coupa, banking portals), with deterministic fallback and human-in-the-loop (HITL) exception handling.

---

## 3. Product Architecture & The Pace Platform

### 3.1 What is "Pace"?
**Pace** is Zamp's flagship agentic platform that coordinates digital employees across enterprise finance and operations.

### 3.2 Key Architectural Components

```
┌────────────────────────────────────────────────────────────────────────┐
│                        ZAMP DIGITAL EMPLOYEE                           │
├────────────────────────────────────────────────────────────────────────┤
│ 1. INGESTION & MULTI-MODAL UNDERSTANDING                               │
│    • PDF Invoices (machine-readable & scanned OCR)                      │
│    • Vendor registration forms & legal documentation (W-9, GSTIN, PAN) │
│    • Inbound email context & unstructured correspondence               │
├────────────────────────────────────────────────────────────────────────┤
│ 2. REASONING & AGENT OPERATING PROCEDURES (AOP)                        │
│    • Natural-language operational policy encoded into rules            │
│    • 2-Way and 3-Way matching logic (PO ↔ Invoice ↔ Receipt)          │
│    • Tolerance variance calculations (e.g., ±2% or $50 thresholds)     │
├────────────────────────────────────────────────────────────────────────┤
│ 3. ENTERPRISE INTEGRATION LAYER                                        │
│    • Direct API & UI-level connectors to ERPs (NetSuite, SAP, Workday) │
│    • Banking systems & treasury ledger updates                         │
├────────────────────────────────────────────────────────────────────────┤
│ 4. GOVERNANCE & HUMAN-IN-THE-LOOP (HITL)                               │
│    • Confidence score thresholding                                     │
│    • Exception routing (fraud flags, mismatched bank account names)    │
│    • Immutable audit trail of every reasoning step                     │
└────────────────────────────────────────────────────────────────────────┘
```

1. **Agent Operating Procedures (AOPs):** Plain-language operational rules provided by enterprise process owners that define standard operating protocols, acceptable tolerances, and regulatory rules.
2. **Context-Aware Extraction:** Combining multi-modal document extraction (OCR + Vision LLMs) with cross-referencing against internal ERP tables.
3. **Deterministic Guardrails:** High-value payments or ambiguous exceptions are not blindly hallucinated; they are surfaced to human reviewers with pre-filled reasoning.

---

## 4. The Role: AI Solutions Analyst (Founder's Office)

### 4.1 What the Role Actually Entails
This is a **forward-deployed engineering and business analyst hybrid** situated inside the Founder's Office:
* **Customer Front-Line:** Engaging enterprise process leaders (Controllers, VPs of Finance, Heads of Procurement) to untangle messy legacy processes.
* **Workflow Architecture:** Mapping unstructured operational steps into precise specifications.
* **Rapid Prototyping:** Utilizing Zamp's internal code-generation and automation engines to assemble, validate, and test runnable AI workflows.
* **End-to-End Delivery:** Deploying solutions into production, tracking business impact (ROI, hours saved, cycle time reduction), and closing feedback loops with product engineering.

### 4.2 Candidate Archetype Desired
* **Top-tier technical & problem-solving foundation:** (IITs / premier institutes preferred, 0–2 years experience).
* **High ownership & agency:** Capable of working in ambiguous startup environments without hand-holding.
* **Pragmatic execution:** Prefers working code and observable workflows over theoretical slide decks.

---

## 5. Case Study Candidate Guide Deconstruction

### 5.1 The Submission Mandate
* **Deadline:** 7-day turnaround.
* **Deliverable 1:** A **working, runnable automated process** (not a mockup or video prototype) built in any stack (Python, n8n, Next.js, FastAPI).
  - Must include a **Live Run View** (displaying stages as they execute in real time).
  - Must include a **Dashboard** (displaying run history, status, and outputs).
* **Deliverable 2:** A **5-minute Loom video** demonstrating:
  - The Happy Path running live.
  - At least one edge case running live.
  - Clear narration of decisions and architecture without slides.
* **Follow-up Round:** Live interactive demo in front of the interview panel where the candidate runs their process on live inputs and justifies every design choice.

### 5.2 Comparative Analysis of Problem Statements

| Problem Statement | Alignment with Zamp's Core IP | Real-World Complexity | Edge Case Richness | Strategic Verdict |
| :--- | :--- | :--- | :--- | :--- |
| **PS-1: Invoice Processing (PDF $\rightarrow$ Decision)** | **10 / 10**<br>(Exact match with Zamp AP Automation) | High data extraction variance; 2-way/3-way matching; tolerance thresholds. | • Split PO allocations<br>• Subtotal vs tax discrepancies<br>• Scanned low-res receipts<br>• Duplicate invoice detection | **Recommended #1 Choice.** Shows direct day-one capability to solve Zamp's primary customer problem. |
| **PS-2: Vendor Onboarding (Submission $\rightarrow$ Approval)** | **9.5 / 10**<br>(Exact match with Zamp Vendor Master Data) | Document verification; format validation; entity cross-checks; automated communication back to vendor. | • Entity name vs bank beneficiary mismatch<br>• Invalid tax ID checksums<br>• Expired compliance certificates<br>• Fraud detection flags | **Strong Alternative.** Clean state machine (Approved / Pending Info / Rejected). |
| **PS-3: Personalised Outreach (Prospect $\rightarrow$ Draft)** | **6.5 / 10**<br>(GTM / Sales auxiliary tool) | External web scraping / LinkedIn signals; high hallucination risk. | • Stale news triggers<br>• Ambiguous career changes<br>• Tone-deaf outreach | **Lower Priority.** Common AI wrapper stereotype; harder to demonstrate enterprise guardrails. |

---

## 6. Case Study Grading Criteria & Winning Signals

Based on Zamp's culture and the Candidate Guide's explicit guidance:

### What Guarantees a High Score
1. **Explainable AI Decisioning:** The output must not simply be `"Status: Approved"`. It must output an explicit **Audit Trail / Reasoning Breakdown** (e.g., `"Line items matched PO #1042 within 0.4% variance ($12.00 difference attributed to state sales tax rule; approved under $50 tolerance policy)"`).
2. **Deterministic UI State Machine:** A clean UI that visually tracks the pipeline stages (`Ingestion` $\rightarrow$ `Extraction` $\rightarrow$ `Cross-Reference` $\rightarrow$ `Rule Engine` $\rightarrow$ `Decision`).
3. **Thoughtful Non-Trivial Edge Cases:** Handling scenarios that simulate real vendor fraud or ERP discrepancies rather than trivial syntax errors.
4. **Clean Code & Local Execution:** A system that runs deterministically during a live screen-share without crashing.

---

## 7. Strategic Recommendations for Next Steps

1. **Commit to PS-1 (Invoice Processing)** or **PS-2 (Vendor Onboarding)** as the target problem statement.
2. **Draft the Process Map on Paper:**
   - Define exact inputs (sample PDFs/JSON).
   - Define step-by-step extraction schemas.
   - Define PO/Vendor dataset structure.
   - Define 3 high-signal edge cases.
3. **Design the Architecture:** Plan the backend pipeline (FastAPI/Python or n8n) and the frontend dashboard (React/Tailwind with a live execution stream).
