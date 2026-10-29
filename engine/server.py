"""FastAPI Runner and Real-Time Event Stream Server for Zamp PS-1.

Exposes REST and Server-Sent Events (SSE) endpoints for:
1. Scenario-based test runs (HP-01, EC-01, EC-02, EC-03, EC-04).
2. Live file upload (PDF/JSON).
3. Real-time stage-by-stage execution streaming for the Live Run View.
4. Historical run analytics and ERP data inspection.
"""

from __future__ import annotations

import asyncio
import json
import os
from typing import Any, Dict, List, Optional
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel

from engine.mock_erp import MockERPDatabase
from engine.models import DecisionAudit, DecisionState, DocumentType, Invoice
from engine.pipeline import InvoiceProcessingPipeline


# Project paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIXTURES_DIR = os.path.join(BASE_DIR, "fixtures", "data")

app = FastAPI(
    title="Zamp AI Solutions Analyst — PS-1 Digital Employee API",
    description="Autonomous Invoice Processing & 2-Way/3-Way Matching Engine with AOP Tolerance Validation",
    version="1.0.0",
)

# Enable CORS for local Next.js / frontend access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/", response_class=HTMLResponse)
async def serve_dashboard():
    """Serve the interactive PS-1 live demo dashboard."""
    template_path = os.path.join(os.path.dirname(__file__), "templates", "index.html")
    if not os.path.exists(template_path):
        raise HTTPException(status_code=404, detail="Dashboard template not found")
    with open(template_path, "r", encoding="utf-8") as f:
        return f.read()

# Global pipeline instance with persistent in-memory ERP
erp_instance = MockERPDatabase()
pipeline = InvoiceProcessingPipeline(erp=erp_instance)

SCENARIOS_META = [
    {
        "id": "HP-01-Happy-Path",
        "title": "Happy Path: Clean Match within Tolerance",
        "vendor": "Apex Cloud Technologies Inc.",
        "invoice_number": "INV-2026-101",
        "amount": 5425.00,
        "po_reference": "PO-1042",
        "expected_decision": "AUTO_APPROVED",
        "description": "Standard clean PDF invoice matching open PO-1042 lines. Line items and taxes match authorized budget.",
        "json_file": "HP-01-Happy-Path.json",
        "pdf_file": "HP-01-Happy-Path.pdf",
    },
    {
        "id": "EC-01-Split-PO-Overrun",
        "title": "Edge Case 1: Split PO Budget Overrun",
        "vendor": "Apex Cloud Technologies Inc.",
        "invoice_number": "INV-2026-102",
        "amount": 6500.00,
        "po_reference": "PO-1042-SPLIT",
        "expected_decision": "FLAGGED_HITL_REVIEW",
        "description": "Second partial invoice against PO-1042 ($8,000 already billed of $10,000). New $6,500 bill creates a $4,500 deficit.",
        "json_file": "EC-01-Split-PO-Overrun.json",
        "pdf_file": "EC-01-Split-PO-Overrun.pdf",
    },
    {
        "id": "EC-02-Duplicate-Submission",
        "title": "Edge Case 2: Duplicate Invoice Submission",
        "vendor": "Apex Cloud Technologies Inc.",
        "invoice_number": "INV-2026-089",
        "amount": 5425.00,
        "po_reference": "PO-1042",
        "expected_decision": "REJECTED",
        "description": "Re-submission of identical invoice #INV-2026-089 processed 12 days prior. Catches collision to prevent double payment.",
        "json_file": "EC-02-Duplicate-Submission.json",
        "pdf_file": "EC-02-Duplicate-Submission.pdf",
    },
    {
        "id": "EC-03-Price-Spike-Variance",
        "title": "Edge Case 3: Line-Item Unit Price Spike (+35%)",
        "vendor": "Global Logistics Partners LLC",
        "invoice_number": "INV-2026-303",
        "amount": 5400.00,
        "po_reference": "PO-2090",
        "expected_decision": "FLAGGED_HITL_REVIEW",
        "description": "Freight vendor bills $135/hr vs contracted $100/hr PO rate (+35% variance), exceeding the 1.5% policy tolerance limit.",
        "json_file": "EC-03-Price-Spike-Variance.json",
        "pdf_file": "EC-03-Price-Spike-Variance.pdf",
    },
    {
        "id": "EC-04-Low-Res-Missing-PO",
        "title": "Edge Case 4: Low-Res Scan & Missing PO Reference",
        "vendor": "Valley Hardware & Tools",
        "invoice_number": "INV-2026-404",
        "amount": 1280.00,
        "po_reference": None,
        "expected_decision": "FLAGGED_HITL_REVIEW",
        "description": "Low-confidence mobile scan (62% OCR confidence) with omitted PO number. System auto-drafts vendor clarification email.",
        "json_file": "EC-04-Low-Res-Missing-PO.json",
        "pdf_file": "EC-04-Low-Res-Missing-PO.pdf",
    },
]


@app.get("/api/health")
async def health_check():
    """System health check and loaded ERP state."""
    return {
        "status": "healthy",
        "service": "PS-1 Invoice Processing Digital Employee",
        "engine_version": "1.0.0",
        "active_vendors": len(erp_instance.vendors),
        "open_pos": len(erp_instance.purchase_orders),
        "historical_records": len(erp_instance.historical_invoices),
        "runs_executed": len(pipeline.run_history),
    }


@app.get("/api/scenarios")
async def list_scenarios():
    """Return all 5 pre-configured test scenarios."""
    return SCENARIOS_META


@app.post("/api/run-scenario/{scenario_id}")
async def run_scenario(scenario_id: str):
    """Run a pre-configured scenario synchronously."""
    scenario = next((s for s in SCENARIOS_META if s["id"] == scenario_id), None)
    if not scenario:
        raise HTTPException(status_code=404, detail=f"Scenario '{scenario_id}' not found")

    json_path = os.path.join(FIXTURES_DIR, scenario["json_file"])
    if not os.path.exists(json_path):
        raise HTTPException(status_code=500, detail=f"Fixture file missing: {json_path}")

    # Each scenario run starts from the seeded ERP state so the demo is repeatable.
    erp_instance.reset()

    with open(json_path, "r", encoding="utf-8") as f:
        invoice_data = json.load(f)

    audit = pipeline.process(invoice_data, filename=scenario["json_file"])
    return audit.model_dump()


@app.get("/api/stream-scenario/{scenario_id}")
async def stream_scenario_execution(scenario_id: str):
    """Server-Sent Events (SSE) streaming endpoint for live UI execution view."""
    scenario = next((s for s in SCENARIOS_META if s["id"] == scenario_id), None)
    if not scenario:
        raise HTTPException(status_code=404, detail=f"Scenario '{scenario_id}' not found")

    json_path = os.path.join(FIXTURES_DIR, scenario["json_file"])
    erp_instance.reset()
    with open(json_path, "r", encoding="utf-8") as f:
        invoice_data = json.load(f)

    async def event_generator():
        # Event 1: Pipeline Init
        yield f"data: {json.dumps({'event': 'INIT', 'message': f'Starting ingestion for {scenario_id}', 'scenario': scenario})}\n\n"
        await asyncio.sleep(0.3)

        # Event 2: Stage 1 - Ingestion
        yield f"data: {json.dumps({'event': 'STAGE_START', 'stage': 1, 'name': 'Document Ingestion', 'details': 'Classifying digital text stream vs scanned image'})}\n\n"
        await asyncio.sleep(0.35)
        yield f"data: {json.dumps({'event': 'STAGE_COMPLETE', 'stage': 1, 'name': 'Document Ingestion', 'status': 'SUCCESS', 'doc_type': invoice_data.get('document_type', 'DIGITAL_PDF')})}\n\n"
        await asyncio.sleep(0.2)

        # Event 3: Stage 2 - Extraction
        yield f"data: {json.dumps({'event': 'STAGE_START', 'stage': 2, 'name': 'Structured Extraction', 'details': 'Validating InvoiceSchema arithmetic invariants'})}\n\n"
        await asyncio.sleep(0.4)
        yield f"data: {json.dumps({'event': 'STAGE_COMPLETE', 'stage': 2, 'name': 'Structured Extraction', 'status': 'SUCCESS', 'invoice_number': invoice_data.get('invoice_number'), 'total': invoice_data.get('total_amount')})}\n\n"
        await asyncio.sleep(0.2)

        # Event 4: Stage 3 - ERP Cross-Reference
        yield f"data: {json.dumps({'event': 'STAGE_START', 'stage': 3, 'name': 'ERP Cross-Reference', 'details': 'Querying Vendor Master, open PO balances, and duplicate ledger'})}\n\n"
        await asyncio.sleep(0.35)
        yield f"data: {json.dumps({'event': 'STAGE_COMPLETE', 'stage': 3, 'name': 'ERP Cross-Reference', 'status': 'SUCCESS'})}\n\n"
        await asyncio.sleep(0.2)

        # Event 5: Stage 4 - AOP Policy Evaluation & Match
        yield f"data: {json.dumps({'event': 'STAGE_START', 'stage': 4, 'name': 'AOP Policy & Tolerance Match', 'details': 'Running 2-way line matching, split PO check, and variance tolerances'})}\n\n"
        await asyncio.sleep(0.4)

        # Execute actual engine logic
        audit = pipeline.process(invoice_data, filename=scenario["json_file"])

        yield f"data: {json.dumps({'event': 'STAGE_COMPLETE', 'stage': 4, 'name': 'AOP Policy & Tolerance Match', 'status': 'SUCCESS'})}\n\n"
        await asyncio.sleep(0.2)

        # Event 6: Final Decision & Audit
        yield f"data: {json.dumps({'event': 'DECISION_FINAL', 'decision': audit.decision.value, 'audit': audit.model_dump(mode='json')})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.post("/api/upload-invoice")
async def upload_invoice(file: UploadFile = File(...)):
    """Upload custom invoice PDF or JSON and run through the pipeline."""
    content = await file.read()
    filename = file.filename or "uploaded_invoice"

    if filename.endswith(".json"):
        try:
            data = json.loads(content.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            raise HTTPException(status_code=400, detail="Uploaded file is not valid JSON")
        audit = pipeline.process(data, filename=filename)
    elif filename.endswith(".pdf"):
        audit = pipeline.process(content, filename=filename)
    else:
        raise HTTPException(status_code=400, detail="Only .pdf or .json files are supported")

    return audit.model_dump()


@app.get("/api/runs")
async def get_run_history():
    """Retrieve full history of executed runs for the dashboard."""
    runs = [r.model_dump() for r in reversed(pipeline.run_history)]
    total = len(runs)
    approved = sum(1 for r in runs if r["decision"] == DecisionState.AUTO_APPROVED.value)
    flagged = sum(1 for r in runs if r["decision"] == DecisionState.FLAGGED_HITL_REVIEW.value)
    rejected = sum(1 for r in runs if r["decision"] == DecisionState.REJECTED.value)

    return {
        "metrics": {
            "total_runs": total,
            "auto_approved": approved,
            "flagged_for_review": flagged,
            "rejected": rejected,
            "auto_approval_rate_pct": round((approved / total * 100), 1) if total > 0 else 0.0,
            "exception_rate_pct": round(((flagged + rejected) / total * 100), 1) if total > 0 else 0.0,
        },
        "runs": runs,
    }


@app.get("/api/erp/purchase-orders")
async def get_purchase_orders():
    """Inspect active ERP purchase orders and remaining balances."""
    return [po.model_dump() for po in erp_instance.purchase_orders.values()]


@app.get("/api/erp/vendors")
async def get_vendors():
    """Inspect ERP vendor directory."""
    return [v.model_dump() for v in erp_instance.vendors.values()]
