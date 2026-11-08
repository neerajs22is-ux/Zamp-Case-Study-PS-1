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
from backend.models.domain import (
    AccessRequest, AuditEvent, Organisation, RevokedAccessToken, RoleAssignment, User, UserInvitation
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
    client_host = request.client.host if request.client else ""
    is_local = client_host in ("127.0.0.1", "localhost", "::1", "testclient") or not client_host
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
        updated_at=now_utc,
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
