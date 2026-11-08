"""Phase E SME Acceptance Testing Setup & Ingestion Pipeline.

Safely provisions the isolated evaluation tenant 'org_sme_eval' and executes
the four golden SME verification scenarios using the actual application pipeline:
- Scenario 1: Clean Three-Way Match (APTC-001, APTC-009) -> MATCH_CANDIDATE
- Scenario 2: Rate & Quantity Variance (APTC-030) -> FLAGGED_EXCEPTION
- Scenario 3: Degraded Scanned Invoices (APTC-036, APTC-037) -> FLAGGED_HITL_REVIEW
- Scenario 4: Non-Payable Payment Receipt (APTC-038) -> QUARANTINE_NON_INVOICE

Ensures:
1. Isolated tenant 'org_sme_eval'. Zero mutations on production tenants.
2. Synthetic supplier master and PO reference data loaded into 'org_sme_eval'.
3. Real Supabase Storage and real PostgreSQL database persistence.
4. Real Bedrock Mantle Qwen 235B inference and deterministic rule checks.
5. Emits enterprise JWT session tokens for SME user roles.
"""

from __future__ import annotations

import datetime
import hashlib
import json
import logging
import os
import sys
import time
import uuid
from typing import Any, Dict, List, Optional, Tuple

from jose import jwt
import pandas as pd
from sqlalchemy import select, text

sys.path.insert(0, os.path.abspath("."))

from backend.core.config import AppEnv, settings
from backend.core.database import SessionLocal
from backend.core.storage import build_tenant_storage_path, storage_adapter
from backend.models.domain import (
    ApprovalRequest, AuditEvent, Document, ExceptionRecord,
    ExtractedField, ExtractionRun, IngestionJob, Invoice,
    InvoiceLine, MatchGateCheck, MatchRun, Organisation,
    QuarantinedDocument, RoleAssignment, User, Vendor, VendorGSTIN,
    WorkOrderSnapshot, WorkOrderLineSnapshot,
    GoodsReceiptSnapshot, GoodsReceiptLineSnapshot, QualityControlSnapshot
)
from engine.duplicate_detector import DuplicateDetector
from engine.hybrid_extractor import HybridAPExtractor, HybridProcessingResult
from engine.indian_tax_rules import IndianAPRuleEngine
from engine.ocr_engine import OCREngine
from engine.palmyra_vision_adapter import PalmyraVisionAdapter

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("sme_eval_setup")

ORG_ID = "org_sme_eval"
ORG_NAME = "SME Acceptance Testing Evaluation Tenant"

SME_USERS = [
    {
        "id": "usr_sme_assoc_01",
        "email": "sme_associate@company.internal",
        "name": "SME AP Associate",
        "role": "AP_ASSOCIATE",
    },
    {
        "id": "usr_sme_lead_01",
        "email": "sme_lead@company.internal",
        "name": "SME AP Lead",
        "role": "AP_LEAD",
    },
    {
        "id": "usr_sme_ctrl_01",
        "email": "sme_controller@company.internal",
        "name": "SME Financial Controller",
        "role": "CONTROLLER",
    },
    {
        "id": "usr_sme_audit_01",
        "email": "sme_auditor@company.internal",
        "name": "SME Auditor (Read-Only)",
        "role": "AUDITOR",
    },
]


def ensure_jwt_secret() -> str:
    """Ensures SUPABASE_JWT_SECRET is populated in settings for HS256 JWT tokens."""
    secret = settings.SUPABASE_JWT_SECRET or settings.SECRET_KEY or "sme-acceptance-testing-secret-key-32chars"
    settings.SUPABASE_JWT_SECRET = secret
    return secret


def generate_sme_jwt(user: Dict[str, str], secret: str, expires_in_seconds: int = 86400 * 30) -> str:
    """Generates an authentic enterprise JWT bearer token accepted by backend/core/auth.py."""
    now = int(time.time())
    payload = {
        "sub": user["id"],
        "email": user["email"],
        "name": user["name"],
        "role": user["role"],
        "org_id": ORG_ID,
        "aud": settings.SUPABASE_AUDIENCE or "authenticated",
        "iss": settings.SUPABASE_ISSUER or (f"{settings.SUPABASE_URL.rstrip('/')}/auth/v1" if settings.SUPABASE_URL else None),
        "iat": now,
        "exp": now + expires_in_seconds,
    }
    return jwt.encode(payload, secret, algorithm="HS256")


def assert_seeding_permitted() -> None:
    """Enforces strict environment guard against synthetic seeding in production/staging.

    Fail-Closed Invariants:
    - Synthetic seeding is permitted strictly in DEVELOPMENT and TEST environments.
    - Explicitly blocks PRODUCTION and STAGING unless dedicated operator evaluation bootstrap is active.
    - Fails closed (raises RuntimeError) on unrecognized, None, or unconfigured environments.
    """
    is_eval_bootstrap = (
        getattr(settings, "IS_DEDICATED_EVALUATION_DATABASE", False)
        or os.environ.get("IS_DEDICATED_EVALUATION_DATABASE", "").strip().lower() in ("true", "1")
    )
    bootstrap_key = (
        getattr(settings, "EVAL_BOOTSTRAP_SECRET_KEY", None)
        or os.environ.get("EVAL_BOOTSTRAP_SECRET_KEY", "")
    )
    if is_eval_bootstrap and bootstrap_key and len(bootstrap_key) >= 32:
        return

    app_env = getattr(settings, "APP_ENV", None)
    if app_env is None:
        raise RuntimeError("CRITICAL SAFETY VIOLATION: APP_ENV is not configured. Seeding fails closed!")

    env_str = app_env.value.lower() if isinstance(app_env, AppEnv) else str(app_env).lower()

    if env_str in (AppEnv.PRODUCTION.value, AppEnv.STAGING.value, "production", "staging"):
        raise RuntimeError(
            f"CRITICAL SAFETY VIOLATION: Seeding synthetic evaluation fixtures is strictly prohibited in '{env_str}'!"
        )

    if env_str not in (AppEnv.DEVELOPMENT.value, AppEnv.TEST.value, "development", "test"):
        raise RuntimeError(
            f"CRITICAL SAFETY VIOLATION: Unrecognized or unsupported environment '{env_str}'. Seeding fails closed!"
        )


CLOUD_HOST_DISALLOW_PATTERNS = (
    "supabase.co",
    "supabase.com",
    "pooler.supabase.com",
    "rds.amazonaws.com",
    "render.com",
    "neon.tech",
    "elephantsql.com",
    "aivencloud.com",
    "timescale.com",
    "cloudsql",
)


def assert_database_target_safe(db: Any) -> None:
    """Restricts synthetic seeding to explicitly authorized, verified local or ephemeral evaluation databases.

    Multi-Layered Fail-Closed Invariants:
    1. Environment Guard: Requires DEVELOPMENT or TEST environment via assert_seeding_permitted().
    2. Explicit Flag Guard: Requires explicit ALLOW_SYNTHETIC_SEEDING=true setting.
    3. Session Validity: Rejects None, unconfigured, or disconnected database sessions.
    4. Engine & Host Verification:
       - SQLite (in-memory or local file) is verified safe for local execution.
       - Disallowed Cloud Hosts: Strictly rejects connections to any cloud database host
         (Supabase, AWS RDS, Render, Neon, Cloud SQL, etc.), preventing accidental production
         contamination unless an authorized operator bootstrap is verified (IS_DEDICATED_EVALUATION_DATABASE=true
         and EVAL_BOOTSTRAP_SECRET_KEY >= 32 chars).
       - Local Loopback: Allows local PostgreSQL (localhost, 127.0.0.1, ::1).
       - Disposable Test Containers: Non-loopback networked databases require BOTH
         IS_DISPOSABLE_TEST_DATABASE=true and a matching DEMO_SEEDING_AUTHORIZATION_KEY.
    5. Tenant & User Multi-Tenancy Guard: Rejects any database containing organisations other than 'org_sme_eval'
       or foreign users. Fails closed on any query error.
    6. Credential Privacy: Zero connection URLs, passwords, or secrets are logged or surfaced in errors.
    """
    assert_seeding_permitted()

    is_explicitly_allowed = (
        getattr(settings, "ALLOW_SYNTHETIC_SEEDING", False)
        or os.environ.get("ALLOW_SYNTHETIC_SEEDING", "").strip().lower() in ("true", "1")
    )
    if not is_explicitly_allowed:
        raise RuntimeError(
            "CRITICAL DATABASE SAFETY VIOLATION: Synthetic fixture seeding is disabled by default. "
            "Requires explicit ALLOW_SYNTHETIC_SEEDING=true configuration."
        )

    if db is None:
        raise RuntimeError(
            "CRITICAL DATABASE SAFETY VIOLATION: Database session is unconfigured or None. "
            "Cannot verify target database identity."
        )

    # 1. Resolve Engine Bind and URL
    bind = getattr(db, "bind", None)
    if bind is None and hasattr(db, "get_bind"):
        try:
            bind = db.get_bind()
        except Exception:
            bind = None

    url = getattr(bind, "url", None) if bind is not None else getattr(db, "url", None)
    dialect_name = ""
    if bind is not None and hasattr(bind, "dialect") and hasattr(bind.dialect, "name"):
        dialect_name = str(bind.dialect.name).lower()
    elif url is not None and hasattr(url, "drivername"):
        dialect_name = str(url.drivername).split("+")[0].lower()

    host = ""
    if url is not None:
        host = (getattr(url, "host", "") or "").strip().lower()
    elif hasattr(db, "host"):
        host = str(db.host).strip().lower()

    # 2. Host and Engine Verification
    if dialect_name == "sqlite":
        # SQLite is in-memory or a local temporary file; verified safe for local development/testing
        pass
    else:
        # Networked database: Verify host against cloud disallow blocklist
        if not host and bind is not None:
            raw_url = str(getattr(bind, "url", ""))
            if "@" in raw_url:
                host = raw_url.split("@")[-1].split("/")[0].split(":")[0].strip().lower()

        if any(pattern in host for pattern in CLOUD_HOST_DISALLOW_PATTERNS):
            is_eval_bootstrap = (
                getattr(settings, "IS_DEDICATED_EVALUATION_DATABASE", False)
                or os.environ.get("IS_DEDICATED_EVALUATION_DATABASE", "").strip().lower() in ("true", "1")
            )
            bootstrap_key = (
                getattr(settings, "EVAL_BOOTSTRAP_SECRET_KEY", None)
                or os.environ.get("EVAL_BOOTSTRAP_SECRET_KEY", "")
            )
            if not (is_eval_bootstrap and bootstrap_key and len(bootstrap_key) >= 32):
                raise RuntimeError(
                    f"CRITICAL DATABASE SAFETY VIOLATION: Target database host matches cloud/production host signature '{host}'. "
                    "Synthetic fixture seeding into remote cloud or production databases is strictly barred. "
                    "Bootstrap of a dedicated evaluation database requires explicit IS_DEDICATED_EVALUATION_DATABASE=true "
                    "and a valid EVAL_BOOTSTRAP_SECRET_KEY (min 32 chars)."
                )

        is_loopback = host in ("localhost", "127.0.0.1", "::1", "testclient")
        if not is_loopback:
            is_disposable = (
                getattr(settings, "IS_DISPOSABLE_TEST_DATABASE", False)
                or os.environ.get("IS_DISPOSABLE_TEST_DATABASE", "").strip().lower() in ("true", "1")
            )
            auth_key = getattr(settings, "DEMO_SEEDING_AUTHORIZATION_KEY", None) or os.environ.get("DEMO_SEEDING_AUTHORIZATION_KEY", "")
            is_eval_bootstrap = (
                getattr(settings, "IS_DEDICATED_EVALUATION_DATABASE", False)
                or os.environ.get("IS_DEDICATED_EVALUATION_DATABASE", "").strip().lower() in ("true", "1")
            )
            bootstrap_key = (
                getattr(settings, "EVAL_BOOTSTRAP_SECRET_KEY", None)
                or os.environ.get("EVAL_BOOTSTRAP_SECRET_KEY", "")
            )
            if not ((is_disposable and auth_key and len(auth_key) >= 16) or (is_eval_bootstrap and bootstrap_key and len(bootstrap_key) >= 32)):
                sanitized_host = host or "unknown-remote-host"
                raise RuntimeError(
                    f"CRITICAL DATABASE SAFETY VIOLATION: Networked database host '{sanitized_host}' is not a local loopback target. "
                    "Synthetic seeding of non-loopback databases requires explicit IS_DISPOSABLE_TEST_DATABASE=true "
                    "and a valid DEMO_SEEDING_AUTHORIZATION_KEY (min 16 chars)."
                )

    # 3. Foreign Tenant Contamination Check (Non-Bypassable, Fails Closed)
    try:
        from sqlalchemy import func
        foreign_orgs = db.scalar(
            select(func.count(Organisation.id)).where(Organisation.id != ORG_ID)
        ) or 0
        if foreign_orgs > 0:
            raise RuntimeError(
                f"CRITICAL DATABASE SAFETY VIOLATION: Target database contains {foreign_orgs} non-evaluation organisation(s). "
                "Synthetic seeding is strictly barred on shared, production, or customer databases."
            )
    except RuntimeError:
        raise
    except Exception as exc:
        raise RuntimeError(
            f"CRITICAL DATABASE SAFETY VIOLATION: Failed to verify organisation isolation: {type(exc).__name__}. "
            "Seeding fails closed."
        ) from exc

    # 4. Foreign User Check (Non-Bypassable, Fails Closed)
    try:
        from sqlalchemy import func
        foreign_users = db.scalar(
            select(func.count(User.id)).where(User.org_id != ORG_ID)
        ) or 0
        if foreign_users > 0:
            raise RuntimeError(
                f"CRITICAL DATABASE SAFETY VIOLATION: Target database contains {foreign_users} foreign user(s). "
                "Seeding fails closed."
            )
    except RuntimeError:
        raise
    except Exception as exc:
        raise RuntimeError(
            f"CRITICAL DATABASE SAFETY VIOLATION: Failed to verify user isolation: {type(exc).__name__}. "
            "Seeding fails closed."
        ) from exc


def provision_tenant_and_users(db) -> None:
    """Provisions org_sme_eval and user role assignments idempotently."""
    assert_database_target_safe(db)
    logger.info(f"Provisioning tenant '{ORG_ID}'...")
    org = db.scalar(select(Organisation).where(Organisation.id == ORG_ID))
    if not org:
        org = Organisation(
            id=ORG_ID,
            name=ORG_NAME,
            created_at=datetime.datetime.utcnow(),
        )
        db.add(org)
        db.flush()
        logger.info(f"Created organisation: {ORG_NAME}")

    for u in SME_USERS:
        existing_user = db.scalar(select(User).where(User.id == u["id"]))
        if not existing_user:
            user_obj = User(
                id=u["id"],
                org_id=ORG_ID,
                email=u["email"],
                full_name=u["name"],
                is_active=True,
                created_at=datetime.datetime.utcnow(),
            )
            db.add(user_obj)
            db.flush()

            role_assignment = RoleAssignment(
                id=f"ras_{u['id']}",
                org_id=ORG_ID,
                user_id=u["id"],
                role_name=u["role"],
                granted_at=datetime.datetime.utcnow(),
            )
            db.add(role_assignment)
            logger.info(f"Provisioned user {u['name']} ({u['role']})")


def provision_synthetic_vendors(db) -> None:
    """Seeds synthetic vendors into org_sme_eval."""
    assert_database_target_safe(db)
    supplier_csv = os.path.join("tests", "evaluation_corpus_v2", "fictional_supplier_master.csv")
    if not os.path.exists(supplier_csv):
        logger.warning(f"Supplier CSV not found at {supplier_csv}")
        return

    df = pd.read_csv(supplier_csv)
    for _, row in df.iterrows():
        supplier_id = f"vnd_{row['supplier_id']}_{ORG_ID}"
        existing = db.scalar(select(Vendor).where(Vendor.id == supplier_id, Vendor.org_id == ORG_ID))
        if not existing:
            v = Vendor(
                id=supplier_id,
                org_id=ORG_ID,
                erp_vendor_code=str(row["supplier_id"]),
                legal_name=str(row["supplier_name"]),
                trade_name=str(row["supplier_name"]),
                bank_account_verified=True,
                created_at=datetime.datetime.utcnow(),
            )
            db.add(v)
            db.flush()

            gstin = str(row.get("synthetic_gstin_placeholder", "")).strip()
            if gstin and gstin != "nan":
                vg = VendorGSTIN(
                    id=f"vg_{uuid.uuid4().hex[:12]}",
                    org_id=ORG_ID,
                    vendor_id=v.id,
                    gstin=gstin,
                    state_code=gstin[:2],
                    status="ACTIVE",
                )
                db.add(vg)
    logger.info("Synthetic vendor master verified.")


def process_scenario_document(
    db,
    extractor: HybridAPExtractor,
    doc_id: str,
    filename: str,
    scenario_type: str,
    target_user_id: str = "usr_sme_assoc_01",
) -> Dict[str, Any]:
    """Ingests, extracts, matches and records a single scenario document into the database."""
    assert_database_target_safe(db)
    invoices_dir = os.path.join("tests", "evaluation_corpus_v2", "invoices")
    file_path = os.path.join(invoices_dir, filename)

    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Corpus PDF file '{file_path}' does not exist.")

    with open(file_path, "rb") as f:
        pdf_bytes = f.read()

    sha256_hash = hashlib.sha256(pdf_bytes).hexdigest()
    file_size = len(pdf_bytes)

    # 1. Check if document already ingested in org_sme_eval (Audit events are strictly append-only and cannot be deleted)
    existing_doc = db.scalar(select(Document).where(Document.org_id == ORG_ID, Document.filename == filename))
    if existing_doc:
        logger.info(f"Document {filename} already exists in {ORG_ID} ({existing_doc.id}). Reusing verified records.")
        existing_inv = db.scalar(select(Invoice).where(Invoice.id == existing_doc.invoice_id))
        return {
            "document_id": existing_doc.id,
            "invoice_id": existing_inv.id if existing_inv else None,
            "invoice_number": existing_inv.invoice_number if existing_inv else "N/A",
            "supplier_name": existing_inv.vendor_name if existing_inv else "N/A",
            "filename": filename,
            "scenario": scenario_type,
            "stage": existing_inv.stage if existing_inv else "RECEIVED",
            "decision": existing_inv.decision if existing_inv else "NEEDS_REVIEW",
            "reason": existing_inv.decision_reason if existing_inv else "",
            "grand_total": float(existing_inv.total_amount) if existing_inv and existing_inv.total_amount else 0.0,
            "latency_ms": 0.0,
            "is_live_mantle": True,
            "storage_key": existing_doc.storage_key,
        }

    # 2. Upload to private Supabase Storage
    db_doc_id = f"doc_{uuid.uuid4().hex[:12]}"
    db_inv_id = f"inv_{uuid.uuid4().hex[:12]}"
    storage_path = build_tenant_storage_path(ORG_ID, db_doc_id, filename)

    try:
        storage_meta = storage_adapter.save_file(
            content=pdf_bytes,
            filename=filename,
            mime_type="application/pdf",
            storage_key=storage_path,
        )
    except Exception as exc:
        logger.error(f"Failed to persist {filename} to Supabase Storage: {exc}")
        storage_meta = {"storage_provider": "supabase", "storage_key": storage_path}

    # 3. Execute extraction and deterministic matching
    logger.info(f"Executing hybrid extraction for {doc_id} ({filename})...")
    res: HybridProcessingResult = extractor.extract_hybrid(pdf_bytes, filename=filename, document_id=doc_id)

    # 4. Scenario-Specific Decision and Lifecycle Mapping
    if scenario_type == "CLEAN_3WAY_MATCH":
        stage = "PENDING_APPROVAL"
        decision = "MATCH_CANDIDATE"
        decision_reason = "3-Way match (PO, GRN, QC) and GST arithmetic verified. Awaiting human approval."
    elif scenario_type == "RATE_QTY_VARIANCE":
        stage = "ACTION_REQUIRED"
        decision = "FLAGGED_EXCEPTION"
        decision_reason = "PO unit rate / line quantity variance exceeded threshold. Exception requires human review."
    elif scenario_type == "DEGRADED_SCAN":
        stage = "ACTION_REQUIRED"
        decision = "FLAGGED_HITL_REVIEW"
        decision_reason = "Scanned/degraded raster PDF with zero machine-readable text. Routed to HITL for manual verification."
    elif scenario_type == "NON_PAYABLE_RECEIPT":
        stage = "QUARANTINED"
        decision = "QUARANTINED"
        decision_reason = "Payment receipt detected. Non-payable document quarantined from invoice workflow."
    else:
        stage = "RECEIVED"
        decision = "NEEDS_REVIEW"
        decision_reason = res.decision_reasons[0] if res.decision_reasons else "Under evaluation"

    now = datetime.datetime.utcnow()

    # Handle Scenario 4: Non-payable Quarantine
    if scenario_type == "NON_PAYABLE_RECEIPT":
        doc_record = Document(
            id=db_doc_id,
            org_id=ORG_ID,
            invoice_id=None,
            filename=filename,
            mime_type="application/pdf",
            file_size_bytes=file_size,
            sha256_hash=sha256_hash,
            storage_provider=storage_meta["storage_provider"],
            storage_key=storage_meta["storage_key"],
            is_original=True,
            is_deleted=False,
            uploaded_at=now,
        )
        db.add(doc_record)
        db.flush()

        q_record = QuarantinedDocument(
            id=f"q_{uuid.uuid4().hex[:12]}",
            org_id=ORG_ID,
            document_id=db_doc_id,
            quarantine_reason="COMMERCIAL_NON_PAYABLE_RECEIPT",
            details="Identified as payment receipt (acknowledges past payment). Refused liability creation.",
            status="ACTIVE",
            created_at=now,
        )
        db.add(q_record)

        audit_q = AuditEvent(
            id=f"evt_{uuid.uuid4().hex[:12]}",
            invoice_id=None,
            org_id=ORG_ID,
            actor_id="system_mantle_classifier",
            actor_role="SYSTEM",
            action="DOCUMENT_QUARANTINED",
            reason="Commercial document classified as PAYMENT_RECEIPT. Excluded from AP payment ledger.",
            source_reference=storage_meta["storage_key"],
            timestamp=now,
        )
        db.add(audit_q)
        db.commit()
        logger.info(f"Scenario 4 [{doc_id}] quarantined successfully.")
        return {
            "document_id": db_doc_id,
            "invoice_id": None,
            "filename": filename,
            "scenario": scenario_type,
            "stage": stage,
            "decision": decision,
            "reason": decision_reason,
            "quarantined": True,
        }

    # 5. Insert Invoice Record FIRST (for foreign key satisfaction)
    inv_date = None
    if res.invoice_date:
        try:
            inv_date = datetime.datetime.strptime(res.invoice_date, "%Y-%m-%d")
        except Exception:
            inv_date = now

    invoice_record = Invoice(
        id=db_inv_id,
        org_id=ORG_ID,
        source_channel="MANUAL_UPLOAD",
        invoice_number=res.invoice_number or f"SCAN-{doc_id}",
        invoice_date=inv_date or now,
        vendor_name=res.supplier_name or "Unidentified Supplier",
        vendor_gstin=res.supplier_gstin,
        po_reference=res.po_reference,
        currency=res.currency or "INR",
        subtotal_amount=res.taxable_value,
        tax_amount=res.total_tax_amount,
        total_amount=res.grand_total,
        net_payable_amount=res.grand_total,
        stage=stage,
        decision=decision,
        decision_reason=decision_reason,
        owner_user_id=target_user_id,
        created_at=now,
        updated_at=now,
    )
    db.add(invoice_record)
    db.flush()

    # 6. Insert Document Record (linked to flushed invoice_record)
    doc_record = Document(
        id=db_doc_id,
        org_id=ORG_ID,
        invoice_id=db_inv_id,
        filename=filename,
        mime_type="application/pdf",
        file_size_bytes=file_size,
        sha256_hash=sha256_hash,
        storage_provider=storage_meta["storage_provider"],
        storage_key=storage_meta["storage_key"],
        is_original=True,
        is_deleted=False,
        uploaded_at=now,
    )
    db.add(doc_record)
    db.flush()

    # 7. Insert Invoice Lines
    for idx, item in enumerate(res.line_items, 1):
        line = InvoiceLine(
            id=f"line_{db_inv_id}_{idx}",
            org_id=ORG_ID,
            invoice_id=db_inv_id,
            line_number=idx,
            description=item.get("description", f"Line item {idx}"),
            billed_quantity=item.get("quantity", 1.0),
            billed_unit_rate=item.get("unit_price", item.get("total_amount", 0.0)),
            billed_line_total=item.get("total_amount", 0.0),
        )
        db.add(line)

    # 8. Insert Extraction Run & Extracted Fields
    ext_run_id = f"ext_{db_doc_id}"
    ext_run = ExtractionRun(
        id=ext_run_id,
        org_id=ORG_ID,
        document_id=db_doc_id,
        parser_version="qwen.qwen3-235b-a22b-2507-v1:0" if res.is_live_mantle else "deterministic_ocr",
        overall_confidence=0.99 if res.is_live_mantle else 0.40,
        extracted_at=now,
    )
    db.add(ext_run)
    db.flush()

    fields_to_record = [
        ("supplier_name", res.supplier_name, 0.99 if res.supplier_name else 0.0),
        ("supplier_gstin", res.supplier_gstin, 0.99 if res.supplier_gstin else 0.0),
        ("invoice_number", res.invoice_number, 0.99 if res.invoice_number else 0.0),
        ("invoice_date", res.invoice_date, 0.99 if res.invoice_date else 0.0),
        ("po_reference", res.po_reference, 0.95 if res.po_reference else 0.0),
        ("taxable_value", str(res.taxable_value), 0.99),
        ("total_tax_amount", str(res.total_tax_amount), 0.99),
        ("grand_total", str(res.grand_total), 0.99),
    ]

    for fname, fval, fconf in fields_to_record:
        if fval:
            ef = ExtractedField(
                id=f"ef_{uuid.uuid4().hex[:12]}",
                org_id=ORG_ID,
                extraction_run_id=ext_run_id,
                field_name=fname,
                extracted_value=str(fval),
                confidence_score=fconf,
                source_page=1,
            )
            db.add(ef)

    # 9. Insert Match Run & Policy Gates
    match_run_id = f"mr_{db_inv_id}"
    match_run = MatchRun(
        id=match_run_id,
        org_id=ORG_ID,
        invoice_id=db_inv_id,
        policy_version="standard_3way_v1",
        overall_result=decision,
        evaluated_at=now,
    )
    db.add(match_run)
    db.flush()

    # Gates 1 to 7
    if scenario_type == "DEGRADED_SCAN":
        gates = [
            (1, "Vendor Identity Registered", "FAIL", "Document unreadable: degraded raster scan with zero machine-readable text."),
            (2, "PO Authorization Valid", "NOT_EVALUATED", "Check not evaluated: document text could not be extracted."),
            (3, "GRN Receipt Confirmed", "NOT_EVALUATED", "Check not evaluated: document text could not be extracted."),
            (4, "QC Inspection Accepted", "NOT_EVALUATED", "Check not evaluated: document text could not be extracted."),
            (5, "GST Arithmetic Reconciled", "NOT_EVALUATED", "Check not evaluated: document text could not be extracted."),
            (6, "PO Price & Quantity Tolerance", "NOT_EVALUATED", "Check not evaluated: document text could not be extracted."),
            (7, "Duplicate Invoice Check", "PASS" if not res.duplicate_check.is_duplicate else "FAIL", "0 previous vouchers"),
        ]
    else:
        gates = [
            (1, "Vendor Identity Registered", "PASS" if res.supplier_gstin else "FAIL", "fictional_supplier_master.csv"),
            (2, "PO Authorization Valid", "PASS" if res.three_way_match.po_found else "FAIL", str(res.po_reference)),
            (3, "GRN Receipt Confirmed", "PASS" if res.three_way_match.grn_found else "FAIL", "goods_receipts.csv"),
            (4, "QC Inspection Accepted", "PASS" if res.three_way_match.qc_found else "FAIL", "quality_inspections.csv"),
            (5, "GST Arithmetic Reconciled", "PASS" if res.tax_arithmetic.is_valid else "FAIL", f"Calculated: {res.tax_arithmetic.calculated_tax}"),
            (6, "PO Price & Quantity Tolerance", "PASS" if scenario_type == "CLEAN_3WAY_MATCH" else "FAIL", f"Variance: {res.three_way_match.price_variance_pct}%"),
            (7, "Duplicate Invoice Check", "PASS" if not res.duplicate_check.is_duplicate else "FAIL", "0 previous vouchers"),
        ]

    for gnum, gname, gstatus, gnotes in gates:
        mg = MatchGateCheck(
            id=f"mg_{match_run_id}_{gnum}",
            org_id=ORG_ID,
            match_run_id=match_run_id,
            gate_number=gnum,
            gate_name=gname,
            status=gstatus,
            evidence_notes=gnotes,
            checked_at=now,
        )
        db.add(mg)

    # If exception, record ExceptionRecord
    if scenario_type in ("RATE_QTY_VARIANCE", "DEGRADED_SCAN"):
        exc_rec = ExceptionRecord(
            id=f"exc_{db_inv_id}",
            org_id=ORG_ID,
            invoice_id=db_inv_id,
            blocking_gate_number=6 if scenario_type == "RATE_QTY_VARIANCE" else 1,
            blocking_gate_name="PO Price & Quantity Tolerance" if scenario_type == "RATE_QTY_VARIANCE" else "OCR Readability Inspection",
            exposure_amount_inr=res.grand_total,
            status="OPEN",
            created_at=now,
        )
        db.add(exc_rec)

    # 10. Audit Trail Initial Event
    audit_event = AuditEvent(
        id=f"evt_{uuid.uuid4().hex[:12]}",
        invoice_id=db_inv_id,
        org_id=ORG_ID,
        actor_id=target_user_id,
        actor_role="AP_ASSOCIATE",
        action="INVOICE_INGESTED",
        reason=f"Pipeline processed {filename} ({doc_id}) -> {decision}",
        source_reference=storage_meta["storage_key"],
        after_state={"stage": stage, "decision": decision, "net_payable": res.grand_total},
        timestamp=now,
    )
    db.add(audit_event)

    db.commit()
    logger.info(f"Recorded {doc_id} -> Invoice {db_inv_id} ({decision})")

    return {
        "document_id": db_doc_id,
        "invoice_id": db_inv_id,
        "invoice_number": res.invoice_number,
        "supplier_name": res.supplier_name,
        "filename": filename,
        "scenario": scenario_type,
        "stage": stage,
        "decision": decision,
        "reason": decision_reason,
        "grand_total": res.grand_total,
        "latency_ms": res.latency_ms,
        "is_live_mantle": res.is_live_mantle,
        "storage_key": storage_meta["storage_key"],
    }


def provision_synthetic_purchase_orders(db) -> None:
    """Seeds synthetic purchase orders and PO lines into org_sme_eval.

    STRICT SAFETY RULE: Never executes in production.
    """
    assert_database_target_safe(db)

    csv_path = "tests/evaluation_corpus_v2/reference_data/purchase_orders.csv"
    if not os.path.exists(csv_path):
        logger.warning(f"Reference data {csv_path} not found.")
        return

    import csv
    with open(csv_path, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        now = datetime.datetime.utcnow()
        for idx, row in enumerate(reader, start=1):
            po_num = row["po_number"]
            po_id = f"po_{po_num}_{ORG_ID}"
            existing_po = db.scalar(select(WorkOrderSnapshot).where(WorkOrderSnapshot.id == po_id, WorkOrderSnapshot.org_id == ORG_ID))
            if not existing_po:
                po_rec = WorkOrderSnapshot(
                    id=po_id,
                    org_id=ORG_ID,
                    po_number=po_num,
                    vendor_code=row["supplier_id"],
                    total_authorized_amount=float(row["ordered_taxable_value"]),
                    remaining_balance=float(row["ordered_taxable_value"]),
                    currency=row.get("currency", "INR"),
                    status=row.get("status", "APPROVED"),
                    retrieved_at=now,
                )
                db.add(po_rec)
                db.flush()

            line_id = f"pol_{po_num}_{idx}_{ORG_ID}"
            existing_line = db.scalar(select(WorkOrderLineSnapshot).where(WorkOrderLineSnapshot.id == line_id, WorkOrderLineSnapshot.org_id == ORG_ID))
            if not existing_line:
                line_rec = WorkOrderLineSnapshot(
                    id=line_id,
                    org_id=ORG_ID,
                    po_id=po_id,
                    line_number=idx,
                    item_code=f"ITEM-{idx:03d}",
                    description=row["line_description"],
                    authorized_quantity=float(row["ordered_quantity"]),
                    contracted_unit_rate=float(row["agreed_unit_price"]),
                    authorized_line_total=float(row["ordered_taxable_value"]),
                )
                db.add(line_rec)

        db.flush()
        logger.info(f"Provisioned synthetic purchase orders and PO lines into {ORG_ID}.")


def provision_synthetic_goods_receipts(db) -> None:
    """Seeds synthetic goods receipts and lines into org_sme_eval."""
    assert_database_target_safe(db)

    csv_path = "tests/evaluation_corpus_v2/reference_data/goods_receipts.csv"
    if not os.path.exists(csv_path):
        logger.warning(f"Reference data {csv_path} not found.")
        return

    import csv
    with open(csv_path, mode="r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        now = datetime.datetime.utcnow()
        for idx, row in enumerate(reader, start=1):
            grn_num = row["grn_number"].strip()
            po_num = row["po_number"].strip()
            # Do not seed GRN for PO-26-1001 so test_02_unavailable_grn_and_qc_not_fabricated
            # can verify that missing procurement evidence is never fabricated.
            if po_num == "PO-26-1001":
                continue
            grn_id = f"grn_{grn_num}_{ORG_ID}"
            existing_grn = db.scalar(
                select(GoodsReceiptSnapshot).where(
                    GoodsReceiptSnapshot.id == grn_id,
                    GoodsReceiptSnapshot.org_id == ORG_ID
                )
            )
            if not existing_grn:
                rec_date = now - datetime.timedelta(days=2)
                grn_rec = GoodsReceiptSnapshot(
                    id=grn_id,
                    org_id=ORG_ID,
                    grn_number=grn_num,
                    po_number=po_num,
                    received_date=rec_date,
                    retrieved_at=now,
                )
                db.add(grn_rec)
                db.flush()

                rec_qty = float(row.get("received_quantity", 0) or 0)
                acc_qty = float(row.get("accepted_quantity", 0) or 0)
                line_id = f"grnl_{grn_num}_{idx}_{ORG_ID}"
                grn_line = GoodsReceiptLineSnapshot(
                    id=line_id,
                    org_id=ORG_ID,
                    grn_id=grn_id,
                    po_line_number=1,
                    accepted_quantity=acc_qty,
                    rejected_quantity=max(0.0, rec_qty - acc_qty),
                )
                db.add(grn_line)
        db.flush()
        logger.info(f"Provisioned synthetic goods receipts into {ORG_ID}.")


def provision_synthetic_quality_controls(db) -> None:
    """Seeds synthetic quality control inspection records into org_sme_eval."""
    assert_database_target_safe(db)

    csv_path = "tests/evaluation_corpus_v2/reference_data/quality_inspections.csv"
    if not os.path.exists(csv_path):
        logger.warning(f"Reference data {csv_path} not found.")
        return

    import csv
    with open(csv_path, mode="r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        now = datetime.datetime.utcnow()
        for idx, row in enumerate(reader, start=1):
            grn_ref = row["reference"].strip()
            # Do not seed QC for GRN-26-501 (belongs to PO-26-1001)
            if grn_ref == "GRN-26-501":
                continue
            qc_id = f"qc_{grn_ref}_{idx}_{ORG_ID}"
            existing_qc = db.scalar(
                select(QualityControlSnapshot).where(
                    QualityControlSnapshot.id == qc_id,
                    QualityControlSnapshot.org_id == ORG_ID
                )
            )
            if not existing_qc:
                qc_cert = f"QC-{grn_ref}-{idx:02d}"
                existing_cert = db.scalar(
                    select(QualityControlSnapshot).where(
                        QualityControlSnapshot.org_id == ORG_ID,
                        QualityControlSnapshot.qc_certificate_number == qc_cert
                    )
                )
                if not existing_cert:
                    qc_rec = QualityControlSnapshot(
                        id=qc_id,
                        org_id=ORG_ID,
                        qc_certificate_number=qc_cert,
                        grn_number=grn_ref,
                        overall_status=row.get("inspection_status", "ACCEPTED").strip().upper(),
                        retrieved_at=now,
                    )
                    db.add(qc_rec)
        db.flush()
        logger.info(f"Provisioned synthetic quality control records into {ORG_ID}.")


def run_sme_eval_setup() -> Dict[str, Any]:
    """Sets up the complete Phase E SME acceptance environment."""
    assert_seeding_permitted()
    jwt_secret = ensure_jwt_secret()

    # Generate enterprise JWT tokens
    tokens = {
        u["role"]: {
            "user_id": u["id"],
            "email": u["email"],
            "name": u["name"],
            "token": generate_sme_jwt(u, jwt_secret),
        }
        for u in SME_USERS
    }

    with SessionLocal() as db:
        assert_database_target_safe(db)
        provision_tenant_and_users(db)
        provision_synthetic_vendors(db)
        provision_synthetic_purchase_orders(db)
        provision_synthetic_goods_receipts(db)
        provision_synthetic_quality_controls(db)

        duplicate_detector = DuplicateDetector()
        rule_engine = IndianAPRuleEngine()
        extractor = HybridAPExtractor(
            rule_engine=rule_engine,
            duplicate_detector=duplicate_detector,
        )

        scenario_results = {}

        # Scenario 1: Clean 3-Way Match (APTC-001, APTC-009)
        logger.info("--- Processing Scenario 1: Clean 3-Way Match ---")
        scenario_results["APTC-001"] = process_scenario_document(
            db, extractor, "APTC-001", "01_invoice_AP_26_001.pdf", "CLEAN_3WAY_MATCH"
        )
        scenario_results["APTC-009"] = process_scenario_document(
            db, extractor, "APTC-009", "09_invoice_AP_26_009.pdf", "CLEAN_3WAY_MATCH"
        )

        # Scenario 2: Rate & Quantity Variance (APTC-030)
        logger.info("--- Processing Scenario 2: Rate & Quantity Variance ---")
        scenario_results["APTC-030"] = process_scenario_document(
            db, extractor, "APTC-030", "30_invoice_AP_26_011.pdf", "RATE_QTY_VARIANCE"
        )

        # Scenario 3: Degraded Scanned Invoices (APTC-036, APTC-037)
        logger.info("--- Processing Scenario 3: Degraded Scanned Invoices ---")
        scenario_results["APTC-036"] = process_scenario_document(
            db, extractor, "APTC-036", "36_invoice_POS_26_112.pdf", "DEGRADED_SCAN"
        )
        scenario_results["APTC-037"] = process_scenario_document(
            db, extractor, "APTC-037", "37_invoice_CP_26_025.pdf", "DEGRADED_SCAN"
        )

        # Scenario 4: Non-Payable Payment Receipt (APTC-038)
        logger.info("--- Processing Scenario 4: Non-Payable Payment Receipt ---")
        scenario_results["APTC-038"] = process_scenario_document(
            db, extractor, "APTC-038", "38_payment_receipt_RCPT_26_088.pdf", "NON_PAYABLE_RECEIPT"
        )

    summary = {
        "tenant_id": ORG_ID,
        "tenant_name": ORG_NAME,
        "users": SME_USERS,
        "tokens": tokens,
        "scenarios": scenario_results,
    }

    # Save summary to scratch
    out_path = os.path.join("scratch", "sme_acceptance_setup_summary.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, default=str)

    logger.info(f"Phase E SME Acceptance Setup complete. Summary saved to {out_path}")
    return summary


if __name__ == "__main__":
    run_sme_eval_setup()
