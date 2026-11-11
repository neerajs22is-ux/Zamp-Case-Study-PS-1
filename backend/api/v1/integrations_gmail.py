"""Gmail OAuth 2.0 Integration & Ingestion Endpoints (Phase B Stage 4.1 & Stage 5).

Enforces:
1. Three-legged OAuth 2.0 with minimum privileged scope: https://www.googleapis.com/auth/gmail.readonly.
2. Separate mailbox authorization flow distinct from application employee login.
3. Server-side refresh token encryption with Fernet (AES-128-CBC + HMAC-SHA256); zero plaintext secret exposure.
4. Single-use, cryptographically signed OAuth state nonces with 10-minute expiry and replay rejection.
5. Preserves existing refresh tokens when reconnecting if Google omits the token.
6. Event-driven push notifications from Google Cloud Pub/Sub with OIDC verification.
7. Durable event persistence in gmail_pubsub_events prior to acknowledgement.
8. History synchronization with automatic resync fallback on HTTP 404 (HistoryExpiredError).
9. Scheduled 48-hour watch renewal and 6-hour periodic reconciliation fallback.
10. Truthful CASA and credentials status reporting: PRODUCTION_GOOGLE_VERIFICATION_PENDING.
"""

from __future__ import annotations

import datetime
import logging
import uuid
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.core.auth import (
    AuthenticatedUser, MaintenanceActor, UserRole, require_active_membership,
    require_maintenance_auth, require_role
)
from backend.core.config import settings
from backend.core.database import get_db, set_tenant_context
from backend.core.gmail import (
    GmailIntegrationError, GmailNotConfiguredError, MailboxSyncLockError,
    PubSubPersistenceError, build_authorization_url, clean_expired_mailbox_locks,
    encrypt_refresh_token, exchange_code_for_tokens, fetch_mailbox_profile,
    fetch_mailbox_profile_address, mailbox_sync_lease,
    process_pubsub_push_notification, reclaim_unfinished_pubsub_events,
    reconcile_all_active_mailboxes, resolve_gmail_redirect_uri, renew_expiring_watches,
    setup_mailbox_watch,
    sync_gmail_history, sync_gmail_mailbox, validate_oauth_state,
    validate_pubsub_oidc_token,
)
from backend.models.domain import AuditEvent, GmailAccount

logger = logging.getLogger("ap_command_center.gmail_api")

router = APIRouter(prefix="/integrations/gmail", tags=["Gmail Ingestion & OAuth"])


@router.get("/status")
def get_gmail_status(
    current_user: AuthenticatedUser = Depends(require_active_membership),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Returns the truthful operational status of the Gmail ingestion pillar."""
    account = db.execute(
        select(GmailAccount).where(GmailAccount.org_id == current_user.org_id)
    ).scalar_one_or_none()

    is_configured = settings.is_gmail_configured()

    if not is_configured and not account:
        status_code = "NOT_CONFIGURED"
        readiness = False
        msg = "Gmail OAuth 2.0 credentials not provisioned in environment."
    elif account and account.oauth_status == "AUTHORIZED":
        status_code = "CONNECTED"
        readiness = True
        if not account.last_synced_at:
            msg = f"Authorized Gmail mailbox {account.mailbox_address} connected. Initial full synchronization pending."
        else:
            msg = f"Authorized Gmail ingestion active for mailbox: {account.mailbox_address}"
    elif account and account.oauth_status == "EXPIRED":
        status_code = "DEGRADED"
        readiness = False
        msg = "Mailbox refresh token expired or revoked. Re-authorization required."
    elif account and account.oauth_status == "REVOKED":
        status_code = "REVOKED"
        readiness = False
        msg = "Mailbox authorization was disconnected by tenant administrator."
    else:
        status_code = "NOT_CONFIGURED"
        readiness = False
        msg = "Mailbox OAuth authorization pending."

    return {
        "status": status_code,
        "pillar": "gmail",
        "mailbox": account.mailbox_address if account else settings.GMAIL_TARGET_MAILBOX,
        "scopes": ["https://www.googleapis.com/auth/gmail.readonly"],
        "required_env": ["GMAIL_CLIENT_ID", "GMAIL_CLIENT_SECRET", "GMAIL_REFRESH_TOKEN", "GMAIL_TARGET_MAILBOX"],
        "redirect_uri": resolve_gmail_redirect_uri(),
        "last_synced_at": account.last_synced_at.isoformat() + "Z" if account and account.last_synced_at else None,
        "last_history_id": account.last_history_id if account else None,
        "initial_sync_pending": bool(account and account.oauth_status == "AUTHORIZED" and not account.last_synced_at),
        "readiness": readiness,
        "watch_status": account.watch_status if account else "NOT_CONFIGURED",
        "watch_expiration_at": (
            account.watch_expiration_at.isoformat() + "Z"
            if account and account.watch_expiration_at
            else None
        ),
        "pubsub_topic": account.pubsub_topic if account else settings.PUBSUB_TOPIC_NAME,
        "compliance_status": "PRODUCTION_GOOGLE_VERIFICATION_PENDING",
        "compliance": {
            "scope": "https://www.googleapis.com/auth/gmail.readonly",
            "compliance_status": "PRODUCTION_GOOGLE_VERIFICATION_PENDING",
            "casa_status": "CASA_ASSESSMENT_PENDING_PRODUCTION_APPROVAL",
            "connection_type": "three_legged_oauth",
            "notes": "Dedicated Google test mailbox in use for development/pilot; CASA Tier 2 assessment required before production authorization expenditure.",
        },
        "scheduling": {
            "watch_renewal": {
                "interval_hours": 48,
                "endpoint": "POST /api/v1/integrations/gmail/watch/renew",
                "function": "renew_expiring_watches",
                "status": "NOT_CONFIGURED",
                "notes": "Automated external trigger (Cloud Scheduler) deferred to Cloud Run deployment preparation.",
            },
            "reconciliation": {
                "interval_hours": 6,
                "endpoint": "POST /api/v1/integrations/gmail/reconcile",
                "function": "reconcile_all_active_mailboxes",
                "status": "NOT_CONFIGURED",
                "notes": "Automated external trigger (Cloud Scheduler) deferred to Cloud Run deployment preparation.",
            },
            "pubsub_recovery": {
                "endpoint": "POST /api/v1/integrations/gmail/pubsub/reclaim",
                "function": "reclaim_unfinished_pubsub_events",
                "status": "NOT_CONFIGURED",
                "processing_mode": "SYNCHRONOUS_IN_WEBHOOK_WITH_ON_DEMAND_RECOVERY",
                "notes": "Webhook processes events synchronously upon receipt; unfinished events recovered on redelivery or via maintenance endpoints. Automated background worker scheduler is NOT CONFIGURED.",
            },
        },
        "message": msg,
    }


@router.get("/authorize")
def authorize_gmail(
    current_user: AuthenticatedUser = Depends(
        require_role([UserRole.SYSTEM_ADMIN, UserRole.CONTROLLER, UserRole.AP_LEAD])
    ),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Generates a secure, signed authorization URL with 10-minute nonce expiration."""
    if not settings.GMAIL_CLIENT_ID:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Gmail OAuth 2.0 is not configured: GMAIL_CLIENT_ID is required.",
        )

    try:
        auth_url = build_authorization_url(current_user.org_id, current_user.id, db=db)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate authorization URL: {str(exc)}",
        )

    return {
        "authorization_url": auth_url,
        "scope": "https://www.googleapis.com/auth/gmail.readonly",
        "org_id": current_user.org_id,
        "expires_in_seconds": 600,
    }


@router.get("/callback")
@router.get("/oauth/callback")
def gmail_oauth_callback(
    code: Optional[str] = Query(default=None),
    state: Optional[str] = Query(default=None),
    error: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
) -> Any:
    """OAuth 2.0 callback endpoint: verifies state nonce atomically, exchanges code, encrypts refresh token."""
    if error:
        logger.warning(f"Google OAuth authorization returned error: {error}")
        return RedirectResponse(url=f"{settings.BASE_URL.rstrip('/')}/connections?gmail=error&detail={error}")

    if not code or not state:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing code or state query parameter in OAuth callback.",
        )

    # 1. Validate cryptographic state signature & atomic single-use nonce consumption
    try:
        org_id, user_id = validate_oauth_state(state, db=db)
    except GmailIntegrationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except Exception:
        # Infrastructure failure while consuming the state nonce: never surface raw errors.
        if db is not None:
            db.rollback()
        logger.exception("Gmail OAuth state verification failed due to a database/infrastructure error.")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Gmail authorization state could not be verified. Please retry the authorization link.",
        )

    # Establish tenant context from the organisation proven by the signed state.
    # This callback runs without a user session, and RLS-protected tables fail closed
    # when app.current_org_id is unset.
    if db is not None:
        set_tenant_context(db, org_id)

    # 2. Exchange authorization code for tokens
    try:
        token_data = exchange_code_for_tokens(code)
    except GmailIntegrationError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))

    refresh_token = token_data.get("refresh_token")
    access_token = token_data.get("access_token")

    if not access_token:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Token exchange response did not contain an access_token.",
        )

    # 3. Query user's verified Gmail profile address & initial history watermark
    try:
        mailbox_address = fetch_mailbox_profile_address(access_token)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to query mailbox profile address: {str(exc)}",
        )

    # Persist the encrypted refresh token, then the mailbox and audit records.
    # Each boundary reports a distinct, safe, actionable failure instead of an
    # unhandled HTTP 500.
    try:
        encrypted_refresh = encrypt_refresh_token(refresh_token) if refresh_token else None
    except Exception:
        if db is not None:
            db.rollback()
        logger.exception("Gmail refresh token could not be encrypted for organisation %s.", org_id)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "The mailbox refresh token could not be encrypted, so the connection was not saved. "
                "An operator must verify that GMAIL_ENCRYPTION_KEY is a valid Fernet key."
            ),
        )

    try:
        # 4. Upsert the mailbox record. Prefer the row already bound to this exact
        #    mailbox address, otherwise reuse the organisation's existing mailbox row,
        #    so re-authorization never creates a duplicate tenant mailbox and a stray
        #    duplicate row can never turn this into a 500/503.
        account = db.execute(
            select(GmailAccount).where(
                GmailAccount.org_id == org_id,
                GmailAccount.mailbox_address == mailbox_address,
            )
        ).scalars().first()
        if account is None:
            account = db.execute(
                select(GmailAccount)
                .where(GmailAccount.org_id == org_id)
                .order_by(GmailAccount.created_at.asc())
                .limit(1)
            ).scalars().first()

        now = datetime.datetime.utcnow()
        if account:
            account.mailbox_address = mailbox_address
            account.oauth_status = "AUTHORIZED"
            if encrypted_refresh:
                account.encrypted_refresh_token = encrypted_refresh
            account.updated_at = now
        else:
            account = GmailAccount(
                id=f"gacc_{uuid.uuid4().hex[:12]}",
                org_id=org_id,
                mailbox_address=mailbox_address,
                oauth_status="AUTHORIZED",
                encrypted_refresh_token=encrypted_refresh,
                last_history_id=None,  # Intentionally None so initial sync performs full reconciliation
                created_at=now,
                updated_at=now,
            )
            db.add(account)

        # 5. Append immutable audit event
        audit = AuditEvent(
            id=f"evt_{uuid.uuid4().hex[:12]}",
            org_id=org_id,
            actor_id=user_id,
            actor_role="ADMINISTRATOR",
            action="GMAIL_MAILBOX_CONNECTED",
            reason=f"Authorized Gmail mailbox {mailbox_address} with gmail.readonly scope.",
            source_reference=mailbox_address,
        )
        db.add(audit)
        db.commit()
    except Exception:
        if db is not None:
            db.rollback()
        logger.exception("Gmail mailbox authorization could not be persisted for organisation %s.", org_id)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Gmail mailbox authorization could not be saved because the database rejected the "
                "mailbox record. Please retry the authorization link; if it repeats, an operator must "
                "check the schema, grants and row-level security for gmail_accounts."
            ),
        )

    return RedirectResponse(
        url=f"{settings.BASE_URL.rstrip('/')}/connections?gmail=connected&mailbox={mailbox_address}"
    )


@router.post("/sync")
def sync_mailbox(
    max_messages: int = Query(default=10, ge=1, le=50),
    force_full: bool = Query(default=False),
    current_user: AuthenticatedUser = Depends(
        require_role([UserRole.AP_ASSOCIATE, UserRole.AP_LEAD, UserRole.CONTROLLER, UserRole.SYSTEM_ADMIN])
    ),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Manually triggers mailbox sync and PDF invoice ingestion for the current tenant.

    If account has an existing history watermark and force_full is False, performs fast
    incremental history synchronization (users.history.list) under a per-mailbox lease.
    Otherwise, performs a full query-based mailbox reconciliation (users.messages.list).
    """
    account = db.execute(
        select(GmailAccount).where(
            GmailAccount.org_id == current_user.org_id,
            GmailAccount.oauth_status == "AUTHORIZED",
        )
    ).scalar_one_or_none()

    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No authorized Gmail mailbox configured for this organisation.",
        )

    # Execute synchronization under an exclusive per-mailbox lease
    try:
        with mailbox_sync_lease(db, account.id, lease_seconds=120):
            # 1. Fast incremental history sync when watermark is established and not forcing full
            if account.last_history_id and not force_full:
                try:
                    result = sync_gmail_history(
                        db=db,
                        account=account,
                        notification_history_id=account.last_history_id,
                        actor_id=current_user.id,
                    )
                    result["sync_mode"] = "INCREMENTAL_HISTORY"
                    return result
                except Exception as exc:
                    logger.warning(f"Incremental history sync failed ({exc}); falling back to full reconciliation.")

            # 2. Full mailbox reconciliation (Initial sync, forced sync, or history recovery fallback)
            result = sync_gmail_mailbox(
                db=db,
                org_id=current_user.org_id,
                actor_id=current_user.id,
                max_messages=max_messages,
            )
            result["sync_mode"] = "FULL_QUERY"

            if result.get("status") == "NOT_CONNECTED":
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="No authorized Gmail mailbox configured for this organisation.",
                )

            if result.get("status") == "AUTH_FAILED":
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=result.get("message", "Gmail authentication failed."),
                )

            return result
    except MailboxSyncLockError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Mailbox synchronization is already in progress for this tenant.",
        )


@router.post("/disconnect")
def disconnect_mailbox(
    current_user: AuthenticatedUser = Depends(
        require_role([UserRole.SYSTEM_ADMIN, UserRole.CONTROLLER])
    ),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Disconnects and revokes mailbox integration for the current tenant."""
    account = db.execute(
        select(GmailAccount).where(GmailAccount.org_id == current_user.org_id)
    ).scalar_one_or_none()

    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No Gmail account configured for this organisation.",
        )

    account.oauth_status = "REVOKED"
    account.encrypted_refresh_token = None
    account.watch_status = "DISABLED"
    account.updated_at = datetime.datetime.utcnow()

    audit = AuditEvent(
        id=f"evt_{uuid.uuid4().hex[:12]}",
        org_id=current_user.org_id,
        actor_id=current_user.id,
        actor_role=current_user.role.value if current_user.role else "UNKNOWN",
        action="GMAIL_MAILBOX_DISCONNECTED",
        reason=f"Revoked Gmail mailbox authorization for {account.mailbox_address}",
        source_reference=account.mailbox_address,
    )
    db.add(audit)
    db.commit()

    return {
        "status": "DISCONNECTED",
        "org_id": current_user.org_id,
        "mailbox": account.mailbox_address,
        "message": f"Gmail mailbox {account.mailbox_address} has been disconnected.",
    }


# ------------------------------------------------------------------------------
# Stage 5: Google Cloud Pub/Sub Webhook & Watch Operations
# ------------------------------------------------------------------------------

@router.post("/pubsub/push")
@router.post("/pubsub/webhook")
def receive_pubsub_push(
    request_body: Dict[str, Any],
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Google Cloud Pub/Sub push notification webhook endpoint.

    Validates Google OIDC Bearer token, persists notification durably before
    processing, and acknowledges with HTTP 200 to prevent delivery retries.
    """
    try:
        validate_pubsub_oidc_token(
            auth_header=authorization,
            expected_audience=settings.PUBSUB_VERIFICATION_AUDIENCE,
            expected_email=settings.PUBSUB_SERVICE_ACCOUNT_EMAIL,
        )
    except GmailIntegrationError as exc:
        err_msg = str(exc)
        logger.warning(f"Pub/Sub push authentication rejected: {err_msg}")
        if "audience" in err_msg.lower() or "mismatch" in err_msg.lower():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=err_msg)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=err_msg)

    try:
        result = process_pubsub_push_notification(db, request_body)
    except PubSubPersistenceError as exc:
        logger.critical(f"Durable acknowledgement failed: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Durable acknowledgement failed: {str(exc)}",
        )
    except GmailIntegrationError as exc:
        logger.warning(f"Pub/Sub push payload malformed: {exc}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except Exception as exc:
        logger.error(f"Unexpected error processing Pub/Sub push: {exc}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))

    return {
        "status": "ACKNOWLEDGED",
        "result": result,
    }


@router.post("/watch/setup")
def setup_watch(
    payload: Optional[Dict[str, Any]] = None,
    current_user: AuthenticatedUser = Depends(
        require_role([UserRole.SYSTEM_ADMIN, UserRole.CONTROLLER])
    ),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Registers Gmail users.watch with Google Cloud Pub/Sub topic for the tenant's mailbox."""
    account = db.execute(
        select(GmailAccount).where(GmailAccount.org_id == current_user.org_id)
    ).scalar_one_or_none()

    if not account or account.oauth_status != "AUTHORIZED":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No authorized Gmail mailbox configured for this organisation.",
        )

    topic_name = payload.get("topic_name") if payload else None
    try:
        res = setup_mailbox_watch(db, account, topic_name=topic_name)
        return res
    except GmailIntegrationError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))


@router.post("/watch/renew")
def renew_watches(
    actor: MaintenanceActor = Depends(require_maintenance_auth),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Renews expiring mailbox watches (<= 48h until expiration).

    Callable by:
    - Dedicated Cloud Scheduler service account via Google OIDC ID token.
    - Human operator with SYSTEM_ADMIN or CONTROLLER role via Supabase Auth JWT.
    """
    if db is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database not connected.")
    return renew_expiring_watches(db)


@router.post("/reconcile")
def trigger_reconciliation(
    max_age_hours: int = Query(default=6, ge=1, le=48),
    actor: MaintenanceActor = Depends(require_maintenance_auth),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Triggers periodic reconciliation across active mailboxes to catch any missed messages.

    Callable by:
    - Dedicated Cloud Scheduler service account via Google OIDC ID token.
    - Human operator with SYSTEM_ADMIN or CONTROLLER role via Supabase Auth JWT.
    """
    if db is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database not connected.")
    return reconcile_all_active_mailboxes(db, max_age_hours=max_age_hours)


@router.post("/pubsub/reclaim")
def reclaim_events(
    max_age_seconds: int = Query(default=60, ge=0, le=86400),
    actor: MaintenanceActor = Depends(require_maintenance_auth),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Scans and reclaims unfinished PubSubEvent records (RECEIVED, FAILED, CONCURRENT_DEFERRED).

    Callable by:
    - Dedicated Cloud Scheduler service account via Google OIDC ID token.
    - Human operator with SYSTEM_ADMIN or CONTROLLER role via Supabase Auth JWT.
    """
    if db is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database not connected.")
    return reclaim_unfinished_pubsub_events(db, max_age_seconds=max_age_seconds)
