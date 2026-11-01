"""004 Stage 4 Gmail OAuth and Ingestion Schema Migration

Revision ID: 004_stage4_gmail_ingestion
Revises: 003_stage2_auth_and_provisioning
Create Date: 2026-10-31 22:15:00

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "004_stage4_gmail_ingestion"
down_revision: Union[str, None] = "003_stage2_auth_and_provisioning"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add encrypted_refresh_token, created_at, updated_at to gmail_accounts
    with op.batch_alter_table("gmail_accounts") as batch_op:
        batch_op.add_column(sa.Column("encrypted_refresh_token", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False))
        batch_op.add_column(sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False))


def downgrade() -> None:
    with op.batch_alter_table("gmail_accounts") as batch_op:
        batch_op.drop_column("updated_at")
        batch_op.drop_column("created_at")
        batch_op.drop_column("encrypted_refresh_token")
