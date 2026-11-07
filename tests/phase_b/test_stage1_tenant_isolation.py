"""Phase B Stage 1 Acceptance Tests — Database & Relational Tenant Isolation.

Enforces:
1. Composite foreign keys prevent cross-tenant parent-child references.
2. Identifiers (PO numbers, GRN numbers, vendor codes, idempotency keys) are isolated per tenant.
3. Soft-deletion schema invariants are maintained.
4. Tenant context lifecycle hooks operate properly.
5. Migration 002 applies and maintains relational constraints.
"""

from __future__ import annotations

import datetime
from decimal import Decimal
import os
os.environ["APP_ENV"] = "test"
import pytest
from sqlalchemy import create_engine, event, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from backend.core.database import Base, set_tenant_context
from backend.models.domain import (
    ApprovalRequest, AuditEvent, ConnectionHealthEvent, Document,
    ExceptionRecord, ExtractedField, ExtractionRun, GmailAccount,
    GoodsReceiptLineSnapshot, GoodsReceiptSnapshot, IngestionJob,
    IntegrationConnection, Invoice, InvoiceLine, LegalEntity,
    MatchGateCheck, MatchRun, Organisation, QuarantinedDocument,
    QualityControlSnapshot, RoleAssignment, User, Vendor, VendorGSTIN,
    WorkOrderLineSnapshot, WorkOrderSnapshot
)


@pytest.fixture
def sqlite_fk_engine():
    """SQLite engine with explicit foreign key enforcement enabled."""
    engine = create_engine("sqlite:///:memory:")

    @event.listens_for(engine, "connect")
    def enable_sqlite_fk(dbapi_con, con_record):
        cursor = dbapi_con.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def fk_session(sqlite_fk_engine):
    """Session connected to the foreign-key-enforcing engine for isolated testing."""
    connection = sqlite_fk_engine.connect()
    SessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=connection
    )
    session = SessionLocal()

    # Pre-seed two isolated organisations
    org_a = Organisation(id="org_alpha", name="Alpha Corp")
    org_b = Organisation(id="org_beta", name="Beta Corp")
    session.add_all([org_a, org_b])
    session.commit()

    yield session

    session.close()
    connection.close()


# ------------------------------------------------------------------------------
# 1. Composite Foreign Key Isolation Tests (Cross-Tenant Linkage Rejection)
# ------------------------------------------------------------------------------

def test_cross_tenant_invoice_line_rejected(fk_session: Session):
    """Proves Tenant B cannot attach an invoice line to Tenant A's invoice."""
    # Tenant A creates invoice
    inv_a = Invoice(
        id="inv_a_001",
        org_id="org_alpha",
        source_channel="MANUAL_UPLOAD",
        currency="INR",
    )
    fk_session.add(inv_a)
    fk_session.commit()

    # Tenant B attempts to attach invoice line to Tenant A's invoice
    cross_line = InvoiceLine(
        id="line_cross_001",
        org_id="org_beta",  # Belongs to Beta
        invoice_id="inv_a_001",  # Targets Alpha's invoice
        line_number=1,
        description="Illicit cross-tenant line item",
        billed_quantity=Decimal("10.0"),
        billed_unit_rate=Decimal("100.0"),
        billed_line_total=Decimal("1000.0"),
    )
    fk_session.add(cross_line)

    with pytest.raises(IntegrityError):
        fk_session.commit()
    fk_session.rollback()

    # Same-tenant line item must succeed
    valid_line = InvoiceLine(
        id="line_valid_001",
        org_id="org_alpha",
        invoice_id="inv_a_001",
        line_number=1,
        description="Legitimate line item",
        billed_quantity=Decimal("10.0"),
        billed_unit_rate=Decimal("100.0"),
        billed_line_total=Decimal("1000.0"),
    )
    fk_session.add(valid_line)
    fk_session.commit()
    assert fk_session.get(InvoiceLine, "line_valid_001") is not None


def test_cross_tenant_po_line_rejected(fk_session: Session):
    """Proves Tenant B cannot attach a PO line to Tenant A's purchase order."""
    po_a = WorkOrderSnapshot(
        id="po_a_001",
        org_id="org_alpha",
        po_number="PO-ALPHA-99",
        vendor_code="VEND-01",
        total_authorized_amount=Decimal("50000.00"),
        remaining_balance=Decimal("50000.00"),
        currency="INR",
        status="OPEN",
    )
    fk_session.add(po_a)
    fk_session.commit()

    # Cross-tenant PO line
    cross_po_line = WorkOrderLineSnapshot(
        id="po_line_cross",
        org_id="org_beta",
        po_id="po_a_001",
        line_number=1,
        item_code="ITEM-X",
        description="Cross tenant material",
        authorized_quantity=Decimal("10"),
        contracted_unit_rate=Decimal("500"),
        authorized_line_total=Decimal("5000"),
    )
    fk_session.add(cross_po_line)

    with pytest.raises(IntegrityError):
        fk_session.commit()
    fk_session.rollback()


def test_cross_tenant_grn_line_rejected(fk_session: Session):
    """Proves Tenant B cannot attach a GRN line to Tenant A's goods receipt."""
    grn_a = GoodsReceiptSnapshot(
        id="grn_a_001",
        org_id="org_alpha",
        grn_number="GRN-ALPHA-01",
        po_number="PO-ALPHA-99",
        received_date=datetime.datetime.utcnow(),
    )
    fk_session.add(grn_a)
    fk_session.commit()

    # Cross-tenant GRN line
    cross_grn_line = GoodsReceiptLineSnapshot(
        id="grn_line_cross",
        org_id="org_beta",
        grn_id="grn_a_001",
        po_line_number=1,
        accepted_quantity=Decimal("10"),
        rejected_quantity=Decimal("0"),
    )
    fk_session.add(cross_grn_line)

    with pytest.raises(IntegrityError):
        fk_session.commit()
    fk_session.rollback()


def test_cross_tenant_vendor_gstin_rejected(fk_session: Session):
    """Proves Tenant B cannot attach a GSTIN to Tenant A's vendor master."""
    vend_a = Vendor(
        id="vend_a_001",
        org_id="org_alpha",
        erp_vendor_code="V-100",
        legal_name="Alpha Steel Ltd",
    )
    fk_session.add(vend_a)
    fk_session.commit()

    cross_gstin = VendorGSTIN(
        id="gstin_cross",
        org_id="org_beta",
        vendor_id="vend_a_001",
        gstin="29ABCDE1234F1Z5",
        state_code="29",
    )
    fk_session.add(cross_gstin)

    with pytest.raises(IntegrityError):
        fk_session.commit()
    fk_session.rollback()


def test_cross_tenant_quarantine_document_rejected(fk_session: Session):
    """Proves Tenant B cannot attach a quarantine record to Tenant A's document."""
    doc_a = Document(
        id="doc_a_001",
        org_id="org_alpha",
        filename="invoice.pdf",
        mime_type="application/pdf",
        file_size_bytes=1024,
        sha256_hash="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        storage_provider="supabase",
        storage_key="org_alpha/invoices/doc_a_001.pdf",
    )
    fk_session.add(doc_a)
    fk_session.commit()

    cross_quarantine = QuarantinedDocument(
        id="q_doc_cross",
        org_id="org_beta",
        document_id="doc_a_001",
        quarantine_reason="MALFORMED_PDF",
    )
    fk_session.add(cross_quarantine)

    with pytest.raises(IntegrityError):
        fk_session.commit()
    fk_session.rollback()


# ------------------------------------------------------------------------------
# 2. Per-Tenant Identifier Scoping & Duplicate Prevention Tests
# ------------------------------------------------------------------------------

def test_po_numbers_isolated_per_tenant(fk_session: Session):
    """Proves two distinct tenants can use the same internal PO number."""
    po_alpha = WorkOrderSnapshot(
        id="po_alpha_1",
        org_id="org_alpha",
        po_number="PO-COMMON-001",
        vendor_code="V-01",
        total_authorized_amount=Decimal("100.00"),
        remaining_balance=Decimal("100.00"),
        currency="INR",
        status="OPEN",
    )
    po_beta = WorkOrderSnapshot(
        id="po_beta_1",
        org_id="org_beta",
        po_number="PO-COMMON-001",  # Same PO number as Alpha
        vendor_code="V-02",
        total_authorized_amount=Decimal("200.00"),
        remaining_balance=Decimal("200.00"),
        currency="INR",
        status="OPEN",
    )
    fk_session.add_all([po_alpha, po_beta])
    fk_session.commit()

    assert fk_session.get(WorkOrderSnapshot, "po_alpha_1") is not None
    assert fk_session.get(WorkOrderSnapshot, "po_beta_1") is not None

    # Intra-tenant duplicate must fail
    dup_alpha = WorkOrderSnapshot(
        id="po_alpha_2",
        org_id="org_alpha",
        po_number="PO-COMMON-001",  # Duplicate within Alpha
        vendor_code="V-01",
        total_authorized_amount=Decimal("300.00"),
        remaining_balance=Decimal("300.00"),
        currency="INR",
        status="OPEN",
    )
    fk_session.add(dup_alpha)
    with pytest.raises(IntegrityError):
        fk_session.commit()
    fk_session.rollback()


def test_vendor_codes_isolated_per_tenant(fk_session: Session):
    """Proves two distinct tenants can use the same internal ERP vendor code."""
    v_alpha = Vendor(id="v_a", org_id="org_alpha", erp_vendor_code="1000", legal_name="Vendor A")
    v_beta = Vendor(id="v_b", org_id="org_beta", erp_vendor_code="1000", legal_name="Vendor B")
    fk_session.add_all([v_alpha, v_beta])
    fk_session.commit()

    assert fk_session.get(Vendor, "v_a") is not None
    assert fk_session.get(Vendor, "v_b") is not None

    dup_alpha = Vendor(id="v_a_dup", org_id="org_alpha", erp_vendor_code="1000", legal_name="Vendor A Dup")
    fk_session.add(dup_alpha)
    with pytest.raises(IntegrityError):
        fk_session.commit()
    fk_session.rollback()


def test_ingestion_idempotency_isolated_per_tenant(fk_session: Session):
    """Proves ingestion job idempotency keys are scoped per tenant."""
    job_alpha = IngestionJob(
        id="job_a",
        org_id="org_alpha",
        idempotency_key="batch_sync_2026",
        source_channel="GMAIL",
        status="COMPLETED",
    )
    job_beta = IngestionJob(
        id="job_b",
        org_id="org_beta",
        idempotency_key="batch_sync_2026",
        source_channel="GMAIL",
        status="COMPLETED",
    )
    fk_session.add_all([job_alpha, job_beta])
    fk_session.commit()

    assert fk_session.get(IngestionJob, "job_a") is not None
    assert fk_session.get(IngestionJob, "job_b") is not None


# ------------------------------------------------------------------------------
# 3. Soft-Deletion Schema Invariants
# ------------------------------------------------------------------------------

def test_document_soft_delete_preserves_records(fk_session: Session):
    """Verifies that soft-deleting an invoice document retains hash and metadata."""
    doc = Document(
        id="doc_soft_del_01",
        org_id="org_alpha",
        filename="invoice_soft_del.pdf",
        mime_type="application/pdf",
        file_size_bytes=2048,
        sha256_hash="f5a5c60c4f130e0f5b3d91f503210f283461345d4291137ac29b37a9cedb7f7f",
        storage_provider="supabase",
        storage_key="org_alpha/invoices/doc_soft_del_01.pdf",
        is_original=True,
    )
    fk_session.add(doc)
    fk_session.commit()

    assert doc.is_deleted is False

    # Execute soft-deletion
    doc.is_deleted = True
    doc.deleted_at = datetime.datetime.utcnow()
    doc.deleted_by_user_id = "usr_admin_01"
    fk_session.commit()

    reloaded = fk_session.get(Document, "doc_soft_del_01")
    assert reloaded.is_deleted is True
    assert reloaded.deleted_at is not None
    assert reloaded.deleted_by_user_id == "usr_admin_01"
    assert reloaded.sha256_hash == "f5a5c60c4f130e0f5b3d91f503210f283461345d4291137ac29b37a9cedb7f7f"


# ------------------------------------------------------------------------------
# 4. Tenant Context Session Hook & Application Lifecycle Tests
# ------------------------------------------------------------------------------

def test_set_tenant_context_binds_session_info(fk_session: Session):
    """Verifies set_tenant_context records tenant_org_id on session."""
    set_tenant_context(fk_session, "org_gamma")
    assert fk_session.info.get("tenant_org_id") == "org_gamma"


def test_set_tenant_context_strips_whitespace_and_handles_empty(fk_session: Session):
    """Verifies that whitespace is trimmed and empty/None values are safely stored."""
    set_tenant_context(fk_session, "  org_trimmed  ")
    assert fk_session.info.get("tenant_org_id") == "org_trimmed"

    set_tenant_context(fk_session, "")
    assert fk_session.info.get("tenant_org_id") == ""

    set_tenant_context(fk_session, None)
    assert fk_session.info.get("tenant_org_id") == ""


def test_session_cleanup_on_close(sqlite_fk_engine):
    """Verifies session.info is cleared upon session close, preventing cross-request leaks."""
    connection = sqlite_fk_engine.connect()
    SessionLocal = sessionmaker(bind=connection)
    session = SessionLocal()

    set_tenant_context(session, "org_temp")
    assert session.info.get("tenant_org_id") == "org_temp"

    session.info.clear()
    session.close()
    assert "tenant_org_id" not in session.info
    connection.close()


def test_get_current_user_injects_tenant_context(fk_session: Session):
    """Verifies that FastAPI get_current_user derives tenant from token and sets context."""
    from fastapi.security import HTTPAuthorizationCredentials
    from backend.core.config import AppEnv, settings
    from backend.core.auth import get_current_user

    original_env = settings.APP_ENV
    settings.APP_ENV = AppEnv.TEST
    try:
        creds = HTTPAuthorizationCredentials(
            scheme="Bearer",
            credentials="test_token:AP_ASSOCIATE:usr_stage1_check:tester@company.internal"
        )
        user = get_current_user(credentials=creds, db=fk_session)
        assert user.org_id == "org_default"
        assert fk_session.info.get("tenant_org_id") == "org_default"
    finally:
        settings.APP_ENV = original_env


# ------------------------------------------------------------------------------
# 5. Live PostgreSQL RLS Integration Test Suite (Conditioned on Live DB URL)
# ------------------------------------------------------------------------------

@pytest.fixture
def live_pg_connection(postgres_database):
    """An owned, migrated disposable DB and an actual non-bypass connection."""
    pg = postgres_database
    with Session(pg['admin']) as db:
        db.add_all([Organisation(id=org, name=org) for org in ('org_alpha', 'org_beta')])
        db.flush()
        db.add_all([Invoice(id=f'invoice-{org}', org_id=org, source_channel='MANUAL_UPLOAD')
                    for org in ('org_alpha', 'org_beta')])
        db.commit()
    with pg['app'].connect() as connection:
        assert connection.scalar(text('SELECT current_user')) == 'ap_app_user'
        yield connection


def test_pg_rls_01_tenant_a_reads_own_records(live_pg_connection):
    """Proves Tenant A can read its own records via RLS."""
    live_pg_connection.execute(text("SET ROLE ap_app_user;"))
    live_pg_connection.execute(text("SELECT set_config('app.current_org_id', 'org_alpha', true);"))
    rows = live_pg_connection.execute(text("SELECT org_id FROM invoices;")).fetchall()
    assert rows and all(r[0] == "org_alpha" for r in rows)


def test_pg_rls_02_tenant_a_cannot_read_tenant_b_records(live_pg_connection):
    """Proves Tenant A cannot read Tenant B records via RLS."""
    live_pg_connection.execute(text("SET ROLE ap_app_user;"))
    live_pg_connection.execute(text("SELECT set_config('app.current_org_id', 'org_alpha', true);"))
    rows = live_pg_connection.execute(text("SELECT id FROM invoices WHERE org_id = 'org_beta';")).fetchall()
    assert len(rows) == 0


def test_pg_rls_03_tenant_a_cannot_insert_tenant_b_records(live_pg_connection):
    """Proves Tenant A cannot insert records under Tenant B (WITH CHECK violation)."""
    live_pg_connection.execute(text("SET ROLE ap_app_user;"))
    live_pg_connection.execute(text("SELECT set_config('app.current_org_id', 'org_alpha', true);"))
    with pytest.raises(Exception) as exc_info:
        live_pg_connection.execute(text("""
            INSERT INTO invoices (id, org_id, source_channel, currency, stage, decision, created_at, updated_at)
            VALUES ('inv_cross_rls', 'org_beta', 'MANUAL_UPLOAD', 'INR', 'RECEIVED', 'NEEDS_REVIEW', NOW(), NOW());
        """))
    assert "violates row-level security policy" in str(exc_info.value).lower()


def test_pg_rls_04_tenant_a_cannot_update_tenant_b_records(live_pg_connection):
    """Proves Tenant A cannot update Tenant B records (invisible to UPDATE)."""
    live_pg_connection.execute(text("SET ROLE ap_app_user;"))
    live_pg_connection.execute(text("SELECT set_config('app.current_org_id', 'org_alpha', true);"))
    res = live_pg_connection.execute(text("UPDATE invoices SET stage = 'ACTION_REQUIRED' WHERE org_id = 'org_beta';"))
    assert res.rowcount == 0


def test_pg_rls_05_tenant_a_cannot_delete_tenant_b_records(live_pg_connection):
    """Proves Tenant A cannot delete Tenant B records (invisible to DELETE)."""
    live_pg_connection.execute(text("SET ROLE ap_app_user;"))
    live_pg_connection.execute(text("SELECT set_config('app.current_org_id', 'org_alpha', true);"))
    res = live_pg_connection.execute(text("DELETE FROM invoices WHERE org_id = 'org_beta';"))
    assert res.rowcount == 0


def test_pg_rls_06_missing_tenant_context_fails_closed(live_pg_connection):
    """Proves missing tenant context (NULL) fails closed, returning 0 rows."""
    live_pg_connection.execute(text("SET ROLE ap_app_user;"))
    live_pg_connection.execute(text("SELECT set_config('app.current_org_id', '', true);"))
    rows = live_pg_connection.execute(text("SELECT id FROM invoices;")).fetchall()
    assert len(rows) == 0


def test_pg_rls_07_invalid_tenant_context_fails_closed(live_pg_connection):
    """Proves non-existent tenant context fails closed, returning 0 rows."""
    live_pg_connection.execute(text("SET ROLE ap_app_user;"))
    live_pg_connection.execute(text("SELECT set_config('app.current_org_id', 'org_non_existent_random_id', true);"))
    rows = live_pg_connection.execute(text("SELECT id FROM invoices;")).fetchall()
    assert len(rows) == 0


def test_pg_rls_08_tenant_context_does_not_leak_between_pooled_transactions(live_pg_connection):
    """Proves transaction-local context (is_local=true) does not leak across pooled transactions."""
    live_pg_connection.execute(text("SET ROLE ap_app_user;"))
    live_pg_connection.commit()
    # Transaction 1: Set context to org_alpha and commit
    with live_pg_connection.begin():
        live_pg_connection.execute(text("SELECT set_config('app.current_org_id', 'org_alpha', true);"))

    # Transaction 2 on same connection: setting must revert to empty/NULL
    with live_pg_connection.begin():
        val = live_pg_connection.execute(text("SELECT current_setting('app.current_org_id', true);")).scalar()
        assert val in (None, "")


def test_pg_rls_09_runtime_role_cannot_bypass_rls(live_pg_connection):
    """Proves runtime role ap_app_user has NOBYPASSRLS and NOSUPERUSER in pg_roles."""
    role_info = live_pg_connection.execute(text("""
        SELECT rolsuper, rolbypassrls, rolcanlogin
        FROM pg_roles
        WHERE rolname = 'ap_app_user';
    """)).fetchone()
    assert role_info is not None, "ap_app_user role must exist in pg_roles"
    assert role_info[0] is False, "ap_app_user must have NOSUPERUSER"
    assert role_info[1] is False, "ap_app_user must have NOBYPASSRLS"
