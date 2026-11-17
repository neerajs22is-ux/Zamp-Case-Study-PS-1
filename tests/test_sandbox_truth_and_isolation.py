"""Regression checks against disposable in-memory workspaces only."""
import datetime
import hashlib

import pytest
from fastapi import HTTPException

from backend.api.v1 import sandbox
from backend.models.domain import Document, IngestionJob, Invoice
from tests.test_production_inspection import db  # noqa: F401


def test_public_scenario_hash_lookup_never_returns_another_workspace(db):
    scenario = sandbox.GENUINE_SCENARIOS[0]
    with open(sandbox.get_scenario_pdf_path(scenario['pdf_filename']), 'rb') as source:
        digest = hashlib.sha256(source.read()).hexdigest()
    db.add(Invoice(id='foreign-invoice', org_id='b', source_channel='MANUAL_UPLOAD',
                   invoice_number='FOREIGN-PRIVATE', stage='RECEIVED', decision='NEEDS_REVIEW'))
    db.add(Document(id='foreign-document', org_id='b', invoice_id='foreign-invoice',
                    filename='renamed.pdf', mime_type='application/pdf', file_size_bytes=10,
                    sha256_hash=digest, storage_provider='test', storage_key='foreign/private.pdf'))
    db.commit()
    with pytest.raises(HTTPException) as error:
        sandbox.explore_sandbox_scenario(scenario['id'], db)
    assert error.value.status_code == 404


@pytest.mark.parametrize('job_status', ['QUEUED', 'PROCESSING', 'FAILED', 'COMPLETED'])
def test_sandbox_result_reports_latest_real_job_status_and_metadata(db, job_status):
    db.add(Invoice(id='invoice', org_id='a', source_channel='MANUAL_UPLOAD',
                   invoice_number='SYNTHETIC-1', stage='RECEIVED', decision='NEEDS_REVIEW'))
    db.add(Document(id='document', org_id='a', invoice_id='invoice',
                    filename='synthetic.pdf', mime_type='application/pdf', file_size_bytes=123,
                    sha256_hash='a' * 64, storage_provider='test', storage_key='a/synthetic.pdf'))
    db.flush()
    db.add(IngestionJob(id='old-job', org_id='a', document_id='document',
                        idempotency_key='old', source_channel='MANUAL_UPLOAD',
                        status='COMPLETED', created_at=datetime.datetime(2026, 1, 1)))
    db.add(IngestionJob(id='new-job', org_id='a', document_id='document',
                        idempotency_key='new', source_channel='MANUAL_UPLOAD',
                        status=job_status, created_at=datetime.datetime(2026, 1, 2)))
    db.commit()
    result = sandbox._get_invoice_sandbox_view(db, 'invoice', 'a', is_previous_run=True)
    assert result['status'] == job_status
    assert result['job_id'] == 'new-job'
    assert result['document_sha256'] == 'a' * 64
    assert result['file_size_bytes'] == 123
    assert result['page_count'] is None
    assert result['grounding']['tripwire_passed'] is None
    assert result['processing_events'] == []


def test_demo_fixture_without_reference_is_rejected_before_intake(db):
    from fastapi import BackgroundTasks
    from backend.core.auth import AuthenticatedUser, UserRole
    user = AuthenticatedUser(id='demo-user', org_id='org_demo_disposable', email='demo@example.test',
                             name='Demo', role=UserRole.AP_ASSOCIATE, is_provisioned=True)
    with pytest.raises(HTTPException) as error:
        sandbox.run_sandbox_scenario('SCN-01-HAPPY-PATH', BackgroundTasks(), False, user, db)
    assert error.value.status_code == 400
    assert 'reference' in error.value.detail or 'purchase-order' in error.value.detail
    assert not db.query(IngestionJob).count()
