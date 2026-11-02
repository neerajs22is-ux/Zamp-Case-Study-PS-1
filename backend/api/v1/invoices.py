"""Single Invoice Inspection & Human Exception Action Hub.

Enforces:
1. Three-pane operational view data retrieval.
2. Server-side role checks and atomic audit on every mutation.
3. Dual-control enforcement above monetary threshold (distinct first and second approvers).
4. No fake transitions; internal approvals never claim ERP posting or payment.
"""

from __future__ import annotations

import datetime
import uuid
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.core.auth import AuthenticatedUser, UserRole, require_active_membership, require_role
from backend.core.config import settings
from backend.core.database import get_db
from backend.core.storage import storage_adapter
from backend.models.domain import (
    ApprovalRequest, AuditEvent, Document, ExceptionRecord, ExtractedField, ExtractionRun,
    GoodsReceiptLineSnapshot, GoodsReceiptSnapshot, Invoice, InvoiceLine, MatchGateCheck, MatchRun,
    QualityControlSnapshot, WorkOrderLineSnapshot, WorkOrderSnapshot
)

router = APIRouter(prefix="/invoices", tags=["Invoice Detail & Actions"])


class ActionPayload(BaseModel):
    action: str = Field(..., description="Action name: APPROVE_AP_REVIEW, APPROVE_UNDISPUTED, REJECT_INVOICE, HOLD_PENDING_EVIDENCE, REQUEST_SUPPLIER_CORRECTION, RAISE_DEBIT_NOTE, ESCALATE, QUARANTINE")
    reason: str = Field(..., min_length=3, description="Operational justification for the action")
    undisputed_amount: Optional[float] = Field(None, description="Required for APPROVE_UNDISPUTED")
    evidence_reference: Optional[str] = None


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
            "line_number": l.line_number,
            "description": l.description,
            "quantity": float(l.billed_quantity),
            "rate": float(l.billed_unit_rate),
            "total": float(l.billed_line_total),
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

    inv = db.scalar(select(Invoice).where(Invoice.id == invoice_id, Invoice.org_id == current_user.org_id))
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
        # Strictly prevent approval if any deterministic match gate check failed (D-04 override deferred)
        match_run = db.scalar(
            select(MatchRun)
            .where(MatchRun.invoice_id == inv.id, MatchRun.org_id == current_user.org_id)
            .order_by(MatchRun.evaluated_at.desc())
        )
        if match_run:
            failed_gates = db.scalars(
                select(MatchGateCheck).where(
                    MatchGateCheck.match_run_id == match_run.id,
                    MatchGateCheck.org_id == current_user.org_id,
                    MatchGateCheck.status == "FAIL",
                )
            ).all()
            if failed_gates:
                failed_names = [g.gate_name for g in failed_gates]
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        f"Cannot approve invoice '{invoice_id}': {len(failed_gates)} validation check(s) failed "
                        f"({', '.join(failed_names)}). Policy overrides are disabled. "
                        f"Authorized triage actions: HOLD_PENDING_EVIDENCE, REQUEST_SUPPLIER_CORRECTION, "
                        f"RAISE_DEBIT_NOTE, ESCALATE, REJECT_INVOICE, or QUARANTINE."
                    ),
                )

        invoice_total = float(inv.total_amount or 0.0)
        is_high_value = invoice_total >= settings.DUAL_APPROVAL_THRESHOLD_INR

        if is_high_value:
            approval_req = db.scalar(
                select(ApprovalRequest).where(
                    ApprovalRequest.invoice_id == inv.id,
                    ApprovalRequest.org_id == inv.org_id,
                )
            )
            if not approval_req:
                # Step 1 of Dual Approval
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
                inv.stage = "ACTION_REQUIRED"
                inv.workflow_substatus = "PENDING_SECOND_APPROVAL"
                inv.decision_reason = f"High-value invoice ({invoice_total:.2f} INR >= threshold). First approval granted by {current_user.name}. Awaiting secondary Controller review."
                for exc in active_exceptions:
                    exc.status = "IN_REVIEW"
                    exc.resolution_notes = f"First approval granted by {current_user.name}. Awaiting Controller sign-off."
            else:
                # Step 2 of Dual Approval: Enforce CONTROLLER / SYSTEM_ADMIN role
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
        inv.stage = "ACTION_REQUIRED"
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
