"""System Administration & Evaluation Workspace Controls.

Enforces:
1. Safe resetting of synthetic evaluation fixtures in 'org_sme_eval'.
2. Role authorization (Auditors strictly barred from executing resets).
3. Append-only audit record preserved for all actions.
"""

from __future__ import annotations

import datetime
import uuid
from typing import Any, Dict, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.api.v1.invoices import reevaluate_match_gates
from backend.core.auth import AuthenticatedUser, UserRole, require_active_membership
from backend.core.database import get_db
from backend.core.config import AppEnv, settings
from backend.models.domain import ApprovalRequest, AuditEvent, Invoice, InvoiceLine

router = APIRouter(prefix="/system", tags=["System Administration"])


@router.post("/reset-demo")
def reset_demo_state(
    current_user: AuthenticatedUser = Depends(require_active_membership),
    db: Optional[Session] = Depends(get_db),
) -> Dict[str, Any]:
    """Resets evaluation state for 'org_sme_eval' to baseline fixtures.

    Allows repeated test execution without polluting non-evaluation tenants.
    Preserves audit history while restoring line items and re-evaluating baseline gates.
    """
    if db is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database not connected.")
    if settings.APP_ENV in (AppEnv.PRODUCTION, AppEnv.STAGING):
        raise HTTPException(status_code=403, detail="Demo reset is disabled in production and staging.")

    if current_user.is_read_only() or current_user.role == UserRole.AUDITOR:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Auditor role is strictly read-only and cannot reset demo fixtures.",
        )

    # Restrict demo resets to evaluation tenant
    if current_user.org_id != "org_sme_eval":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Demo fixture reset is only permitted on the evaluation tenant 'org_sme_eval'.",
        )

    now_utc = datetime.datetime.utcnow()

    # 1. Reset any corrected invoice lines back to their previous/unaltered values
    lines = db.scalars(
        select(InvoiceLine).where(InvoiceLine.org_id == current_user.org_id, InvoiceLine.is_corrected == True)
    ).all()

    for line in lines:
        if line.previous_unit_rate is not None:
            line.billed_unit_rate = line.previous_unit_rate
            line.previous_unit_rate = None
            line.billed_line_total = round(float(line.billed_unit_rate) * float(line.billed_quantity), 2)
        line.is_corrected = False
        line.line_version = 1

    # 2. Reset approval requests and re-evaluate gates for all evaluation invoices
    invoices = db.scalars(
        select(Invoice).where(Invoice.org_id == current_user.org_id)
    ).all()

    for inv in invoices:
        all_lines = db.scalars(
            select(InvoiceLine).where(InvoiceLine.invoice_id == inv.id, InvoiceLine.org_id == current_user.org_id)
        ).all()
        if all_lines:
            new_subtotal = round(sum(float(l.billed_line_total) for l in all_lines), 2)
            inv.subtotal_amount = new_subtotal
            inv.total_amount = round(new_subtotal + float(inv.tax_amount or 0.0), 2)
            inv.net_payable_amount = inv.total_amount

        # Clear approvals
        approval_req = db.scalar(
            select(ApprovalRequest).where(ApprovalRequest.invoice_id == inv.id, ApprovalRequest.org_id == current_user.org_id)
        )
        if approval_req:
            approval_req.status = "RESET_TO_BASELINE"
            approval_req.first_approver_id = None
            approval_req.first_approved_at = None
            approval_req.second_approver_id = None
            approval_req.second_approved_at = None

        inv.workflow_substatus = None
        inv.updated_at = now_utc
        # Re-run policy gates
        reevaluate_match_gates(db, inv, current_user.org_id)

    # 3. Log reset audit event
    audit = AuditEvent(
        id=f"evt_{uuid.uuid4().hex[:12]}",
        invoice_id=invoices[0].id if invoices else "system_eval",
        org_id=current_user.org_id,
        actor_id=current_user.id,
        actor_role=current_user.role.value if current_user.role else "CONTROLLER",
        action="EVALUATION_FIXTURES_RESET",
        reason="Reviewer triggered evaluation reset to baseline fixture state.",
        source_reference="system_reset_demo",
        timestamp=now_utc,
    )
    db.add(audit)
    db.commit()

    return {
        "status": "SUCCESS",
        "message": "Evaluation workspace successfully reset to baseline fixtures.",
        "tenant": current_user.org_id,
        "reset_lines_count": len(lines),
        "re_evaluated_invoices_count": len(invoices),
        "timestamp": now_utc.isoformat() + "Z",
    }
