"""Real migrated PostgreSQL; privileged setup, non-bypass application exercises.

Run via scripts/inspect_postgres.py. All databases belong to that runner's
temporary loopback cluster and are dropped by the fixture, including failures.
"""
import datetime as dt
import hashlib
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from fastapi.testclient import TestClient
from jose import jwt
from sqlalchemy import select, text, func
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from backend.core.auth import get_current_user
from backend.core.config import settings
from backend.core.database import get_db, set_tenant_context
from backend.main import app
from backend.models.domain import (
    Organisation, User, RoleAssignment, AuditEvent, IdentityMembership, UserInvitation,
    Invoice, InvoiceLine, MatchRun, WorkOrderSnapshot, WorkOrderLineSnapshot, Vendor,
    VendorGSTIN, GoodsReceiptSnapshot, GoodsReceiptLineSnapshot, QualityControlSnapshot,
)
from backend.api.v1.invoices import execute_invoice_action, ActionPayload, reevaluate_match_gates
from backend.api.v1.auth import accept_invitation, AcceptInvitationPayload

ISSUER = 'https://disposable.example.test/auth/v1'
SECRET = 'disposable-postgres-test-key-at-least-32-characters'


@pytest.fixture(autouse=True)
def identity_config(monkeypatch):
    monkeypatch.setattr(settings, 'SUPABASE_ISSUER', ISSUER)
    monkeypatch.setattr(settings, 'SUPABASE_URL', None)
    monkeypatch.setattr(settings, 'SUPABASE_JWT_SECRET', SECRET)


def credentials(subject='lead', email=None, **extra):
    claims = dict(sub=subject, email=email or f'{subject}@example.test', iss=ISSUER,
        aud='authenticated', exp=dt.datetime.now(dt.timezone.utc) + dt.timedelta(minutes=10))
    claims.update(extra)
    return HTTPAuthorizationCredentials(scheme='Bearer', credentials=jwt.encode(claims, SECRET, algorithm='HS256'))


def assert_restricted(db):
    row = db.execute(text('SELECT current_user, rolsuper, rolbypassrls FROM pg_roles WHERE rolname=current_user')).one()
    assert tuple(row) == ('ap_app_user', False, False)
    assert not db.scalar(text("SELECT pg_has_role(current_user, 'postgres', 'MEMBER')"))


def test_platform_backup_rejects_rls_filtered_application_session(postgres_database):
    from backend.core.backup import BackupError, DatabaseBackupManager
    with Session(postgres_database['app']) as db:
        assert_restricted(db)
        set_tenant_context(db, 'a')
        with pytest.raises(BackupError, match='no complete backup'):
            DatabaseBackupManager.export_database_state(db)


def test_logout_replay_denied_across_application_connections(postgres_database):
    from backend.api.v1.auth import logout
    with Session(postgres_database['admin']) as db:
        seed_users(db)
    bearer = credentials()
    with Session(postgres_database['app']) as db:
        assert not db.scalar(text("SELECT has_table_privilege(current_user, 'revoked_access_tokens', 'DELETE')"))
        assert not db.scalar(text("SELECT has_table_privilege(current_user, 'revoked_access_tokens', 'UPDATE')"))
        user = get_current_user(credentials=bearer, db=db, requested_org=None)
        assert logout(user, bearer, db)['status'] == 'ACCESS_TOKEN_REVOKED'
    with Session(postgres_database['app']) as db:
        with pytest.raises(HTTPException) as denied:
            get_current_user(credentials=bearer, db=db, requested_org=None)
        assert denied.value.status_code == 401


def test_revocation_cleanup_requires_privilege_and_keeps_recent_rows(postgres_database):
    from backend.models.domain import RevokedAccessToken
    from backend.scripts.prune_revoked_tokens import prune
    now = dt.datetime.utcnow()
    with Session(postgres_database['admin']) as db:
        for key, expires in [('old', now - dt.timedelta(days=2)),
                             ('recent', now - dt.timedelta(hours=1)),
                             ('active', now + dt.timedelta(hours=1))]:
            db.add(RevokedAccessToken(token_hash=key, expires_at=expires))
        db.commit()
    with Session(postgres_database['app']) as db:
        with pytest.raises(DBAPIError):
            prune(db)
        db.rollback()
    with Session(postgres_database['admin']) as db:
        assert prune(db) == 1
        db.commit()
        assert set(db.scalars(select(RevokedAccessToken.token_hash))) == {'recent', 'active'}


def test_model_reservations_are_atomic_and_tenant_isolated(postgres_database, monkeypatch):
    from backend.core.model_quota import reserve_model_attempt, ModelQuotaExceeded
    monkeypatch.setattr(settings, 'MODEL_MAX_ATTEMPTS_PER_TENANT_MINUTE', 3)
    monkeypatch.setattr(settings, 'MODEL_RESERVATION_BUDGET_USD_PER_TENANT_MONTH', 10.0)
    monkeypatch.setattr(settings, 'MANTLE_MAX_DOCUMENT_COST_USD', 0.1)
    with Session(postgres_database['admin']) as db:
        seed_users(db)
    barrier = threading.Barrier(10)
    def attempt():
        with Session(postgres_database['app']) as db:
            set_tenant_context(db, 'a')
            barrier.wait(timeout=10)
            try:
                reserve_model_attempt(db, 'a')
                db.commit()
                return True
            except ModelQuotaExceeded:
                db.rollback()
                return False
    with ThreadPoolExecutor(max_workers=10) as pool:
        assert sum(pool.map(lambda _: attempt(), range(10))) == 3
    with Session(postgres_database['app']) as db:
        set_tenant_context(db, 'b')
        assert not db.scalar(text("SELECT has_table_privilege(current_user, 'model_quota_buckets', 'DELETE')"))
        assert db.execute(text("SELECT count(*) FROM model_quota_buckets WHERE org_id = 'a'")).scalar() == 0
        reserve_model_attempt(db, 'b')
        db.commit()
        assert db.execute(text("SELECT count(*) FROM model_quota_buckets WHERE org_id = 'b'")).scalar() == 2
        with pytest.raises(DBAPIError):
            reserve_model_attempt(db, 'a')
        db.rollback()


def test_monthly_reservation_rolls_back_minute_counter_when_full(postgres_database, monkeypatch):
    from backend.core.model_quota import reserve_model_attempt, ModelQuotaExceeded
    monkeypatch.setattr(settings, 'MODEL_MAX_ATTEMPTS_PER_TENANT_MINUTE', 10)
    monkeypatch.setattr(settings, 'MODEL_RESERVATION_BUDGET_USD_PER_TENANT_MONTH', 0.2)
    monkeypatch.setattr(settings, 'MANTLE_MAX_DOCUMENT_COST_USD', 0.1)
    with Session(postgres_database['admin']) as db:
        seed_users(db)
    with Session(postgres_database['app']) as db:
        set_tenant_context(db, 'a')
        for _ in range(2):
            reserve_model_attempt(db, 'a'); db.commit()
        with pytest.raises(ModelQuotaExceeded):
            reserve_model_attempt(db, 'a')
        db.rollback()
        assert db.execute(text("SELECT used FROM model_quota_buckets WHERE period='minute'")).scalar() == 2


def test_platform_backup_restore_in_disposable_postgres(postgres_database, tmp_path, monkeypatch):
    import uuid
    from sqlalchemy import create_engine
    from sqlalchemy.engine import make_url
    from sqlalchemy.pool import NullPool
    from alembic import command
    from alembic.config import Config
    from backend.core.backup import create_backup_archive, restore_backup_archive, generate_backup_encryption_key, BackupError, DatabaseRestoreError
    from backend.core import backup as backup_module
    from backend.core.storage import TestInMemoryStorageAdapter
    from backend.models.domain import Document
    pg = postgres_database
    # Both databases live in the fixture's verified owned cluster.
    target_name = 'ap_restore_' + uuid.uuid4().hex + '_test'
    control_url = make_url(pg['admin_url']).set(database='postgres')
    control = create_engine(control_url, isolation_level='AUTOCOMMIT', poolclass=NullPool)
    target_url = make_url(pg['admin_url']).set(database=target_name)
    target = None
    with control.connect() as con:
        con.execute(text(f'CREATE DATABASE "{target_name}"'))
    try:
        cfg = Config('alembic.ini')
        cfg.set_main_option('sqlalchemy.url', target_url.render_as_string(hide_password=False))
        command.upgrade(cfg, 'head')
        target = create_engine(target_url, poolclass=NullPool)
        original = TestInMemoryStorageAdapter()
        restored = TestInMemoryStorageAdapter()
        content = b'synthetic private invoice bytes'
        with Session(pg['admin']) as db:
            with pytest.raises(BackupError, match='repeatable-read'):
                create_backup_archive(db, original, backup_dir=str(tmp_path), encryption_key=generate_backup_encryption_key(), prune=False)
        original.save_file(content=content, filename='synthetic.pdf', mime_type='application/pdf', storage_key='a/synthetic.pdf')
        with Session(pg['admin']) as db:
            seed_users(db)
            db.add(Invoice(id='backup-invoice', org_id='a', source_channel='MANUAL_UPLOAD', invoice_number='INV;SYNTHETIC', total_amount=100))
            db.flush()
            db.add(Document(id='backup-doc', org_id='a', invoice_id='backup-invoice', filename='synthetic.pdf', mime_type='application/pdf', file_size_bytes=len(content), sha256_hash=hashlib.sha256(content).hexdigest(), storage_provider='test', storage_key='a/synthetic.pdf'))
            db.add(AuditEvent(id='backup-audit', org_id='a', actor_id='lead', actor_role='AP_LEAD', action='SYNTHETIC_BACKUP_TEST'))
            db.commit()
        snapshot_engine = create_engine(pg['admin_url'], isolation_level='REPEATABLE READ', poolclass=NullPool)
        try:
          with Session(snapshot_engine) as db:
            key = generate_backup_encryption_key()
            result = create_backup_archive(db, original, backup_dir=str(tmp_path), encryption_key=key, prune=False)
            assert result['completion_status'] == 'SUCCESS'
        finally:
            snapshot_engine.dispose()
        with Session(target) as db, monkeypatch.context() as failing:
            def reject_integrity(*args, **kwargs):
                raise DatabaseRestoreError('Synthetic verification failure')
            failing.setattr(backup_module, 'verify_restore_integrity', reject_integrity)
            failed_restore_storage = TestInMemoryStorageAdapter()
            with pytest.raises(DatabaseRestoreError):
                restore_backup_archive(result['archive_path'], key, db, failed_restore_storage, confirm_restore=True)
            assert db.scalar(text('SELECT count(*) FROM organisations')) == 0
            # Storage is a separate system and cannot join the DB transaction.
            assert failed_restore_storage.get_file('a/synthetic.pdf') == content
        with Session(target) as db:
            result = restore_backup_archive(result['archive_path'], key, db, restored, confirm_restore=True)
            assert result['status'] == 'RESTORE_COMPLETE'
            assert db.get(Invoice, 'backup-invoice').invoice_number == 'INV;SYNTHETIC'
            assert db.get(AuditEvent, 'backup-audit').actor_id == 'lead'
            assert restored.get_file('a/synthetic.pdf') == content
            db.execute(text('SET LOCAL session_replication_role = replica'))
            db.execute(text("UPDATE documents SET org_id='b' WHERE id='backup-doc'"))
            db.execute(text('SET LOCAL session_replication_role = origin'))
            with pytest.raises(DatabaseRestoreError):
                backup_module.verify_restore_integrity(db, restored, {'database': {'table_counts': {'audit_events': 1}}, 'objects': []})
            db.rollback()
        app_url = target_url.set(username='ap_app_user')
        app = create_engine(app_url, poolclass=NullPool)
        try:
            with Session(app) as db:
                set_tenant_context(db, 'b')
                assert db.get(Invoice, 'backup-invoice') is None
        finally:
            app.dispose()
    finally:
        if target is not None: target.dispose()
        with control.connect() as con:
            con.execute(text(f'DROP DATABASE "{target_name}" WITH (FORCE)'))
        control.dispose()


def seed_users(db):
    db.add_all([Organisation(id='a', name='Disposable A'), Organisation(id='b', name='Disposable B')])
    db.flush()
    for uid, org, role in [('lead','a','AP_LEAD'), ('controller','a','CONTROLLER'),
                           ('auditor','a','AUDITOR'), ('other','b','AP_LEAD')]:
        db.add(User(id=uid, org_id=org, email=f'{uid}@example.test', full_name=uid, is_active=True))
        db.flush()
        db.add(RoleAssignment(id=f'role-{uid}', user_id=uid, org_id=org, role_name=role))
    db.commit()


def seed_po_and_invoices(db, ids=('one', 'two'), amount=600):
    seed_users(db)
    db.add(Vendor(id='v', org_id='a', erp_vendor_code='V1', legal_name='Disposable supplier'))
    db.flush()
    db.add(VendorGSTIN(id='vg', org_id='a', vendor_id='v', gstin='29ABCDE1234F1Z5', state_code='29', status='ACTIVE'))
    db.add(WorkOrderSnapshot(id='po', org_id='a', po_number='PO1', vendor_code='V1',
        currency='INR', total_authorized_amount=1000, remaining_balance=1000, status='OPEN'))
    db.flush()
    db.add(WorkOrderLineSnapshot(id='pol', org_id='a', po_id='po', line_number=1,
        item_code='ITEM', description='Widget', authorized_quantity=10,
        contracted_unit_rate=100, authorized_line_total=1000))
    db.add(GoodsReceiptSnapshot(id='grn', org_id='a', grn_number='GRN1', po_number='PO1', received_date=dt.datetime(2026, 10, 1)))
    db.flush()
    db.add(GoodsReceiptLineSnapshot(id='grnl', org_id='a', grn_id='grn', po_line_number=1, accepted_quantity=10, rejected_quantity=0))
    db.add(QualityControlSnapshot(id='qc', org_id='a', grn_number='GRN1', qc_certificate_number='QC1', overall_status='ACCEPTED'))
    for key in ids:
        inv = Invoice(id=key, org_id='a', source_channel='MANUAL_UPLOAD', invoice_number=f'INV-{key}',
            po_reference='PO1', vendor_gstin='29ABCDE1234F1Z5', currency='INR',
            subtotal_amount=amount, tax_amount=0, total_amount=amount, net_payable_amount=amount,
            stage='RECEIVED', decision='NEEDS_REVIEW')
        db.add(inv)
        db.flush()
        db.add(InvoiceLine(id=f'line-{key}', org_id='a', invoice_id=key, line_number=1,
            description='Widget', billed_quantity=amount/100, billed_unit_rate=100, billed_line_total=amount))
        db.flush()
        assert reevaluate_match_gates(db, inv, 'a').overall_result == 'PASS'
    db.commit()


@pytest.mark.parametrize('postgres_database', ['009_phase_a_core'], indirect=True)
def test_upgrade_010_011_preserves_existing_identity_roles_and_audit(postgres_database, monkeypatch):
    pg = postgres_database
    with Session(pg['admin']) as db:
        seed_users(db)
        db.add(User(id='no-role', org_id='a', email='no-role@example.test', full_name='No role'))
        db.add(AuditEvent(id='old-audit', org_id='a', actor_id='lead', actor_role='AP_LEAD', action='HISTORICAL_REVIEW'))
        db.add(Invoice(id='old-invoice', org_id='a', source_channel='MANUAL_UPLOAD',
            owner_user_id='lead', invoice_number='HISTORICAL-001', total_amount=100))
        db.commit()
        seed_invitation(db)
        before_users = db.execute(text('SELECT id, org_id, email, full_name, is_active, created_at FROM users ORDER BY id')).all()
        before_roles = db.execute(text('SELECT * FROM role_assignments ORDER BY id')).all()
        before_audit = db.execute(text('SELECT * FROM audit_events ORDER BY id')).all()
        before_invoices = db.execute(text('SELECT * FROM invoices ORDER BY id')).all()
        before_function_acl = db.execute(text("SELECT proowner, proacl::text FROM pg_proc WHERE proname='find_pending_invitation'")).one()
    pg['upgrade']('010_identity_memberships')
    # Current runtime requires 013; verify it fails closed on the old schema,
    # then isolate the older migration's identity assertions from that new gate.
    with Session(pg['app']) as db:
        with pytest.raises(HTTPException) as missing_store:
            get_current_user(credentials(), db, None)
        assert missing_store.value.status_code == 503
    from backend.models.domain import RevokedAccessToken
    original_get = Session.get
    def legacy_schema_get(session, entity, ident, *args, **kwargs):
        if entity is RevokedAccessToken:
            return None
        return original_get(session, entity, ident, *args, **kwargs)
    monkeypatch.setattr(Session, 'get', legacy_schema_get)
    with Session(pg['app']) as db:
        assert_restricted(db)
        legacy = get_current_user(credentials(), db, None)
        assert legacy.id == 'lead' and legacy.org_id == 'a' and legacy.role.value == 'AP_LEAD'
        with pytest.raises(DBAPIError):
            db.execute(text("SELECT * FROM resolve_user_memberships('lead', 'lead@example.test')"))
        db.rollback()
    with Session(pg['admin']) as db:
        db.add(IdentityMembership(id='binding', issuer=ISSUER, subject='provider-subject', user_id='lead', org_id='a', is_active=True))
        db.commit()
    pg['upgrade']('011_require_assigned_roles')
    with Session(pg['admin']) as db:
        assert db.execute(text('SELECT id, org_id, email, full_name, is_active, created_at FROM users ORDER BY id')).all() == before_users
        assert db.execute(text('SELECT * FROM role_assignments ORDER BY id')).all() == before_roles
        assert db.execute(text('SELECT * FROM audit_events ORDER BY id')).all() == before_audit
        assert db.execute(text('SELECT * FROM invoices ORDER BY id')).all() == before_invoices
    with Session(pg['app']) as db:
        actor = get_current_user(credentials('provider-subject', email='lead@example.test'), db, 'a')
        execute_invoice_action('old-invoice', ActionPayload(action='REJECT_INVOICE',
            reason='Post-migration identity attribution verification'), actor, db)
    with Session(pg['admin']) as db:
        event = db.scalar(select(AuditEvent).where(AuditEvent.action == 'REJECT_INVOICE'))
        assert event.actor_id == 'lead' and event.actor_role == 'AP_LEAD'
        assert db.get(Invoice, 'old-invoice').owner_user_id == 'lead'
        assert db.get(IdentityMembership, 'binding').subject == 'provider-subject'
        before_012_audit = db.execute(text('SELECT * FROM audit_events ORDER BY id')).all()
        before_012_invoices = db.execute(text('SELECT * FROM invoices ORDER BY id')).all()
    with Session(pg['app']) as db:
        assert_restricted(db)
        bound = get_current_user(credentials('provider-subject', email='lead@example.test'), db, 'a')
        assert bound.id == 'lead' and bound.auth_subject == 'provider-subject'
        assert db.scalar(select(AuditEvent.actor_id).where(AuditEvent.id == 'old-audit')) == 'lead'
        with pytest.raises(HTTPException) as denied:
            get_current_user(credentials('no-role'), db, None)
        assert denied.value.status_code == 503
    # Reproduce the historical timezone defect on the actual 011 schema before
    # applying 012. No data mutation or downgrade is needed for this comparison.
    lookup = text("SELECT count(*) FROM find_pending_invitation(:hash, 'invitee@example.test')")
    parameters = {'hash':hashlib.sha256(b'disposable-token').hexdigest()}
    with Session(pg['app']) as db:
        assert_restricted(db)
        db.execute(text("SET TIME ZONE 'UTC'"))
        assert db.scalar(lookup, parameters) == 1
        db.execute(text("SET TIME ZONE 'Asia/Calcutta'"))
        assert db.scalar(lookup, parameters) == 0
    pg['upgrade']('012_invitation_utc_expiry')
    with Session(pg['app']) as db:
        assert_restricted(db)
        for zone in ('UTC', 'Asia/Calcutta', 'America/New_York'):
            db.execute(text("SELECT set_config('TimeZone', :zone, true)"), {'zone':zone})
            assert db.scalar(lookup, parameters) == 1
    with Session(pg['admin']) as db:
        assert db.execute(text("SELECT proowner, proacl::text FROM pg_proc WHERE proname='find_pending_invitation'")).one() == before_function_acl
        assert db.execute(text('SELECT * FROM audit_events ORDER BY id')).all() == before_012_audit
        assert db.execute(text('SELECT * FROM invoices ORDER BY id')).all() == before_012_invoices


def test_direct_rls_cross_tenant_reads_writes_and_audit_immutability(postgres_database):
    pg = postgres_database
    with Session(pg['admin']) as db:
        seed_users(db)
        db.add_all([Invoice(id=key, org_id=key, source_channel='MANUAL_UPLOAD') for key in ['a','b']])
        db.add(AuditEvent(id='audit-a', org_id='a', actor_id='lead', actor_role='AP_LEAD', action='REVIEW'))
        db.commit()
    with Session(pg['app']) as db:
        assert_restricted(db)
        assert db.scalars(select(Invoice.id)).all() == []
        user = get_current_user(credentials(), db, 'a')
        assert db.scalars(select(Invoice.id)).all() == ['a']
        assert db.execute(text("UPDATE invoices SET decision='REJECTED' WHERE id='b'")).rowcount == 0
        with pytest.raises(HTTPException) as denied:
            execute_invoice_action('b', ActionPayload(action='REJECT_INVOICE', reason='Cross tenant'), user, db)
        assert denied.value.status_code == 404
        db.rollback()
        set_tenant_context(db, 'a')
        with pytest.raises(DBAPIError):
            db.execute(text("INSERT INTO invoices (id,org_id,source_channel,currency,stage,decision,created_at,updated_at) VALUES ('evil','b','MANUAL_UPLOAD','INR','RECEIVED','NEEDS_REVIEW',now(),now())"))
        db.rollback()
        set_tenant_context(db, 'a')
        with pytest.raises(DBAPIError) as cross_link:
            db.add(InvoiceLine(id='cross-link', org_id='a', invoice_id='b', line_number=1,
                description='Cross-tenant pointer', billed_quantity=1, billed_unit_rate=1, billed_line_total=1))
            db.flush()
        assert cross_link.value.orig.sqlstate == '23503'
        db.rollback()
        for operation in ["UPDATE audit_events SET actor_id='other' WHERE id='audit-a'", "DELETE FROM audit_events WHERE id='audit-a'"]:
            set_tenant_context(db, 'a')
            with pytest.raises(DBAPIError):
                db.execute(text(operation))
            db.rollback()
    with Session(pg['admin']) as db:
        assert db.get(Invoice, 'b').decision == 'NEEDS_REVIEW'
        assert db.get(AuditEvent, 'audit-a').actor_id == 'lead'


@pytest.fixture
def pg_client(postgres_database):
    pg = postgres_database
    def request_db():
        with Session(pg['app']) as db:
            assert_restricted(db)
            try:
                yield db
            except Exception:
                db.rollback()
                raise
    previous = dict(app.dependency_overrides)
    app.dependency_overrides[get_db] = request_db
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()
    app.dependency_overrides.update(previous)


def seed_invitation(db, email='invitee@example.test', target='a', token='disposable-token', expired=False):
    db.add(UserInvitation(id=f'invite-{token}', org_id=target, email=email, role_name='AP_ASSOCIATE',
        token_hash=hashlib.sha256(token.encode()).hexdigest(), invited_by_user_id='lead' if target == 'a' else 'other',
        expires_at=dt.datetime.utcnow() + dt.timedelta(hours=-1 if expired else 1), status='PENDING'))
    db.commit()


def headers(subject='invitee', email=None):
    return {'Authorization': 'Bearer ' + credentials(subject, email).credentials}


def test_invitation_real_signed_identity_wrong_account_expiry_and_replay(postgres_database, pg_client):
    with Session(postgres_database['admin']) as db:
        seed_users(db)
        seed_invitation(db)
        seed_invitation(db, token='expired', expired=True)
    assert pg_client.post('/api/v1/auth/invitations/accept', headers=headers('wrong'), json={'token':'disposable-token'}).status_code == 400
    assert pg_client.post('/api/v1/auth/invitations/accept', headers=headers(), json={'token':'expired'}).status_code == 400
    response = pg_client.post('/api/v1/auth/invitations/accept', headers=headers(), json={'token':'disposable-token'})
    assert response.status_code == 200, response.text
    profile = pg_client.get('/api/v1/auth/me', headers=headers()).json()
    assert profile['id'] == 'invitee' and profile['org_id'] == 'a' and profile['role'] == 'AP_ASSOCIATE'
    assert pg_client.get('/api/v1/inbox', headers={**headers(), 'X-Tenant-ID':'b'}).status_code == 403
    assert pg_client.post('/api/v1/auth/invitations/accept', headers=headers(), json={'token':'disposable-token'}).status_code == 400
    with Session(postgres_database['admin']) as db:
        events = db.scalars(select(AuditEvent).where(AuditEvent.action == 'INVITATION_ACCEPTED')).all()
        assert len(events) == 1 and events[0].actor_id == 'invitee'
        assert db.get(UserInvitation, 'invite-expired').status != 'ACCEPTED'


def test_invitation_cannot_take_over_different_existing_identity(postgres_database, pg_client):
    with Session(postgres_database['admin']) as db:
        seed_users(db)
        seed_invitation(db, email='lead@example.test')
    response = pg_client.post('/api/v1/auth/invitations/accept', headers=headers('different-subject', 'lead@example.test'), json={'token':'disposable-token'})
    assert response.status_code == 409, response.text
    with Session(postgres_database['admin']) as db:
        assert db.get(User, 'lead').is_active
        assert db.get(RoleAssignment, 'role-lead').role_name == 'AP_LEAD'
        assert db.get(UserInvitation, 'invite-disposable-token').status == 'PENDING'


def test_cross_workspace_invitation_preserves_current_identity(postgres_database, pg_client):
    with Session(postgres_database['admin']) as db:
        seed_users(db)
        seed_invitation(db, email='lead@example.test', target='b')
    response = pg_client.post('/api/v1/auth/invitations/accept', headers=headers('lead'), json={'token':'disposable-token'})
    assert response.status_code == 409
    with Session(postgres_database['admin']) as db:
        assert db.get(User, 'lead').org_id == 'a'
        assert db.get(RoleAssignment, 'role-lead').role_name == 'AP_LEAD'
        assert db.get(UserInvitation, 'invite-disposable-token').status == 'PENDING'
        assert db.scalar(select(func.count(User.id)).where(User.email == 'lead@example.test')) == 1


@pytest.mark.parametrize('zone', ['UTC', 'Asia/Calcutta', 'America/New_York'])
def test_invitation_expiry_is_independent_of_session_timezone(postgres_database, zone):
    pg = postgres_database
    with Session(pg['admin']) as db:
        seed_users(db)
        seed_invitation(db)
        seed_invitation(db, token='expired', expired=True)
    with Session(pg['app']) as db:
        assert_restricted(db)
        assert db.scalar(text("SELECT has_function_privilege(current_user,'find_pending_invitation(text,text)','EXECUTE')"))
        assert not db.scalar(text("SELECT EXISTS(SELECT 1 FROM pg_proc p, LATERAL aclexplode(p.proacl) a WHERE p.proname='find_pending_invitation' AND a.grantee=0 AND a.privilege_type='EXECUTE')"))
        db.execute(text("SELECT set_config('TimeZone', :zone, false)"), {'zone':zone})
        actor = get_current_user(credentials('invitee'), db, None)
        with pytest.raises(HTTPException) as denied:
            accept_invitation(AcceptInvitationPayload(token='expired'), actor, db)
        assert denied.value.status_code == 400
        db.rollback()
        db.execute(text("SELECT set_config('TimeZone', :zone, false)"), {'zone':zone})
        assert accept_invitation(AcceptInvitationPayload(token='disposable-token'), actor, db)['status'] == 'SUCCESS'


def test_concurrent_invitation_acceptance_has_one_membership_and_actor(postgres_database):
    pg = postgres_database
    with Session(pg['admin']) as db:
        seed_users(db)
        seed_invitation(db)
    barrier = threading.Barrier(2)
    def accept():
        with Session(pg['app']) as db:
            assert_restricted(db)
            actor = get_current_user(credentials('invitee'), db, None)
            barrier.wait(timeout=5)
            try:
                return accept_invitation(AcceptInvitationPayload(token='disposable-token'), actor, db)['status']
            except HTTPException as exc:
                db.rollback()
                return exc.status_code
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: accept(), range(2)))
    assert results.count('SUCCESS') == 1 and results.count(400) == 1
    with Session(pg['admin']) as db:
        assert db.scalar(select(func.count(RoleAssignment.id)).where(RoleAssignment.user_id == 'invitee')) == 1
        events = db.scalars(select(AuditEvent).where(AuditEvent.action == 'INVITATION_ACCEPTED')).all()
        assert len(events) == 1 and events[0].actor_id == 'invitee'


def test_high_value_approval_keeps_role_and_distinct_actor_checks(postgres_database, pg_client):
    pg = postgres_database
    with Session(pg['admin']) as db:
        seed_po_and_invoices(db, ids=('one',))
        db.get(WorkOrderSnapshot, 'po').total_authorized_amount = 1000000
        db.get(WorkOrderSnapshot, 'po').remaining_balance = 1000000
        db.get(WorkOrderLineSnapshot, 'pol').authorized_quantity = 10000
        db.get(GoodsReceiptLineSnapshot, 'grnl').accepted_quantity = 10000
        inv = db.get(Invoice, 'one')
        inv.total_amount = inv.subtotal_amount = inv.net_payable_amount = 750000
        line = db.get(InvoiceLine, 'line-one')
        line.billed_quantity, line.billed_line_total = 7500, 750000
        db.commit()
    payload = {'action':'APPROVE_AP_REVIEW', 'reason':'Reviewed high-value source evidence'}
    first = pg_client.post('/api/v1/invoices/one/actions', headers=headers('lead'), json=payload)
    assert first.status_code == 200, first.text
    assert first.json()['new_stage'] == 'ACTION_REQUIRED'
    assert pg_client.post('/api/v1/invoices/one/actions', headers=headers('lead'), json=payload).status_code == 400
    # A signed token claim cannot promote a server-side auditor to controller.
    forged_role = {'Authorization':'Bearer '+credentials('auditor', user_role='CONTROLLER').credentials}
    assert pg_client.post('/api/v1/invoices/one/actions', headers=forged_role, json=payload).status_code == 403
    second = pg_client.post('/api/v1/invoices/one/actions', headers=headers('controller'), json=payload)
    assert second.status_code == 200, second.text
    assert second.json()['new_stage'] == 'INTERNAL_APPROVAL_COMPLETE'
    with Session(pg['admin']) as db:
        events = db.scalars(select(AuditEvent).where(AuditEvent.action == 'APPROVE_AP_REVIEW').order_by(AuditEvent.timestamp)).all()
        assert [e.actor_id for e in events] == ['lead','controller']
        assert [e.actor_role for e in events] == ['AP_LEAD','CONTROLLER']


def test_concurrent_po_commitments_cannot_approve_beyond_balance(postgres_database):
    pg = postgres_database
    with Session(pg['admin']) as db:
        seed_po_and_invoices(db)
    locked, proceed = threading.Event(), threading.Event()
    def approve(key, hold=False):
        with Session(pg['app']) as db:
            assert_restricted(db)
            actor = get_current_user(credentials(), db, 'a')
            if hold:
                db.scalar(select(WorkOrderSnapshot).where(WorkOrderSnapshot.id == 'po').with_for_update())
                locked.set()
                assert proceed.wait(5)
            try:
                return execute_invoice_action(key, ActionPayload(action='APPROVE_AP_REVIEW', reason='Concurrent financial review'), actor, db)['status']
            except HTTPException as exc:
                db.rollback()
                return exc.status_code
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(approve, 'one', True)
        assert locked.wait(5)
        second = pool.submit(approve, 'two')
        # Observe actual PostgreSQL lock contention, not just two sequential calls.
        deadline = time.monotonic() + 4
        waiting = False
        try:
            while time.monotonic() < deadline:
                with pg['admin'].connect() as monitor:
                    waiting = monitor.scalar(text("SELECT EXISTS(SELECT 1 FROM pg_stat_activity WHERE datname=current_database() AND usename='ap_app_user' AND wait_event_type='Lock')"))
                if waiting:
                    break
                time.sleep(.02)
        finally:
            proceed.set()
        results = [first.result(timeout=8), second.result(timeout=8)]
    assert waiting, 'Did not observe real PO lock contention'
    assert results == ['SUCCESS', 400]
    with Session(pg['admin']) as db:
        assert db.scalar(select(func.sum(Invoice.total_amount)).where(Invoice.stage == 'INTERNAL_APPROVAL_COMPLETE')) == 600
        assert db.scalar(select(func.count(AuditEvent.id)).where(AuditEvent.action == 'APPROVE_AP_REVIEW')) == 1


def test_concurrent_approvals_cannot_reuse_receipt_quantity(postgres_database):
    pg = postgres_database
    with Session(pg['admin']) as db:
        seed_po_and_invoices(db)
        po=db.get(WorkOrderSnapshot,'po');po.total_authorized_amount=10000;po.remaining_balance=10000
        db.commit()
    barrier=threading.Barrier(2)
    def approve(key):
        with Session(pg['app']) as db:
            assert_restricted(db)
            actor=get_current_user(credentials(),db,'a')
            barrier.wait(timeout=5)
            try:
                return execute_invoice_action(key,ActionPayload(action='APPROVE_AP_REVIEW',reason='Disposable receipt review'),actor,db)['status']
            except HTTPException as exc:
                db.rollback()
                return exc.status_code
    with ThreadPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(approve,('one','two')))
    assert sorted(map(str,results))==['400','SUCCESS']
    with Session(pg['admin']) as db:
        assert db.scalar(select(func.count(Invoice.id)).where(Invoice.stage=='INTERNAL_APPROVAL_COMPLETE'))==1
        assert db.scalar(select(func.count(AuditEvent.id)).where(AuditEvent.action=='APPROVE_AP_REVIEW'))==1


def test_concurrent_same_invoice_approval_is_idempotent(postgres_database):
    pg = postgres_database
    with Session(pg['admin']) as db:
        seed_po_and_invoices(db, ids=('one',), amount=118)
    barrier = threading.Barrier(2)
    def approve():
        with Session(pg['app']) as db:
            assert_restricted(db)
            actor = get_current_user(credentials(), db, 'a')
            barrier.wait(timeout=5)
            return execute_invoice_action('one', ActionPayload(action='APPROVE_AP_REVIEW', reason='Concurrent replay'), actor, db)['status']
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: approve(), range(2)))
    assert sorted(results) == ['ALREADY_APPROVED', 'SUCCESS']
    with Session(pg['admin']) as db:
        assert db.scalar(select(func.count(AuditEvent.id)).where(AuditEvent.action == 'APPROVE_AP_REVIEW')) == 1
