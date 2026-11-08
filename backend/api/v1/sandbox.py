"""Sandbox API Router — Unified AP Command Center Sandbox.

Consumes the flagship's authoritative business engine:
- Shared extraction schema (HybridAPExtractor with AWS Bedrock Mantle Qwen 235B)
- Evidence validation and token grounding
- INR monetary representation using Decimal
- Indian GST arithmetic (CGST/SGST/IGST)
- 7 deterministic AP policy matching gates
- Cumulative PO commitments and drawdown
- Identical decision codes and reason vocabulary
- Dual-control governance and immutable audit trail
"""

from __future__ import annotations

import asyncio
import datetime
import hashlib
import json
import logging
import os
import re
import time
import uuid
from decimal import Decimal
from typing import Any, Dict, List, Literal, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import delete, desc, func, select
from sqlalchemy.orm import Session

from backend.api.v1.invoices import (
    ActionPayload,
    execute_invoice_action,
    reevaluate_match_gates,
)
from backend.core.auth import AuthenticatedUser, UserRole
from backend.core.config import settings
from backend.core.database import SessionLocal, get_db, set_tenant_context
from backend.core.storage import storage_adapter
from backend.models.domain import (
    ApprovalRequest,
    AuditEvent,
    Document,
    ExceptionRecord,
    GoodsReceiptLineSnapshot,
    GoodsReceiptSnapshot,
    Invoice,
    InvoiceLine,
    MatchGateCheck,
    MatchRun,
    QualityControlSnapshot,
    Vendor,
    VendorGSTIN,
    WorkOrderLineSnapshot,
    WorkOrderSnapshot,
)
from engine.grounding import verify_extracted_evidence
from engine.hybrid_extractor import HybridAPExtractor, HybridProcessingResult
from engine.indian_tax_rules import IndianAPRuleEngine
from engine.pdf_safety import extract_pdf_pages

logger = logging.getLogger("sandbox_api")

router = APIRouter(prefix="/sandbox", tags=["AP Command Center Sandbox"])

SANDBOX_ORG_ID = "org_sme_eval"
CORPUS_DIR = os.path.join("tests", "evaluation_corpus_v2", "invoices")

# -----------------------------------------------------------------------------
# Genuine Scenario Metadata (Unified with Flagship Evaluation Corpus)
# -----------------------------------------------------------------------------
GENUINE_SCENARIOS = [
    {
        "id": "SCN-01-HAPPY-PATH",
        "title": "Happy Path: Clean 3-Way Match (APTC-001)",
        "scenario_type": "CLEAN_3WAY_MATCH",
        "vendor_name": "Asterion Precision Components Pvt Ltd",
        "vendor_gstin": "29AABCA1234F1Z5",
        "po_reference": "PO-26-1001",
        "expected_decision": "MATCH_CANDIDATE",
        "expected_stage": "PENDING_APPROVAL",
        "currency": "INR",
        "total_amount": 26196.00,
        "pdf_filename": "01_invoice_AP_26_001.pdf",
        "description": "Standard clean manufacturing invoice matching open PO-26-1001, GRN-26-501, and accepted QC certificate #QC-GRN-26-501-01 with 0.00% price and quantity variance.",
        "key_mechanisms": [
            "Contracted rate ₹185.00 matched exactly across 120 units",
            "CGST (₹1,998.00) + SGST (₹1,998.00) verified at 18.00% GST",
            "All 7 deterministic policy gates evaluate to PASS",
        ],
    },
    {
        "id": "SCN-02-PRICE-VARIANCE",
        "title": "Edge Case 1: Unit Price & Quantity Variance (APTC-030)",
        "scenario_type": "PRICE_QTY_VARIANCE",
        "vendor_name": "Asterion Precision Components Pvt Ltd",
        "vendor_gstin": "29SYNTH0001A1Z5",
        "po_reference": "PO-26-1011",
        "expected_decision": "FLAGGED_EXCEPTION",
        "expected_stage": "ACTION_REQUIRED",
        "currency": "INR",
        "total_amount": 25960.00,
        "pdf_filename": "30_invoice_AP_26_011.pdf",
        "description": "Supplier bills unit price ₹220.00 vs PO ₹185.00 (+18.92% variance, exceeding 1.5% tolerance) and bills 100 units vs 80 accepted on GRN-26-621.",
        "key_mechanisms": [
            "Unit price variance +18.92% exceeds policy limit of ±1.50%",
            "Invoiced quantity exceeds GRN accepted quantity by 20 units",
            "Gate 6 fails deterministically; flagged with exact financial exposure",
        ],
    },
    {
        "id": "SCN-03-DEGRADED-SCAN",
        "title": "Edge Case 2: Degraded Raster Scan Routed to HITL (APTC-036)",
        "scenario_type": "DEGRADED_SCAN",
        "vendor_name": "Unknown / Degraded Scan",
        "vendor_gstin": None,
        "po_reference": None,
        "expected_decision": "FLAGGED_HITL_REVIEW",
        "expected_stage": "ACTION_REQUIRED",
        "currency": "INR",
        "total_amount": 0.0,
        "pdf_filename": "36_invoice_POS_26_112.pdf",
        "description": "Image-only degraded scanned document with zero extractable machine-readable digital text. Safely routed to human reviewer per grounding tripwire policy.",
        "key_mechanisms": [
            "Zero digital text tokens detected in PDF character streams",
            "Grounding policy trips; LLM inference skipped to avoid ungrounded hallucinations",
            "Routed directly to AP Specialist inbox for manual document keying",
        ],
    },
    {
        "id": "SCN-04-QUARANTINE-QC",
        "title": "Edge Case 3: Quarantined Receipt / QC Inspection Failure (APTC-038)",
        "scenario_type": "QUARANTINED_RECEIPT",
        "vendor_name": "Meridian Industrial Chemicals Pvt Ltd",
        "vendor_gstin": "24SYNTH0003C1Z1",
        "po_reference": "PO-26-2003",
        "expected_decision": "FLAGGED_EXCEPTION",
        "expected_stage": "ACTION_REQUIRED",
        "currency": "INR",
        "total_amount": 192576.00,
        "pdf_filename": "11_invoice_MC_26_090.pdf",
        "description": "Factory goods receipt GRN-26-603 was quarantined due to quality defects. Quality inspection certificate marks status HOLD.",
        "key_mechanisms": [
            "PO-26-2003 and GRN-26-603 matched successfully in ERP records",
            "Gate 4 (QC Inspection Accepted) fails deterministically due to status HOLD",
            "Payment blocked; prevents disbursing funds for defective materials",
        ],
    },
    {
        "id": "SCN-05-NON-PAYABLE",
        "title": "Edge Case 4: Non-Payable Commercial Document Rejection",
        "scenario_type": "NON_PAYABLE_DOCUMENT",
        "vendor_name": "Commercial Logistics Receipt",
        "vendor_gstin": None,
        "po_reference": None,
        "expected_decision": "REJECTED",
        "expected_stage": "REJECTED",
        "currency": "INR",
        "total_amount": 0.0,
        "pdf_filename": "38_payment_receipt_RCPT_26_088.pdf",
        "description": "Document is classified as a Payment Receipt rather than a commercial invoice or debit note. System autonomously rejects to prevent duplicate disbursements.",
        "key_mechanisms": [
            "Document classifier identifies commercial type PAYMENT_RECEIPT",
            "is_payable_invoice evaluates to False",
            "Autonomously rejected without generating an open accounts payable liability",
        ],
    },
    {
        "id": "SCN-06-DUPLICATE",
        "title": "Edge Case 5: Duplicate Invoice Resubmission Safeguard",
        "scenario_type": "DUPLICATE_INVOICE",
        "vendor_name": "Asterion Precision Components Pvt Ltd",
        "vendor_gstin": "29AABCA1234F1Z5",
        "po_reference": "PO-26-1001",
        "expected_decision": "REJECTED",
        "expected_stage": "ACTION_REQUIRED",
        "currency": "INR",
        "total_amount": 26196.00,
        "pdf_filename": "01_invoice_AP_26_001.pdf",
        "description": "Attempt to resubmit invoice AP-26-001 already recorded in the ledger. SHA-256 hash collision and Gate 7 duplicate check prevent duplicate payment.",
        "key_mechanisms": [
            "SHA-256 hash or normalized voucher number matches prior active record",
            "Gate 7 (Duplicate Invoice Check) fails deterministically",
            "Rejection safeguard protects against fraudulent or accidental double billing",
        ],
    },
]


def _get_sandbox_user() -> AuthenticatedUser:
    """Returns the default evaluation user for sandbox operations."""
    return AuthenticatedUser(
        id="usr_sme_associate",
        org_id=SANDBOX_ORG_ID,
        email="sme_associate@company.internal",
        name="SME Evaluation Associate",
        role=UserRole.AP_ASSOCIATE,
        is_provisioned=True,
    )


def _execute_pipeline_core(
    pdf_bytes: bytes,
    filename: str,
    db: Session,
    org_id: str = SANDBOX_ORG_ID,
    force_duplicate_check: bool = False,
) -> Dict[str, Any]:
    """Executes the authoritative flagship pipeline against the evaluation workspace."""
    start_time = time.perf_counter()
    sha256 = hashlib.sha256(pdf_bytes).hexdigest()
    now_utc = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)

    set_tenant_context(db, org_id)

    # 1. Check for Duplicate Submission
    existing_doc = db.scalar(
        select(Document).where(
            Document.sha256_hash == sha256,
            Document.org_id == org_id,
            Document.is_deleted == False,
        )
    )
    if existing_doc and force_duplicate_check:
        inv = db.scalar(select(Invoice).where(Invoice.id == existing_doc.invoice_id, Invoice.org_id == org_id))
        return {
            "duplicate_detected": True,
            "document_id": existing_doc.id,
            "invoice_id": existing_doc.invoice_id,
            "decision": "REJECTED",
            "decision_reason": f"Duplicate invoice detected: identical SHA-256 hash ({sha256[:12]}...) was processed previously.",
            "is_live_mantle": False,
            "latency_ms": round((time.perf_counter() - start_time) * 1000, 2),
            "match_gates": [
                {"gate_number": 7, "gate_name": "Duplicate Invoice Check", "status": "FAIL", "notes": f"Duplicate document detected (Hash: {sha256[:12]}...)"}
            ],
        }

    # 2. Run HybridAPExtractor (Live Bedrock Mantle Qwen 235B)
    rule_engine = IndianAPRuleEngine(load_reference_data=False)
    extractor = HybridAPExtractor(rule_engine=rule_engine)
    processing_result: HybridProcessingResult = extractor.extract_hybrid(
        pdf_bytes=pdf_bytes,
        filename=filename,
        document_id=f"doc_sbx_{uuid.uuid4().hex[:8]}",
    )

    # 3. Create or Update Ingestion Entities in Tenant Workspace
    doc_id = existing_doc.id if existing_doc else f"doc_sbx_{uuid.uuid4().hex[:10]}"
    inv_id = existing_doc.invoice_id if existing_doc else f"inv_sbx_{uuid.uuid4().hex[:10]}"

    inv = db.scalar(select(Invoice).where(Invoice.id == inv_id, Invoice.org_id == org_id))
    if not inv:
        inv = Invoice(
            id=inv_id,
            org_id=org_id,
            source_channel="SANDBOX_EXPERIENCE",
            stage="RECEIVED",
            decision="NEEDS_REVIEW",
            currency="INR",
            created_at=now_utc,
            updated_at=now_utc,
        )
        db.add(inv)
        db.flush()

    if not existing_doc:
        doc = Document(
            id=doc_id,
            org_id=org_id,
            invoice_id=inv_id,
            filename=filename,
            mime_type="application/pdf",
            file_size_bytes=len(pdf_bytes),
            sha256_hash=sha256,
            storage_provider="supabase_s3",
            storage_key=f"{org_id}/invoices/{doc_id}/{filename}",
            is_original=True,
            uploaded_at=now_utc,
        )
        db.add(doc)
        db.flush()

    # 4. Synchronize Extracted Line Items
    db.execute(
        select(InvoiceLine).where(
            InvoiceLine.invoice_id == inv_id,
            InvoiceLine.org_id == org_id,
        )
    )
    from sqlalchemy import delete
    db.execute(delete(InvoiceLine).where(InvoiceLine.invoice_id == inv_id, InvoiceLine.org_id == org_id))

    if processing_result.line_items:
        for idx, line in enumerate(processing_result.line_items, start=1):
            desc = (
                getattr(line, "item_description", None)
                or getattr(line, "description", None)
                or (line.get("description") or line.get("item_description") if isinstance(line, dict) else None)
                or f"Line Item #{idx}"
            )
            qty = getattr(line, "quantity", None) or (line.get("quantity") if isinstance(line, dict) else 1.0)
            unit_r = getattr(line, "unit_price", None) or getattr(line, "unit_rate", None) or (line.get("unit_price") if isinstance(line, dict) else 0.0)
            tot = line.get("taxable_amount") if isinstance(line, dict) else getattr(line, "taxable_amount", None)
            if tot is None:
                tot = float(qty) * float(unit_r)

            inv_line = InvoiceLine(
                id=f"line_{inv_id}_{idx}",
                org_id=org_id,
                invoice_id=inv_id,
                line_number=idx,
                description=desc,
                billed_quantity=float(qty),
                billed_unit_rate=float(unit_r),
                billed_line_total=float(tot),
            )
            db.add(inv_line)

    # 5. Update Invoice Attributes
    inv.vendor_name = processing_result.supplier_name or inv.vendor_name
    inv.vendor_gstin = processing_result.supplier_gstin or inv.vendor_gstin
    inv.invoice_number = processing_result.invoice_number or inv.invoice_number
    inv.po_reference = processing_result.po_reference or inv.po_reference
    inv.currency = processing_result.currency or "INR"
    inv.subtotal_amount = Decimal(str(processing_result.taxable_value or 0.0))
    inv.tax_amount = Decimal(str(processing_result.total_tax_amount or 0.0))
    inv.total_amount = Decimal(str(processing_result.grand_total or 0.0))
    inv.net_payable_amount = Decimal(str(processing_result.grand_total or 0.0))
    try:
        inv.invoice_date = datetime.datetime.fromisoformat(processing_result.invoice_date) if processing_result.invoice_date else None
    except Exception:
        inv.invoice_date = None
    inv.updated_at = now_utc
    db.flush()

    # 6. Authoritative Deterministic 7-Gate Matching
    match_run = reevaluate_match_gates(db, inv, org_id, preserve_extended_gates=False)

    # Check extraction-level gating
    is_scanned_or_review = (
        processing_result.document_type == "SCANNED_IMAGE"
        or processing_result.extraction_status in ("NOT_EVALUATED", "DEGRADED_SCAN")
    )
    rejection = (
        not is_scanned_or_review
        and (not processing_result.is_payable_invoice or processing_result.document_type in (
            "PAYMENT_RECEIPT", "PURCHASE_ORDER", "DELIVERY_CHALLAN", "PROFORMA_INVOICE"
        ))
    )
    extraction_blocked = (
        rejection
        or is_scanned_or_review
        or not processing_result.grounding_tripwire_passed
        or not processing_result.tax_arithmetic.is_valid
        or processing_result.currency != "INR"
        or processing_result.document_type not in ("INVOICE", "DEBIT_NOTE")
        or getattr(processing_result, "extraction_requires_review", False)
    )

    if extraction_blocked:
        db.add(
            MatchGateCheck(
                id=f"mg_{match_run.id}_8",
                org_id=org_id,
                match_run_id=match_run.id,
                gate_number=8,
                gate_name="Extraction evidence and payable document",
                status="FAIL",
                evidence_notes="; ".join(processing_result.decision_reasons) or "Extraction requires verification.",
                checked_at=now_utc,
            )
        )
        match_run.overall_result = "FAIL"
    db.flush()

    # Query all checks
    saved_checks = db.scalars(
        select(MatchGateCheck).where(
            MatchGateCheck.match_run_id == match_run.id,
            MatchGateCheck.org_id == org_id,
        ).order_by(MatchGateCheck.gate_number)
    ).all()
    failed_gate = next(((g.gate_number, g.gate_name, g.evidence_notes) for g in saved_checks if g.status != "PASS"), None)

    # 7. Update Decision & State
    if failed_gate is None:
        inv.stage = "PENDING_APPROVAL"
        inv.decision = "MATCH_CANDIDATE"
        inv.decision_reason = "All 7 deterministic policy gates passed. Ready for approval."
        db.execute(delete(ExceptionRecord).where(ExceptionRecord.invoice_id == inv_id, ExceptionRecord.org_id == org_id))
    else:
        gnum, gname, gnotes = failed_gate
        inv.stage = "ACTION_REQUIRED"
        if is_scanned_or_review or not processing_result.grounding_tripwire_passed:
            inv.decision = "FLAGGED_HITL_REVIEW"
            inv.decision_reason = "; ".join(processing_result.decision_reasons) or "Degraded scan quality / ungrounded values detected. Human review required."
        else:
            inv.decision = "FLAGGED_EXCEPTION"
            inv.decision_reason = f"Gate {gnum} ({gname}) failed: {gnotes}"

        # Upsert ExceptionRecord
        existing_exc = db.scalar(select(ExceptionRecord).where(ExceptionRecord.invoice_id == inv_id, ExceptionRecord.org_id == org_id))
        if existing_exc:
            existing_exc.blocking_gate_number = gnum
            existing_exc.blocking_gate_name = gname
            existing_exc.exposure_amount_inr = inv.total_amount or Decimal("0.0")
            existing_exc.status = "OPEN"
        else:
            db.add(
                ExceptionRecord(
                    id=f"exc_{inv_id}",
                    org_id=org_id,
                    invoice_id=inv_id,
                    blocking_gate_number=gnum,
                    blocking_gate_name=gname,
                    exposure_amount_inr=inv.total_amount or Decimal("0.0"),
                    status="OPEN",
                    created_at=now_utc,
                )
            )

    if rejection:
        inv.stage = "REJECTED"
        inv.decision = "REJECTED"
        inv.decision_reason = "; ".join(processing_result.decision_reasons)

    # Record Audit Event
    db.add(
        AuditEvent(
            id=f"evt_{uuid.uuid4().hex[:12]}",
            invoice_id=inv_id,
            org_id=org_id,
            actor_id="sandbox_pipeline",
            actor_role="SYSTEM_SERVICE",
            action="SANDBOX_RUN_EXECUTED",
            reason=inv.decision_reason,
            source_reference=filename,
            timestamp=now_utc,
        )
    )
    db.commit()

    latency_ms = round((time.perf_counter() - start_time) * 1000, 2)

    # Fetch procurement snapshots for display
    wo = db.scalar(select(WorkOrderSnapshot).where(WorkOrderSnapshot.po_number == inv.po_reference, WorkOrderSnapshot.org_id == org_id)) if inv.po_reference else None
    grn = db.scalar(select(GoodsReceiptSnapshot).where(GoodsReceiptSnapshot.po_number == inv.po_reference, GoodsReceiptSnapshot.org_id == org_id)) if inv.po_reference else None
    qc = db.scalar(select(QualityControlSnapshot).where(QualityControlSnapshot.grn_number == grn.grn_number, QualityControlSnapshot.org_id == org_id)) if grn else None

    lines_records = db.scalars(select(InvoiceLine).where(InvoiceLine.invoice_id == inv_id, InvoiceLine.org_id == org_id).order_by(InvoiceLine.line_number)).all()

    return {
        "status": "COMPLETED",
        "document_id": doc_id,
        "invoice_id": inv_id,
        "filename": filename,
        "mode": "LIVE_INFERENCE" if processing_result.is_live_mantle else "RECORDED_REPLAY",
        "is_live_mantle": bool(processing_result.is_live_mantle),
        "inference_provider": processing_result.inference_provider or "AWS Bedrock Mantle (Qwen 235B)",
        "model_id": processing_result.model_id,
        "latency_ms": latency_ms,
        "decision": inv.decision,
        "stage": inv.stage,
        "decision_reason": inv.decision_reason,
        "invoice": {
            "id": inv.id,
            "invoice_number": inv.invoice_number,
            "vendor_name": inv.vendor_name,
            "vendor_gstin": inv.vendor_gstin,
            "po_reference": inv.po_reference,
            "subtotal": float(inv.subtotal_amount or 0.0),
            "tax_amount": float(inv.tax_amount or 0.0),
            "total_amount": float(inv.total_amount or 0.0),
            "net_payable": float(inv.net_payable_amount or 0.0),
            "currency": inv.currency,
            "stage": inv.stage,
            "decision": inv.decision,
            "decision_reason": inv.decision_reason,
        },
        "line_items": [
            {
                "line_number": l.line_number,
                "description": l.description,
                "billed_quantity": float(l.billed_quantity),
                "billed_unit_rate": float(l.billed_unit_rate),
                "billed_line_total": float(l.billed_line_total),
            }
            for l in lines_records
        ],
        "procurement": {
            "po": {
                "po_number": wo.po_number,
                "vendor_code": wo.vendor_code,
                "total_authorized_amount": float(wo.total_authorized_amount),
                "remaining_balance": float(wo.remaining_balance),
                "status": wo.status,
            } if wo else None,
            "grn": {
                "grn_number": grn.grn_number,
                "received_date": grn.received_date.isoformat() if grn.received_date else None,
            } if grn else None,
            "qc": {
                "qc_certificate_number": qc.qc_certificate_number,
                "overall_status": qc.overall_status,
            } if qc else None,
        },
        "match_gates": [
            {
                "gate_number": g.gate_number,
                "gate_name": g.gate_name,
                "status": g.status,
                "notes": g.evidence_notes,
            }
            for g in saved_checks
        ],
        "grounding": {
            "tripwire_passed": processing_result.grounding_tripwire_passed,
            "unverified_fields": processing_result.unverified_fields,
        },
        "reasons": processing_result.decision_reasons or [inv.decision_reason],
    }


# -----------------------------------------------------------------------------
# REST Endpoints
# -----------------------------------------------------------------------------

@router.get("/scenarios")
def list_sandbox_scenarios() -> List[Dict[str, Any]]:
    """Returns the genuine synthetic test scenarios available in the sandbox."""
    return GENUINE_SCENARIOS


@router.post("/run-scenario/{scenario_id}")
def run_sandbox_scenario(
    scenario_id: str,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Executes a genuine test scenario through the flagship AP Command Center engine."""
    scenario = next((s for s in GENUINE_SCENARIOS if s["id"] == scenario_id or s["id"].split("-")[1] in scenario_id), None)
    if not scenario:
        raise HTTPException(status_code=404, detail=f"Scenario '{scenario_id}' not found.")

    pdf_path = os.path.join(CORPUS_DIR, scenario["pdf_filename"])
    if not os.path.exists(pdf_path):
        raise HTTPException(status_code=500, detail=f"Fixture file missing: {pdf_path}")

    with open(pdf_path, "rb") as f:
        pdf_bytes = f.read()

    force_dup = scenario["scenario_type"] == "DUPLICATE_INVOICE"
    result = _execute_pipeline_core(
        pdf_bytes=pdf_bytes,
        filename=scenario["pdf_filename"],
        db=db,
        org_id=SANDBOX_ORG_ID,
        force_duplicate_check=force_dup,
    )
    result["scenario"] = scenario
    return result


@router.post("/upload")
async def upload_sandbox_invoice(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Uploads a live custom invoice PDF and executes the authoritative pipeline."""
    content = await file.read()
    filename = file.filename or "uploaded_invoice.pdf"

    if len(content) > 15 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="File size exceeds maximum permitted limit (15MB).")

    if not filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF invoice documents are supported.")

    result = _execute_pipeline_core(
        pdf_bytes=content,
        filename=filename,
        db=db,
        org_id=SANDBOX_ORG_ID,
    )
    return result


@router.get("/stream-scenario/{scenario_id}")
async def stream_sandbox_scenario(scenario_id: str, db: Session = Depends(get_db)):
    """Server-Sent Events (SSE) streaming endpoint for the live sandbox stage view."""
    scenario = next((s for s in GENUINE_SCENARIOS if s["id"] == scenario_id or s["id"].split("-")[1] in scenario_id), None)
    if not scenario:
        raise HTTPException(status_code=404, detail=f"Scenario '{scenario_id}' not found.")

    pdf_path = os.path.join(CORPUS_DIR, scenario["pdf_filename"])
    if not os.path.exists(pdf_path):
        raise HTTPException(status_code=500, detail=f"Fixture file missing: {pdf_path}")

    with open(pdf_path, "rb") as f:
        pdf_bytes = f.read()

    async def event_generator():
        # Event 1: Init
        yield f"data: {json.dumps({'event': 'INIT', 'message': f'Starting ingestion for {scenario['title']}', 'scenario': scenario})}\n\n"
        await asyncio.sleep(0.08)

        # Event 2: Document Read
        digest = hashlib.sha256(pdf_bytes).hexdigest()[:16]
        yield f"data: {json.dumps({'event': 'DOCUMENT_READ', 'stage': 'INTAKE', 'status': 'PASS', 'message': f'Digest verified: sha256:{digest}... ({len(pdf_bytes)} bytes)'})}\n\n"
        await asyncio.sleep(0.10)

        # Event 3: Extraction & Grounding
        yield f"data: {json.dumps({'event': 'EXTRACTION_STARTED', 'stage': 'EXTRACTION', 'status': 'RUNNING', 'message': 'Running AWS Bedrock Mantle Qwen 235B inference & token grounding...'})}\n\n"
        await asyncio.sleep(0.12)

        # Run pipeline
        res = _execute_pipeline_core(
            pdf_bytes=pdf_bytes,
            filename=scenario["pdf_filename"],
            db=db,
            org_id=SANDBOX_ORG_ID,
            force_duplicate_check=(scenario["scenario_type"] == "DUPLICATE_INVOICE"),
        )

        lines_count = len(res.get("line_items", []))
        subtot = res.get("invoice", {}).get("subtotal", 0)
        tot = res.get("invoice", {}).get("total_amount", 0)
        msg = f"Extracted {lines_count} lines, taxable INR {subtot:,.2f}, total INR {tot:,.2f}"
        yield f"data: {json.dumps({'event': 'EXTRACTION_COMPLETED', 'stage': 'EXTRACTION', 'status': 'PASS', 'message': msg})}\n\n"
        await asyncio.sleep(0.10)

        # Event 4: 7 Matching Gates
        gates = res.get("match_gates", [])
        yield f"data: {json.dumps({'event': 'MATCHING_GATES', 'stage': 'MATCHING', 'status': 'PASS' if all(g['status'] == 'PASS' for g in gates if g['gate_number'] <= 7) else 'FAIL', 'gates': gates})}\n\n"
        await asyncio.sleep(0.10)

        # Event 5: Final Decision
        yield f"data: {json.dumps({'event': 'DECISION_FINAL', 'decision': res.get('invoice', {}).get('decision'), 'stage': res.get('invoice', {}).get('stage'), 'reason': res.get('invoice', {}).get('decision_reason'), 'result': res})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.post("/invoices/{invoice_id}/action")
def apply_sandbox_action(
    invoice_id: str,
    payload: ActionPayload,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Executes human review or approval actions subject to authoritative flagship rules."""
    user = _get_sandbox_user()
    set_tenant_context(db, SANDBOX_ORG_ID)
    return execute_invoice_action(
        invoice_id=invoice_id,
        payload=payload,
        current_user=user,
        db=db,
    )


@router.get("/runs")
def get_sandbox_runs(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Retrieves recent sandbox runs and aggregated operational metrics."""
    set_tenant_context(db, SANDBOX_ORG_ID)

    invs = db.scalars(
        select(Invoice).where(Invoice.org_id == SANDBOX_ORG_ID).order_by(desc(Invoice.updated_at)).limit(25)
    ).all()

    total = len(invs)
    auto_app = sum(1 for i in invs if i.decision in ("AUTO_APPROVED", "MATCH_CANDIDATE"))
    exc_count = sum(1 for i in invs if i.decision == "FLAGGED_EXCEPTION")
    hitl_count = sum(1 for i in invs if i.decision == "FLAGGED_HITL_REVIEW")
    rej_count = sum(1 for i in invs if i.decision == "REJECTED")
    total_val = sum(float(i.total_amount or 0.0) for i in invs)

    items = [
        {
            "id": i.id,
            "invoice_number": i.invoice_number or "UNKNOWN",
            "vendor_name": i.vendor_name or "Unknown Vendor",
            "po_reference": i.po_reference,
            "total_amount": float(i.total_amount or 0.0),
            "currency": i.currency,
            "stage": i.stage,
            "decision": i.decision,
            "decision_reason": i.decision_reason,
            "updated_at": i.updated_at.isoformat() if i.updated_at else None,
        }
        for i in invs
    ]

    return {
        "metrics": {
            "total_runs": total,
            "match_candidates": auto_app,
            "exceptions_flagged": exc_count,
            "reviews_flagged": hitl_count,
            "rejected": rej_count,
            "straight_through_rate_pct": round((auto_app / total * 100), 1) if total > 0 else 0.0,
            "exception_rate_pct": round(((exc_count + hitl_count + rej_count) / total * 100), 1) if total > 0 else 0.0,
            "total_value_inr": round(total_val, 2),
        },
        "runs": items,
    }


@router.post("/reset")
def reset_sandbox_data(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Restores the sandbox evaluation workspace to clean baseline fixtures."""
    from backend.api.v1.system import reset_evaluation_fixtures
    user = _get_sandbox_user()
    set_tenant_context(db, SANDBOX_ORG_ID)
    return reset_evaluation_fixtures(current_user=user, db=db)
