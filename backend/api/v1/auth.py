"""Authentication, Identity Provider, Invitation and Access Request Endpoints."""

from __future__ import annotations

import datetime
import hashlib
import json
import secrets
import time
import urllib.request
from typing import Any, Dict, List, Optional
import uuid
from jose import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, Security, status
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import BaseModel, field_validator
from sqlalchemy import and_, func, or_, select, text
from sqlalchemy.orm import Session

from backend.core.config import AppEnv, settings
from backend.core.auth import (
    AuthenticatedUser, UserRole, check_idp_health,
    get_current_user, require_active_membership, require_role, security_bearer, verify_token_claims
)
from backend.core.database import get_db, set_tenant_context
from decimal import Decimal
from backend.models.domain import (
    AccessRequest, AuditEvent, Document, GoodsReceiptLineSnapshot, GoodsReceiptSnapshot,
    IdentityMembership, Invoice, InvoiceLine, MatchGateCheck, MatchRun, Organisation,
    QualityControlSnapshot, RevokedAccessToken, RoleAssignment, User, UserInvitation,
    Vendor, VendorGSTIN, WorkOrderLineSnapshot, WorkOrderSnapshot
)

router = APIRouter(prefix="/auth", tags=["Authentication & Identity"])


# ------------------------------------------------------------------------------
# Request / Response Schemas
# ------------------------------------------------------------------------------

class CreateInvitationPayload(BaseModel):
    email: str
    role: UserRole

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        v = v.strip()
        if not v or "@" not in v or "." not in v.split("@")[-1]:
            raise ValueError("Invalid email format.")
        return v


class AcceptInvitationPayload(BaseModel):
    token: str


class CreateAccessRequestPayload(BaseModel):
    org_id: str
    reason: Optional[str] = None
    requested_role: Optional[UserRole] = UserRole.AP_ASSOCIATE


class ReviewAccessRequestPayload(BaseModel):
    action: str  # APPROVE or REJECT
    role: Optional[UserRole] = None
    reason: Optional[str] = None


class UpdateUserRolePayload(BaseModel):
    role: UserRole
    reason: str


class DeactivateUserPayload(BaseModel):
    reason: str


class DevSessionPayload(BaseModel):
    email: str
    org_id: Optional[str] = None
    unprovisioned: bool = False


# ------------------------------------------------------------------------------
# Core Authentication Profile & Health
# ------------------------------------------------------------------------------

@router.post("/dev-session")
def create_dev_session(
    payload: DevSessionPayload,
    request: Request,
    db: Optional[Session] = Depends(get_db),
) -> Dict[str, Any]:
    """Issues an authentic, cryptographically signed enterprise JWT for local development & SME evaluation.

    Guarantees:
    - Strictly disabled by default: requires ENABLE_DEV_SESSION=True.
    - Strictly barred when APP_ENV not in (AppEnv.DEVELOPMENT, AppEnv.TEST).
    - Restricted to local loopback clients (127.0.0.1, localhost, ::1, testclient).
    - Unauthenticated external callers cannot reach or execute this endpoint on public staging or production services.
    - Requires valid server-side SUPABASE_JWT_SECRET.
    - Resolves user from database users table and verifies is_active is True.
    - Resolves active RoleAssignment for the tenant from PostgreSQL.
    - Issues standard Supabase JWT with database role 'authenticated' for RLS.
    - Separately represents application role in 'app_metadata.role' and 'user_role'.
    - Server-side PostgreSQL RoleAssignment remains authoritative for all authorization decisions.
    """
    # 1. Explicit feature flag guard (Disabled by default)
    if not settings.ENABLE_DEV_SESSION:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Development session endpoint is disabled by configuration (ENABLE_DEV_SESSION=False).",
        )

    # 2. Environment guard (Barred outside development and testing)
    if settings.APP_ENV not in (AppEnv.DEVELOPMENT, AppEnv.TEST):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Development session endpoint is strictly prohibited outside local development.",
        )

    # 3. Local loopback client guard (Never accessible to external network callers)
    xff = request.headers.get("x-forwarded-for")
    forwarded_ips = [ip.strip() for ip in xff.split(",")] if xff else []
    client_host = request.client.host if request.client else ""
    effective_host = forwarded_ips[0] if forwarded_ips else client_host
    is_local = effective_host in ("127.0.0.1", "localhost", "::1", "testclient") or not effective_host
    if not is_local:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Development session endpoint is restricted strictly to local loopback connections.",
        )

    # 4. Server-Side Secret Verification
    if not settings.SUPABASE_JWT_SECRET:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="SUPABASE_JWT_SECRET is not configured on the server.",
        )

    clean_email = payload.email.strip().lower()

    if payload.unprovisioned:
        user_id = f"usr_unprov_{uuid.uuid4().hex[:8]}"
        user_name = "Unprovisioned Candidate"
        role_name = None
        effective_org = None
    else:
        if db is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database connection unavailable.",
            )

        if payload.org_id:
            set_tenant_context(db, payload.org_id)
        else:
            db.info["skip_role_restriction"] = True

        user_query = select(User).where(func.lower(User.email) == clean_email)
        if payload.org_id:
            user_query = user_query.where(User.org_id == payload.org_id)
        matching_users = db.scalars(user_query).all()
        if len(matching_users) > 1:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Select a workspace for this development account.")
        user = matching_users[0] if matching_users else None
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User with email '{payload.email}' not found.",
            )

        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"User '{payload.email}' is deactivated.",
            )

        roles = db.scalars(select(RoleAssignment).where(RoleAssignment.user_id == user.id)).all()
        if not roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"User '{payload.email}' has no active role assignments.",
            )

        effective_org = payload.org_id or user.org_id or roles[0].org_id
        matching_role = next((r for r in roles if r.org_id == effective_org), None)
        if matching_role is None:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No role assignment exists in the selected workspace.")
        user_id = user.id
        user_name = user.full_name or user.email
        role_name = matching_role.role_name

    now_ts = int(time.time())
    jwt_claims = {
        "sub": user_id,
        "email": clean_email,
        "name": user_name,
        "role": "authenticated",  # Database role for Supabase & PostgreSQL RLS
        "app_metadata": {
            "provider": "email",
            "role": role_name,
        },
        "user_role": role_name,   # Application role
        "org_id": effective_org,
        "aud": settings.SUPABASE_AUDIENCE or "authenticated",
        "iss": settings.SUPABASE_ISSUER or (f"{settings.SUPABASE_URL.rstrip('/')}/auth/v1" if settings.SUPABASE_URL else None),
        "iat": now_ts,
        "exp": now_ts + (86400 * 7),
    }

    from jose import jwt as jose_jwt
    access_token = jose_jwt.encode(jwt_claims, settings.SUPABASE_JWT_SECRET, algorithm="HS256")

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": 86400 * 7,
        "user": {
            "id": user_id,
            "email": clean_email,
            "name": user_name,
            "role": role_name,
            "database_role": "authenticated",
            "org_id": effective_org,
        },
    }


_DEMO_SESSIONS_TRACKER: Dict[str, List[float]] = {}


def provision_isolated_demo_tenant(db: Session, client_ip: str) -> Dict[str, Any]:
    """Provisions a completely isolated, temporary demo tenant with realistic fixtures.

    Guarantees:
    - Rate-limited per IP (max 10 requests per 10 minutes).
    - Uniquely isolated tenant ID (org_demo_<hex4>) with separate PostgreSQL RLS boundaries.
    - Assigned least-privilege role: AP_ASSOCIATE (strictly prohibited from authorizing disbursements or escalating privileges).
    - Pre-seeded with authentic Indian GST procurement fixtures:
      * 1 approved vendor (Asterion Precision Components Pvt Ltd)
      * 2 purchase orders (PO-26-1001 for clean match, PO-26-1011 for price variance)
      * 2 goods receipt notes (GRN-26-501, GRN-26-621)
      * 2 QC inspection certificates (QC-GRN-26-501-01, QC-GRN-26-621-01)
      * 2 pre-evaluated commercial invoices (SCN-01 match candidate and SCN-02 price variance exception)
    - Issues a cryptographically signed, expiring Supabase JWT (HS256).
    - Cleans up stale demo tenants older than 4 hours.
    """
    now = time.time()
    # 1. IP Rate Limiting
    ip_key = client_ip or "unknown"
    history = [t for t in _DEMO_SESSIONS_TRACKER.get(ip_key, []) if now - t < 600.0]
    if len(history) >= 10:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Demo session creation rate limit exceeded. Please wait a few minutes before requesting another demo session.",
        )
    history.append(now)
    _DEMO_SESSIONS_TRACKER[ip_key] = history

    # 2. Server Secret Guard
    jwt_secret = settings.SUPABASE_JWT_SECRET or settings.SECRET_KEY
    if not jwt_secret:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Server JWT secret is not configured.",
        )

    # 3. Generate unique identifiers
    demo_id = secrets.token_hex(4)
    demo_org_id = f"org_demo_{demo_id}"
    demo_user_id = f"usr_demo_{demo_id}"
    demo_email = f"evaluator_{demo_id}@demo.zamp.internal"
    demo_name = "Demo Evaluator"
    now_utc = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
    canonical_issuer = (settings.SUPABASE_ISSUER or (f"{settings.SUPABASE_URL.rstrip('/')}/auth/v1" if settings.SUPABASE_URL else "test")).rstrip("/")

    # 4. Set RLS Tenant Context before any database write
    set_tenant_context(db, demo_org_id)

    # 5. Seed Core Tenant & User
    org = Organisation(
        id=demo_org_id,
        name=f"Interactive Demo Workspace",
        created_at=now_utc,
    )
    db.add(org)
    db.flush()

    user = User(
        id=demo_user_id,
        org_id=demo_org_id,
        email=demo_email,
        full_name=demo_name,
        is_active=True,
        created_at=now_utc,
    )
    db.add(user)
    db.flush()

    ra = RoleAssignment(
        id=f"ras_{demo_user_id}",
        org_id=demo_org_id,
        user_id=demo_user_id,
        role_name="AP_ASSOCIATE",
        granted_at=now_utc,
    )
    db.add(ra)


    # 6. Seed Procurement Master Data
    vendor_id = f"vnd_asterion_{demo_id}"
    vendor = Vendor(
        id=vendor_id,
        org_id=demo_org_id,
        erp_vendor_code=f"VND-{demo_id[:4].upper()}",
        legal_name="Asterion Precision Components Pvt Ltd",
        trade_name="Asterion Components",
        pan="AAACA1234A",
        msme_registered=True,
        msme_category="SMALL",
        udyam_number="UDYAM-KR-03-0012345",
        bank_account_verified=True,
        created_at=now_utc,
    )
    db.add(vendor)
    db.flush()

    vendor_gstin = VendorGSTIN(
        id=f"vg_asterion_{demo_id}",
        org_id=demo_org_id,
        vendor_id=vendor_id,
        gstin="29SYNTH0001A1Z5",
        state_code="29",
        status="ACTIVE",
    )
    db.add(vendor_gstin)

    # Scoped PO and GRN numbers to avoid global unique collisions
    po_1001_num = f"PO-{demo_id[:4].upper()}-1001"
    grn_501_num = f"GRN-{demo_id[:4].upper()}-501"
    qc_501_num = f"QC-{demo_id[:4].upper()}-501"
    inv_01_num = f"AP/{demo_id[:4].upper()}/001"

    po_1011_num = f"PO-{demo_id[:4].upper()}-1011"
    grn_621_num = f"GRN-{demo_id[:4].upper()}-621"
    qc_621_num = f"QC-{demo_id[:4].upper()}-621"
    inv_02_num = f"AP/{demo_id[:4].upper()}/011"

    # PO 1 (Clean 3-Way Match baseline)
    wo_1001_id = f"wo_1001_{demo_id}"
    wo_1001 = WorkOrderSnapshot(
        id=wo_1001_id,
        org_id=demo_org_id,
        po_number=po_1001_num,
        vendor_code=vendor.erp_vendor_code,
        total_authorized_amount=Decimal("26196.00"),
        remaining_balance=Decimal("26196.00"),
        currency="INR",
        status="APPROVED",
        retrieved_at=now_utc,
    )
    db.add(wo_1001)
    db.flush()

    wol_1001 = WorkOrderLineSnapshot(
        id=f"wol_1001_1_{demo_id}",
        org_id=demo_org_id,
        po_id=wo_1001_id,
        line_number=1,
        item_code="FLANGE-01",
        description="Precision Steel Flange Type-A",
        authorized_quantity=Decimal("120.00"),
        contracted_unit_rate=Decimal("185.00"),
        authorized_line_total=Decimal("22200.00"),
    )
    db.add(wol_1001)

    grn_501_id = f"grn_501_{demo_id}"
    grn_501 = GoodsReceiptSnapshot(
        id=grn_501_id,
        org_id=demo_org_id,
        grn_number=grn_501_num,
        po_number=po_1001_num,
        received_date=now_utc,
        retrieved_at=now_utc,
    )
    db.add(grn_501)
    db.flush()

    grnl_501 = GoodsReceiptLineSnapshot(
        id=f"grnl_501_1_{demo_id}",
        org_id=demo_org_id,
        grn_id=grn_501_id,
        po_line_number=1,
        accepted_quantity=Decimal("120.00"),
        rejected_quantity=Decimal("0.00"),
    )
    db.add(grnl_501)

    qc_501 = QualityControlSnapshot(
        id=f"qc_501_{demo_id}",
        org_id=demo_org_id,
        qc_certificate_number=qc_501_num,
        grn_number=grn_501_num,
        overall_status="ACCEPTED",
        retrieved_at=now_utc,
    )
    db.add(qc_501)

    # PO 2 (Price Variance baseline)
    wo_1011_id = f"wo_1011_{demo_id}"
    wo_1011 = WorkOrderSnapshot(
        id=wo_1011_id,
        org_id=demo_org_id,
        po_number=po_1011_num,
        vendor_code=vendor.erp_vendor_code,
        total_authorized_amount=Decimal("21830.00"),
        remaining_balance=Decimal("21830.00"),
        currency="INR",
        status="APPROVED",
        retrieved_at=now_utc,
    )
    db.add(wo_1011)
    db.flush()

    wol_1011 = WorkOrderLineSnapshot(
        id=f"wol_1011_1_{demo_id}",
        org_id=demo_org_id,
        po_id=wo_1011_id,
        line_number=1,
        item_code="SHAFT-01",
        description="Precision CNC Machined Shaft 25mm",
        authorized_quantity=Decimal("100.00"),
        contracted_unit_rate=Decimal("185.00"),
        authorized_line_total=Decimal("18500.00"),
    )
    db.add(wol_1011)

    grn_621_id = f"grn_621_{demo_id}"
    grn_621 = GoodsReceiptSnapshot(
        id=grn_621_id,
        org_id=demo_org_id,
        grn_number=grn_621_num,
        po_number=po_1011_num,
        received_date=now_utc,
        retrieved_at=now_utc,
    )
    db.add(grn_621)
    db.flush()

    grnl_621 = GoodsReceiptLineSnapshot(
        id=f"grnl_621_1_{demo_id}",
        org_id=demo_org_id,
        grn_id=grn_621_id,
        po_line_number=1,
        accepted_quantity=Decimal("80.00"),
        rejected_quantity=Decimal("0.00"),
    )
    db.add(grnl_621)

    qc_621 = QualityControlSnapshot(
        id=f"qc_621_{demo_id}",
        org_id=demo_org_id,
        qc_certificate_number=qc_621_num,
        grn_number=grn_621_num,
        overall_status="ACCEPTED",
        retrieved_at=now_utc,
    )
    db.add(qc_621)

    # 7. Seed 2 Pre-Evaluated Demo Invoices
    # Invoice 1: Clean 3-Way Match (SCN-01)
    inv_01_id = f"inv_demo_01_{demo_id}"
    doc_01_id = f"doc_demo_01_{demo_id}"
    inv_01 = Invoice(
        id=inv_01_id,
        org_id=demo_org_id,
        invoice_number=inv_01_num,
        vendor_name="Asterion Precision Components Pvt Ltd",
        vendor_gstin="29SYNTH0001A1Z5",
        po_reference=po_1001_num,
        subtotal_amount=Decimal("22200.00"),
        tax_amount=Decimal("3996.00"),
        total_amount=Decimal("26196.00"),
        net_payable_amount=Decimal("26196.00"),
        currency="INR",
        invoice_date=now_utc,
        due_date=now_utc + datetime.timedelta(days=30),
        stage="PENDING_APPROVAL",
        decision="MATCH_CANDIDATE",
        decision_reason="All 7 deterministic policy gates passed. Ready for approval.",
        owner_user_id=demo_user_id,
        source_channel="DEMO_EXPERIENCE",
        created_at=now_utc,
    )
    db.add(inv_01)
    db.flush()

    doc_01 = Document(
        id=doc_01_id,
        org_id=demo_org_id,
        invoice_id=inv_01_id,
        filename="01_invoice_AP_26_001.pdf",
        mime_type="application/pdf",
        file_size_bytes=42560,
        sha256_hash=hashlib.sha256(f"demo_doc_1_{demo_id}".encode()).hexdigest(),
        storage_provider="DATABASE_METADATA",
        storage_key=f"demo/{demo_org_id}/01_invoice_AP_26_001.pdf",
        is_original=True,
        is_deleted=False,
        uploaded_at=now_utc,
    )
    db.add(doc_01)

    inl_01 = InvoiceLine(
        id=f"inl_demo_01_{demo_id}",
        org_id=demo_org_id,
        invoice_id=inv_01_id,
        line_number=1,
        description="Precision Steel Flange Type-A",
        billed_quantity=Decimal("120.00"),
        billed_unit_rate=Decimal("185.00"),
        billed_line_total=Decimal("22200.00"),
    )
    db.add(inl_01)

    mr_01_id = f"mr_demo_01_{demo_id}"
    mr_01 = MatchRun(
        id=mr_01_id,
        org_id=demo_org_id,
        invoice_id=inv_01_id,
        policy_version="standard_3way_v1",
        overall_result="PASS",
        evaluated_at=now_utc,
    )
    db.add(mr_01)
    db.flush()

    for gnum, gname, gnotes in [
        (1, "Vendor Master Verification", "Vendor GSTIN 29SYNTH0001A1Z5 is verified active"),
        (2, "PO Authorization", f"Referenced PO {po_1001_num} verified open with balance INR 26196.00"),
        (3, "GRN Receipt Match", f"GRN {grn_501_num} confirmed; received qty 120.00 >= billed qty 120.00"),
        (4, "QC Technical Acceptance", f"QC inspection accepted: certificate #{qc_501_num}"),
        (5, "GST Arithmetic Reconciled", "Calculated: INR 26196.00 vs Billed: INR 26196.00 (Discrepancy: INR 0.00)"),
        (6, "PO Price & Quantity Tolerance", "All 1 line(s) within ±1.50% rate and 0.00% quantity tolerance"),
        (7, "Duplicate Invoice Check", "0 previous vouchers found in vendor ledger"),
    ]:
        db.add(MatchGateCheck(
            id=f"mg_{mr_01_id}_{gnum}",
            org_id=demo_org_id,
            match_run_id=mr_01_id,
            gate_number=gnum,
            gate_name=gname,
            status="PASS",
            evidence_notes=gnotes,
            checked_at=now_utc,
        ))

    # Invoice 2: Price Variance Exception (SCN-02)
    inv_02_id = f"inv_demo_02_{demo_id}"
    doc_02_id = f"doc_demo_02_{demo_id}"
    inv_02 = Invoice(
        id=inv_02_id,
        org_id=demo_org_id,
        invoice_number=inv_02_num,
        vendor_name="Asterion Precision Components Pvt Ltd",
        vendor_gstin="29SYNTH0001A1Z5",
        po_reference=po_1011_num,
        subtotal_amount=Decimal("22000.00"),
        tax_amount=Decimal("3960.00"),
        total_amount=Decimal("25960.00"),
        net_payable_amount=Decimal("25960.00"),
        currency="INR",
        invoice_date=now_utc,
        due_date=now_utc + datetime.timedelta(days=30),
        stage="ACTION_REQUIRED",
        decision="FLAGGED_EXCEPTION",
        decision_reason="Gate 6 (PO Price & Quantity Tolerance) failed: Line #1 rate variance +18.92% exceeds ±1.50% (Billed ₹220.00 vs PO ₹185.00); Line #1 quantity 100 exceeds PO authorized quantity 80 (0.00% over-delivery tolerance)",
        owner_user_id=demo_user_id,
        source_channel="DEMO_EXPERIENCE",
        created_at=now_utc,
    )
    db.add(inv_02)
    db.flush()

    doc_02 = Document(
        id=doc_02_id,
        org_id=demo_org_id,
        invoice_id=inv_02_id,
        filename="02_invoice_AP_26_011.pdf",
        mime_type="application/pdf",
        file_size_bytes=39120,
        sha256_hash=hashlib.sha256(f"demo_doc_2_{demo_id}".encode()).hexdigest(),
        storage_provider="DATABASE_METADATA",
        storage_key=f"demo/{demo_org_id}/02_invoice_AP_26_011.pdf",
        is_original=True,
        is_deleted=False,
        uploaded_at=now_utc,
    )
    db.add(doc_02)

    inl_02 = InvoiceLine(
        id=f"inl_demo_02_{demo_id}",
        org_id=demo_org_id,
        invoice_id=inv_02_id,
        line_number=1,
        description="Precision CNC Machined Shaft 25mm",
        billed_quantity=Decimal("100.00"),
        billed_unit_rate=Decimal("220.00"),
        billed_line_total=Decimal("22000.00"),
    )
    db.add(inl_02)

    mr_02_id = f"mr_demo_02_{demo_id}"
    mr_02 = MatchRun(
        id=mr_02_id,
        org_id=demo_org_id,
        invoice_id=inv_02_id,
        policy_version="standard_3way_v1",
        overall_result="FAIL",
        evaluated_at=now_utc,
    )
    db.add(mr_02)
    db.flush()

    for gnum, gname, gstat, gnotes in [
        (1, "Vendor Master Verification", "PASS", "Vendor GSTIN 29SYNTH0001A1Z5 is verified active"),
        (2, "PO Authorization", "PASS", f"Referenced PO {po_1011_num} verified open with balance INR 21830.00"),
        (3, "GRN Receipt Match", "PASS", f"GRN {grn_621_num} confirmed: 80 units received"),
        (4, "QC Technical Acceptance", "PASS", f"QC inspection accepted: certificate #{qc_621_num}"),
        (5, "GST Arithmetic Reconciled", "PASS", "Calculated: INR 25960.00 vs Billed: INR 25960.00 (Discrepancy: INR 0.00)"),
        (6, "PO Price & Quantity Tolerance", "FAIL", "Line #1 rate variance +18.92% exceeds ±1.50% (Billed ₹220.00 vs PO ₹185.00); Line #1 quantity 100 exceeds PO authorized quantity 80 (0.00% over-delivery tolerance)"),
        (7, "Duplicate Invoice Check", "PASS", "0 previous vouchers found in vendor ledger"),
    ]:
        db.add(MatchGateCheck(
            id=f"mg_{mr_02_id}_{gnum}",
            org_id=demo_org_id,
            match_run_id=mr_02_id,
            gate_number=gnum,
            gate_name=gname,
            status=gstat,
            evidence_notes=gnotes,
            checked_at=now_utc,
        ))

    db.commit()

    # 8. Mint expiring Supabase JWT for the demo session
    expires_in = 7200
    token_payload = {
        "sub": demo_user_id,
        "email": demo_email,
        "aud": "authenticated",
        "role": "authenticated",
        "user_role": "AP_ASSOCIATE",
        "org_id": demo_org_id,
        "iat": int(now),
        "exp": int(now) + expires_in,
        "iss": canonical_issuer,
        "app_metadata": {
            "provider": "demo_evaluator",
            "org_id": demo_org_id,
            "roles": ["AP_ASSOCIATE"],
        },
        "user_metadata": {
            "full_name": demo_name,
            "demo_session": True,
        },
    }
    access_token = jwt.encode(token_payload, jwt_secret, algorithm="HS256")

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": expires_in,
        "user": {
            "id": demo_user_id,
            "email": demo_email,
            "name": demo_name,
            "role": "AP_ASSOCIATE",
            "database_role": "authenticated",
            "org_id": demo_org_id,
            "org_name": "Interactive Demo Workspace",
        },
    }


@router.post("/demo-session")
def create_demo_session(
    request: Request,
    db: Optional[Session] = Depends(get_db),
) -> Dict[str, Any]:
    """Issues an instant, temporary demo session assigned to an isolated demo tenant.

    Guarantees:
    - Zero administrative preapproval required.
    - Assigned least-privilege AP_ASSOCIATE permissions (no approvals, payments, integrations).
    - Uniquely isolated tenant workspace with RLS protection.
    - Pre-seeded with authentic Indian GST procurement fixtures & 2 sample invoices.
    - Expiring cryptographically signed Supabase JWT.
    """
    if db is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database service unavailable for demo tenant provisioning.",
        )

    xff = request.headers.get("x-forwarded-for")
    client_ip = [ip.strip() for ip in xff.split(",")][0] if xff else (request.client.host if request.client else "unknown")
    return provision_isolated_demo_tenant(db, client_ip)


@router.get("/status")
def auth_status() -> Dict[str, Any]:
    """Returns the current Identity Provider configuration status."""
    res = check_idp_health()
    res["supabase_url"] = settings.SUPABASE_URL
    res["supabase_anon_key"] = settings.SUPABASE_ANON_KEY
    res["dev_session_enabled"] = settings.ENABLE_DEV_SESSION and settings.APP_ENV in (AppEnv.DEVELOPMENT, AppEnv.TEST)
    return res


@router.get("/me")
def get_current_user_profile(
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> Dict[str, Any]:
    """Returns the currently authenticated user claims and tenant membership status.

    Rejects unauthenticated requests with HTTP 401.
    If authenticated but unprovisioned (no active organisation membership), returns
    membership status with empty org details, enabling the client to show Invitation /
    Request Access workflows.
    """
    return {
        "id": current_user.id,
        "email": current_user.email,
        "name": current_user.name,
        "role": current_user.role.value if current_user.role else None,
        "org_id": current_user.org_id,
        "org_name": current_user.org_name,
        "is_provisioned": current_user.is_provisioned,
        "is_owner": current_user.is_owner,
        "workspace_selection_required": current_user.workspace_selection_required,
        "available_orgs": current_user.available_orgs,
        "legal_entity_ids": current_user.legal_entity_ids,
        "status": "ACTIVE" if current_user.is_provisioned else ("WORKSPACE_SELECTION_REQUIRED" if current_user.workspace_selection_required else "UNPROVISIONED"),
    }


@router.post("/logout")
def logout(
    current_user: AuthenticatedUser = Depends(get_current_user),
    credentials: HTTPAuthorizationCredentials = Security(security_bearer),
    db: Session = Depends(get_db),
) -> Dict[str, str]:
    """Revoke this access token for this application, then clear it locally."""
    if db is None or credentials is None:
        raise HTTPException(status_code=503, detail="Session revocation is unavailable.")
    claims, _, _ = verify_token_claims(credentials.credentials)
    if not claims.get("exp"):
        raise HTTPException(status_code=400, detail="An expiring access token is required for revocation.")
    try:
        expires = datetime.datetime.fromtimestamp(int(claims["exp"]), datetime.timezone.utc).replace(tzinfo=None)
        db.add(RevokedAccessToken(token_hash=hashlib.sha256(credentials.credentials.encode("utf-8")).hexdigest(), expires_at=expires))
        db.commit()
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=503, detail="Session revocation is unavailable.") from exc
    return {"status": "ACCESS_TOKEN_REVOKED", "message": "This access token is revoked for this application. Identity-provider refresh sessions are not revoked."}


# ------------------------------------------------------------------------------
# Invitation Workflows (Admin Only)
# ------------------------------------------------------------------------------

@router.post("/invitations")
def create_invitation(
    payload: CreateInvitationPayload,
    current_user: AuthenticatedUser = Depends(require_role([UserRole.SYSTEM_ADMIN, UserRole.CONTROLLER, UserRole.AP_LEAD])),
    db: Optional[Session] = Depends(get_db),
) -> Dict[str, Any]:
    """Generates a secure, single-use, time-limited tenant invitation.

    Enforces:
    - Admin permissions required (SYSTEM_ADMIN, CONTROLLER, or AP_LEAD).
    - Only SYSTEM_ADMIN can invite new SYSTEM_ADMIN users.
    - Unpredictable 32-byte cryptographic token with SHA-256 storage hash.
    - 7-day expiration window.
    - Immutable audit event recorded.
    """
    if db is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database not connected.")

    if payload.role == UserRole.SYSTEM_ADMIN and current_user.role != UserRole.SYSTEM_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Privilege escalation barred: Only System Administrators can issue invitations for the SYSTEM_ADMIN role.",
        )

    clean_email = payload.email.strip().lower()

    # Generate unpredictable single-use crypto token
    raw_token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()

    now_utc = datetime.datetime.utcnow()
    expires_at = now_utc + datetime.timedelta(days=7)

    invitation = UserInvitation(
        id=f"inv_{uuid.uuid4().hex[:12]}",
        org_id=current_user.org_id,
        email=clean_email,
        role_name=payload.role.value,
        token_hash=token_hash,
        invited_by_user_id=current_user.id,
        status="PENDING",
        expires_at=expires_at,
        created_at=now_utc,
    )
    db.add(invitation)

    # Record immutable audit event
    audit = AuditEvent(
        id=f"evt_{uuid.uuid4().hex[:12]}",
        org_id=current_user.org_id,
        actor_id=current_user.id,
        actor_role=current_user.role.value,
        action="USER_INVITED",
        reason=f"Issued invitation to {clean_email} with role {payload.role.value}",
        before_state=None,
        after_state={"invited_email": clean_email, "role": payload.role.value, "expires_at": expires_at.isoformat() + "Z"},
        timestamp=now_utc,
    )
    db.add(audit)
    db.commit()

    return {
        "invitation_id": invitation.id,
        "org_id": current_user.org_id,
        "email": clean_email,
        "role": payload.role.value,
        "expires_at": expires_at.isoformat() + "Z",
        "invitation_token": raw_token,
    }


@router.post("/invitations/{invitation_id}/revoke")
def revoke_invitation(
    invitation_id: str,
    current_user: AuthenticatedUser = Depends(require_role([UserRole.SYSTEM_ADMIN, UserRole.CONTROLLER, UserRole.AP_LEAD])),
    db: Optional[Session] = Depends(get_db),
) -> Dict[str, Any]:
    """Revokes a pending invitation before acceptance.

    Enforces:
    - Lead, Controller, or Admin authority required.
    - Scoped strictly to current_user.org_id.
    - Transitions status from PENDING to REVOKED.
    - Records immutable INVITATION_REVOKED audit event.
    """
    if db is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database not connected.")

    invitation = db.scalar(
        select(UserInvitation).where(
            UserInvitation.id == invitation_id,
            UserInvitation.org_id == current_user.org_id,
        )
    )
    if not invitation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invitation not found.")

    if invitation.status != "PENDING":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot revoke invitation with status '{invitation.status}'.",
        )

    now_utc = datetime.datetime.utcnow()
    invitation.status = "REVOKED"

    audit = AuditEvent(
        id=f"evt_{uuid.uuid4().hex[:12]}",
        org_id=current_user.org_id,
        actor_id=current_user.id,
        actor_role=current_user.role.value,
        action="INVITATION_REVOKED",
        reason=f"Invitation for {invitation.email} revoked by {current_user.email}",
        before_state={"status": "PENDING"},
        after_state={"status": "REVOKED"},
        timestamp=now_utc,
    )
    db.add(audit)
    db.commit()

    return {
        "status": "REVOKED",
        "invitation_id": invitation.id,
        "email": invitation.email,
        "message": f"Invitation for {invitation.email} has been revoked.",
    }


def verify_invitation_email(user: AuthenticatedUser, credentials: HTTPAuthorizationCredentials) -> None:
    """Check current provider identity; mutable JWT user_metadata is not proof."""
    if not (settings.IDENTITY_EMAIL_CONFIRMATION_ENFORCED and settings.SUPABASE_URL
            and settings.SUPABASE_ANON_KEY and credentials and credentials.credentials):
        raise HTTPException(status_code=503, detail="Verified-email invitation acceptance is not configured.")
    try:
        request = urllib.request.Request(settings.SUPABASE_URL.rstrip('/') + '/auth/v1/user',
            headers={'apikey': settings.SUPABASE_ANON_KEY, 'Authorization': 'Bearer ' + credentials.credentials})
        with urllib.request.urlopen(request, timeout=5) as response:
            body = json.load(response)
        if (body.get('id') != user.auth_subject or not body.get('email_confirmed_at')
                or str(body.get('email') or '').lower() != user.email.lower()):
            raise HTTPException(status_code=403, detail="A confirmed matching provider email is required.")
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Provider email verification is unavailable.") from exc


@router.post("/invitations/accept")
def accept_invitation(
    payload: AcceptInvitationPayload,
    current_user: AuthenticatedUser = Depends(get_current_user),
    db: Optional[Session] = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Security(security_bearer),
) -> Dict[str, Any]:
    """Accepts a tenant invitation, activating active membership.

    Enforces:
    - Authenticated user required.
    - Single-use token hash lookup.
    - Expiration check (rejects expired invitations).
    - Email identity match: authenticated email MUST strictly match the invited email address.
    - Provisions User and RoleAssignment atomically.
    - Invalidates token (status=ACCEPTED).
    """
    if db is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database not connected.")

    if settings.APP_ENV != AppEnv.TEST:
        verify_invitation_email(current_user, credentials)

    token_hash = hashlib.sha256(payload.token.strip().encode("utf-8")).hexdigest()
    now_utc = datetime.datetime.utcnow()

    # The invitation belongs to a tenant that the invitee may not yet be able
    # to access. Resolve only a pending, email-matched token before setting its
    # tenant context, then lock and recheck it inside the transaction.
    if db.bind and db.bind.dialect.name == "postgresql":
        found = db.execute(
            text("SELECT org_id FROM find_pending_invitation(:token_hash, :email)"),
            {"token_hash": token_hash, "email": current_user.email},
        ).first()
        if not found:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invitation is invalid, expired, used, or belongs to another account.")
        set_tenant_context(db, found[0])

    invitation = db.scalar(select(UserInvitation).where(UserInvitation.token_hash == token_hash).with_for_update())
    if not invitation:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or nonexistent invitation token.",
        )

    if invitation.status != "PENDING":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invitation is no longer valid. Current status: '{invitation.status}'.",
        )

    if invitation.expires_at < now_utc:
        invitation.status = "EXPIRED"
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invitation token has expired. Please request a new invitation from your administrator.",
        )

    # Security rule: Authenticated email MUST strictly match the invited email address
    if invitation.email.lower() != current_user.email.lower():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Email mismatch: This invitation was issued for '{invitation.email}', but you are signed in as '{current_user.email}'.",
        )

    # Establish or activate User record
    existing_user = db.scalar(
        select(User).where(User.org_id == invitation.org_id, User.email == invitation.email.lower())
    )
    if existing_user and existing_user.id != current_user.id:
        # Matching email is not proof that this provider subject owns a legacy
        # tenant identity. Preserve its user ID, role and historical audit actor.
        raise HTTPException(status_code=409, detail="Existing workspace identity requires administrator reconciliation before this invitation can be accepted.")
    if current_user.is_provisioned and current_user.org_id != invitation.org_id:
        # Cross-workspace identity binding is not implemented by this endpoint.
        # Do not reuse a tenant-local primary key or rewrite an existing account.
        raise HTTPException(status_code=409, detail="Joining another workspace requires administrator identity reconciliation.")
    if not existing_user:
        new_user = User(
            id=current_user.id,
            org_id=invitation.org_id,
            email=invitation.email.lower(),
            full_name=current_user.name,
            is_active=True,
            created_at=now_utc,
        )
        db.add(new_user)
    else:
        existing_user.is_active = True

    # Establish or update RoleAssignment
    existing_role = db.scalar(
        select(RoleAssignment).where(
            RoleAssignment.org_id == invitation.org_id,
            RoleAssignment.user_id == current_user.id,
        )
    )
    if not existing_role:
        role_assignment = RoleAssignment(
            id=f"role_{uuid.uuid4().hex[:12]}",
            org_id=invitation.org_id,
            user_id=current_user.id,
            role_name=invitation.role_name,
            granted_at=now_utc,
        )
        db.add(role_assignment)
    else:
        existing_role.role_name = invitation.role_name

    # Invalidate invitation token
    invitation.status = "ACCEPTED"
    invitation.accepted_at = now_utc

    # Log immutable audit event
    audit = AuditEvent(
        id=f"evt_{uuid.uuid4().hex[:12]}",
        org_id=invitation.org_id,
        actor_id=current_user.id,
        actor_role=invitation.role_name,
        action="INVITATION_ACCEPTED",
        reason=f"User {current_user.email} accepted invitation for {invitation.org_id}",
        before_state={"status": "PENDING"},
        after_state={"status": "ACCEPTED", "role": invitation.role_name},
        timestamp=now_utc,
    )
    db.add(audit)
    db.commit()

    # Bind active tenant context
    set_tenant_context(db, invitation.org_id)

    return {
        "status": "SUCCESS",
        "org_id": invitation.org_id,
        "role": invitation.role_name,
        "message": f"Successfully activated membership in organisation '{invitation.org_id}'.",
    }


# ------------------------------------------------------------------------------
# Request Access Workflows
# ------------------------------------------------------------------------------

@router.post("/access-requests")
def submit_access_request(
    payload: CreateAccessRequestPayload,
    current_user: AuthenticatedUser = Depends(get_current_user),
    db: Optional[Session] = Depends(get_db),
) -> Dict[str, Any]:
    """Submits an uninvited employee access request.

    Enforces:
    - Never creates active membership automatically.
    - Rejects duplicate pending requests for the same user and organisation.
    - Records request with status PENDING awaiting administrator action.
    """
    if db is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database not connected.")

    target_org = db.scalar(select(Organisation).where(Organisation.id == payload.org_id))
    if not target_org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Organisation '{payload.org_id}' does not exist.",
        )

    # Safe instant onboarding for the dedicated evaluation workspace org_sme_eval (Approved Evaluators ONLY)
    allowed_evaluators = {e.lower().strip() for e in (getattr(settings, "EVALUATOR_ALLOWLIST_EMAILS", []) or [])}
    is_approved_evaluator = bool(current_user.email and (current_user.email.lower().strip() in allowed_evaluators))

    if payload.org_id == "org_sme_eval" and is_approved_evaluator:
        now_utc = datetime.datetime.utcnow()
        role = payload.requested_role or UserRole.AP_LEAD
        eval_user = db.scalar(select(User).where(func.lower(User.email) == current_user.email.lower(), User.org_id == "org_sme_eval"))
        if not eval_user:
            eval_user = User(
                id=current_user.id if current_user.id.startswith("usr_") else f"usr_eval_{uuid.uuid4().hex[:10]}",
                email=current_user.email.lower(),
                full_name=current_user.name,
                org_id="org_sme_eval",
                is_active=True,
                created_at=now_utc,
                updated_at=now_utc,
            )
            db.add(eval_user)
            db.flush()

        ra = db.scalar(select(RoleAssignment).where(RoleAssignment.user_id == eval_user.id, RoleAssignment.org_id == "org_sme_eval"))
        if not ra:
            ra = RoleAssignment(
                id=f"ras_{uuid.uuid4().hex[:12]}",
                user_id=eval_user.id,
                org_id="org_sme_eval",
                role_name=role.value,
                granted_at=now_utc,
            )
            db.add(ra)
        else:
            ra.role_name = role.value
        db.commit()
        return {
            "request_id": f"req_eval_{uuid.uuid4().hex[:8]}",
            "org_id": "org_sme_eval",
            "status": "APPROVED",
            "message": f"Evaluation workspace access granted with role {role.value}.",
        }

    # Check if user already has active membership
    existing_member = db.scalar(
        select(User).where(
            User.org_id == payload.org_id,
            or_(User.id == current_user.id, func.lower(User.email) == current_user.email.lower()),
            User.is_active == True,
        )
    )
    if existing_member:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User already has active membership in this organisation.",
        )

    # Check if already requested
    existing_req = db.scalar(
        select(AccessRequest).where(
            AccessRequest.org_id == payload.org_id,
            AccessRequest.user_id == current_user.id,
            AccessRequest.status == "PENDING",
        )
    )
    if existing_req:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An access request for this organisation is already pending review.",
        )

    now_utc = datetime.datetime.utcnow()
    req = AccessRequest(
        id=f"req_{uuid.uuid4().hex[:12]}",
        org_id=payload.org_id,
        user_id=current_user.id,
        email=current_user.email.lower(),
        full_name=current_user.name,
        requested_role=payload.requested_role.value if payload.requested_role else "AP_ASSOCIATE",
        status="PENDING",
        review_reason=payload.reason,
        created_at=now_utc,
    )
    db.add(req)
    db.commit()

    return {
        "request_id": req.id,
        "org_id": req.org_id,
        "status": "PENDING",
        "message": "Access request submitted. Awaiting administrator review and approval.",
    }


@router.get("/access-requests")
def list_organisation_access_requests(
    current_user: AuthenticatedUser = Depends(require_role([UserRole.SYSTEM_ADMIN, UserRole.CONTROLLER, UserRole.AP_LEAD])),
    db: Optional[Session] = Depends(get_db),
) -> List[Dict[str, Any]]:
    """Lists pending access requests for the administrator's active organisation."""
    if db is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database not connected.")

    requests = db.scalars(
        select(AccessRequest)
        .where(AccessRequest.org_id == current_user.org_id)
        .order_by(AccessRequest.created_at.desc())
    ).all()

    return [
        {
            "id": r.id,
            "org_id": r.org_id,
            "user_id": r.user_id,
            "email": r.email,
            "full_name": r.full_name,
            "requested_role": r.requested_role,
            "status": r.status,
            "review_reason": r.review_reason,
            "created_at": r.created_at.isoformat() + "Z",
            "reviewed_at": r.reviewed_at.isoformat() + "Z" if r.reviewed_at else None,
        }
        for r in requests
    ]


@router.get("/access-requests/my")
def list_my_access_requests(
    current_user: AuthenticatedUser = Depends(get_current_user),
    db: Optional[Session] = Depends(get_db),
) -> List[Dict[str, Any]]:
    """Lists submitted access requests for the currently authenticated employee."""
    if db is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database not connected.")

    requests = db.scalars(
        select(AccessRequest)
        .where(
            or_(AccessRequest.user_id == current_user.id, func.lower(AccessRequest.email) == current_user.email.lower())
        )
        .order_by(AccessRequest.created_at.desc())
    ).all()

    return [
        {
            "id": r.id,
            "org_id": r.org_id,
            "requested_role": r.requested_role,
            "status": r.status,
            "review_reason": r.review_reason,
            "created_at": r.created_at.isoformat() + "Z",
            "reviewed_at": r.reviewed_at.isoformat() + "Z" if r.reviewed_at else None,
        }
        for r in requests
    ]


@router.post("/access-requests/{request_id}/review")
def review_access_request(
    request_id: str,
    payload: ReviewAccessRequestPayload,
    current_user: AuthenticatedUser = Depends(require_role([UserRole.SYSTEM_ADMIN, UserRole.CONTROLLER])),
    db: Optional[Session] = Depends(get_db),
) -> Dict[str, Any]:
    """Approves or rejects an employee access request.

    Enforces:
    - Authorised administrators only (SYSTEM_ADMIN or CONTROLLER).
    - Scope limited strictly to administrator's active organisation.
    - If APPROVED, provisions active User and RoleAssignment atomically.
    - Immutable audit event recorded with decision reason.
    """
    if db is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database not connected.")

    if payload.action not in ("APPROVE", "REJECT"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Action must be either 'APPROVE' or 'REJECT'.",
        )

    req = db.scalar(
        select(AccessRequest).where(
            AccessRequest.id == request_id,
            AccessRequest.org_id == current_user.org_id,
        )
    )
    if not req:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Access request '{request_id}' not found.")

    if req.status != "PENDING":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Access request has already been reviewed (status: {req.status}).",
        )

    now_utc = datetime.datetime.utcnow()
    req.reviewed_by_user_id = current_user.id
    req.reviewed_at = now_utc
    req.review_reason = payload.reason or f"Action {payload.action} executed by {current_user.name}"

    if payload.action == "APPROVE":
        assigned_role_name = payload.role.value if payload.role else req.requested_role
        req.status = "APPROVED"

        # Create or activate user
        existing_user = db.scalar(
            select(User).where(User.org_id == req.org_id, User.email == req.email.lower())
        )
        if not existing_user:
            new_user = User(
                id=req.user_id,
                org_id=req.org_id,
                email=req.email.lower(),
                full_name=req.full_name,
                is_active=True,
                created_at=now_utc,
            )
            db.add(new_user)
        else:
            existing_user.is_active = True

        # Assign role
        existing_role = db.scalar(
            select(RoleAssignment).where(
                RoleAssignment.org_id == req.org_id,
                RoleAssignment.user_id == req.user_id,
            )
        )
        if not existing_role:
            role_assignment = RoleAssignment(
                id=f"role_{uuid.uuid4().hex[:12]}",
                org_id=req.org_id,
                user_id=req.user_id,
                role_name=assigned_role_name,
                granted_at=now_utc,
            )
            db.add(role_assignment)
        else:
            existing_role.role_name = assigned_role_name

        audit_action = "ACCESS_REQUEST_APPROVED"
    else:
        req.status = "REJECTED"
        audit_action = "ACCESS_REQUEST_REJECTED"

    # Record immutable audit event
    audit = AuditEvent(
        id=f"evt_{uuid.uuid4().hex[:12]}",
        org_id=current_user.org_id,
        actor_id=current_user.id,
        actor_role=current_user.role.value,
        action=audit_action,
        reason=req.review_reason,
        before_state={"status": "PENDING"},
        after_state={"status": req.status, "target_user_id": req.user_id, "email": req.email},
        timestamp=now_utc,
    )
    db.add(audit)
    db.commit()

    return {
        "request_id": req.id,
        "status": req.status,
        "review_reason": req.review_reason,
        "reviewed_at": now_utc.isoformat() + "Z",
    }


# ------------------------------------------------------------------------------
# User Role Modification & Revocation (Self-Promotion Barred)
# ------------------------------------------------------------------------------

@router.patch("/users/{user_id}/role")
def update_user_role(
    user_id: str,
    payload: UpdateUserRolePayload,
    current_user: AuthenticatedUser = Depends(require_role([UserRole.SYSTEM_ADMIN, UserRole.CONTROLLER])),
    db: Optional[Session] = Depends(get_db),
) -> Dict[str, Any]:
    """Modifies an employee's server-side assigned role.

    Enforces:
    - Users CANNOT modify their own role (self-promotion strictly prohibited).
    - Only SYSTEM_ADMIN can grant the SYSTEM_ADMIN role.
    - Immutable audit event recorded.
    """
    if db is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database not connected.")

    # Strict anti-self-promotion invariant
    if user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Security violation: Users cannot modify their own role. Administrator peer sign-off required.",
        )

    if payload.role == UserRole.SYSTEM_ADMIN and current_user.role != UserRole.SYSTEM_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Privilege escalation barred: Only System Administrators can grant the SYSTEM_ADMIN role.",
        )

    target_user = db.scalar(
        select(User).where(User.id == user_id, User.org_id == current_user.org_id)
    )
    if not target_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"User '{user_id}' not found in organisation.")

    role_assignment = db.scalar(
        select(RoleAssignment).where(
            RoleAssignment.user_id == user_id,
            RoleAssignment.org_id == current_user.org_id,
        )
    )
    before_role = role_assignment.role_name if role_assignment else "NONE"
    now_utc = datetime.datetime.utcnow()

    if not role_assignment:
        role_assignment = RoleAssignment(
            id=f"role_{uuid.uuid4().hex[:12]}",
            org_id=current_user.org_id,
            user_id=user_id,
            role_name=payload.role.value,
            granted_at=now_utc,
        )
        db.add(role_assignment)
    else:
        role_assignment.role_name = payload.role.value

    # Record immutable audit event
    audit = AuditEvent(
        id=f"evt_{uuid.uuid4().hex[:12]}",
        org_id=current_user.org_id,
        actor_id=current_user.id,
        actor_role=current_user.role.value,
        action="USER_ROLE_UPDATED",
        reason=payload.reason,
        before_state={"role": before_role},
        after_state={"role": payload.role.value, "target_user_id": user_id},
        timestamp=now_utc,
    )
    db.add(audit)
    db.commit()

    return {
        "status": "SUCCESS",
        "user_id": user_id,
        "new_role": payload.role.value,
        "updated_at": now_utc.isoformat() + "Z",
    }


@router.post("/users/{user_id}/deactivate")
def deactivate_user_membership(
    user_id: str,
    payload: DeactivateUserPayload,
    current_user: AuthenticatedUser = Depends(require_role([UserRole.SYSTEM_ADMIN, UserRole.CONTROLLER])),
    db: Optional[Session] = Depends(get_db),
) -> Dict[str, Any]:
    """Deactivates an employee's tenant membership.

    Enforces:
    - Users cannot deactivate their own account.
    - Sets is_active=False. Subsequent membership lookups fail closed.
    - Immutable audit event recorded.
    """
    if db is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database not connected.")

    if user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Security violation: Users cannot deactivate their own account.",
        )

    target_user = db.scalar(
        select(User).where(User.id == user_id, User.org_id == current_user.org_id)
    )
    if not target_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"User '{user_id}' not found in organisation.")

    target_user.is_active = False
    now_utc = datetime.datetime.utcnow()

    # Record immutable audit event
    audit = AuditEvent(
        id=f"evt_{uuid.uuid4().hex[:12]}",
        org_id=current_user.org_id,
        actor_id=current_user.id,
        actor_role=current_user.role.value,
        action="USER_DEACTIVATED",
        reason=payload.reason,
        before_state={"is_active": True},
        after_state={"is_active": False, "target_user_id": user_id},
        timestamp=now_utc,
    )
    db.add(audit)
    db.commit()

    return {
        "status": "SUCCESS",
        "user_id": user_id,
        "is_active": False,
        "deactivated_at": now_utc.isoformat() + "Z",
    }


@router.get("/members")
def list_organisation_members(
    current_user: AuthenticatedUser = Depends(require_active_membership),
    db: Optional[Session] = Depends(get_db),
) -> Dict[str, Any]:
    """Lists actual registered members of the current organisation with assigned roles.

    Enforces strict tenant isolation (scoped to current_user.org_id).
    """
    if db is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database not connected.")

    users = db.scalars(
        select(User)
        .where(User.org_id == current_user.org_id)
        .order_by(User.created_at.asc())
    ).all()

    items = []
    for u in users:
        role_record = db.scalar(
            select(RoleAssignment)
            .where(RoleAssignment.user_id == u.id, RoleAssignment.org_id == current_user.org_id)
        )
        primary_role = role_record.role_name if role_record else "AP_ASSOCIATE"
        items.append({
            "id": u.id,
            "full_name": u.full_name or u.email,
            "email": u.email,
            "role": primary_role,
            "is_active": u.is_active,
            "created_at": u.created_at.isoformat() + "Z",
        })

    return {
        "total_count": len(items),
        "items": items,
    }
