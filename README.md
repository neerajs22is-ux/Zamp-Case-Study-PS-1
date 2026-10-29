# Zamp Pace — Autonomous AP Digital Employee (PS-1)
### Case Study Submission: AI Solutions Analyst (Founder's Office)

[![Tests](https://img.shields.io/badge/tests-31%2F31%20passing-emerald.svg?style=flat-square)](./tests/)
[![Architecture](https://img.shields.io/badge/Architecture-Plan--Execute--Validate%20(PEV)-blue.svg?style=flat-square)](./specs/PS1_INVOICE_PROCESSING_SPEC.md)
[![Runtime](https://img.shields.io/badge/Runtime-Python%203.12%20%7C%20FastAPI-informational.svg?style=flat-square)](https://fastapi.tiangolo.com)
[![UI](https://img.shields.io/badge/UI-Live%20Run%20View%20%2B%20Dashboard%20(SSE)-purple.svg?style=flat-square)](http://127.0.0.1:8000)

> **Candidate:** Neeraj Shivkumar — Founder's Office & Product Analytics Lead  
> **Target Role:** AI Solutions Analyst — Founder's Office @ Zamp (Zamp.ai)  
> **Problem Statement:** PS-1 (Finance / AP — Invoice Processing from PDF to Decision)  
> **Submission Email:** `palak@zamp.ai`  

---

## 🌟 Executive Summary

Mid-size and enterprise companies process hundreds of vendor invoices monthly across emails, portals, and paper receipts. A tired accounts payable clerk on a Friday afternoon makes expensive mistakes: paying duplicate invoices, overlooking price increases, or approving bills beyond purchase order caps.

This project delivers an autonomous **Accounts Payable Digital Employee** running on Zamp's core philosophy—the **Agent Operating Procedure (AOP)** with a **Plan-Execute-Validate (PEV)** loop:
1. **Multi-Modal Document Understanding:** Ingests machine-readable PDFs, structured JSON, and noisy low-resolution mobile scans with field-level confidence scoring.
2. **Deterministic Mathematical Guardrails:** Completely eliminates LLM arithmetic hallucinations via Pydantic v2 invariants ($\left|\sum \text{lines} - \text{subtotal}\right| < 0.05$).
3. **Enterprise 2-Way Matching & Policy Tolerances:** Cross-references open ERP purchase orders, absorbs authorized tax and freight rounding variances ($\le \$20$ or $\le 1.5\%$), and flags rate spikes.
4. **Human-in-the-Loop (HITL) Exception Packaging:** Autonomously approves routine invoices, and packages exceptions with plain-English CFO explanations alongside 1-click pre-drafted vendor clarification emails.
5. **Real-Time Interactive UI (Deliverable 1):** Features a live 5-stage execution stepper powered by **Server-Sent Events (SSE)** and a comprehensive runs history dashboard.

---

## 🏛️ System Architecture

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

## 📊 Proven Scenarios: Happy Path + 4 Non-Trivial Edge Cases

All scenarios execute deterministically in **under 0.5 seconds** across 31 automated unit and integration tests:

| Scenario | Simulated Input | Pipeline Behavior | Decision Outcome | Audit & Business Impact |
| :--- | :--- | :--- | :---: | :--- |
| **HP-01** | Clean PDF from *Apex Cloud Inc.* for **\$5,425.00** matching PO #1042. | Lines match; tax variance is \$0.00; balance is \$10,000. | **`AUTO_APPROVED`** | Generated ERP Voucher `VCHR-XXXXXX` for automated disbursement. |
| **EC-01** | Second invoice from *Apex Cloud Inc.* for **\$6,500.00** on PO #1042. | System recalls earlier \$8,000 drawdown. Current bill creates a **\$4,500 deficit**. | **`FLAGGED_HITL_REVIEW`** | Flags budget overrun; pre-drafts PO amendment notice for Procurement Manager. |
| **EC-02** | Re-submission of *Apex Cloud Inc.* invoice #INV-2026-089 12 days later. | Hash/Invoice# collision detected against historical billing ledger. | **`REJECTED`** | Prevents \$5,425.00 duplicate payment; references prior batch ID. |
| **EC-03** | Freight invoice from *Global Logistics* billing **\$135/hr** vs PO rate **\$100/hr**. | Quantity matches (40 hrs), but unit price variance (+35%) exceeds 1.5% policy tolerance. | **`FLAGGED_HITL_REVIEW`** | Flags unit price spike; generates vendor rate addendum verification draft. |
| **EC-04** | Distorted scanned receipt from *Valley Hardware* with missing PO number. | Low OCR confidence (62%) and omitted PO reference. | **`FLAGGED_HITL_REVIEW`** | Flags low confidence; auto-generates 1-click vendor clarification email. |

---

## 🚀 Quickstart & Local Execution

### 1. Requirements
* Python 3.10+ (Tested on Python 3.12)
* Built with standard FastAPI, Pydantic v2, ReportLab, and PyPDF.

### 2. Run All Automated Verification Tests
```bash
python -m pytest tests/ -v
```
*(All 31 unit, integration, and hardening tests pass in ~3s, including the paced SSE stream test)*

### 3. Launch the Local Application & Dashboard
```bash
python run.py
```
* **Interactive UI Dashboard:** Open [http://127.0.0.1:8000](http://127.0.0.1:8000)
* **Swagger API Explorer:** Open [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
* **System Health:** Open [http://127.0.0.1:8000/api/health](http://127.0.0.1:8000/api/health)

---

## 🖥️ User Interface Overview (Deliverable 1)

* **Live Run View (Execution Inspector):**
  * Select any test scenario or upload a custom invoice PDF.
  * Real-time 5-stage stepper with animated spinners and millisecond timers powered by Server-Sent Events (SSE).
  * Extracted line-item table comparing billed vs contracted rates with variance percentages.
  * Decision badge with CFO-level reasoning and 1-click vendor email draft modal.
* **Runs History Dashboard:**
  * Executive metrics: Total Processed, Auto-Approval Rate, Exception Rate, Rejected Count.
  * Filterable audit table detailing all executed runs.
* **Mock ERP Master Inspector:**
  * Real-time view of ERP Vendor Master directory and active Purchase Orders showing authorized vs remaining balances.

---

## 🎥 Deliverable 2: 5-Minute Loom Video Storyboard

* **0:00 – 0:45 | Problem & FDE Framing:**  
  * Introduce the AP operational bottleneck: tired clerks making expensive mistakes on Friday afternoons.
  * Introduce Zamp’s AOP paradigm: moving from fragile chat copilots to bounded, autonomous digital employees.
* **0:45 – 2:00 | Live Happy Path Run (HP-01):**  
  * Select HP-01 on `http://127.0.0.1:8000`.
  * Trigger execution: watch the SSE stepper transition through all 5 stages in real time.
  * Highlight the `AUTO_APPROVED` state, ERP voucher creation, and zero financial variance.
* **2:00 – 3:30 | Live Edge Cases (The Real Judgment):**  
  * Run **Split PO Overrun (EC-01):** Show the system detecting cumulative over-billing and computing the exact $4,500 deficit.
  * Run **Duplicate Submission (EC-02):** Show immediate collision rejection with reference to prior batch records.
  * Run **Price Variance Spike (EC-03):** Show line-item highlighting for the +35% rate increase outside tolerance.
* **3:30 – 4:30 | Dashboard & Vendor Email Resolution:**  
  * Switch to the Runs History Dashboard tab to demonstrate operational KPIs and audit trails.
  * Open the 1-click **Auto-Draft Email Modal** showing how human-in-the-loop exception resolution is streamlined.
* **4:30 – 5:00 | Production Architecture & Summary:**  
  * Explain the zero-hallucination boundary: deterministic Python math + LLM extraction.
  * Emphasize how non-technical controllers can adjust AOP tolerance thresholds without writing code.

---

## 📂 Repository Directory Layout

```
.
├── engine/
│   ├── models.py            # Pydantic v2 schemas, arithmetic validators, DecisionAudit
│   ├── mock_erp.py          # In-memory ERP database (Vendors, PO balances, historical ledger)
│   ├── rules.py             # AOP Policy engine, tolerance math, vendor email generator
│   ├── pipeline.py          # 5-stage Plan-Execute-Validate orchestrator with ms latencies
│   ├── server.py            # FastAPI REST & Server-Sent Events (SSE) streaming server
│   └── templates/
│       └── index.html       # Single-file Tailwind/Lucide live dashboard & run inspector
├── fixtures/
│   ├── generate_test_data.py# Script synthesizing real PDF invoices & JSON payloads
│   └── data/                # Generated PDF and JSON test fixtures (HP-01, EC-01..EC-04)
├── tests/
│   ├── test_engine.py       # Pytest suite for core engine and 4 edge cases
│   ├── test_api.py          # Pytest suite for FastAPI REST & streaming endpoints
│   └── test_hardening.py    # PDF extraction, fail-soft, duplicate & tolerance regressions
├── specs/
│   └── PS1_INVOICE_PROCESSING_SPEC.md # Full blueprint and mathematical specification
├── research/
│   ├── company_dossier_zamp.md             # Initial Zamp background
│   ├── zamp_deep_research_primary_sources.md # Verified primary-source intelligence
│   └── zamp_institutional_due_diligence.md   # Institutional due diligence report
├── run.py                   # Single-command launcher (`python run.py --test`)
└── README.md                # Project documentation and submission guide
```

---
*Developed for Zamp AI Solutions Analyst Take-Home Case Study · October 2026*
