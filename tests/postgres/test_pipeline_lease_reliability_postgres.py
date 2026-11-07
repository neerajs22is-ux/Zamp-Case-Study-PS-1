"""Slow providers and concurrent recovery on a migrated, non-bypass database."""
import datetime as dt
import threading
import time
import subprocess
import sys
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import pytest
from sqlalchemy import select, func, text
from sqlalchemy.orm import Session, sessionmaker
from backend.core import pipeline
from backend.core.config import settings
from backend.core.database import set_tenant_context
from backend.core.processing_events import processing_snapshot, lease_now
from backend.models.domain import IngestionJob, AuditEvent, ExtractionRun, InvoiceLine, Invoice
from backend.api.v1.invoices import execute_invoice_action, ActionPayload
from backend.core.auth import AuthenticatedUser, UserRole
from tests.test_processing_events import seed, result
from tests.postgres.test_migrations_and_financial_concurrency import seed_users


def wait_for(predicate, seconds=8):
    deadline = time.monotonic()+seconds
    while time.monotonic() < deadline:
        if predicate(): return
        time.sleep(.03)
    pytest.fail('Disposable worker did not reach the expected boundary')


@pytest.fixture
def work(postgres_database, monkeypatch):
    pg = postgres_database
    with Session(pg['admin']) as db:
        seed_users(db)
        content = seed(db)
    monkeypatch.setattr(pipeline,'SessionLocal',sessionmaker(bind=pg['app'],autoflush=False))
    monkeypatch.setattr(pipeline,'JOB_LEASE_SECONDS',2)
    monkeypatch.setattr(pipeline,'storage_adapter',SimpleNamespace(get_file=lambda _: content))
    return pg,content


def claim(pg, org='a'):
    with Session(pg['app']) as db:
        set_tenant_context(db,org)
        return pipeline.claim_ingestion_job(db,org,lease_seconds=2)


def snapshot(pg):
    with Session(pg['app']) as db:
        set_tenant_context(db,'a')
        return processing_snapshot(db,'inv','a')['jobs'][0]


def expired(pg):
    with Session(pg['app']) as db:
        set_tenant_context(db,'a')
        return db.get(IngestionJob,'job').lease_expires_at <= lease_now(db)


def assert_one_result_and_approval(pg):
    with Session(pg['app']) as db:
        set_tenant_context(db,'a')
        assert db.scalar(select(func.count()).select_from(ExtractionRun)) == 1
        assert db.scalar(select(func.count()).select_from(InvoiceLine)) == 1
        assert db.scalar(select(func.count()).select_from(AuditEvent).where(AuditEvent.action=='DOCUMENT_PROCESSED')) == 1
        assert len([e for e in snapshot(pg)['events'] if e['status']=='RECORDED']) == 1
        actor = AuthenticatedUser(id='lead',org_id='a',email='lead@example.test',name='Lead',role=UserRole.AP_LEAD,is_provisioned=True)
        payload = ActionPayload(action='APPROVE_AP_REVIEW',reason='Disposable evidence checked')
        assert execute_invoice_action('inv',payload,actor,db)['new_stage'] == 'INTERNAL_APPROVAL_COMPLETE'
        assert execute_invoice_action('inv',payload,actor,db)['status'] == 'ALREADY_APPROVED'
        assert db.scalar(select(func.count()).select_from(AuditEvent).where(AuditEvent.action=='APPROVE_AP_REVIEW')) == 1
        assert db.scalar(select(func.sum(Invoice.net_payable_amount)).where(Invoice.stage=='INTERNAL_APPROVAL_COMPLETE')) == 118


@pytest.mark.parametrize('slow_stage',['storage','extraction'])
def test_slow_provider_keeps_lease_without_claiming_stage_progress(work,monkeypatch,slow_stage):
    pg,content = work
    claimed = claim(pg)
    entered,release = threading.Event(),threading.Event()
    original_expiry = snapshot(pg)['lease_expires_at']
    def wait():
        entered.set()
        assert release.wait(12)
    def read(_):
        if slow_stage=='storage': wait()
        return content
    def extract(**_):
        if slow_stage=='extraction': wait()
        return result()
    monkeypatch.setattr(pipeline,'storage_adapter',SimpleNamespace(get_file=read))
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(pipeline.execute_document_pipeline,'job',claimed[3],extractor=SimpleNamespace(extract_hybrid=extract),org_id='a')
        try:
            assert entered.wait(5)
            wait_for(lambda: any(e['stage']=='LEASE' for e in snapshot(pg)['events']))
            # Provider remains blocked past the original lease, not just past one heartbeat.
            wait_for(lambda: dt.datetime.now(dt.timezone.utc) > dt.datetime.fromisoformat(original_expiry))
            assert not expired(pg)
            assert claim(pg) is None
            rows = snapshot(pg)['events']
            assert not any(e['stage']==('DOCUMENT_READ' if slow_stage=='storage' else 'EXTRACTION') and e['status']=='SUCCEEDED' for e in rows)
        finally:
            release.set()
        assert future.result(timeout=8)['status']=='COMPLETED'
    assert_one_result_and_approval(pg)


@pytest.mark.parametrize('loss',['stopped_worker','budget','renewal_error'])
def test_late_provider_result_discarded_after_recovery(work,monkeypatch,loss):
    pg,_ = work
    if loss=='budget': monkeypatch.setattr(settings,'PIPELINE_PROVIDER_BUDGET_SECONDS',.8)
    real_keeper = pipeline._ProviderLease
    keepers = []
    def capture(*args):
        keeper = real_keeper(*args); keepers.append(keeper); return keeper
    monkeypatch.setattr(pipeline,'_ProviderLease',capture)
    entered,release = threading.Event(),threading.Event()
    def provider(**_):
        value = result()  # Provider may have finished even though response delivery is interrupted.
        entered.set()
        assert release.wait(12)
        return value
    old = claim(pg)
    with ThreadPoolExecutor(max_workers=3) as pool:
        future = pool.submit(pipeline.execute_document_pipeline,'job',old[3],extractor=SimpleNamespace(extract_hybrid=provider),org_id='a')
        try:
            assert entered.wait(5)
            if loss=='stopped_worker': keepers[0].stop()
            elif loss=='renewal_error':
                def fail(*args): raise RuntimeError('Disposable DB outage')
                monkeypatch.setattr(keepers[0],'_renew',fail)
                wait_for(lambda: keepers[0].lost.is_set())
            else:
                wait_for(lambda: any(e['status']=='RENEWAL_STOPPED' for e in snapshot(pg)['events']))
                monkeypatch.setattr(settings,'PIPELINE_PROVIDER_BUDGET_SECONDS',900)
            wait_for(lambda: expired(pg))
            barrier = threading.Barrier(2)
            def recover(): barrier.wait(timeout=3); return claim(pg)
            attempts = [pool.submit(recover) for _ in range(2)]
            claims = [f.result(timeout=5) for f in attempts]
            assert sum(value is not None for value in claims)==1
            new = next(value for value in claims if value)
            assert new[3] != old[3]
            rows = snapshot(pg)['events']
            interrupted = [e for e in rows if e['status']=='INTERRUPTED']
            assert len(interrupted)==1 and interrupted[0]['attempt']==1
            assert 'unknown' in interrupted[0]['message']
            assert pipeline.execute_document_pipeline('job',new[3],extractor=SimpleNamespace(extract_hybrid=lambda **_:result()),org_id='a')['status']=='COMPLETED'
        finally:
            release.set()
        assert future.result(timeout=8)['status']=='ABORTED'
    rows = snapshot(pg)['events']
    assert rows[-1]['attempt']==2 and rows[-1]['status']=='RECORDED'
    assert_one_result_and_approval(pg)


def test_renewal_cannot_resurrect_lease_after_waiting_for_row_lock(work):
    pg,_ = work
    old = claim(pg)
    with Session(pg['app']) as holder, ThreadPoolExecutor(max_workers=1) as pool:
        set_tenant_context(holder,'a')
        job = holder.scalar(select(IngestionJob).where(IngestionJob.id=='job').with_for_update())
        entered = threading.Event()
        def renew():
            with Session(pg['app']) as db:
                entered.set()
                return pipeline.renew_job_lease(db,'job',old[3],org_id='a')
        future = pool.submit(renew)
        assert entered.wait(3)
        def waiting_on_lock():
            with Session(pg['admin']) as monitor:
                return monitor.scalar(text("SELECT count(*) FROM pg_stat_activity WHERE datname=current_database() AND wait_event_type='Lock' AND query LIKE '%ingestion_jobs%'")) > 0
        wait_for(waiting_on_lock,seconds=4)
        # The waiting query sees a now-expired committed row after obtaining its lock.
        job.lease_expires_at = lease_now(holder)-dt.timedelta(seconds=1)
        holder.commit()
        assert future.result(timeout=5) is False
    assert expired(pg)


def test_renewal_and_recovery_cannot_cross_tenant(work):
    pg,_ = work
    old = claim(pg)
    with Session(pg['app']) as db:
        set_tenant_context(db,'b')
        assert not pipeline.renew_job_lease(db,'job',old[3],org_id='b')
        assert pipeline.recover_expired_jobs(db,'b') == 0
        assert processing_snapshot(db,'inv','b')['jobs']==[]
    assert snapshot(pg)['retry_count']==0


def test_process_termination_recovers_without_cleanup_or_duplicate_result(work,tmp_path):
    pg,content = work
    with Session(pg['app']) as db:
        set_tenant_context(db,'a')
        old = pipeline.claim_ingestion_job(db,'a',lease_seconds=5)
    marker,content_file = tmp_path/'provider-entered', tmp_path/'invoice.pdf'
    content_file.write_bytes(content)
    script = Path(__file__).resolve().parents[1]/'helpers'/'disposable_invoice_worker.py'
    # This child has only disposable DB credentials and a stubbed provider; no server.
    log = (tmp_path/'child.log').open('w+')
    process = subprocess.Popen([sys.executable,str(script),pg['app_url'],old[3],str(marker),str(content_file)],
        stdout=log,stderr=subprocess.STDOUT,
        creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    try:
        def ready():
            if process.poll() is not None:
                log.seek(0)
                pytest.fail(f'Disposable worker exited early: {log.read()}')
            return marker.exists()
        wait_for(ready,seconds=8)
        wait_for(lambda: any(e['status']=='RENEWED' for e in snapshot(pg)['events']))
        process.terminate()
        process.wait(timeout=5)
        wait_for(lambda: expired(pg))
        new = claim(pg)
        assert new and new[3] != old[3]
        assert snapshot(pg)['retry_count']==1
        assert pipeline.execute_document_pipeline('job',new[3],extractor=SimpleNamespace(extract_hybrid=lambda **_:result()),org_id='a')['status']=='COMPLETED'
        assert_one_result_and_approval(pg)
    finally:
        if process.poll() is None:
            process.terminate()
            process.wait(timeout=5)
        log.close()


def test_gmail_intake_checkpoint_commits_under_application_role(work,monkeypatch):
    import base64
    from backend.core import gmail
    from backend.models.domain import GmailAccount
    pg,content = work
    detail = {'payload':{'headers':[{'name':'From','value':'Acme <billing@example.test>'}],
        'parts':[{'filename':'gmail.pdf','mimeType':'application/pdf',
            'body':{'data':base64.urlsafe_b64encode(content+b'\n% disposable Gmail fixture\n').decode()}}]}}
    monkeypatch.setattr(gmail,'get_message_detail',lambda *args:detail)
    monkeypatch.setattr(gmail,'storage_adapter',SimpleNamespace(save_file=lambda **kw:{'storage_provider':'test','storage_key':kw['storage_key']}))
    with Session(pg['app']) as db:
        set_tenant_context(db,'a')
        account = GmailAccount(id='mail',org_id='a',mailbox_address='ap@example.test',oauth_status='AUTHORIZED',encrypted_refresh_token='disposable')
        db.add(account); db.commit()
        accepted = gmail.process_single_message_ingestion(db,account,'disposable-token','message-one','lead')
        assert len(accepted['ingested'])==1
        db.commit()
        inv_id = accepted['ingested'][0]['invoice_id']
        run = processing_snapshot(db,inv_id,'a')['jobs'][0]
        assert [(e['sequence'],e['stage'],e['status']) for e in run['events']] == [(1,'INTAKE','QUEUED')]
        audit = db.scalar(select(AuditEvent).where(AuditEvent.invoice_id==inv_id))
        assert (audit.action,audit.actor_id,audit.actor_role)==('GMAIL_INVOICE_INGESTED','lead','SYSTEM_ADMIN')
        set_tenant_context(db,'b')
        assert processing_snapshot(db,inv_id,'b')['jobs']==[]
