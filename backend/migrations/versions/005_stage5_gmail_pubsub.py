"""005 Stage 5 Gmail PubSub Push, History Sync & OAuth Nonce Schema Migration

Revision ID: 005_stage5_gmail_pubsub
Revises: 004_stage4_gmail_ingestion
Create Date: 2026-10-31 22:35:00

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "005_stage5_gmail_pubsub"
down_revision: Union[str, None] = "004_stage4_gmail_ingestion"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add watch columns to gmail_accounts
    with op.batch_alter_table("gmail_accounts") as batch_op:
        batch_op.add_column(sa.Column("pubsub_topic", sa.String(255), nullable=True))
        batch_op.add_column(sa.Column("watch_history_id", sa.String(64), nullable=True))
        batch_op.add_column(sa.Column("watch_expiration_at", sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column("watch_last_renewed_at", sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column("watch_status", sa.String(32), server_default="DISABLED", nullable=False))

    # 2. Create oauth_state_nonces table for replay prevention
    op.create_table(
        "oauth_state_nonces",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("org_id", sa.String(64), sa.ForeignKey("organisations.id"), nullable=False, index=True),
        sa.Column("user_id", sa.String(64), nullable=False),
        sa.Column("session_binding", sa.String(64), nullable=True),
        sa.Column("is_consumed", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("consumed_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("id", "org_id", name="uq_oauth_nonces_id_org"),
    )

    # 3. Create gmail_pubsub_events table for durable notification acceptance
    op.create_table(
        "gmail_pubsub_events",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("org_id", sa.String(64), sa.ForeignKey("organisations.id"), nullable=False, index=True),
        sa.Column("mailbox_address", sa.String(255), nullable=False, index=True),
        sa.Column("history_id", sa.String(64), nullable=False, index=True),
        sa.Column("pubsub_message_id", sa.String(128), unique=True, nullable=False, index=True),
        sa.Column("subscription", sa.String(255), nullable=True),
        sa.Column("payload_json", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(32), server_default="RECEIVED", nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("received_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("processed_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("id", "org_id", name="uq_pubsub_events_id_org"),
    )


def downgrade() -> None:
    op.drop_table("gmail_pubsub_events")
    op.drop_table("oauth_state_nonces")
    with op.batch_alter_table("gmail_accounts") as batch_op:
        batch_op.drop_column("watch_status")
        batch_op.drop_column("watch_last_renewed_at")
        batch_op.drop_column("watch_expiration_at")
        batch_op.drop_column("watch_history_id")
        batch_op.drop_column("pubsub_topic")
