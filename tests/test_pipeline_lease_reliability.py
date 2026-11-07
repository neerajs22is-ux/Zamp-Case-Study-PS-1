"""Lease regression tests; providers and databases are disposable."""
import datetime as dt
import pytest
from backend.core import pipeline
from backend.models.domain import IngestionJob
from tests.test_processing_events import seed
from tests.test_production_inspection import db


def test_expired_lease_cannot_be_resurrected(db):
    seed(db)
    claimed = pipeline.claim_ingestion_job(db,'a')
    job = db.get(IngestionJob,'job')
    job.lease_expires_at = dt.datetime.utcnow()-dt.timedelta(seconds=1)
    db.commit()
    assert not pipeline.renew_job_lease(db,'job',claimed[3])
    db.refresh(job)
    assert job.lease_expires_at < dt.datetime.utcnow()


@pytest.mark.parametrize('org,token', [('b',None),('a','wrong-token')])
def test_renewal_requires_tenant_and_current_token(db,org,token):
    seed(db)
    claimed = pipeline.claim_ingestion_job(db,'a')
    before = db.get(IngestionJob,'job').lease_expires_at
    assert not pipeline.renew_job_lease(db,'job',token or claimed[3],org_id=org)
    db.refresh(db.get(IngestionJob,'job'))
    assert db.get(IngestionJob,'job').lease_expires_at == before


def test_initial_renewal_failure_prevents_provider_call(db,monkeypatch):
    seed(db)
    claimed = pipeline.claim_ingestion_job(db,'a')
    def fail(*args,**kwargs): raise RuntimeError('Disposable unavailable database')
    monkeypatch.setattr(pipeline,'renew_job_lease',fail)
    from types import SimpleNamespace
    monkeypatch.setattr(pipeline,'storage_adapter',SimpleNamespace(get_file=lambda _: pytest.fail('Provider must not start without ownership')))
    assert pipeline.execute_document_pipeline('job',claimed[3],db_session=db)['status']=='ABORTED'
