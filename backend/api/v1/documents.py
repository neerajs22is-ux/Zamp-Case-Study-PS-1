"""Documents API: Ingestion, Presigned URL Generation, Integrity Verification & Lifecycle.

Enforces:
1. Strict tenant isolation on document path: org_{org_id}/invoices/{document_id}/{filename}.
2. MIME validation (application/pdf) and magic-byte header validation (%PDF-).
3. Maximum file size enforcement (<= 50 MB, matching Supabase Free plan).
4. SHA-256 calculation and duplicate detection within tenant.
5. Encrypted private object storage persistence with compensating rollback on DB error.
6. Short-lived presigned URL generation (TTL <= 300s).
7. Cross-tenant access denial (HTTP 403).
8. Soft deletion preserving physical storage vs authorized permanent purge.
"""

from __future__ import annotations

import datetime
import hashlib
import logging
import os
import uuid
from typing import Any, Dict, List, Optional
from urllib.parse import quote

from fastapi import (
    APIRouter, BackgroundTasks, Depends, File, HTTPException, Query, Response, UploadFile, status
)
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.core.auth import (
    AuthenticatedUser, UserRole, require_active_membership, require_role
)
from backend.core.config import settings
from backend.core.database import get_db
from backend.core.storage import (
    build_tenant_storage_path, storage_adapter
)
from backend.models.domain import (
    ApprovalRequest, AuditEvent, Document, IngestionJob, Invoice, Organisation
)
from backend.core.pipeline import (
    claim_ingestion_job, recover_expired_jobs, process_document_pipeline_background
)
from engine.pdf_safety import InvalidPDF, extract_pdf_pages
from backend.core.processing_events import append_checkpoint

logger = logging.getLogger("ap_command_center.documents")

router = APIRouter(prefix="/documents", tags=["Documents & Ingestion"])


class DocumentMetadataResponse(BaseModel):
    id: str
    org_id: str
    invoice_id: Optional[str]
    filename: str
    mime_type: str
    file_size_bytes: int
    sha256_hash: str
    storage_provider: str
    storage_key: str
    is_original: bool
    is_deleted: bool
    deleted_at: Optional[str] = None
    uploaded_at: str


@router.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    current_user: AuthenticatedUser = Depends(
        require_role([UserRole.AP_ASSOCIATE, UserRole.AP_LEAD, UserRole.CONTROLLER, UserRole.SYSTEM_ADMIN])
    ),
    db: Optional[Session] = Depends(get_db),
) -> Dict[str, Any]:
    """Authenticated tenant document upload with full integrity & isolation guarantees."""
    if db is None:
        raise HTTPException(status_code=503, detail="Database not connected; document was not queued.")
    # 1. MIME & Filename Check
    filename = file.filename or "unknown.pdf"
    filename = filename.replace("\\", "/").rsplit("/", 1)[-1]
    if len(filename) > 200 or any(ord(c) < 32 or ord(c) == 127 for c in filename):
        raise HTTPException(status_code=400, detail="Invalid document filename.")
    if not filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported file format: Only PDF documents are supported for ingestion.",
        )
    if file.content_type and file.content_type not in ("application/pdf", "application/octet-stream"):
        raise HTTPException(status_code=400, detail="Unsupported document content type.")

    # 2. Read bytes in chunks with hard memory limit
    CHUNK_SIZE = 1024 * 1024  # 1 MB
    max_bytes = settings.MAX_UPLOAD_FILE_SIZE_BYTES
    chunks = []
    total_read = 0

    while True:
        chunk = await file.read(CHUNK_SIZE)
        if not chunk:
            break
        total_read += len(chunk)
        if total_read > max_bytes:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File exceeds maximum permitted size of {max_bytes // (1024 * 1024)} MB.",
            )
        chunks.append(chunk)

    if total_read == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty.",
        )

    content = b"".join(chunks)

    # 3. Magic bytes validation
    if not content.startswith(b"%PDF-"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Corrupted file: Invalid PDF header signature.",
        )

    try:
        # Upload is async; keep bounded parser work off the ASGI event loop.
        from starlette.concurrency import run_in_threadpool
        await run_in_threadpool(extract_pdf_pages, content)
    except InvalidPDF as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    # 4. SHA-256 calculation
    sha256_hash = hashlib.sha256(content).hexdigest()

    # 5. Tenant duplicate detection
    if db is not None:
        # Serialize tenant intake on PostgreSQL: duplicates and queue limits must
        # be checked in the same transaction as persistence, not raced by tabs.
        if not db.scalar(select(Organisation).where(Organisation.id == current_user.org_id).with_for_update()):
            raise HTTPException(status_code=403, detail="Workspace unavailable.")
        existing = db.execute(
            select(Document).where(
                Document.org_id == current_user.org_id,
                Document.sha256_hash == sha256_hash,
                Document.is_deleted == False,
            )
        ).scalar_one_or_none()

        if existing:
            return JSONResponse(
                status_code=status.HTTP_409_CONFLICT,
                content={
                    "status": "DUPLICATE_DETECTED",
                    "detail": f"Duplicate document detected: file '{existing.filename}' with identical SHA-256 hash already exists in this organisation.",
                    "document_id": existing.id,
                    "invoice_id": existing.invoice_id,
                    "sha256": sha256_hash,
                },
            )

        pending = db.scalar(select(func.count(IngestionJob.id)).where(
            IngestionJob.org_id == current_user.org_id,
            IngestionJob.status.in_(["QUEUED", "PROCESSING"]))) or 0
        if pending >= settings.MAX_PENDING_UPLOADS_PER_TENANT:
            raise HTTPException(status_code=429, detail="Workspace processing queue is full. Retry after pending invoices finish.", headers={"Retry-After": "30"})

    # 6. Build deterministic tenant-isolated storage path
    doc_id = f"doc_{uuid.uuid4().hex[:12]}"
    inv_id = f"inv_{uuid.uuid4().hex[:12]}"
    job_id = f"job_{uuid.uuid4().hex[:12]}"
    storage_path = build_tenant_storage_path(current_user.org_id, doc_id, filename)

    # 7. Upload to object storage
    try:
        storage_meta = storage_adapter.save_file(
            content=content,
            filename=filename,
            mime_type="application/pdf",
            storage_key=storage_path,
        )
    except Exception as exc:
        logger.error("Storage adapter save_file failed (%s)", type(exc).__name__)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Secure storage failed. Document was not queued; retry or contact an administrator.",
        )

    # 8. Persist to database with compensating rollback
    if db is not None:
        try:
            doc = Document(
                id=doc_id,
                org_id=current_user.org_id,
                invoice_id=inv_id,
                filename=filename,
                mime_type="application/pdf",
                file_size_bytes=len(content),
                sha256_hash=sha256_hash,
                storage_provider=storage_meta["storage_provider"],
                storage_key=storage_meta["storage_key"],
                is_original=True,
                is_deleted=False,
            )
            db.add(doc)

            invoice = Invoice(
                id=inv_id,
                org_id=current_user.org_id,
                source_channel="MANUAL_UPLOAD",
                stage="RECEIVED",
                decision="NEEDS_REVIEW",
                decision_reason="Uploaded via manual intake. Awaiting pipeline execution.",
                owner_user_id=current_user.id,
            )
            db.add(invoice)

            job = IngestionJob(
                id=job_id,
                org_id=current_user.org_id,
                document_id=doc_id,
                idempotency_key=f"upload_{sha256_hash}_{uuid.uuid4().hex[:6]}",
                source_channel="MANUAL_UPLOAD",
                status="QUEUED",
            )
            db.add(job)

            db.flush()
            append_checkpoint(db, job, 'INTAKE', 'QUEUED',
                f"Authenticated document upload: {filename}", attempt=0, invoice_id=inv_id,
                actor_id=current_user.id, actor_role=current_user.role.value,
                action='DOCUMENT_UPLOADED', source_reference=storage_meta['storage_key'])
            db.commit()

        except Exception as exc:
            db.rollback()
            # COMPENSATING ROLLBACK: delete orphaned object from storage
            try:
                storage_adapter.delete_file(storage_meta["storage_key"])
                logger.info(f"Compensating cleanup executed: deleted orphaned object {storage_meta['storage_key']}")
            except Exception as cleanup_err:
                logger.error(f"Compensating cleanup failed for {storage_meta['storage_key']}: {cleanup_err}")

            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Document ingestion could not be committed. Retry or contact an administrator.",
            )

        # After commit, dispatch failure must not remove the accepted evidence.
        if background_tasks is not None and os.getenv("ENABLE_BACKGROUND_PIPELINE", "true").lower() == "true":
            try:
                claimed = claim_ingestion_job(db, org_id=current_user.org_id, job_id=job.id)
                if claimed:
                    c_job_id, c_org_id, c_doc_id, c_token = claimed
                    background_tasks.add_task(process_document_pipeline_background, c_job_id, c_token, c_org_id)
            except Exception:
                db.rollback()
                logger.error("Accepted document remains queued after dispatch failure")

    return {
        "status": "QUEUED",
        "document_id": doc_id,
        "invoice_id": inv_id,
        "filename": filename,
        "sha256": sha256_hash,
        "size_bytes": len(content),
        "storage_provider": storage_meta["storage_provider"],
        "storage_key": storage_meta["storage_key"],
        "message": "File received, verified and queued for processing.",
    }


@router.post("/process-next")
def process_next_document(
    background_tasks: BackgroundTasks,
    current_user: AuthenticatedUser = Depends(require_role([
        UserRole.AP_ASSOCIATE, UserRole.AP_LEAD, UserRole.CONTROLLER, UserRole.SYSTEM_ADMIN,
    ])),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Resume one durable tenant job after restart or transient provider failure."""
    if db is None:
        raise HTTPException(status_code=503, detail="Database not connected.")
    claimed = claim_ingestion_job(db, org_id=current_user.org_id)
    if not claimed:
        return {"status": "NO_QUEUED_JOB"}
    job_id, org_id, document_id, lock_token = claimed
    background_tasks.add_task(process_document_pipeline_background, job_id, lock_token, org_id)
    return {"status": "PROCESSING", "job_id": job_id, "document_id": document_id}


@router.get("", response_model=List[DocumentMetadataResponse])
def list_documents(
    include_deleted: bool = False,
    current_user: AuthenticatedUser = Depends(require_active_membership),
    db: Session = Depends(get_db),
) -> List[DocumentMetadataResponse]:
    """Lists documents belonging to the authenticated user's tenant."""
    query = select(Document).where(Document.org_id == current_user.org_id)
    if not include_deleted:
        query = query.where(Document.is_deleted == False)
    query = query.order_by(Document.uploaded_at.desc())

    records = db.execute(query).scalars().all()
    return [
        DocumentMetadataResponse(
            id=d.id,
            org_id=d.org_id,
            invoice_id=d.invoice_id,
            filename=d.filename,
            mime_type=d.mime_type,
            file_size_bytes=d.file_size_bytes,
            sha256_hash=d.sha256_hash,
            storage_provider=d.storage_provider,
            storage_key=d.storage_key,
            is_original=d.is_original,
            is_deleted=d.is_deleted,
            deleted_at=d.deleted_at.isoformat() + "Z" if d.deleted_at else None,
            uploaded_at=d.uploaded_at.isoformat() + "Z",
        )
        for d in records
    ]


@router.get("/{document_id}", response_model=DocumentMetadataResponse)
def get_document_metadata(
    document_id: str,
    current_user: AuthenticatedUser = Depends(require_active_membership),
    db: Session = Depends(get_db),
) -> DocumentMetadataResponse:
    """Retrieves document metadata with cross-tenant denial."""
    doc = db.execute(select(Document).where(Document.id == document_id)).scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")

    if doc.org_id != current_user.org_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: Cross-tenant document access is prohibited.",
        )

    if doc.is_deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document has been soft-deleted.")

    return DocumentMetadataResponse(
        id=doc.id,
        org_id=doc.org_id,
        invoice_id=doc.invoice_id,
        filename=doc.filename,
        mime_type=doc.mime_type,
        file_size_bytes=doc.file_size_bytes,
        sha256_hash=doc.sha256_hash,
        storage_provider=doc.storage_provider,
        storage_key=doc.storage_key,
        is_original=doc.is_original,
        is_deleted=doc.is_deleted,
        deleted_at=doc.deleted_at.isoformat() + "Z" if doc.deleted_at else None,
        uploaded_at=doc.uploaded_at.isoformat() + "Z",
    )


@router.get("/{document_id}/signed-url")
def get_document_signed_url(
    document_id: str,
    expires_in: int = Query(default=300, ge=1, le=300),
    current_user: AuthenticatedUser = Depends(require_active_membership),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Generates a short-lived presigned URL (TTL <= 300s) with cross-tenant check."""
    doc = db.execute(select(Document).where(Document.id == document_id)).scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")

    if doc.org_id != current_user.org_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: Cross-tenant document access is prohibited.",
        )

    if doc.is_deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document has been soft-deleted.")

    effective_ttl = min(max(expires_in, 1), 300)
    try:
        signed_url = storage_adapter.generate_signed_url(doc.storage_key, expires_in=effective_ttl)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Document access URL could not be generated.",
        )

    return {
        "document_id": doc.id,
        "storage_key": doc.storage_key,
        "signed_url": signed_url,
        "expires_in": effective_ttl,
    }


@router.get("/{document_id}/download")
def download_document(
    document_id: str,
    current_user: AuthenticatedUser = Depends(require_active_membership),
    db: Session = Depends(get_db),
) -> Response:
    """Streams document bytes after verifying SHA-256 cryptographic integrity."""
    doc = db.execute(select(Document).where(Document.id == document_id)).scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")

    if doc.org_id != current_user.org_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: Cross-tenant document access is prohibited.",
        )

    if doc.is_deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document has been soft-deleted.")

    try:
        content = storage_adapter.get_file(doc.storage_key)
    except FileNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Physical object not found in storage.")
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Document storage is temporarily unavailable.")

    # Cryptographic integrity check
    calculated_hash = hashlib.sha256(content).hexdigest()
    if calculated_hash != doc.sha256_hash:
        logger.critical(
            f"INTEGRITY VIOLATION: Document {doc.id} hash mismatch. Expected {doc.sha256_hash}, calculated {calculated_hash}."
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Document integrity verification failed: SHA-256 mismatch detected.",
        )

    return Response(
        content=content,
        media_type=doc.mime_type or "application/pdf",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(doc.filename, safe='')}", "Cache-Control": "no-store"},
    )


@router.get("/{document_id}/preview")
def preview_document(
    document_id: str,
    current_user: AuthenticatedUser = Depends(require_active_membership),
    db: Session = Depends(get_db),
) -> Response:
    """Returns inline document response for in-browser preview."""
    doc = db.execute(select(Document).where(Document.id == document_id)).scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")

    if doc.org_id != current_user.org_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: Cross-tenant document access is prohibited.",
        )

    if doc.is_deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document has been soft-deleted.")

    try:
        content = storage_adapter.get_file(doc.storage_key)
    except FileNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Physical object not found in storage.")
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Document storage is temporarily unavailable.")

    if hashlib.sha256(content).hexdigest() != doc.sha256_hash:
        raise HTTPException(status_code=500, detail="Document integrity verification failed: SHA-256 mismatch detected.")

    return Response(
        content=content,
        media_type=doc.mime_type or "application/pdf",
        headers={"Content-Disposition": f"inline; filename*=UTF-8''{quote(doc.filename, safe='')}", "Cache-Control": "no-store", "Content-Security-Policy": "sandbox"},
    )


@router.delete("/{document_id}")
def soft_delete_document(
    document_id: str,
    reason: Optional[str] = Query(default=None),
    current_user: AuthenticatedUser = Depends(
        require_role([UserRole.AP_ASSOCIATE, UserRole.AP_LEAD, UserRole.CONTROLLER, UserRole.SYSTEM_ADMIN])
    ),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Soft deletes document record while preserving physical file in storage."""
    doc = db.execute(select(Document).where(Document.id == document_id)).scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")

    if doc.org_id != current_user.org_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: Cross-tenant document access is prohibited.",
        )

    if doc.is_deleted:
        return {
            "status": "ALREADY_SOFT_DELETED",
            "document_id": doc.id,
            "is_deleted": True,
            "deleted_at": doc.deleted_at.isoformat() + "Z" if doc.deleted_at else None,
        }

    now = datetime.datetime.utcnow()
    doc.is_deleted = True
    doc.deleted_at = now
    doc.deleted_by_user_id = current_user.id

    # Append immutable audit event
    audit = AuditEvent(
        id=f"evt_{uuid.uuid4().hex[:12]}",
        invoice_id=doc.invoice_id,
        org_id=current_user.org_id,
        actor_id=current_user.id,
        actor_role=current_user.role.value if current_user.role else "UNKNOWN",
        action="DOCUMENT_SOFT_DELETED",
        reason=reason or f"Soft deleted document {doc.filename}",
        source_reference=doc.storage_key,
    )
    db.add(audit)
    db.commit()

    return {
        "status": "SOFT_DELETED",
        "document_id": doc.id,
        "is_deleted": True,
        "deleted_at": now.isoformat() + "Z",
    }


@router.post("/{document_id}/purge")
def permanently_purge_document(
    document_id: str,
    reason: Optional[str] = Query(default=None),
    current_user: AuthenticatedUser = Depends(require_role([UserRole.SYSTEM_ADMIN, UserRole.CONTROLLER])),
    db: Session = Depends(get_db),
) -> Any:
    """Permanently purges document under strict dual-control authorization and retention eligibility.

    Enforces:
    1. Cross-tenant access denial (HTTP 403).
    2. Must be soft-deleted before permanent purge can be initiated.
    3. If enterprise purge policy is disabled or unconfigured, returns honest BLOCKED response.
    4. Verifies statutory retention eligibility (DOCUMENT_RETENTION_DAYS).
    5. Requires two distinct authorized approvers (SYSTEM_ADMIN or CONTROLLER).
    6. Preserves append-only immutable audit trail recording both approvers and timestamps.
    7. Deletes physical storage file and removes document row without cascading audit deletion.
    """
    doc = db.execute(select(Document).where(Document.id == document_id)).scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")

    if doc.org_id != current_user.org_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: Cross-tenant document access is prohibited.",
        )

    # 1. Soft-deleted check
    if not doc.is_deleted:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Document must be soft-deleted before permanent purge can be initiated.",
        )

    # 2. Check if permanent purge policy is configured / enabled
    if not settings.ENABLE_PERMANENT_PURGE:
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={
                "status": "BLOCKED",
                "detail": (
                    "Permanent purge is BLOCKED: Enterprise document purge policy is not enabled. "
                    "Statutory financial records are protected by mandatory retention (Companies Act 2013 s.128, GST Act s.36)."
                ),
                "retention_policy_active": True,
            },
        )

    # 3. Check statutory retention eligibility
    now = datetime.datetime.utcnow()
    if doc.deleted_at:
        days_retained = (now - doc.deleted_at).days
        if days_retained < settings.DOCUMENT_RETENTION_DAYS:
            return JSONResponse(
                status_code=status.HTTP_409_CONFLICT,
                content={
                    "status": "BLOCKED",
                    "detail": (
                        f"Permanent purge is BLOCKED: Document has not reached retention eligibility "
                        f"({days_retained} days retained, {settings.DOCUMENT_RETENTION_DAYS} days required under statutory retention)."
                    ),
                    "retention_eligible": False,
                    "days_retained": days_retained,
                    "required_retention_days": settings.DOCUMENT_RETENTION_DAYS,
                },
            )

    # 4. Check dual-approval workflow
    approval = None
    if doc.invoice_id:
        approval = db.execute(
            select(ApprovalRequest).where(
                ApprovalRequest.invoice_id == doc.invoice_id,
                ApprovalRequest.org_id == current_user.org_id,
            )
        ).scalars().first()

    if not approval or approval.status != "PENDING_SECOND_APPROVAL":
        # Record First Approval
        new_appr = ApprovalRequest(
            id=f"appr_{uuid.uuid4().hex[:12]}",
            org_id=current_user.org_id,
            invoice_id=doc.invoice_id or f"inv_doc_{doc.id}",
            requires_dual_approval=True,
            first_approver_id=current_user.id,
            first_approved_at=now,
            status="PENDING_SECOND_APPROVAL",
        )
        db.add(new_appr)
        db.commit()
        return JSONResponse(
            status_code=status.HTTP_202_ACCEPTED,
            content={
                "status": "PENDING_SECOND_APPROVAL",
                "document_id": doc.id,
                "first_approver_id": current_user.id,
                "first_approved_at": now.isoformat() + "Z",
                "message": "First purge approval recorded. Permanent purge cannot be executed by a single user and requires a second distinct authorized approver.",
            },
        )

    # Approval exists with status PENDING_SECOND_APPROVAL
    if current_user.id == approval.first_approver_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Dual-control violation: First approver cannot provide second approval. Permanent purge must be confirmed by a distinct authorized approver.",
        )

    # Second distinct approver confirmed
    first_approver_id = approval.first_approver_id
    first_approved_at = approval.first_approved_at
    approval.second_approver_id = current_user.id
    approval.second_approved_at = now
    approval.status = "APPROVED"

    # 5. Append immutable audit event capturing both approvers and timestamps
    audit = AuditEvent(
        id=f"evt_{uuid.uuid4().hex[:12]}",
        invoice_id=doc.invoice_id,
        org_id=current_user.org_id,
        actor_id=current_user.id,
        actor_role=current_user.role.value if current_user.role else "UNKNOWN",
        action="DOCUMENT_PERMANENTLY_PURGED",
        reason=f"Dual-control permanent purge approved by {first_approver_id} and {current_user.id}: {reason or 'Statutory retention expired purge'}",
        source_reference=doc.storage_key,
        before_state={
            "document_id": doc.id,
            "filename": doc.filename,
            "sha256": doc.sha256_hash,
            "first_approver_id": first_approver_id,
            "first_approved_at": first_approved_at.isoformat() + "Z" if first_approved_at else None,
            "second_approver_id": current_user.id,
            "second_approved_at": now.isoformat() + "Z",
            "retention_eligible": True,
        },
    )
    db.add(audit)

    # 6. Delete physical file from storage
    deleted_from_storage = storage_adapter.delete_file(doc.storage_key)

    # 7. Remove document record from database (audit record is strictly preserved)
    db.delete(doc)
    db.commit()

    return {
        "status": "PERMANENTLY_PURGED",
        "document_id": document_id,
        "first_approver_id": first_approver_id,
        "first_approved_at": first_approved_at.isoformat() + "Z" if first_approved_at else None,
        "second_approver_id": current_user.id,
        "second_approved_at": now.isoformat() + "Z",
        "purged_from_storage": deleted_from_storage,
    }
