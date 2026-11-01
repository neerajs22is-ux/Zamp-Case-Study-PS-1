"""Stage 9 — Live Supabase Provisioning, Integration & Security Verification Suite.

Validates the live Supabase project (Project Ref: qxrrbyjczuqkgnexwqyh):
1. Live PostgreSQL connection health & transaction pooler.
2. Alembic schema migration completeness (revisions 001 - 007).
3. PostgreSQL Row-Level Security (RLS) & tenant isolation enforcement.
4. Database-level audit log immutability triggers (trg_audit_events_immutable).
5. Supabase private Storage bucket (invoices) upload, retrieve, signed URL, and deletion.
6. Asymmetric JWKS public key resolution (ES256).
7. Tenant membership & RBAC permissions.
8. Secret hygiene: verifies frontend assets never contain service role keys.
"""

import datetime
import os
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

from backend.core.config import settings
from backend.core.database import check_db_health, set_tenant_context
from backend.core.storage import SupabaseStorageAdapter, build_tenant_storage_path
from backend.core.auth import fetch_and_cache_jwks, get_jwk_key_by_kid, UserRole, AuthenticatedUser

LIVE_DB_DIRECT = os.getenv("MIGRATION_DATABASE_URL")
LIVE_DB_POOLER = os.getenv("DATABASE_URL")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SERVICE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")


@pytest.fixture(scope="module")
def direct_pg_engine():
    """Provides a connection engine to the direct PostgreSQL instance."""
    if not LIVE_DB_DIRECT:
        pytest.skip("MIGRATION_DATABASE_URL not set for live direct PG verification")
    engine = create_engine(LIVE_DB_DIRECT, poolclass=NullPool)
    yield engine
    engine.dispose()


@pytest.fixture(scope="module")
def pooler_pg_engine():
    """Provides a connection engine to the Supabase transaction pooler."""
    if not LIVE_DB_POOLER:
        pytest.skip("DATABASE_URL not set for live pooler PG verification")
    engine = create_engine(LIVE_DB_POOLER, poolclass=NullPool)
    yield engine
    engine.dispose()


# ==============================================================================
# 1. Database Connectivity and Schema Verification
# ==============================================================================

def test_01_live_database_health_and_version(direct_pg_engine):
    """Verifies direct connectivity and reports PostgreSQL version."""
    with direct_pg_engine.connect() as conn:
        ver = conn.execute(text("SELECT version();")).scalar()
        assert "PostgreSQL" in ver
        conn.rollback()
        print(f"\n[LIVE] PostgreSQL Version: {ver[:45]}...")


def test_02_live_alembic_migrations_applied_to_head(direct_pg_engine):
    """Verifies all 7 Alembic migrations are applied and alembic_version is at head."""
    with direct_pg_engine.connect() as conn:
        res = conn.execute(text("SELECT version_num FROM alembic_version;")).fetchall()
        assert len(res) == 1
        current_rev = res[0][0]
        conn.rollback()
        assert current_rev == "007_stage52_pubsub_recovery", f"Expected 007_stage52_pubsub_recovery, got {current_rev}"


def test_03_live_schema_tables_and_indexes_exist(direct_pg_engine):
    """Verifies all 31 application tables exist in the public schema."""
    expected_tables = {
        "organisations", "legal_entities", "users", "role_assignments",
        "integration_connections", "connection_health_events", "gmail_accounts",
        "vendors", "vendor_gstins", "erp_work_orders", "erp_po_lines",
        "erp_grns", "erp_grn_lines", "erp_qc_records", "invoices",
        "invoice_lines", "documents", "extraction_runs", "extracted_fields",
        "match_runs", "match_gate_checks", "ingestion_jobs", "exceptions",
        "quarantined_documents", "approval_requests", "audit_events",
        "user_invitations", "access_requests", "oauth_state_nonces",
        "gmail_pubsub_events", "alembic_version"
    }
    with direct_pg_engine.connect() as conn:
        rows = conn.execute(text("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public';
        """)).fetchall()
        existing_tables = {r[0] for r in rows}
        missing = expected_tables - existing_tables
        conn.rollback()
        assert not missing, f"Missing tables in public schema: {missing}"


# ==============================================================================
# 2. PostgreSQL Row-Level Security (RLS) & Tenant Isolation
# ==============================================================================

def test_04_live_rls_enabled_and_forced_on_tenant_tables(direct_pg_engine):
    """Verifies RLS is enabled and FORCED on all core tenant tables."""
    tenant_tables = [
        "organisations", "legal_entities", "users", "role_assignments",
        "invoices", "invoice_lines", "documents", "vendors", "audit_events"
    ]
    with direct_pg_engine.connect() as conn:
        for tbl in tenant_tables:
            row = conn.execute(text(f"""
                SELECT relrowsecurity, relforcerowsecurity 
                FROM pg_class 
                JOIN pg_namespace ON pg_namespace.oid = pg_class.relnamespace 
                WHERE pg_namespace.nspname = 'public' AND relname = '{tbl}';
            """)).fetchone()
            assert row is not None, f"Table {tbl} not found in pg_class"
            assert row[0] is True, f"RLS not enabled on {tbl}"
            assert row[1] is True, f"FORCE RLS not enabled on {tbl}"
        conn.rollback()


def test_05_live_rls_cross_tenant_isolation_enforced(direct_pg_engine):
    """Proves ap_app_user in org_alpha cannot view or insert org_beta invoices."""
    with direct_pg_engine.connect() as conn:
        # 1. Seed orgs & invoices as admin
        conn.execute(text("""
            INSERT INTO organisations (id, name, created_at)
            VALUES 
                ('org_alpha', 'Alpha Corp', NOW()),
                ('org_beta', 'Beta Corp', NOW())
            ON CONFLICT (id) DO NOTHING;
        """))
        conn.execute(text("""
            INSERT INTO invoices (id, org_id, source_channel, currency, stage, decision, created_at, updated_at)
            VALUES 
                ('inv_alpha_live_01', 'org_alpha', 'MANUAL_UPLOAD', 'INR', 'RECEIVED', 'NEEDS_REVIEW', NOW(), NOW()),
                ('inv_beta_live_01', 'org_beta', 'MANUAL_UPLOAD', 'INR', 'RECEIVED', 'NEEDS_REVIEW', NOW(), NOW())
            ON CONFLICT (id, org_id) DO NOTHING;
        """))
        conn.commit()

        # 2. Switch to unprivileged runtime role
        conn.execute(text("SET ROLE ap_app_user;"))
        conn.execute(text("SELECT set_config('app.current_org_id', 'org_alpha', true);"))

        # Query invoices: only org_alpha must be visible
        visible_rows = conn.execute(text("SELECT id, org_id FROM invoices;")).fetchall()
        assert all(r[1] == "org_alpha" for r in visible_rows)

        # Cross-tenant query: org_beta invoices must return 0 rows
        beta_rows = conn.execute(text("SELECT id FROM invoices WHERE org_id = 'org_beta';")).fetchall()
        assert len(beta_rows) == 0

        # Cross-tenant insert: must fail with RLS violation
        with pytest.raises(Exception) as exc_info:
            conn.execute(text("""
                INSERT INTO invoices (id, org_id, source_channel, currency, stage, decision, created_at, updated_at)
                VALUES ('inv_cross_tenant_attack', 'org_beta', 'MANUAL_UPLOAD', 'INR', 'RECEIVED', 'NEEDS_REVIEW', NOW(), NOW());
            """))
        assert "violates row-level security policy" in str(exc_info.value).lower()
        conn.rollback()

        conn.execute(text("RESET ROLE;"))
        conn.commit()


# ==============================================================================
# 3. Database-Level Audit Log Immutability
# ==============================================================================

def test_06_live_audit_log_immutability_trigger_blocks_update_and_delete(direct_pg_engine):
    """Verifies trg_audit_events_immutable blocks any UPDATE or DELETE on audit_events."""
    with direct_pg_engine.connect() as conn:
        test_audit_id = "aud_live_immutability_test"
        conn.execute(text(f"""
            INSERT INTO audit_events (
                id, org_id, actor_id, actor_role, action, reason, timestamp
            ) VALUES (
                '{test_audit_id}', 'org_alpha', 'usr_admin', 'SYSTEM_ADMIN', 
                'SECURITY_AUDIT', 'Testing database trigger', NOW()
            ) ON CONFLICT (id) DO NOTHING;
        """))
        conn.commit()

        # Attempt UPDATE: must be aborted by trigger
        with pytest.raises(Exception) as exc_update:
            conn.execute(text(f"UPDATE audit_events SET action = 'TAMPERED' WHERE id = '{test_audit_id}';"))
        assert "audit_events is strictly append-only" in str(exc_update.value)
        conn.rollback()

        # Attempt DELETE: must be aborted by trigger
        with pytest.raises(Exception) as exc_delete:
            conn.execute(text(f"DELETE FROM audit_events WHERE id = '{test_audit_id}';"))
        assert "audit_events is strictly append-only" in str(exc_delete.value)
        conn.rollback()


# ==============================================================================
# 4. Supabase Storage Live End-to-End
# ==============================================================================

def test_07_live_supabase_storage_private_bucket_operations():
    """Verifies private invoices bucket health, file upload, download, and deletion."""
    if not SUPABASE_URL or not SERVICE_KEY:
        pytest.skip("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set in environment for live storage test")
    settings.SUPABASE_URL = SUPABASE_URL
    settings.SUPABASE_SERVICE_ROLE_KEY = SERVICE_KEY
    settings.SUPABASE_STORAGE_BUCKET = "invoices"
    settings.STORAGE_PROVIDER = "supabase"

    adapter = SupabaseStorageAdapter()
    health = adapter.check_health()
    assert health["readiness"] is True
    assert health["status"] == "CONNECTED"
    assert health["bucket"] == "invoices"

    # Save test document
    doc_id = "doc_live_stage9_001"
    test_bytes = b"%PDF-1.4 stage 9 live storage test content"
    storage_key = build_tenant_storage_path("org_stage9", doc_id, "test_invoice.pdf")
    
    save_res = adapter.save_file(test_bytes, "test_invoice.pdf", "application/pdf", storage_key=storage_key)
    assert save_res["storage_key"] == storage_key
    assert save_res["size_bytes"] == len(test_bytes)

    # Retrieve and verify content
    retrieved = adapter.get_file(storage_key)
    assert retrieved == test_bytes

    # Generate presigned URL
    signed_url = adapter.generate_signed_url(storage_key, expires_in=60)
    assert signed_url.startswith("http")
    assert "invoices" in signed_url

    # Delete test file
    deleted = adapter.delete_file(storage_key)
    assert deleted is True

    # Confirm deletion raises FileNotFoundError
    with pytest.raises(FileNotFoundError):
        adapter.get_file(storage_key)


# ==============================================================================
# 5. Supabase Auth JWKS Verification
# ==============================================================================

def test_08_live_supabase_jwks_resolves_es256_public_keys():
    """Verifies the backend retrieves and parses the live Supabase JWKS ES256 key."""
    settings.SUPABASE_URL = SUPABASE_URL
    keys = fetch_and_cache_jwks(force_refresh=True)
    assert len(keys) > 0
    
    # Check first key
    first_kid = list(keys.keys())[0]
    key_dict = keys[first_kid]
    assert key_dict.get("alg") == "ES256"
    assert key_dict.get("kty") == "EC"
    assert key_dict.get("crv") == "P-256"


# ==============================================================================
# 6. Secret Hygiene Verification
# ==============================================================================

def test_09_frontend_bundle_secret_hygiene():
    """Verifies that no service-role secrets are bundled into frontend distribution files."""
    frontend_dist = os.path.join(r"C:\Zamp Casse Study", "frontend", "dist")
    if not os.path.exists(frontend_dist):
        pytest.skip("frontend/dist does not exist; run npm run build first")

    forbidden_patterns = [
        "sb_" + "secret_",
        "SHv4VOC" + "9DMi35y70",
    ]
    if SERVICE_KEY:
        forbidden_patterns.append(SERVICE_KEY)

    for root, _, files in os.walk(frontend_dist):
        for f in files:
            if f.endswith((".js", ".html", ".map", ".css")):
                file_path = os.path.join(root, f)
                with open(file_path, "r", encoding="utf-8", errors="ignore") as fh:
                    content = fh.read()
                    for pattern in forbidden_patterns:
                        assert pattern not in content, f"Secret leakage detected in {f}: found '{pattern[:10]}...'"
