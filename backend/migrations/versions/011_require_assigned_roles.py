"""Require an explicit role for legacy identities; preserve users and audit actors."""
from alembic import op

revision = "011_require_assigned_roles"
down_revision = "010_identity_memberships"
branch_labels = None
depends_on = None


def upgrade():
    if op.get_bind().dialect.name != "postgresql":
        return
    # Keep the pre-tenant lookup and existing function ACL/owner. A missing role
    # now returns NULL and is rejected by the application, never defaulted to a
    # write-capable AP role. No identity, membership or financial row is changed.
    op.execute("""
        CREATE OR REPLACE FUNCTION resolve_workspace_memberships(
            p_issuer text, p_subject text, p_legacy_allowed boolean)
        RETURNS TABLE (user_id varchar(64), org_id varchar(64), org_name varchar(255),
                       role_name varchar(64), is_owner boolean)
        LANGUAGE sql SECURITY DEFINER SET search_path = public, pg_temp STABLE AS $$
            SELECT u.id, u.org_id, o.name, r.role_name, m.is_owner
            FROM identity_memberships m
            JOIN users u ON u.id = m.user_id AND u.org_id = m.org_id
            JOIN organisations o ON o.id = u.org_id
            LEFT JOIN role_assignments r ON r.user_id = u.id AND r.org_id = u.org_id
            WHERE m.issuer = p_issuer AND m.subject = p_subject AND m.is_active AND u.is_active
            UNION ALL
            SELECT u.id, u.org_id, o.name, r.role_name, false
            FROM users u JOIN organisations o ON o.id = u.org_id
            LEFT JOIN role_assignments r ON r.user_id = u.id AND r.org_id = u.org_id
            WHERE p_legacy_allowed AND u.id = p_subject AND u.is_active
              AND NOT EXISTS (SELECT 1 FROM identity_memberships m WHERE m.user_id = u.id AND m.org_id = u.org_id)
        $$
    """)


def downgrade():
    raise RuntimeError("Restoring implicit role grants requires a reviewed authorization rollback.")
