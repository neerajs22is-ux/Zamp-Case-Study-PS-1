"""Bind verified identity subjects to tenant user records without rewriting history."""
from alembic import op
import sqlalchemy as sa

revision = "010_identity_memberships"
down_revision = "009_phase_a_core"
branch_labels = None
depends_on = None


def upgrade():
    # The original global email index prevents one identity having a tenant user
    # in more than one workspace. Keep the existing (org_id, email) constraint.
    op.drop_index("ix_users_email", table_name="users")
    op.create_index("ix_users_email", "users", ["email"], unique=False)
    op.create_table(
        "identity_memberships",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("issuer", sa.String(512), nullable=False),
        sa.Column("subject", sa.String(255), nullable=False),
        sa.Column("org_id", sa.String(64), sa.ForeignKey("organisations.id"), nullable=False),
        sa.Column("user_id", sa.String(64), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("is_owner", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["user_id", "org_id"], ["users.id", "users.org_id"], name="fk_identity_membership_user_org"),
        sa.UniqueConstraint("issuer", "subject", "org_id", name="uq_identity_membership_identity_org"),
        sa.UniqueConstraint("org_id", "user_id", name="uq_identity_membership_user_org"),
    )
    op.create_index("ix_identity_memberships_org_id", "identity_memberships", ["org_id"])
    if op.get_bind().dialect.name == "postgresql":
        # FORCE RLS also applies to table owners. The definer must really be able
        # to perform the pre-tenant lookup, or existing users would be locked out.
        op.execute("""
            DO $$ BEGIN
              IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = current_user AND (rolsuper OR rolbypassrls)) THEN
                RAISE EXCEPTION 'identity membership function owner requires BYPASSRLS; use the approved migration role';
              END IF;
            END $$
        """)
        op.execute("ALTER TABLE identity_memberships ENABLE ROW LEVEL SECURITY")
        op.execute("ALTER TABLE identity_memberships FORCE ROW LEVEL SECURITY")
        op.execute("REVOKE ALL ON identity_memberships FROM PUBLIC, ap_app_user")
        op.execute("REVOKE ALL ON FUNCTION resolve_user_memberships(text, text) FROM PUBLIC, ap_app_user")
        op.execute("""
            CREATE FUNCTION resolve_workspace_memberships(p_issuer text, p_subject text, p_legacy_allowed boolean)
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
                SELECT u.id, u.org_id, o.name, COALESCE(r.role_name, 'AP_ASSOCIATE')::varchar(64), false
                FROM users u JOIN organisations o ON o.id = u.org_id
                LEFT JOIN role_assignments r ON r.user_id = u.id AND r.org_id = u.org_id
                WHERE p_legacy_allowed AND u.id = p_subject AND u.is_active
                  AND NOT EXISTS (SELECT 1 FROM identity_memberships m WHERE m.user_id = u.id AND m.org_id = u.org_id)
            $$
        """)
        op.execute("REVOKE ALL ON FUNCTION resolve_workspace_memberships(text, text, boolean) FROM PUBLIC")
        op.execute("GRANT EXECUTE ON FUNCTION resolve_workspace_memberships(text, text, boolean) TO ap_app_user")


def downgrade():
    raise RuntimeError("Identity bindings must be exported and reviewed before downgrading this migration.")
