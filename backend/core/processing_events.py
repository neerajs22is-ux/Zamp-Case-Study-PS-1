"""Durable processing checkpoints in the existing append-only tenant audit log.

Call append_checkpoint with the job row locked (or before a new job is visible).
Sequence numbers are local to a job and span retries; no synthetic backfill.
"""
import datetime
import uuid
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from backend.models.domain import AuditEvent, Document, IngestionJob

EVENT_ACTIONS = ('PIPELINE_STAGE', 'DOCUMENT_UPLOADED', 'GMAIL_INVOICE_INGESTED')


def lease_now(db: Session):
    """Use the database clock for cross-worker lease comparisons on PostgreSQL."""
    if db.get_bind().dialect.name == 'postgresql':
        return db.scalar(select(func.timezone('UTC', func.clock_timestamp())))
    return datetime.datetime.utcnow()


def append_checkpoint(db: Session, job: IngestionJob, stage: str, status: str,
                      message: str, *, attempt=None, invoice_id=None, outcome=None,
                      actor_id='system_pipeline', actor_role='SYSTEM_SERVICE',
                      action='PIPELINE_STAGE', source_reference=None):
    sequence = db.scalar(select(func.max(AuditEvent.after_state['sequence'].as_integer())).where(
        AuditEvent.org_id == job.org_id, AuditEvent.action.in_(EVENT_ACTIONS),
        AuditEvent.after_state['processing_version'].as_integer() == 1,
        AuditEvent.after_state['job_id'].as_string() == job.id)) or 0
    if invoice_id is None and job.document_id:
        invoice_id = db.scalar(select(Document.invoice_id).where(
            Document.id == job.document_id, Document.org_id == job.org_id))
    payload = dict(processing_version=1, job_id=job.id, sequence=sequence + 1,
        attempt=job.retry_count + 1 if attempt is None else attempt,
        stage=stage, status=status, message=message)
    if outcome is not None:
        payload['outcome'] = outcome
    db.add(AuditEvent(id=f'evt_{uuid.uuid4().hex[:12]}', org_id=job.org_id,
        invoice_id=invoice_id, actor_id=actor_id, actor_role=actor_role,
        action=action, reason=message, after_state=payload,
        source_reference=source_reference or job.document_id,
        timestamp=datetime.datetime.utcnow()))
    db.flush()


def processing_snapshot(db: Session, invoice_id: str, org_id: str):
    """Caller must authorize the invoice first. This function never changes state."""
    rows = db.scalars(select(IngestionJob).join(Document,
        (Document.id == IngestionJob.document_id) & (Document.org_id == IngestionJob.org_id)).where(
        Document.invoice_id == invoice_id, Document.org_id == org_id,
        IngestionJob.org_id == org_id).order_by(IngestionJob.created_at, IngestionJob.id)).all()
    records = db.scalars(select(AuditEvent).where(AuditEvent.org_id == org_id,
        AuditEvent.invoice_id == invoice_id, AuditEvent.action.in_(EVENT_ACTIONS),
        AuditEvent.after_state['processing_version'].as_integer() == 1)).all()
    by_job = {job.id: [] for job in rows}
    for record in records:
        payload = record.after_state
        if payload.get('job_id') in by_job:
            by_job[payload['job_id']].append(dict(id=record.id, sequence=payload['sequence'],
                attempt=payload['attempt'], stage=payload['stage'], status=payload['status'],
                message=payload['message'], timestamp=record.timestamp.isoformat() + 'Z',
                outcome=payload.get('outcome')))
    now = lease_now(db)
    return dict(invoice_id=invoice_id, jobs=[dict(id=job.id, status=job.status,
        created_at=job.created_at.isoformat() + 'Z', retry_count=job.retry_count,
        lease_expires_at=job.lease_expires_at.isoformat() + 'Z' if job.lease_expires_at else None,
        lease_expired=bool(job.status == 'PROCESSING' and job.lease_expires_at and job.lease_expires_at <= now),
        completed_at=job.completed_at.isoformat() + 'Z' if job.completed_at else None,
        error_recorded=bool(job.error_message),
        error_message=job.error_message,
        events=sorted(by_job[job.id], key=lambda event: event['sequence'])) for job in rows])
