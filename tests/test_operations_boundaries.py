"""Disposable checks for truthful financial and operational boundaries."""
import pytest
from fastapi import HTTPException
from backend.api.v1 import backup, dashboard, exceptions
from backend.models.domain import ExceptionRecord, User, AuditEvent, RoleAssignment
from tests.test_production_inspection import db, actor, invoice, api_client


def test_foreign_currency_exception_is_visible_but_not_reported_as_inr(db,actor):
    invoice(db,id='usd',currency='USD',stage='ACTION_REQUIRED',total_amount=100,net_payable_amount=100)
    db.add(ExceptionRecord(id='exc-usd',org_id='a',invoice_id='usd',blocking_gate_number=1,blocking_gate_name='Review',exposure_amount_inr=100,status='OPEN'))
    db.commit()
    item=exceptions.list_exceptions(actor,db)['items'][0]
    assert item['exposure_amount_inr'] is None and item['currency']=='USD'
    metrics=dashboard.get_dashboard_metrics(db,actor)
    assert metrics['summary']['blocked_value_inr']==0
    assert metrics['summary']['non_inr_exceptions_excluded']==1
    exposure=dashboard.get_dashboard_exposure(db,actor)
    assert exposure['total_blocked_liability_inr']==0 and exposure['non_inr_invoices_excluded']==1


def test_backup_failure_does_not_expose_internal_exception(db,actor,monkeypatch):
    monkeypatch.setattr(backup,'verify_platform_operator',lambda user:None)
    def fail(**kwargs): raise RuntimeError('sensitive internal diagnostic')
    monkeypatch.setattr(backup,'create_backup_archive',fail)
    with pytest.raises(HTTPException) as exc:
        backup.trigger_backup(prune=False,current_user=actor,db=db)
    assert exc.value.status_code==500 and 'sensitive internal diagnostic' not in exc.value.detail


def test_backup_database_export_fails_closed_on_table_error(caplog):
    from backend.core.backup import BackupError, DatabaseBackupManager
    class BrokenSession:
        def get_bind(self):
            class Bind:
                class dialect:
                    name = 'sqlite'
            return Bind()
        def execute(self, *args, **kwargs):
            raise RuntimeError('private database diagnostic')
    with pytest.raises(BackupError, match='no complete backup'):
        DatabaseBackupManager.export_database_state(BrokenSession())
    assert 'private database diagnostic' not in caplog.text


def test_backup_role_script_preserves_revocation_and_quota_grants():
    from backend.core.backup import DatabaseBackupManager
    sql = DatabaseBackupManager.export_roles()
    assert 'REVOKE UPDATE, DELETE ON TABLE revoked_access_tokens' in sql
    assert 'REVOKE DELETE ON TABLE model_quota_buckets' in sql


def test_logout_revokes_signed_access_token(db, api_client):
    from tests.test_production_inspection import token
    headers = token()
    assert api_client.get('/api/v1/auth/me', headers=headers).status_code == 200
    response = api_client.post('/api/v1/auth/logout', headers=headers)
    assert response.status_code == 200
    assert response.json()['status'] == 'ACCESS_TOKEN_REVOKED'
    assert api_client.get('/api/v1/auth/me', headers=headers).status_code == 401
    assert api_client.get('/api/v1/auth/me', headers=token('other')).status_code == 200


def test_session_store_unavailable_fails_closed(db, api_client, monkeypatch):
    from tests.test_production_inspection import token
    def unavailable(*args, **kwargs):
        raise RuntimeError('private storage error')
    monkeypatch.setattr(db, 'get', unavailable)
    for method, path in [('get', '/api/v1/auth/me'), ('post', '/api/v1/auth/logout')]:
        response = getattr(api_client, method)(path, headers=token())
        assert response.status_code == 503
        assert 'private storage error' not in response.text


def test_logout_write_failure_reports_no_revocation(db, api_client, monkeypatch):
    from tests.test_production_inspection import token
    def fail(): raise RuntimeError('sensitive database failure')
    monkeypatch.setattr(db, 'commit', fail)
    response = api_client.post('/api/v1/auth/logout', headers=token())
    assert response.status_code == 503
    assert 'sensitive' not in response.text


def test_recovery_cutoff_rejects_old_or_missing_iat(db, api_client, monkeypatch):
    import datetime as dt
    from backend.core.config import settings
    from tests.test_production_inspection import token
    cutoff = int(dt.datetime.now(dt.timezone.utc).timestamp()) - 30
    monkeypatch.setattr(settings, 'AUTH_REJECT_TOKENS_ISSUED_BEFORE', cutoff)
    path = '/api/v1/auth/me'
    assert api_client.get(path, headers=token(iat=cutoff - 1)).status_code == 401
    assert api_client.get(path, headers=token()).status_code == 401
    assert api_client.get(path, headers=token(iat=cutoff)).status_code == 200


def test_invitation_email_uses_provider_identity_and_fails_closed(monkeypatch):
    import io, json
    from fastapi.security import HTTPAuthorizationCredentials
    from backend.api.v1.auth import verify_invitation_email
    from backend.core.auth import AuthenticatedUser
    from backend.core.config import settings
    user = AuthenticatedUser(id='u', auth_subject='subject', email='u@example.test', name='U')
    credentials = HTTPAuthorizationCredentials(scheme='Bearer', credentials='fixture-token')
    monkeypatch.setattr(settings, 'IDENTITY_EMAIL_CONFIRMATION_ENFORCED', False)
    with pytest.raises(HTTPException) as unavailable:
        verify_invitation_email(user, credentials)
    assert unavailable.value.status_code == 503
    monkeypatch.setattr(settings, 'IDENTITY_EMAIL_CONFIRMATION_ENFORCED', True)
    monkeypatch.setattr(settings, 'SUPABASE_URL', 'https://identity.example.test')
    monkeypatch.setattr(settings, 'SUPABASE_ANON_KEY', 'public-fixture-key')
    def respond(payload):
        monkeypatch.setattr('urllib.request.urlopen', lambda *a, **k: io.BytesIO(json.dumps(payload).encode()))
    for payload in [dict(id='subject', email='u@example.test', email_confirmed_at=None),
                    dict(id='other', email='u@example.test', email_confirmed_at='2026-01-01'),
                    dict(id='subject', email='other@example.test', email_confirmed_at='2026-01-01')]:
        respond(payload)
        with pytest.raises(HTTPException) as denied:
            verify_invitation_email(user, credentials)
        assert denied.value.status_code == 403
    respond(dict(id='subject', email='u@example.test', email_confirmed_at='2026-01-01'))
    verify_invitation_email(user, credentials)
    def fail(*args, **kwargs): raise OSError('sensitive upstream failure')
    monkeypatch.setattr('urllib.request.urlopen', fail)
    with pytest.raises(HTTPException) as unavailable:
        verify_invitation_email(user, credentials)
    assert unavailable.value.status_code == 503 and 'sensitive' not in unavailable.value.detail


def test_reassign_rejects_foreign_or_inactive_user(db,actor):
    invoice(db)
    db.add_all([User(id='foreign',org_id='b',email='foreign@example.test',full_name='Foreign'),
        User(id='inactive',org_id='a',email='inactive@example.test',full_name='Inactive',is_active=False),
        User(id='valid',org_id='a',email='valid@example.test',full_name='Valid',is_active=True),
        ExceptionRecord(id='exc',org_id='a',invoice_id='inv',blocking_gate_number=1,blocking_gate_name='Review',exposure_amount_inr=1,status='OPEN')])
    db.commit()
    db.add(RoleAssignment(id='role-valid',org_id='a',user_id='valid',role_name='AP_ASSOCIATE'))
    db.commit()
    for uid in ['foreign','inactive','missing']:
        with pytest.raises(HTTPException) as exc:
            exceptions.reassign_exception('exc',exceptions.ReassignPayload(assigned_user_id=uid,reason='Route to review'),actor,db)
        assert exc.value.status_code==404
        assert db.get(ExceptionRecord,'exc').assigned_user_id is None
    result=exceptions.reassign_exception('exc',exceptions.ReassignPayload(assigned_user_id='valid',reason='Route to review'),actor,db)
    assert result['assigned_user_id']=='valid'
    assert db.query(AuditEvent).filter_by(action='EXCEPTION_REASSIGNED').count()==1


def test_corrected_amount_cannot_pass_tax_check_without_reverified_evidence(db):
    from backend.api.v1.invoices import reevaluate_match_gates
    from backend.models.domain import InvoiceLine, MatchGateCheck
    from tests.test_production_inspection import reference_data
    inv = invoice(db)
    reference_data(db)
    db.add(InvoiceLine(id='corrected-line', org_id='a', invoice_id=inv.id, line_number=1,
        description='Widget', billed_quantity=1, billed_unit_rate=100, billed_line_total=100,
        is_corrected=True))
    db.flush()
    match = reevaluate_match_gates(db, inv, 'a')
    gate = db.query(MatchGateCheck).filter_by(match_run_id=match.id, gate_number=5).one()
    assert gate.status == 'FAIL' and 'not been re-grounded' in gate.evidence_notes
    assert match.overall_result == 'FAIL' and inv.decision == 'FLAGGED_EXCEPTION'
