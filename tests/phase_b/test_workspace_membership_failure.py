from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from backend.core.auth import AuthenticatedUser, UserRole, resolve_server_side_membership, verify_platform_operator
from backend.core.config import AppEnv, settings


def test_membership_lookup_failure_is_not_an_unprovisioned_user():
    db = MagicMock()
    db.bind.dialect.name = "sqlite"
    db.execute.side_effect = RuntimeError("database unavailable")

    with pytest.raises(HTTPException) as error:
        resolve_server_side_membership("subject", "user@example.com", db=db)

    assert error.value.status_code == 503
    assert "membership could not be verified" in error.value.detail


def test_missing_database_does_not_trust_tenant_hint(monkeypatch):
    monkeypatch.setattr(settings, "APP_ENV", AppEnv.DEVELOPMENT)
    with pytest.raises(HTTPException) as error:
        resolve_server_side_membership("subject", "user@example.com", hint_org_id="org_other")
    assert error.value.status_code == 503


def test_workspace_admin_is_not_automatically_a_platform_operator(monkeypatch):
    user = AuthenticatedUser(id="owner", email="owner@example.com", name="Owner", role=UserRole.SYSTEM_ADMIN, org_id="org", is_provisioned=True)
    monkeypatch.setattr(settings, "PLATFORM_OPERATOR_SUBJECTS", "other")
    with pytest.raises(HTTPException) as error:
        verify_platform_operator(user)
    assert error.value.status_code == 403
    monkeypatch.setattr(settings, "PLATFORM_OPERATOR_SUBJECTS", "other, owner")
    verify_platform_operator(user)


def test_platform_allowlist_uses_identity_subject_not_tenant_user_id(monkeypatch):
    user = AuthenticatedUser(id="local-user", auth_subject="identity", email="owner@example.com", name="Owner", role=UserRole.SYSTEM_ADMIN, org_id="org", is_provisioned=True)
    monkeypatch.setattr(settings, "PLATFORM_OPERATOR_SUBJECTS", "local-user")
    with pytest.raises(HTTPException):
        verify_platform_operator(user)
    monkeypatch.setattr(settings, "PLATFORM_OPERATOR_SUBJECTS", "identity")
    verify_platform_operator(user)
