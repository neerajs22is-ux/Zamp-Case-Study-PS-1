"""Focused regression tests for stalled invoice recovery and safe document removal."""

import datetime as dt
import hashlib

import pytest
from sqlalchemy import select

from backend.api.v1 import invoices
from backend.models.domain import AuditEvent, Document, IngestionJob, Invoice
from tests.test_production_inspection import api_client, db, invoice, pdf_bytes, token  # noqa: F401


def _seed_job(db, status="PROCESSING", retry_count=0, lease_offset_seconds=-5):
    invoice(db, stage="RECEIVED", decision="NEEDS_REVIEW", total_amount=None)
    content = pdf_bytes()
    db.add(Document(
        id="doc", org_id="a", invoice_id="inv", filename="invoice.pdf",
        mime_type="application/pdf", file_size_bytes=len(content),
        sha256_hash=hashlib.sha256(content).hexdigest(),
        storage_provider="test", storage_key="workspace-a/invoice.pdf",
    ))
    job = IngestionJob(
        id="job", org_id="a", document_id="doc", idempotency_key="upload-job",
        source_channel="MANUAL_UPLOAD", status=status, retry_count=retry_count,
    )
    if status == "PROCESSING":
        job.lock_token = "worker-token"
        job.lease_expires_at = dt.datetime.utcnow() + dt.timedelta(seconds=lease_offset_seconds)
    db.add(job)
    db.commit()
    return job


def test_retry_recovers_expired_lease_for_the_requested_invoice(
    db, api_client, monkeypatch  # noqa: F811
):
    _seed_job(db)
    # A second stalled invoice must not be touched by a targeted retry.
    db.add(Invoice(id="inv2", org_id="a", source_channel="MANUAL_UPLOAD",
                   stage="RECEIVED", decision="NEEDS_REVIEW"))
    db.add(Document(
        id="doc2", org_id="a", invoice_id="inv2", filename="other.pdf",
        mime_type="application/pdf", file_size_bytes=1, sha256_hash="0" * 64,
        storage_provider="test", storage_key="workspace-a/other.pdf",
    ))
    other = IngestionJob(
        id="other-job", org_id="a", document_id="doc2",
        idempotency_key="other-upload", source_channel="MANUAL_UPLOAD",
        status="PROCESSING", retry_count=0, lock_token="other-token",
        lease_expires_at=dt.datetime.utcnow() - dt.timedelta(minutes=1),
    )
    db.add(other)
    db.commit()
    monkeypatch.setenv("ENABLE_BACKGROUND_PIPELINE", "true")
    monkeypatch.setattr(invoices, "process_document_pipeline_background", lambda *args: None)

    detail = api_client.get("/api/v1/invoices/inv", headers=token())
    assert detail.status_code == 200
    assert detail.json()["invoice"]["job_id"] == "job"
    assert detail.json()["invoice"]["job_lease_expired"] is True

    response = api_client.post("/api/v1/invoices/inv/processing/retry", headers=token())

    assert response.status_code == 202
    assert response.json()["status"] == "PROCESSING"
    job = db.get(IngestionJob, "job")
    db.refresh(job)
    assert job.status == "PROCESSING"
    assert job.retry_count == 1
    assert job.lock_token and job.lock_token != "worker-token"
    assert job.lease_expires_at and job.lease_expires_at > dt.datetime.utcnow()

    db.refresh(other)
    assert other.status == "PROCESSING"
    assert other.lock_token == "other-token"
    assert other.retry_count == 0

    events = db.scalars(select(AuditEvent).where(
        AuditEvent.invoice_id == "inv", AuditEvent.action == "PIPELINE_STAGE",
    ).order_by(AuditEvent.timestamp, AuditEvent.id)).all()
    assert any(e.after_state.get("status") == "INTERRUPTED" for e in events)
    assert any(e.after_state.get("status") == "STARTED" for e in events)

    # A second click must not spawn another worker while the lease is active.
    second = api_client.post("/api/v1/invoices/inv/processing/retry", headers=token())
    assert second.status_code == 202
    assert second.json()["status"] == "ALREADY_PROCESSING"
    assert db.scalar(select(IngestionJob).where(
        IngestionJob.document_id == "doc", IngestionJob.org_id == "a",
    ).order_by(IngestionJob.created_at)) is not None


def test_retry_is_tenant_scoped_and_rejects_completed_work(
    db, api_client  # noqa: F811
):
    _seed_job(db, status="COMPLETED")
    assert api_client.post("/api/v1/invoices/inv/processing/retry", headers=token("other")).status_code == 404
    assert api_client.post("/api/v1/invoices/inv/processing/retry", headers=token()).status_code == 409


def test_failed_job_gets_a_new_bounded_job_and_is_limited(
    db, api_client, monkeypatch  # noqa: F811
):
    _seed_job(db, status="FAILED", retry_count=3)
    db.get(Invoice, "inv").stage = "ACTION_REQUIRED"
    db.get(Invoice, "inv").decision = "FLAGGED_HITL_REVIEW"
    db.commit()
    monkeypatch.setenv("ENABLE_BACKGROUND_PIPELINE", "true")
    monkeypatch.setattr(invoices, "process_document_pipeline_background", lambda *args: None)

    response = api_client.post("/api/v1/invoices/inv/processing/retry", headers=token())
    assert response.status_code == 202
    jobs = db.scalars(select(IngestionJob).where(
        IngestionJob.document_id == "doc", IngestionJob.org_id == "a",
    ).order_by(IngestionJob.created_at, IngestionJob.id)).all()
    assert len(jobs) == 2
    assert jobs[-1].status == "PROCESSING"
    assert jobs[0].status == "FAILED"
    inv = db.get(Invoice, "inv")
    assert (inv.stage, inv.decision) == ("RECEIVED", "NEEDS_REVIEW")

    # The second re-run has now failed. A third job is permitted, a fourth is not.
    jobs[-1].status = "FAILED"
    jobs[-1].lock_token = None
    jobs[-1].lease_expires_at = None
    db.commit()
    third = api_client.post("/api/v1/invoices/inv/processing/retry", headers=token())
    assert third.status_code == 202
    jobs = db.scalars(select(IngestionJob).where(
        IngestionJob.document_id == "doc", IngestionJob.org_id == "a",
    ).order_by(IngestionJob.created_at, IngestionJob.id)).all()
    assert len(jobs) == 3

    jobs[-1].status = "FAILED"
    jobs[-1].lock_token = None
    jobs[-1].lease_expires_at = None
    db.commit()
    limited = api_client.post("/api/v1/invoices/inv/processing/retry", headers=token())
    assert limited.status_code == 409
    assert "Retry limit" in limited.json()["detail"]


def test_soft_delete_fences_active_processing_and_preserves_audit(
    db, api_client, monkeypatch  # noqa: F811
):
    _seed_job(db)
    storage = type("Storage", (), {"delete_file": lambda self, key: pytest.fail("soft delete must not remove evidence")})()
    monkeypatch.setattr("backend.api.v1.documents.storage_adapter", storage)

    response = api_client.delete("/api/v1/documents/doc?reason=Operator%20removed%20duplicate", headers=token())

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "SOFT_DELETED"
    assert body["cancelled_job_ids"] == ["job"]
    doc = db.get(Document, "doc")
    job = db.get(IngestionJob, "job")
    inv = db.get(Invoice, "inv")
    db.refresh(doc)
    db.refresh(job)
    db.refresh(inv)
    assert doc.is_deleted is True
    assert doc.deleted_at is not None
    assert job.status == "FAILED"
    assert job.lock_token is None
    assert job.lease_expires_at is None
    assert "cancelled" in (job.error_message or "").lower()
    assert inv.stage == "ACTION_REQUIRED"
    assert inv.decision == "FLAGGED_HITL_REVIEW"
    assert "processing was cancelled" in inv.decision_reason.lower()

    cancelled = db.scalars(select(AuditEvent).where(
        AuditEvent.invoice_id == "inv",
        AuditEvent.action == "PIPELINE_STAGE",
    )).all()
    assert any(e.after_state.get("status") == "CANCELLED" for e in cancelled)
    deleted = db.scalars(select(AuditEvent).where(
        AuditEvent.invoice_id == "inv",
        AuditEvent.action == "DOCUMENT_SOFT_DELETED",
    )).all()
    assert len(deleted) == 1
    assert deleted[0].after_state["cancelled_job_ids"] == ["job"]

    retry = api_client.post("/api/v1/invoices/inv/processing/retry", headers=token())
    assert retry.status_code == 409
    assert "soft-deleted" in retry.json()["detail"]

    # Idempotent repeat does not fabricate another cancellation or audit event.
    repeat = api_client.delete("/api/v1/documents/doc", headers=token())
    assert repeat.status_code == 200
    assert repeat.json()["status"] == "ALREADY_SOFT_DELETED"
    assert repeat.json()["cancelled_job_ids"] == []
