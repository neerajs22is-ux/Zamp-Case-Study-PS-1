"""Dedicated Dual-Approval Queue API (Phase 4).

Enforces:
1. Retrieval of invoices requiring single or dual approval scoped to current organization.
2. Server-side computation of whether the current authenticated user can approve:
   - User cannot approve their own first approval (dual control).
   - Second approval strictly requires CONTROLLER or SYSTEM_ADMIN.
   - Auditors are strictly read-only.
   - Failed validation gates block approval.
3. Zero fake approvals; approvals represent internal review sign-off, never ERP posting or bank disbursement.
"""

from __future__ import annotations

import datetime
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.core.auth import AuthenticatedUser, UserRole, require_active_membership
from backend.core.config import settings
from backend.core.database import get_db
from backend.models.domain import ApprovalRequest, Invoice, MatchGateCheck, MatchRun, User

router = APIRouter(prefix="/approvals", tags=["Approvals Queue"])


@router.get("")
def list_approvals(
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by status: PENDING_SECOND_APPROVAL, APPROVED, etc."),
    mine: Optional[bool] = Query(None, description="Filter for items where user is eligible to act"),
    current_user: AuthenticatedUser = Depends(require_active_membership),
    db: Optional[Session] = Depends(get_db),
) -> Dict[str, Any]:
    """Returns the organization's approval requests queue."""
    if db is None:
        return {
            "total_count": 0,
            "items": [],
            "message": "Database not connected. No approval requests available.",
        }

    # Query all approval requests in the user's organization
    stmt = (
        select(ApprovalRequest, Invoice)
        .join(Invoice, ApprovalRequest.invoice_id == Invoice.id)
        .where(
            ApprovalRequest.org_id == current_user.org_id,
            Invoice.org_id == current_user.org_id,
        )
    )

    if status_filter:
        stmt = stmt.where(ApprovalRequest.status == status_filter)

    # Order by priority: high value first, then earliest creation
    stmt = stmt.order_by(
        Invoice.total_amount.desc().nullslast(),
        ApprovalRequest.first_approved_at.asc().nullslast(),
    )

    rows = db.execute(stmt).all()

    # Pre-fetch user full names for approver IDs
    approver_ids = set()
    for req, inv in rows:
        if req.first_approver_id:
            approver_ids.add(req.first_approver_id)
        if req.second_approver_id:
            approver_ids.add(req.second_approver_id)

    user_names = {}
    if approver_ids:
        users = db.scalars(select(User).where(User.id.in_(list(approver_ids)), User.org_id == current_user.org_id)).all()
        for u in users:
            user_names[u.id] = u.full_name or u.email

    items = []
    for req, inv in rows:
        # Check failed gates on the invoice
        match_run = db.scalar(
            select(MatchRun)
            .where(MatchRun.invoice_id == inv.id, MatchRun.org_id == current_user.org_id)
            .order_by(MatchRun.evaluated_at.desc())
        )
        has_failed_gate = False
        failed_gate_names = []
        if match_run:
            failed_gates = db.scalars(
                select(MatchGateCheck).where(
                    MatchGateCheck.match_run_id == match_run.id,
                    MatchGateCheck.org_id == current_user.org_id,
                    MatchGateCheck.status == "FAIL",
                )
            ).all()
            if failed_gates:
                has_failed_gate = True
                failed_gate_names = [g.gate_name for g in failed_gates]

        # Determine if current user can approve this item
        can_approve = True
        cannot_approve_reason = None

        if current_user.is_read_only():
            can_approve = False
            cannot_approve_reason = "Auditor role has read-only oversight permissions."
        elif has_failed_gate:
            can_approve = False
            cannot_approve_reason = f"Approval blocked: {len(failed_gate_names)} validation gate(s) failed ({', '.join(failed_gate_names)}). Overrides (D-04) are disabled."
        elif req.status == "APPROVED":
            can_approve = False
            cannot_approve_reason = "Dual approval is already complete."
        elif req.status == "PENDING_SECOND_APPROVAL":
            # Rule 1: Distinct approvers
            if req.first_approver_id == current_user.id:
                can_approve = False
                cannot_approve_reason = "Dual control policy violation: You rendered the initial approval; second approver must be distinct."
            # Rule 2: Controller or System Admin role
            elif current_user.role not in (UserRole.CONTROLLER, UserRole.SYSTEM_ADMIN):
                can_approve = False
                cannot_approve_reason = "Dual control policy requires Financial Controller or System Admin role for second sign-off."

        item = {
            "id": req.id,
            "invoice_id": inv.id,
            "invoice_number": inv.invoice_number,
            "vendor_name": inv.vendor_name,
            "vendor_gstin": inv.vendor_gstin,
            "po_reference": inv.po_reference,
            "total_amount": float(inv.total_amount) if inv.total_amount else 0.0,
            "currency": inv.currency,
            "stage": inv.stage,
            "decision": inv.decision,
            "requires_dual_approval": req.requires_dual_approval,
            "threshold_inr": settings.DUAL_APPROVAL_THRESHOLD_INR,
            "first_approver_id": req.first_approver_id,
            "first_approver_name": user_names.get(req.first_approver_id, req.first_approver_id),
            "first_approved_at": req.first_approved_at.isoformat() + "Z" if req.first_approved_at else None,
            "second_approver_id": req.second_approver_id,
            "second_approver_name": user_names.get(req.second_approver_id, req.second_approver_id),
            "second_approved_at": req.second_approved_at.isoformat() + "Z" if req.second_approved_at else None,
            "status": req.status,
            "can_approve": can_approve,
            "cannot_approve_reason": cannot_approve_reason,
            "has_failed_gate": has_failed_gate,
            "failed_gates": failed_gate_names,
        }

        if mine is True and not can_approve:
            continue
        items.append(item)

    return {
        "total_count": len(items),
        "threshold_inr": settings.DUAL_APPROVAL_THRESHOLD_INR,
        "items": items,
    }
