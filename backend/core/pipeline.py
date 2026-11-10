"""AP Command Center — Durable Ingestion & Document Intelligence Pipeline.

Durable, recoverable, idempotent background processing engine designed for
Render Free + Supabase architecture.

Key Invariants:
1. Atomic job claiming via PostgreSQL FOR UPDATE SKIP LOCKED.
2. Distinct lock token assignment and lease expiration timestamps.
3. Provider workers retain no DB transaction during calls; keepalive uses short independent transactions.
4. Opportunistic recovery of expired leases on incoming authenticated requests.
5. Strict transactional commit of extraction runs, fields, lines, and gates.
6. Clean state transitions:
   - 7/7 gates PASS -> PENDING_APPROVAL / MATCH_CANDIDATE
   - Gate fail (degraded scan) -> ACTION_REQUIRED / FLAGGED_HITL_REVIEW
   - Gate fail (other policy) -> ACTION_REQUIRED / FLAGGED_EXCEPTION + ExceptionRecord
7. Bounded retries (max 3) before marking IngestionJob as FAILED.
"""

from __future__ import annotations

import datetime
import logging
import threading
import time
import uuid
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import delete, or_, select, text
from sqlalchemy.orm import Session, sessionmaker

from backend.core.config import settings
from backend.core.database import get_db, engine, set_tenant_context
from backend.core.storage import storage_adapter
from backend.core.processing_events import append_checkpoint, lease_now
from backend.core.model_quota import reserve_model_attempt, ModelQuotaExceeded
from backend.models.domain import (
    AuditEvent, Document, ExceptionRecord, ExtractedField, ExtractionRun,
    IngestionJob, Invoice, InvoiceLine, MatchGateCheck, MatchRun
)
from engine.hybrid_extractor import HybridAPExtractor, HybridProcessingResult

logger = logging.getLogger("ap_pipeline")
logger.setLevel(logging.INFO)

# Session factory for background execution
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
JOB_LEASE_SECONDS = 180


class _ProviderLease:
    """Bounded keepalive using independent short tenant transactions, never a shared Session.

    Losing renewal fails closed even if the provider later returns. A thread cannot
    cancel an external call: only its financial result is fenced out.
    """
    def __init__(self, job_id, token, org_id, factory):
        self.job_id, self.token, self.org_id, self.factory = job_id, token, org_id, factory
        self.stopped = threading.Event()
        self.lost = threading.Event()
        self.deadline = time.monotonic() + settings.PIPELINE_PROVIDER_BUDGET_SECONDS
        self.thread = threading.Thread(target=self._run, daemon=True, name='invoice-lease')

    @property
    def valid(self):
        return not self.lost.is_set() and time.monotonic() < self.deadline

    def _renew(self, record=False):
        with self.factory() as db:
            set_tenant_context(db, self.org_id)
            if db.get_bind().dialect.name == 'postgresql':
                # Do not hang a provider worker on recovery/DB lock contention.
                db.execute(text("SET LOCAL lock_timeout = '2s'"))
                db.execute(text("SET LOCAL statement_timeout = '3s'"))
            return renew_job_lease(db, self.job_id, self.token, JOB_LEASE_SECONDS,
                org_id=self.org_id, record_checkpoint=record)

    def start(self):
        try:
            if not self._renew():
                self.lost.set()
                return
        except Exception:
            self.lost.set()
            logger.warning('Provider lease could not be established for job %s', self.job_id)
            return
        self.thread.start()

    def _run(self):
        record = True
        interval = min(30, JOB_LEASE_SECONDS / 3)
        while not self.stopped.wait(min(interval, max(0, self.deadline - time.monotonic()))):
            if not self.valid:
                self.lost.set()
                try:
                    with self.factory() as db:
                        _checkpoint(self.job_id, self.token, self.org_id, 'LEASE', 'RENEWAL_STOPPED',
                            'Provider renewal budget exhausted; external completion is unconfirmed. Late results will not be accepted.', db)
                except Exception:
                    logger.warning('Could not record renewal budget expiry for job %s', self.job_id)
                return
            try:
                if not self._renew(record):
                    self.lost.set()
                    return
                record = False
            except Exception:
                self.lost.set()
                logger.warning('Lease renewal failed; provider result will be discarded for job %s', self.job_id)
                return

    def stop(self):
        self.stopped.set()
        if self.thread.ident is not None:
            self.thread.join(timeout=4)
            if self.thread.is_alive():
                self.lost.set()


def _checkpoint(job_id, token, org_id, stage, status, message, session=None, failure=False, outcome=None):
    """Short fenced transaction; stale workers cannot record progress or retry."""
    db = session if session is not None else SessionLocal()
    try:
        set_tenant_context(db, org_id)
        job = db.scalar(select(IngestionJob).where(
            IngestionJob.id == job_id, IngestionJob.org_id == org_id,
            IngestionJob.lock_token == token, IngestionJob.status == 'PROCESSING',
            IngestionJob.lease_expires_at > lease_now(db)).with_for_update().execution_options(populate_existing=True))
        if job is None or job.lease_expires_at <= lease_now(db):
            db.rollback()
            return False
        append_checkpoint(db, job, stage, status, message, outcome=outcome)
        if failure:
            job.retry_count += 1
            job.status = 'FAILED' if job.retry_count >= 3 else 'QUEUED'
            job.error_message = message
            job.lock_token = None
            job.lease_expires_at = None
            if job.status == 'FAILED':
                doc = db.scalar(select(Document).where(Document.id == job.document_id, Document.org_id == org_id))
                inv = db.scalar(select(Invoice).where(Invoice.id == doc.invoice_id, Invoice.org_id == org_id)) if doc else None
                if inv:
                    inv.stage = 'ACTION_REQUIRED'
                    inv.decision = 'FLAGGED_HITL_REVIEW'
                    inv.decision_reason = 'Document processing failed after three attempts; evidence requires review.'
        db.commit()
        return True
    finally:
        if session is None:
            db.close()


def _reserve_extraction(job_id, token, org_id, session=None):
    db = session if session is not None else SessionLocal()
    try:
        set_tenant_context(db, org_id)
        job = db.scalar(select(IngestionJob).where(
            IngestionJob.id == job_id, IngestionJob.org_id == org_id,
            IngestionJob.lock_token == token, IngestionJob.status == 'PROCESSING',
            IngestionJob.lease_expires_at > lease_now(db)).with_for_update().execution_options(populate_existing=True))
        if not job or job.lease_expires_at <= lease_now(db):
            db.rollback()
            return False
        reserve_model_attempt(db, org_id)
        db.commit()
        return True
    except Exception:
        db.rollback()
        raise
    finally:
        if session is None:
            db.close()


def claim_ingestion_job(
    db: Session,
    org_id: Optional[str] = None,
    lease_seconds: int = 180,
    job_id: Optional[str] = None,
    recover_expired: bool = True,
) -> Optional[Tuple[str, str, str, str]]:
    """Atomically claims a queued or expired ingestion job using FOR UPDATE SKIP LOCKED.

    Args:
        db: Active database session.
        org_id: Optional tenant isolation filter.
        lease_seconds: Worker lease duration in seconds.
        job_id: Optional specific job identifier to claim. If provided, claims this exact job.
        recover_expired: Whether to opportunistically recover unrelated expired
            jobs first. Targeted retries pass False after recovering their own row.

    Returns:
        Tuple of (job_id, org_id, document_id, lock_token) or None if no job available.
    """
    if recover_expired:
        recover_expired_jobs(db, org_id=org_id)
    stmt = (
        select(IngestionJob)
        .where(
            IngestionJob.status == "QUEUED"
        )
    )
    if org_id:
        stmt = stmt.where(IngestionJob.org_id == org_id)
    if job_id:
        stmt = stmt.where(IngestionJob.id == job_id)

    stmt = stmt.order_by(IngestionJob.created_at.asc()).with_for_update(skip_locked=True).limit(1)
    job = db.scalar(stmt.execution_options(populate_existing=True))

    if not job:
        return None

    token = uuid.uuid4().hex
    job.status = "PROCESSING"
    job.lock_token = token
    job.lease_expires_at = lease_now(db) + datetime.timedelta(seconds=lease_seconds)
    append_checkpoint(db, job, 'RUN', 'STARTED', 'Worker claimed this processing attempt.')
    db.commit()

    logger.info(f"Claimed job {job.id} for org {job.org_id} with lock token {token[:8]} (lease: {lease_seconds}s)")
    return (job.id, job.org_id, job.document_id, token)


def renew_job_lease(db: Session, job_id: str, lock_token: str, additional_seconds: int = 180,
                    *, org_id=None, record_checkpoint=False) -> bool:
    """Never resurrect expired ownership, including expiry while waiting for its row lock."""
    if additional_seconds <= 0:
        raise ValueError('Lease extension must be positive')
    if org_id:
        set_tenant_context(db, org_id)
    stmt = select(IngestionJob).where(IngestionJob.id == job_id,
        IngestionJob.lock_token == lock_token, IngestionJob.status == 'PROCESSING')
    if org_id:
        stmt = stmt.where(IngestionJob.org_id == org_id)
    job = db.scalar(stmt.with_for_update().execution_options(populate_existing=True))
    now = lease_now(db)
    if job is None or job.lease_expires_at is None or job.lease_expires_at <= now:
        db.rollback()
        return False
    job.lease_expires_at = max(job.lease_expires_at, now + datetime.timedelta(seconds=additional_seconds))
    if record_checkpoint:
        append_checkpoint(db, job, 'LEASE', 'RENEWED',
            'Worker renewed its lease while awaiting provider work; this does not confirm provider progress.')
    db.commit()
    return True


def recover_expired_jobs(db: Session, org_id: Optional[str] = None, max_retries: int = 3,
                         job_id: Optional[str] = None) -> int:
    """Scans for abandoned or interrupted PROCESSING jobs whose lease has expired.

    Reclaims them to QUEUED if retry_count < max_retries, else marks them FAILED.
    Passing ``job_id`` scopes recovery to that exact row; a PROCESSING row with
    no lease is also recoverable because it cannot make further progress.
    """
    now = lease_now(db)
    stmt = select(IngestionJob).where(IngestionJob.status == "PROCESSING")
    if job_id:
        stmt = stmt.where(
            IngestionJob.id == job_id,
            or_(
                IngestionJob.lease_expires_at <= now,
                IngestionJob.lease_expires_at.is_(None),
            ),
        )
    else:
        stmt = stmt.where(IngestionJob.lease_expires_at <= now)
    if org_id:
        stmt = stmt.where(IngestionJob.org_id == org_id)

    expired_jobs = db.scalars(stmt.with_for_update(skip_locked=True).execution_options(populate_existing=True)).all()
    recovered_count = 0

    for job in expired_jobs:
        append_checkpoint(db, job, 'RUN', 'INTERRUPTED', 'Worker lease expired; external call completion is unknown. Repeating provider work may occur; stale results cannot commit.')
        job.retry_count += 1
        if job.retry_count >= max_retries:
            job.status = "FAILED"
            job.error_message = f"Job lease expired {job.retry_count} times; exceeded max retries ({max_retries})."
            job.lock_token = None
            job.lease_expires_at = None

            # Mark linked invoice as failed/action required
            if job.document_id:
                doc = db.scalar(select(Document).where(Document.id == job.document_id, Document.org_id == job.org_id))
                if doc and doc.invoice_id:
                    inv = db.scalar(select(Invoice).where(Invoice.id == doc.invoice_id, Invoice.org_id == job.org_id))
                    if inv:
                        inv.stage = "ACTION_REQUIRED"
                        inv.decision = "FLAGGED_EXCEPTION"
                        inv.decision_reason = f"Document processing failed after {max_retries} lease timeouts."
            logger.warning(f"Job {job.id} marked FAILED after {job.retry_count} timeouts.")
        else:
            job.status = "QUEUED"
            job.lock_token = None
            job.lease_expires_at = None
            job.error_message = f"Lease expired. Re-queued for retry {job.retry_count}/{max_retries}."
            logger.info(f"Job {job.id} recovered from expired lease; re-queued (retry {job.retry_count}).")

        recovered_count += 1

    if recovered_count > 0:
        db.commit()

    return recovered_count


def execute_document_pipeline(
    job_id: str,
    lock_token: str,
    db_session: Optional[Session] = None,
    extractor: Optional[Any] = None,
    org_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Executes the complete document extraction and deterministic matching pipeline.

    Provider calls never retain a database transaction. Lease renewal uses
    independent short transactions rather than sharing the worker Session.
    """
    managed_session = db_session is None
    db = db_session or SessionLocal()

    if org_id:
        set_tenant_context(db, org_id)

    # Phase A: Short Claim & Document Fetch Transaction (< 10 ms)
    try:
        job = db.scalar(
            select(IngestionJob).where(
                IngestionJob.id == job_id,
                IngestionJob.org_id == org_id if org_id else True,
                IngestionJob.lock_token == lock_token,
                IngestionJob.status == "PROCESSING",
                IngestionJob.lease_expires_at > lease_now(db),
            ).with_for_update().execution_options(populate_existing=True)
        )
        if not job or job.lease_expires_at <= lease_now(db):
            logger.warning(f"Job {job_id} is no longer owned by token {lock_token[:8]}; aborting.")
            db.rollback()
            if managed_session:
                db.close()
            return {"status": "ABORTED", "reason": "Lock token mismatch or job no longer PROCESSING."}

        document_id = job.document_id
        org_id = job.org_id

        doc = db.scalar(select(Document).where(
            Document.id == document_id,
            Document.org_id == org_id,
            Document.is_deleted == False,
        ))
        if not doc:
            append_checkpoint(db, job, 'DOCUMENT_READ', 'FAILED', 'Processing document is unavailable or was soft-deleted.')
            job.status = "FAILED"
            job.error_message = f"Document '{document_id}' not found."
            job.lock_token = None
            job.lease_expires_at = None
            db.commit()
            if managed_session:
                db.close()
            return {"status": "FAILED", "reason": f"Document '{document_id}' not found."}

        storage_key = doc.storage_key
        expected_hash = doc.sha256_hash
        filename = doc.filename
        invoice_id = doc.invoice_id
        append_checkpoint(db, job, 'DOCUMENT_READ', 'STARTED', 'Reading the stored document and verifying its digest.')
        db.commit()

    finally:
        # Explicitly close/commit session before external network call
        if managed_session:
            db.close()

    # Phase B: Provider calls retain no worker database transaction.
    current_stage = 'DOCUMENT_READ'
    checkpoint_session = None if managed_session else db
    keeper = _ProviderLease(job_id, lock_token, org_id,
        SessionLocal if managed_session else sessionmaker(bind=db.get_bind(), autoflush=False))
    keeper.start()
    try:
        if not keeper.valid:
            return {'status': 'ABORTED', 'reason': 'Provider lease unavailable; external completion is unconfirmed.'}
        pdf_bytes = storage_adapter.get_file(storage_key)
        if not keeper.valid:
            return {'status': 'ABORTED', 'reason': 'Provider lease lost; returned bytes discarded.'}
        if not pdf_bytes:
            raise ValueError(f"Storage adapter returned empty content for storage key '{storage_key}'")
        import hashlib
        if hashlib.sha256(pdf_bytes).hexdigest() != expected_hash:
            raise ValueError("Stored document integrity verification failed")

        if not _checkpoint(job_id, lock_token, org_id, 'DOCUMENT_READ', 'SUCCEEDED', 'Stored document digest verified.', checkpoint_session):
            return {'status': 'ABORTED'}
        current_stage = 'EXTRACTION'
        try:
            if not _reserve_extraction(job_id, lock_token, org_id, checkpoint_session):
                return {'status': 'ABORTED'}
        except ModelQuotaExceeded as exc:
            _checkpoint(job_id, lock_token, org_id, 'EXTRACTION', 'FAILED', str(exc), checkpoint_session, failure=True)
            return {'status': 'FAILED', 'error': str(exc)}
        if not _checkpoint(job_id, lock_token, org_id, 'EXTRACTION', 'STARTED', 'Running document extraction, grounding and validation.', checkpoint_session):
            return {'status': 'ABORTED'}

        if extractor is None:
            from engine.indian_tax_rules import IndianAPRuleEngine
            extractor = HybridAPExtractor(rule_engine=IndianAPRuleEngine(load_reference_data=False))
        processing_result: HybridProcessingResult = extractor.extract_hybrid(
            pdf_bytes=pdf_bytes,
            filename=filename,
            document_id=document_id,
        )
        keeper.stop()
        if not keeper.valid:
            return {'status': 'ABORTED', 'reason': 'Provider lease lost or budget exhausted; returned result discarded.'}
        extraction_outcome = "SKIPPED" if getattr(processing_result, "inference_provider", None) == "NONE_ROUTED_HITL" else "EXTRACTED"
        extraction_msg = (
            "Degraded scan tripwire triggered; LLM inference skipped to avoid ungrounded hallucinations."
            if extraction_outcome == "SKIPPED"
            else f"Live Mantle Qwen 235B extraction completed ({len(processing_result.line_items)} line items)."
        )
        if not _checkpoint(job_id, lock_token, org_id, 'EXTRACTION', 'SUCCEEDED', extraction_msg, checkpoint_session, outcome=extraction_outcome):
            return {'status': 'ABORTED'}
        if not _checkpoint(job_id, lock_token, org_id, 'MATCHING', 'STARTED', 'Evaluating tenant source records and persisting the processing outcome.', checkpoint_session):
            return {'status': 'ABORTED'}

    except Exception as e:
        logger.error(f"Inference failed for job {job_id}: {str(e)}", exc_info=True)
        keeper.stop()
        if not keeper.valid:
            return {'status': 'ABORTED', 'reason': 'Provider ownership unconfirmed; recovery required.'}
        if not _checkpoint(job_id, lock_token, org_id, current_stage, 'FAILED',
            'Document read or extraction failed. Use the job ID for investigation.', checkpoint_session, failure=True):
            return {'status': 'ABORTED', 'reason': 'Provider ownership lost; recovery required.'}
        return {"status": "FAILED", "error": "Document processing failed; see job status."}
    finally:
        keeper.stop()

    # Phase C: Atomic Result Persistence Transaction (< 20 ms)
    persist_db = SessionLocal() if managed_session else db
    set_tenant_context(persist_db, org_id)
    try:
        # Re-verify lock token to avoid split-brain execution
        active_job = persist_db.scalar(
            select(IngestionJob).where(
                IngestionJob.id == job_id,
                IngestionJob.org_id == org_id,
                IngestionJob.lock_token == lock_token,
                IngestionJob.status == "PROCESSING",
                IngestionJob.lease_expires_at > lease_now(persist_db),
            ).with_for_update().execution_options(populate_existing=True)
        )
        if not active_job or active_job.lease_expires_at <= lease_now(persist_db):
            logger.warning(f"Lock lost during inference for job {job_id}; rolling back persistence.")
            persist_db.rollback()
            return {"status": "ABORTED", "reason": "Lock expired during inference execution."}

        source_document = persist_db.scalar(select(Document).where(
            Document.id == document_id,
            Document.org_id == org_id,
        ))
        if source_document is None or source_document.is_deleted:
            raise ValueError("Source document was removed before the result could be committed")

        now_utc = datetime.datetime.utcnow()

        # 1. Persist Extraction Run
        extraction_run_id = f"ext_{uuid.uuid4().hex[:12]}"
        parser_ver = f"{processing_result.model_id or 'hybrid_v1'}"[:32]
        extraction_run = ExtractionRun(
            id=extraction_run_id,
            org_id=org_id,
            document_id=document_id,
            parser_version=parser_ver,
            overall_confidence=None,
            extracted_at=now_utc,
        )
        persist_db.add(extraction_run)

        # 2. Persist Extracted Fields
        fields_to_record = [
            ("invoice_number", processing_result.invoice_number, 0.99),
            ("invoice_date", processing_result.invoice_date, 0.99),
            ("supplier_name", processing_result.supplier_name, 0.99),
            ("supplier_gstin", processing_result.supplier_gstin, 0.99),
            ("po_reference", processing_result.po_reference, 0.95),
            ("taxable_value", str(processing_result.taxable_value), 0.99),
            ("cgst_amount", str(processing_result.cgst_amount), 0.99),
            ("sgst_amount", str(processing_result.sgst_amount), 0.99),
            ("igst_amount", str(processing_result.igst_amount), 0.99),
            ("total_tax_amount", str(processing_result.total_tax_amount), 0.99),
            ("grand_total", str(processing_result.grand_total), 0.99),
        ]
        for fname, fval, fconf in fields_to_record:
            if fval is not None:
                ef = ExtractedField(
                    id=f"fld_{uuid.uuid4().hex[:12]}",
                    org_id=org_id,
                    extraction_run_id=extraction_run_id,
                    field_name=fname,
                    extracted_value=str(fval),
                    confidence_score=None,
                    source_page=(processing_result.evidence.get(fname).page_number if getattr(processing_result, "evidence", {}).get(fname) and processing_result.evidence[fname].is_verified else None),
                )
                persist_db.add(ef)

        # 3. Persist Extracted Lines
        if invoice_id and processing_result.line_items:
            persist_db.execute(
                delete(InvoiceLine).where(
                    InvoiceLine.invoice_id == invoice_id,
                    InvoiceLine.org_id == org_id,
                )
            )
            for idx, line in enumerate(processing_result.line_items, start=1):
                desc = (
                    getattr(line, "item_description", None)
                    or getattr(line, "description", None)
                    or (line.get("description") or line.get("item_description") if isinstance(line, dict) else None)
                    or f"Line Item #{idx}"
                )
                qty = (
                    getattr(line, "quantity", None)
                    or (line.get("quantity") if isinstance(line, dict) else None)
                    or 1.0
                )
                unit_r = (
                    getattr(line, "unit_price", None)
                    or getattr(line, "unit_rate", None)
                    or (line.get("unit_price") or line.get("unit_rate") if isinstance(line, dict) else None)
                    or 0.0
                )
                # InvoiceLine totals are before tax; extracted total_amount may
                # include GST and would be taxed twice during reconciliation.
                tot = line.get("taxable_amount") if isinstance(line, dict) else getattr(line, "taxable_amount", None)
                if tot is None:
                    tot = float(qty) * float(unit_r)
                inv_line = InvoiceLine(
                    id=f"line_{invoice_id}_{idx}",
                    org_id=org_id,
                    invoice_id=invoice_id,
                    line_number=idx,
                    description=desc,
                    billed_quantity=float(qty),
                    billed_unit_rate=float(unit_r),
                    billed_line_total=float(tot),
                )
                persist_db.add(inv_line)

        # Authoritative matching uses the same tenant-scoped snapshots as corrections.
        # The extraction adapter's offline CSV result is never an authorization source.
        from backend.api.v1.invoices import reevaluate_match_gates
        inv = persist_db.scalar(select(Invoice).where(Invoice.id == invoice_id, Invoice.org_id == org_id).with_for_update())
        if inv is None:
            raise ValueError("Invoice not found in processing workspace")
        inv.vendor_name = processing_result.supplier_name
        inv.vendor_gstin = processing_result.supplier_gstin
        inv.invoice_number = processing_result.invoice_number
        inv.po_reference = processing_result.po_reference
        inv.currency = processing_result.currency
        inv.total_amount = processing_result.grand_total
        inv.subtotal_amount = processing_result.taxable_value
        inv.tax_amount = processing_result.total_tax_amount
        inv.net_payable_amount = processing_result.grand_total
        try:
            inv.invoice_date = datetime.datetime.fromisoformat(processing_result.invoice_date)
        except ValueError:
            inv.invoice_date = None
        persist_db.flush()
        match_run = reevaluate_match_gates(persist_db, inv, org_id)
        is_scanned_or_review = (
            processing_result.document_type == "SCANNED_IMAGE"
            or processing_result.extraction_status in ("NOT_EVALUATED", "DEGRADED_SCAN")
        )
        rejection = (
            not is_scanned_or_review
            and (not processing_result.is_payable_invoice or processing_result.document_type in (
                "PAYMENT_RECEIPT", "PURCHASE_ORDER", "DELIVERY_CHALLAN", "PROFORMA_INVOICE"
            ))
        )
        extraction_blocked = (
            rejection
            or is_scanned_or_review
            or not processing_result.grounding_tripwire_passed
            or not processing_result.tax_arithmetic.is_valid
            or processing_result.currency != "INR"
            or processing_result.document_type not in ("INVOICE", "DEBIT_NOTE")
            or getattr(processing_result, "extraction_requires_review", False)
        )
        if extraction_blocked:
            persist_db.add(MatchGateCheck(id=f"mg_{match_run.id}_8", org_id=org_id,
                match_run_id=match_run.id, gate_number=8, gate_name="Extraction evidence and payable document",
                status="FAIL", evidence_notes="; ".join(processing_result.decision_reasons) or "Extraction requires verification.",
                checked_at=now_utc))
            match_run.overall_result = "FAIL"
        persist_db.flush()
        saved_checks = persist_db.scalars(select(MatchGateCheck).where(
            MatchGateCheck.match_run_id == match_run.id, MatchGateCheck.org_id == org_id)).all()
        gate_checks = [(g.gate_number, g.gate_name, g.status, g.evidence_notes) for g in saved_checks]
        failed_gate = next(((n, name, notes) for n, name, state, notes in gate_checks if state != "PASS"), None)

        # 5. Update Invoice State & Financial Metadata
        if invoice_id:
            inv = persist_db.scalar(select(Invoice).where(Invoice.id == invoice_id, Invoice.org_id == org_id))
            if inv:
                inv.vendor_name = processing_result.supplier_name or inv.vendor_name
                inv.vendor_gstin = processing_result.supplier_gstin or inv.vendor_gstin
                inv.po_reference = processing_result.po_reference or inv.po_reference
                inv.invoice_number = processing_result.invoice_number or inv.invoice_number
                inv.total_amount = processing_result.grand_total or inv.total_amount
                inv.subtotal_amount = processing_result.taxable_value or inv.subtotal_amount
                inv.tax_amount = processing_result.total_tax_amount or inv.tax_amount
                inv.net_payable_amount = processing_result.grand_total or inv.net_payable_amount
                inv.updated_at = now_utc

                if failed_gate is None:
                    # Clean match
                    inv.stage = "PENDING_APPROVAL"
                    inv.decision = "MATCH_CANDIDATE"
                    inv.decision_reason = "All 7 deterministic policy gates passed. Ready for approval."
                    persist_db.execute(
                        delete(ExceptionRecord).where(
                            ExceptionRecord.invoice_id == invoice_id,
                            ExceptionRecord.org_id == org_id,
                        )
                    )
                else:
                    gnum, gname, gnotes = failed_gate
                    inv.stage = "ACTION_REQUIRED"
                    if not processing_result.grounding_tripwire_passed or processing_result.extraction_status in ("DEGRADED_SCAN", "NOT_EVALUATED") or is_scanned_or_review:
                        inv.decision = "FLAGGED_HITL_REVIEW"
                        inv.decision_reason = "; ".join(processing_result.decision_reasons) or "Degraded scan quality / ungrounded values detected. Human review required."
                    else:
                        inv.decision = "FLAGGED_EXCEPTION"
                        inv.decision_reason = f"Gate {gnum} ({gname}) failed: {gnotes}"

                    # Create or update Exception Record
                    existing_exc = persist_db.scalar(
                        select(ExceptionRecord).where(
                            ExceptionRecord.invoice_id == invoice_id,
                            ExceptionRecord.org_id == org_id,
                        )
                    )
                    if existing_exc:
                        existing_exc.blocking_gate_number = gnum
                        existing_exc.blocking_gate_name = gname
                        existing_exc.exposure_amount_inr = inv.total_amount or 0.0
                        existing_exc.status = "OPEN"
                    else:
                        exc_record = ExceptionRecord(
                            id=f"exc_{invoice_id}",
                            org_id=org_id,
                            invoice_id=invoice_id,
                            blocking_gate_number=gnum,
                            blocking_gate_name=gname,
                            exposure_amount_inr=inv.total_amount or 0.0,
                            status="OPEN",
                            created_at=now_utc,
                        )
                        persist_db.add(exc_record)

                if rejection:
                    inv.stage = "REJECTED"
                    inv.decision = "REJECTED"
                    inv.decision_reason = "; ".join(processing_result.decision_reasons)
                elif extraction_blocked:
                    inv.stage = "ACTION_REQUIRED"
                    inv.decision = "FLAGGED_HITL_REVIEW"
                    inv.decision_reason = "; ".join(processing_result.decision_reasons) or "Extraction requires verification."

                # Record Processed Audit Event
                audit = AuditEvent(
                    id=f"evt_{uuid.uuid4().hex[:12]}",
                    invoice_id=invoice_id,
                    org_id=org_id,
                    actor_id="system_pipeline",
                    actor_role="SYSTEM_SERVICE",
                    action="DOCUMENT_PROCESSED",
                    reason=inv.decision_reason,
                    before_state={"stage": "RECEIVED", "decision": "NEEDS_REVIEW"},
                    after_state={"stage": inv.stage, "decision": inv.decision},
                    source_reference=document_id,
                    timestamp=now_utc,
                )
                persist_db.add(audit)

        # 6. Mark Job Completed
        append_checkpoint(persist_db, active_job, 'MATCHING', 'SUCCEEDED', 'Deterministic checks and processing outcome committed together.')
        append_checkpoint(persist_db, active_job, 'OUTCOME', 'RECORDED', inv.decision_reason,
            outcome={'stage': inv.stage, 'decision': inv.decision, 'reason': inv.decision_reason})
        active_job.status = "COMPLETED"
        active_job.completed_at = datetime.datetime.utcnow()
        active_job.lock_token = None
        active_job.lease_expires_at = None

        persist_db.commit()
        logger.info(f"Pipeline successfully completed for job {job_id} (Invoice: {invoice_id})")

        return {
            "status": "COMPLETED",
            "invoice_id": invoice_id,
            "stage": inv.stage if invoice_id else None,
            "decision": inv.decision if invoice_id else None,
            "gates_passed": 7 if failed_gate is None else sum(1 for _, _, s, _ in gate_checks if s == "PASS"),
        }

    except Exception as e:
        persist_db.rollback()
        logger.error(f"Persistence transaction failed for job {job_id}: {str(e)}", exc_info=True)
        _checkpoint(job_id, lock_token, org_id, 'MATCHING', 'FAILED',
            'Matching or result persistence failed; the result transaction was rolled back.',
            None if managed_session else persist_db, failure=True)
        return {"status": "FAILED", "error": "Matching or result persistence failed; see job status."}
    finally:
        if managed_session:
            persist_db.close()


def process_document_pipeline_background(job_id: str, lock_token: str, org_id: str) -> None:
    """Safe wrapper invoked via FastAPI BackgroundTasks."""
    try:
        execute_document_pipeline(job_id=job_id, lock_token=lock_token, org_id=org_id)
    except Exception as e:
        logger.error(f"Unhandled background task error in pipeline for job {job_id}: {str(e)}", exc_info=True)
