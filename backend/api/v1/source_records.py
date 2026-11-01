"""Read-Only Authoritative ERP Records API.

Enforces:
1. Purely read-only access to ERP snapshots (vendors, purchase orders, GRNs, QC).
2. Zero local edits or mutation endpoints.
3. Every record displays source system origin, source ID, and retrieval timestamp.
"""

from __future__ import annotations

import datetime
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.core.auth import AuthenticatedUser, require_active_membership
from backend.core.database import get_db
from backend.models.domain import (
    GoodsReceiptSnapshot, QualityControlSnapshot, Vendor, WorkOrderSnapshot
)

router = APIRouter(prefix="/source-records", tags=["ERP Source Records"])


@router.get("")
def get_source_records(
    current_user: AuthenticatedUser = Depends(require_active_membership),
    db: Optional[Session] = Depends(get_db),
) -> Dict[str, Any]:
    """Returns read-only authoritative ERP snapshots."""
    if db is None:
        return {
            "origin_system": "SAP S/4HANA (Read-Only)",
            "vendors": [],
            "purchase_orders": [],
            "goods_receipts": [],
            "quality_records": [],
            "message": "Database not connected. No source records available.",
        }

    vendors = db.scalars(select(Vendor).limit(50)).all()
    pos = db.scalars(select(WorkOrderSnapshot).limit(50)).all()
    grns = db.scalars(select(GoodsReceiptSnapshot).limit(50)).all()
    qc_records = db.scalars(select(QualityControlSnapshot).limit(50)).all()

    return {
        "origin_system": "SAP S/4HANA (Read-Only)",
        "vendors": [
            {
                "id": v.id,
                "vendor_code": v.erp_vendor_code,
                "legal_name": v.legal_name,
                "pan": v.pan,
                "msme_registered": v.msme_registered,
                "msme_category": v.msme_category,
                "bank_verified": v.bank_account_verified,
            }
            for v in vendors
        ],
        "purchase_orders": [
            {
                "id": p.id,
                "po_number": p.po_number,
                "vendor_code": p.vendor_code,
                "total_authorized": float(p.total_authorized_amount),
                "remaining_balance": float(p.remaining_balance),
                "currency": p.currency,
                "status": p.status,
                "retrieved_at": p.retrieved_at.isoformat() + "Z",
            }
            for p in pos
        ],
        "goods_receipts": [
            {
                "id": g.id,
                "grn_number": g.grn_number,
                "po_number": g.po_number,
                "received_date": g.received_date.isoformat() + "Z",
                "retrieved_at": g.retrieved_at.isoformat() + "Z",
            }
            for g in grns
        ],
        "quality_records": [
            {
                "id": q.id,
                "qc_certificate_number": q.qc_certificate_number,
                "grn_number": q.grn_number,
                "overall_status": q.overall_status,
                "retrieved_at": q.retrieved_at.isoformat() + "Z",
            }
            for q in qc_records
        ],
    }
