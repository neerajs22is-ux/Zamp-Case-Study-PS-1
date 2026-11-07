"""Compare UTC-naive invitation expiry independently of PostgreSQL timezone."""
from alembic import op

revision = '012_invitation_utc_expiry'
down_revision = '011_require_assigned_roles'
branch_labels = None
depends_on = None


def upgrade():
    if op.get_bind().dialect.name != 'postgresql':
        return
    # expires_at follows the existing UTC-naive timestamp convention. Comparing
    # it with timestamptz NOW() implicitly used the server/session timezone.
    # CREATE OR REPLACE retains the established privileged owner and ACL.
    op.execute("""
        CREATE OR REPLACE FUNCTION find_pending_invitation(p_token_hash text, p_email text)
        RETURNS TABLE (invitation_id varchar(64), org_id varchar(64), email varchar(255),
                       role_name varchar(64), expires_at timestamp)
        LANGUAGE sql SECURITY DEFINER SET search_path = public, pg_temp STABLE AS $$
            SELECT i.id, i.org_id, i.email, i.role_name, i.expires_at
            FROM user_invitations i
            WHERE i.token_hash = p_token_hash AND LOWER(i.email) = LOWER(p_email)
              AND i.status = 'PENDING'
              AND i.expires_at > (NOW() AT TIME ZONE 'UTC')
        $$
    """)


def downgrade():
    raise RuntimeError('Restoring timezone-dependent invitation expiry requires a reviewed rollback.')
