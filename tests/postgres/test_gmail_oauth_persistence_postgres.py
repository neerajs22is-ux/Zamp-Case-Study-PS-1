"""Gmail OAuth persistence on a migrated, non-bypass database with FORCE RLS."""

from __future__ import annotations

import pytest
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from backend.core.database import set_tenant_context
from backend.core.gmail import encrypt_refresh_token
from backend.models.domain import AuditEvent, GmailAccount

MAILBOX = "ap-inbox@terrace.test"
ORG_A = "org_gmail_a"
ORG_B = "org_gmail_b"


@pytest.fixture
def gmail_pg(postgres_database):
    pg = postgres_database
    with Session(pg["admin"]) as db:
        db.execute(text(
            "INSERT INTO organisations (id, name, created_at) "
            f"VALUES ('{ORG_A}','Gmail A', now()), ('{ORG_B}','Gmail B', now())"
        ))
        db.commit()
    return pg


def seed_account(pg, acc_id, org_id, mailbox=MAILBOX, status="EXPIRED"):
    with Session(pg["admin"]) as db:
        db.execute(text(
            "INSERT INTO gmail_accounts (id, org_id, mailbox_address, oauth_status, watch_status, "
            "created_at, updated_at) VALUES (:id, :org, :box, :st, 'DISABLED', now(), now())"
        ), {"id": acc_id, "org": org_id, "box": mailbox, "st": status})
        db.commit()


def test_legacy_global_mailbox_uniqueness_is_removed(gmail_pg):
    """Migration 014 drops the pre-multi-tenant UNIQUE(mailbox_address) that PostgreSQL
    enforced while the ORM model declared only org-scoped uniqueness."""
    with Session(gmail_pg["admin"]) as db:
        names = {row[0] for row in db.execute(text(
            "SELECT conname FROM pg_constraint WHERE conrelid = 'gmail_accounts'::regclass"
        )).all()}
    assert "gmail_accounts_mailbox_address_key" not in names
    assert "uq_gmail_accounts_org_mailbox" in names
    assert "uq_gmail_accounts_id_org" in names


def test_two_tenants_may_bind_the_same_mailbox_address(gmail_pg):
    seed_account(gmail_pg, "gacc_a", ORG_A)
    seed_account(gmail_pg, "gacc_b", ORG_B)
    with Session(gmail_pg["admin"]) as db:
        count = db.execute(text(
            "SELECT count(*) FROM gmail_accounts WHERE mailbox_address = :box"
        ), {"box": MAILBOX}).scalar()
    assert count == 2


def test_callback_persistence_succeeds_under_forced_rls(gmail_pg):
    """Mirrors the OAuth callback writes as ap_app_user: tenant context derived from the
    verified state, encrypted refresh token, mailbox row and append-only audit event."""
    seed_account(gmail_pg, "gacc_a", ORG_A)

    with Session(gmail_pg["app"]) as db:
        set_tenant_context(db, ORG_A)
        account = db.execute(
            select(GmailAccount)
            .where(GmailAccount.org_id == ORG_A)
            .order_by(GmailAccount.created_at.asc())
            .limit(1)
        ).scalars().first()
        assert account is not None
        account.mailbox_address = MAILBOX
        account.oauth_status = "AUTHORIZED"
        account.encrypted_refresh_token = encrypt_refresh_token("plaintext-refresh-token")
        db.add(AuditEvent(
            id="evt_gmail_conn", org_id=ORG_A, actor_id="usr_admin",
            actor_role="ADMINISTRATOR", action="GMAIL_MAILBOX_CONNECTED",
            reason="Authorized Gmail mailbox with gmail.readonly scope.",
            source_reference=MAILBOX,
        ))
        db.commit()

    with Session(gmail_pg["app"]) as db:
        set_tenant_context(db, ORG_A)
        stored = db.execute(select(GmailAccount).where(GmailAccount.id == "gacc_a")).scalar_one()
        assert stored.oauth_status == "AUTHORIZED"
        assert stored.mailbox_address == MAILBOX
        assert stored.encrypted_refresh_token
        assert "plaintext-refresh-token" not in stored.encrypted_refresh_token
        assert db.execute(
            select(AuditEvent).where(AuditEvent.id == "evt_gmail_conn")
        ).scalar_one()

    # Tenant isolation is preserved: the other workspace cannot see this mailbox.
    with Session(gmail_pg["app"]) as db:
        set_tenant_context(db, ORG_B)
        assert db.execute(
            select(GmailAccount).where(GmailAccount.id == "gacc_a")
        ).scalar_one_or_none() is None


def test_failed_persistence_rolls_back_without_partial_writes(gmail_pg):
    seed_account(gmail_pg, "gacc_b", ORG_B, status="AUTHORIZED")

    with Session(gmail_pg["app"]) as db:
        set_tenant_context(db, ORG_B)
        account = db.execute(select(GmailAccount).where(GmailAccount.id == "gacc_b")).scalar_one()
        account.oauth_status = "EXPIRED"
        db.add(AuditEvent(
            id="evt_gmail_fail", org_id=ORG_B, actor_id="usr_admin",
            actor_role="ADMINISTRATOR", action="GMAIL_MAILBOX_CONNECTED",
            reason="Authorization attempt that must not persist.", source_reference=MAILBOX,
        ))
        db.rollback()

    with Session(gmail_pg["app"]) as db:
        set_tenant_context(db, ORG_B)
        unchanged = db.execute(select(GmailAccount).where(GmailAccount.id == "gacc_b")).scalar_one()
        assert unchanged.oauth_status == "AUTHORIZED"
        assert db.execute(
            select(AuditEvent).where(AuditEvent.id == "evt_gmail_fail")
        ).scalar_one_or_none() is None
