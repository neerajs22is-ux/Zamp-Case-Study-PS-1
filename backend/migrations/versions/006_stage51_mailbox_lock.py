"""006 Stage 5.1 Mailbox Processing Lease & Lock Schema Migration

Revision ID: 006_stage51_mailbox_lock
Revises: 005_stage5_gmail_pubsub
Create Date: 2026-10-31 22:50:00

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "006_stage51_mailbox_lock"
down_revision: Union[str, None] = "005_stage5_gmail_pubsub"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("gmail_accounts") as batch_op:
        batch_op.add_column(sa.Column("sync_lock_token", sa.String(64), nullable=True))
        batch_op.add_column(sa.Column("sync_lock_expires_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("gmail_accounts") as batch_op:
        batch_op.drop_column("sync_lock_expires_at")
        batch_op.drop_column("sync_lock_token")
