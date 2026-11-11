"""Scope Gmail mailbox uniqueness to the tenant.

Revision ID: 014_gmail_mailbox_scoping
Revises: 013_revoke_access_tokens
Create Date: 2026-11-11

Migration 001 declared gmail_accounts.mailbox_address UNIQUE globally (an artefact of
the pre-multi-tenant schema). Migration 002 introduced org-scoped uniqueness
(uq_gmail_accounts_org_mailbox) but never removed that global constraint, so PostgreSQL
kept rejecting a mailbox address that was already bound to another organisation with
`duplicate key value violates unique constraint "gmail_accounts_mailbox_address_key"`.
The ORM model declares only the composite constraints, so SQLite/model-derived test
schemas never reproduced the failure.

Tenant isolation is unaffected: row-level security and both composite unique
constraints remain in force.
"""
from alembic import op

revision = "014_gmail_mailbox_scoping"
down_revision = "013_revoke_access_tokens"
branch_labels = None
depends_on = None

LEGACY_CONSTRAINT = "gmail_accounts_mailbox_address_key"


def upgrade():
    if op.get_bind().dialect.name != "postgresql":
        return
    op.execute(f"ALTER TABLE gmail_accounts DROP CONSTRAINT IF EXISTS {LEGACY_CONSTRAINT}")


def downgrade():
    # Re-adding a global unique constraint would fail as soon as two tenants have
    # connected the same mailbox address, and would silently break re-authorization.
    raise RuntimeError(
        "Reinstating the global gmail_accounts.mailbox_address unique constraint is unsafe; "
        "uniqueness is intentionally scoped per organisation."
    )
