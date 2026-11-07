"""PostgreSQL-only checks using the owned cluster/database fixture, never .env."""
import datetime
import hashlib
import os
import uuid

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from backend.api.v1.auth import AcceptInvitationPayload, accept_invitation
from backend.core.auth import AuthenticatedUser
from backend.models.domain import Organisation, RoleAssignment, User, UserInvitation


def test_invitation_accepted_under_rls_and_cannot_be_replayed(postgres_database):
    url = postgres_database['admin_url']
    engine = create_engine(url)
    suffix = uuid.uuid4().hex[:10]
    org_id, inviter_id, subject = f"org_{suffix}", f"inviter_{suffix}", f"subject_{suffix}"
    email, token = f"{suffix}@example.test", uuid.uuid4().hex
    now = datetime.datetime.utcnow()
    try:
        with Session(engine) as db:
            db.add(Organisation(id=org_id, name="Disposable test workspace"))
            db.add(User(id=inviter_id, org_id=org_id, email=f"inviter-{email}", full_name="Inviter", is_active=True))
            db.flush()
            db.add(RoleAssignment(id=f"role_{suffix}", org_id=org_id, user_id=inviter_id, role_name="SYSTEM_ADMIN"))
            db.add(UserInvitation(id=f"invite_{suffix}", org_id=org_id, email=email, role_name="AP_ASSOCIATE", token_hash=hashlib.sha256(token.encode()).hexdigest(), invited_by_user_id=inviter_id, status="PENDING", expires_at=now + datetime.timedelta(hours=1)))
            db.commit()

        identity = AuthenticatedUser(id=subject, email=email, name="Invitee")
        with Session(engine) as db:
            db.execute(text("SET ROLE ap_app_user"))
            wrong_identity = AuthenticatedUser(id="wrong", email="wrong@example.test", name="Wrong account")
            with pytest.raises(HTTPException):
                accept_invitation(AcceptInvitationPayload(token=token), wrong_identity, db)
            result = accept_invitation(AcceptInvitationPayload(token=token), identity, db)
            assert result["org_id"] == org_id
            with pytest.raises(HTTPException):
                accept_invitation(AcceptInvitationPayload(token=token), identity, db)
            db.execute(text("RESET ROLE"))
            db.commit()

        with Session(engine) as db:
            member = db.scalar(select(User).where(User.id == subject, User.org_id == org_id))
            assert member is not None and member.is_active
    finally:
        engine.dispose()
