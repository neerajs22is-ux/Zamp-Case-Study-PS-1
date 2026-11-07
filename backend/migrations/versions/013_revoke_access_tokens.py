"""Durable denylist for application access tokens, without storing tokens."""
from alembic import op
import sqlalchemy as sa

revision = "013_revoke_access_tokens"
down_revision = "012_invitation_utc_expiry"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("revoked_access_tokens",
        sa.Column("token_hash", sa.String(64), primary_key=True),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("revoked_at", sa.DateTime(), nullable=False))
    op.create_index("ix_revoked_access_tokens_expires_at", "revoked_access_tokens", ["expires_at"])
    op.create_table("model_quota_buckets",
        sa.Column("org_id", sa.String(64), sa.ForeignKey("organisations.id"), primary_key=True),
        sa.Column("period", sa.String(20), primary_key=True),
        sa.Column("bucket", sa.String(20), primary_key=True),
        sa.Column("used", sa.Integer(), nullable=False))
    if op.get_bind().dialect.name == "postgresql":
        op.execute("REVOKE ALL ON revoked_access_tokens FROM PUBLIC, ap_app_user")
        op.execute("GRANT SELECT, INSERT ON revoked_access_tokens TO ap_app_user")
        op.execute("ALTER TABLE model_quota_buckets ENABLE ROW LEVEL SECURITY")
        op.execute("ALTER TABLE model_quota_buckets FORCE ROW LEVEL SECURITY")
        op.execute("CREATE POLICY model_quota_tenant ON model_quota_buckets USING (org_id = current_setting('app.current_org_id', true)) WITH CHECK (org_id = current_setting('app.current_org_id', true))")
        op.execute("REVOKE ALL ON model_quota_buckets FROM PUBLIC, ap_app_user")
        op.execute("GRANT SELECT, INSERT, UPDATE ON model_quota_buckets TO ap_app_user")


def downgrade():
    raise RuntimeError("Removing token revocations would reactivate unexpired tokens; use a reviewed rollback after expiry.")
