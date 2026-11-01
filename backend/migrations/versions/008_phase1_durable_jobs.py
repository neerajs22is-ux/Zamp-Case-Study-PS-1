"""008 Phase 1 Durable Jobs & Workflow

Revision ID: 008_phase1_durable_jobs
Revises: 007_stage52_pubsub_recovery
Create Date: 2026-11-01 23:55:00

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "008_phase1_durable_jobs"
down_revision: Union[str, None] = "007_stage52_pubsub_recovery"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add workflow_substatus to invoices table
    with op.batch_alter_table("invoices") as batch_op:
        batch_op.add_column(sa.Column("workflow_substatus", sa.String(length=32), nullable=True))

    # 2. Add lease, lock_token and document_id to ingestion_jobs table
    with op.batch_alter_table("ingestion_jobs") as batch_op:
        batch_op.add_column(sa.Column("document_id", sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column("lock_token", sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column("lease_expires_at", sa.DateTime(), nullable=True))
        batch_op.create_index("ix_ingestion_jobs_status_lease", ["status", "lease_expires_at"], unique=False)

    # 3. Add resolution_notes and resolved_at to exceptions table
    with op.batch_alter_table("exceptions") as batch_op:
        batch_op.add_column(sa.Column("resolution_notes", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("resolved_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("exceptions") as batch_op:
        batch_op.drop_column("resolved_at")
        batch_op.drop_column("resolution_notes")

    with op.batch_alter_table("ingestion_jobs") as batch_op:
        batch_op.drop_index("ix_ingestion_jobs_status_lease")
        batch_op.drop_column("lease_expires_at")
        batch_op.drop_column("lock_token")
        batch_op.drop_column("document_id")

    with op.batch_alter_table("invoices") as batch_op:
        batch_op.drop_column("workflow_substatus")
