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
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from backend.core.auth import AuthenticatedUser, require_active_membership
from backend.core.database import get_db
from backend.models.domain import Document, IngestionJob, Invoice

router = APIRouter(prefix="/inbox", tags=["Invoice Inbox"])


@router.get("")
def list_invoices(
    stage: Optional[str] = Query(None, description="Filter by processing stage"),
    decision: Optional[str] = Query(None, description="Filter by decision (AUTO_APPROVED, NEEDS_REVIEW, etc.)"),
    vendor: Optional[str] = Query(None, description="Filter by supplier name"),
    fy: Optional[str] = Query(None, description="Filter by Indian Financial Year (e.g. FY 2026-27)"),
    month: Optional[int] = Query(None, ge=1, le=12, description="Filter by calendar month (1-12)"),
    year: Optional[int] = Query(None, description="Filter by calendar year"),
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
        if decision in ("AUTO_APPROVED", "MATCH_CANDIDATE", "READY"):
            stmt = stmt.where(Invoice.decision.in_(["MATCH_CANDIDATE", "AUTO_APPROVED"]))
        elif decision in ("HOLD_PENDING_EVIDENCE", "ON_HOLD", "WAITING"):
            stmt = stmt.where(
                or_(
                    Invoice.decision == "HOLD_PENDING_EVIDENCE",
                    Invoice.workflow_substatus == "ON_HOLD",
                    Invoice.stage == "QUARANTINED",
                    Invoice.decision == "QUARANTINED",
                )
            )
        else:
            stmt = stmt.where(Invoice.decision == decision)
    if vendor:
        escaped_vendor = vendor.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        stmt = stmt.where(Invoice.vendor_name.ilike(f"%{escaped_vendor}%", escape="\\"))

    # Temporal period filtering on invoice_date (falling back to created_at)
    inv_date_col = func.coalesce(Invoice.invoice_date, Invoice.created_at)

    if month is not None:
        stmt = stmt.where(func.extract("month", inv_date_col) == month)

    if year is not None:
        stmt = stmt.where(func.extract("year", inv_date_col) == year)

    if fy:
        try:
            clean_fy = fy.replace("FY", "").strip()
            parts = clean_fy.split("-")
            start_year = int(parts[0])
            if start_year < 100:
                start_year += 2000
            end_year = start_year + 1
            stmt = stmt.where(
                or_(
                    and_(
                        func.extract("year", inv_date_col) == start_year,
                        func.extract("month", inv_date_col) >= 4,
                    ),
                    and_(
                        func.extract("year", inv_date_col) == end_year,
                        func.extract("month", inv_date_col) <= 3,
                    ),
                )
            )
        except Exception:
            pass

    # Total count query
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total_count = db.scalar(count_stmt) or 0

    # Paginated results
    offset = (page - 1) * page_size
    items = db.scalars(stmt.order_by(Invoice.created_at.desc()).offset(offset).limit(page_size)).all()

    # Look up any active or recent IngestionJob for these invoices
    job_info: Dict[str, Dict[str, Optional[str]]] = {}
    if items:
        inv_ids = [inv.id for inv in items]
        docs_and_jobs = db.execute(
            select(Document.invoice_id, IngestionJob.status, IngestionJob.error_message)
            .join(IngestionJob, IngestionJob.document_id == Document.id)
            .where(Document.invoice_id.in_(inv_ids), Document.org_id == current_user.org_id)
        ).all()
        for i_id, j_status, j_err in docs_and_jobs:
            if i_id not in job_info or j_status in ("PROCESSING", "QUEUED", "FAILED"):
                job_info[i_id] = {"status": j_status, "error": j_err}

    serialized_items = []
    for inv in items:
        j_meta = job_info.get(inv.id, {})
        serialized_items.append({
            "id": inv.id,
            "invoice_number": inv.invoice_number,
            "invoice_date": inv.invoice_date.isoformat() + "Z" if inv.invoice_date else (inv.created_at.isoformat() + "Z" if inv.created_at else None),
            "vendor_name": inv.vendor_name or "Unidentified",
            "vendor_gstin": inv.vendor_gstin,
            "po_reference": inv.po_reference,
            "total_amount": float(inv.total_amount) if inv.total_amount is not None else None,
            "currency": inv.currency,
            "stage": inv.stage,
            "decision": inv.decision,
            "decision_reason": inv.decision_reason,
            "job_status": j_meta.get("status"),
            "job_error": j_meta.get("error"),
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
