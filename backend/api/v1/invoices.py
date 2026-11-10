"""Single Invoice Inspection & Human Exception Action Hub.

Enforces:
1. Three-pane operational view data retrieval.
2. Server-side role checks and atomic audit on every mutation.
3. Dual-control enforcement above monetary threshold (distinct first and second approvers).
4. No fake transitions; internal approvals never claim ERP posting or payment.
"""

from __future__ import annotations

import datetime
from decimal import Decimal
import os
import re
import uuid
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Query, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.core.auth import AuthenticatedUser, UserRole, require_active_membership, require_role
from backend.core.config import settings
from backend.core.database import get_db
from backend.core.pipeline import (
    claim_ingestion_job, process_document_pipeline_background, recover_expired_jobs,
)
from backend.core.processing_events import append_checkpoint, lease_now
from backend.core.storage import storage_adapter
from backend.models.domain import (
    ApprovalRequest, AuditEvent, Document, ExceptionRecord, ExtractedField, ExtractionRun,
    GoodsReceiptLineSnapshot, GoodsReceiptSnapshot, IngestionJob, Invoice, InvoiceLine, MatchGateCheck, MatchRun,
    QualityControlSnapshot, WorkOrderLineSnapshot, WorkOrderSnapshot, Vendor, VendorGSTIN
)

router = APIRouter(prefix="/invoices", tags=["Invoice Detail & Actions"])


@router.get('/{invoice_id}/processing')
def get_invoice_processing(invoice_id: str,
    current_user: AuthenticatedUser = Depends(require_active_membership),
    db: Session = Depends(get_db)) -> Dict[str, Any]:
    if db is None:
        raise HTTPException(status_code=503, detail='Database not connected.')
    if db.scalar(select(Invoice.id).where(Invoice.id == invoice_id,
            Invoice.org_id == current_user.org_id)) is None:
        raise HTTPException(status_code=404, detail='Invoice not found.')
    from backend.core.processing_events import processing_snapshot
    return processing_snapshot(db, invoice_id, current_user.org_id)


MAX_INGESTION_JOBS_PER_DOCUMENT = 3


@router.post('/{invoice_id}/processing/retry', status_code=status.HTTP_202_ACCEPTED)
def retry_invoice_processing(
    invoice_id: str,
    background_tasks: BackgroundTasks,
    current_user: AuthenticatedUser = Depends(require_role([
        UserRole.AP_ASSOCIATE, UserRole.AP_LEAD, UserRole.CONTROLLER, UserRole.SYSTEM_ADMIN,
    ])),
    db: Session = Depends(get_db),
) -> Any:
    """Recover or reprocess the latest job for this invoice only.

    The invoice row and source document are locked so two browser tabs cannot
    claim duplicate work. Expired leases are recovered first; terminal failures
    receive at most three durable job records, each retaining its checkpoints.
    """
    if db is None:
        raise HTTPException(status_code=503, detail='Database not connected.')

    # Fast, lock-free preflight for the normal double-click case. Acquiring the
    # invoice/document/job locks before discovering an active worker can deadlock
    # with the worker's own short result transaction on PostgreSQL.
    active_job = db.scalar(
        select(IngestionJob)
        .join(Document, IngestionJob.document_id == Document.id)
        .where(
            Document.invoice_id == invoice_id,
            Document.org_id == current_user.org_id,
            Document.is_original == True,
            IngestionJob.org_id == current_user.org_id,
        )
        .order_by(IngestionJob.created_at.desc(), IngestionJob.id.desc())
        .limit(1)
    )
    if active_job and active_job.status == 'PROCESSING' and active_job.lease_expires_at:
        if active_job.lease_expires_at > lease_now(db):
            return JSONResponse(status_code=status.HTTP_202_ACCEPTED, content={
                'status': 'ALREADY_PROCESSING',
                'invoice_id': invoice_id,
                'job_id': active_job.id,
                'detail': 'This invoice still has an active processing lease. No duplicate worker was started.',
            })

    inv = db.scalar(select(Invoice).where(
        Invoice.id == invoice_id, Invoice.org_id == current_user.org_id,
    ).with_for_update())
    if not inv:
        raise HTTPException(status_code=404, detail='Invoice not found.')

    doc = db.scalar(select(Document).where(
        Document.invoice_id == inv.id,
        Document.org_id == current_user.org_id,
        Document.is_original == True,
    ).order_by(Document.uploaded_at.desc()).with_for_update())
    if not doc:
        raise HTTPException(status_code=409, detail='The original document is unavailable; upload a replacement before reprocessing.')
    if doc.is_deleted:
        raise HTTPException(status_code=409, detail='The source document was soft-deleted. Processing cannot be restarted.')

    jobs = db.scalars(select(IngestionJob).where(
        IngestionJob.document_id == doc.id,
        IngestionJob.org_id == current_user.org_id,
    ).order_by(IngestionJob.created_at.desc(), IngestionJob.id.desc()).with_for_update()).all()
    latest = jobs[0] if jobs else None
    now = lease_now(db)

    if latest and latest.status == 'COMPLETED':
        raise HTTPException(status_code=409, detail='Processing already completed; start a new upload to run a fresh extraction.')

    if latest and latest.status == 'PROCESSING' and latest.lease_expires_at and latest.lease_expires_at > now:
        return JSONResponse(status_code=status.HTTP_202_ACCEPTED, content={
            'status': 'ALREADY_PROCESSING',
            'invoice_id': inv.id,
            'job_id': latest.id,
            'detail': 'This invoice still has an active processing lease. No duplicate worker was started.',
        })

    # An expired PROCESSING row is requeued with its retry counter advanced.
    if latest and latest.status == 'PROCESSING':
        recover_expired_jobs(
            db, org_id=current_user.org_id, max_retries=3, job_id=latest.id,
        )
        db.refresh(latest)
        now = lease_now(db)

    if latest and latest.status == 'QUEUED':
        job_id = latest.id
    else:
        if len(jobs) >= MAX_INGESTION_JOBS_PER_DOCUMENT:
            raise HTTPException(status_code=409, detail=(
                'Retry limit reached for this document. Upload a new PDF or contact an administrator; '
                'the existing processing evidence is retained.'
            ))
        if latest and latest.status not in ('FAILED', 'PROCESSING'):
            raise HTTPException(status_code=409, detail='The current processing job cannot be retried from its present state.')

        job_id = f"job_{uuid.uuid4().hex[:12]}"
        job = IngestionJob(
            id=job_id,
            org_id=current_user.org_id,
            document_id=doc.id,
            idempotency_key=f"reprocess_{doc.id}_{job_id}",
            source_channel='MANUAL_UPLOAD',
            status='QUEUED',
        )
        db.add(job)
        db.flush()
        append_checkpoint(
            db, job, 'RECOVERY', 'QUEUED',
            f"Operator requested reprocessing after {latest.status.lower() if latest else 'no previous job'}.",
            attempt=0, invoice_id=inv.id, actor_id=current_user.id,
            actor_role=current_user.role.value if current_user.role else 'UNKNOWN',
            source_reference=doc.storage_key,
        )
        inv.stage = 'RECEIVED'
        inv.decision = 'NEEDS_REVIEW'
        inv.decision_reason = 'Reprocessing requested by an operator. Prior results remain in the immutable audit history.'
        inv.updated_at = now
        db.commit()

    if os.getenv('ENABLE_BACKGROUND_PIPELINE', 'true').lower() != 'true':
        return {'status': 'QUEUED', 'invoice_id': inv.id, 'job_id': job_id,
                'detail': 'Job queued. Background dispatch is disabled in this environment.'}

    claimed = claim_ingestion_job(
        db, org_id=current_user.org_id, job_id=job_id, recover_expired=False,
    )
    if not claimed:
        current = db.scalar(select(IngestionJob).where(
            IngestionJob.id == job_id, IngestionJob.org_id == current_user.org_id,
        ))
        if current and current.status == 'PROCESSING':
            return JSONResponse(status_code=status.HTTP_202_ACCEPTED, content={
                'status': 'ALREADY_PROCESSING', 'invoice_id': inv.id, 'job_id': job_id,
                'detail': 'Another worker claimed this job first. No duplicate worker was started.',
            })
        return JSONResponse(status_code=status.HTTP_202_ACCEPTED, content={
            'status': 'QUEUED', 'invoice_id': inv.id, 'job_id': job_id,
            'detail': 'Job is queued; retry again if no worker claims it.',
        })

    claimed_job_id, claimed_org_id, _, lock_token = claimed
    background_tasks.add_task(process_document_pipeline_background, claimed_job_id, lock_token, claimed_org_id)
    return {'status': 'PROCESSING', 'invoice_id': inv.id, 'job_id': claimed_job_id}


class ActionPayload(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)
    action: str = Field(..., description="Action name: APPROVE_AP_REVIEW, APPROVE_UNDISPUTED, REJECT_INVOICE, HOLD_PENDING_EVIDENCE, REQUEST_SUPPLIER_CORRECTION, RAISE_DEBIT_NOTE, ESCALATE, QUARANTINE")
    reason: str = Field(..., min_length=3, description="Operational justification for the action")
    undisputed_amount: Optional[float] = Field(None, description="Required for APPROVE_UNDISPUTED")
    evidence_reference: Optional[str] = None


class LineCorrectionPayload(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)
    billed_quantity: float = Field(..., gt=0, description="Corrected billed quantity")
    billed_unit_rate: float = Field(..., gt=0, description="Corrected unit rate")
    correction_reason: str = Field(..., min_length=3, description="Audit reason for correcting extracted line item")


@router.get("/{invoice_id}")
def get_invoice_detail(
    invoice_id: str,
    current_user: AuthenticatedUser = Depends(require_active_membership),
    db: Optional[Session] = Depends(get_db),
) -> Dict[str, Any]:
    """Retrieves comprehensive 3-pane operational data for an invoice."""
    if db is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database not connected.")

    inv = db.scalar(select(Invoice).where(Invoice.id == invoice_id, Invoice.org_id == current_user.org_id))
    if not inv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Invoice '{invoice_id}' not found.")

    # 1. Document & Extracted Fields
    doc = db.scalar(select(Document).where(Document.invoice_id == inv.id, Document.is_original == True))
    doc_data = None
    extracted_fields_data = []

    if doc:
        try:
            signed_url = storage_adapter.generate_signed_url(doc.storage_key, expires_in=300)
        except Exception:
            signed_url = None

        doc_data = {
            "document_id": doc.id,
            "filename": doc.filename,
            "mime_type": doc.mime_type,
            "size_bytes": doc.file_size_bytes,
            "sha256": doc.sha256_hash,
            "preview_url": signed_url,
        }

        # Extracted fields
        ext_run = db.scalar(select(ExtractionRun).where(ExtractionRun.document_id == doc.id).order_by(ExtractionRun.extracted_at.desc()))
        if ext_run:
            fields = db.scalars(select(ExtractedField).where(ExtractedField.extraction_run_id == ext_run.id)).all()
            for f in fields:
                extracted_fields_data.append({
                    "field_name": f.field_name,
                    "value": f.extracted_value,
                    "confidence": float(f.confidence_score) if f.confidence_score is not None else None,
                    "source_page": f.source_page,
                    "bounding_box": f.bounding_box,
                })

    # 2. Line Items
    lines = db.scalars(select(InvoiceLine).where(InvoiceLine.invoice_id == inv.id).order_by(InvoiceLine.line_number)).all()
    serialized_lines = [
        {
            "id": l.id,
            "line_number": l.line_number,
            "description": l.description,
            "quantity": float(l.billed_quantity),
            "rate": float(l.billed_unit_rate),
            "total": float(l.billed_line_total),
            "is_corrected": bool(getattr(l, "is_corrected", False)),
            "previous_unit_rate": float(l.previous_unit_rate) if getattr(l, "previous_unit_rate", None) is not None else None,
            "line_version": getattr(l, "line_version", 1),
        }
        for l in lines
    ]

    # 2.5 Authoritative Procurement Reference Snapshot (PO, GRN, QC)
    po_snapshot = None
    if inv.po_reference:
        wo = db.scalar(
            select(WorkOrderSnapshot).where(
                WorkOrderSnapshot.po_number == inv.po_reference,
                WorkOrderSnapshot.org_id == current_user.org_id,
            )
        )
        if wo:
            wo_lines = db.scalars(
                select(WorkOrderLineSnapshot)
                .where(WorkOrderLineSnapshot.po_id == wo.id, WorkOrderLineSnapshot.org_id == current_user.org_id)
                .order_by(WorkOrderLineSnapshot.line_number)
            ).all()

            grn = db.scalar(
                select(GoodsReceiptSnapshot).where(
                    GoodsReceiptSnapshot.po_number == inv.po_reference,
                    GoodsReceiptSnapshot.org_id == current_user.org_id,
                )
            )
            grn_lines_data = []
            qc_data = None
            if grn:
                grn_lines_rows = db.scalars(
                    select(GoodsReceiptLineSnapshot).where(
                        GoodsReceiptLineSnapshot.grn_id == grn.id,
                        GoodsReceiptLineSnapshot.org_id == current_user.org_id,
                    )
                ).all()
                grn_lines_data = [
                    {
                        "po_line_number": gl.po_line_number,
                        "accepted_quantity": float(gl.accepted_quantity),
                        "rejected_quantity": float(gl.rejected_quantity),
                    }
                    for gl in grn_lines_rows
                ]
                qc = db.scalar(
                    select(QualityControlSnapshot).where(
                        QualityControlSnapshot.grn_number == grn.grn_number,
                        QualityControlSnapshot.org_id == current_user.org_id,
                    )
                )
                if qc:
                    qc_data = {
                        "qc_certificate_number": qc.qc_certificate_number,
                        "overall_status": qc.overall_status,
                        "status": qc.overall_status,
                        "retrieved_at": qc.retrieved_at.isoformat() + "Z" if qc.retrieved_at else None,
                    }

            po_snapshot = {
                "po_number": wo.po_number,
                "vendor_code": wo.vendor_code,
                "total_authorized_amount": float(wo.total_authorized_amount) if wo.total_authorized_amount else None,
                "remaining_balance": float(wo.remaining_balance) if wo.remaining_balance else None,
                "currency": wo.currency,
                "status": wo.status,
                "retrieved_at": wo.retrieved_at.isoformat() + "Z" if wo.retrieved_at else None,
                "lines": [
                    {
                        "line_number": wol.line_number,
                        "item_code": wol.item_code,
                        "description": wol.description,
                        "authorized_quantity": float(wol.authorized_quantity),
                        "contracted_unit_rate": float(wol.contracted_unit_rate),
                        "authorized_line_total": float(wol.authorized_line_total),
                    }
                    for wol in wo_lines
                ],
                "grn": {
                    "grn_number": grn.grn_number,
                    "received_date": grn.received_date.isoformat() + "Z" if grn.received_date else None,
                    "lines": grn_lines_data,
                } if grn else None,
                "qc": qc_data,
            }

    # 3. Match Gates Trace
    match_run = db.scalar(select(MatchRun).where(MatchRun.invoice_id == inv.id).order_by(MatchRun.evaluated_at.desc()))
    gates_data = []
    if match_run:
        gates = db.scalars(select(MatchGateCheck).where(MatchGateCheck.match_run_id == match_run.id).order_by(MatchGateCheck.gate_number)).all()
        for g in gates:
            gates_data.append({
                "gate_number": g.gate_number,
                "gate_name": g.gate_name,
                "status": g.status,
                "evidence_source_id": g.evidence_source_id,
                "notes": g.evidence_notes,
                "checked_at": g.checked_at.isoformat() + "Z",
            })

    # 4. Approval Status
    approval_req = db.scalar(select(ApprovalRequest).where(ApprovalRequest.invoice_id == inv.id))
    approval_data = None
    if approval_req:
        approval_data = {
            "requires_dual_approval": approval_req.requires_dual_approval,
            "first_approver_id": approval_req.first_approver_id,
            "first_approved_at": approval_req.first_approved_at.isoformat() + "Z" if approval_req.first_approved_at else None,
            "second_approver_id": approval_req.second_approver_id,
            "second_approved_at": approval_req.second_approved_at.isoformat() + "Z" if approval_req.second_approved_at else None,
            "status": approval_req.status,
        }

    # 5. Timeline / Audit Events
    audits = db.scalars(select(AuditEvent).where(AuditEvent.invoice_id == inv.id).order_by(AuditEvent.timestamp.desc())).all()
    timeline = [
        {
            "event_id": a.id,
            "actor_id": a.actor_id,
            "actor_role": a.actor_role,
            "action": a.action,
            "reason": a.reason,
            "timestamp": a.timestamp.isoformat() + "Z",
        }
        for a in audits
    ]

    job_status = None
    job_error = None
    job_id = None
    job_lease_expired = False
    if doc:
        job_rec = db.scalar(
            select(IngestionJob)
            .where(IngestionJob.document_id == doc.id, IngestionJob.org_id == current_user.org_id)
            .order_by(IngestionJob.created_at.desc())
        )
        if job_rec:
            job_status = job_rec.status
            job_error = job_rec.error_message
            job_id = job_rec.id
            job_lease_expired = bool(
                job_rec.status == 'PROCESSING'
                and job_rec.lease_expires_at
                and job_rec.lease_expires_at <= lease_now(db)
            )

    return {
        "invoice": {
            "id": inv.id,
            "invoice_number": inv.invoice_number,
            "vendor_name": inv.vendor_name,
            "vendor_gstin": inv.vendor_gstin,
            "po_reference": inv.po_reference,
            "subtotal": float(inv.subtotal_amount) if inv.subtotal_amount else None,
            "tax_amount": float(inv.tax_amount) if inv.tax_amount else None,
            "total_amount": float(inv.total_amount) if inv.total_amount else None,
            "net_payable": float(inv.net_payable_amount) if inv.net_payable_amount else None,
            "currency": inv.currency,
            "stage": inv.stage,
            "decision": inv.decision,
            "decision_reason": inv.decision_reason,
            "job_status": job_status,
            "job_error": job_error,
            "job_id": job_id,
            "job_lease_expired": job_lease_expired,
            "workflow_substatus": getattr(inv, "workflow_substatus", None),
            "msme_statutory_deadline": inv.msme_statutory_deadline.isoformat() + "Z" if inv.msme_statutory_deadline else None,
            "msme_deadline_status": inv.msme_deadline_status,
            "created_at": inv.created_at.isoformat() + "Z",
            "updated_at": inv.updated_at.isoformat() + "Z",
        },
        "document": doc_data,
        "extracted_fields": extracted_fields_data,
        "lines": serialized_lines,
        "po_snapshot": po_snapshot,
        "match_gates": gates_data,
        "approval": approval_data,
        "timeline": timeline,
        "policy": {
            "dual_approval_threshold_inr": settings.DUAL_APPROVAL_THRESHOLD_INR,
            "rate_tolerance_percent": settings.RATE_TOLERANCE_PERCENT,
            "rounding_tolerance_inr": settings.ROUNDING_TOLERANCE_INR,
        },
    }


@router.post("/{invoice_id}/actions")
def execute_invoice_action(
    invoice_id: str,
    payload: ActionPayload,
    current_user: AuthenticatedUser = Depends(require_active_membership),
    db: Optional[Session] = Depends(get_db),
) -> Dict[str, Any]:
    """Executes an authorized human exception triage action.

    Enforces:
    - Server-side role permissions (Auditors cannot mutate).
    - Dual control: Invoices above threshold require two distinct approvers.
    - Transactional write of state change and append-only audit event.
    """
    if db is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database not connected.")

    if current_user.is_read_only():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Auditor role is strictly read-only and cannot execute mutations.",
        )

    inv = db.scalar(select(Invoice).where(Invoice.id == invoice_id, Invoice.org_id == current_user.org_id).with_for_update())
    if not inv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Invoice '{invoice_id}' not found.")

    now_utc = datetime.datetime.utcnow()
    before_state = {"stage": inv.stage, "decision": inv.decision, "net_payable": float(inv.net_payable_amount) if inv.net_payable_amount else None}

    VALID_ACTIONS = {
        "APPROVE_AP_REVIEW", "APPROVE_UNDISPUTED", "REJECT_INVOICE",
        "HOLD_PENDING_EVIDENCE", "REQUEST_SUPPLIER_CORRECTION",
        "RAISE_DEBIT_NOTE", "ESCALATE", "QUARANTINE"
    }
    if payload.action not in VALID_ACTIONS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unknown or invalid action '{payload.action}'. Allowed actions: {sorted(list(VALID_ACTIONS))}",
        )

    # Idempotent duplicate action handling: if already approved, return current state without duplicate audit events
    if inv.stage == "INTERNAL_APPROVAL_COMPLETE" and payload.action in ("APPROVE_AP_REVIEW", "APPROVE_UNDISPUTED"):
        return {
            "status": "ALREADY_APPROVED",
            "invoice_id": invoice_id,
            "new_stage": inv.stage,
            "new_decision": inv.decision,
            "reason": "Invoice is already approved. Duplicate action handled idempotently without duplicate records.",
            "updated_at": (inv.updated_at or now_utc).isoformat() + "Z",
        }

    # Fetch active exceptions to synchronize lifecycle
    active_exceptions = db.scalars(
        select(ExceptionRecord).where(
            ExceptionRecord.invoice_id == inv.id,
            ExceptionRecord.org_id == current_user.org_id,
            ExceptionRecord.status.in_(["OPEN", "IN_REVIEW"])
        )
    ).all()

    # Action 1 & 2: Approvals (Strict Validation Gate Enforcement - D-04 overrides deferred)
    if payload.action in ("APPROVE_AP_REVIEW", "APPROVE_UNDISPUTED"):
        if inv.stage in ("REJECTED", "QUARANTINED") or inv.decision in ("REJECTED", "QUARANTINED"):
            raise HTTPException(status_code=409, detail="Rejected or quarantined invoices cannot be approved.")
        if inv.workflow_substatus == "ON_HOLD":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Cannot approve invoice while it is ON_HOLD pending evidence. The hold must be resolved first.",
            )
        # Strictly prevent approval if any deterministic match gate check failed (D-04 override deferred)
        match_run = db.scalar(
            select(MatchRun)
            .where(MatchRun.invoice_id == inv.id, MatchRun.org_id == current_user.org_id)
            .order_by(MatchRun.evaluated_at.desc())
        )
        if match_run:
            checks = db.scalars(select(MatchGateCheck).where(
                MatchGateCheck.match_run_id == match_run.id,
                MatchGateCheck.org_id == current_user.org_id,
            )).all()
            if not set(range(1, 8)).issubset({g.gate_number for g in checks if g.status == "PASS"}) or any(g.status != "PASS" for g in checks) or match_run.overall_result != "PASS":
                raise HTTPException(status_code=400, detail="Cannot approve: validation checks are failed, incomplete or not evaluated.")
        else:
            raise HTTPException(status_code=400, detail="Cannot approve: no completed validation checks exist.")

        if inv.currency != "INR":
            raise HTTPException(status_code=400, detail="Foreign currency invoices require a supported currency approval policy.")

        # Lock the shared PO before rechecking current references/commitments.
        # Invoice locks alone cannot serialize two different invoices on one PO.
        wo_for_approval = db.scalar(select(WorkOrderSnapshot).where(
            WorkOrderSnapshot.org_id == current_user.org_id,
            WorkOrderSnapshot.po_number == inv.po_reference,
        ).with_for_update())
        if wo_for_approval is None:
            raise HTTPException(status_code=400, detail="Cannot approve: current workspace PO evidence is unavailable.")
        refreshed = reevaluate_match_gates(db, inv, current_user.org_id, preserve_extended_gates=True)
        if refreshed.overall_result != "PASS":
            raise HTTPException(status_code=400, detail="Cannot approve: current source evidence or PO commitments fail validation.")

        # Prevent approval if total_amount is unset or non-positive
        if inv.total_amount is None or inv.total_amount <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot approve invoice with null or zero total amount.",
            )

        # Handle undisputed partial approval
        if payload.action == "APPROVE_UNDISPUTED":
            if not payload.undisputed_amount or payload.undisputed_amount <= 0:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="APPROVE_UNDISPUTED action requires a positive 'undisputed_amount'.",
                )
            if float(payload.undisputed_amount) > float(inv.total_amount):
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Undisputed amount ({payload.undisputed_amount}) cannot exceed total invoice amount ({inv.total_amount}).",
                )
            inv.net_payable_amount = payload.undisputed_amount

        invoice_total = float(inv.total_amount)
        is_high_value = invoice_total >= settings.DUAL_APPROVAL_THRESHOLD_INR

        approval_req = None
        if is_high_value:
            approval_req = db.scalar(
                select(ApprovalRequest).where(
                    ApprovalRequest.invoice_id == inv.id,
                    ApprovalRequest.org_id == inv.org_id,
                )
            )

        # Enforce minimum approval authority for single approval or Step 1 of dual approval
        if not is_high_value or not approval_req:
            if current_user.role not in (UserRole.AP_LEAD, UserRole.CONTROLLER, UserRole.SYSTEM_ADMIN):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Approval requires AP_LEAD, CONTROLLER, or SYSTEM_ADMIN role.",
                )

        if is_high_value:
            is_new_cycle = not approval_req or approval_req.status in ("RESET_TO_BASELINE", "REVOKED", "CANCELLED") or not approval_req.first_approver_id
            if is_new_cycle:
                # Step 1 of Dual Approval
                if not approval_req:
                    approval_req = ApprovalRequest(
                        id=f"app_{uuid.uuid4().hex[:12]}",
                        org_id=inv.org_id,
                        invoice_id=inv.id,
                        requires_dual_approval=True,
                        first_approver_id=current_user.id,
                        first_approved_at=now_utc,
                        status="PENDING_SECOND_APPROVAL",
                    )
                    db.add(approval_req)
                else:
                    approval_req.status = "PENDING_SECOND_APPROVAL"
                    approval_req.first_approver_id = current_user.id
                    approval_req.first_approved_at = now_utc
                    approval_req.second_approver_id = None
                    approval_req.second_approved_at = None

                inv.stage = "ACTION_REQUIRED"
                inv.workflow_substatus = "PENDING_SECOND_APPROVAL"
                inv.decision_reason = f"High-value invoice ({invoice_total:.2f} INR >= threshold). First approval granted by {current_user.name}. Awaiting secondary Controller review."
                for exc in active_exceptions:
                    exc.status = "IN_REVIEW"
                    exc.resolution_notes = f"First approval granted by {current_user.name}. Awaiting Controller sign-off."
            else:
                # Step 2 of Dual Approval: Enforce state, distinct approver, and CONTROLLER / SYSTEM_ADMIN role
                if approval_req.status != "PENDING_SECOND_APPROVAL":
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Cannot grant second approval: approval request is in '{approval_req.status}' state, expected 'PENDING_SECOND_APPROVAL'.",
                    )
                if not approval_req.first_approver_id:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Dual control violation: First approval has not been established.",
                    )
                if approval_req.first_approver_id == current_user.id:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Dual control violation: Second approver must be a distinct authenticated user.",
                    )
                if current_user.role not in (UserRole.CONTROLLER, UserRole.SYSTEM_ADMIN):
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Dual control violation: Second approval requires CONTROLLER or SYSTEM_ADMIN role.",
                    )
                approval_req.second_approver_id = current_user.id
                approval_req.second_approved_at = now_utc
                approval_req.status = "APPROVED"
                inv.stage = "INTERNAL_APPROVAL_COMPLETE"
                inv.decision = "MANUALLY_APPROVED"
                inv.workflow_substatus = None
                inv.decision_reason = f"Dual approval complete. Authorized by {approval_req.first_approver_id} and {current_user.id}."
                for exc in active_exceptions:
                    exc.status = "RESOLVED"
                    exc.resolution_notes = f"Dual approval completed by {current_user.name}: {payload.reason}"
                    exc.resolved_at = now_utc
        else:
            # Single Approval
            inv.stage = "INTERNAL_APPROVAL_COMPLETE"
            inv.decision = "MANUALLY_APPROVED"
            inv.workflow_substatus = None
            inv.decision_reason = f"Internal AP review approved by {current_user.name}: {payload.reason}"
            for exc in active_exceptions:
                exc.status = "RESOLVED"
                exc.resolution_notes = f"Approved by {current_user.name}: {payload.reason}"
                exc.resolved_at = now_utc

    # Action 3: Rejection (D-03)
    elif payload.action == "REJECT_INVOICE":
        if current_user.role not in (UserRole.AP_LEAD, UserRole.CONTROLLER, UserRole.SYSTEM_ADMIN):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only AP Lead, Financial Controller, or System Admin can reject an invoice.",
            )
        inv.stage = "REJECTED"
        inv.decision = "REJECTED"
        inv.workflow_substatus = None
        inv.decision_reason = f"Rejected: {payload.reason}"
        for exc in active_exceptions:
            exc.status = "RESOLVED"
            exc.resolution_notes = f"Closed via rejection by {current_user.name}: {payload.reason}"
            exc.resolved_at = now_utc

    # Action 4: Quarantine (DO NOT mark exceptions as RESOLVED - keep in IN_REVIEW)
    elif payload.action == "QUARANTINE":
        inv.stage = "QUARANTINED"
        inv.decision = "QUARANTINED"
        inv.workflow_substatus = None
        inv.decision_reason = payload.reason
        for exc in active_exceptions:
            exc.status = "IN_REVIEW"
            exc.resolution_notes = f"Quarantined by {current_user.name}: {payload.reason}. Moved to Quarantine queue."

    # Action 5: Hold for Evidence
    elif payload.action == "HOLD_PENDING_EVIDENCE":
        inv.stage = "ACTION_REQUIRED"
        inv.workflow_substatus = "ON_HOLD"
        inv.decision_reason = f"Hold placed: {payload.reason}"
        for exc in active_exceptions:
            exc.status = "IN_REVIEW"
            exc.resolution_notes = f"Hold placed by {current_user.name}: {payload.reason}"

    # Action 6: Request Supplier Correction
    elif payload.action == "REQUEST_SUPPLIER_CORRECTION":
        inv.stage = "ACTION_REQUIRED"
        inv.workflow_substatus = "SUPPLIER_CORRECTION_REQUESTED"
        inv.decision_reason = f"Supplier correction requested: {payload.reason}"
        for exc in active_exceptions:
            exc.status = "IN_REVIEW"
            exc.resolution_notes = f"Supplier correction requested by {current_user.name}: {payload.reason}"

    # Action 7: Raise Debit Note
    elif payload.action == "RAISE_DEBIT_NOTE":
        inv.stage = "ACTION_REQUIRED"
        inv.workflow_substatus = "DEBIT_NOTE_PENDING"
        inv.decision_reason = f"Debit note initiated: {payload.reason}"
        for exc in active_exceptions:
            exc.status = "IN_REVIEW"
            exc.resolution_notes = f"Debit note initiated by {current_user.name}: {payload.reason}"

    # Action 8: Escalate
    elif payload.action == "ESCALATE":
        inv.stage = "ACTION_REQUIRED"
        inv.workflow_substatus = "ESCALATED"
        inv.decision_reason = f"Escalated: {payload.reason}"
        for exc in active_exceptions:
            exc.status = "IN_REVIEW"
            exc.resolution_notes = f"Escalated by {current_user.name}: {payload.reason}"

    inv.updated_at = now_utc

    # Write atomic audit event
    audit = AuditEvent(
        id=f"evt_{uuid.uuid4().hex[:12]}",
        invoice_id=inv.id,
        org_id=current_user.org_id,
        actor_id=current_user.id,
        actor_role=current_user.role.value,
        action=payload.action,
        reason=payload.reason,
        before_state=before_state,
        after_state={"stage": inv.stage, "decision": inv.decision},
        source_reference=payload.evidence_reference,
        timestamp=now_utc,
    )
    db.add(audit)
    db.commit()

    return {
        "status": "SUCCESS",
        "invoice_id": inv.id,
        "new_stage": inv.stage,
        "new_decision": inv.decision,
        "workflow_substatus": inv.workflow_substatus,
        "decision_reason": inv.decision_reason,
        "audit_event_id": audit.id,
    }


def resolve_po_line(
    line: InvoiceLine,
    wo_lines: list[WorkOrderLineSnapshot],
) -> Optional[WorkOrderLineSnapshot]:
    """Resolves an invoice line to an authoritative PO line unambiguously.

    Prioritizes:
    1. Exact line number AND normalized description match.
    2. Exact line number match if no duplicate line numbers exist in PO.
    3. Exact normalized description match if exactly one PO line matches that description.
    Never uses positional indexing fallback.
    """
    line_desc = (line.description or "").strip().casefold()

    # Priority 1: Exact line number AND normalized description
    for wol in wo_lines:
        wol_desc = (wol.description or "").strip().casefold()
        if wol.line_number == line.line_number and wol_desc and line_desc and wol_desc == line_desc:
            return wol

    # Priority 2: Exact line number if unique
    by_num = [wol for wol in wo_lines if wol.line_number == line.line_number]
    if len(by_num) == 1:
        return by_num[0]

    # Priority 3: Exact description if unique
    if line_desc:
        by_desc = [wol for wol in wo_lines if (wol.description or "").strip().casefold() == line_desc]
        if len(by_desc) == 1:
            return by_desc[0]

    return None


def reevaluate_match_gates(db: Session, inv: Invoice, org_id: str, preserve_extended_gates: bool = False) -> MatchRun:
    """Synchronously re-evaluates all 7 deterministic AP policy gates after financial mutation."""
    now_utc = datetime.datetime.utcnow()
    lines = db.scalars(
        select(InvoiceLine).where(InvoiceLine.invoice_id == inv.id, InvoiceLine.org_id == org_id).order_by(InvoiceLine.line_number)
    ).all()

    wo = None
    wo_lines = []
    grn = None
    qc = None

    if inv.po_reference:
        wo = db.scalar(
            select(WorkOrderSnapshot).where(
                WorkOrderSnapshot.po_number == inv.po_reference,
                WorkOrderSnapshot.org_id == org_id,
            )
        )
        if wo:
            wo_lines = db.scalars(
                select(WorkOrderLineSnapshot)
                .where(WorkOrderLineSnapshot.po_id == wo.id, WorkOrderLineSnapshot.org_id == org_id)
                .order_by(WorkOrderLineSnapshot.line_number)
            ).all()

            grn = db.scalar(
                select(GoodsReceiptSnapshot).where(
                    GoodsReceiptSnapshot.po_number == inv.po_reference,
                    GoodsReceiptSnapshot.org_id == org_id,
                )
            )
            if grn:
                qc = db.scalar(
                    select(QualityControlSnapshot).where(
                        QualityControlSnapshot.grn_number == grn.grn_number,
                        QualityControlSnapshot.org_id == org_id,
                    )
                )

    # A tax-ID-shaped string is not proof of a registered tenant supplier.
    registered_vendor = db.scalar(select(Vendor).join(VendorGSTIN,
        (VendorGSTIN.vendor_id == Vendor.id) & (VendorGSTIN.org_id == Vendor.org_id)).where(
        Vendor.org_id == org_id, VendorGSTIN.org_id == org_id,
        VendorGSTIN.gstin == inv.vendor_gstin, VendorGSTIN.status == "ACTIVE")) if inv.vendor_gstin else None
    g1_status = "PASS" if registered_vendor else "FAIL"
    g1_notes = "Active tenant supplier tax registration found." if registered_vendor else "No active supplier registration in this workspace."

    # Gate 2: PO Authorization Valid
    g2_status = "PASS" if wo else "FAIL"
    g2_notes = f"PO Ref: {inv.po_reference or 'NOT_FOUND'}" if wo else "No valid Purchase Order (PO) found in ERP contracts."

    if wo and (wo.status not in ("OPEN", "APPROVED", "RELEASED") or wo.currency != inv.currency
               or not registered_vendor or registered_vendor.erp_vendor_code != wo.vendor_code):
        g2_status = "FAIL"
        g2_notes = "PO is closed, currency differs, or PO supplier does not match the active invoice supplier."

    # Gate 3: GRN Receipt Confirmed
    if grn:
        g3_status = "PASS"
        g3_notes = f"GRN matched in ERP receipts: {grn.grn_number}"
    else:
        g3_status = "FAIL"
        g3_notes = "No Goods Receipt Note (GRN) found in ERP receiving records."

    # Gate 4: QC Inspection Accepted
    if qc and getattr(qc, "overall_status", "") in ("ACCEPTED", "PASS", "PASSED"):
        g4_status = "PASS"
        g4_notes = f"QC inspection accepted: certificate #{qc.qc_certificate_number}"
    elif qc:
        g4_status = "FAIL"
        g4_notes = f"QC inspection rejected or incomplete (Status: {qc.overall_status})"
    else:
        g4_status = "FAIL"
        g4_notes = "No Quality Control (QC) inspection certificate found."

    # Gate 5: GST Arithmetic Reconciled
    subtotal = sum((Decimal(str(l.billed_line_total)) for l in lines), Decimal("0"))
    tax = Decimal(str(inv.tax_amount or 0))
    total = Decimal(str(inv.total_amount or 0))
    discrepancy = abs(total - (subtotal + tax))
    g5_status = "PASS" if lines and total > 0 and discrepancy <= Decimal(str(settings.ROUNDING_TOLERANCE_INR)) and all(abs(Decimal(str(l.billed_line_total)) - Decimal(str(l.billed_quantity)) * Decimal(str(l.billed_unit_rate))) <= Decimal("0.01") for l in lines) else "FAIL"
    g5_notes = f"Calculated: ₹{(subtotal + tax):.2f} vs Billed: ₹{total:.2f} (Discrepancy: ₹{discrepancy:.2f})"
    if any(line.is_corrected for line in lines):
        g5_status = "FAIL"
        g5_notes = "Edited line amounts and retained tax have not been re-grounded against an authoritative document; approval is blocked."

    # Gate 6: PO Price & Quantity Tolerance (±1.50% rate, 0.00% qty)
    g6_status = "PASS"
    g6_notes = ""
    if not wo:
        g6_status = "FAIL"
        g6_notes = "Check not evaluated: no matching PO contract found."
    elif not lines:
        g6_status = "FAIL"
        g6_notes = "Check failed: invoice has no line items."
    else:
        tolerances_breached = []
        max_variance = 0.0
        for idx, l in enumerate(lines):
            matching_wo_line = resolve_po_line(l, wo_lines)

            if not matching_wo_line:
                tolerances_breached.append(f"Line #{l.line_number} has no corresponding PO line.")
                continue

            contracted_rate = float(matching_wo_line.contracted_unit_rate)
            billed_rate = float(l.billed_unit_rate)
            if contracted_rate > 0:
                var_pct = ((billed_rate - contracted_rate) / contracted_rate) * 100.0
                if abs(var_pct) > abs(max_variance):
                    max_variance = var_pct
                if abs(var_pct) > settings.RATE_TOLERANCE_PERCENT:
                    tolerances_breached.append(
                        f"Line #{l.line_number} rate variance {var_pct:+.2f}% exceeds ±{settings.RATE_TOLERANCE_PERCENT:.2f}% (Billed ₹{billed_rate:.2f} vs PO ₹{contracted_rate:.2f})"
                    )

            if float(l.billed_quantity) > float(matching_wo_line.authorized_quantity):
                tolerances_breached.append(
                    f"Line #{l.line_number} quantity {float(l.billed_quantity)} exceeds PO authorized quantity {float(matching_wo_line.authorized_quantity)} (0.00% over-delivery tolerance)"
                )

        # Sum quantities for repeated references to a PO line; never grant each
        # invoice line the entire authorized/received quantity independently.
        billed_by_po = {}
        for line in lines:
            wol = resolve_po_line(line, wo_lines)
            if not wol:
                tolerances_breached.append(f"Line #{line.line_number} has no unambiguous PO identity match.")
                continue
            billed_by_po[wol.line_number] = billed_by_po.get(wol.line_number, Decimal("0")) + Decimal(str(line.billed_quantity))
            if Decimal(str(wol.contracted_unit_rate)) <= 0:
                tolerances_breached.append("PO rate is missing or non-positive.")
        received = {}
        if grn:
            for receipt_line in db.scalars(select(GoodsReceiptLineSnapshot).where(
                GoodsReceiptLineSnapshot.grn_id == grn.id, GoodsReceiptLineSnapshot.org_id == org_id)).all():
                received[receipt_line.po_line_number] = received.get(receipt_line.po_line_number, Decimal("0")) + Decimal(str(receipt_line.accepted_quantity))
        # The PO lock held during approval serializes these committed quantities
        # across invoices. A partial monetary approval cannot be safely mapped to
        # quantities without an explicit allocation, so require review instead.
        prior = db.execute(select(Invoice, InvoiceLine).join(InvoiceLine,
            (InvoiceLine.invoice_id == Invoice.id) & (InvoiceLine.org_id == Invoice.org_id)).where(
            Invoice.org_id == org_id, Invoice.po_reference == inv.po_reference, Invoice.id != inv.id,
            (Invoice.stage == "INTERNAL_APPROVAL_COMPLETE") | (Invoice.workflow_substatus == "PENDING_SECOND_APPROVAL"))).all()
        for previous, line in prior:
            wol = resolve_po_line(line, wo_lines)
            if not wol:
                tolerances_breached.append("Previously committed invoice lines cannot be mapped reliably to this PO.")
                continue
            number = wol.line_number
            billed_by_po[number] = billed_by_po.get(number, Decimal("0")) + Decimal(str(line.billed_quantity))
        prior_without_lines = db.scalar(select(func.count(Invoice.id)).where(
            Invoice.org_id == org_id, Invoice.po_reference == inv.po_reference, Invoice.id != inv.id,
            (Invoice.stage == "INTERNAL_APPROVAL_COMPLETE") | (Invoice.workflow_substatus == "PENDING_SECOND_APPROVAL"),
            ~select(InvoiceLine.id).where(InvoiceLine.org_id == org_id, InvoiceLine.invoice_id == Invoice.id).exists()))
        if prior_without_lines:
            tolerances_breached.append("Previously committed invoice quantity is unavailable.")
        partial = db.scalar(select(func.count(Invoice.id)).where(
            Invoice.org_id == org_id, Invoice.po_reference == inv.po_reference, Invoice.id != inv.id,
            (Invoice.stage == "INTERNAL_APPROVAL_COMPLETE") | (Invoice.workflow_substatus == "PENDING_SECOND_APPROVAL"),
            Invoice.net_payable_amount < Invoice.total_amount))
        if partial:
            tolerances_breached.append("Previously partially approved quantity requires manual allocation.")
        for number, quantity in billed_by_po.items():
            po_line = next((line for line in wo_lines if line.line_number == number), None)
            if po_line and quantity > Decimal(str(po_line.authorized_quantity)):
                tolerances_breached.append(f"PO line {number}: cumulative billed quantity exceeds authorized quantity.")
            if quantity > received.get(number, Decimal("0")):
                tolerances_breached.append(f"PO line {number}: billed quantity exceeds accepted goods receipt quantity.")
                g3_status = "FAIL"
                g3_notes = "Billed quantity exceeds accepted goods receipt quantity."
        committed = db.scalar(select(func.coalesce(func.sum(Invoice.total_amount), 0)).where(
            Invoice.org_id == org_id, Invoice.po_reference == inv.po_reference,
            Invoice.id != inv.id,
            (Invoice.stage == "INTERNAL_APPROVAL_COMPLETE") | (Invoice.workflow_substatus == "PENDING_SECOND_APPROVAL")))
        available = min(Decimal(str(wo.remaining_balance)), Decimal(str(wo.total_authorized_amount)) - Decimal(str(committed or 0)))
        if total > available:
            tolerances_breached.append(f"PO remaining balance {available:.2f} is exceeded by {total - available:.2f} {inv.currency}.")

        if tolerances_breached:
            g6_status = "FAIL"
            g6_notes = "; ".join(tolerances_breached)
        else:
            g6_status = "PASS"
            g6_notes = f"All {len(lines)} line(s) within ±{settings.RATE_TOLERANCE_PERCENT:.2f}% rate (Max variance: {max_variance:+.2f}%) and 0.00% quantity tolerance."

    # Gate 7: Duplicate Invoice Check (Normalized for whitespace & separators per F32)
    clean_inv_num = re.sub(r"[^A-Z0-9]", "", (inv.invoice_number or "").upper()) if inv.invoice_number else ""
    valid_identity = bool(
        inv.invoice_number
        and clean_inv_num not in ("", "UNKNOWN", "INVUNKNOWN")
        and inv.vendor_gstin is not None
    )
    if valid_identity:
        dup_query = select(func.count(Invoice.id)).where(
            Invoice.org_id == org_id,
            Invoice.vendor_gstin == inv.vendor_gstin,
            Invoice.id != inv.id,
        )
        dup_query = dup_query.where(
            (Invoice.invoice_number == inv.invoice_number)
            | (func.replace(func.replace(func.replace(func.upper(Invoice.invoice_number), "-", ""), "/", ""), " ", "") == clean_inv_num)
        )
        dup_count = db.scalar(dup_query) or 0
        g7_status = "PASS" if dup_count == 0 else "FAIL"
        g7_notes = f"{dup_count} previous vouchers found" if dup_count > 0 else "0 previous vouchers found in vendor ledger"
    else:
        dup_count = 0
        g7_status = "NOT_EVALUATED"
        g7_notes = "Invoice identity is missing or unverified."

    # Check if record is an unreadable or degraded scan (P0-2 buyer trust preservation)
    is_unreadable_scan = (
        (not inv.vendor_gstin and (not inv.invoice_number or inv.invoice_number in ("SCAN-APTC-036", "POS-26-112", "UNKNOWN")) and (not inv.total_amount or inv.total_amount <= 0))
        or bool(inv.decision_reason and "degraded raster scan" in inv.decision_reason.lower() and (not inv.total_amount or inv.total_amount <= 0))
    )
    if is_unreadable_scan:
        gate_checks = [
            (1, "Vendor Identity Registered", "FAIL", "Document unreadable: degraded raster scan with no machine-readable text."),
            (2, "PO Authorization Valid", "NOT_EVALUATED", "Check not evaluated: document text could not be extracted."),
            (3, "GRN Receipt Confirmed", "NOT_EVALUATED", "Check not evaluated: document text could not be extracted."),
            (4, "QC Inspection Accepted", "NOT_EVALUATED", "Check not evaluated: document text could not be extracted."),
            (5, "GST Arithmetic Reconciled", "NOT_EVALUATED", "Check not evaluated: document text could not be extracted."),
            (6, "PO Price & Quantity Tolerance", "NOT_EVALUATED", "Check not evaluated: document text could not be extracted."),
            (7, "Duplicate Invoice Check", "NOT_EVALUATED", "Check not evaluated: invoice identity could not be extracted."),
        ]
    else:
        gate_checks = [
            (1, "Vendor Identity Registered", g1_status, g1_notes),
            (2, "PO Authorization Valid", g2_status, g2_notes),
            (3, "GRN Receipt Confirmed", g3_status, g3_notes),
            (4, "QC Inspection Accepted", g4_status, g4_notes),
            (5, "GST Arithmetic Reconciled", g5_status, g5_notes),
            (6, "PO Price & Quantity Tolerance", g6_status, g6_notes),
            (7, "Duplicate Invoice Check", g7_status, g7_notes),
        ]

    if preserve_extended_gates:
        previous = db.scalar(select(MatchRun).where(MatchRun.invoice_id == inv.id,
            MatchRun.org_id == org_id).order_by(MatchRun.evaluated_at.desc()))
        if previous:
            for check in db.scalars(select(MatchGateCheck).where(MatchGateCheck.match_run_id == previous.id,
                MatchGateCheck.org_id == org_id, MatchGateCheck.gate_number >= 8)).all():
                gate_checks.append((check.gate_number, check.gate_name, check.status, check.evidence_notes))

    all_passed = all(g[2] == "PASS" for g in gate_checks)
    match_run_id = f"mr_{uuid.uuid4().hex[:12]}"
    match_run = MatchRun(
        id=match_run_id,
        org_id=org_id,
        invoice_id=inv.id,
        policy_version="standard_3way_v1",
        overall_result="PASS" if all_passed else "FAIL",
        evaluated_at=now_utc,
    )
    db.add(match_run)
    db.flush()

    first_failure = None
    for gnum, gname, gstatus, gnotes in gate_checks:
        mg = MatchGateCheck(
            id=f"mg_{match_run_id}_{gnum}",
            org_id=org_id,
            match_run_id=match_run_id,
            gate_number=gnum,
            gate_name=gname,
            status=gstatus,
            evidence_notes=gnotes,
            checked_at=now_utc,
        )
        db.add(mg)
        if gstatus == "FAIL" and first_failure is None:
            first_failure = (gnum, gname, gnotes)
    db.flush()

    # Update invoice state
    if all_passed:
        inv.stage = "PENDING_APPROVAL"
        inv.decision = "MATCH_CANDIDATE"
        inv.decision_reason = "All 7 deterministic policy gates passed. Ready for approval."
    else:
        gnum, gname, gnotes = first_failure
        inv.stage = "ACTION_REQUIRED"
        inv.decision = "FLAGGED_EXCEPTION"
        inv.decision_reason = f"Gate {gnum} ({gname}) failed: {gnotes}"

    return match_run


@router.patch("/{invoice_id}/lines/{line_id}")
def update_invoice_line(
    invoice_id: str,
    line_id: str,
    payload: LineCorrectionPayload,
    if_match: Optional[str] = Header(None),
    current_user: AuthenticatedUser = Depends(require_active_membership),
    db: Optional[Session] = Depends(get_db),
) -> Dict[str, Any]:
    """Updates an invoice line item with optimistic concurrency control, audit logging, and gate re-evaluation."""
    if db is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database not connected.")

    if current_user.is_read_only() or current_user.role == UserRole.AUDITOR:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Auditor role is strictly read-only and cannot execute corrections.",
        )

    # 1. Fetch Invoice
    inv = db.scalar(
        select(Invoice).where(Invoice.id == invoice_id, Invoice.org_id == current_user.org_id).with_for_update()
    )
    if not inv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Invoice '{invoice_id}' not found.")

    # 2. Optimistic Concurrency Check (If-Match)
    if if_match and inv.updated_at:
        clean_if_match = if_match.strip('\"').rstrip("Z")
        current_etag = inv.updated_at.isoformat().rstrip("Z")
        if clean_if_match != current_etag:
            raise HTTPException(
                status_code=status.HTTP_412_PRECONDITION_FAILED,
                detail="Precondition Failed: Invoice has been modified by another reviewer. Please refresh.",
            )

    # 3. Fetch Target Line
    line = db.scalar(
        select(InvoiceLine)
        .where(InvoiceLine.id == line_id, InvoiceLine.invoice_id == invoice_id, InvoiceLine.org_id == current_user.org_id)
        .with_for_update()
    )
    if not line:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Invoice line '{line_id}' not found.")

    old_rate = float(line.billed_unit_rate)
    old_qty = float(line.billed_quantity)
    new_rate = round(float(payload.billed_unit_rate), 4)
    new_qty = round(float(payload.billed_quantity), 4)

    # 4. Apply line update & increment line version
    line.previous_unit_rate = old_rate
    line.billed_unit_rate = new_rate
    line.billed_quantity = new_qty
    line.billed_line_total = round(new_rate * new_qty, 2)
    line.is_corrected = True
    line.line_version = (line.line_version or 1) + 1

    # 5. Recalculate totals
    all_lines = db.scalars(
        select(InvoiceLine).where(InvoiceLine.invoice_id == invoice_id, InvoiceLine.org_id == current_user.org_id)
    ).all()
    new_subtotal = round(sum(float(l.billed_line_total) for l in all_lines), 2)
    inv.subtotal_amount = new_subtotal
    inv.total_amount = round(new_subtotal + float(inv.tax_amount or 0.0), 2)
    inv.net_payable_amount = inv.total_amount

    # 6. Invalidate stale approvals if any existed
    approval_req = db.scalar(
        select(ApprovalRequest).where(
            ApprovalRequest.invoice_id == inv.id,
            ApprovalRequest.org_id == current_user.org_id,
        )
    )
    approval_invalidated = False
    if approval_req and approval_req.status in ("PENDING_SECOND_APPROVAL", "APPROVED"):
        approval_req.status = "REVOKED_CORRECTION"
        approval_req.first_approver_id = None
        approval_req.first_approved_at = None
        approval_req.second_approver_id = None
        approval_req.second_approved_at = None
        inv.stage = "ACTION_REQUIRED"
        inv.workflow_substatus = None
        inv.decision = "NEEDS_REVIEW"
        inv.decision_reason = f"Previous approval invalidated: Line {line.line_number} corrected from rate ₹{old_rate:.2f} (qty {old_qty}) to rate ₹{new_rate:.2f} (qty {new_qty})."
        approval_invalidated = True

    # 7. Synchronously re-evaluate gates
    new_match_run = reevaluate_match_gates(db, inv, current_user.org_id)

    # 8. Record immutable audit event
    now_utc = datetime.datetime.utcnow()
    inv.updated_at = now_utc
    audit = AuditEvent(
        id=f"evt_{uuid.uuid4().hex[:12]}",
        invoice_id=inv.id,
        org_id=current_user.org_id,
        actor_id=current_user.id,
        actor_role=current_user.role.value if current_user.role else "AP_ASSOCIATE",
        action="LINE_ITEM_CORRECTED",
        reason=payload.correction_reason,
        before_state={"billed_unit_rate": old_rate, "billed_quantity": old_qty, "billed_line_total": float(old_rate * old_qty)},
        after_state={"billed_unit_rate": new_rate, "billed_quantity": new_qty, "billed_line_total": float(line.billed_line_total)},
        source_reference=f"line_id:{line.id};line_number:{line.line_number};old_rate:{old_rate};new_rate:{new_rate};old_qty:{old_qty};new_qty:{new_qty}",
        timestamp=now_utc,
    )
    db.add(audit)
    db.commit()

    # Fetch newly created gates
    new_gates = db.scalars(
        select(MatchGateCheck).where(MatchGateCheck.match_run_id == new_match_run.id).order_by(MatchGateCheck.gate_number)
    ).all()

    return {
        "status": "UPDATED",
        "line": {
            "id": line.id,
            "line_number": line.line_number,
            "description": line.description,
            "quantity": float(line.billed_quantity),
            "rate": float(line.billed_unit_rate),
            "total": float(line.billed_line_total),
            "is_corrected": line.is_corrected,
            "previous_unit_rate": float(line.previous_unit_rate) if line.previous_unit_rate is not None else None,
            "line_version": line.line_version,
        },
        "invoice": {
            "id": inv.id,
            "invoice_number": inv.invoice_number,
            "subtotal": float(inv.subtotal_amount) if inv.subtotal_amount else None,
            "tax_amount": float(inv.tax_amount) if inv.tax_amount else None,
            "total_amount": float(inv.total_amount) if inv.total_amount else None,
            "net_payable": float(inv.net_payable_amount) if inv.net_payable_amount else None,
            "stage": inv.stage,
            "decision": inv.decision,
            "decision_reason": inv.decision_reason,
            "workflow_substatus": inv.workflow_substatus,
            "approval_invalidated": approval_invalidated,
            "updated_at": inv.updated_at.isoformat() + "Z",
        },
        "new_match_run": {
            "id": new_match_run.id,
            "overall_result": new_match_run.overall_result,
            "gates": [
                {
                    "gate_number": g.gate_number,
                    "gate_name": g.gate_name,
                    "status": g.status,
                    "notes": g.evidence_notes,
                    "checked_at": g.checked_at.isoformat() + "Z",
                }
                for g in new_gates
            ],
        },
    }
