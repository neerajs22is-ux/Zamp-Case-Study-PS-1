"""Explicit financial reference fixtures; never connects to a configured service."""
import datetime
from decimal import Decimal
import uuid

import pytest


def pytest_addoption(parser):
    parser.addoption('--disposable-postgres-port', type=int, default=None,
        help='Loopback port supplied by scripts/inspect_postgres.py; never a configured database URL')
    parser.addoption('--disposable-postgres-root', default=None,
        help='Owned cluster directory created by the PostgreSQL runner')
    parser.addoption('--reverse-order', action='store_true', default=False,
        help='Run the same collected tests in reverse order to expose shared-state dependencies')


def pytest_collection_modifyitems(config, items):
    if config.getoption('--reverse-order'):
        items.reverse()


@pytest.fixture
def postgres_database(request, monkeypatch):
    """Migrate a unique database in the runner-owned cluster; drop it afterwards."""
    port = request.config.getoption('--disposable-postgres-port')
    if port is None:
        pytest.skip('Run scripts/inspect_postgres.py for an owned disposable PostgreSQL cluster')
    from pathlib import Path
    supplied_root = request.config.getoption('--disposable-postgres-root')
    if not supplied_root:
        pytest.fail('A port alone is insufficient; use the owned PostgreSQL runner')
    owned_root = Path(supplied_root).resolve()
    scratch = Path(__file__).resolve().parents[1] / 'scratch'
    if owned_root.parent != scratch or not (owned_root / '.owned-by-inspection').is_file():
        pytest.fail('Refusing a PostgreSQL cluster outside the owned scratch directory')
    pid_info = (owned_root / 'data' / 'postmaster.pid').read_text().splitlines()
    if int(pid_info[3]) != port or Path(pid_info[1]).resolve() != (owned_root / 'data').resolve():
        pytest.fail('PostgreSQL port/data directory does not match the owned cluster')
    from sqlalchemy import create_engine, text
    from sqlalchemy.pool import NullPool
    from alembic.config import Config
    from alembic import command
    from backend.core.config import settings
    name = f'ap_inspection_{uuid.uuid4().hex}_test'
    base = f'postgresql+psycopg://postgres@127.0.0.1:{port}'
    control = create_engine(base + '/postgres', isolation_level='AUTOCOMMIT', poolclass=NullPool)
    with control.connect() as connection:
        if Path(connection.scalar(text('SHOW data_directory'))).resolve() != (owned_root / 'data').resolve():
            pytest.fail('Connected PostgreSQL is not the runner-owned cluster')
        connection.execute(text(f'CREATE DATABASE "{name}"'))
    admin_url = base + '/' + name
    admin = create_engine(admin_url, poolclass=NullPool)
    monkeypatch.setattr(settings, 'MIGRATION_DATABASE_URL', None)
    monkeypatch.delenv('MIGRATION_DATABASE_URL', raising=False)
    config = Config(str(__import__('pathlib').Path(__file__).resolve().parents[1] / 'alembic.ini'))
    config.set_main_option('sqlalchemy.url', admin_url)
    def upgrade(target='head'):
        command.upgrade(config, target)
    try:
        upgrade(getattr(request, 'param', 'head'))
        with admin.begin() as connection:
            connection.execute(text('ALTER ROLE ap_app_user LOGIN NOSUPERUSER NOBYPASSRLS'))
        app_url = f'postgresql+psycopg://ap_app_user@127.0.0.1:{port}/{name}'
        app = create_engine(app_url, poolclass=NullPool,
            connect_args={'options': '-c statement_timeout=8000 -c lock_timeout=5000'})
        yield dict(admin=admin, app=app, admin_url=admin_url, app_url=app_url, upgrade=upgrade)
        app.dispose()
    finally:
        admin.dispose()
        with control.connect() as connection:
            connection.execute(text(f'DROP DATABASE "{name}" WITH (FORCE)'))
        control.dispose()


@pytest.fixture
def disposable_app_db(monkeypatch, request):
    """Function-scoped database/storage for tests that used application globals.

    Patch imported session factories explicitly; never initialize the configured
    application engine or reuse records from another test.
    """
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool
    from backend.models.domain import Base
    from backend.core import database, pipeline
    from backend.core.config import settings, AppEnv
    from backend.core.storage import TestInMemoryStorageAdapter
    from backend.main import app
    engine = create_engine('sqlite://', poolclass=StaticPool, connect_args={'check_same_thread': False})
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False)
    storage = TestInMemoryStorageAdapter()
    monkeypatch.setattr(settings, 'APP_ENV', AppEnv.TEST)
    monkeypatch.setattr(database, 'SessionLocal', factory)
    monkeypatch.setattr(pipeline, 'SessionLocal', factory)
    monkeypatch.setattr(pipeline, 'storage_adapter', storage)
    if hasattr(request.module, 'SessionLocal'):
        monkeypatch.setattr(request.module, 'SessionLocal', factory)
    if hasattr(request.module, 'storage_adapter'):
        monkeypatch.setattr(request.module, 'storage_adapter', storage)
    def get_test_db():
        with factory() as db:
            try:
                yield db
            except Exception:
                db.rollback()
                raise
    previous = dict(app.dependency_overrides)
    app.dependency_overrides[database.get_db] = get_test_db
    yield factory
    app.dependency_overrides.clear()
    app.dependency_overrides.update(previous)
    engine.dispose()


@pytest.fixture
def evaluation_workspace(disposable_app_db, monkeypatch):
    """Explicit synthetic reference records for legacy database-contract suites.

    Every check is computed by the current matching function. No live providers,
    setup script, pre-existing IDs, or cross-test mutations are required.
    """
    from backend.core.config import settings
    from backend.models.domain import (
        Organisation, User, RoleAssignment, Invoice, InvoiceLine, Vendor, VendorGSTIN,
        WorkOrderSnapshot, WorkOrderLineSnapshot, GoodsReceiptSnapshot,
        GoodsReceiptLineSnapshot, QualityControlSnapshot, ExceptionRecord,
    )
    from backend.api.v1.invoices import reevaluate_match_gates
    monkeypatch.setattr(settings, 'SUPABASE_ISSUER', 'https://offline.example.test/auth/v1')
    monkeypatch.setattr(settings, 'SUPABASE_URL', None)
    monkeypatch.setattr(settings, 'SUPABASE_JWT_SECRET', 'disposable-offline-tests-only-32-character-secret')
    org = 'org_sme_eval'
    identities = [('AP_ASSOCIATE', 'usr_sme_assoc_01'), ('AP_LEAD', 'usr_sme_lead_01'),
                  ('CONTROLLER', 'usr_sme_ctrl_01'), ('AUDITOR', 'usr_sme_audit_01')]
    ids = {}
    with disposable_app_db() as db:
        db.add(Organisation(id=org, name='Disposable evaluation workspace'))
        for role, uid in identities:
            db.add(User(id=uid, org_id=org, email=f'{uid}@example.test', full_name=role))
            db.add(RoleAssignment(id=f'role-{uid}', org_id=org, user_id=uid, role_name=role))
        db.commit()
        def seed(key, number, po, qty, rate, billed_rate=None, receipts=True):
            gstin = f'29TEST{len(ids):04d}A1Z5'
            vendor = f'V{len(ids) + 1:03d}'
            subtotal = Decimal(str(qty)) * Decimal(str(billed_rate or rate))
            tax = subtotal * Decimal('.18')
            inv = Invoice(id=f'test-{key}', org_id=org, source_channel='MANUAL_UPLOAD',
                invoice_number=number, invoice_date=datetime.datetime(2026, 11, 1),
                vendor_name='Disposable supplier', vendor_gstin=gstin, po_reference=po,
                currency='INR', subtotal_amount=subtotal, tax_amount=tax,
                total_amount=subtotal+tax, net_payable_amount=subtotal+tax,
                stage='RECEIVED', decision='NEEDS_REVIEW')
            db.add_all([inv, Vendor(id=f'v-{key}', org_id=org, erp_vendor_code=vendor, legal_name='Disposable supplier'),
                VendorGSTIN(id=f'vg-{key}', org_id=org, vendor_id=f'v-{key}', gstin=gstin, state_code='29', status='ACTIVE'),
                WorkOrderSnapshot(id=f'po-{key}', org_id=org, po_number=po, vendor_code=vendor,
                    total_authorized_amount=1000000, remaining_balance=1000000, currency='INR', status='OPEN'),
                WorkOrderLineSnapshot(id=f'pol-{key}', org_id=org, po_id=f'po-{key}', line_number=1,
                    item_code='ITEM', description='Disposable service', authorized_quantity=qty,
                    contracted_unit_rate=rate, authorized_line_total=qty*rate),
                InvoiceLine(id=f'line-{key}', org_id=org, invoice_id=inv.id, line_number=1,
                    description='Disposable service', billed_quantity=qty,
                    billed_unit_rate=billed_rate or rate, billed_line_total=subtotal)])
            if receipts:
                db.add_all([GoodsReceiptSnapshot(id=f'grn-{key}', org_id=org, grn_number='GRN-26-601' if key == 'clean' else f'GRN-{key}',
                    po_number=po, received_date=datetime.datetime(2026, 10, 1)),
                    GoodsReceiptLineSnapshot(id=f'grnl-{key}', org_id=org, grn_id=f'grn-{key}',
                        po_line_number=1, accepted_quantity=qty, rejected_quantity=0),
                    QualityControlSnapshot(id=f'qc-{key}', org_id=org,
                        grn_number='GRN-26-601' if key == 'clean' else f'GRN-{key}',
                        qc_certificate_number='QC-GRN-26-601' if key == 'clean' else f'QC-{key}', overall_status='ACCEPTED')])
            db.flush()
            reevaluate_match_gates(db, inv, org)
            if key != 'clean':
                db.add(ExceptionRecord(id=f'exc-{key}', org_id=org, invoice_id=inv.id,
                    blocking_gate_number=6, blocking_gate_name='PO Price & Quantity Tolerance',
                    exposure_amount_inr=inv.total_amount, status='OPEN'))
            ids[key] = inv.id
            db.commit()
        seed('clean', 'AP-26-009', 'PO-26-2001', 80, 300)
        seed('incomplete', 'AP-26-001', 'PO-26-1001', 120, 185, receipts=False)
        seed('variance', 'AP-26-011', 'PO-26-3001', 10, 100, billed_rate=135)
        scan = Invoice(id='test-scan', org_id=org, source_channel='MANUAL_UPLOAD',
            invoice_number='UNKNOWN', vendor_name='Unknown', currency='INR', total_amount=0,
            stage='ACTION_REQUIRED', decision='FLAGGED_HITL_REVIEW')
        db.add(scan)
        db.flush()
        reevaluate_match_gates(db, scan, org)
        db.commit()
        ids['scan'] = scan.id
    return ids


@pytest.fixture
def sme_tokens(evaluation_workspace):
    """Signed identities with server-side roles in this test's own workspace."""
    from backend.core.config import settings
    from jose import jwt
    users = {'AP_ASSOCIATE': 'usr_sme_assoc_01', 'AP_LEAD': 'usr_sme_lead_01',
             'CONTROLLER': 'usr_sme_ctrl_01', 'AUDITOR': 'usr_sme_audit_01'}
    return {role: jwt.encode(dict(sub=uid, email=f'{uid}@example.test',
        iss=settings.SUPABASE_ISSUER, aud='authenticated',
        exp=datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=10)),
        settings.SUPABASE_JWT_SECRET, algorithm='HS256') for role, uid in users.items()}


@pytest.fixture
def record_valid_match():
    """Give a state-machine test real tenant PO/vendor/GRN/QC evidence first.

    This fixture is opt-in: negative validation tests must continue exercising
    missing evidence. No production path can synthesize these source records.
    """
    def seed(db, inv, *, line_items=True, quantity=1, description="Disposable service"):
        from backend.models.domain import (
            InvoiceLine, Vendor, VendorGSTIN, WorkOrderSnapshot, WorkOrderLineSnapshot,
            GoodsReceiptSnapshot, GoodsReceiptLineSnapshot, QualityControlSnapshot,
        )
        from backend.api.v1.invoices import reevaluate_match_gates
        from sqlalchemy import select
        suffix = uuid.uuid4().hex[:12]
        org = inv.org_id
        inv.vendor_gstin = inv.vendor_gstin or '29ABCDE1234F1Z5'
        inv.invoice_number = inv.invoice_number or f'INV-{suffix}'
        inv.po_reference = f'PO-{suffix}'
        inv.currency = 'INR'
        inv.tax_amount = inv.tax_amount or Decimal('0')
        subtotal = Decimal(str(inv.total_amount)) - Decimal(str(inv.tax_amount))
        inv.subtotal_amount = subtotal
        vendor = db.scalar(select(Vendor).join(VendorGSTIN,
            (VendorGSTIN.vendor_id == Vendor.id) & (VendorGSTIN.org_id == Vendor.org_id)).where(
            Vendor.org_id == org, VendorGSTIN.gstin == inv.vendor_gstin))
        if not vendor:
            vendor = Vendor(id=f'v-{suffix}', org_id=org, erp_vendor_code=f'V-{suffix}', legal_name='Disposable supplier')
            db.add(vendor)
            db.add(VendorGSTIN(id=f'vg-{suffix}', org_id=org, vendor_id=vendor.id,
                gstin=inv.vendor_gstin, state_code='29', status='ACTIVE'))
        db.add(WorkOrderSnapshot(id=f'po-{suffix}', org_id=org, po_number=inv.po_reference,
            vendor_code=vendor.erp_vendor_code, total_authorized_amount=100000000,
            remaining_balance=100000000, currency='INR', status='OPEN'))
        db.add(WorkOrderLineSnapshot(id=f'pol-{suffix}', org_id=org, po_id=f'po-{suffix}',
            line_number=1, item_code='SERVICE', description=description,
            authorized_quantity=quantity, contracted_unit_rate=subtotal / Decimal(str(quantity)), authorized_line_total=subtotal))
        db.add(GoodsReceiptSnapshot(id=f'grn-{suffix}', org_id=org, grn_number=f'GRN-{suffix}',
            po_number=inv.po_reference, received_date=datetime.datetime(2026, 10, 1)))
        db.add(GoodsReceiptLineSnapshot(id=f'grnl-{suffix}', org_id=org, grn_id=f'grn-{suffix}',
            po_line_number=1, accepted_quantity=quantity, rejected_quantity=0))
        db.add(QualityControlSnapshot(id=f'qc-{suffix}', org_id=org, grn_number=f'GRN-{suffix}',
            qc_certificate_number=f'QC-{suffix}', overall_status='ACCEPTED'))
        if line_items:
            db.add(InvoiceLine(id=f'line-{suffix}', org_id=org, invoice_id=inv.id, line_number=1,
                description=description, billed_quantity=quantity,
                billed_unit_rate=subtotal / Decimal(str(quantity)), billed_line_total=subtotal))
            db.flush()
            assert reevaluate_match_gates(db, inv, org).overall_result == 'PASS'
        db.commit()
    return seed
