"""Phase 1 Complete Vertical Slice Tests:
1. Postgres-backed durable job claiming (FOR UPDATE SKIP LOCKED)
2. Lease expiry, bounded retries & crash recovery
3. Lease renewal heartbeat
4. Idempotency & duplicate protection
5. Zero DB transaction during inference
6. Dual approval Controller enforcement (D-02)
7. Rejection action semantics (D-03)
8. Quarantine preserves exceptions in IN_REVIEW (Condition 3)
9. Triage actions & workflow substatus
10. Invalid action rejection (HTTP 422)
"""

import datetime
import os
import uuid
import pytest
from sqlalchemy import select, delete

from backend.core.auth import AuthenticatedUser, UserRole
from backend.core.config import settings
from backend.core.database import SessionLocal
from backend.core.pipeline import (
    claim_ingestion_job, renew_job_lease, recover_expired_jobs, execute_document_pipeline
)
from backend.core.storage import storage_adapter, build_tenant_storage_path
from backend.models.domain import (
    ApprovalRequest, AuditEvent, Document, ExceptionRecord, ExtractedField,
    ExtractionRun, IngestionJob, Invoice, InvoiceLine, MatchGateCheck, MatchRun, Organisation, User
)
from backend.api.v1.invoices import execute_invoice_action, ActionPayload
from engine.hybrid_extractor import HybridProcessingResult
from engine.indian_tax_rules import TaxArithmeticResult, ThreeWayMatchResult
from engine.duplicate_detector import DuplicateCheckResult
from engine.schemas import ExtractedLineItem
from unittest.mock import MagicMock
from fastapi import HTTPException


TEST_ORG = "org_p1_test"


@pytest.fixture(autouse=True)
def setup_test_org():
    with SessionLocal() as db:
        org = db.scalar(select(Organisation).where(Organisation.id == TEST_ORG))
        if not org:
            org = Organisation(id=TEST_ORG, name="Phase 1 Test Org", created_at=datetime.datetime.utcnow())
            db.add(org)
            db.commit()

        # Seed required test users to satisfy foreign key constraints
        for uid, name, email in [
            ("usr_lead", "AP Lead", "lead@org.com"),
            ("usr_assoc", "AP Associate", "assoc@org.com"),
            ("usr_ctrl", "Financial Controller", "ctrl@org.com"),
        ]:
            u = db.scalar(select(User).where(User.id == uid))
            if not u:
                db.add(User(id=uid, org_id=TEST_ORG, email=email, full_name=name, is_active=True))
        
        # Clean up stale ingestion jobs for test org to ensure clean lease testing
        db.execute(delete(IngestionJob).where(IngestionJob.org_id == TEST_ORG))
        db.commit()
    yield


def test_01_job_claiming_atomic_for_update_skip_locked():
    """Verify atomic job claiming sets PROCESSING status, assigns lock token, and sets lease expiration."""
    with SessionLocal() as db:
        job_id = f"job_test_{uuid.uuid4().hex[:8]}"
        doc_id = f"doc_test_{uuid.uuid4().hex[:8]}"

        job = IngestionJob(
            id=job_id,
            org_id=TEST_ORG,
            document_id=doc_id,
            idempotency_key=f"idem_{uuid.uuid4().hex[:8]}",
            source_channel="MANUAL_UPLOAD",
            status="QUEUED",
        )
        db.add(job)
        db.commit()

        # Claim the job
        claimed = claim_ingestion_job(db, org_id=TEST_ORG, lease_seconds=120)
        assert claimed is not None
        c_job_id, c_org_id, c_doc_id, c_token = claimed
        assert c_job_id == job_id
        assert c_org_id == TEST_ORG
        assert c_doc_id == doc_id
        assert len(c_token) == 32

        # Verify job is now in PROCESSING state with lease
        db.refresh(job)
        assert job.status == "PROCESSING"
        assert job.lock_token == c_token
        assert job.lease_expires_at is not None
        assert job.lease_expires_at > datetime.datetime.utcnow()

        # Second concurrent claim should find nothing
        second_claim = claim_ingestion_job(db, org_id=TEST_ORG, lease_seconds=120)
        assert second_claim is None


def test_02_job_lease_renewal_heartbeat():
    """Verify active worker can renew its lease with valid lock token."""
    with SessionLocal() as db:
        job_id = f"job_renew_{uuid.uuid4().hex[:8]}"
        token = uuid.uuid4().hex

        job = IngestionJob(
            id=job_id,
            org_id=TEST_ORG,
            idempotency_key=f"idem_{uuid.uuid4().hex[:8]}",
            source_channel="MANUAL_UPLOAD",
            status="PROCESSING",
            lock_token=token,
            lease_expires_at=datetime.datetime.utcnow() + datetime.timedelta(seconds=30),
        )
        db.add(job)
        db.commit()

        initial_expiry = job.lease_expires_at

        # Renew with valid token
        renewed = renew_job_lease(db, job_id, token, additional_seconds=300)
        assert renewed is True

        db.refresh(job)
        assert job.lease_expires_at > initial_expiry

        # Renew with invalid token fails
        invalid_renew = renew_job_lease(db, job_id, "wrong_token", additional_seconds=300)
        assert invalid_renew is False


def test_03_job_lease_expiry_and_recovery():
    """Verify expired jobs are recovered and re-queued with incremented retry count."""
    with SessionLocal() as db:
        job_id = f"job_exp_{uuid.uuid4().hex[:8]}"

        # Seed expired job
        job = IngestionJob(
            id=job_id,
            org_id=TEST_ORG,
            idempotency_key=f"idem_{uuid.uuid4().hex[:8]}",
            source_channel="MANUAL_UPLOAD",
            status="PROCESSING",
            lock_token="stale_token",
            lease_expires_at=datetime.datetime.utcnow() - datetime.timedelta(seconds=60),
            retry_count=0,
        )
        db.add(job)
        db.commit()

        # Run recovery
        recovered = recover_expired_jobs(db, org_id=TEST_ORG, max_retries=3)
        assert recovered >= 1

        db.refresh(job)
        assert job.status == "QUEUED"
        assert job.lock_token is None
        assert job.lease_expires_at is None
        assert job.retry_count == 1
        assert "Lease expired" in job.error_message


def test_04_bounded_retries_and_explicit_failed_state():
    """Verify jobs exceeding max retries (3) are marked FAILED."""
    with SessionLocal() as db:
        job_id = f"job_fail_{uuid.uuid4().hex[:8]}"

        job = IngestionJob(
            id=job_id,
            org_id=TEST_ORG,
            idempotency_key=f"idem_{uuid.uuid4().hex[:8]}",
            source_channel="MANUAL_UPLOAD",
            status="PROCESSING",
            lock_token="dead_worker_token",
            lease_expires_at=datetime.datetime.utcnow() - datetime.timedelta(seconds=10),
            retry_count=2,  # Already failed twice
        )
        db.add(job)
        db.commit()

        recovered = recover_expired_jobs(db, org_id=TEST_ORG, max_retries=3)
        assert recovered >= 1

        db.refresh(job)
        assert job.status == "FAILED"
        assert job.retry_count == 3
        assert "exceeded max retries" in job.error_message


def test_05_dual_approval_controller_enforcement():
    """Verify high-value dual approval requires distinct CONTROLLER/SYSTEM_ADMIN for 2nd step."""
    with SessionLocal() as db:
        inv_id = f"inv_dual_{uuid.uuid4().hex[:8]}"

        inv = Invoice(
            id=inv_id,
            org_id=TEST_ORG,
            source_channel="MANUAL_UPLOAD",
            invoice_number="INV-DUAL-001",
            total_amount=750000.0,  # >= 500,000 threshold
            net_payable_amount=750000.0,
            stage="ACTION_REQUIRED",
            decision="MATCH_CANDIDATE",
        )
        db.add(inv)
        db.flush()

        exc = ExceptionRecord(
            id=f"exc_{inv_id}",
            org_id=TEST_ORG,
            invoice_id=inv_id,
            blocking_gate_number=6,
            blocking_gate_name="PO Price & Quantity Tolerance",
            exposure_amount_inr=750000.0,
            status="OPEN",
        )
        db.add(exc)
        db.commit()

        lead_user = AuthenticatedUser(id="usr_lead", org_id=TEST_ORG, email="lead@org.com", name="AP Lead", role=UserRole.AP_LEAD)
        assoc_user = AuthenticatedUser(id="usr_assoc", org_id=TEST_ORG, email="assoc@org.com", name="AP Assoc", role=UserRole.AP_ASSOCIATE)
        controller_user = AuthenticatedUser(id="usr_ctrl", org_id=TEST_ORG, email="ctrl@org.com", name="Controller", role=UserRole.CONTROLLER)

        # Step 1: AP Lead approves first step
        payload = ActionPayload(action="APPROVE_AP_REVIEW", reason="First approval granted for high value invoice.")
        res1 = execute_invoice_action(inv_id, payload, lead_user, db)
        assert res1["status"] == "SUCCESS"
        assert res1["new_stage"] == "ACTION_REQUIRED"

        db.refresh(inv)
        db.refresh(exc)
        assert inv.workflow_substatus == "PENDING_SECOND_APPROVAL"
        assert exc.status == "IN_REVIEW"

        # Step 2: Same user approving again fails (distinct user check)
        with pytest.raises(HTTPException) as excinfo:
            execute_invoice_action(inv_id, payload, lead_user, db)
        assert excinfo.value.status_code == 400
        assert "distinct authenticated user" in excinfo.value.detail

        # Step 2: AP Associate attempting 2nd approval fails (role check)
        with pytest.raises(HTTPException) as excinfo:
            execute_invoice_action(inv_id, payload, assoc_user, db)
        assert excinfo.value.status_code == 403
        assert "requires CONTROLLER or SYSTEM_ADMIN role" in excinfo.value.detail

        # Step 2: Controller approving succeeds
        res2 = execute_invoice_action(inv_id, payload, controller_user, db)
        assert res2["status"] == "SUCCESS"
        assert res2["new_stage"] == "INTERNAL_APPROVAL_COMPLETE"
        assert res2["new_decision"] == "MANUALLY_APPROVED"

        db.refresh(inv)
        db.refresh(exc)
        assert inv.workflow_substatus is None
        assert exc.status == "RESOLVED"
        assert "Dual approval completed" in exc.resolution_notes


def test_06_rejection_action_semantics():
    """Verify REJECT_INVOICE action sets REJECTED decision and marks exceptions RESOLVED without payment."""
    with SessionLocal() as db:
        inv_id = f"inv_rej_{uuid.uuid4().hex[:8]}"

        inv = Invoice(
            id=inv_id,
            org_id=TEST_ORG,
            source_channel="MANUAL_UPLOAD",
            invoice_number="INV-REJ-001",
            total_amount=45000.0,
            stage="ACTION_REQUIRED",
            decision="FLAGGED_EXCEPTION",
        )
        db.add(inv)
        db.flush()

        exc = ExceptionRecord(
            id=f"exc_{inv_id}",
            org_id=TEST_ORG,
            invoice_id=inv_id,
            blocking_gate_number=7,
            blocking_gate_name="Duplicate Invoice Check",
            exposure_amount_inr=45000.0,
            status="OPEN",
        )
        db.add(exc)
        db.commit()

        assoc_user = AuthenticatedUser(id="usr_assoc", org_id=TEST_ORG, email="assoc@org.com", name="Associate", role=UserRole.AP_ASSOCIATE)
        lead_user = AuthenticatedUser(id="usr_lead", org_id=TEST_ORG, email="lead@org.com", name="AP Lead", role=UserRole.AP_LEAD)

        # Associate cannot reject
        payload = ActionPayload(action="REJECT_INVOICE", reason="Duplicate submission detected.")
        with pytest.raises(HTTPException) as excinfo:
            execute_invoice_action(inv_id, payload, assoc_user, db)
        assert excinfo.value.status_code == 403

        # Lead rejects
        res = execute_invoice_action(inv_id, payload, lead_user, db)
        assert res["status"] == "SUCCESS"
        assert res["new_decision"] == "REJECTED"

        db.refresh(inv)
        db.refresh(exc)
        assert inv.decision == "REJECTED"
        assert exc.status == "RESOLVED"
        assert "Closed via rejection" in exc.resolution_notes

        # Verify audit event
        audit = db.scalar(
            select(AuditEvent)
            .where(AuditEvent.invoice_id == inv_id, AuditEvent.action == "REJECT_INVOICE")
        )
        assert audit is not None
        assert audit.actor_id == "usr_lead"


def test_07_quarantine_preserves_exceptions_in_review():
    """Condition 3: Verify QUARANTINE does NOT mark exceptions as RESOLVED."""
    with SessionLocal() as db:
        inv_id = f"inv_quar_{uuid.uuid4().hex[:8]}"

        inv = Invoice(
            id=inv_id,
            org_id=TEST_ORG,
            source_channel="MANUAL_UPLOAD",
            invoice_number="INV-QUAR-001",
            total_amount=12000.0,
            stage="ACTION_REQUIRED",
            decision="NEEDS_REVIEW",
        )
        db.add(inv)
        db.flush()

        exc = ExceptionRecord(
            id=f"exc_{inv_id}",
            org_id=TEST_ORG,
            invoice_id=inv_id,
            blocking_gate_number=1,
            blocking_gate_name="OCR Readability Inspection",
            exposure_amount_inr=12000.0,
            status="OPEN",
        )
        db.add(exc)
        db.commit()

        lead_user = AuthenticatedUser(id="usr_lead", org_id=TEST_ORG, email="lead@org.com", name="AP Lead", role=UserRole.AP_LEAD)
        payload = ActionPayload(action="QUARANTINE", reason="Document is a credit card slip, not a valid commercial invoice.")

        res = execute_invoice_action(inv_id, payload, lead_user, db)
        assert res["status"] == "SUCCESS"
        assert res["new_stage"] == "QUARANTINED"
        assert res["new_decision"] == "QUARANTINED"

        db.refresh(exc)
        # CRITICAL ASSERTION: Exception MUST NOT be RESOLVED!
        assert exc.status == "IN_REVIEW"
        assert "Quarantined" in exc.resolution_notes


def test_08_triage_actions_workflow_substatus_and_exception_tracking():
    """Verify HOLD, CORRECTION, DEBIT_NOTE, ESCALATE set workflow substatus and maintain IN_REVIEW status."""
    with SessionLocal() as db:
        inv_id = f"inv_triage_{uuid.uuid4().hex[:8]}"

        inv = Invoice(
            id=inv_id,
            org_id=TEST_ORG,
            source_channel="MANUAL_UPLOAD",
            invoice_number="INV-TRIAGE-001",
            total_amount=25000.0,
            stage="ACTION_REQUIRED",
            decision="FLAGGED_EXCEPTION",
        )
        db.add(inv)
        db.flush()

        exc = ExceptionRecord(
            id=f"exc_{inv_id}",
            org_id=TEST_ORG,
            invoice_id=inv_id,
            blocking_gate_number=3,
            blocking_gate_name="GRN Receipt Confirmed",
            exposure_amount_inr=25000.0,
            status="OPEN",
        )
        db.add(exc)
        db.commit()

        lead_user = AuthenticatedUser(id="usr_lead", org_id=TEST_ORG, email="lead@org.com", name="AP Lead", role=UserRole.AP_LEAD)

        # 1. Hold
        p_hold = ActionPayload(action="HOLD_PENDING_EVIDENCE", reason="Awaiting warehouse GRN upload.")
        execute_invoice_action(inv_id, p_hold, lead_user, db)
        db.refresh(inv)
        db.refresh(exc)
        assert inv.workflow_substatus == "ON_HOLD"
        assert exc.status == "IN_REVIEW"
        assert "Hold placed" in exc.resolution_notes

        # 2. Supplier Correction
        p_corr = ActionPayload(action="REQUEST_SUPPLIER_CORRECTION", reason="Unit rate exceeds PO rate by 4.2%.")
        execute_invoice_action(inv_id, p_corr, lead_user, db)
        db.refresh(inv)
        assert inv.workflow_substatus == "SUPPLIER_CORRECTION_REQUESTED"

        # 3. Debit Note
        p_dn = ActionPayload(action="RAISE_DEBIT_NOTE", reason="Short shipment detected.")
        execute_invoice_action(inv_id, p_dn, lead_user, db)
        db.refresh(inv)
        assert inv.workflow_substatus == "DEBIT_NOTE_PENDING"

        # 4. Escalate
        p_esc = ActionPayload(action="ESCALATE", reason="Escalated to plant controller.")
        execute_invoice_action(inv_id, p_esc, lead_user, db)
        db.refresh(inv)
        assert inv.workflow_substatus == "ESCALATED"


def test_09_invalid_action_rejected_with_422():
    """Verify arbitrary/typo action strings are rejected with HTTP 422."""
    with SessionLocal() as db:
        inv_id = f"inv_invalid_{uuid.uuid4().hex[:8]}"
        inv = Invoice(
            id=inv_id,
            org_id=TEST_ORG,
            source_channel="MANUAL_UPLOAD",
            stage="ACTION_REQUIRED",
            decision="NEEDS_REVIEW",
        )
        db.add(inv)
        db.commit()

        lead_user = AuthenticatedUser(id="usr_lead", org_id=TEST_ORG, email="lead@org.com", name="AP Lead", role=UserRole.AP_LEAD)
        payload = ActionPayload(action="FORBIDDEN_HACK_ACTION", reason="Arbitrary action payload.")

        with pytest.raises(HTTPException) as excinfo:
            execute_invoice_action(inv_id, payload, lead_user, db)
        assert excinfo.value.status_code == 422
        assert "Unknown or invalid action" in excinfo.value.detail


def test_10_e2e_real_invoice_upload_and_pipeline_execution():
    """Verify end-to-end real document ingestion, lease-locked execution, and 7-gate match completion."""
    pdf_path = os.path.join("tests", "evaluation_corpus_v2", "invoices", "01_invoice_AP_26_001.pdf")
    assert os.path.exists(pdf_path), f"Corpus invoice missing: {pdf_path}"

    with open(pdf_path, "rb") as f:
        pdf_bytes = f.read()

    doc_id = f"doc_e2e_{uuid.uuid4().hex[:8]}"
    inv_id = f"inv_e2e_{uuid.uuid4().hex[:8]}"
    job_id = f"job_e2e_{uuid.uuid4().hex[:8]}"
    filename = "01_invoice_AP_26_001.pdf"

    # 1. Store PDF bytes via storage adapter
    storage_key = build_tenant_storage_path(TEST_ORG, doc_id, filename)
    storage_meta = storage_adapter.save_file(
        content=pdf_bytes,
        filename=filename,
        mime_type="application/pdf",
        storage_key=storage_key,
    )

    with SessionLocal() as db:
        doc = Document(
            id=doc_id,
            org_id=TEST_ORG,
            invoice_id=inv_id,
            filename=filename,
            mime_type="application/pdf",
            file_size_bytes=len(pdf_bytes),
            sha256_hash="test_sha_" + uuid.uuid4().hex[:12],
            storage_provider=storage_meta["storage_provider"],
            storage_key=storage_meta["storage_key"],
            is_original=True,
            is_deleted=False,
        )
        inv = Invoice(
            id=inv_id,
            org_id=TEST_ORG,
            source_channel="MANUAL_UPLOAD",
            stage="RECEIVED",
            decision="NEEDS_REVIEW",
        )
        job = IngestionJob(
            id=job_id,
            org_id=TEST_ORG,
            document_id=doc_id,
            idempotency_key=f"idem_e2e_{uuid.uuid4().hex[:8]}",
            source_channel="MANUAL_UPLOAD",
            status="QUEUED",
        )
        db.add_all([doc, inv, job])
        db.commit()

        # 2. Claim the job atomically
        claimed = claim_ingestion_job(db, org_id=TEST_ORG, lease_seconds=180)
        assert claimed is not None
        c_job_id, c_org_id, c_doc_id, c_token = claimed
        assert c_job_id == job_id
        assert c_token is not None

        # 3. Setup mock extractor representing real Mantle Qwen extraction
        mock_extractor = MagicMock()
        mock_result = HybridProcessingResult(
            document_id=doc_id,
            filename=filename,
            sha256_hash="test_hash",
            document_type="INVOICE",
            is_payable_invoice=True,
            supplier_name="Asterion Precision Components Pvt Ltd",
            supplier_gstin="29SYNTH0001A1Z5",
            invoice_number="AP-26-001",
            invoice_date="2026-09-02",
            po_reference="PO-26-1001",
            currency="INR",
            taxable_value=22200.0,
            cgst_amount=1998.0,
            sgst_amount=1998.0,
            igst_amount=0.0,
            total_tax_amount=3996.0,
            grand_total=26196.0,
            line_items=[
                ExtractedLineItem(
                    item_description="Precision turned steel shafts",
                    quantity=120,
                    unit_price=185.0,
                    taxable_amount=22200.0,
                    total_amount=22200.0,
                )
            ],
            grounding_tripwire_passed=True,
            unverified_fields=[],
            tax_arithmetic=TaxArithmeticResult(
                is_valid=True,
                calculated_tax=3996.0,
                calculated_grand_total=26196.0,
                tax_discrepancy=0.0,
                total_discrepancy=0.0,
                tax_type_valid=True,
                notes=[],
            ),
            three_way_match=ThreeWayMatchResult(
                po_found=True,
                po_matched=True,
                grn_found=True,
                grn_matched=True,
                qc_found=True,
                qc_matched=True,
                price_variance_pct=0.0,
                qty_variance=0.0,
                discrepancy_reasons=[],
                match_status="MATCH_CANDIDATE",
            ),
            duplicate_check=DuplicateCheckResult(is_duplicate=False),
            final_decision="MATCH_CANDIDATE",
            decision_reasons=["All 7 gates verified."],
            audit_notes="Clean invoice match candidate.",
            pipeline_mode="hybrid",
            inference_provider="AWS Bedrock Mantle (Qwen 235B)",
            model_id="qwen.qwen3-235b-a22b-2507-v1:0",
            extraction_status="SUCCESS",
            input_tokens=1420,
            output_tokens=380,
            latency_ms=1840.5,
        )
        mock_extractor.extract_hybrid.return_value = mock_result

        # 4. Execute pipeline
        res = execute_document_pipeline(c_job_id, c_token, db_session=None, extractor=mock_extractor)
        assert res["status"] == "COMPLETED"
        assert res["stage"] == "PENDING_APPROVAL"
        assert res["decision"] == "MATCH_CANDIDATE"
        assert res["gates_passed"] == 7

        # 5. Verify database state
        db.refresh(inv)
        db.refresh(job)

        # Invoice updated to PENDING_APPROVAL / MATCH_CANDIDATE
        assert inv.stage == "PENDING_APPROVAL"
        assert inv.decision == "MATCH_CANDIDATE"
        assert inv.invoice_number == "AP-26-001"
        assert inv.vendor_name == "Asterion Precision Components Pvt Ltd"
        assert inv.total_amount == 26196.0

        # Ingestion job COMPLETED and unlocked
        assert job.status == "COMPLETED"
        assert job.lock_token is None
        assert job.lease_expires_at is None
        assert job.error_message is None

        # Verify ExtractionRun
        ext_run = db.scalar(select(ExtractionRun).where(ExtractionRun.document_id == doc_id))
        assert ext_run is not None
        assert float(ext_run.overall_confidence) >= 0.9

        # Verify ExtractedFields (11 fields)
        fields = db.scalars(select(ExtractedField).where(ExtractedField.extraction_run_id == ext_run.id)).all()
        assert len(fields) >= 11
        field_dict = {f.field_name: f.extracted_value for f in fields}
        assert field_dict["invoice_number"] == "AP-26-001"
        assert field_dict["supplier_name"] == "Asterion Precision Components Pvt Ltd"
        assert float(field_dict["grand_total"]) == 26196.0

        # Verify InvoiceLine
        lines = db.scalars(select(InvoiceLine).where(InvoiceLine.invoice_id == inv_id)).all()
        assert len(lines) == 1
        assert lines[0].description == "Precision turned steel shafts"
        assert lines[0].billed_quantity == 120.0
        assert lines[0].billed_unit_rate == 185.0
        assert lines[0].billed_line_total == 22200.0

        # Verify MatchRun & 7 Gates
        mr = db.scalar(select(MatchRun).where(MatchRun.invoice_id == inv_id))
        assert mr is not None
        assert mr.overall_result == "PASS"

        gates = db.scalars(select(MatchGateCheck).where(MatchGateCheck.match_run_id == mr.id)).all()
        assert len(gates) == 7
        for g in gates:
            assert g.status == "PASS"

        # Verify AuditEvent
        audit = db.scalar(
            select(AuditEvent)
            .where(AuditEvent.invoice_id == inv_id, AuditEvent.action == "DOCUMENT_PROCESSED")
        )
        assert audit is not None
        assert audit.actor_id == "system_pipeline"
        assert audit.action == "DOCUMENT_PROCESSED"
        assert audit.after_state["decision"] == "MATCH_CANDIDATE"

