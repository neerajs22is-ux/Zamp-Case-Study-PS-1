"""007 Stage 5.2 PubSub Event Retry Count and Last Attempted At Schema Migration

Revision ID: 007_stage52_pubsub_recovery
Revises: 006_stage51_mailbox_lock
Create Date: 2026-10-31 23:25:00

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "007_stage52_pubsub_recovery"
down_revision: Union[str, None] = "006_stage51_mailbox_lock"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("gmail_pubsub_events") as batch_op:
        batch_op.add_column(sa.Column("retry_count", sa.Integer(), server_default="0", nullable=False))
        batch_op.add_column(sa.Column("last_attempted_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("gmail_pubsub_events") as batch_op:
        batch_op.drop_column("last_attempted_at")
        batch_op.drop_column("retry_count")
