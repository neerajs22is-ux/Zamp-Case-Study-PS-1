"""Ordered durable events through the non-bypass app role, on actual migrations."""
import datetime as dt
from concurrent.futures import ThreadPoolExecutor
import threading

import pytest
from sqlalchemy import select, text
from sqlalchemy.orm import Session
from sqlalchemy.exc import DBAPIError
from backend.core.database import set_tenant_context
from backend.core.processing_events import append_checkpoint, processing_snapshot
from backend.core.pipeline import _checkpoint, claim_ingestion_job, recover_expired_jobs
from backend.models.domain import Organisation, Invoice, Document, IngestionJob, AuditEvent


def test_postgres_event_lock_order_rls_and_failure_recovery(postgres_database):
    pg = postgres_database
    with Session(pg['admin']) as db:
        db.add_all([Organisation(id='a',name='A'),Organisation(id='b',name='B')]); db.flush()
        db.add(Invoice(id='inv',org_id='a',source_channel='MANUAL_UPLOAD',stage='RECEIVED',decision='NEEDS_REVIEW')); db.flush()
        db.add(Document(id='doc',org_id='a',invoice_id='inv',filename='test.pdf',mime_type='application/pdf',file_size_bytes=1,
            sha256_hash='0'*64,storage_provider='test',storage_key='private')); db.flush()
        db.add(IngestionJob(id='job',org_id='a',document_id='doc',idempotency_key='unique',source_channel='MANUAL_UPLOAD',status='QUEUED')); db.commit()
    with Session(pg['app']) as db:
        set_tenant_context(db,'a')
        assert tuple(db.execute(text('SELECT rolsuper,rolbypassrls FROM pg_roles WHERE rolname=current_user')).one()) == (False,False)
        claimed = claim_ingestion_job(db,'a')
    barrier = threading.Barrier(2)
    def worker(number):
        barrier.wait(timeout=5)
        with Session(pg['app']) as db:
            return _checkpoint('job',claimed[3],'a','EXTRACTION','STARTED',f'Disposable concurrent checkpoint {number}',db)
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert all(pool.map(worker,[1,2]))
    with Session(pg['app']) as db:
        set_tenant_context(db,'a')
        snapshot = processing_snapshot(db,'inv','a')
        assert [e['sequence'] for e in snapshot['jobs'][0]['events']] == [1,2,3]
        job = db.get(IngestionJob,'job')
        job.lease_expires_at = dt.datetime.utcnow()-dt.timedelta(seconds=1); db.commit()
        assert recover_expired_jobs(db,'a') == 1
        rows = processing_snapshot(db,'inv','a')['jobs'][0]['events']
        assert rows[-1]['status'] == 'INTERRUPTED'
        assert rows[-1]['attempt'] == 1
        assert not _checkpoint('job',claimed[3],'a','OUTCOME','RECORDED','stale worker',db)
        claimed = claim_ingestion_job(db,'a')
        assert _checkpoint('job',claimed[3],'a','DOCUMENT_READ','FAILED','Disposable failure',db,failure=True)
        rows = processing_snapshot(db,'inv','a')['jobs'][0]['events']
        assert rows[-1]['attempt'] == 2 and rows[-1]['status'] == 'FAILED'
        assert [e['sequence'] for e in rows] == list(range(1,7))
        assert not any(e['status'] == 'RECORDED' for e in rows)
    with Session(pg['app']) as db:
        set_tenant_context(db,'b')
        assert processing_snapshot(db,'inv','a')['jobs'] == []
        assert db.scalars(select(AuditEvent)).all() == []
        db.add(AuditEvent(id='forged',org_id='a',invoice_id='inv',actor_id='other',actor_role='AP_LEAD',action='PIPELINE_STAGE'))
        with pytest.raises(DBAPIError): db.commit()
        db.rollback()
    with Session(pg['app']) as db:
        set_tenant_context(db,'a')
        with pytest.raises(DBAPIError):
            db.execute(text("UPDATE audit_events SET reason='tampered' WHERE org_id='a'"))
        db.rollback()
