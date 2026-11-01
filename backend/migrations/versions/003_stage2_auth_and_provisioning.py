"""003 Stage 2 Auth, Invitations, Access Requests & RLS Bootstrap

Revision ID: 003_stage2_auth_and_provisioning
Revises: 002_tenant_isolation_and_rls
Create Date: 2026-10-31 20:45:00

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "003_stage2_auth_and_provisioning"
down_revision: Union[str, None] = "002_tenant_isolation_and_rls"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"

    # 1. Create user_invitations table
    op.create_table(
        "user_invitations",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("org_id", sa.String(64), sa.ForeignKey("organisations.id"), nullable=False, index=True),
        sa.Column("email", sa.String(255), nullable=False, index=True),
        sa.Column("role_name", sa.String(64), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True, index=True),
        sa.Column("invited_by_user_id", sa.String(64), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("status", sa.String(32), server_default="PENDING", nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("accepted_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )

    # 2. Create access_requests table
    op.create_table(
        "access_requests",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("org_id", sa.String(64), sa.ForeignKey("organisations.id"), nullable=False, index=True),
        sa.Column("user_id", sa.String(64), nullable=False, index=True),
        sa.Column("email", sa.String(255), nullable=False, index=True),
        sa.Column("full_name", sa.String(255), nullable=False),
        sa.Column("requested_role", sa.String(64), server_default="AP_ASSOCIATE", nullable=False),
        sa.Column("status", sa.String(32), server_default="PENDING", nullable=False),
        sa.Column("reviewed_by_user_id", sa.String(64), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
        sa.Column("review_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )

    if is_postgres:
        # Composite unique and foreign key constraints
        op.create_unique_constraint("uq_user_invitations_id_org", "user_invitations", ["id", "org_id"])
        op.create_foreign_key(
            "fk_invitations_user_org",
            "user_invitations",
            "users",
            ["invited_by_user_id", "org_id"],
            ["id", "org_id"],
        )

        op.create_unique_constraint("uq_access_requests_id_org", "access_requests", ["id", "org_id"])
        op.create_foreign_key(
            "fk_access_requests_reviewer_org",
            "access_requests",
            "users",
            ["reviewed_by_user_id", "org_id"],
            ["id", "org_id"],
        )

        # Grants to ap_app_user
        op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON user_invitations, access_requests TO ap_app_user;")

        # Enable and force Row Level Security
        for tbl in ["user_invitations", "access_requests"]:
            op.execute(f"ALTER TABLE {tbl} ENABLE ROW LEVEL SECURITY;")
            op.execute(f"ALTER TABLE {tbl} FORCE ROW LEVEL SECURITY;")
            op.execute(f"""
                DROP POLICY IF EXISTS tenant_isolation_policy ON {tbl};
                CREATE POLICY tenant_isolation_policy ON {tbl}
                AS PERMISSIVE
                FOR ALL
                TO ap_app_user
                USING (org_id::text = NULLIF(TRIM(current_setting('app.current_org_id', true)), ''))
                WITH CHECK (org_id::text = NULLIF(TRIM(current_setting('app.current_org_id', true)), ''));
            """)

        # SECURITY DEFINER function to solve the RLS bootstrap chicken-and-egg problem:
        # Resolves active user membership without requiring app.current_org_id to be set beforehand.
        op.execute("""
            CREATE OR REPLACE FUNCTION resolve_user_memberships(p_auth_user_id text, p_email text)
            RETURNS TABLE (
                user_id varchar(64),
                org_id varchar(64),
                org_name varchar(255),
                role_name varchar(64),
                is_active boolean
            )
            LANGUAGE sql
            SECURITY DEFINER
            SET search_path = public, pg_temp
            STABLE
            AS $$
                SELECT 
                    u.id AS user_id,
                    u.org_id AS org_id,
                    o.name AS org_name,
                    COALESCE(r.role_name, 'AP_ASSOCIATE') AS role_name,
                    u.is_active AS is_active
                FROM users u
                JOIN organisations o ON o.id = u.org_id
                LEFT JOIN role_assignments r ON r.user_id = u.id AND r.org_id = u.org_id
                WHERE (u.id = p_auth_user_id OR LOWER(u.email) = LOWER(p_email))
                  AND u.is_active = TRUE;
            $$;
            REVOKE ALL ON FUNCTION resolve_user_memberships(text, text) FROM PUBLIC;
            GRANT EXECUTE ON FUNCTION resolve_user_memberships(text, text) TO ap_app_user;
        """)

        # SECURITY DEFINER function to look up pending invitations across tenants securely
        op.execute("""
            CREATE OR REPLACE FUNCTION find_pending_invitation(p_token_hash text, p_email text)
            RETURNS TABLE (
                invitation_id varchar(64),
                org_id varchar(64),
                email varchar(255),
                role_name varchar(64),
                expires_at timestamp
            )
            LANGUAGE sql
            SECURITY DEFINER
            SET search_path = public, pg_temp
            STABLE
            AS $$
                SELECT 
                    i.id AS invitation_id,
                    i.org_id AS org_id,
                    i.email AS email,
                    i.role_name AS role_name,
                    i.expires_at AS expires_at
                FROM user_invitations i
                WHERE i.token_hash = p_token_hash
                  AND LOWER(i.email) = LOWER(p_email)
                  AND i.status = 'PENDING'
                  AND i.expires_at > NOW();
            $$;
            REVOKE ALL ON FUNCTION find_pending_invitation(text, text) FROM PUBLIC;
            GRANT EXECUTE ON FUNCTION find_pending_invitation(text, text) TO ap_app_user;
        """)


def downgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"

    if is_postgres:
        op.execute("DROP FUNCTION IF EXISTS find_pending_invitation(text, text);")
        op.execute("DROP FUNCTION IF EXISTS resolve_user_memberships(text, text);")
        op.drop_constraint("fk_access_requests_reviewer_org", "access_requests", type_="foreignkey")
        op.drop_constraint("uq_access_requests_id_org", "access_requests", type_="unique")
        op.drop_constraint("fk_invitations_user_org", "user_invitations", type_="foreignkey")
        op.drop_constraint("uq_user_invitations_id_org", "user_invitations", type_="unique")

    op.drop_table("access_requests")
    op.drop_table("user_invitations")
