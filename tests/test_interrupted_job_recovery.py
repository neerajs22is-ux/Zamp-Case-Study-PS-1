"""Verification of durable background-job lease recovery, worker fencing, and retry limits.

Tests:
1. Interrupted worker with expired lease is automatically re-queued when retry_count < max_retries.
2. Interrupted worker exceeding max_retries transitions to FAILED, flagging the invoice.
3. Stale worker attempting to renew or commit after lease expiry is fenced.
4. Tenant isolation: recover_expired_jobs respects tenant boundaries when org_id is supplied.
"""

from __future__ import annotations

import datetime as dt
import uuid
from decimal import Decimal
import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.core import pipeline
from backend.core.database import set_tenant_context
from backend.core.processing_events import lease_now, processing_snapshot
from backend.models.domain import (
    Document, IngestionJob, Invoice, Organisation, User
)


def seed_job_fixture(db: Session, org_id: str = "org_recovery_test", job_id: str = "job_rec_01"):
    """Helper to seed a test tenant, document, invoice, and ingestion job."""
    set_tenant_context(db, org_id)

    org = db.scalar(select(Organisation).where(Organisation.id == org_id))
    if not org:
        org = Organisation(id=org_id, name=f"Recovery Test Org {org_id}")
        db.add(org)

    user = db.scalar(select(User).where(User.id == f"usr_{org_id}"))
    if not user:
        user = User(
            id=f"usr_{org_id}",
            org_id=org_id,
            email=f"worker@{org_id}.com",
            full_name="Worker User",
            is_active=True,
        )
        db.add(user)

    inv = Invoice(
        id=f"inv_{job_id}",
        org_id=org_id,
        source_channel="MANUAL_UPLOAD",
        stage="RECEIVED",
        decision="NEEDS_REVIEW",
        total_amount=Decimal("1000.00"),
    )
    db.add(inv)

    doc = Document(
        id=f"doc_{job_id}",
        org_id=org_id,
        invoice_id=inv.id,
        filename="test_invoice.pdf",
        mime_type="application/pdf",
        file_size_bytes=1024,
        sha256_hash=uuid.uuid4().hex,
        storage_provider="test",
        storage_key=f"{org_id}/test_invoice.pdf",
    )
    db.add(doc)

    job = IngestionJob(
        id=job_id,
        org_id=org_id,
        document_id=doc.id,
        idempotency_key=f"idem_{job_id}",
        source_channel="MANUAL_UPLOAD",
        status="QUEUED",
        retry_count=0,
    )
    db.add(job)
    db.commit()
    return job, inv, doc


def test_interrupted_job_lease_expiry_requeues_when_under_max_retries(disposable_app_db):
    """When a worker crashes or abandons a job, lease expiry re-queues it for retry."""
    with disposable_app_db() as db:
        job, inv, doc = seed_job_fixture(db, "org_test_retry", "job_retry_1")

        # 1. Claim job to PROCESSING with active lease
        claimed = pipeline.claim_ingestion_job(db, org_id="org_test_retry", lease_seconds=10)
        assert claimed is not None
        job_id, org_id, doc_id, lock_token = claimed

        claimed_job = db.get(IngestionJob, job_id)
        assert claimed_job.status == "PROCESSING"
        assert claimed_job.lock_token == lock_token

        # 2. Simulate worker crash: lease expires in past
        claimed_job.lease_expires_at = dt.datetime.utcnow() - dt.timedelta(seconds=5)
        db.commit()

        # 3. Trigger recovery
        recovered_count = pipeline.recover_expired_jobs(db, org_id="org_test_retry", max_retries=3)
        assert recovered_count == 1

        # 4. Verify job is re-queued with incremented retry count
        reloaded_job = db.get(IngestionJob, job_id)
        assert reloaded_job.status == "QUEUED"
        assert reloaded_job.retry_count == 1
        assert reloaded_job.lock_token is None
        assert reloaded_job.lease_expires_at is None
        assert "Re-queued for retry 1/3" in reloaded_job.error_message

        # Verify INTERRUPTED checkpoint was recorded
        snapshot = processing_snapshot(db, inv.id, org_id)
        events = snapshot["jobs"][0]["events"]
        assert any(e["status"] == "INTERRUPTED" for e in events)


def test_interrupted_job_exceeding_max_retries_fails_and_flags_invoice(disposable_app_db):
    """When a job exceeds max_retries after repeated lease timeouts, it transitions to FAILED."""
    with disposable_app_db() as db:
        job, inv, doc = seed_job_fixture(db, "org_test_fail", "job_fail_1")

        # Pre-set retry_count to 2
        job.retry_count = 2
        job.status = "PROCESSING"
        job.lock_token = "token_stale_99"
        job.lease_expires_at = dt.datetime.utcnow() - dt.timedelta(seconds=10)
        db.commit()

        # Trigger recovery with max_retries = 3
        recovered_count = pipeline.recover_expired_jobs(db, org_id="org_test_fail", max_retries=3)
        assert recovered_count == 1

        # Verify job marked FAILED
        reloaded_job = db.get(IngestionJob, "job_fail_1")
        assert reloaded_job.status == "FAILED"
        assert reloaded_job.retry_count == 3
        assert reloaded_job.lock_token is None
        assert reloaded_job.lease_expires_at is None
        assert "exceeded max retries" in reloaded_job.error_message

        # Verify linked invoice marked FLAGGED_EXCEPTION
        reloaded_inv = db.get(Invoice, inv.id)
        assert reloaded_inv.stage == "ACTION_REQUIRED"
        assert reloaded_inv.decision == "FLAGGED_EXCEPTION"
        assert "failed after 3 lease timeouts" in reloaded_inv.decision_reason


def test_stale_worker_with_expired_lease_fenced_from_renewal_and_checkpoint(disposable_app_db):
    """A stale worker cannot renew its lease or write checkpoints after lease expiry."""
    with disposable_app_db() as db:
        job, inv, doc = seed_job_fixture(db, "org_test_fence", "job_fence_1")

        # Claim the job
        claimed = pipeline.claim_ingestion_job(db, org_id="org_test_fence", lease_seconds=5)
        _, _, _, lock_token = claimed

        # Simulate expiration
        active_job = db.get(IngestionJob, "job_fence_1")
        active_job.lease_expires_at = dt.datetime.utcnow() - dt.timedelta(seconds=1)
        db.commit()

        # Stale worker tries to renew lease: MUST FAIL
        renewed = pipeline.renew_job_lease(db, "job_fence_1", lock_token, additional_seconds=60, org_id="org_test_fence")
        assert renewed is False

        # Stale worker tries to write checkpoint: MUST FAIL
        checkpoint_ok = pipeline._checkpoint("job_fence_1", lock_token, "org_test_fence", "EXTRACTION", "SUCCEEDED", "stale payload", db)
        assert checkpoint_ok is False


def test_recover_expired_jobs_respects_tenant_isolation(disposable_app_db):
    """Recovery scoped to org A does not mutate expired jobs belonging to org B."""
    with disposable_app_db() as db:
        seed_job_fixture(db, "org_alpha", "job_alpha_1")
        seed_job_fixture(db, "org_beta", "job_beta_1")

        # Both jobs are in PROCESSING with expired leases
        job_a = db.get(IngestionJob, "job_alpha_1")
        job_a.status = "PROCESSING"
        job_a.lock_token = "token_a"
        job_a.lease_expires_at = dt.datetime.utcnow() - dt.timedelta(seconds=20)

        job_b = db.get(IngestionJob, "job_beta_1")
        job_b.status = "PROCESSING"
        job_b.lock_token = "token_b"
        job_b.lease_expires_at = dt.datetime.utcnow() - dt.timedelta(seconds=20)
        db.commit()

        # Run recovery scoped ONLY to org_alpha
        recovered = pipeline.recover_expired_jobs(db, org_id="org_alpha")
        assert recovered == 1

        # Assert job A was recovered to QUEUED
        assert db.get(IngestionJob, "job_alpha_1").status == "QUEUED"

        # Assert job B remains untouched in PROCESSING
        assert db.get(IngestionJob, "job_beta_1").status == "PROCESSING"
