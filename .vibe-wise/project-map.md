# Project Map — Zamp PS-1 (Digital AP Employee)

## Purpose
Build an end-to-end, runnable AI-powered Invoice Processing Digital Employee (PS-1) with an interactive Live Run View and Runs History Dashboard for the Zamp AI Solutions Analyst case study submission.

## Architecture: The Plan-Execute-Validate (PEV) Pipeline

```
[Incoming Invoice PDF / Scan]
              │
              ▼
    ┌────────────────────┐
    │ Stage 1: Ingestion │ ──► Digital text parsing OR Vision/OCR fallback
    └─────────┬──────────┘
              │
              ▼
    ┌────────────────────┐
    │ Stage 2: Extract   │ ──► Typed InvoiceSchema (Vendor, Tax ID, PO#, Line Items, Total)
    └─────────┬──────────┘
              │
              ▼
    ┌────────────────────┐
    │ Stage 3: Cross-Ref │ ──► ERP Mock Database (Verify Vendor Status & Fetch PO Records)
    └─────────┬──────────┘
              │
              ▼
    ┌────────────────────┐
    │ Stage 4: AOP Match │ ──► Duplicate Check | 2-Way/3-Way Line Match | Policy Variance Check
    └─────────┬──────────┘
              │
              ▼
    ┌────────────────────┐
    │ Stage 5: Decision  │ ──► AUTO_APPROVED | FLAGGED_HITL_REVIEW | REJECTED
    └─────────┬──────────┘
              │
              ▼
    ┌────────────────────┐
    │ UI & Audit Stream  │ ──► Live Stage Visualizer + Runs History + Vendor Draft Generator
    └────────────────────┘
```

## Components
1. **`engine/models.py`:** [Chosen] Strict Pydantic models for Extracted Invoice, PO Records, Matching Results, and Audit Trail.
2. **`engine/mock_erp.py`:** [Chosen] Mock ERP database with realistic vendor profiles, open PO lines, and historical invoices.
3. **`engine/rules.py`:** [Chosen] Agent Operating Procedure (AOP) rule engine:
   - Duplicate detection ($0$ tolerance for identical invoice number within 30 days).
   - Tolerance thresholds ($\le \$20$ or $\le 1.5\%$ variance auto-approved).
   - Split PO budget tracking (allocated vs remaining balance).
   - Unit price variance check.
4. **`engine/pipeline.py`:** [Chosen] Orchestrator running the 5-stage pipeline with timing and step-by-step audit logs.
5. **`fixtures/`:** [Chosen] Test PDF invoices generator producing:
   - Happy Path invoice.
   - Edge Case 1: Split PO exceeding balance.
   - Edge Case 2: Duplicate invoice submission.
   - Edge Case 3: Unit price variance (> tolerance).
   - Edge Case 4: Low-confidence scan missing PO reference.
6. **`web/`:** [Chosen] Next.js / Tailwind UI ported from Ask4i featuring Live Stage Run View, Runs History Dashboard, and Vendor Draft modal.

## Build and Deployment
- Backend: Python 3.10+ / FastAPI runner with SSE (Server-Sent Events) for real-time stage updates.
- Frontend: Next.js 16 / React 19 / Tailwind CSS v4 dashboard.
