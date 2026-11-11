import datetime
import hashlib
from io import BytesIO

from pypdf import PdfReader
import pypdfium2 as pdfium
from sqlalchemy import select

from backend.core.storage import TestInMemoryStorageAdapter
from backend.models.domain import Document, Invoice, IngestionJob, MatchGateCheck, MatchRun


def test_prepared_demo_real_pdf_and_policy(disposable_app_db, monkeypatch):
    from backend.api.v1.auth import provision_isolated_demo_tenant
    from backend.core import demo_seed
    from backend.core.config import settings
    storage = TestInMemoryStorageAdapter()
    monkeypatch.setattr(demo_seed, 'storage_adapter', storage)
    monkeypatch.setattr(settings, 'SUPABASE_JWT_SECRET', 'test-secret-long-enough-for-this-test')
    with disposable_app_db() as db:
        session = provision_isolated_demo_tenant(db, 'demo-seed-test')
        org = session['user']['org_id']
        invoices = db.scalars(select(Invoice).where(Invoice.org_id == org).order_by(Invoice.id)).all()
        assert len(invoices) == 5
        assert [i.decision for i in invoices] == ['MATCH_CANDIDATE', 'FLAGGED_EXCEPTION', 'FLAGGED_EXCEPTION', 'FLAGGED_HITL_REVIEW', 'REJECTED']
        assert not db.scalars(select(IngestionJob).where(IngestionJob.org_id == org)).all()
        for index, inv in enumerate(invoices, 1):
            doc = db.scalar(select(Document).where(Document.invoice_id == inv.id))
            data = storage.get_file(doc.storage_key)
            assert data.startswith(b'%PDF-') and hashlib.sha256(data).hexdigest() == doc.sha256_hash
            assert len(data) == doc.file_size_bytes and doc.mime_type == 'application/pdf'
            rendered = pdfium.PdfDocument(data)[0].render(scale=1).to_pil()
            assert rendered.width > 0 and rendered.height > 0
            text = ''.join(page.extract_text() for page in PdfReader(BytesIO(data)).pages)
            if index == 4:
                assert not text.strip()
            else:
                assert inv.invoice_number in text and inv.vendor_name in text
                if index <= 3:
                    assert inv.po_reference in text
                    assert f'{inv.total_amount:.2f}' in text
            if index <= 3:
                run = db.scalar(select(MatchRun).where(MatchRun.invoice_id == inv.id))
                gates = db.scalars(select(MatchGateCheck).where(MatchGateCheck.match_run_id == run.id).order_by(MatchGateCheck.gate_number)).all()
                assert len(gates) == 7
                if index == 1:
                    assert all(g.status == 'PASS' for g in gates)
                else:
                    assert gates[5 if index == 2 else 3].status == 'FAIL'
        demo_seed.seed_demo_examples(db, org, session['user']['id'], datetime.datetime.utcnow())
        assert len(db.scalars(select(Invoice).where(Invoice.org_id == org)).all()) == 5
        second = provision_isolated_demo_tenant(db, 'demo-seed-test-2')
        assert second['user']['org_id'] != org
        keys = [d.storage_key for d in db.scalars(select(Document).where(Document.org_id == org)).all()]
        assert all(k.startswith(org + '/') for k in keys)
        assert not set(keys) & {d.storage_key for d in db.scalars(select(Document).where(Document.org_id == second['user']['org_id'])).all()}


def test_demo_upload_quota_and_document_access(disposable_app_db, monkeypatch):
    import asyncio
    from fastapi import BackgroundTasks, HTTPException, UploadFile
    from backend.api.v1 import documents
    from backend.api.v1.auth import provision_isolated_demo_tenant
    from backend.core import demo_seed
    from backend.core.auth import AuthenticatedUser, UserRole
    from backend.core.config import settings
    storage = TestInMemoryStorageAdapter()
    monkeypatch.setattr(demo_seed, 'storage_adapter', storage)
    monkeypatch.setattr(documents, 'storage_adapter', storage)
    monkeypatch.setattr(settings, 'SUPABASE_JWT_SECRET', 'test-secret-long-enough-for-this-test')
    monkeypatch.setenv('ENABLE_BACKGROUND_PIPELINE', 'false')
    with disposable_app_db() as db:
        first = provision_isolated_demo_tenant(db, 'upload-test-1')['user']
        second = provision_isolated_demo_tenant(db, 'upload-test-2')['user']
        def user(info):
            return AuthenticatedUser(id=info['id'], org_id=info['org_id'], email=info['email'],
                                     name=info['name'], role=UserRole.AP_ASSOCIATE, is_provisioned=True)
        owner, other = user(first), user(second)
        doc = db.scalar(select(Document).where(Document.org_id == first['org_id']))
        assert documents.download_document(doc.id, owner, db).body.startswith(b'%PDF-')
        assert documents.get_document_signed_url(doc.id, 300, owner, db)['expires_in'] == 300
        import pytest
        with pytest.raises(HTTPException) as denied:
            documents.get_document_signed_url(doc.id, 300, other, db)
        assert denied.value.status_code == 403
        for n in range(6):
            case = dict(number=5, title='CUSTOM', vendor='Test supplier', invoice=f'CUSTOM-{n}',
                        date='2026-01-01', total=100)
            upload = UploadFile(filename=f'custom-{n}.pdf', file=BytesIO(demo_seed.render_pdf(case)))
            if n < 5:
                result = asyncio.run(documents.upload_document(upload, BackgroundTasks(), owner, db))
                assert result['status'] == 'QUEUED'
                assert storage.get_file(result['storage_key']).startswith(b'%PDF-')
            else:
                with pytest.raises(HTTPException) as limited:
                    asyncio.run(documents.upload_document(upload, BackgroundTasks(), owner, db))
                assert limited.value.status_code == 429


def test_failed_seed_rolls_back_and_cleans_storage(disposable_app_db, monkeypatch):
    import pytest
    from backend.api.v1.auth import provision_isolated_demo_tenant
    from backend.core import demo_seed
    from backend.core.config import settings
    class FailingStorage(TestInMemoryStorageAdapter):
        def save_file(self, *args, **kwargs):
            if len(self._store) == 2:
                raise RuntimeError('simulated storage outage')
            return super().save_file(*args, **kwargs)
    storage = FailingStorage()
    monkeypatch.setattr(demo_seed, 'storage_adapter', storage)
    monkeypatch.setattr(settings, 'SUPABASE_JWT_SECRET', 'test-secret-long-enough-for-this-test')
    with disposable_app_db() as db:
        with pytest.raises(RuntimeError, match='simulated storage outage'):
            provision_isolated_demo_tenant(db, 'failure-test')
        assert not storage._store
        assert not db.scalars(select(Invoice)).all()
        assert not db.scalars(select(Document)).all()
