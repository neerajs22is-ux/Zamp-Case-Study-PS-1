"""002 Tenant Isolation, Composite Constraints & PostgreSQL RLS

Revision ID: 002_tenant_isolation_and_rls
Revises: 001_initial_schema
Create Date: 2026-10-31 19:45:00

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "002_tenant_isolation_and_rls"
down_revision: Union[str, None] = "001_initial_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TENANT_TABLES = [
    "organisations",
    "legal_entities",
    "users",
    "role_assignments",
    "integration_connections",
    "connection_health_events",
    "gmail_accounts",
    "vendors",
    "vendor_gstins",
    "erp_work_orders",
    "erp_po_lines",
    "erp_grns",
    "erp_grn_lines",
    "erp_qc_records",
    "invoices",
    "invoice_lines",
    "documents",
    "extraction_runs",
    "extracted_fields",
    "match_runs",
    "match_gate_checks",
    "ingestion_jobs",
    "exceptions",
    "quarantined_documents",
    "approval_requests",
    "audit_events",
]


def upgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"

    # 1. Add missing org_id columns to tables that lacked it in 001
    tables_needing_org_id = [
        "gmail_accounts",
        "erp_work_orders",
        "erp_po_lines",
        "erp_grns",
        "erp_grn_lines",
        "erp_qc_records",
        "ingestion_jobs",
        "documents",
        "invoice_lines",
        "approval_requests",
        "exceptions",
        "quarantined_documents",
        "connection_health_events",
        "role_assignments",
        "vendor_gstins",
        "extraction_runs",
        "extracted_fields",
        "match_runs",
        "match_gate_checks",
    ]

    for table_name in tables_needing_org_id:
        op.add_column(
            table_name,
            sa.Column("org_id", sa.String(64), nullable=False, server_default="org_default")
        )
        op.create_index(f"ix_{table_name}_org_id", table_name, ["org_id"])
        if is_postgres:
            op.create_foreign_key(
                f"fk_{table_name}_org_id",
                table_name,
                "organisations",
                ["org_id"],
                ["id"],
            )

    # 2. Add soft-delete columns to documents
    op.add_column("documents", sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("documents", sa.Column("deleted_at", sa.DateTime(), nullable=True))
    op.add_column("documents", sa.Column("deleted_by_user_id", sa.String(64), nullable=True))

    # 3. Add composite unique constraints on parent tables (required for composite FKs in PostgreSQL)
    if is_postgres:
        op.create_unique_constraint("uq_legal_entities_org_company", "legal_entities", ["org_id", "company_code"])
        op.create_unique_constraint("uq_legal_entities_id_org", "legal_entities", ["id", "org_id"])
        op.create_unique_constraint("uq_users_org_email", "users", ["org_id", "email"])
        op.create_unique_constraint("uq_users_id_org", "users", ["id", "org_id"])
        op.create_unique_constraint("uq_integration_connections_org_pillar", "integration_connections", ["org_id", "pillar"])
        op.create_unique_constraint("uq_integration_connections_id_org", "integration_connections", ["id", "org_id"])
        op.create_unique_constraint("uq_gmail_accounts_org_mailbox", "gmail_accounts", ["org_id", "mailbox_address"])
        op.create_unique_constraint("uq_gmail_accounts_id_org", "gmail_accounts", ["id", "org_id"])
        op.create_unique_constraint("uq_vendors_org_code", "vendors", ["org_id", "erp_vendor_code"])
        op.create_unique_constraint("uq_vendors_id_org", "vendors", ["id", "org_id"])
        op.create_unique_constraint("uq_erp_work_orders_org_po", "erp_work_orders", ["org_id", "po_number"])
        op.create_unique_constraint("uq_erp_work_orders_id_org", "erp_work_orders", ["id", "org_id"])
        op.create_unique_constraint("uq_erp_grns_org_grn", "erp_grns", ["org_id", "grn_number"])
        op.create_unique_constraint("uq_erp_grns_id_org", "erp_grns", ["id", "org_id"])
        op.create_unique_constraint("uq_erp_qc_records_org_qc", "erp_qc_records", ["org_id", "qc_certificate_number"])
        op.create_unique_constraint("uq_invoices_id_org", "invoices", ["id", "org_id"])
        op.create_unique_constraint("uq_documents_id_org", "documents", ["id", "org_id"])
        op.create_unique_constraint("uq_extraction_runs_id_org", "extraction_runs", ["id", "org_id"])
        op.create_unique_constraint("uq_match_runs_id_org", "match_runs", ["id", "org_id"])
        op.create_unique_constraint("uq_ingestion_jobs_org_idempotency", "ingestion_jobs", ["org_id", "idempotency_key"])

        # 4. Add composite foreign keys on child tables (blocking cross-tenant linkage)
        op.create_foreign_key(
            "fk_role_assignments_user_org",
            "role_assignments",
            "users",
            ["user_id", "org_id"],
            ["id", "org_id"],
        )
        op.create_foreign_key(
            "fk_conn_health_conn_org",
            "connection_health_events",
            "integration_connections",
            ["connection_id", "org_id"],
            ["id", "org_id"],
        )
        op.create_foreign_key(
            "fk_vendor_gstins_vendor_org",
            "vendor_gstins",
            "vendors",
            ["vendor_id", "org_id"],
            ["id", "org_id"],
        )
        op.create_foreign_key(
            "fk_erp_po_lines_po_org",
            "erp_po_lines",
            "erp_work_orders",
            ["po_id", "org_id"],
            ["id", "org_id"],
        )
        op.create_foreign_key(
            "fk_erp_grn_lines_grn_org",
            "erp_grn_lines",
            "erp_grns",
            ["grn_id", "org_id"],
            ["id", "org_id"],
        )
        op.create_foreign_key(
            "fk_invoice_lines_invoice_org",
            "invoice_lines",
            "invoices",
            ["invoice_id", "org_id"],
            ["id", "org_id"],
        )
        op.create_foreign_key(
            "fk_extraction_runs_doc_org",
            "extraction_runs",
            "documents",
            ["document_id", "org_id"],
            ["id", "org_id"],
        )
        op.create_foreign_key(
            "fk_extracted_fields_run_org",
            "extracted_fields",
            "extraction_runs",
            ["extraction_run_id", "org_id"],
            ["id", "org_id"],
        )
        op.create_foreign_key(
            "fk_match_runs_invoice_org",
            "match_runs",
            "invoices",
            ["invoice_id", "org_id"],
            ["id", "org_id"],
        )
        op.create_foreign_key(
            "fk_match_gates_run_org",
            "match_gate_checks",
            "match_runs",
            ["match_run_id", "org_id"],
            ["id", "org_id"],
        )
        op.create_foreign_key(
            "fk_exceptions_invoice_org",
            "exceptions",
            "invoices",
            ["invoice_id", "org_id"],
            ["id", "org_id"],
        )
        op.create_foreign_key(
            "fk_quarantined_docs_doc_org",
            "quarantined_documents",
            "documents",
            ["document_id", "org_id"],
            ["id", "org_id"],
        )
        op.create_foreign_key(
            "fk_approval_requests_invoice_org",
            "approval_requests",
            "invoices",
            ["invoice_id", "org_id"],
            ["id", "org_id"],
        )

    # 5. PostgreSQL Row-Level Security (RLS) & Runtime Role Configuration
    if is_postgres:
        # Create unprivileged application runtime role if it doesn't already exist.
        # Zero passwords embedded in migration code; authentication credentials must be supplied
        # out-of-band via operator secrets or connection pooler configuration.
        op.execute("""
            DO $$
            BEGIN
                IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'ap_app_user') THEN
                    CREATE ROLE ap_app_user WITH LOGIN
                        NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS NOINHERIT;
                END IF;
            END
            $$;
        """)
        op.execute("GRANT ap_app_user TO postgres;")

        # Grant minimal DML privileges to ap_app_user.
        # Retain table ownership exclusively with the migration role (postgres).
        op.execute("GRANT USAGE ON SCHEMA public TO ap_app_user;")
        op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO ap_app_user;")
        op.execute("REVOKE UPDATE, DELETE ON audit_events FROM ap_app_user;")
        op.execute("GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO ap_app_user;")
        op.execute("ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO ap_app_user;")
        op.execute("ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO ap_app_user;")

        # Enable and force RLS on all tenant tables.
        # PostgreSQL RLS Policy Semantics:
        # PostgreSQL evaluates access as: (perm1 OR perm2 OR ...) AND (rest1 AND rest2 AND ...).
        # Without at least one PERMISSIVE policy, PostgreSQL applies a default-deny rule, barring all access.
        # Therefore, the tenant isolation policy must be declared AS PERMISSIVE.
        # Because this is the ONLY policy assigned to ap_app_user, access is granted strictly when the
        # tenant predicate evaluates to TRUE. Missing or mismatched context evaluates to NULL/FALSE, failing closed.
        for table in TENANT_TABLES:
            op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;")
            op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY;")

            # For organisations, isolation evaluates against id; for all other tables, against org_id.
            # Explicit cast to ::text guarantees type compatibility whether org_id is VARCHAR, TEXT, or UUID.
            # TRIM and NULLIF ensure unset or whitespace-only context evaluates to NULL and fails closed.
            if table == "organisations":
                op.execute(f"""
                    DROP POLICY IF EXISTS tenant_isolation_policy ON {table};
                    CREATE POLICY tenant_isolation_policy ON {table}
                    AS PERMISSIVE
                    FOR ALL
                    TO ap_app_user
                    USING (id::text = NULLIF(TRIM(current_setting('app.current_org_id', true)), ''))
                    WITH CHECK (id::text = NULLIF(TRIM(current_setting('app.current_org_id', true)), ''));
                """)
            else:
                op.execute(f"""
                    DROP POLICY IF EXISTS tenant_isolation_policy ON {table};
                    CREATE POLICY tenant_isolation_policy ON {table}
                    AS PERMISSIVE
                    FOR ALL
                    TO ap_app_user
                    USING (org_id::text = NULLIF(TRIM(current_setting('app.current_org_id', true)), ''))
                    WITH CHECK (org_id::text = NULLIF(TRIM(current_setting('app.current_org_id', true)), ''));
                """)


def downgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"

    if is_postgres:
        for table in TENANT_TABLES:
            op.execute(f"DROP POLICY IF EXISTS tenant_isolation_policy ON {table};")
            op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY;")
            op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY;")

    # Drop composite foreign keys
    op.drop_constraint("fk_approval_requests_invoice_org", "approval_requests", type_="foreignkey")
    op.drop_constraint("fk_quarantined_docs_doc_org", "quarantined_documents", type_="foreignkey")
    op.drop_constraint("fk_exceptions_invoice_org", "exceptions", type_="foreignkey")
    op.drop_constraint("fk_match_gates_run_org", "match_gate_checks", type_="foreignkey")
    op.drop_constraint("fk_match_runs_invoice_org", "match_runs", type_="foreignkey")
    op.drop_constraint("fk_extracted_fields_run_org", "extracted_fields", type_="foreignkey")
    op.drop_constraint("fk_extraction_runs_doc_org", "extraction_runs", type_="foreignkey")
    op.drop_constraint("fk_invoice_lines_invoice_org", "invoice_lines", type_="foreignkey")
    op.drop_constraint("fk_erp_grn_lines_grn_org", "erp_grn_lines", type_="foreignkey")
    op.drop_constraint("fk_erp_po_lines_po_org", "erp_po_lines", type_="foreignkey")
    op.drop_constraint("fk_vendor_gstins_vendor_org", "vendor_gstins", type_="foreignkey")
    op.drop_constraint("fk_conn_health_conn_org", "connection_health_events", type_="foreignkey")
    op.drop_constraint("fk_role_assignments_user_org", "role_assignments", type_="foreignkey")

    # Drop composite unique constraints
    op.drop_constraint("uq_ingestion_jobs_org_idempotency", "ingestion_jobs", type_="unique")
    op.drop_constraint("uq_match_runs_id_org", "match_runs", type_="unique")
    op.drop_constraint("uq_extraction_runs_id_org", "extraction_runs", type_="unique")
    op.drop_constraint("uq_documents_id_org", "documents", type_="unique")
    op.drop_constraint("uq_invoices_id_org", "invoices", type_="unique")
    op.drop_constraint("uq_erp_qc_records_org_qc", "erp_qc_records", type_="unique")
    op.drop_constraint("uq_erp_grns_id_org", "erp_grns", type_="unique")
    op.drop_constraint("uq_erp_grns_org_grn", "erp_grns", type_="unique")
    op.drop_constraint("uq_erp_work_orders_id_org", "erp_work_orders", type_="unique")
    op.drop_constraint("uq_erp_work_orders_org_po", "erp_work_orders", type_="unique")
    op.drop_constraint("uq_vendors_id_org", "vendors", type_="unique")
    op.drop_constraint("uq_vendors_org_code", "vendors", type_="unique")
    op.drop_constraint("uq_gmail_accounts_id_org", "gmail_accounts", type_="unique")
    op.drop_constraint("uq_gmail_accounts_org_mailbox", "gmail_accounts", type_="unique")
    op.drop_constraint("uq_integration_connections_id_org", "integration_connections", type_="unique")
    op.drop_constraint("uq_integration_connections_org_pillar", "integration_connections", type_="unique")
    op.drop_constraint("uq_users_id_org", "users", type_="unique")
    op.drop_constraint("uq_users_org_email", "users", type_="unique")
    op.drop_constraint("uq_legal_entities_id_org", "legal_entities", type_="unique")
    op.drop_constraint("uq_legal_entities_org_company", "legal_entities", type_="unique")

    # Drop soft-delete columns
    op.drop_column("documents", "deleted_by_user_id")
    op.drop_column("documents", "deleted_at")
    op.drop_column("documents", "is_deleted")

    # Drop org_id columns
    tables_needing_org_id = [
        "gmail_accounts", "erp_work_orders", "erp_po_lines", "erp_grns",
        "erp_grn_lines", "erp_qc_records", "ingestion_jobs", "documents",
        "invoice_lines", "approval_requests", "exceptions", "quarantined_documents",
        "connection_health_events", "role_assignments", "vendor_gstins",
        "extraction_runs", "extracted_fields", "match_runs", "match_gate_checks",
    ]
    for table_name in tables_needing_org_id:
        if is_postgres:
            op.drop_constraint(f"fk_{table_name}_org_id", table_name, type_="foreignkey")
        op.drop_index(f"ix_{table_name}_org_id", table_name)
        op.drop_column(table_name, "org_id")
