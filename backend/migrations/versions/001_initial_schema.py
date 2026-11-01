"""001 Initial Schema & Append-Only Audit Trigger

Revision ID: 001_initial_schema
Revises: 
Create Date: 2026-10-31 15:40:00

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"

    # 1. Organisations & Legal Entities
    op.create_table(
        "organisations",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )

    op.create_table(
        "legal_entities",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("org_id", sa.String(64), sa.ForeignKey("organisations.id"), nullable=False, index=True),
        sa.Column("company_code", sa.String(32), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("gstin", sa.String(15), nullable=False),
        sa.Column("state_code", sa.String(2), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )

    # 2. Users & Roles
    op.create_table(
        "users",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("org_id", sa.String(64), sa.ForeignKey("organisations.id"), nullable=False, index=True),
        sa.Column("email", sa.String(255), unique=True, nullable=False, index=True),
        sa.Column("full_name", sa.String(255), nullable=False),
        sa.Column("is_active", sa.Boolean(), default=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )

    op.create_table(
        "role_assignments",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("user_id", sa.String(64), sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("role_name", sa.String(64), nullable=False),
        sa.Column("granted_at", sa.DateTime(), nullable=False),
    )

    # 3. Integrations
    op.create_table(
        "integration_connections",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("org_id", sa.String(64), sa.ForeignKey("organisations.id"), nullable=False, index=True),
        sa.Column("pillar", sa.String(32), nullable=False),
        sa.Column("provider", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("last_health_check", sa.DateTime(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("configuration_metadata", sa.JSON(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )

    op.create_table(
        "gmail_accounts",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("mailbox_address", sa.String(255), unique=True, nullable=False),
        sa.Column("oauth_status", sa.String(32), nullable=False),
        sa.Column("last_history_id", sa.String(64), nullable=True),
        sa.Column("last_synced_at", sa.DateTime(), nullable=True),
    )

    op.create_table(
        "connection_health_events",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("connection_id", sa.String(64), sa.ForeignKey("integration_connections.id"), nullable=False, index=True),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("timestamp", sa.DateTime(), nullable=False),
    )

    # 4. Vendors & GSTINs
    op.create_table(
        "vendors",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("org_id", sa.String(64), sa.ForeignKey("organisations.id"), nullable=False, index=True),
        sa.Column("erp_vendor_code", sa.String(64), unique=True, nullable=False),
        sa.Column("legal_name", sa.String(255), nullable=False),
        sa.Column("trade_name", sa.String(255), nullable=True),
        sa.Column("pan", sa.String(10), nullable=True, index=True),
        sa.Column("msme_registered", sa.Boolean(), default=False, nullable=False),
        sa.Column("msme_category", sa.String(32), nullable=True),
        sa.Column("udyam_number", sa.String(64), nullable=True),
        sa.Column("bank_account_verified", sa.Boolean(), default=False, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )

    op.create_table(
        "vendor_gstins",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("vendor_id", sa.String(64), sa.ForeignKey("vendors.id"), nullable=False, index=True),
        sa.Column("gstin", sa.String(15), nullable=False, index=True),
        sa.Column("state_code", sa.String(2), nullable=False),
        sa.Column("status", sa.String(32), default="ACTIVE", nullable=False),
    )

    # 5. ERP Snapshots
    op.create_table(
        "erp_work_orders",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("po_number", sa.String(64), unique=True, nullable=False, index=True),
        sa.Column("vendor_code", sa.String(64), nullable=False),
        sa.Column("total_authorized_amount", sa.Numeric(15, 2), nullable=False),
        sa.Column("remaining_balance", sa.Numeric(15, 2), nullable=False),
        sa.Column("currency", sa.String(3), default="INR", nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("retrieved_at", sa.DateTime(), nullable=False),
    )

    op.create_table(
        "erp_po_lines",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("po_id", sa.String(64), sa.ForeignKey("erp_work_orders.id"), nullable=False, index=True),
        sa.Column("line_number", sa.Integer(), nullable=False),
        sa.Column("item_code", sa.String(64), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("authorized_quantity", sa.Numeric(12, 4), nullable=False),
        sa.Column("contracted_unit_rate", sa.Numeric(12, 4), nullable=False),
        sa.Column("authorized_line_total", sa.Numeric(15, 2), nullable=False),
    )

    op.create_table(
        "erp_grns",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("grn_number", sa.String(64), unique=True, nullable=False, index=True),
        sa.Column("po_number", sa.String(64), nullable=False, index=True),
        sa.Column("received_date", sa.DateTime(), nullable=False),
        sa.Column("retrieved_at", sa.DateTime(), nullable=False),
    )

    op.create_table(
        "erp_grn_lines",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("grn_id", sa.String(64), sa.ForeignKey("erp_grns.id"), nullable=False, index=True),
        sa.Column("po_line_number", sa.Integer(), nullable=False),
        sa.Column("accepted_quantity", sa.Numeric(12, 4), nullable=False),
        sa.Column("rejected_quantity", sa.Numeric(12, 4), default=0, nullable=False),
    )

    op.create_table(
        "erp_qc_records",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("qc_certificate_number", sa.String(64), unique=True, nullable=False, index=True),
        sa.Column("grn_number", sa.String(64), nullable=False, index=True),
        sa.Column("overall_status", sa.String(32), nullable=False),
        sa.Column("retrieved_at", sa.DateTime(), nullable=False),
    )

    # 6. Invoices, Documents & Lines
    op.create_table(
        "invoices",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("org_id", sa.String(64), sa.ForeignKey("organisations.id"), nullable=False, index=True),
        sa.Column("legal_entity_id", sa.String(64), sa.ForeignKey("legal_entities.id"), nullable=True, index=True),
        sa.Column("source_channel", sa.String(32), nullable=False),
        sa.Column("invoice_number", sa.String(128), nullable=True, index=True),
        sa.Column("invoice_date", sa.DateTime(), nullable=True),
        sa.Column("due_date", sa.DateTime(), nullable=True),
        sa.Column("msme_statutory_deadline", sa.DateTime(), nullable=True),
        sa.Column("msme_deadline_status", sa.String(64), nullable=True),
        sa.Column("vendor_name", sa.String(255), nullable=True),
        sa.Column("vendor_gstin", sa.String(15), nullable=True),
        sa.Column("po_reference", sa.String(64), nullable=True, index=True),
        sa.Column("currency", sa.String(3), default="INR", nullable=False),
        sa.Column("subtotal_amount", sa.Numeric(15, 2), nullable=True),
        sa.Column("tax_amount", sa.Numeric(15, 2), nullable=True),
        sa.Column("total_amount", sa.Numeric(15, 2), nullable=True),
        sa.Column("net_payable_amount", sa.Numeric(15, 2), nullable=True),
        sa.Column("stage", sa.String(32), default="RECEIVED", nullable=False),
        sa.Column("decision", sa.String(32), default="NEEDS_REVIEW", nullable=False),
        sa.Column("decision_reason", sa.Text(), nullable=True),
        sa.Column("owner_user_id", sa.String(64), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )

    op.create_table(
        "invoice_lines",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("invoice_id", sa.String(64), sa.ForeignKey("invoices.id"), nullable=False, index=True),
        sa.Column("line_number", sa.Integer(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("billed_quantity", sa.Numeric(12, 4), nullable=False),
        sa.Column("billed_unit_rate", sa.Numeric(12, 4), nullable=False),
        sa.Column("billed_line_total", sa.Numeric(15, 2), nullable=False),
    )

    op.create_table(
        "documents",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("invoice_id", sa.String(64), sa.ForeignKey("invoices.id"), nullable=True, index=True),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("mime_type", sa.String(64), nullable=False),
        sa.Column("file_size_bytes", sa.Integer(), nullable=False),
        sa.Column("sha256_hash", sa.String(64), nullable=False, index=True),
        sa.Column("storage_provider", sa.String(32), nullable=False),
        sa.Column("storage_key", sa.String(512), nullable=False),
        sa.Column("is_original", sa.Boolean(), default=True, nullable=False),
        sa.Column("uploaded_at", sa.DateTime(), nullable=False),
    )

    # 7. Extraction Runs & Fields
    op.create_table(
        "extraction_runs",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("document_id", sa.String(64), sa.ForeignKey("documents.id"), nullable=False, index=True),
        sa.Column("parser_version", sa.String(32), nullable=False),
        sa.Column("overall_confidence", sa.Numeric(5, 4), nullable=True),
        sa.Column("extracted_at", sa.DateTime(), nullable=False),
    )

    op.create_table(
        "extracted_fields",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("extraction_run_id", sa.String(64), sa.ForeignKey("extraction_runs.id"), nullable=False, index=True),
        sa.Column("field_name", sa.String(64), nullable=False),
        sa.Column("extracted_value", sa.Text(), nullable=True),
        sa.Column("confidence_score", sa.Numeric(5, 4), nullable=True),
        sa.Column("source_page", sa.Integer(), nullable=True),
        sa.Column("bounding_box", sa.JSON(), nullable=True),
    )

    # 8. Match Runs & Gates
    op.create_table(
        "match_runs",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("invoice_id", sa.String(64), sa.ForeignKey("invoices.id"), nullable=False, index=True),
        sa.Column("policy_version", sa.String(32), default="v1.0-default", nullable=False),
        sa.Column("overall_result", sa.String(32), nullable=False),
        sa.Column("evaluated_at", sa.DateTime(), nullable=False),
    )

    op.create_table(
        "match_gate_checks",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("match_run_id", sa.String(64), sa.ForeignKey("match_runs.id"), nullable=False, index=True),
        sa.Column("gate_number", sa.Integer(), nullable=False),
        sa.Column("gate_name", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("evidence_source_id", sa.String(128), nullable=True),
        sa.Column("evidence_notes", sa.Text(), nullable=True),
        sa.Column("checked_at", sa.DateTime(), nullable=False),
    )

    # 9. Ingestion Jobs, Exceptions, Quarantine & Approvals
    op.create_table(
        "ingestion_jobs",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("idempotency_key", sa.String(128), unique=True, nullable=False, index=True),
        sa.Column("source_channel", sa.String(32), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("retry_count", sa.Integer(), default=0, nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
    )

    op.create_table(
        "exceptions",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("invoice_id", sa.String(64), sa.ForeignKey("invoices.id"), nullable=False, index=True),
        sa.Column("blocking_gate_number", sa.Integer(), nullable=False),
        sa.Column("blocking_gate_name", sa.String(64), nullable=False),
        sa.Column("exposure_amount_inr", sa.Numeric(15, 2), nullable=False),
        sa.Column("msme_statutory_deadline", sa.DateTime(), nullable=True),
        sa.Column("assigned_user_id", sa.String(64), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("status", sa.String(32), default="OPEN", nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )

    op.create_table(
        "quarantined_documents",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("document_id", sa.String(64), sa.ForeignKey("documents.id"), nullable=False, index=True),
        sa.Column("quarantine_reason", sa.String(64), nullable=False),
        sa.Column("details", sa.Text(), nullable=True),
        sa.Column("status", sa.String(32), default="ACTIVE", nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )

    op.create_table(
        "approval_requests",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("invoice_id", sa.String(64), sa.ForeignKey("invoices.id"), nullable=False, index=True),
        sa.Column("requires_dual_approval", sa.Boolean(), default=False, nullable=False),
        sa.Column("first_approver_id", sa.String(64), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("first_approved_at", sa.DateTime(), nullable=True),
        sa.Column("second_approver_id", sa.String(64), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("second_approved_at", sa.DateTime(), nullable=True),
        sa.Column("status", sa.String(32), default="PENDING", nullable=False),
    )

    # 10. Append-Only Audit Events Table
    op.create_table(
        "audit_events",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("invoice_id", sa.String(64), sa.ForeignKey("invoices.id"), nullable=True, index=True),
        sa.Column("org_id", sa.String(64), sa.ForeignKey("organisations.id"), nullable=True, index=True),
        sa.Column("legal_entity_id", sa.String(64), nullable=True),
        sa.Column("actor_id", sa.String(64), nullable=False),
        sa.Column("actor_role", sa.String(64), nullable=False),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("correlation_id", sa.String(64), nullable=True, index=True),
        sa.Column("before_state", sa.JSON(), nullable=True),
        sa.Column("after_state", sa.JSON(), nullable=True),
        sa.Column("policy_version", sa.String(32), nullable=True),
        sa.Column("source_reference", sa.String(255), nullable=True),
        sa.Column("timestamp", sa.DateTime(), nullable=False, index=True),
    )

    # 11. Database-Level Append-Only Protections
    if is_postgres:
        op.execute("""
            CREATE OR REPLACE FUNCTION prevent_audit_events_mutation()
            RETURNS TRIGGER AS $$
            BEGIN
                RAISE EXCEPTION 'audit_events is strictly append-only. UPDATE and DELETE operations are prohibited.';
            END;
            $$ LANGUAGE plpgsql;

            CREATE TRIGGER trg_audit_events_immutable
            BEFORE UPDATE OR DELETE ON audit_events
            FOR EACH ROW
            EXECUTE FUNCTION prevent_audit_events_mutation();
        """)
    else:
        # SQLite trigger support for isolated test environments
        op.execute("""
            CREATE TRIGGER IF NOT EXISTS trg_audit_events_no_update
            BEFORE UPDATE ON audit_events
            BEGIN
                SELECT RAISE(ABORT, 'audit_events is strictly append-only: UPDATE operations are prohibited.');
            END;
        """)
        op.execute("""
            CREATE TRIGGER IF NOT EXISTS trg_audit_events_no_delete
            BEFORE DELETE ON audit_events
            BEGIN
                SELECT RAISE(ABORT, 'audit_events is strictly append-only: DELETE operations are prohibited.');
            END;
        """)


def downgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"

    if is_postgres:
        op.execute("DROP TRIGGER IF EXISTS trg_audit_events_immutable ON audit_events;")
        op.execute("DROP FUNCTION IF EXISTS prevent_audit_events_mutation();")
    else:
        op.execute("DROP TRIGGER IF EXISTS trg_audit_events_no_update;")
        op.execute("DROP TRIGGER IF EXISTS trg_audit_events_no_delete;")

    op.drop_table("audit_events")
    op.drop_table("approval_requests")
    op.drop_table("quarantined_documents")
    op.drop_table("exceptions")
    op.drop_table("ingestion_jobs")
    op.drop_table("match_gate_checks")
    op.drop_table("match_runs")
    op.drop_table("extracted_fields")
    op.drop_table("extraction_runs")
    op.drop_table("documents")
    op.drop_table("invoice_lines")
    op.drop_table("invoices")
    op.drop_table("erp_qc_records")
    op.drop_table("erp_grn_lines")
    op.drop_table("erp_grns")
    op.drop_table("erp_po_lines")
    op.drop_table("erp_work_orders")
    op.drop_table("vendor_gstins")
    op.drop_table("vendors")
    op.drop_table("connection_health_events")
    op.drop_table("gmail_accounts")
    op.drop_table("integration_connections")
    op.drop_table("role_assignments")
    op.drop_table("users")
    op.drop_table("legal_entities")
    op.drop_table("organisations")
