"""009 Phase A Core Improvements

Revision ID: 009_phase_a_core
Revises: 008_phase1_durable_jobs
Create Date: 2026-11-03 21:40:00

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "009_phase_a_core"
down_revision: Union[str, None] = "008_phase1_durable_jobs"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add line correction tracking columns to invoice_lines
    with op.batch_alter_table("invoice_lines") as batch_op:
        batch_op.add_column(
            sa.Column("is_corrected", sa.Boolean(), nullable=False, server_default=sa.text("false"))
        )
        batch_op.add_column(
            sa.Column("previous_unit_rate", sa.Numeric(12, 4), nullable=True)
        )
        batch_op.add_column(
            sa.Column("line_version", sa.Integer(), nullable=False, server_default=sa.text("1"))
        )

    # 2. Add composite index on invoices (org_id, invoice_date) for temporal period queries
    with op.batch_alter_table("invoices") as batch_op:
        batch_op.create_index(
            "idx_invoices_org_invoice_date",
            ["org_id", "invoice_date"],
            unique=False
        )


def downgrade() -> None:
    with op.batch_alter_table("invoices") as batch_op:
        batch_op.drop_index("idx_invoices_org_invoice_date")

    with op.batch_alter_table("invoice_lines") as batch_op:
        batch_op.drop_column("line_version")
        batch_op.drop_column("previous_unit_rate")
        batch_op.drop_column("is_corrected")
