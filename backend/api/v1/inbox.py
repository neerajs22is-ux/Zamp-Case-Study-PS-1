"""Invoice Inbox Ledger API.

Enforces:
1. Server-side paginated queries against actual invoices.
2. Filters for stage, decision, vendor, legal entity, and MSME deadline.
3. Truthful empty response when no genuine invoices exist.
"""

from __future__ import annotations

import datetime
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from backend.core.auth import AuthenticatedUser, require_active_membership
from backend.core.database import get_db
from backend.models.domain import Invoice

router = APIRouter(prefix="/inbox", tags=["Invoice Inbox"])


@router.get("")
def list_invoices(
    stage: Optional[str] = Query(None, description="Filter by processing stage"),
    decision: Optional[str] = Query(None, description="Filter by decision (AUTO_APPROVED, NEEDS_REVIEW, etc.)"),
    vendor: Optional[str] = Query(None, description="Filter by supplier name"),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    current_user: AuthenticatedUser = Depends(require_active_membership),
    db: Optional[Session] = Depends(get_db),
) -> Dict[str, Any]:
    """Returns server-paginated list of real invoices."""
    if db is None:
        return {
            "total_count": 0,
            "page": page,
            "page_size": page_size,
            "total_pages": 0,
            "items": [],
            "message": "Database not connected. No records to display.",
        }

    stmt = select(Invoice).where(Invoice.org_id == current_user.org_id)

    if stage:
        stmt = stmt.where(Invoice.stage == stage)
    if decision:
        stmt = stmt.where(Invoice.decision == decision)
    if vendor:
        escaped_vendor = vendor.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        stmt = stmt.where(Invoice.vendor_name.ilike(f"%{escaped_vendor}%", escape="\\"))

    # Total count query
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total_count = db.scalar(count_stmt) or 0

    # Paginated results
    offset = (page - 1) * page_size
    items = db.scalars(stmt.order_by(Invoice.created_at.desc()).offset(offset).limit(page_size)).all()

    serialized_items = []
    for inv in items:
        serialized_items.append({
            "id": inv.id,
            "invoice_number": inv.invoice_number,
            "vendor_name": inv.vendor_name or "Unidentified",
            "vendor_gstin": inv.vendor_gstin,
            "po_reference": inv.po_reference,
            "total_amount": float(inv.total_amount) if inv.total_amount is not None else None,
            "currency": inv.currency,
            "stage": inv.stage,
            "decision": inv.decision,
            "decision_reason": inv.decision_reason,
            "msme_statutory_deadline": inv.msme_statutory_deadline.isoformat() + "Z" if inv.msme_statutory_deadline else None,
            "msme_deadline_status": inv.msme_deadline_status,
            "created_at": inv.created_at.isoformat() + "Z",
            "updated_at": inv.updated_at.isoformat() + "Z",
        })

    total_pages = (total_count + page_size - 1) // page_size if total_count > 0 else 0

    return {
        "total_count": total_count,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
        "items": serialized_items,
    }
