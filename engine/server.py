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
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Literal, Optional
import uuid
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel

from engine.mock_erp import MockERPDatabase
from engine.models import DecisionAudit, DecisionState, DocumentType, HistoricalInvoiceRecord, Invoice
from engine.pipeline import InvoiceProcessingPipeline


# Project paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIXTURES_DIR = os.path.join(BASE_DIR, "fixtures", "data")

app = FastAPI(
    title="AI Solutions Associate — PS-1 Digital Employee API",
    description="Autonomous Invoice Processing & 2-Way/3-Way Matching Engine with AOP Tolerance Validation",
    version="1.0.0",
)

# Enable CORS for local Next.js / frontend access
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from backend.api.v1.sandbox import router as unified_sandbox_router
app.include_router(unified_sandbox_router, prefix="/api/v1")

@app.get("/", response_class=HTMLResponse)
@app.get("/legacy", response_class=HTMLResponse)
async def serve_legacy_dashboard():
    """Serve the original interactive PS-1 standalone rules sandbox demo."""
    template_path = os.path.join(os.path.dirname(__file__), "templates", "index.html")
    if not os.path.exists(template_path):
        raise HTTPException(status_code=404, detail="Legacy dashboard template not found")
    with open(template_path, "r", encoding="utf-8") as f:
        return f.read()


@app.get("/sandbox", response_class=HTMLResponse)
async def serve_sandbox_dashboard():
    """Serve the interactive unified AP Command Center Sandbox demo."""
    template_path = os.path.join(os.path.dirname(__file__), "templates", "sandbox.html")
    if not os.path.exists(template_path):
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
        "amount": 3250.00,
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

    pdf_path = os.path.join(FIXTURES_DIR, scenario.get("pdf_file", ""))
    json_path = os.path.join(FIXTURES_DIR, scenario["json_file"])
    erp_instance.reset()

    if os.path.exists(pdf_path):
        with open(pdf_path, "rb") as f:
            invoice_data = f.read()
        file_name = scenario["pdf_file"]
    elif os.path.exists(json_path):
        with open(json_path, "r", encoding="utf-8") as f:
            invoice_data = json.load(f)
        file_name = scenario["json_file"]
    else:
        raise HTTPException(status_code=500, detail=f"Fixture file missing: {json_path}")

    audit = pipeline.process(invoice_data, filename=file_name)
    return audit.model_dump()


class OperatorActionPayload(BaseModel):
    action: Literal["APPROVE", "REJECT", "RECORD_CLARIFICATION"]
    notes: Optional[str] = None
    override_reason: Optional[str] = None


@app.get("/api/stream-scenario/{scenario_id}")
async def stream_scenario_execution(scenario_id: str):
    """Server-Sent Events (SSE) streaming endpoint for live UI execution view."""
    scenario = next((s for s in SCENARIOS_META if s["id"] == scenario_id), None)
    if not scenario:
        raise HTTPException(status_code=404, detail=f"Scenario '{scenario_id}' not found")

    pdf_path = os.path.join(FIXTURES_DIR, scenario.get("pdf_file", ""))
    json_path = os.path.join(FIXTURES_DIR, scenario["json_file"])
    erp_instance.reset()

    if os.path.exists(pdf_path):
        with open(pdf_path, "rb") as f:
            invoice_data = f.read()
        file_name = scenario["pdf_file"]
    elif os.path.exists(json_path):
        with open(json_path, "r", encoding="utf-8") as f:
            invoice_data = json.load(f)
        file_name = scenario["json_file"]
    else:
        raise HTTPException(status_code=500, detail=f"Fixture file missing: {json_path}")

    async def event_generator():
        # Event 1: Pipeline Init
        yield f"data: {json.dumps({'event': 'INIT', 'message': f'Starting genuine ingestion for {scenario_id}', 'scenario': scenario})}\n\n"
        await asyncio.sleep(0.08)

        # Genuine incremental stage execution
        for event in pipeline.process_iter(invoice_data, filename=file_name):
            evt_type = event["event"]
            if evt_type == "DECISION_FINAL":
                audit = event["audit"]
                payload = {
                    "event": "DECISION_FINAL",
                    "decision": audit.decision.value,
                    "audit": audit.model_dump(mode="json"),
                }
            else:
                payload = {
                    "event": evt_type,
                    "stage": event["stage"],
                    "name": event["name"],
                    "status": event.get("status", "SUCCESS"),
                    "details": event.get("details", {}),
                }
            yield f"data: {json.dumps(payload)}\n\n"
            await asyncio.sleep(0.12)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.post("/api/invoices/{run_id}/action")
async def apply_operator_action(run_id: str, action_req: OperatorActionPayload):
    """Allow human AP operator to review, override, reject, or record clarification on an invoice."""
    audit = next((r for r in pipeline.run_history if r.run_id == run_id), None)
    if not audit:
        audit = next(
            (r for r in pipeline.run_history if r.invoice_number == run_id),
            None,
        )
    if not audit:
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found in audit history")

    if action_req.action == "APPROVE":
        if audit.decision in (DecisionState.AUTO_APPROVED, DecisionState.MANUALLY_APPROVED):
            # Idempotent response: already approved, avoid duplicate drawdown and ledger write
            return {
                "status": "SUCCESS",
                "run_id": audit.run_id,
                "decision": audit.decision.value,
                "audit": audit.model_dump(mode="json"),
                "message": "Invoice already approved; duplicate approval action ignored.",
            }
        if audit.decision == DecisionState.REJECTED:
            raise HTTPException(
                status_code=400,
                detail="Cannot override an invoice with decision REJECTED. Re-upload or resolve hard rejection grounds.",
            )

        # Enterprise Fraud Risk Gate (Section 7): Bank details mismatch override control
        if "bank_details_mismatch" in audit.discrepancy_details:
            notes_lower = (action_req.notes or action_req.override_reason or "").lower()
            verification_tokens = ["callback", "call-back", "telephone", "phone", "out-of-band", "voice verified", "verified via call"]
            if not any(token in notes_lower for token in verification_tokens):
                raise HTTPException(
                    status_code=403,
                    detail="Fraud Risk Gate: Overriding an invoice with bank details mismatch requires documented out-of-band telephone callback verification in operator notes.",
                )

        audit.decision = DecisionState.MANUALLY_APPROVED
        audit.erp_voucher_id = audit.erp_voucher_id or f"VCHR-OVR-{uuid.uuid4().hex[:6].upper()}"
        note = action_req.notes or action_req.override_reason or "Approved via human operator tolerance override"
        audit.reasons.append(f"[OPERATOR OVERRIDE]: {note}")
        audit.discrepancy_details["operator_override"] = {
            "action": "APPROVED",
            "notes": note,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        # Resolve real vendor_id from PO or vendor directory
        vendor_id = "VEND-UNKNOWN"
        if audit.po_number:
            po = erp_instance.get_po(audit.po_number)
            if po and po.vendor_id:
                vendor_id = po.vendor_id
        if vendor_id == "VEND-UNKNOWN" and audit.vendor_name:
            vend = erp_instance.get_vendor_by_name(audit.vendor_name)
            if vend and vend.vendor_id:
                vendor_id = vend.vendor_id

        # Clear in-flight hold since invoice is now approved
        if audit.invoice_number:
            erp_instance.clear_in_flight(vendor_id, audit.invoice_number)

        # Financial consistency: record PO drawdown if PO exists, and record in historical ledger
        if audit.po_number:
            erp_instance.record_po_drawdown(audit.po_number, audit.total_amount or 0.0)
        today = date.today()
        erp_instance.record_processed_invoice(
            HistoricalInvoiceRecord(
                invoice_id=f"PROC-OVR-{uuid.uuid4().hex[:6].upper()}",
                vendor_id=vendor_id,
                invoice_number=audit.invoice_number,
                amount=audit.total_amount or 0.0,
                invoice_date=today,
                processed_date=today,
                sha256_hash=f"OVERRIDE_HASH_{audit.run_id}",
                batch_id=f"BATCH-OVR-{today.isoformat()}",
                status=DecisionState.MANUALLY_APPROVED,
            )
        )
    elif action_req.action == "REJECT":
        if audit.decision in (DecisionState.AUTO_APPROVED, DecisionState.MANUALLY_APPROVED):
            raise HTTPException(
                status_code=400,
                detail="Cannot reject an invoice that has already been approved and recorded in the ERP general ledger. A manual adjustment or credit memo is required.",
            )
        audit.decision = DecisionState.REJECTED
        note = action_req.notes or "Rejected by human AP operator during exception review"
        audit.reasons.append(f"[OPERATOR REJECTED]: {note}")
        audit.discrepancy_details["operator_action"] = {
            "action": "REJECTED",
            "notes": note,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        # Clear in-flight hold on rejection
        vendor_id = "VEND-UNKNOWN"
        if audit.po_number:
            po = erp_instance.get_po(audit.po_number)
            if po and po.vendor_id:
                vendor_id = po.vendor_id
        if vendor_id == "VEND-UNKNOWN" and audit.vendor_name:
            vend = erp_instance.get_vendor_by_name(audit.vendor_name)
            if vend and vend.vendor_id:
                vendor_id = vend.vendor_id
        if audit.invoice_number:
            erp_instance.clear_in_flight(vendor_id, audit.invoice_number)
    elif action_req.action == "RECORD_CLARIFICATION":
        note = action_req.notes or "Supplier clarification requested via email"
        audit.reasons.append(f"[VENDOR CLARIFICATION]: {note}")
        audit.discrepancy_details["clarification_logged"] = {
            "notes": note,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    return {
        "status": "SUCCESS",
        "run_id": audit.run_id,
        "decision": audit.decision.value,
        "audit": audit.model_dump(mode="json"),
    }


@app.post("/api/upload-invoice")
async def upload_invoice(file: UploadFile = File(...)):
    """Upload custom invoice PDF or JSON and run through the pipeline."""
    content = await file.read()
    filename = file.filename or "uploaded_invoice"
    fn_lower = filename.lower()

    if len(content) > 15 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="File size exceeds maximum permitted limit (15MB).")

    if fn_lower.endswith(".json"):
        try:
            data = json.loads(content.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            raise HTTPException(status_code=400, detail="Uploaded file is not valid JSON")
        audit = pipeline.process(data, filename=filename)
    elif fn_lower.endswith(".pdf"):
        audit = pipeline.process(content, filename=filename)
    else:
        raise HTTPException(status_code=400, detail="Only .pdf or .json files are supported")

    return audit.model_dump()


@app.get("/api/runs")
async def get_run_history():
    """Retrieve full history of executed runs for the dashboard."""
    runs = [r.model_dump() for r in reversed(pipeline.run_history)]
    total = len(runs)
    auto_app = sum(1 for r in runs if r["decision"] == DecisionState.AUTO_APPROVED.value)
    manual_app = sum(1 for r in runs if r["decision"] == DecisionState.MANUALLY_APPROVED.value)
    total_approved = auto_app + manual_app
    flagged = sum(1 for r in runs if r["decision"] == DecisionState.FLAGGED_HITL_REVIEW.value)
    rejected = sum(1 for r in runs if r["decision"] == DecisionState.REJECTED.value)
    total_value = sum(float(r.get("total_amount") or 0.0) for r in runs)

    return {
        "metrics": {
            "total_runs": total,
            "auto_approved": auto_app,
            "manually_approved": manual_app,
            "total_approved": total_approved,
            "flagged_for_review": flagged,
            "rejected": rejected,
            "straight_through_rate_pct": round((auto_app / total * 100), 1) if total > 0 else 0.0,
            "auto_approval_rate_pct": round((auto_app / total * 100), 1) if total > 0 else 0.0,
            "total_approval_rate_pct": round((total_approved / total * 100), 1) if total > 0 else 0.0,
            "exception_rate_pct": round(((flagged + rejected) / total * 100), 1) if total > 0 else 0.0,
            "total_value_processed": round(total_value, 2),
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

@app.post("/api/reset-data")
async def reset_demo_data():
    """Restore mock ERP and pipeline run history to seeded demo baseline."""
    erp_instance.reset()
    pipeline.run_history.clear()
    return {"status": "success", "message": "ERP database and run history reset to factory demo baseline"}


@app.post("/api/run-sequence")
async def run_sequence_demo():
    """Execute the sequential split-PO drawdown demo (Item 19).
    
    1. First invoice (HP-01, $5,425) draws down PO-1042 authorized budget ($10,000 -> $4,575).
    2. Second invoice ($5,000) evaluates against the remaining $4,575 balance, flagging a budget overrun.
    """
    erp_instance.reset()
    hp_path = os.path.join(FIXTURES_DIR, "HP-01-Happy-Path.json")
    with open(hp_path, "r", encoding="utf-8") as f:
        inv1 = json.load(f)
    audit1 = pipeline.process(inv1, filename="HP-01-Happy-Path.json")
    po_balance_after_inv1 = erp_instance.get_po("PO-1042").remaining_balance

    inv2 = dict(inv1)
    inv2["invoice_number"] = "INV-2026-102-SEQ"
    inv2["invoice_date"] = "2026-10-30"
    inv2["total_amount"] = 5000.00
    inv2["subtotal"] = 5000.00
    inv2["tax_amount"] = 0.00
    inv2["line_items"] = [{
        "line_number": 1,
        "description": "Enterprise API Compute Tier 3",
        "quantity": 10.0,
        "unit_price": 500.0,
        "total": 5000.0,
    }]
    audit2 = pipeline.process(inv2, filename="INV-2026-102-SEQ.json")

    return {
        "status": "success",
        "step_1": {
            "invoice_number": audit1.invoice_number,
            "amount": inv1["total_amount"],
            "decision": audit1.decision.value,
            "po_number": "PO-1042",
            "authorized_budget": 10000.00,
            "remaining_balance_after_drawdown": po_balance_after_inv1,
        },
        "step_2": {
            "invoice_number": audit2.invoice_number,
            "amount": inv2["total_amount"],
            "decision": audit2.decision.value,
            "remaining_po_balance": po_balance_after_inv1,
            "deficit": round(inv2["total_amount"] - po_balance_after_inv1, 2),
            "reasons": audit2.reasons,
        }
    }
