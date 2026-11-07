"""Run against the isolated database supplied by scripts/inspect_postgres.py."""
import datetime
import os
import uuid

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from jose import jwt
from sqlalchemy import create_engine, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session
from sqlalchemy.pool import NullPool

from backend.core.auth import get_current_user
from backend.api.v1.auth import get_current_user_profile
from backend.core.config import AppEnv, settings
from backend.models.domain import AuditEvent, IdentityMembership, Organisation, RoleAssignment, User


def test_identity_memberships_isolate_and_revoke(monkeypatch, postgres_database):
    url = postgres_database['admin_url']
    engine = create_engine(url, poolclass=NullPool)
    suffix = uuid.uuid4().hex[:10]
    issuer, subject = "https://issuer.example.test/auth/v1", f"subject-{suffix}"
    org_a, org_b, org_c = (f"org-{suffix}-{x}" for x in "abc")
    local_b = f"member-{suffix}"
    secret = "test-only-identity-secret-at-least-32-characters"
    monkeypatch.setattr(settings, "APP_ENV", AppEnv.TEST)
    monkeypatch.setattr(settings, "SUPABASE_JWT_SECRET", secret)
    monkeypatch.setattr(settings, "SUPABASE_ISSUER", issuer)
    monkeypatch.setattr(settings, "SUPABASE_URL", None)
    monkeypatch.setattr(settings, "SUPABASE_AUDIENCE", "authenticated")
    token = jwt.encode({"sub": subject, "email": "same@example.test", "iss": issuer,
                        "aud": "authenticated", "exp": datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=1)}, secret, algorithm="HS256")
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
    try:
        with Session(engine) as db:
            db.add_all([Organisation(id=o, name=o) for o in (org_a, org_b, org_c)])
            db.add_all([User(id=subject, org_id=org_a, email="same@example.test", full_name="A", is_active=True),
                        User(id=local_b, org_id=org_b, email="same@example.test", full_name="B", is_active=True)])
            db.flush()
            db.add_all([RoleAssignment(id=f"ra-{suffix}", org_id=org_a, user_id=subject, role_name="AP_LEAD"),
                        RoleAssignment(id=f"rb-{suffix}", org_id=org_b, user_id=local_b, role_name="AUDITOR"),
                        AuditEvent(id=f"audit-{suffix}", org_id=org_a, actor_id=subject, actor_role="AP_LEAD", action="TEST")])
            db.commit()

        with Session(engine) as db:
            db.execute(text("SET ROLE ap_app_user"))
            legacy = get_current_user(credentials, db, None)
            assert legacy.id == subject and legacy.org_id == org_a and legacy.role.value == "AP_LEAD"
            other_token = jwt.encode({"sub": f"other-{suffix}", "email": "same@example.test", "iss": issuer,
                                      "aud": "authenticated", "exp": datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=1)}, secret, algorithm="HS256")
            other = get_current_user(HTTPAuthorizationCredentials(scheme="Bearer", credentials=other_token), db, None)
            assert not other.is_provisioned and not other.available_orgs
            with pytest.raises(HTTPException) as denied:
                get_current_user(credentials, db, org_b)
            assert denied.value.status_code == 403

        with Session(engine) as db:
            db.add_all([IdentityMembership(id=f"ma-{suffix}", issuer=issuer, subject=subject, org_id=org_a, user_id=subject, is_active=True, is_owner=True),
                        IdentityMembership(id=f"mb-{suffix}", issuer=issuer, subject=subject, org_id=org_b, user_id=local_b, is_active=True, is_owner=False)])
            db.commit()

        with Session(engine) as db:
            db.execute(text("SET ROLE ap_app_user"))
            chooser = get_current_user(credentials, db, None)
            assert chooser.workspace_selection_required and not chooser.is_provisioned
            assert get_current_user_profile(chooser)["status"] == "WORKSPACE_SELECTION_REQUIRED"
            a = get_current_user(credentials, db, org_a)
            assert a.id == subject and a.is_owner and a.role.value == "AP_LEAD"
            b = get_current_user(credentials, db, org_b)
            assert b.id == local_b and b.auth_subject == subject and not b.is_owner and b.role.value == "AUDITOR"
            assert db.scalar(text("SELECT current_setting('app.current_org_id', true)")) == org_b
            with pytest.raises(HTTPException) as denied:
                get_current_user(credentials, db, org_c)
            assert denied.value.status_code == 403
            db.commit()
            # Session tenant state intentionally rebinds on subsequent transactions;
            # releasing the session must remove it from the pooled connection.

        with Session(engine) as db:
            db.execute(text("UPDATE identity_memberships SET is_active = false WHERE id = :id"), {"id": f"mb-{suffix}"})
            db.commit()
            assert db.scalar(select(AuditEvent.actor_id).where(AuditEvent.id == f"audit-{suffix}")) == subject
        with Session(engine) as db:
            db.execute(text("SET ROLE ap_app_user"))
            with pytest.raises(HTTPException) as denied:
                get_current_user(credentials, db, org_b)
            assert denied.value.status_code == 403
            assert get_current_user(credentials, db, None).org_id == org_a
        with Session(engine) as db:
            db.execute(text("UPDATE identity_memberships SET is_active = true WHERE id = :id"), {"id": f"mb-{suffix}"})
            db.execute(text("UPDATE users SET is_active = false WHERE id = :id"), {"id": local_b})
            db.commit()
        with Session(engine) as db:
            db.execute(text("SET ROLE ap_app_user"))
            with pytest.raises(HTTPException) as denied:
                get_current_user(credentials, db, org_b)
            assert denied.value.status_code == 403
        # A new request/session must not inherit the previous tenant context.
        with Session(engine) as db:
            db.execute(text("SET ROLE ap_app_user"))
            assert db.scalar(text("SELECT current_setting('app.current_org_id', true)")) in (None, "")
            with pytest.raises(DBAPIError):
                db.execute(text("SELECT * FROM identity_memberships"))

        pooled = create_engine(url, pool_size=1, max_overflow=0)
        try:
            with Session(pooled) as db:
                db.execute(text("SET ROLE ap_app_user"))
                assert get_current_user(credentials, db, org_a).org_id == org_a
                db.commit()
            with Session(pooled) as db:
                assert db.scalar(text("SELECT current_setting('app.current_org_id', true)")) in (None, "")
        finally:
            pooled.dispose()
    finally:
        engine.dispose()
