"""Real pipeline transactions with disposable storage and extraction providers."""
import datetime as dt
import hashlib
from types import SimpleNamespace

import pytest
from sqlalchemy import select
from backend.core import pipeline
from backend.api.v1 import documents
from backend.core.processing_events import processing_snapshot
from backend.models.domain import Document, IngestionJob, ExtractionRun, AuditEvent, Invoice
from tests.test_production_inspection import db, api_client, invoice, reference_data, pdf_bytes, token
from engine.hybrid_extractor import HybridProcessingResult
from engine.indian_tax_rules import TaxArithmeticResult, ThreeWayMatchResult
from engine.duplicate_detector import DuplicateCheckResult


def seed(db):
    invoice(db, stage='RECEIVED', decision='NEEDS_REVIEW')
    reference_data(db)
    content = pdf_bytes()
    db.add(Document(id='doc', org_id='a', invoice_id='inv', filename='invoice.pdf', mime_type='application/pdf',
        file_size_bytes=len(content), sha256_hash=hashlib.sha256(content).hexdigest(), storage_provider='test', storage_key='test'))
    db.add(IngestionJob(id='job', org_id='a', document_id='doc', idempotency_key='test', source_channel='MANUAL_UPLOAD', status='QUEUED'))
    db.commit()
    return content


def result():
    return HybridProcessingResult(document_id='doc', filename='invoice.pdf', sha256_hash='0'*64,
        document_type='INVOICE', is_payable_invoice=True, supplier_name='Acme', supplier_gstin='29ABCDE1234F1Z5',
        invoice_number='INV-100', invoice_date='2026-10-01', po_reference='PO-100', currency='INR',
        taxable_value=100, cgst_amount=9, sgst_amount=9, igst_amount=0, total_tax_amount=18, grand_total=118,
        line_items=[dict(description='Widget', quantity=1, unit_price=100, taxable_amount=100)],
        grounding_tripwire_passed=True, unverified_fields=[],
        tax_arithmetic=TaxArithmeticResult(True,18,118,0,0,True),
        three_way_match=ThreeWayMatchResult(True,True,True,True,True,True,match_status='MATCH_CANDIDATE'),
        duplicate_check=DuplicateCheckResult(False), final_decision='MATCH_CANDIDATE',
        decision_reasons=[], audit_notes='disposable', pipeline_mode='hybrid')


def events(db):
    return processing_snapshot(db, 'inv', 'a')['jobs'][0]['events']


def test_real_pipeline_order_and_atomic_outcome(db, monkeypatch):
    content = seed(db)
    monkeypatch.setattr(pipeline, 'storage_adapter', SimpleNamespace(get_file=lambda _: content))
    claimed = pipeline.claim_ingestion_job(db, 'a')
    outcome = pipeline.execute_document_pipeline(claimed[0], claimed[3], db, SimpleNamespace(extract_hybrid=lambda **_: result()))
    assert outcome['status'] == 'COMPLETED'
    rows = events(db)
    assert [(e['stage'], e['status']) for e in rows] == [
        ('RUN','STARTED'), ('DOCUMENT_READ','STARTED'), ('DOCUMENT_READ','SUCCEEDED'),
        ('EXTRACTION','STARTED'), ('EXTRACTION','SUCCEEDED'), ('MATCHING','STARTED'),
        ('MATCHING','SUCCEEDED'), ('OUTCOME','RECORDED')]
    assert [e['sequence'] for e in rows] == list(range(1,9))
    assert all(e['attempt'] == 1 and e['timestamp'].endswith('Z') for e in rows)
    assert rows[-1]['outcome']['decision'] == db.get(Invoice,'inv').decision == 'MATCH_CANDIDATE'
    # Replayed worker cannot append events or process financial results twice.
    assert pipeline.execute_document_pipeline(claimed[0], claimed[3], db)['status'] == 'ABORTED'
    assert len(events(db)) == 8


def test_quota_denial_records_failure_before_extractor(db, monkeypatch):
    from backend.core.config import settings
    content = seed(db)
    monkeypatch.setattr(pipeline, 'storage_adapter', SimpleNamespace(get_file=lambda _: content))
    monkeypatch.setattr(settings, 'MODEL_RESERVATION_BUDGET_USD_PER_TENANT_MONTH', 0.05)
    monkeypatch.setattr(settings, 'MANTLE_MAX_DOCUMENT_COST_USD', 0.1)
    claimed = pipeline.claim_ingestion_job(db, 'a')
    extractor = SimpleNamespace(extract_hybrid=lambda **_: pytest.fail('quota must reject before extraction'))
    outcome = pipeline.execute_document_pipeline(claimed[0], claimed[3], db, extractor)
    assert outcome['status'] == 'FAILED'
    assert events(db)[-1]['stage'] == 'EXTRACTION'
    assert events(db)[-1]['status'] == 'FAILED'
    assert 'reservation' in events(db)[-1]['message'].lower()
    assert not db.scalar(select(ExtractionRun))


@pytest.mark.parametrize('failure', ['storage', 'digest', 'extractor', 'persistence'])
def test_failure_records_actual_boundary_without_success_and_bounded_retries(db, monkeypatch, failure):
    content = seed(db)
    def read(_):
        if failure == 'storage': raise RuntimeError('secret provider response')
        return b'tampered' if failure == 'digest' else content
    def extract(**_):
        if failure == 'extractor': raise RuntimeError('secret provider response')
        value = result()
        if failure == 'persistence': value.invoice_date = None  # Transaction must roll back.
        return value
    monkeypatch.setattr(pipeline, 'storage_adapter', SimpleNamespace(get_file=read))
    for attempt in range(1,4):
        claimed = pipeline.claim_ingestion_job(db,'a')
        assert pipeline.execute_document_pipeline(claimed[0],claimed[3],db,SimpleNamespace(extract_hybrid=extract))['status'] == 'FAILED'
        rows = events(db)
        assert rows[-1]['status'] == 'FAILED'
        assert rows[-1]['attempt'] == attempt
        assert rows[-1]['stage'] == {'storage':'DOCUMENT_READ','digest':'DOCUMENT_READ','extractor':'EXTRACTION','persistence':'MATCHING'}[failure]
        assert not any(e['status'] == 'RECORDED' for e in rows)
        assert 'secret provider response' not in str(rows)
        assert not db.scalar(select(ExtractionRun))
    assert db.get(IngestionJob,'job').status == 'FAILED'
    assert db.get(IngestionJob,'job').lock_token is None
    assert db.get(Invoice,'inv').decision == 'FLAGGED_HITL_REVIEW'
    assert pipeline.claim_ingestion_job(db,'a') is None


def test_lease_recovery_and_stale_worker_fenced(db):
    seed(db)
    claimed = pipeline.claim_ingestion_job(db,'a')
    job = db.get(IngestionJob,'job')
    job.lease_expires_at = dt.datetime.utcnow() - dt.timedelta(seconds=1)
    db.commit()
    assert not pipeline._checkpoint('job',claimed[3],'a','EXTRACTION','SUCCEEDED','stale',db)
    assert pipeline.recover_expired_jobs(db,'a') == 1
    assert events(db)[-1]['status'] == 'INTERRUPTED'
    assert events(db)[-1]['attempt'] == 1
    pipeline.claim_ingestion_job(db,'a')
    assert events(db)[-1]['attempt'] == 2
    assert [e['sequence'] for e in events(db)] == [1,2,3]


def test_authenticated_snapshot_legacy_and_cross_tenant_denial(db, api_client):
    seed(db)
    response = api_client.get('/api/v1/invoices/inv/processing',headers=token('auditor'))
    assert response.status_code == 200
    assert response.json()['jobs'][0]['events'] == []  # No synthetic backfill.
    assert api_client.get('/api/v1/invoices/inv/processing',headers=token('other')).status_code == 404
    assert api_client.get('/api/v1/invoices/inv/processing').status_code == 401
    pipeline.claim_ingestion_job(db,'a')
    first = api_client.get('/api/v1/invoices/inv/processing',headers=token()).json()
    assert first == api_client.get('/api/v1/invoices/inv/processing',headers=token()).json()
    assert 'lock_token' not in str(first) and 'storage_key' not in str(first)
    invoice(db,id='old')
    assert api_client.get('/api/v1/invoices/old/processing',headers=token()).json()['jobs'] == []


def test_authenticated_upload_records_intake_and_real_actor(db, api_client, monkeypatch):
    monkeypatch.setenv("ENABLE_BACKGROUND_PIPELINE", "false")
    monkeypatch.setattr(documents, 'storage_adapter', SimpleNamespace(save_file=lambda **kw: {
        'storage_provider':'test', 'storage_key':kw['storage_key']}))
    response = api_client.post('/api/v1/documents/upload',headers=token(),files={'file':('invoice.pdf',pdf_bytes(),'application/pdf')})
    assert response.status_code in (200,201)
    inv_id = response.json()['invoice_id']
    snapshot = api_client.get(f'/api/v1/invoices/{inv_id}/processing',headers=token()).json()
    assert [(e['stage'],e['status'],e['attempt']) for e in snapshot['jobs'][0]['events']] == [('INTAKE','QUEUED',0)]
    audits = db.scalars(select(AuditEvent).where(AuditEvent.invoice_id == inv_id)).all()
    upload_audit = next((a for a in audits if a.action == 'DOCUMENT_UPLOADED'), None)
    assert upload_audit is not None
    assert (upload_audit.actor_id, upload_audit.actor_role, upload_audit.action) == ('lead', 'AP_LEAD', 'DOCUMENT_UPLOADED')


def test_managed_pipeline_sessions_release_transactions_around_provider(disposable_app_db, monkeypatch):
    from sqlalchemy import event
    # The background path opens its own sessions, unlike direct-handler unit tests.
    with disposable_app_db() as db:
        from backend.models.domain import Organisation
        db.add_all([Organisation(id='a',name='A'),Organisation(id='b',name='B')]); db.commit()
        content = seed(db)
        claimed = pipeline.claim_ingestion_job(db,'a')
    provider_calls = []
    connections = []
    event.listen(disposable_app_db.kw['bind'], 'checkout', lambda *args: connections.append(True))
    event.listen(disposable_app_db.kw['bind'], 'checkin', lambda *args: connections.pop())
    def read(_):
        assert not connections, 'Storage must run without a checked-out DB connection'
        return content
    def extract(**_):
        assert not connections, 'Extraction must run without a checked-out DB connection'
        with disposable_app_db() as db:
            rows = events(db)
            assert rows[-1]['stage'] == 'EXTRACTION' and rows[-1]['status'] == 'STARTED'
            provider_calls.append(True)
        return result()
    monkeypatch.setattr(pipeline,'storage_adapter',SimpleNamespace(get_file=read))
    assert pipeline.execute_document_pipeline(claimed[0],claimed[3],extractor=SimpleNamespace(extract_hybrid=extract),org_id='a')['status'] == 'COMPLETED'
    assert provider_calls == [True]
    with disposable_app_db() as db: assert events(db)[-1]['status'] == 'RECORDED'
