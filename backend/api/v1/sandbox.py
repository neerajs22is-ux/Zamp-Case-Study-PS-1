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

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Query, Security, UploadFile, status
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import delete, desc, func, select
from sqlalchemy.orm import Session

from backend.api.v1.invoices import (
    ActionPayload,
    execute_invoice_action,
    reevaluate_match_gates,
)
from backend.core.auth import (
    AuthenticatedUser,
    UserRole,
    get_current_user,
    require_active_membership,
    require_role,
    security_bearer,
    verify_token_claims,
    resolve_server_side_membership,
)
from backend.core.config import AppEnv, settings
from backend.core.database import SessionLocal, get_db, set_tenant_context
from backend.core.pipeline import (
    claim_ingestion_job,
    execute_document_pipeline,
    process_document_pipeline_background,
)
from backend.core.processing_events import append_checkpoint, lease_now, processing_snapshot
from backend.core.storage import build_tenant_storage_path, storage_adapter
from backend.models.domain import (
    ApprovalRequest,
    AuditEvent,
    Document,
    ExceptionRecord,
    ExtractedField,
    ExtractionRun,
    GoodsReceiptLineSnapshot,
    GoodsReceiptSnapshot,
    IngestionJob,
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
from engine.pdf_safety import InvalidPDF, extract_pdf_pages

logger = logging.getLogger("sandbox_api")

router = APIRouter(prefix="/sandbox", tags=["AP Command Center Sandbox"])

SANDBOX_ORG_ID = "org_sme_eval"

# Reliable application-relative fixture paths (works in local repo and containerized runtime)
APP_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
DEMO_FIXTURES_DIR = os.path.join(APP_ROOT, "engine", "demo_fixtures")
FALLBACK_CORPUS_DIR = os.path.join(APP_ROOT, "tests", "evaluation_corpus_v2", "invoices")
CORPUS_DIR = DEMO_FIXTURES_DIR if os.path.exists(DEMO_FIXTURES_DIR) else FALLBACK_CORPUS_DIR


def get_scenario_pdf_path(filename: str) -> str:
    """Resolves scenario fixture path reliably across local repo and production Docker container."""
    p_demo = os.path.join(DEMO_FIXTURES_DIR, filename)
    if os.path.exists(p_demo):
        return p_demo
    p_fallback = os.path.join(FALLBACK_CORPUS_DIR, filename)
    if os.path.exists(p_fallback):
        return p_fallback
    rel_demo = os.path.join("engine", "demo_fixtures", filename)
    if os.path.exists(rel_demo):
        return rel_demo
    rel_tests = os.path.join("tests", "evaluation_corpus_v2", "invoices", filename)
    if os.path.exists(rel_tests):
        return rel_tests
    raise HTTPException(status_code=500, detail=f"Scenario fixture file missing: {filename}")


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
    """Returns the default evaluation user for programmatic sandbox tests."""
    return AuthenticatedUser(
        id="usr_sme_assoc_01",
        org_id=SANDBOX_ORG_ID,
        email="sme_associate@company.internal",
        name="SME Evaluation Associate",
        role=UserRole.AP_ASSOCIATE,
        is_provisioned=True,
    )


def _build_duplicate_response(
    existing_doc: Document,
    inv: Optional[Invoice],
    sha256: str,
    start_time: float,
) -> Dict[str, Any]:
    """Constructs a deterministic, non-destructive duplicate rejection response."""
    return {
        "status": "COMPLETED",
        "duplicate_detected": True,
        "document_id": existing_doc.id,
        "invoice_id": existing_doc.invoice_id,
        "decision": "REJECTED",
        "stage": "ACTION_REQUIRED",
        "decision_reason": f"Duplicate invoice detected: identical SHA-256 hash ({sha256[:12]}...) was processed previously. Rejection safeguard prevents duplicate payment.",
        "is_live_mantle": False,
        "inference_provider": "Deterministic Hash Guard",
        "latency_ms": round((time.perf_counter() - start_time) * 1000, 2),
        "match_gates": [
            {
                "gate_number": 7,
                "gate_name": "Duplicate Invoice Check",
                "status": "FAIL",
                "notes": f"Duplicate document detected (Hash: {sha256[:12]}...)",
            }
        ],
        "invoice": {
            "id": existing_doc.invoice_id,
            "invoice_number": inv.invoice_number if inv else "DUPLICATE",
            "vendor_name": inv.vendor_name if inv else "Unknown Vendor",
            "vendor_gstin": inv.vendor_gstin if inv else None,
            "po_reference": inv.po_reference if inv else None,
            "subtotal": float(inv.subtotal_amount or 0.0) if inv else 0.0,
            "tax_amount": float(inv.tax_amount or 0.0) if inv else 0.0,
            "total_amount": float(inv.total_amount or 0.0) if inv else 0.0,
            "net_payable": float(inv.net_payable_amount or 0.0) if inv else 0.0,
            "currency": inv.currency if inv else "INR",
            "stage": "ACTION_REQUIRED",
            "decision": "REJECTED",
            "decision_reason": f"Duplicate invoice detected: identical SHA-256 hash ({sha256[:12]}...) was processed previously.",
        },
        "line_items": [],
        "procurement": {"po": None, "grn": None, "qc": None},
        "grounding": {"tripwire_passed": True, "unverified_fields": []},
        "reasons": [f"Duplicate invoice detected: identical SHA-256 hash ({sha256[:12]}...) was processed previously."],
    }


def _get_invoice_sandbox_view(
    db: Session,
    inv_id: str,
    org_id: str,
    scenario: Optional[Dict[str, Any]] = None,
    latency_ms: float = 0.0,
) -> Dict[str, Any]:
    """Retrieves full authoritative 3-pane operational data from persisted PostgreSQL entities."""
    db.expire_all()
    inv = db.scalar(select(Invoice).where(Invoice.id == inv_id, Invoice.org_id == org_id))
    if not inv:
        raise HTTPException(status_code=404, detail="Invoice record not found.")

    doc = db.scalar(select(Document).where(Document.invoice_id == inv_id, Document.org_id == org_id))
    lines_records = db.scalars(
        select(InvoiceLine).where(InvoiceLine.invoice_id == inv_id, InvoiceLine.org_id == org_id).order_by(InvoiceLine.line_number)
    ).all()
    match_run = db.scalar(
        select(MatchRun).where(MatchRun.invoice_id == inv_id, MatchRun.org_id == org_id).order_by(desc(MatchRun.evaluated_at))
    )
    saved_checks = []
    if match_run:
        saved_checks = db.scalars(
            select(MatchGateCheck).where(
                MatchGateCheck.match_run_id == match_run.id,
                MatchGateCheck.org_id == org_id,
            ).order_by(MatchGateCheck.gate_number)
        ).all()

    if saved_checks:
        match_gates = [
            {
                "gate_number": c.gate_number,
                "gate_name": c.gate_name,
                "status": c.status,
                "notes": c.evidence_notes,
            }
            for c in saved_checks
        ]
    else:
        run = reevaluate_match_gates(db, inv, org_id)
        saved_checks = db.scalars(
            select(MatchGateCheck).where(
                MatchGateCheck.match_run_id == run.id,
                MatchGateCheck.org_id == org_id,
            ).order_by(MatchGateCheck.gate_number)
        ).all()
        match_gates = [
            {
                "gate_number": c.gate_number,
                "gate_name": c.gate_name,
                "status": c.status,
                "notes": c.evidence_notes,
            }
            for c in saved_checks
        ]

    # Procurement references
    wo = db.scalar(select(WorkOrderSnapshot).where(WorkOrderSnapshot.po_number == inv.po_reference, WorkOrderSnapshot.org_id == org_id)) if inv.po_reference else None
    grn = None
    qc = None
    if wo:
        grn = db.scalar(select(GoodsReceiptSnapshot).where(GoodsReceiptSnapshot.po_number == wo.po_number, GoodsReceiptSnapshot.org_id == org_id))
        if grn:
            qc = db.scalar(select(QualityControlSnapshot).where(QualityControlSnapshot.grn_number == grn.grn_number, QualityControlSnapshot.org_id == org_id))

    # Extraction Run for Provider info
    ext_run = db.scalar(select(ExtractionRun).where(ExtractionRun.document_id == doc.id).order_by(desc(ExtractionRun.extracted_at))) if doc else None
    is_live = bool(ext_run and ("qwen" in (ext_run.parser_version or "").lower() or "mantle" in (ext_run.parser_version or "").lower()))
    inf_provider = "AWS Bedrock Mantle (Qwen 235B)" if is_live else ("Deterministic AP Engine" if (ext_run and ext_run.parser_version != "NONE_ROUTED_HITL") else "Deterministic Tripwire")

    is_hitl = inv.decision == "FLAGGED_HITL_REVIEW"

    return {
        "status": "COMPLETED",
        "document_id": doc.id if doc else None,
        "invoice_id": inv.id,
        "job_id": None,
        "filename": doc.filename if doc else None,
        "mode": "LIVE_INFERENCE" if is_live else "DETERMINISTIC_RULES",
        "is_live_mantle": is_live,
        "inference_provider": inf_provider,
        "model_id": ext_run.parser_version if ext_run else None,
        "latency_ms": latency_ms,
        "decision": inv.decision,
        "stage": inv.stage,
        "decision_reason": inv.decision_reason,
        "scenario": scenario,
        "invoice": {
            "id": inv.id,
            "invoice_number": inv.invoice_number or "UNKNOWN",
            "vendor_name": inv.vendor_name or "Unknown Supplier",
            "vendor_gstin": inv.vendor_gstin,
            "po_reference": inv.po_reference,
            "subtotal": float(inv.subtotal_amount or 0.0),
            "tax_amount": float(inv.tax_amount or 0.0),
            "total_amount": float(inv.total_amount or 0.0),
            "net_payable": float(inv.net_payable_amount or 0.0),
            "currency": inv.currency or "INR",
            "stage": inv.stage,
            "decision": inv.decision,
            "decision_reason": inv.decision_reason,
        },
        "line_items": [
            {
                "id": l.id,
                "line_number": l.line_number,
                "description": l.description,
                "billed_quantity": float(l.billed_quantity or 0.0),
                "billed_unit_rate": float(l.billed_unit_rate or 0.0),
                "billed_line_total": float(l.billed_line_total or 0.0),
            }
            for l in lines_records
        ],
        "procurement": {
            "po": {
                "po_number": wo.po_number,
                "vendor_code": wo.vendor_code,
                "total_authorized_amount": float(wo.total_authorized_amount or 0.0),
                "remaining_balance": float(wo.remaining_balance or 0.0),
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
        "match_gates": match_gates,
        "grounding": {
            "tripwire_passed": not (is_hitl and "grounding" in (inv.decision_reason or "").lower()),
            "unverified_fields": ["scanned_document_no_text"] if is_hitl and "raster" in (inv.decision_reason or "").lower() else [],
        },
        "reasons": [inv.decision_reason] if inv.decision_reason else [],
    }


def _execute_pipeline_core(
    pdf_bytes: bytes,
    filename: str,
    db: Session,
    org_id: str = SANDBOX_ORG_ID,
    user: Optional[AuthenticatedUser] = None,
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
        actor_id = user.id if user else "usr_sme_assoc_01"
        actor_role = user.role.value if (user and user.role) else "AP_ASSOCIATE"
        db.add(AuditEvent(
            id=f"evt_{uuid.uuid4().hex[:12]}",
            org_id=org_id,
            invoice_id=existing_doc.invoice_id,
            actor_id=actor_id,
            actor_role=actor_role,
            action="DUPLICATE_INTAKE_REJECTED",
            reason=f"Duplicate invoice intake rejected by SHA-256 collision guard ({sha256[:12]}...).",
            after_state={"stage": "ACTION_REQUIRED", "decision": "REJECTED", "sha256": sha256},
            timestamp=datetime.datetime.utcnow(),
        ))
        db.commit()
        return _build_duplicate_response(existing_doc, inv, sha256, start_time)
    elif existing_doc and not force_duplicate_check:
        # Mark previous document version as superseded to allow idempotent re-evaluation in test/pipeline runs
        existing_doc.is_deleted = True
        db.flush()

    # 2. Persist File in Tenant-Isolated Object Storage
    doc_id = f"doc_sbx_{uuid.uuid4().hex[:10]}"
    inv_id = f"inv_sbx_{uuid.uuid4().hex[:10]}"
    job_id = f"job_sbx_{uuid.uuid4().hex[:10]}"

    storage_path = build_tenant_storage_path(org_id, doc_id, filename)
    try:
        storage_meta = storage_adapter.save_file(
            content=pdf_bytes,
            filename=filename,
            mime_type="application/pdf",
            storage_key=storage_path,
        )
    except Exception as exc:
        logger.error("Storage adapter save_file failed in sandbox (%s)", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Secure storage persistence failed.",
        )

    # 3. Create Ingestion Entities in Tenant Workspace
    actor_id = user.id if user else "usr_sme_assoc_01"
    actor_role = user.role.value if (user and user.role) else "AP_ASSOCIATE"

    inv = Invoice(
        id=inv_id,
        org_id=org_id,
        source_channel="SANDBOX_EXPERIENCE",
        stage="RECEIVED",
        decision="NEEDS_REVIEW",
        decision_reason="Uploaded via Sandbox. Awaiting authoritative pipeline execution.",
        currency="INR",
        created_at=now_utc,
        updated_at=now_utc,
        owner_user_id=actor_id,
    )
    db.add(inv)
    db.flush()

    doc = Document(
        id=doc_id,
        org_id=org_id,
        invoice_id=inv_id,
        filename=filename,
        mime_type="application/pdf",
        file_size_bytes=len(pdf_bytes),
        sha256_hash=sha256,
        storage_provider=storage_meta["storage_provider"],
        storage_key=storage_meta["storage_key"],
        is_original=True,
        is_deleted=False,
        uploaded_at=now_utc,
    )
    db.add(doc)
    db.flush()

    lock_token = uuid.uuid4().hex
    job = IngestionJob(
        id=job_id,
        org_id=org_id,
        document_id=doc_id,
        idempotency_key=f"sbx_{sha256[:12]}_{uuid.uuid4().hex[:6]}",
        source_channel="SANDBOX_EXPERIENCE",
        status="PROCESSING",
        lock_token=lock_token,
        lease_expires_at=lease_now(db) + datetime.timedelta(seconds=180),
        created_at=now_utc,
    )
    db.add(job)
    db.flush()

    append_checkpoint(
        db, job, 'INTAKE', 'QUEUED',
        f"Sandbox document intake accepted: {filename}",
        attempt=0,
        invoice_id=inv_id,
        actor_id=actor_id,
        actor_role=actor_role,
        action="DOCUMENT_UPLOADED",
        source_reference=storage_meta['storage_key'],
    )
    db.commit()

    # 4. Execute the Authoritative Pipeline
    pipeline_res = execute_document_pipeline(
        job_id=job.id,
        lock_token=lock_token,
        db_session=db,
        org_id=org_id,
    )

    latency_ms = round((time.perf_counter() - start_time) * 1000, 2)
    return _get_invoice_sandbox_view(db, inv_id, org_id, latency_ms=latency_ms)


# -----------------------------------------------------------------------------
# REST Endpoints
# -----------------------------------------------------------------------------

@router.get("/scenarios")
def list_sandbox_scenarios(
    current_user: AuthenticatedUser = Depends(require_active_membership),
) -> List[Dict[str, Any]]:
    """Returns the genuine synthetic test scenarios available in the sandbox."""
    return GENUINE_SCENARIOS


@router.post("/run-scenario/{scenario_id}")
def run_sandbox_scenario(
    scenario_id: str,
    background_tasks: BackgroundTasks,
    sync: bool = False,
    current_user: AuthenticatedUser = Depends(
        require_role([UserRole.AP_ASSOCIATE, UserRole.AP_LEAD, UserRole.CONTROLLER, UserRole.SYSTEM_ADMIN])
    ),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Executes a genuine test scenario through the authoritative flagship AP Command Center engine."""
    # 1. Enforce Evaluation Workspace Guard (Requirement 5)
    if current_user.org_id != SANDBOX_ORG_ID:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Demonstration scenarios are restricted to authorized evaluation workspaces ('org_sme_eval').",
        )

    # 2. Validate scenario identifier format
    if not re.match(r"^SCN-[A-Za-z0-9_-]+$", scenario_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Malformed scenario identifier.",
        )

    scenario = next((s for s in GENUINE_SCENARIOS if s["id"] == scenario_id or s["id"].split("-")[1] in scenario_id), None)
    if not scenario:
        raise HTTPException(status_code=404, detail=f"Scenario '{scenario_id}' not found.")

    pdf_path = get_scenario_pdf_path(scenario["pdf_filename"])
    with open(pdf_path, "rb") as f:
        pdf_bytes = f.read()

    # 3. Synchronous execution path (for programmatic test clients)
    if sync:
        res = _execute_pipeline_core(
            pdf_bytes=pdf_bytes,
            filename=scenario["pdf_filename"],
            db=db,
            org_id=current_user.org_id,
            user=current_user,
            force_duplicate_check=(scenario["scenario_type"] == "DUPLICATE_INVOICE"),
        )
        res["scenario"] = scenario
        return res

    # 4. Asynchronous Intake (Requirements 2, 4, 5)
    sha256 = hashlib.sha256(pdf_bytes).hexdigest()
    set_tenant_context(db, current_user.org_id)

    existing_doc = db.scalar(
        select(Document).where(
            Document.sha256_hash == sha256,
            Document.org_id == current_user.org_id,
            Document.is_deleted == False,
        )
    )

    # Duplicate scenario (SCN-06)
    if scenario["scenario_type"] == "DUPLICATE_INVOICE":
        if existing_doc:
            inv = db.scalar(select(Invoice).where(Invoice.id == existing_doc.invoice_id, Invoice.org_id == current_user.org_id))
            db.add(AuditEvent(
                id=f"evt_{uuid.uuid4().hex[:12]}",
                org_id=current_user.org_id,
                invoice_id=existing_doc.invoice_id,
                actor_id=current_user.id,
                actor_role=current_user.role.value,
                action="DUPLICATE_INTAKE_REJECTED",
                reason=f"Duplicate invoice intake rejected by SHA-256 collision guard ({sha256[:12]}...).",
                after_state={"stage": "ACTION_REQUIRED", "decision": "REJECTED", "sha256": sha256},
                timestamp=datetime.datetime.utcnow(),
            ))
            db.commit()
            dup_res = _build_duplicate_response(existing_doc, inv, sha256, time.perf_counter())
            dup_res["scenario"] = scenario
            return dup_res
        else:
            # Baseline execution if SCN-01 hasn't been ingested yet
            res = _execute_pipeline_core(
                pdf_bytes=pdf_bytes,
                filename=scenario["pdf_filename"],
                db=db,
                org_id=current_user.org_id,
                user=current_user,
                force_duplicate_check=False,
            )
            res["scenario"] = scenario
            return res

    # Standard scenarios (SCN-01 to SCN-05)
    if existing_doc:
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={
                "status": "DUPLICATE_DETECTED",
                "detail": f"Duplicate document detected: scenario file '{scenario['pdf_filename']}' already exists as invoice '{existing_doc.invoice_id}'.",
                "document_id": existing_doc.id,
                "invoice_id": existing_doc.invoice_id,
                "sha256": sha256,
            },
        )

    # Unique document persistence
    doc_id = f"doc_sbx_{uuid.uuid4().hex[:10]}"
    inv_id = f"inv_sbx_{uuid.uuid4().hex[:10]}"
    job_id = f"job_sbx_{uuid.uuid4().hex[:10]}"
    storage_path = build_tenant_storage_path(current_user.org_id, doc_id, scenario["pdf_filename"])
    storage_meta = storage_adapter.save_file(
        content=pdf_bytes,
        filename=scenario["pdf_filename"],
        mime_type="application/pdf",
        storage_key=storage_path,
    )

    now_utc = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
    inv = Invoice(
        id=inv_id,
        org_id=current_user.org_id,
        source_channel="SANDBOX_EXPERIENCE",
        stage="RECEIVED",
        decision="NEEDS_REVIEW",
        decision_reason="Scenario intake accepted. Awaiting pipeline execution.",
        currency="INR",
        created_at=now_utc,
        updated_at=now_utc,
        owner_user_id=current_user.id,
    )
    db.add(inv)
    db.flush()

    doc = Document(
        id=doc_id,
        org_id=current_user.org_id,
        invoice_id=inv_id,
        filename=scenario["pdf_filename"],
        mime_type="application/pdf",
        file_size_bytes=len(pdf_bytes),
        sha256_hash=sha256,
        storage_provider=storage_meta["storage_provider"],
        storage_key=storage_meta["storage_key"],
        is_original=True,
        is_deleted=False,
        uploaded_at=now_utc,
    )
    db.add(doc)
    db.flush()

    job = IngestionJob(
        id=job_id,
        org_id=current_user.org_id,
        document_id=doc_id,
        idempotency_key=f"sbx_{sha256[:12]}_{uuid.uuid4().hex[:6]}",
        source_channel="SANDBOX_EXPERIENCE",
        status="QUEUED",
        created_at=now_utc,
    )
    db.add(job)
    db.flush()

    append_checkpoint(
        db, job, 'INTAKE', 'QUEUED',
        f"Scenario intake accepted: {scenario['pdf_filename']}",
        attempt=0,
        invoice_id=inv_id,
        actor_id=current_user.id,
        actor_role=current_user.role.value,
        action="DOCUMENT_UPLOADED",
        source_reference=storage_meta['storage_key'],
    )
    db.commit()

    claimed = claim_ingestion_job(db, org_id=current_user.org_id)
    if claimed:
        c_job_id, c_org_id, c_doc_id, c_token = claimed
        background_tasks.add_task(process_document_pipeline_background, c_job_id, c_token, c_org_id)

    return {
        "status": "QUEUED",
        "document_id": doc_id,
        "invoice_id": inv_id,
        "job_id": job.id,
        "filename": scenario["pdf_filename"],
        "scenario": scenario,
        "message": f"Scenario {scenario_id} accepted and queued for processing.",
    }


@router.post("/upload")
async def upload_sandbox_invoice(
    file: UploadFile = File(...),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    sync: bool = False,
    current_user: AuthenticatedUser = Depends(
        require_role([UserRole.AP_ASSOCIATE, UserRole.AP_LEAD, UserRole.CONTROLLER, UserRole.SYSTEM_ADMIN])
    ),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Uploads a live custom invoice PDF and executes the authoritative pipeline asynchronously."""
    filename = file.filename or "unknown.pdf"
    filename = filename.replace("\\", "/").rsplit("/", 1)[-1]

    # Validate filename length and characters
    if len(filename) > 200 or any(ord(c) < 32 or ord(c) == 127 for c in filename):
        raise HTTPException(status_code=400, detail="Invalid document filename.")
    if not filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported file format: Only PDF documents are supported for ingestion.",
        )
    if file.content_type and file.content_type not in ("application/pdf", "application/octet-stream"):
        raise HTTPException(status_code=400, detail="Unsupported document content type.")

    CHUNK_SIZE = 1024 * 1024
    max_bytes = settings.MAX_UPLOAD_FILE_SIZE_BYTES
    chunks = []
    total_read = 0

    while True:
        chunk = await file.read(CHUNK_SIZE)
        if not chunk:
            break
        total_read += len(chunk)
        if total_read > max_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File exceeds maximum permitted size of {max_bytes // (1024 * 1024)} MB.",
            )
        chunks.append(chunk)

    if total_read == 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    content = b"".join(chunks)

    # Validate magic bytes
    if not content.startswith(b"%PDF-"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Corrupted file: Invalid PDF header signature.",
        )

    # Validate PDF structure safely
    try:
        from starlette.concurrency import run_in_threadpool
        await run_in_threadpool(extract_pdf_pages, content)
    except InvalidPDF as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    sha256 = hashlib.sha256(content).hexdigest()
    set_tenant_context(db, current_user.org_id)

    # Tenant duplicate detection
    existing_doc = db.scalar(
        select(Document).where(
            Document.sha256_hash == sha256,
            Document.org_id == current_user.org_id,
            Document.is_deleted == False,
        )
    )
    if existing_doc:
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={
                "status": "DUPLICATE_DETECTED",
                "detail": f"Duplicate document detected: file '{existing_doc.filename}' already exists as invoice '{existing_doc.invoice_id}'.",
                "document_id": existing_doc.id,
                "invoice_id": existing_doc.invoice_id,
                "sha256": sha256,
            },
        )

    if sync:
        return _execute_pipeline_core(
            pdf_bytes=content,
            filename=filename,
            db=db,
            org_id=current_user.org_id,
            user=current_user,
        )

    doc_id = f"doc_sbx_{uuid.uuid4().hex[:10]}"
    inv_id = f"inv_sbx_{uuid.uuid4().hex[:10]}"
    job_id = f"job_sbx_{uuid.uuid4().hex[:10]}"
    storage_path = build_tenant_storage_path(current_user.org_id, doc_id, filename)
    storage_meta = storage_adapter.save_file(
        content=content,
        filename=filename,
        mime_type="application/pdf",
        storage_key=storage_path,
    )

    now_utc = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
    inv = Invoice(
        id=inv_id,
        org_id=current_user.org_id,
        source_channel="SANDBOX_EXPERIENCE",
        stage="RECEIVED",
        decision="NEEDS_REVIEW",
        decision_reason="Custom upload accepted. Awaiting pipeline execution.",
        currency="INR",
        created_at=now_utc,
        updated_at=now_utc,
        owner_user_id=current_user.id,
    )
    db.add(inv)
    db.flush()

    doc = Document(
        id=doc_id,
        org_id=current_user.org_id,
        invoice_id=inv_id,
        filename=filename,
        mime_type="application/pdf",
        file_size_bytes=len(content),
        sha256_hash=sha256,
        storage_provider=storage_meta["storage_provider"],
        storage_key=storage_meta["storage_key"],
        is_original=True,
        is_deleted=False,
        uploaded_at=now_utc,
    )
    db.add(doc)
    db.flush()

    job = IngestionJob(
        id=job_id,
        org_id=current_user.org_id,
        document_id=doc_id,
        idempotency_key=f"sbx_{sha256[:12]}_{uuid.uuid4().hex[:6]}",
        source_channel="SANDBOX_EXPERIENCE",
        status="QUEUED",
        created_at=now_utc,
    )
    db.add(job)
    db.flush()

    append_checkpoint(
        db, job, 'INTAKE', 'QUEUED',
        f"Custom document upload accepted: {filename}",
        attempt=0,
        invoice_id=inv_id,
        actor_id=current_user.id,
        actor_role=current_user.role.value,
        action="DOCUMENT_UPLOADED",
        source_reference=storage_meta['storage_key'],
    )
    db.commit()

    claimed = claim_ingestion_job(db, org_id=current_user.org_id)
    if claimed:
        c_job_id, c_org_id, c_doc_id, c_token = claimed
        background_tasks.add_task(process_document_pipeline_background, c_job_id, c_token, c_org_id)

    return {
        "status": "QUEUED",
        "document_id": doc_id,
        "invoice_id": inv_id,
        "job_id": job.id,
        "filename": filename,
        "message": "Custom document uploaded and queued for processing.",
    }


@router.get("/invoices/{invoice_id}/result")
def get_sandbox_invoice_result(
    invoice_id: str,
    current_user: AuthenticatedUser = Depends(require_active_membership),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Retrieves authoritative structured results for a completed sandbox invoice."""
    set_tenant_context(db, current_user.org_id)
    return _get_invoice_sandbox_view(db, invoice_id, current_user.org_id)


@router.get("/stream-scenario/{scenario_id}")
async def stream_sandbox_scenario(
    scenario_id: str,
    current_user: AuthenticatedUser = Depends(require_active_membership),
    db: Session = Depends(get_db),
):
    """Server-Sent Events (SSE) streaming endpoint deriving real-time events from genuine checkpoints."""
    if not re.match(r"^SCN-[A-Za-z0-9_-]+$", scenario_id):
        raise HTTPException(status_code=400, detail="Malformed scenario identifier.")

    scenario = next((s for s in GENUINE_SCENARIOS if s["id"] == scenario_id or s["id"].split("-")[1] in scenario_id), None)
    if not scenario:
        raise HTTPException(status_code=404, detail=f"Scenario '{scenario_id}' not found.")

    pdf_path = get_scenario_pdf_path(scenario["pdf_filename"])
    with open(pdf_path, "rb") as f:
        pdf_bytes = f.read()

    res = _execute_pipeline_core(
        pdf_bytes=pdf_bytes,
        filename=scenario["pdf_filename"],
        db=db,
        org_id=current_user.org_id,
        user=current_user,
        force_duplicate_check=(scenario["scenario_type"] == "DUPLICATE_INVOICE"),
    )
    res["scenario"] = scenario
    invoice_id = res["invoice_id"]

    snapshot = processing_snapshot(db, invoice_id, current_user.org_id)
    jobs = snapshot.get("jobs", [])
    events = []
    if jobs:
        events = jobs[0].get("events", [])

    async def event_generator():
        yield f"data: {json.dumps({'event': 'INIT', 'scenario_id': scenario_id, 'title': scenario['title'], 'invoice_id': invoice_id})}\n\n"
        for ck in events:
            event_payload = {
                "event": "CHECKPOINT",
                "stage": ck.get("stage"),
                "status": ck.get("status"),
                "sequence": ck.get("sequence"),
                "message": ck.get("message"),
                "timestamp": ck.get("timestamp"),
                "outcome": ck.get("outcome"),
            }
            yield f"data: {json.dumps(event_payload)}\n\n"

        gates = res.get("match_gates", [])
        yield f"data: {json.dumps({'event': 'MATCHING_GATES', 'gates': gates, 'pass_count': sum(1 for g in gates if g.get('status') == 'PASS')})}\n\n"
        yield f"data: {json.dumps({'event': 'DECISION_FINAL', 'decision': res.get('decision'), 'stage': res.get('stage'), 'reason': res.get('decision_reason'), 'result': res})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.post("/invoices/{invoice_id}/action")
def apply_sandbox_action(
    invoice_id: str,
    payload: ActionPayload,
    current_user: AuthenticatedUser = Depends(
        require_role([UserRole.AP_ASSOCIATE, UserRole.AP_LEAD, UserRole.CONTROLLER, UserRole.SYSTEM_ADMIN])
    ),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Executes human review or approval actions subject to authoritative flagship rules and RBAC."""
    set_tenant_context(db, current_user.org_id)
    return execute_invoice_action(
        invoice_id=invoice_id,
        payload=payload,
        current_user=current_user,
        db=db,
    )


@router.get("/runs")
def get_sandbox_runs(
    current_user: AuthenticatedUser = Depends(require_active_membership),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Retrieves recent sandbox runs and aggregated operational metrics for the tenant."""
    set_tenant_context(db, current_user.org_id)

    invs = db.scalars(
        select(Invoice).where(Invoice.org_id == current_user.org_id).order_by(desc(Invoice.updated_at)).limit(25)
    ).all()

    total = len(invs)
    matched_candidates = sum(1 for i in invs if i.decision == "MATCH_CANDIDATE" and i.stage != "APPROVED")
    approved_count = sum(1 for i in invs if i.stage == "APPROVED" or i.decision == "AUTO_APPROVED")
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
            "match_candidates": matched_candidates,
            "approved_count": approved_count,
            "exceptions_flagged": exc_count,
            "reviews_flagged": hitl_count,
            "rejected": rej_count,
            "straight_through_rate_pct": round((approved_count / total * 100), 1) if total > 0 else 0.0,
            "match_candidate_rate_pct": round((matched_candidates / total * 100), 1) if total > 0 else 0.0,
            "exception_rate_pct": round(((exc_count + hitl_count + rej_count) / total * 100), 1) if total > 0 else 0.0,
            "total_value_inr": round(total_val, 2),
        },
        "runs": items,
    }


@router.post("/reset")
def reset_sandbox_data(
    current_user: AuthenticatedUser = Depends(
        require_role([UserRole.AP_LEAD, UserRole.CONTROLLER, UserRole.SYSTEM_ADMIN])
    ),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Restores baseline line items on evaluation tenant 'org_sme_eval' without altering immutable audit records."""
    if settings.APP_ENV in (AppEnv.PRODUCTION, AppEnv.STAGING):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Sandbox reset is disabled in production and staging environments.",
        )
    if current_user.org_id != SANDBOX_ORG_ID:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Sandbox reset is strictly restricted to the 'org_sme_eval' evaluation workspace.",
        )
    from backend.api.v1.system import reset_demo_state
    set_tenant_context(db, current_user.org_id)
    return reset_demo_state(current_user=current_user, db=db)
