"""Exceptions Priority Queue API.

Enforces:
1. Queue sorted primarily by verified MSME statutory deadline, then exposure amount.
2. Claim and reassign actions are persisted and audited.
3. Snooze never suppresses statutory payment deadlines.
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
from backend.core.database import get_db
from backend.models.domain import AuditEvent, ExceptionRecord, Invoice

router = APIRouter(prefix="/exceptions", tags=["Exceptions Queue"])


class ReassignPayload(BaseModel):
    assigned_user_id: str = Field(..., description="ID of the assigned AP associate/lead")
    reason: str = Field(..., min_length=3)


@router.get("")
def list_exceptions(
    current_user: AuthenticatedUser = Depends(require_active_membership),
    db: Optional[Session] = Depends(get_db),
) -> Dict[str, Any]:
    """Returns the priority-sorted exceptions queue."""
    if db is None:
        return {
            "total_count": 0,
            "items": [],
            "message": "Database not connected. No exception records.",
        }

    stmt = (
        select(ExceptionRecord, Invoice)
        .join(Invoice, ExceptionRecord.invoice_id == Invoice.id)
        .where(ExceptionRecord.status == "OPEN", Invoice.org_id == current_user.org_id)
        .order_by(
            ExceptionRecord.msme_statutory_deadline.asc().nullslast(),
            ExceptionRecord.exposure_amount_inr.desc(),
        )
    )

    rows = db.execute(stmt).all()
    items = []
    for exc, inv in rows:
        items.append({
            "exception_id": exc.id,
            "invoice_id": inv.id,
            "invoice_number": inv.invoice_number,
            "vendor_name": inv.vendor_name,
            "blocking_gate_number": exc.blocking_gate_number,
            "blocking_gate_name": exc.blocking_gate_name,
            "exposure_amount_inr": float(exc.exposure_amount_inr),
            "msme_statutory_deadline": exc.msme_statutory_deadline.isoformat() + "Z" if exc.msme_statutory_deadline else None,
            "assigned_user_id": exc.assigned_user_id,
            "created_at": exc.created_at.isoformat() + "Z",
        })

    return {
        "total_count": len(items),
        "items": items,
    }


@router.post("/{exception_id}/reassign")
def reassign_exception(
    exception_id: str,
    payload: ReassignPayload,
    current_user: AuthenticatedUser = Depends(
        require_role([UserRole.AP_LEAD, UserRole.CONTROLLER, UserRole.SYSTEM_ADMIN])
    ),
    db: Optional[Session] = Depends(get_db),
) -> Dict[str, Any]:
    """Reassigns an exception to another team member and logs audit."""
    if db is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database not connected.")

    exc = db.scalar(
        select(ExceptionRecord).where(
            ExceptionRecord.id == exception_id,
            ExceptionRecord.org_id == current_user.org_id,
        )
    )
    if not exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exception record not found.")

    old_owner = exc.assigned_user_id
    exc.assigned_user_id = payload.assigned_user_id

    # Atomic audit
    audit = AuditEvent(
        id=f"evt_{uuid.uuid4().hex[:12]}",
        invoice_id=exc.invoice_id,
        org_id=current_user.org_id,
        actor_id=current_user.id,
        actor_role=current_user.role.value,
        action="EXCEPTION_REASSIGNED",
        reason=payload.reason,
        before_state={"assigned_user_id": old_owner},
        after_state={"assigned_user_id": payload.assigned_user_id},
    )
    db.add(audit)
    db.commit()

    return {
        "status": "SUCCESS",
        "exception_id": exc.id,
        "assigned_user_id": exc.assigned_user_id,
        "audit_event_id": audit.id,
    }
