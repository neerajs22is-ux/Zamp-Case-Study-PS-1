"""Authentication, Supabase Auth Integration, Server-Side Membership Resolution & RBAC.

Enforces:
1. Supabase Auth JWT validation (signature, issuer, audience, expiry, sub, email).
2. Server-side organisation membership resolution before establishing database tenant context.
3. Zero trust for client-supplied org_id; no automatic domain-based admin grants.
4. Invitation-only tenant membership and explicit Request Access workflow.
5. Strict Role-Based Access Control (RBAC) across all protected operations.
6. Returns HTTP 401 Unauthorized for unauthenticated / invalid JWT requests.
7. Returns HTTP 403 Forbidden for uninvited / unprovisioned users or insufficient roles.
"""

from __future__ import annotations

import datetime
from enum import Enum
import hashlib
import json
import logging
import secrets
import time
from typing import Any, Dict, List, Optional, Tuple
from fastapi import Depends, Header, HTTPException, Request, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import jwk, jwt, JWTError
from pydantic import BaseModel, EmailStr
from sqlalchemy import and_, func, or_, select, text
from sqlalchemy.orm import Session

from backend.core.config import AppEnv, settings
from backend.core.database import get_db, set_tenant_context
from backend.models.domain import Organisation, RoleAssignment, User

logger = logging.getLogger("ap_command_center.auth")

security_bearer = HTTPBearer(auto_error=False)


class UserRole(str, Enum):
    AP_ASSOCIATE = "AP_ASSOCIATE"
    AP_LEAD = "AP_LEAD"
    CONTROLLER = "CONTROLLER"
    FINANCIAL_CONTROLLER = "CONTROLLER"
    CATEGORY_MANAGER = "CATEGORY_MANAGER"
    AUDITOR = "AUDITOR"
    SYSTEM_ADMIN = "SYSTEM_ADMIN"


class AuthenticatedUser(BaseModel):
    id: str
    email: str
    name: str
    role: Optional[UserRole] = None
    org_id: Optional[str] = None
    org_name: Optional[str] = None
    is_provisioned: bool = False
    available_orgs: List[Dict[str, str]] = []
    legal_entity_ids: List[str] = []

    def can_approve_high_value(self) -> bool:
        """Only Controllers and designated AP Leads can authorize disbursements above threshold."""
        return self.role in (UserRole.CONTROLLER, UserRole.AP_LEAD)

    def is_read_only(self) -> bool:
        return self.role == UserRole.AUDITOR

    def is_admin(self) -> bool:
        return self.role in (UserRole.SYSTEM_ADMIN, UserRole.CONTROLLER, UserRole.AP_LEAD)


def check_idp_health() -> Dict[str, Any]:
    """Returns truthful IdP integration status."""
    if not settings.is_identity_configured():
        return {
            "status": "NOT_CONFIGURED",
            "provider": settings.IDP_PROVIDER,
            "issuer": settings.SUPABASE_ISSUER or (f"{settings.SUPABASE_URL}/auth/v1" if settings.SUPABASE_URL else settings.OIDC_ISSUER_URL),
            "client_id_configured": bool(settings.SUPABASE_URL or settings.OIDC_CLIENT_ID),
            "redirect_uri": settings.OIDC_REDIRECT_URI,
            "readiness": False,
            "message": "Supabase Auth / Google Workspace Identity Provider is not configured. Setup required.",
        }

    return {
        "status": "CONNECTED",
        "provider": settings.IDP_PROVIDER,
        "issuer": settings.SUPABASE_ISSUER or (f"{settings.SUPABASE_URL}/auth/v1" if settings.SUPABASE_URL else settings.OIDC_ISSUER_URL),
        "client_id_configured": True,
        "redirect_uri": settings.OIDC_REDIRECT_URI,
        "readiness": True,
        "message": f"Configured against {settings.IDP_PROVIDER} ({settings.SUPABASE_URL or settings.OIDC_ISSUER_URL}).",
    }


ALLOWED_JWT_ALGORITHMS = {"RS256", "ES256", "HS256"}

# ------------------------------------------------------------------------------
# Supabase JWKS Public Key Cache & Resolution (Stage 7.3)
# ------------------------------------------------------------------------------

_JWKS_CACHE: Dict[str, Dict[str, Any]] = {}
_JWKS_LAST_FETCH_TIME: float = 0.0
_JWKS_CACHE_TTL_SECONDS: float = 3600.0  # 1 hour cache TTL
_JWKS_MIN_REFRESH_INTERVAL: float = 5.0   # Rate-limit between network fetches


def clear_jwks_cache() -> None:
    """Resets in-memory JWKS cache (used for testing and manual cache busts)."""
    global _JWKS_CACHE, _JWKS_LAST_FETCH_TIME
    _JWKS_CACHE = {}
    _JWKS_LAST_FETCH_TIME = 0.0


def inject_jwks_cache_for_testing(jwks_data: Dict[str, Any]) -> None:
    """Injects test JWKS dictionary into cache for offline code-level algorithm tests."""
    global _JWKS_CACHE, _JWKS_LAST_FETCH_TIME
    keys = jwks_data.get("keys", [])
    _JWKS_CACHE = {k["kid"]: k for k in keys if "kid" in k}
    _JWKS_LAST_FETCH_TIME = time.time()


def get_supabase_jwks_url() -> Optional[str]:
    """Returns the effective Supabase JWKS endpoint URL."""
    if settings.SUPABASE_JWKS_URL:
        return settings.SUPABASE_JWKS_URL
    if settings.SUPABASE_URL:
        return f"{settings.SUPABASE_URL.rstrip('/')}/auth/v1/.well-known/jwks.json"
    return None


def fetch_and_cache_jwks(force_refresh: bool = False) -> Dict[str, Dict[str, Any]]:
    """Fetches public keys from Supabase JWKS endpoint and updates in-memory cache.

    Guarantees:
    1. Returns cached keys when within TTL and force_refresh is False.
    2. Debounces rapid subsequent fetches to prevent cache-stampede / DoS on unknown kids.
    3. Fails closed and preserves existing cache if the network call fails.
    """
    global _JWKS_CACHE, _JWKS_LAST_FETCH_TIME
    now = time.time()

    if not force_refresh and _JWKS_CACHE and (now - _JWKS_LAST_FETCH_TIME < _JWKS_CACHE_TTL_SECONDS):
        return _JWKS_CACHE

    if (now - _JWKS_LAST_FETCH_TIME < _JWKS_MIN_REFRESH_INTERVAL) and _JWKS_CACHE:
        return _JWKS_CACHE

    jwks_url = get_supabase_jwks_url()
    if not jwks_url:
        return _JWKS_CACHE

    try:
        import httpx
        resp = httpx.get(jwks_url, timeout=5.0)
        if resp.status_code != 200:
            logger.warning(f"Failed to fetch Supabase JWKS from {jwks_url} (HTTP {resp.status_code}): {resp.text}")
            return _JWKS_CACHE

        data = resp.json()
        keys_list = data.get("keys", [])
        new_cache: Dict[str, Dict[str, Any]] = {}
        for key_dict in keys_list:
            kid = key_dict.get("kid")
            if kid:
                new_cache[kid] = key_dict

        _JWKS_CACHE = new_cache
        _JWKS_LAST_FETCH_TIME = now
        logger.info(f"Refreshed Supabase JWKS cache with {len(new_cache)} public key(s).")
        return _JWKS_CACHE
    except Exception as exc:
        logger.warning(f"Network error querying Supabase JWKS at {jwks_url}: {exc}")
        return _JWKS_CACHE


def get_jwk_key_by_kid(kid: str) -> Optional[Any]:
    """Retrieves and constructs a public key object for the given kid.

    If the kid is not present in the current cache, forces a refresh against the JWKS endpoint.
    """
    keys = _JWKS_CACHE
    if not keys or kid not in keys:
        keys = fetch_and_cache_jwks(force_refresh=True)

    key_dict = keys.get(kid)
    if not key_dict:
        return None

    try:
        return jwk.construct(key_dict)
    except Exception as exc:
        logger.error(f"Failed to construct public key from JWK for kid '{kid}': {exc}")
        return None


def verify_token_claims(token: str) -> Tuple[Dict[str, Any], Optional[str], Optional[UserRole]]:
    """Cryptographically validates bearer token claims.

    Supports:
    1. Supabase Auth asymmetric signed JWTs (RS256/ES256) via Supabase JWKS endpoint with kid matching.
    2. Supabase Auth legacy symmetric signed JWTs (HS256) via explicitly configured SUPABASE_JWT_SECRET.
    3. Test harness tokens ('test_token:<role>:<user_id>:<email>[:<org_id>]') strictly in TEST environment.
    """
    if settings.APP_ENV == AppEnv.TEST and token.startswith("test_token:"):
        parts = token.split(":")
        role_str = parts[1] if len(parts) > 1 else "AP_ASSOCIATE"
        user_id = parts[2] if len(parts) > 2 else "usr_test_01"
        email = parts[3] if len(parts) > 3 else "test.user@company.internal"
        if len(parts) > 4:
            hint_org = parts[4] if parts[4] not in ("NONE", "") else None
        else:
            hint_org = None if role_str in ("UNPROVISIONED", "NONE") else "org_default"

        role_enum = UserRole(role_str) if role_str in UserRole.__members__ else None
        claims = {
            "sub": user_id,
            "email": email,
            "name": "Test Authenticated User",
            "aud": "authenticated",
        }
        return claims, hint_org, role_enum

    # 1. Unverified Header Extraction
    try:
        unverified_header = jwt.get_unverified_header(token)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Malformed JWT header: {str(exc)}",
            headers={"WWW-Authenticate": "Bearer"},
        )

    alg = unverified_header.get("alg")
    kid = unverified_header.get("kid")

    # 2. Strict Algorithm Whitelist (Never accept unsigned 'none' or arbitrary algorithms)
    if not alg or alg not in ALLOWED_JWT_ALGORITHMS or alg == "none":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Unsupported or disallowed JWT algorithm '{alg}'. Accepted: {sorted(list(ALLOWED_JWT_ALGORITHMS))}.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 3. Resolve Cryptographic Verification Key
    verification_key: Any = None

    if alg in ("RS256", "ES256"):
        # Asymmetric Verification via JWKS
        if not kid:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Asymmetric token ({alg}) requires a 'kid' (Key ID) header.",
                headers={"WWW-Authenticate": "Bearer"},
            )
        verification_key = get_jwk_key_by_kid(kid)
        if not verification_key:
            jwks_url = get_supabase_jwks_url()
            err_msg = f"Public key for kid '{kid}' not found in Supabase JWKS."
            if not jwks_url and not _JWKS_CACHE:
                err_msg = "Supabase JWKS endpoint is not configured and key is not cached."
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=err_msg,
                headers={"WWW-Authenticate": "Bearer"},
            )

    elif alg == "HS256":
        # Legacy Symmetric Path
        jwt_secret = settings.SUPABASE_JWT_SECRET
        if not jwt_secret and settings.APP_ENV == AppEnv.TEST:
            jwt_secret = settings.SECRET_KEY

        if not jwt_secret:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Legacy HS256 token received but SUPABASE_JWT_SECRET is not configured for symmetric verification.",
                headers={"WWW-Authenticate": "Bearer"},
            )
        verification_key = jwt_secret

    # 4. Audience and Issuer Verification Constraints
    expected_aud = settings.SUPABASE_AUDIENCE or "authenticated"
    valid_issuers = set()
    if settings.SUPABASE_ISSUER:
        valid_issuers.add(settings.SUPABASE_ISSUER.rstrip('/'))
        if not settings.SUPABASE_ISSUER.endswith("/auth/v1"):
            valid_issuers.add(f"{settings.SUPABASE_ISSUER.rstrip('/')}/auth/v1")
    if settings.SUPABASE_URL:
        valid_issuers.add(f"{settings.SUPABASE_URL.rstrip('/')}/auth/v1")
        valid_issuers.add(settings.SUPABASE_URL.rstrip('/'))
    expected_iss = list(valid_issuers) if valid_issuers else None

    options = {
        "verify_signature": True,
        "verify_aud": bool(expected_aud),
        "verify_exp": True,
        "verify_iss": bool(expected_iss),
    }

    try:
        claims = jwt.decode(
            token,
            verification_key,
            algorithms=[alg],
            audience=expected_aud if options["verify_aud"] else None,
            issuer=expected_iss if options["verify_iss"] else None,
            options=options,
        )

        sub = claims.get("sub")
        email = claims.get("email")
        if not sub or not email:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token claims: sub (user_id) and email are required.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        db_role = claims.get("role")
        if db_role and db_role not in ("authenticated", "service_role", "anon"):
            if db_role not in UserRole.__members__:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail=f"Invalid database role claim '{db_role}'. Expected 'authenticated'.",
                    headers={"WWW-Authenticate": "Bearer"},
                )

        # Extract separate application role claim (user_role, app_metadata.role, or fallback to legacy role claim)
        app_metadata = claims.get("app_metadata")
        app_metadata_role = app_metadata.get("role") if isinstance(app_metadata, dict) else None
        app_role_claim = claims.get("user_role") or app_metadata_role or (db_role if db_role in UserRole.__members__ else None)
        hint_role = UserRole(app_role_claim) if app_role_claim and app_role_claim in UserRole.__members__ else None
        hint_org = claims.get("org_id")

        return claims, hint_org, hint_role

    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired. Please re-authenticate.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.JWTClaimsError as err:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token claims validation failed: {str(err)}",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except (JWTError, Exception) as exc:
        logger.error(f"JWT cryptographic validation failed ({alg}): {exc}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token or signature verification failed.",
            headers={"WWW-Authenticate": "Bearer"},
        )


def resolve_server_side_membership(
    auth_user_id: str,
    email: str,
    requested_org_id: Optional[str] = None,
    db: Optional[Session] = None,
    hint_org_id: Optional[str] = None,
    hint_role: Optional[UserRole] = None,
) -> Tuple[Optional[str], Optional[str], Optional[UserRole], bool, List[Dict[str, str]]]:
    """Resolves authenticated user organisation membership from server-side database records.

    Solves the RLS bootstrap sequence:
    1. Queries user memberships across organisations (using SECURITY DEFINER function in PostgreSQL
       or explicit un-scoped query before tenant context is set).
    2. Validates that the user has an active membership.
    3. If multiple organisations exist, validates requested_org_id against user's actual memberships.
    4. Returns: (resolved_org_id, resolved_org_name, resolved_role, is_provisioned, available_orgs).
    """
    if db is None:
        # Fallback when database is unconfigured
        if hint_org_id:
            return hint_org_id, "Default Organisation", hint_role or UserRole.AP_ASSOCIATE, True, [{"id": hint_org_id, "name": "Default Organisation"}]
        return None, None, None, False, []

    memberships: List[Dict[str, Any]] = []

    try:
        # 1. Attempt PostgreSQL SECURITY DEFINER lookup if running against live PostgreSQL
        if db.bind and "postgresql" in db.bind.dialect.name:
            res = db.execute(
                text("SELECT user_id, org_id, org_name, role_name, is_active FROM resolve_user_memberships(:uid, :email);"),
                {"uid": auth_user_id, "email": email}
            ).fetchall()
            for r in res:
                memberships.append({
                    "user_id": r[0],
                    "org_id": r[1],
                    "org_name": r[2],
                    "role": r[3],
                    "is_active": r[4],
                })
        else:
            # 2. SQLite / unit test bootstrap query
            stmt = (
                select(User.id, User.org_id, Organisation.name, RoleAssignment.role_name, User.is_active)
                .join(Organisation, Organisation.id == User.org_id)
                .outerjoin(
                    RoleAssignment,
                    and_(RoleAssignment.user_id == User.id, RoleAssignment.org_id == User.org_id)
                )
                .where(
                    or_(User.id == auth_user_id, func.lower(User.email) == email.lower()),
                    User.is_active == True,
                )
            )
            rows = db.execute(stmt).fetchall()
            for r in rows:
                memberships.append({
                    "user_id": r[0],
                    "org_id": r[1],
                    "org_name": r[2],
                    "role": r[3] or "AP_ASSOCIATE",
                    "is_active": r[4],
                })
    except Exception as exc:
        logger.debug(f"Membership query failed: {exc}")

    # If no records exist in database
    if not memberships:
        # In test mode with explicit test token hint before seeding
        if settings.APP_ENV == AppEnv.TEST and hint_org_id:
            return hint_org_id, "Test Organisation", hint_role or UserRole.AP_ASSOCIATE, True, [{"id": hint_org_id, "name": "Test Organisation"}]
        # User is authenticated in Supabase but has NO active organization membership (uninvited/unprovisioned)
        return None, None, None, False, []

    available_orgs = [{"id": m["org_id"], "name": m["org_name"]} for m in memberships]

    # Validate requested_org_id if supplied by client header
    if requested_org_id:
        matching = [m for m in memberships if m["org_id"] == requested_org_id]
        if not matching:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied: User is not an active member of organisation '{requested_org_id}'.",
            )
        selected = matching[0]
    else:
        selected = memberships[0]

    role_val = selected["role"]
    resolved_role = UserRole(role_val) if role_val in UserRole.__members__ else UserRole.AP_ASSOCIATE

    return selected["org_id"], selected["org_name"], resolved_role, True, available_orgs


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(security_bearer),
    db: Optional[Session] = Depends(get_db),
    requested_org: Optional[str] = Header(None, alias="X-Tenant-ID"),
) -> AuthenticatedUser:
    """Dependency verifying identity and resolving server-side membership.

    Enforces:
    1. Cryptographic JWT signature and claim validation.
    2. Server-side membership lookup (resolves org_id and role).
    3. Rejection of unauthenticated requests (HTTP 401).
    4. Transaction-local tenant context binding ONLY after membership is confirmed.
    """
    if credentials is None or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Please provide a valid Bearer token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    claims, hint_org, hint_role = verify_token_claims(credentials.credentials)
    user_id = claims["sub"]
    email = claims["email"]
    name = claims.get("name") or email.split("@")[0]

    org_id, org_name, role, is_provisioned, available_orgs = resolve_server_side_membership(
        auth_user_id=user_id,
        email=email,
        requested_org_id=requested_org,
        db=db,
        hint_org_id=hint_org,
        hint_role=hint_role,
    )

    # Establish transaction-local tenant context strictly after membership is confirmed
    if is_provisioned and org_id and db is not None:
        set_tenant_context(db, org_id)

    return AuthenticatedUser(
        id=user_id,
        email=email,
        name=name,
        role=role,
        org_id=org_id,
        org_name=org_name,
        is_provisioned=is_provisioned,
        available_orgs=available_orgs,
    )


def require_active_membership(
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> AuthenticatedUser:
    """Dependency barring uninvited / unprovisioned users from accessing tenant data."""
    if not current_user.is_provisioned or not current_user.org_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: User is not provisioned in any active organisation. "
                   "Please request access or accept an invitation to proceed.",
        )
    return current_user


def require_role(allowed_roles: List[UserRole]):
    """Dependency generator enforcing server-side Role-Based Access Control."""
    def role_checker(current_user: AuthenticatedUser = Depends(require_active_membership)) -> AuthenticatedUser:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Operation forbidden for role '{current_user.role.value if current_user.role else 'NONE'}'. "
                       f"Allowed roles: {[r.value for r in allowed_roles]}",
            )
        return current_user
    return role_checker


class MaintenanceActor(BaseModel):
    """Encapsulates authenticated caller identity for scheduled/operator maintenance tasks."""
    id: str
    email: str
    actor_type: str  # "CLOUD_SCHEDULER" or "USER"
    role: Optional[UserRole] = None
    org_id: Optional[str] = None
    is_provisioned: bool = True


def require_maintenance_auth(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Security(security_bearer),
    db: Optional[Session] = Depends(get_db),
) -> MaintenanceActor:
    """Dependency verifying caller identity for maintenance operations (Stage 7.1).

    Enforces:
    1. Rejects unauthenticated requests (HTTP 401).
    2. Allows dedicated Google Cloud Scheduler service account via Google OIDC Bearer token.
       - Validates issuer ('https://accounts.google.com').
       - Validates email strictly matches settings.CLOUD_SCHEDULER_SERVICE_ACCOUNT_EMAIL.
       - Validates audience matches target URI or settings.CLOUD_SCHEDULER_VERIFICATION_AUDIENCE.
       - Strictly rejects unrelated service accounts (e.g. Pub/Sub push identity) with HTTP 403.
    3. Allows human operators authenticated via Supabase Auth JWT with SYSTEM_ADMIN or CONTROLLER role.
    4. Does not expect Google service accounts to be Supabase employees.
    5. Does not weaken normal user JWT validation or RBAC on non-maintenance endpoints.
    """
    if credentials is None or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required for maintenance operations.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    raw_token = credentials.credentials.strip()

    # 1. Test environment handling
    if settings.APP_ENV == AppEnv.TEST:
        if raw_token.startswith("test_scheduler:"):
            parts = raw_token.split(":", 2)
            # test_scheduler:<email>:<aud>
            email = parts[1] if len(parts) > 1 else (settings.CLOUD_SCHEDULER_SERVICE_ACCOUNT_EMAIL or "cloud-scheduler@gcp.internal")
            aud = parts[2] if len(parts) > 2 else (settings.CLOUD_SCHEDULER_VERIFICATION_AUDIENCE or str(request.url))

            if settings.CLOUD_SCHEDULER_SERVICE_ACCOUNT_EMAIL and email != settings.CLOUD_SCHEDULER_SERVICE_ACCOUNT_EMAIL:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Unauthorized service account identity: '{email}'. Expected '{settings.CLOUD_SCHEDULER_SERVICE_ACCOUNT_EMAIL}'.",
                )
            if settings.CLOUD_SCHEDULER_VERIFICATION_AUDIENCE and aud != settings.CLOUD_SCHEDULER_VERIFICATION_AUDIENCE:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Audience mismatch: expected '{settings.CLOUD_SCHEDULER_VERIFICATION_AUDIENCE}', got '{aud}'.",
                )
            return MaintenanceActor(
                id=f"service:{email}",
                email=email,
                actor_type="CLOUD_SCHEDULER",
                role=UserRole.SYSTEM_ADMIN,
            )
        elif raw_token == "test_scheduler_invalid":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid Cloud Scheduler token signature.",
            )
        elif raw_token.startswith("test_oidc:"):
            # Pub/Sub push identity must NOT be allowed to invoke maintenance endpoints
            parts = raw_token.split(":")
            email = parts[1] if len(parts) > 1 else "pubsub@gcp.internal"
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Unauthorized service identity: '{email}'. Pub/Sub push identity is restricted from maintenance operations.",
            )

    # 2. Inspect unverified claims to distinguish Google OIDC vs Supabase tokens
    is_google_issuer = False
    unverified_claims: Dict[str, Any] = {}
    try:
        unverified_claims = jwt.get_unverified_claims(raw_token)
        iss = unverified_claims.get("iss", "")
        if iss in ("https://accounts.google.com", "accounts.google.com"):
            is_google_issuer = True
    except Exception:
        is_google_issuer = False

    if is_google_issuer:
        # Validate as Google OIDC token for Cloud Scheduler
        try:
            email = unverified_claims.get("email", "")
            aud = unverified_claims.get("aud", "")

            expected_email = settings.CLOUD_SCHEDULER_SERVICE_ACCOUNT_EMAIL
            if not expected_email:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Cloud Scheduler service account identity is not configured on this server.",
                )
            if email != expected_email:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Unauthorized service account identity: '{email}'. Expected '{expected_email}'.",
                )

            # Validate audience
            expected_aud = settings.CLOUD_SCHEDULER_VERIFICATION_AUDIENCE or str(request.url)
            if expected_aud and aud != expected_aud and str(request.url) not in aud:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Audience mismatch: expected '{expected_aud}', got '{aud}'.",
                )

            # In production or staging, verify signature against Google's public certs
            if settings.APP_ENV in (AppEnv.PRODUCTION, AppEnv.STAGING):
                import requests
                jwks_resp = requests.get("https://www.googleapis.com/oauth2/v3/certs", timeout=5)
                jwks = jwks_resp.json()
                jwt.decode(raw_token, jwks, algorithms=["RS256"], audience=aud)

            return MaintenanceActor(
                id=f"service:{email}",
                email=email,
                actor_type="CLOUD_SCHEDULER",
                role=UserRole.SYSTEM_ADMIN,
            )
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Cloud Scheduler OIDC token validation failed: {str(exc)}",
            )

    # 3. If not Google issuer, validate as human user via Supabase Auth
    try:
        requested_org = request.headers.get("x-tenant-id")
        user = get_current_user(credentials=credentials, db=db, requested_org=requested_org)
        if user.role not in (UserRole.SYSTEM_ADMIN, UserRole.CONTROLLER):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Operation forbidden for role '{user.role.value if user.role else 'NONE'}'. "
                       f"Allowed roles: {[UserRole.SYSTEM_ADMIN.value, UserRole.CONTROLLER.value]}",
            )
        return MaintenanceActor(
            id=user.id,
            email=user.email,
            actor_type="USER",
            role=user.role,
            org_id=user.org_id,
            is_provisioned=user.is_provisioned,
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Authentication failed: {str(exc)}",
        )
