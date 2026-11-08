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

from fastapi import APIRouter, Depends, File, HTTPException, Query, Security, UploadFile, status
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
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
from backend.core.pipeline import execute_document_pipeline
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
    """Returns the default evaluation user for programmatic sandbox tests."""
    return AuthenticatedUser(
        id="usr_sme_associate",
        org_id=SANDBOX_ORG_ID,
        email="sme_associate@company.internal",
        name="SME Evaluation Associate",
        role=UserRole.AP_ASSOCIATE,
        is_provisioned=True,
    )


def _resolve_sse_user(
    auth_token: Optional[str] = Query(None),
    credentials: Optional[HTTPAuthorizationCredentials] = Security(security_bearer),
    db: Session = Depends(get_db),
) -> AuthenticatedUser:
    """Authenticates SSE stream requests via Bearer header or query token parameter."""
    token = None
    if credentials and credentials.credentials:
        token = credentials.credentials
    elif auth_token:
        token = auth_token

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required for SSE stream. Provide Bearer header or auth_token query parameter.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    claims, hint_org, hint_role = verify_token_claims(token)
    user_id = claims["sub"]
    email = claims["email"]
    name = claims.get("name") or email.split("@")[0]
    issuer = claims.get("iss") or ("test" if settings.APP_ENV == AppEnv.TEST else None)

    org_id, org_name, role, is_provisioned, available_orgs, member_id, is_owner = resolve_server_side_membership(
        auth_user_id=user_id,
        email=email,
        requested_org_id=hint_org,
        db=db,
        hint_org_id=hint_org,
        hint_role=hint_role,
        issuer=issuer,
    )

    if not is_provisioned or not org_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is not provisioned in an active organisation.",
        )

    set_tenant_context(db, org_id)
    return AuthenticatedUser(
        id=member_id or user_id,
        auth_subject=user_id,
        identity_issuer=issuer,
        email=email,
        name=name,
        role=role,
        org_id=org_id,
        org_name=org_name,
        is_provisioned=is_provisioned,
        is_owner=is_owner,
    )


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
        return {
            "status": "COMPLETED",
            "duplicate_detected": True,
            "document_id": existing_doc.id,
            "invoice_id": existing_doc.invoice_id,
            "decision": "REJECTED",
            "stage": "ACTION_REQUIRED",
            "decision_reason": f"Duplicate invoice detected: identical SHA-256 hash ({sha256[:12]}...) was processed previously.",
            "is_live_mantle": False,
            "latency_ms": round((time.perf_counter() - start_time) * 1000, 2),
            "match_gates": [
                {"gate_number": 7, "gate_name": "Duplicate Invoice Check", "status": "FAIL", "notes": f"Duplicate document detected (Hash: {sha256[:12]}...)"}
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

    # 2. Persist File in Tenant-Isolated Object Storage
    doc_id = existing_doc.id if existing_doc else f"doc_sbx_{uuid.uuid4().hex[:10]}"
    inv_id = existing_doc.invoice_id if existing_doc else f"inv_sbx_{uuid.uuid4().hex[:10]}"
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

    # 3. Create or Update Ingestion Entities in Tenant Workspace
    actor_id = user.id if user else "usr_sme_associate"
    actor_role = user.role.value if (user and user.role) else "AP_ASSOCIATE"

    inv = db.scalar(select(Invoice).where(Invoice.id == inv_id, Invoice.org_id == org_id))
    if not inv:
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

    if not existing_doc:
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

    # 5. Fetch Authoritative Persisted Records
    db.expire_all()
    inv = db.scalar(select(Invoice).where(Invoice.id == inv_id, Invoice.org_id == org_id))
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

    ext_run = db.scalar(
        select(ExtractionRun).where(ExtractionRun.document_id == doc_id, ExtractionRun.org_id == org_id)
    )

    is_live = bool(ext_run and ("qwen" in (ext_run.parser_version or "").lower() or "mantle" in (ext_run.parser_version or "").lower()))

    # Procurement references
    wo = db.scalar(select(WorkOrderSnapshot).where(WorkOrderSnapshot.po_number == inv.po_reference, WorkOrderSnapshot.org_id == org_id)) if (inv and inv.po_reference) else None
    grn = db.scalar(select(GoodsReceiptSnapshot).where(GoodsReceiptSnapshot.po_number == inv.po_reference, GoodsReceiptSnapshot.org_id == org_id)) if (inv and inv.po_reference) else None
    qc = db.scalar(select(QualityControlSnapshot).where(QualityControlSnapshot.grn_number == grn.grn_number, QualityControlSnapshot.org_id == org_id)) if grn else None

    # Tripwire & reasoning flags
    is_hitl = inv.decision == "FLAGGED_HITL_REVIEW" if inv else False

    return {
        "status": "COMPLETED",
        "document_id": doc_id,
        "invoice_id": inv_id,
        "job_id": job_id,
        "filename": filename,
        "mode": "LIVE_INFERENCE" if is_live else "DETERMINISTIC_RULES",
        "is_live_mantle": is_live,
        "inference_provider": "AWS Bedrock Mantle (Qwen 235B)" if is_live else "Deterministic AP Engine",
        "model_id": ext_run.parser_version if ext_run else None,
        "latency_ms": latency_ms,
        "decision": inv.decision if inv else "UNKNOWN",
        "stage": inv.stage if inv else "UNKNOWN",
        "decision_reason": inv.decision_reason if inv else "",
        "invoice": {
            "id": inv.id if inv else inv_id,
            "invoice_number": inv.invoice_number if inv else "UNKNOWN",
            "vendor_name": inv.vendor_name if inv else "Unknown Supplier",
            "vendor_gstin": inv.vendor_gstin if inv else None,
            "po_reference": inv.po_reference if inv else None,
            "subtotal": float(inv.subtotal_amount or 0.0) if inv else 0.0,
            "tax_amount": float(inv.tax_amount or 0.0) if inv else 0.0,
            "total_amount": float(inv.total_amount or 0.0) if inv else 0.0,
            "net_payable": float(inv.net_payable_amount or 0.0) if inv else 0.0,
            "currency": inv.currency if inv else "INR",
            "stage": inv.stage if inv else "UNKNOWN",
            "decision": inv.decision if inv else "UNKNOWN",
            "decision_reason": inv.decision_reason if inv else "",
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
            "tripwire_passed": not (is_hitl and "grounding" in (inv.decision_reason or "").lower()),
            "unverified_fields": ["scanned_document_no_text"] if is_hitl and "raster" in (inv.decision_reason or "").lower() else [],
        },
        "reasons": [inv.decision_reason] if inv and inv.decision_reason else [],
    }


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
    current_user: AuthenticatedUser = Depends(
        require_role([UserRole.AP_ASSOCIATE, UserRole.AP_LEAD, UserRole.CONTROLLER, UserRole.SYSTEM_ADMIN])
    ),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Executes a genuine test scenario through the flagship AP Command Center engine."""
    # Validate scenario identifier format
    if not re.match(r"^SCN-[A-Za-z0-9_-]+$", scenario_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Malformed scenario identifier.",
        )

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
        org_id=current_user.org_id,
        user=current_user,
        force_duplicate_check=force_dup,
    )
    result["scenario"] = scenario
    return result


@router.post("/upload")
async def upload_sandbox_invoice(
    file: UploadFile = File(...),
    current_user: AuthenticatedUser = Depends(
        require_role([UserRole.AP_ASSOCIATE, UserRole.AP_LEAD, UserRole.CONTROLLER, UserRole.SYSTEM_ADMIN])
    ),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Uploads a live custom invoice PDF and executes the authoritative pipeline."""
    filename = file.filename or "unknown.pdf"
    filename = filename.replace("\\", "/").rsplit("/", 1)[-1]

    # Validate filename length and characters
    if len(filename) > 200 or any(ord(c) < 32 or ord(c) == 127 for c in filename):
        raise HTTPException(status_code=400, detail="Invalid document filename.")

    # Validate file extension
    if not filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported file format: Only PDF documents are supported for ingestion.",
        )

    # Read bytes with bounded limit (15 MB for sandbox)
    MAX_BYTES = 15 * 1024 * 1024
    CHUNK_SIZE = 1024 * 1024
    chunks = []
    total_read = 0

    while True:
        chunk = await file.read(CHUNK_SIZE)
        if not chunk:
            break
        total_read += len(chunk)
        if total_read > MAX_BYTES:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File exceeds maximum permitted size of {MAX_BYTES // (1024 * 1024)} MB.",
            )
        chunks.append(chunk)

    if total_read == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty.",
        )

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

    result = _execute_pipeline_core(
        pdf_bytes=content,
        filename=filename,
        db=db,
        org_id=current_user.org_id,
        user=current_user,
    )
    return result


@router.get("/stream-scenario/{scenario_id}")
async def stream_sandbox_scenario(
    scenario_id: str,
    current_user: AuthenticatedUser = Depends(_resolve_sse_user),
    db: Session = Depends(get_db),
):
    """Server-Sent Events (SSE) streaming endpoint deriving real-time events from genuine checkpoints."""
    if not re.match(r"^SCN-[A-Za-z0-9_-]+$", scenario_id):
        raise HTTPException(status_code=400, detail="Malformed scenario identifier.")

    scenario = next((s for s in GENUINE_SCENARIOS if s["id"] == scenario_id or s["id"].split("-")[1] in scenario_id), None)
    if not scenario:
        raise HTTPException(status_code=404, detail=f"Scenario '{scenario_id}' not found.")

    pdf_path = os.path.join(CORPUS_DIR, scenario["pdf_filename"])
    if not os.path.exists(pdf_path):
        raise HTTPException(status_code=500, detail=f"Fixture file missing: {pdf_path}")

    with open(pdf_path, "rb") as f:
        pdf_bytes = f.read()

    # Execute authoritative pipeline
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

    # Retrieve genuine persisted checkpoints from AuditEvent
    snapshot = processing_snapshot(db, invoice_id, current_user.org_id)
    jobs = snapshot.get("jobs", [])
    events = []
    if jobs:
        events = jobs[0].get("events", [])

    async def event_generator():
        # Emit initial scenario context
        yield f"data: {json.dumps({'event': 'INIT', 'scenario_id': scenario_id, 'title': scenario['title'], 'invoice_id': invoice_id})}\n\n"

        # Stream genuine persisted checkpoints recorded by append_checkpoint
        for ck in events:
            event_payload = {
                "event": "CHECKPOINT",
                "stage": ck.get("stage"),
                "status": ck.get("status"),
                "sequence": ck.get("sequence"),
                "message": ck.get("message"),
                "timestamp": ck.get("timestamp"),
            }
            yield f"data: {json.dumps(event_payload)}\n\n"

        # Emit matching gates summary
        gates = res.get("match_gates", [])
        yield f"data: {json.dumps({'event': 'MATCHING_GATES', 'gates': gates, 'pass_count': sum(1 for g in gates if g.get('status') == 'PASS')})}\n\n"

        # Emit final decision
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
def reset_sandbox_data(
    current_user: AuthenticatedUser = Depends(
        require_role([UserRole.AP_LEAD, UserRole.CONTROLLER, UserRole.SYSTEM_ADMIN])
    ),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Restores the sandbox evaluation workspace to clean baseline fixtures."""
    from backend.api.v1.system import reset_evaluation_fixtures
    set_tenant_context(db, current_user.org_id)
    return reset_evaluation_fixtures(current_user=current_user, db=db)
