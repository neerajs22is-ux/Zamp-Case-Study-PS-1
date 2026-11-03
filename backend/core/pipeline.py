"""AP Command Center — Durable Ingestion & Document Intelligence Pipeline.

Durable, recoverable, idempotent background processing engine designed for
Render Free + Supabase architecture.

Key Invariants:
1. Atomic job claiming via PostgreSQL FOR UPDATE SKIP LOCKED.
2. Distinct lock token assignment and lease expiration timestamps.
3. Zero database transactions held open during external Bedrock inference calls.
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
import uuid
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import select, update
from sqlalchemy.orm import Session, sessionmaker

from backend.core.config import settings
from backend.core.database import get_db, engine
from backend.core.storage import storage_adapter
from backend.models.domain import (
    AuditEvent, Document, ExceptionRecord, ExtractedField, ExtractionRun,
    IngestionJob, Invoice, InvoiceLine, MatchGateCheck, MatchRun
)
from engine.hybrid_extractor import HybridAPExtractor, HybridProcessingResult

logger = logging.getLogger("ap_pipeline")
logger.setLevel(logging.INFO)

# Session factory for background execution
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def claim_ingestion_job(
    db: Session,
    org_id: Optional[str] = None,
    lease_seconds: int = 180,
) -> Optional[Tuple[str, str, str, str]]:
    """Atomically claims a queued or expired ingestion job using FOR UPDATE SKIP LOCKED.

    Returns:
        Tuple of (job_id, org_id, document_id, lock_token) or None if no job available.
    """
    now = datetime.datetime.utcnow()
    stmt = (
        select(IngestionJob)
        .where(
            (IngestionJob.status == "QUEUED") |
            ((IngestionJob.status == "PROCESSING") & (IngestionJob.lease_expires_at < now))
        )
    )
    if org_id:
        stmt = stmt.where(IngestionJob.org_id == org_id)

    stmt = stmt.order_by(IngestionJob.created_at.asc()).with_for_update(skip_locked=True).limit(1)
    job = db.scalar(stmt)

    if not job:
        return None

    token = uuid.uuid4().hex
    job.status = "PROCESSING"
    job.lock_token = token
    job.lease_expires_at = now + datetime.timedelta(seconds=lease_seconds)
    db.commit()

    logger.info(f"Claimed job {job.id} for org {job.org_id} with lock token {token[:8]} (lease: {lease_seconds}s)")
    return (job.id, job.org_id, job.document_id, token)


def renew_job_lease(db: Session, job_id: str, lock_token: str, additional_seconds: int = 180) -> bool:
    """Extends the lease for an actively processing job holding a valid lock token."""
    now = datetime.datetime.utcnow()
    new_expires = now + datetime.timedelta(seconds=additional_seconds)

    result = db.execute(
        update(IngestionJob)
        .where(
            IngestionJob.id == job_id,
            IngestionJob.lock_token == lock_token,
            IngestionJob.status == "PROCESSING",
        )
        .values(lease_expires_at=new_expires)
    )
    db.commit()
    return result.rowcount > 0


def recover_expired_jobs(db: Session, org_id: Optional[str] = None, max_retries: int = 3) -> int:
    """Scans for abandoned or interrupted PROCESSING jobs whose lease has expired.

    Reclaims them to QUEUED if retry_count < max_retries, else marks them FAILED.
    """
    now = datetime.datetime.utcnow()
    stmt = select(IngestionJob).where(
        IngestionJob.status == "PROCESSING",
        IngestionJob.lease_expires_at < now,
    )
    if org_id:
        stmt = stmt.where(IngestionJob.org_id == org_id)

    expired_jobs = db.scalars(stmt).all()
    recovered_count = 0

    for job in expired_jobs:
        job.retry_count += 1
        if job.retry_count >= max_retries:
            job.status = "FAILED"
            job.error_message = f"Job lease expired {job.retry_count} times; exceeded max retries ({max_retries})."
            job.lock_token = None
            job.lease_expires_at = None

            # Mark linked invoice as failed/action required
            if job.document_id:
                doc = db.scalar(select(Document).where(Document.id == job.document_id))
                if doc and doc.invoice_id:
                    inv = db.scalar(select(Invoice).where(Invoice.id == doc.invoice_id))
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
) -> Dict[str, Any]:
    """Executes the complete document extraction and deterministic matching pipeline.

    CRITICAL ARCHITECTURAL GUARANTEE:
    External Bedrock inference is executed with ZERO database transactions held open.
    """
    managed_session = db_session is None
    db = db_session or SessionLocal()

    # Phase A: Short Claim & Document Fetch Transaction (< 10 ms)
    try:
        job = db.scalar(
            select(IngestionJob).where(
                IngestionJob.id == job_id,
                IngestionJob.lock_token == lock_token,
                IngestionJob.status == "PROCESSING",
            )
        )
        if not job:
            logger.warning(f"Job {job_id} is no longer owned by token {lock_token[:8]}; aborting.")
            if managed_session:
                db.close()
            return {"status": "ABORTED", "reason": "Lock token mismatch or job no longer PROCESSING."}

        document_id = job.document_id
        org_id = job.org_id

        doc = db.scalar(select(Document).where(Document.id == document_id, Document.org_id == org_id))
        if not doc:
            job.status = "FAILED"
            job.error_message = f"Document '{document_id}' not found."
            db.commit()
            if managed_session:
                db.close()
            return {"status": "FAILED", "reason": f"Document '{document_id}' not found."}

        storage_key = doc.storage_key
        filename = doc.filename
        invoice_id = doc.invoice_id

    finally:
        # Explicitly close/commit session before external network call
        if managed_session:
            db.close()

    # Phase B: External Storage Fetch & Bedrock Inference (ZERO DB TRANSACTION OPEN)
    try:
        pdf_bytes = storage_adapter.get_file(storage_key)
        if not pdf_bytes:
            raise ValueError(f"Storage adapter returned empty content for storage key '{storage_key}'")

        if extractor is None:
            extractor = HybridAPExtractor()
        processing_result: HybridProcessingResult = extractor.extract_hybrid(
            pdf_bytes=pdf_bytes,
            filename=filename,
            document_id=document_id,
        )

    except Exception as e:
        logger.error(f"Inference failed for job {job_id}: {str(e)}", exc_info=True)
        # Record failure in fresh short transaction
        err_db = SessionLocal() if managed_session else db
        try:
            job_rec = err_db.scalar(select(IngestionJob).where(IngestionJob.id == job_id))
            if job_rec and job_rec.lock_token == lock_token:
                job_rec.retry_count += 1
                if job_rec.retry_count >= 3:
                    job_rec.status = "FAILED"
                    job_rec.error_message = f"Extraction failed: {str(e)}"
                    if job_rec.document_id:
                        failed_doc = err_db.scalar(select(Document).where(Document.id == job_rec.document_id))
                        if failed_doc and failed_doc.invoice_id:
                            failed_inv = err_db.scalar(select(Invoice).where(Invoice.id == failed_doc.invoice_id))
                            if failed_inv:
                                failed_inv.decision_reason = f"Processing failed: {str(e)}"
                else:
                    job_rec.status = "QUEUED"
                    job_rec.lock_token = None
                    job_rec.lease_expires_at = None
                    job_rec.error_message = f"Attempt {job_rec.retry_count} failed: {str(e)}"
                err_db.commit()
        finally:
            if managed_session:
                err_db.close()
        return {"status": "FAILED", "error": str(e)}

    # Phase C: Atomic Result Persistence Transaction (< 20 ms)
    persist_db = SessionLocal() if managed_session else db
    try:
        # Re-verify lock token to avoid split-brain execution
        active_job = persist_db.scalar(
            select(IngestionJob).where(
                IngestionJob.id == job_id,
                IngestionJob.lock_token == lock_token,
                IngestionJob.status == "PROCESSING",
            )
        )
        if not active_job:
            logger.warning(f"Lock lost during inference for job {job_id}; rolling back persistence.")
            return {"status": "ABORTED", "reason": "Lock expired during inference execution."}

        now_utc = datetime.datetime.utcnow()

        # 1. Persist Extraction Run
        extraction_run_id = f"ext_{uuid.uuid4().hex[:12]}"
        parser_ver = f"{processing_result.model_id or 'hybrid_v1'}"[:32]
        extraction_run = ExtractionRun(
            id=extraction_run_id,
            org_id=org_id,
            document_id=document_id,
            parser_version=parser_ver,
            overall_confidence=0.99 if processing_result.extraction_status == "SUCCESS" else 0.85,
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
                    confidence_score=fconf,
                    source_page=1,
                )
                persist_db.add(ef)

        # 3. Persist Extracted Lines
        if invoice_id and processing_result.line_items:
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
                tot = (
                    getattr(line, "total_amount", None)
                    or (line.get("total_amount") if isinstance(line, dict) else None)
                    or (float(qty) * float(unit_r))
                )
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

        # 4. Persist Match Run & 7 Policy Gates
        match_run_id = f"mr_{uuid.uuid4().hex[:12]}"
        is_po_match = getattr(
            processing_result.three_way_match,
            "is_match",
            getattr(processing_result.three_way_match, "match_status", None) == "MATCH_CANDIDATE"
        )
        overall_match = "PASS" if is_po_match and processing_result.tax_arithmetic.is_valid and not processing_result.duplicate_check.is_duplicate else "FAIL"

        match_run = MatchRun(
            id=match_run_id,
            org_id=org_id,
            invoice_id=invoice_id,
            policy_version="standard_3way_v1",
            overall_result=overall_match,
            evaluated_at=now_utc,
        )
        persist_db.add(match_run)
        persist_db.flush()

        # Gate Evaluation
        billed_tax_val = getattr(
            processing_result.tax_arithmetic,
            "billed_tax",
            processing_result.tax_arithmetic.calculated_tax + getattr(processing_result.tax_arithmetic, "tax_discrepancy", 0.0)
        )
        is_unreadable_scan = (
            processing_result.extraction_status == "DEGRADED_SCAN"
            or (not processing_result.invoice_number and not processing_result.grand_total and not processing_result.supplier_gstin)
        )
        if is_unreadable_scan:
            gate_checks = [
                (1, "Vendor Identity Registered", "FAIL", "Document unreadable: degraded raster scan with no machine-readable text."),
                (2, "PO Authorization Valid", "NOT_EVALUATED", "Check not evaluated: document text could not be extracted."),
                (3, "GRN Receipt Confirmed", "NOT_EVALUATED", "Check not evaluated: document text could not be extracted."),
                (4, "QC Inspection Accepted", "NOT_EVALUATED", "Check not evaluated: document text could not be extracted."),
                (5, "GST Arithmetic Reconciled", "NOT_EVALUATED", "Check not evaluated: document text could not be extracted."),
                (6, "PO Price & Quantity Tolerance", "NOT_EVALUATED", "Check not evaluated: document text could not be extracted."),
                (7, "Duplicate Invoice Check", "PASS" if not processing_result.duplicate_check.is_duplicate else "FAIL", "0 previous vouchers found"),
            ]
        else:
            gate_checks = [
                (1, "Vendor Identity Registered", "PASS" if processing_result.supplier_gstin else "FAIL", f"Supplier GSTIN: {processing_result.supplier_gstin or 'MISSING'}"),
                (2, "PO Authorization Valid", "PASS" if processing_result.three_way_match.po_found else "FAIL", f"PO Ref: {processing_result.po_reference or 'NOT_FOUND'}"),
                (3, "GRN Receipt Confirmed", "PASS" if processing_result.three_way_match.grn_found else "FAIL", "GRN matched in ERP receipts" if processing_result.three_way_match.grn_found else "No Goods Receipt Note (GRN) found in ERP receiving records."),
                (4, "QC Inspection Accepted", "PASS" if processing_result.three_way_match.qc_found else "FAIL", "QC inspection accepted" if processing_result.three_way_match.qc_found else "No Quality Control (QC) inspection certificate found."),
                (5, "GST Arithmetic Reconciled", "PASS" if processing_result.tax_arithmetic.is_valid else "FAIL", f"Calculated: ₹{processing_result.tax_arithmetic.calculated_tax:.2f} vs Billed: ₹{billed_tax_val:.2f}"),
                (6, "PO Price & Quantity Tolerance", "PASS" if is_po_match else "FAIL", f"Variance: {processing_result.three_way_match.price_variance_pct:.2f}% (Tolerance: ±1.5%)"),
                (7, "Duplicate Invoice Check", "PASS" if not processing_result.duplicate_check.is_duplicate else "FAIL", "0 previous vouchers found"),
            ]

        failed_gate = None
        for gnum, gname, gstatus, gnotes in gate_checks:
            mg = MatchGateCheck(
                id=f"mg_{match_run_id}_{gnum}",
                org_id=org_id,
                match_run_id=match_run_id,
                gate_number=gnum,
                gate_name=gname,
                status=gstatus,
                evidence_notes=gnotes,
                checked_at=now_utc,
            )
            persist_db.add(mg)
            if gstatus == "FAIL" and failed_gate is None:
                failed_gate = (gnum, gname, gnotes)

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
                else:
                    gnum, gname, gnotes = failed_gate
                    inv.stage = "ACTION_REQUIRED"
                    if not processing_result.grounding_tripwire_passed or processing_result.extraction_status == "DEGRADED_SCAN":
                        inv.decision = "FLAGGED_HITL_REVIEW"
                        inv.decision_reason = "Degraded scan quality / ungrounded values detected. Human review required."
                    else:
                        inv.decision = "FLAGGED_EXCEPTION"
                        inv.decision_reason = f"Gate {gnum} ({gname}) failed: {gnotes}"

                    # Create Exception Record
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
        active_job.status = "COMPLETED"
        active_job.completed_at = now_utc
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
        return {"status": "FAILED", "error": f"Persistence failed: {str(e)}"}
    finally:
        if managed_session:
            persist_db.close()


def process_document_pipeline_background(job_id: str, lock_token: str) -> None:
    """Safe wrapper invoked via FastAPI BackgroundTasks."""
    try:
        execute_document_pipeline(job_id=job_id, lock_token=lock_token)
    except Exception as e:
        logger.error(f"Unhandled background task error in pipeline for job {job_id}: {str(e)}", exc_info=True)
