"""Dashboard and Operational Metrics API.

Enforces:
1. Every metric is computed strictly from live database queries.
2. If inputs are missing or unconfigured, status is 'unavailable' with explicit reason (never fake zero).
3. Metric displays 0 only when live query returns 0 rows.
4. Zero invented activity, targets, or simulated throughput.
"""

from __future__ import annotations

import datetime
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from backend.core.auth import AuthenticatedUser, require_active_membership
from backend.core.config import settings
from backend.core.database import get_db
from backend.models.domain import ApprovalRequest, ExceptionRecord, IngestionJob, Invoice, Vendor, VendorGSTIN

router = APIRouter(prefix="/dashboard", tags=["Dashboard Operations"])


@router.get("/metrics")
def get_dashboard_metrics(
    db: Optional[Session] = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_active_membership),
) -> Dict[str, Any]:
    """Calculates live operational metrics from actual database state.

    Requires authentication. Returns truthful calculation metadata.
    """
    now_utc = datetime.datetime.utcnow().isoformat() + "Z"

    if db is None:
        return {
            "status": "unavailable",
            "reason": "Database is not connected. Live metric aggregation requires an active database session.",
            "timestamp": now_utc,
            "timezone": settings.APP_TIMEZONE,
            "metrics": {},
        }

    try:
        org_id = current_user.org_id

        # 1. Total Invoices Received for Tenant
        total_invoices = db.scalar(select(func.count(Invoice.id)).where(Invoice.org_id == org_id)) or 0

        # 2. Stage Breakdown
        stage_counts = dict(
            db.execute(
                select(Invoice.stage, func.count(Invoice.id))
                .where(Invoice.org_id == org_id)
                .group_by(Invoice.stage)
            ).all()
        )

        # 3. Decision Breakdown
        decision_counts = dict(
            db.execute(
                select(Invoice.decision, func.count(Invoice.id))
                .where(Invoice.org_id == org_id)
                .group_by(Invoice.decision)
            ).all()
        )

        # 4. Open Exceptions Count & Blocked Value
        open_exceptions_count = db.scalar(
            select(func.count(ExceptionRecord.id)).where(
                ExceptionRecord.status == "OPEN",
                ExceptionRecord.org_id == org_id,
            )
        ) or 0

        blocked_value = db.scalar(
            select(func.sum(ExceptionRecord.exposure_amount_inr)).join(Invoice,
                (Invoice.id == ExceptionRecord.invoice_id) & (Invoice.org_id == ExceptionRecord.org_id)).where(
                ExceptionRecord.status == "OPEN",
                ExceptionRecord.org_id == org_id,
                Invoice.currency == "INR",
            )
        ) or 0.0
        non_inr_exceptions = db.scalar(select(func.count(ExceptionRecord.id)).join(Invoice,
            (Invoice.id == ExceptionRecord.invoice_id) & (Invoice.org_id == ExceptionRecord.org_id)).where(
            ExceptionRecord.status == "OPEN", ExceptionRecord.org_id == org_id, Invoice.currency != "INR")) or 0

        # 5. MSME Critical Exposure (Eligible payables within statutory horizon)
        msme_exposure_count = db.scalar(
            select(func.count(Invoice.id)).where(
                Invoice.org_id == org_id,
                Invoice.msme_statutory_deadline.isnot(None),
                Invoice.decision == "NEEDS_REVIEW",
            )
        ) or 0

        # 6. Touchless Auto-Approval Rate
        final_decision_count = (decision_counts.get("AUTO_APPROVED", 0) + decision_counts.get("REJECTED", 0))
        auto_approved_count = decision_counts.get("AUTO_APPROVED", 0)
        touchless_rate = (
            round((auto_approved_count / final_decision_count) * 100.0, 2)
            if final_decision_count > 0
            else None
        )

        # 7. Active Ingestion Jobs for Tenant
        active_jobs_count = db.scalar(
            select(func.count(IngestionJob.id)).where(
                IngestionJob.org_id == org_id,
                IngestionJob.status.in_(["QUEUED", "PROCESSING"])
            )
        ) or 0

        # 8. Dedicated Dual-Approval & Ready Counts (B-10)
        pending_second_approval = db.scalar(
            select(func.count(ApprovalRequest.id)).where(
                ApprovalRequest.org_id == org_id,
                ApprovalRequest.status == "PENDING_SECOND_APPROVAL"
            )
        ) or 0

        ready_to_approve = db.scalar(
            select(func.count(Invoice.id)).where(
                Invoice.org_id == org_id,
                Invoice.decision == "MATCH_CANDIDATE",
                Invoice.stage.in_(["PENDING_APPROVAL", "ACTION_REQUIRED"])
            )
        ) or 0

        return {
            "status": "active",
            "timestamp": now_utc,
            "timezone": settings.APP_TIMEZONE,
            "summary": {
                "total_invoices": total_invoices,
                "open_exceptions": open_exceptions_count,
                "blocked_value_inr": float(blocked_value),
                "non_inr_exceptions_excluded": non_inr_exceptions,
                "msme_exposure_count": msme_exposure_count,
                "touchless_rate_pct": touchless_rate,
                "active_ingestion_jobs": active_jobs_count,
                "pending_second_approval": pending_second_approval,
                "ready_to_approve": ready_to_approve,
                "pipeline": {
                    "received": stage_counts.get("RECEIVED", 0),
                    "needs_attention": open_exceptions_count,
                    "ready_to_approve": ready_to_approve,
                    "waiting_second_approval": pending_second_approval,
                    "approved": stage_counts.get("INTERNAL_APPROVAL_COMPLETE", 0),
                }
            },
            "stages": stage_counts,
            "decisions": decision_counts,
            "metric_definitions": {
                "open_exceptions": "Count of unresolved exception records in OPEN status.",
                "blocked_value_inr": "Total net payable amount held in open exception triage.",
                "msme_exposure_count": "Invoices with computed MSMED Act statutory deadlines requiring resolution.",
                "touchless_rate_pct": "Percentage of decided invoices auto-approved without human intervention.",
            },
        }
    except Exception as exc:
        return {
            "status": "unavailable",
            "reason": "Database query error during aggregation. Contact an administrator.",
            "timestamp": now_utc,
            "timezone": settings.APP_TIMEZONE,
            "metrics": {},
        }



@router.get("/exposure")
def get_dashboard_exposure(
    db: Optional[Session] = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_active_membership),
) -> Dict[str, Any]:
    """Executive AP Capital Exposure & Operational Aging Scorecard (OPP-06).

    Strictly separates operational ageing (> 30 days) from verified statutory MSME liabilities.
    """
    if db is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=503, detail="Database not connected; exposure metrics are unavailable.")

    org_id = current_user.org_id
    now = datetime.datetime.utcnow()
    thirty_days_ago = now - datetime.timedelta(days=30)
    net_payable_col = func.coalesce(Invoice.net_payable_amount, Invoice.total_amount, 0.0)
    inv_date_col = func.coalesce(Invoice.invoice_date, Invoice.created_at)

    # 1. Blocked Invoices (in Exception or pending review/approval, not yet cleared or rejected)
    blocked_stmt = select(
        func.coalesce(func.sum(net_payable_col), 0.0),
        func.count(Invoice.id)
    ).where(
        Invoice.org_id == org_id,
        Invoice.currency == "INR",
        Invoice.stage.in_(["ACTION_REQUIRED", "PENDING_APPROVAL", "PENDING_SECOND_APPROVAL", "RECEIVED"]),
        Invoice.stage != "INTERNAL_APPROVAL_COMPLETE",
        Invoice.decision != "REJECTED",
    )
    blocked_sum, blocked_count = db.execute(blocked_stmt).one()

    # 2. Operational Aging (> 30 Days Unsettled)
    aging_stmt = select(
        func.coalesce(func.sum(net_payable_col), 0.0),
        func.count(Invoice.id)
    ).where(
        Invoice.org_id == org_id,
        Invoice.currency == "INR",
        Invoice.stage != "INTERNAL_APPROVAL_COMPLETE",
        Invoice.decision != "REJECTED",
        inv_date_col < thirty_days_ago,
    )
    aging_sum, aging_count = db.execute(aging_stmt).one()

    # 3. Cleared for ERP Posting (Internal Approval Complete)
    cleared_stmt = select(
        func.coalesce(func.sum(net_payable_col), 0.0),
        func.count(Invoice.id)
    ).where(
        Invoice.org_id == org_id,
        Invoice.currency == "INR",
        Invoice.stage == "INTERNAL_APPROVAL_COMPLETE",
    )
    cleared_sum, cleared_count = db.execute(cleared_stmt).one()

    # 4. Verified Statutory MSME §15 Liabilities
    # Only for vendors with verified Udyam number and registered MSME status
    msme_stmt = select(
        func.coalesce(func.sum(net_payable_col), 0.0),
        func.count(Invoice.id)
    ).join(
        VendorGSTIN, and_(VendorGSTIN.gstin == Invoice.vendor_gstin, VendorGSTIN.org_id == Invoice.org_id)
    ).join(
        Vendor, and_(Vendor.id == VendorGSTIN.vendor_id, Vendor.org_id == org_id)
    ).where(
        Invoice.org_id == org_id,
        Invoice.currency == "INR",
        Invoice.stage != "INTERNAL_APPROVAL_COMPLETE",
        Vendor.msme_registered == True,
        Vendor.udyam_number.isnot(None),
    )
    msme_sum, msme_count = db.execute(msme_stmt).one()

    non_inr_count = db.scalar(select(func.count(Invoice.id)).where(Invoice.org_id == org_id, Invoice.currency != "INR")) or 0
    return {
        "total_blocked_liability_inr": float(blocked_sum),
        "blocked_invoices_count": int(blocked_count),
        "operational_aging_over_30_days_inr": float(aging_sum),
        "operational_aging_count": int(aging_count),
        "cleared_for_erp_inr": float(cleared_sum),
        "cleared_invoices_count": int(cleared_count),
        "statutory_msme_verified_due_inr": float(msme_sum),
        "statutory_msme_verified_count": int(msme_count),
        "non_inr_invoices_excluded": int(non_inr_count),
        "statutory_msme_note": "Statutory MSME §15 deadlines displayed only for verified Udyam suppliers. Operational aging reflects standard invoice ageing.",
    }
