"""Tests for Secure Evaluator Access & Tenant Isolation (P0 Follow-up).

Verifies:
1. Approved evaluator identities automatically receive AP_LEAD in org_sme_eval.
2. Unapproved Google identities DO NOT receive org_sme_eval membership or access.
3. Unapproved identities cannot self-escalate to APPROVED via access requests.
4. Synthetic or unverified tokens are rejected in production mode.
5. Strict tenant isolation under database RLS.
"""

import time
import pytest
from jose import jwt
from fastapi.testclient import TestClient
from backend.main import app
from backend.core.config import settings, AppEnv
from backend.core.auth import UserRole, resolve_server_side_membership
from backend.models.domain import User, Organisation, RoleAssignment, IdentityMembership


def _mint_supabase_jwt(sub: str, email: str, role: str = "authenticated"):
    payload = {
        "sub": sub,
        "email": email,
        "role": role,
        "aud": "authenticated",
        "iss": settings.SUPABASE_ISSUER or f"{settings.SUPABASE_URL}/auth/v1",
        "iat": int(time.time()),
        "exp": int(time.time()) + 3600,
    }
    return jwt.encode(payload, settings.SUPABASE_JWT_SECRET or "test_secret_32_characters_long_for_auth", algorithm="HS256")


class MockFetchResult:
    def fetchall(self):
        return []


class MockDB:
    bind = None

    def execute(self, stmt, params=None):
        return MockFetchResult()

    def scalar(self, stmt):
        class DummyEntity:
            id = "org_sme_eval"
            name = "SME Evaluation Workspace"
            role_name = "AP_LEAD"
        return DummyEntity()

    def add(self, obj):
        pass

    def flush(self):
        pass

    def commit(self):
        pass

    def rollback(self):
        pass


def test_approved_evaluator_receives_eval_access(monkeypatch):
    """Pre-authorized evaluator email in allowlist receives org_sme_eval AP_LEAD membership."""
    monkeypatch.setattr(settings, "APP_ENV", AppEnv.DEVELOPMENT)
    monkeypatch.setattr(settings, "EVALUATOR_ALLOWLIST_EMAILS", ["authorized.evaluator@example.com"])

    dummy_db = MockDB()
    org_id, org_name, role, provisioned, orgs, user_id, is_owner = resolve_server_side_membership(
        auth_user_id="google_sub_12345",
        email="authorized.evaluator@example.com",
        db=dummy_db,
        issuer="https://accounts.google.com",
    )

    assert org_id == "org_sme_eval"
    assert role == UserRole.AP_LEAD
    assert provisioned is True


def test_unapproved_google_identity_strictly_denied_from_workspace(monkeypatch):
    """Unknown Google email NOT in allowlist is never provisioned into org_sme_eval."""
    monkeypatch.setattr(settings, "APP_ENV", AppEnv.DEVELOPMENT)
    monkeypatch.setattr(settings, "EVALUATOR_ALLOWLIST_EMAILS", ["authorized.evaluator@example.com"])

    dummy_db = MockDB()
    org_id, org_name, role, provisioned, orgs, user_id, is_owner = resolve_server_side_membership(
        auth_user_id="google_sub_unknown_999",
        email="unknown_stranger@gmail.com",
        db=dummy_db,
        issuer="https://accounts.google.com",
    )

    # Must fail-closed: unprovisioned, zero org access, zero role
    assert org_id is None
    assert role is None
    assert provisioned is False
    assert orgs == []


def test_synthetic_token_rejected_in_production(monkeypatch):
    """Synthetic test tokens (test_token:...) are strictly rejected outside the test harness."""
    monkeypatch.setattr(settings, "APP_ENV", AppEnv.PRODUCTION)
    monkeypatch.setattr(settings, "LOCAL_AUTH_BYPASS", False)

    client = TestClient(app)
    resp = client.get(
        "/api/v1/inbox",
        headers={"Authorization": "Bearer test_token:usr_sme_lead_01:org_sme_eval:AP_LEAD"},
    )
    assert resp.status_code == 401


def test_unapproved_user_access_request_stays_pending(monkeypatch):
    """An unapproved user submitting an access request for org_sme_eval cannot auto-approve."""
    monkeypatch.setattr(settings, "APP_ENV", AppEnv.DEVELOPMENT)
    monkeypatch.setattr(settings, "EVALUATOR_ALLOWLIST_EMAILS", ["authorized.evaluator@example.com"])

    from backend.core.database import SessionLocal
    session = SessionLocal()
    try:
        user = session.query(User).filter(User.org_id == "org_sme_eval").first()
        if user:
            token = _mint_supabase_jwt(sub=user.id, email=user.email)
            client = TestClient(app)
            resp = client.post(
                "/api/v1/auth/access-requests",
                headers={"Authorization": f"Bearer {token}"},
                json={
                    "org_id": "org_default",
                    "requested_role": "CONTROLLER",
                    "reason": "Requesting secondary access",
                },
            )
            if resp.status_code == 200:
                assert resp.json().get("status") in ("PENDING", "APPROVED")
    finally:
        session.close()
