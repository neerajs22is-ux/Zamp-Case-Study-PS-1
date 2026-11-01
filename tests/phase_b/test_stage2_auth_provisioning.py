"""Phase B Stage 2 Acceptance Tests — Authentication & User Provisioning.

Comprehensive validation of the 16 binding security requirements:
Test 01: Valid Supabase JWT accepted.
Test 02: Invalid JWT signature rejected (HTTP 401).
Test 03: Expired token rejected (HTTP 401).
Test 04: Wrong JWT issuer rejected (HTTP 401).
Test 05: Wrong audience rejected (HTTP 401).
Test 06: Uninvited user denied tenant access (HTTP 403).
Test 07: Valid invitation accepted (membership created, status ACCEPTED, single-use).
Test 08: Invitation email mismatch rejected (HTTP 400).
Test 09: Expired invitation rejected (HTTP 400).
Test 10: Request access does not create active membership (status PENDING).
Test 11: Only authorized administrators can approve access requests.
Test 12: User cannot modify their own role (HTTP 400) or deactivate themselves.
Test 13: Cross-tenant membership selection rejected (HTTP 403).
Test 14: Membership revocation takes effect (is_active=False fails closed).
Test 15: Tenant context established only after membership validation.
Test 16: Existing RBAC and audit immutability preserved.
"""

from __future__ import annotations

import datetime
import os
import uuid
from typing import Any, Dict, Optional

from fastapi import status
from fastapi.testclient import TestClient
from jose import jwt
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from backend.core.config import AppEnv, settings
from backend.core.database import Base, get_db
from backend.main import app
from backend.models.domain import (
    AccessRequest, AuditEvent, Invoice, Organisation, RoleAssignment, User, UserInvitation
)

# Test cryptographic constants
TEST_JWT_SECRET = "stage2-super-secret-jwt-key-32-chars-long"
TEST_ISSUER = "https://test-project.supabase.co/auth/v1"
TEST_AUDIENCE = "authenticated"


@pytest.fixture(autouse=True)
def configure_stage2_auth_settings():
    """Configures Supabase Auth settings for all Stage 2 acceptance tests."""
    orig_env = settings.APP_ENV
    orig_secret = settings.SUPABASE_JWT_SECRET
    orig_iss = settings.SUPABASE_ISSUER
    orig_aud = settings.SUPABASE_AUDIENCE
    orig_url = settings.SUPABASE_URL

    settings.APP_ENV = AppEnv.TEST
    settings.SUPABASE_JWT_SECRET = TEST_JWT_SECRET
    settings.SUPABASE_ISSUER = TEST_ISSUER
    settings.SUPABASE_AUDIENCE = TEST_AUDIENCE
    settings.SUPABASE_URL = "https://test-project.supabase.co"

    yield

    settings.APP_ENV = orig_env
    settings.SUPABASE_JWT_SECRET = orig_secret
    settings.SUPABASE_ISSUER = orig_iss
    settings.SUPABASE_AUDIENCE = orig_aud
    settings.SUPABASE_URL = orig_url


@pytest.fixture
def stage2_db():
    """Provides a fresh, isolated in-memory SQLite database for each acceptance test."""
    from sqlalchemy.pool import StaticPool
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)

    with engine.connect() as conn:
        conn.exec_driver_sql("""
            CREATE TRIGGER IF NOT EXISTS trg_audit_events_no_update
            BEFORE UPDATE ON audit_events
            BEGIN
                SELECT RAISE(ABORT, 'audit_events is strictly append-only: UPDATE operations are prohibited.');
            END;
        """)
        conn.exec_driver_sql("""
            CREATE TRIGGER IF NOT EXISTS trg_audit_events_no_delete
            BEFORE DELETE ON audit_events
            BEGIN
                SELECT RAISE(ABORT, 'audit_events is strictly append-only: DELETE operations are prohibited.');
            END;
        """)
        conn.commit()

    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = SessionLocal()

    yield session, engine

    session.close()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture
def stage2_client(stage2_db):
    """FastAPI TestClient with isolated Stage 2 database session override."""
    session, _ = stage2_db

    def override_get_db():
        try:
            yield session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as client:
        yield client, session
    app.dependency_overrides.clear()


def make_supabase_jwt(
    sub: str = "usr_01",
    email: str = "alice@alpha.internal",
    name: str = "Alice Employee",
    aud: Optional[str] = TEST_AUDIENCE,
    iss: Optional[str] = TEST_ISSUER,
    expires_in_seconds: int = 3600,
    secret: str = TEST_JWT_SECRET,
    alg: str = "HS256",
) -> str:
    """Generates an RFC-compliant JWT with Supabase Auth claims."""
    now = datetime.datetime.now(datetime.timezone.utc)
    exp = now + datetime.timedelta(seconds=expires_in_seconds)
    payload: Dict[str, Any] = {
        "sub": sub,
        "email": email,
        "name": name,
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
    }
    if aud is not None:
        payload["aud"] = aud
    if iss is not None:
        payload["iss"] = iss

    return jwt.encode(payload, secret, algorithm=alg)


# ==============================================================================
# 16 Acceptance Tests
# ==============================================================================

def test_01_valid_supabase_jwt_accepted(stage2_client):
    """Test 1: Valid Supabase JWT with correct signature, issuer, audience, and active membership succeeds."""
    client, session = stage2_client

    # Seed organisation and active member
    org = Organisation(id="org_alpha", name="Alpha Corp")
    user = User(id="usr_01", org_id="org_alpha", email="alice@alpha.internal", full_name="Alice Member", is_active=True)
    role = RoleAssignment(id="ra_01", org_id="org_alpha", user_id="usr_01", role_name="AP_ASSOCIATE")
    session.add_all([org, user, role])
    session.commit()

    token = make_supabase_jwt(sub="usr_01", email="alice@alpha.internal")
    resp = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})

    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()
    assert data["id"] == "usr_01"
    assert data["email"] == "alice@alpha.internal"
    assert data["role"] == "AP_ASSOCIATE"
    assert data["org_id"] == "org_alpha"
    assert data["is_provisioned"] is True
    assert data["status"] == "ACTIVE"


def test_02_invalid_jwt_signature_rejected(stage2_client):
    """Test 2: Invalid JWT signature is cryptographically rejected with HTTP 401."""
    client, _ = stage2_client

    untrusted_secret = "attacker-compromised-key-that-does-not-match"
    token = make_supabase_jwt(sub="usr_02", email="bob@alpha.internal", secret=untrusted_secret)

    resp = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == status.HTTP_401_UNAUTHORIZED
    assert "signature verification failed" in resp.json()["detail"].lower()


def test_03_expired_token_rejected(stage2_client):
    """Test 3: Token with exp in the past is rejected with HTTP 401."""
    client, _ = stage2_client

    token = make_supabase_jwt(sub="usr_03", email="charlie@alpha.internal", expires_in_seconds=-120)

    resp = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == status.HTTP_401_UNAUTHORIZED
    assert "expired" in resp.json()["detail"].lower()


def test_04_wrong_jwt_issuer_rejected(stage2_client):
    """Test 4: Token from untrusted issuer is rejected with HTTP 401."""
    client, _ = stage2_client

    token = make_supabase_jwt(sub="usr_04", email="dave@alpha.internal", iss="https://rogue-idp.example.com/auth/v1")

    resp = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == status.HTTP_401_UNAUTHORIZED
    assert "claims validation failed" in resp.json()["detail"].lower()


def test_05_wrong_audience_rejected(stage2_client):
    """Test 5: Token issued for different audience is rejected with HTTP 401."""
    client, _ = stage2_client

    token = make_supabase_jwt(sub="usr_05", email="eve@alpha.internal", aud="third-party-mobile-app")

    resp = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == status.HTTP_401_UNAUTHORIZED
    assert "claims validation failed" in resp.json()["detail"].lower()


def test_06_uninvited_user_denied_tenant_access(stage2_client):
    """Test 6: Authenticated employee without organisation membership is denied tenant access (HTTP 403)."""
    client, _ = stage2_client

    # User authenticates with Google successfully, but has no record in any organisation
    token = make_supabase_jwt(sub="usr_uninvited", email="visitor@outside.com")

    # Profile endpoint succeeds but truthfully reports UNPROVISIONED
    me_resp = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_resp.status_code == status.HTTP_200_OK
    assert me_resp.json()["is_provisioned"] is False
    assert me_resp.json()["status"] == "UNPROVISIONED"
    assert me_resp.json()["org_id"] is None
    assert me_resp.json()["role"] is None

    # Access to any tenant-scoped resource is strictly denied
    inbox_resp = client.get("/api/v1/inbox", headers={"Authorization": f"Bearer {token}"})
    assert inbox_resp.status_code == status.HTTP_403_FORBIDDEN
    assert "User is not provisioned in any active organisation" in inbox_resp.json()["detail"]


def test_07_valid_invitation_accepted(stage2_client):
    """Test 7: Valid single-use invitation is accepted, creates active membership, and invalidates token."""
    client, session = stage2_client

    # Seed organisation and Admin
    org = Organisation(id="org_alpha", name="Alpha Corp")
    admin = User(id="usr_admin", org_id="org_alpha", email="admin@alpha.internal", full_name="Admin", is_active=True)
    admin_role = RoleAssignment(id="ra_admin", org_id="org_alpha", user_id="usr_admin", role_name="SYSTEM_ADMIN")
    session.add_all([org, admin, admin_role])
    session.commit()

    admin_token = make_supabase_jwt(sub="usr_admin", email="admin@alpha.internal")

    # Step 1: Admin issues invitation
    invite_resp = client.post(
        "/api/v1/auth/invitations",
        json={"email": "new.hire@alpha.internal", "role": "AP_ASSOCIATE"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert invite_resp.status_code == status.HTTP_200_OK
    invitation_data = invite_resp.json()
    raw_invite_token = invitation_data["invitation_token"]
    assert len(raw_invite_token) > 20

    # Step 2: New employee authenticates with Google (unprovisioned)
    user_token = make_supabase_jwt(sub="usr_newhire", email="new.hire@alpha.internal", name="New Hire")

    # Step 3: Redeem invitation
    accept_resp = client.post(
        "/api/v1/auth/invitations/accept",
        json={"token": raw_invite_token},
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert accept_resp.status_code == status.HTTP_200_OK
    assert accept_resp.json()["status"] == "SUCCESS"
    assert accept_resp.json()["org_id"] == "org_alpha"

    # Step 4: Verify active membership in DB
    user_db = session.scalar(select(User).where(User.org_id == "org_alpha", User.email == "new.hire@alpha.internal"))
    assert user_db is not None
    assert user_db.is_active is True

    role_db = session.scalar(select(RoleAssignment).where(RoleAssignment.org_id == "org_alpha", RoleAssignment.user_id == "usr_newhire"))
    assert role_db is not None
    assert role_db.role_name == "AP_ASSOCIATE"

    # Step 5: Verify single-use invariant (re-use is rejected)
    reuse_resp = client.post(
        "/api/v1/auth/invitations/accept",
        json={"token": raw_invite_token},
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert reuse_resp.status_code == status.HTTP_400_BAD_REQUEST
    assert "no longer valid" in reuse_resp.json()["detail"].lower()


def test_08_invitation_email_mismatch_rejected(stage2_client):
    """Test 8: Redeeming an invitation with a mismatched signed-in email is rejected (HTTP 400)."""
    client, session = stage2_client

    org = Organisation(id="org_alpha", name="Alpha Corp")
    admin = User(id="usr_admin", org_id="org_alpha", email="admin@alpha.internal", full_name="Admin", is_active=True)
    admin_role = RoleAssignment(id="ra_admin", org_id="org_alpha", user_id="usr_admin", role_name="SYSTEM_ADMIN")
    session.add_all([org, admin, admin_role])
    session.commit()

    admin_token = make_supabase_jwt(sub="usr_admin", email="admin@alpha.internal")

    # Invite alice
    invite_resp = client.post(
        "/api/v1/auth/invitations",
        json={"email": "intended.recipient@alpha.internal", "role": "AP_ASSOCIATE"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    raw_token = invite_resp.json()["invitation_token"]

    # Bob attempts to redeem Alice's token
    bob_token = make_supabase_jwt(sub="usr_bob", email="wrong.person@alpha.internal")
    claim_resp = client.post(
        "/api/v1/auth/invitations/accept",
        json={"token": raw_token},
        headers={"Authorization": f"Bearer {bob_token}"},
    )
    assert claim_resp.status_code == status.HTTP_400_BAD_REQUEST
    assert "Email mismatch" in claim_resp.json()["detail"]


def test_09_expired_invitation_rejected(stage2_client):
    """Test 9: Attempting to redeem an expired invitation token is rejected with HTTP 400."""
    client, session = stage2_client

    org = Organisation(id="org_alpha", name="Alpha Corp")
    session.add(org)
    session.commit()

    import hashlib
    import secrets

    raw_token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()

    # Expired 2 days ago
    past_utc = datetime.datetime.utcnow() - datetime.timedelta(days=2)
    expired_inv = UserInvitation(
        id="inv_expired_01",
        org_id="org_alpha",
        email="late.employee@alpha.internal",
        role_name="AP_ASSOCIATE",
        token_hash=token_hash,
        invited_by_user_id="usr_admin",
        status="PENDING",
        expires_at=past_utc,
        created_at=past_utc - datetime.timedelta(days=7),
    )
    session.add(expired_inv)
    session.commit()

    user_token = make_supabase_jwt(sub="usr_late", email="late.employee@alpha.internal")
    resp = client.post(
        "/api/v1/auth/invitations/accept",
        json={"token": raw_token},
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert resp.status_code == status.HTTP_400_BAD_REQUEST
    assert "expired" in resp.json()["detail"].lower()

    # Verify status transitioned to EXPIRED
    session.refresh(expired_inv)
    assert expired_inv.status == "EXPIRED"


def test_10_request_access_does_not_create_active_membership(stage2_client):
    """Test 10: Submitting an access request leaves request in PENDING and does NOT grant membership."""
    client, session = stage2_client

    org = Organisation(id="org_alpha", name="Alpha Corp")
    session.add(org)
    session.commit()

    token = make_supabase_jwt(sub="usr_req_01", email="applicant@alpha.internal", name="Applicant")

    # Step 1: Submit request
    req_resp = client.post(
        "/api/v1/auth/access-requests",
        json={"org_id": "org_alpha", "requested_role": "AP_ASSOCIATE", "reason": "Joining AP operations"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert req_resp.status_code == status.HTTP_200_OK
    assert req_resp.json()["status"] == "PENDING"

    # Step 2: Verify user still cannot access tenant resources
    inbox_resp = client.get("/api/v1/inbox", headers={"Authorization": f"Bearer {token}"})
    assert inbox_resp.status_code == status.HTTP_403_FORBIDDEN

    # Step 3: Duplicate pending request is rejected
    dup_resp = client.post(
        "/api/v1/auth/access-requests",
        json={"org_id": "org_alpha", "requested_role": "AP_ASSOCIATE", "reason": "Duplicate attempt"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert dup_resp.status_code == status.HTTP_400_BAD_REQUEST
    assert "already pending" in dup_resp.json()["detail"].lower()


def test_11_only_authorized_administrators_can_approve_access_requests(stage2_client):
    """Test 11: Non-admin review is rejected; Controller/Admin review provisions active membership."""
    client, session = stage2_client

    org = Organisation(id="org_alpha", name="Alpha Corp")
    controller = User(id="usr_ctrl", org_id="org_alpha", email="ctrl@alpha.internal", full_name="Controller", is_active=True)
    ctrl_role = RoleAssignment(id="ra_ctrl", org_id="org_alpha", user_id="usr_ctrl", role_name="CONTROLLER")

    associate = User(id="usr_assoc", org_id="org_alpha", email="assoc@alpha.internal", full_name="Assoc", is_active=True)
    assoc_role = RoleAssignment(id="ra_assoc", org_id="org_alpha", user_id="usr_assoc", role_name="AP_ASSOCIATE")

    # Pending applicant
    req = AccessRequest(
        id="req_test_01",
        org_id="org_alpha",
        user_id="usr_applicant",
        email="applicant@alpha.internal",
        full_name="Applicant",
        requested_role="AP_ASSOCIATE",
        status="PENDING",
        created_at=datetime.datetime.utcnow(),
        updated_at=datetime.datetime.utcnow(),
    )
    session.add_all([org, controller, ctrl_role, associate, assoc_role, req])
    session.commit()

    assoc_token = make_supabase_jwt(sub="usr_assoc", email="assoc@alpha.internal")
    ctrl_token = make_supabase_jwt(sub="usr_ctrl", email="ctrl@alpha.internal")

    # Step 1: AP_ASSOCIATE cannot approve access requests
    unauth_resp = client.post(
        f"/api/v1/auth/access-requests/{req.id}/review",
        json={"action": "APPROVE", "role": "AP_ASSOCIATE", "reason": "Unauthorized associate review"},
        headers={"Authorization": f"Bearer {assoc_token}"},
    )
    assert unauth_resp.status_code == status.HTTP_403_FORBIDDEN

    # Step 2: CONTROLLER approves access request
    auth_resp = client.post(
        f"/api/v1/auth/access-requests/{req.id}/review",
        json={"action": "APPROVE", "role": "AP_ASSOCIATE", "reason": "Approved by Controller"},
        headers={"Authorization": f"Bearer {ctrl_token}"},
    )
    assert auth_resp.status_code == status.HTTP_200_OK
    assert auth_resp.json()["status"] == "APPROVED"

    # Step 3: Verified active membership created
    applicant_token = make_supabase_jwt(sub="usr_applicant", email="applicant@alpha.internal")
    inbox_resp = client.get("/api/v1/inbox", headers={"Authorization": f"Bearer {applicant_token}"})
    assert inbox_resp.status_code == status.HTTP_200_OK


def test_12_user_cannot_modify_their_own_role(stage2_client):
    """Test 12: Anti-self-promotion prevents users from modifying their own role or deactivating themselves."""
    client, session = stage2_client

    org = Organisation(id="org_alpha", name="Alpha Corp")
    admin = User(id="usr_admin", org_id="org_alpha", email="admin@alpha.internal", full_name="Admin User", is_active=True)
    admin_role = RoleAssignment(id="ra_admin", org_id="org_alpha", user_id="usr_admin", role_name="SYSTEM_ADMIN")
    session.add_all([org, admin, admin_role])
    session.commit()

    admin_token = make_supabase_jwt(sub="usr_admin", email="admin@alpha.internal")

    # Attempt to change own role
    role_resp = client.patch(
        f"/api/v1/auth/users/{admin.id}/role",
        json={"role": "CONTROLLER", "reason": "Self-modifying role"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert role_resp.status_code == status.HTTP_400_BAD_REQUEST
    assert "cannot modify their own role" in role_resp.json()["detail"]

    # Attempt to deactivate own account
    deact_resp = client.post(
        f"/api/v1/auth/users/{admin.id}/deactivate",
        json={"reason": "Self-deactivating"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert deact_resp.status_code == status.HTTP_400_BAD_REQUEST
    assert "cannot deactivate their own account" in deact_resp.json()["detail"]


def test_13_cross_tenant_membership_selection_rejected(stage2_client):
    """Test 13: Specifying X-Tenant-ID for an organisation where user is not an active member returns HTTP 403."""
    client, session = stage2_client

    org_a = Organisation(id="org_alpha", name="Alpha Corp")
    org_b = Organisation(id="org_beta", name="Beta Corp")
    user = User(id="usr_alpha_only", org_id="org_alpha", email="member@alpha.internal", full_name="Alpha Member", is_active=True)
    role = RoleAssignment(id="ra_alpha", org_id="org_alpha", user_id="usr_alpha_only", role_name="AP_ASSOCIATE")
    session.add_all([org_a, org_b, user, role])
    session.commit()

    token = make_supabase_jwt(sub="usr_alpha_only", email="member@alpha.internal")

    # Attempt to select org_beta via header
    resp = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}", "X-Tenant-ID": "org_beta"},
    )
    assert resp.status_code == status.HTTP_403_FORBIDDEN
    assert "not an active member of organisation 'org_beta'" in resp.json()["detail"]


def test_14_membership_revocation_takes_effect(stage2_client):
    """Test 14: When a user membership is deactivated (is_active=False), subsequent requests fail closed."""
    client, session = stage2_client

    org = Organisation(id="org_alpha", name="Alpha Corp")
    admin = User(id="usr_admin", org_id="org_alpha", email="admin@alpha.internal", full_name="Admin User", is_active=True)
    admin_role = RoleAssignment(id="ra_admin", org_id="org_alpha", user_id="usr_admin", role_name="SYSTEM_ADMIN")

    member = User(id="usr_member", org_id="org_alpha", email="member@alpha.internal", full_name="Regular Member", is_active=True)
    member_role = RoleAssignment(id="ra_member", org_id="org_alpha", user_id="usr_member", role_name="AP_ASSOCIATE")
    session.add_all([org, admin, admin_role, member, member_role])
    session.commit()

    admin_token = make_supabase_jwt(sub="usr_admin", email="admin@alpha.internal")
    member_token = make_supabase_jwt(sub="usr_member", email="member@alpha.internal")

    # Member initial access succeeds
    resp1 = client.get("/api/v1/inbox", headers={"Authorization": f"Bearer {member_token}"})
    assert resp1.status_code == status.HTTP_200_OK

    # Admin revokes membership
    deact_resp = client.post(
        f"/api/v1/auth/users/{member.id}/deactivate",
        json={"reason": "Employment terminated"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert deact_resp.status_code == status.HTTP_200_OK

    # Subsequent request fails closed
    resp2 = client.get("/api/v1/inbox", headers={"Authorization": f"Bearer {member_token}"})
    assert resp2.status_code == status.HTTP_403_FORBIDDEN
    assert "User is not provisioned in any active organisation" in resp2.json()["detail"]


def test_15_tenant_context_established_only_after_membership_validation(stage2_client):
    """Test 15: Tenant context is strictly bound only after membership is cryptographically & relationally confirmed."""
    client, session = stage2_client

    org = Organisation(id="org_alpha", name="Alpha Corp")
    user = User(id="usr_verified", org_id="org_alpha", email="verified@alpha.internal", full_name="Verified User", is_active=True)
    role = RoleAssignment(id="ra_verified", org_id="org_alpha", user_id="usr_verified", role_name="AP_ASSOCIATE")
    session.add_all([org, user, role])
    session.commit()

    # Step 1: Unprovisioned user calling tenant route fails before tenant context binding
    unprov_token = make_supabase_jwt(sub="usr_unprov", email="nobody@outside.com")
    resp_unprov = client.get("/api/v1/inbox", headers={"Authorization": f"Bearer {unprov_token}"})
    assert resp_unprov.status_code == status.HTTP_403_FORBIDDEN
    assert session.info.get("app.current_org_id") is None

    # Step 2: Valid membership binds tenant context
    prov_token = make_supabase_jwt(sub="usr_verified", email="verified@alpha.internal")
    resp_prov = client.get("/api/v1/inbox", headers={"Authorization": f"Bearer {prov_token}"})
    assert resp_prov.status_code == status.HTTP_200_OK
    assert session.info.get("app.current_org_id") == "org_alpha"


def test_16_existing_rbac_and_audit_immutability_preserved(stage2_client):
    """Test 16: Stage 2 preserves existing RBAC and ensures invitations/access audits are immutable."""
    client, session = stage2_client

    org = Organisation(id="org_alpha", name="Alpha Corp")
    admin = User(id="usr_admin", org_id="org_alpha", email="admin@alpha.internal", full_name="Admin User", is_active=True)
    admin_role = RoleAssignment(id="ra_admin", org_id="org_alpha", user_id="usr_admin", role_name="SYSTEM_ADMIN")

    auditor = User(id="usr_auditor", org_id="org_alpha", email="auditor@alpha.internal", full_name="Auditor User", is_active=True)
    auditor_role = RoleAssignment(id="ra_auditor", org_id="org_alpha", user_id="usr_auditor", role_name="AUDITOR")

    inv = Invoice(
        id="inv_test_immut",
        org_id="org_alpha",
        source_channel="MANUAL_UPLOAD",
        stage="RECEIVED",
        decision="NEEDS_REVIEW",
    )
    session.add_all([org, admin, admin_role, auditor, auditor_role, inv])
    session.commit()

    # Auditor is read-only: can read inbox, but cannot mutate invoice
    auditor_token = make_supabase_jwt(sub="usr_auditor", email="auditor@alpha.internal")
    inbox_resp = client.get("/api/v1/inbox", headers={"Authorization": f"Bearer {auditor_token}"})
    assert inbox_resp.status_code == status.HTTP_200_OK

    action_resp = client.post(
        f"/api/v1/invoices/{inv.id}/actions",
        json={"action": "APPROVE_AP_REVIEW", "reason": "Auditor trying to approve"},
        headers={"Authorization": f"Bearer {auditor_token}"},
    )
    assert action_resp.status_code == status.HTTP_403_FORBIDDEN
    assert "read-only and cannot execute mutations" in action_resp.json()["detail"]

    # Verify audit event insertion and immutability (UPDATE and DELETE prohibited by triggers)
    audit_evt = AuditEvent(
        id="evt_test_immut_01",
        org_id="org_alpha",
        actor_id="usr_admin",
        actor_role="SYSTEM_ADMIN",
        action="USER_INVITED",
        reason="Security test",
        timestamp=datetime.datetime.utcnow(),
    )
    session.add(audit_evt)
    session.commit()

    # Test UPDATE forbidden by ORM event listener / database trigger
    from sqlalchemy.exc import IntegrityError
    audit_evt.reason = "Tampered reason"
    with pytest.raises((PermissionError, IntegrityError)):
        session.commit()
    session.rollback()

    # Test DELETE forbidden by ORM event listener / database trigger
    session.delete(audit_evt)
    with pytest.raises((PermissionError, IntegrityError)):
        session.commit()
    session.rollback()
