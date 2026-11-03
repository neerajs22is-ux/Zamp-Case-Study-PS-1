"""SQLAlchemy 2.0 Relational Models for AP Command Center.

Covers all 10 domain groups:
1. Tenancy, Organizations, Legal Entities & RBAC
2. Integrations, Connections, Sync Cursors & Health Events
3. Vendors, GSTINs & Verified Supplier Evidence
4. ERP Read-Only Snapshots (Work Orders, Lines, Milestones, GRNs, QC, Rates)
5. Invoices, Lines, Documents & Source Messages
6. Extraction Runs, Extracted Fields & Evidence Spans
7. Match Runs, Rule Gates & Calculation Steps
8. Ingestion Jobs, Retries & Idempotency Keys
9. Exceptions, Assignments, Internal Tasks & Quarantine
10. Approval Requests, Steps & Append-Only Immutable Audit Events
"""

from __future__ import annotations

import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional
from sqlalchemy import (
    and_, Boolean, Column, DateTime, Enum as SAEnum, ForeignKey, ForeignKeyConstraint,
    Index, Integer, Numeric, String, Text, UniqueConstraint, event
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.types import JSON

from backend.core.database import Base


# ------------------------------------------------------------------------------
# 1. Tenancy, Organizations, Legal Entities & RBAC
# ------------------------------------------------------------------------------

class Organisation(Base):
    __tablename__ = "organisations"

    id = Column(String(64), primary_key=True)
    name = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

    entities = relationship("LegalEntity", back_populates="org")
    users = relationship("User", back_populates="org")


class LegalEntity(Base):
    __tablename__ = "legal_entities"

    id = Column(String(64), primary_key=True)
    org_id = Column(String(64), ForeignKey("organisations.id"), nullable=False, index=True)
    company_code = Column(String(32), nullable=False)  # ERP Company Code (e.g. 1000)
    name = Column(String(255), nullable=False)
    gstin = Column(String(15), nullable=False)
    state_code = Column(String(2), nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

    org = relationship("Organisation", back_populates="entities")
    invoices = relationship("Invoice", back_populates="legal_entity")

    __table_args__ = (
        UniqueConstraint("org_id", "company_code", name="uq_legal_entities_org_company"),
        UniqueConstraint("id", "org_id", name="uq_legal_entities_id_org"),
    )


class User(Base):
    __tablename__ = "users"

    id = Column(String(64), primary_key=True)
    org_id = Column(String(64), ForeignKey("organisations.id"), nullable=False, index=True)
    email = Column(String(255), nullable=False, index=True)
    full_name = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

    org = relationship("Organisation", back_populates="users")
    roles = relationship(
        "RoleAssignment",
        back_populates="user",
        primaryjoin="and_(User.id == RoleAssignment.user_id, User.org_id == RoleAssignment.org_id)"
    )

    __table_args__ = (
        UniqueConstraint("org_id", "email", name="uq_users_org_email"),
        UniqueConstraint("id", "org_id", name="uq_users_id_org"),
    )


class RoleAssignment(Base):
    __tablename__ = "role_assignments"

    id = Column(String(64), primary_key=True)
    org_id = Column(String(64), ForeignKey("organisations.id"), nullable=False, index=True)
    user_id = Column(String(64), ForeignKey("users.id"), nullable=False, index=True)
    role_name = Column(String(64), nullable=False)  # AP_ASSOCIATE, CONTROLLER, etc.
    granted_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

    user = relationship(
        "User",
        back_populates="roles",
        primaryjoin="and_(User.id == RoleAssignment.user_id, User.org_id == RoleAssignment.org_id)"
    )

    __table_args__ = (
        ForeignKeyConstraint(["user_id", "org_id"], ["users.id", "users.org_id"], name="fk_role_assignments_user_org"),
    )


class UserInvitation(Base):
    __tablename__ = "user_invitations"

    id = Column(String(64), primary_key=True)
    org_id = Column(String(64), ForeignKey("organisations.id"), nullable=False, index=True)
    email = Column(String(255), nullable=False, index=True)
    role_name = Column(String(64), nullable=False)
    token_hash = Column(String(64), nullable=False, unique=True, index=True)
    invited_by_user_id = Column(String(64), ForeignKey("users.id"), nullable=False)
    status = Column(String(32), default="PENDING", nullable=False)  # PENDING, ACCEPTED, EXPIRED, REVOKED
    expires_at = Column(DateTime, nullable=False)
    accepted_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

    __table_args__ = (
        ForeignKeyConstraint(["invited_by_user_id", "org_id"], ["users.id", "users.org_id"], name="fk_invitations_user_org"),
        UniqueConstraint("id", "org_id", name="uq_user_invitations_id_org"),
    )


class AccessRequest(Base):
    __tablename__ = "access_requests"

    id = Column(String(64), primary_key=True)
    org_id = Column(String(64), ForeignKey("organisations.id"), nullable=False, index=True)
    user_id = Column(String(64), nullable=False, index=True)  # Supabase sub / user identity
    email = Column(String(255), nullable=False, index=True)
    full_name = Column(String(255), nullable=False)
    requested_role = Column(String(64), default="AP_ASSOCIATE", nullable=False)
    status = Column(String(32), default="PENDING", nullable=False)  # PENDING, APPROVED, REJECTED
    reviewed_by_user_id = Column(String(64), ForeignKey("users.id"), nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    review_reason = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow, nullable=False)

    __table_args__ = (
        ForeignKeyConstraint(["reviewed_by_user_id", "org_id"], ["users.id", "users.org_id"], name="fk_access_requests_reviewer_org"),
        UniqueConstraint("id", "org_id", name="uq_access_requests_id_org"),
    )


# ------------------------------------------------------------------------------
# 2. Integrations, Connections, Sync Cursors & Health Events
# ------------------------------------------------------------------------------

class IntegrationConnection(Base):
    __tablename__ = "integration_connections"

    id = Column(String(64), primary_key=True)
    org_id = Column(String(64), ForeignKey("organisations.id"), nullable=False, index=True)
    pillar = Column(String(32), nullable=False)  # identity, gmail, sap_erp, storage
    provider = Column(String(64), nullable=False)
    status = Column(String(32), nullable=False)  # NOT_CONFIGURED, CONNECTED, DEGRADED, REVOKED
    last_health_check = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)
    configuration_metadata = Column(JSON, nullable=True)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("org_id", "pillar", name="uq_integration_connections_org_pillar"),
        UniqueConstraint("id", "org_id", name="uq_integration_connections_id_org"),
    )


class GmailAccount(Base):
    __tablename__ = "gmail_accounts"

    id = Column(String(64), primary_key=True)
    org_id = Column(String(64), ForeignKey("organisations.id"), nullable=False, index=True)
    mailbox_address = Column(String(255), nullable=False)
    oauth_status = Column(String(32), nullable=False)  # AUTHORIZED, EXPIRED, REVOKED
    encrypted_refresh_token = Column(Text, nullable=True)
    last_history_id = Column(String(64), nullable=True)
    last_synced_at = Column(DateTime, nullable=True)
    pubsub_topic = Column(String(255), nullable=True)
    watch_history_id = Column(String(64), nullable=True)
    watch_expiration_at = Column(DateTime, nullable=True)
    watch_last_renewed_at = Column(DateTime, nullable=True)
    watch_status = Column(String(32), default="DISABLED", nullable=False)  # ACTIVE, EXPIRED, FAILED, DISABLED
    sync_lock_token = Column(String(64), nullable=True)
    sync_lock_expires_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("org_id", "mailbox_address", name="uq_gmail_accounts_org_mailbox"),
        UniqueConstraint("id", "org_id", name="uq_gmail_accounts_id_org"),
    )


class OAuthStateNonce(Base):
    __tablename__ = "oauth_state_nonces"

    id = Column(String(64), primary_key=True)  # The nonce string itself
    org_id = Column(String(64), ForeignKey("organisations.id"), nullable=False, index=True)
    user_id = Column(String(64), nullable=False)
    session_binding = Column(String(64), nullable=True)
    is_consumed = Column(Boolean, default=False, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    consumed_at = Column(DateTime, nullable=True)

    __table_args__ = (
        UniqueConstraint("id", "org_id", name="uq_oauth_nonces_id_org"),
    )


class PubSubEvent(Base):
    __tablename__ = "gmail_pubsub_events"

    id = Column(String(64), primary_key=True)
    org_id = Column(String(64), ForeignKey("organisations.id"), nullable=False, index=True)
    mailbox_address = Column(String(255), nullable=False, index=True)
    history_id = Column(String(64), nullable=False, index=True)
    pubsub_message_id = Column(String(128), unique=True, nullable=False, index=True)
    subscription = Column(String(255), nullable=True)
    payload_json = Column(JSON, nullable=True)
    status = Column(String(32), default="RECEIVED", nullable=False)  # RECEIVED, COMPLETED, FAILED, DUPLICATE, CONCURRENT_DEFERRED, OUT_OF_ORDER_SKIPPED
    error_message = Column(Text, nullable=True)
    retry_count = Column(Integer, default=0, nullable=False)
    received_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    last_attempted_at = Column(DateTime, nullable=True)
    processed_at = Column(DateTime, nullable=True)

    __table_args__ = (
        UniqueConstraint("id", "org_id", name="uq_pubsub_events_id_org"),
    )


class ConnectionHealthEvent(Base):
    __tablename__ = "connection_health_events"

    id = Column(String(64), primary_key=True)
    org_id = Column(String(64), ForeignKey("organisations.id"), nullable=False, index=True)
    connection_id = Column(String(64), ForeignKey("integration_connections.id"), nullable=False, index=True)
    status = Column(String(32), nullable=False)
    latency_ms = Column(Integer, nullable=True)
    message = Column(Text, nullable=True)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

    __table_args__ = (
        ForeignKeyConstraint(
            ["connection_id", "org_id"],
            ["integration_connections.id", "integration_connections.org_id"],
            name="fk_conn_health_conn_org"
        ),
    )


# ------------------------------------------------------------------------------
# 3. Vendors, GSTINs & Verified Supplier Evidence
# ------------------------------------------------------------------------------

class Vendor(Base):
    __tablename__ = "vendors"

    id = Column(String(64), primary_key=True)
    org_id = Column(String(64), ForeignKey("organisations.id"), nullable=False, index=True)
    erp_vendor_code = Column(String(64), nullable=False)
    legal_name = Column(String(255), nullable=False)
    trade_name = Column(String(255), nullable=True)
    pan = Column(String(10), nullable=True, index=True)
    msme_registered = Column(Boolean, default=False, nullable=False)
    msme_category = Column(String(32), nullable=True)  # MICRO, SMALL, MEDIUM
    udyam_number = Column(String(64), nullable=True)
    bank_account_verified = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

    gstins = relationship(
        "VendorGSTIN",
        back_populates="vendor",
        primaryjoin="and_(Vendor.id == VendorGSTIN.vendor_id, Vendor.org_id == VendorGSTIN.org_id)"
    )

    __table_args__ = (
        UniqueConstraint("org_id", "erp_vendor_code", name="uq_vendors_org_code"),
        UniqueConstraint("id", "org_id", name="uq_vendors_id_org"),
    )


class VendorGSTIN(Base):
    __tablename__ = "vendor_gstins"

    id = Column(String(64), primary_key=True)
    org_id = Column(String(64), ForeignKey("organisations.id"), nullable=False, index=True)
    vendor_id = Column(String(64), ForeignKey("vendors.id"), nullable=False, index=True)
    gstin = Column(String(15), nullable=False, index=True)
    state_code = Column(String(2), nullable=False)
    status = Column(String(32), default="ACTIVE", nullable=False)

    vendor = relationship(
        "Vendor",
        back_populates="gstins",
        primaryjoin="and_(Vendor.id == VendorGSTIN.vendor_id, Vendor.org_id == VendorGSTIN.org_id)"
    )

    __table_args__ = (
        ForeignKeyConstraint(["vendor_id", "org_id"], ["vendors.id", "vendors.org_id"], name="fk_vendor_gstins_vendor_org"),
    )


# ------------------------------------------------------------------------------
# 4. ERP Read-Only Snapshots (Work Orders, GRNs, QC, Rates)
# ------------------------------------------------------------------------------

class WorkOrderSnapshot(Base):
    __tablename__ = "erp_work_orders"

    id = Column(String(64), primary_key=True)
    org_id = Column(String(64), ForeignKey("organisations.id"), nullable=False, index=True)
    po_number = Column(String(64), nullable=False, index=True)
    vendor_code = Column(String(64), nullable=False)
    total_authorized_amount = Column(Numeric(15, 2), nullable=False)
    remaining_balance = Column(Numeric(15, 2), nullable=False)
    currency = Column(String(3), default="INR", nullable=False)
    status = Column(String(32), nullable=False)
    retrieved_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

    lines = relationship(
        "WorkOrderLineSnapshot",
        back_populates="po",
        primaryjoin="and_(WorkOrderSnapshot.id == WorkOrderLineSnapshot.po_id, WorkOrderSnapshot.org_id == WorkOrderLineSnapshot.org_id)"
    )

    __table_args__ = (
        UniqueConstraint("org_id", "po_number", name="uq_erp_work_orders_org_po"),
        UniqueConstraint("id", "org_id", name="uq_erp_work_orders_id_org"),
    )


class WorkOrderLineSnapshot(Base):
    __tablename__ = "erp_po_lines"

    id = Column(String(64), primary_key=True)
    org_id = Column(String(64), ForeignKey("organisations.id"), nullable=False, index=True)
    po_id = Column(String(64), ForeignKey("erp_work_orders.id"), nullable=False, index=True)
    line_number = Column(Integer, nullable=False)
    item_code = Column(String(64), nullable=False)
    description = Column(Text, nullable=False)
    authorized_quantity = Column(Numeric(12, 4), nullable=False)
    contracted_unit_rate = Column(Numeric(12, 4), nullable=False)
    authorized_line_total = Column(Numeric(15, 2), nullable=False)

    po = relationship(
        "WorkOrderSnapshot",
        back_populates="lines",
        primaryjoin="and_(WorkOrderSnapshot.id == WorkOrderLineSnapshot.po_id, WorkOrderSnapshot.org_id == WorkOrderLineSnapshot.org_id)"
    )

    __table_args__ = (
        ForeignKeyConstraint(["po_id", "org_id"], ["erp_work_orders.id", "erp_work_orders.org_id"], name="fk_erp_po_lines_po_org"),
    )


class GoodsReceiptSnapshot(Base):
    __tablename__ = "erp_grns"

    id = Column(String(64), primary_key=True)
    org_id = Column(String(64), ForeignKey("organisations.id"), nullable=False, index=True)
    grn_number = Column(String(64), nullable=False, index=True)
    po_number = Column(String(64), nullable=False, index=True)
    received_date = Column(DateTime, nullable=False)
    retrieved_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

    lines = relationship(
        "GoodsReceiptLineSnapshot",
        back_populates="grn",
        primaryjoin="and_(GoodsReceiptSnapshot.id == GoodsReceiptLineSnapshot.grn_id, GoodsReceiptSnapshot.org_id == GoodsReceiptLineSnapshot.org_id)"
    )

    __table_args__ = (
        UniqueConstraint("org_id", "grn_number", name="uq_erp_grns_org_grn"),
        UniqueConstraint("id", "org_id", name="uq_erp_grns_id_org"),
    )


class GoodsReceiptLineSnapshot(Base):
    __tablename__ = "erp_grn_lines"

    id = Column(String(64), primary_key=True)
    org_id = Column(String(64), ForeignKey("organisations.id"), nullable=False, index=True)
    grn_id = Column(String(64), ForeignKey("erp_grns.id"), nullable=False, index=True)
    po_line_number = Column(Integer, nullable=False)
    accepted_quantity = Column(Numeric(12, 4), nullable=False)
    rejected_quantity = Column(Numeric(12, 4), default=0, nullable=False)

    grn = relationship(
        "GoodsReceiptSnapshot",
        back_populates="lines",
        primaryjoin="and_(GoodsReceiptSnapshot.id == GoodsReceiptLineSnapshot.grn_id, GoodsReceiptSnapshot.org_id == GoodsReceiptLineSnapshot.org_id)"
    )

    __table_args__ = (
        ForeignKeyConstraint(["grn_id", "org_id"], ["erp_grns.id", "erp_grns.org_id"], name="fk_erp_grn_lines_grn_org"),
    )


class QualityControlSnapshot(Base):
    __tablename__ = "erp_qc_records"

    id = Column(String(64), primary_key=True)
    org_id = Column(String(64), ForeignKey("organisations.id"), nullable=False, index=True)
    qc_certificate_number = Column(String(64), nullable=False, index=True)
    grn_number = Column(String(64), nullable=False, index=True)
    overall_status = Column(String(32), nullable=False)  # PASSED, CONDITIONALLY_ACCEPTED, REJECTED
    retrieved_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("org_id", "qc_certificate_number", name="uq_erp_qc_records_org_qc"),
    )


# ------------------------------------------------------------------------------
# 5. Invoices, Documents & Source Messages
# ------------------------------------------------------------------------------

class Invoice(Base):
    __tablename__ = "invoices"

    id = Column(String(64), primary_key=True)
    org_id = Column(String(64), ForeignKey("organisations.id"), nullable=False, index=True)
    legal_entity_id = Column(String(64), ForeignKey("legal_entities.id"), nullable=True, index=True)
    source_channel = Column(String(32), nullable=False)  # GMAIL, MANUAL_UPLOAD, DIRECT_API
    invoice_number = Column(String(128), nullable=True, index=True)
    invoice_date = Column(DateTime, nullable=True)
    due_date = Column(DateTime, nullable=True)
    msme_statutory_deadline = Column(DateTime, nullable=True)
    msme_deadline_status = Column(String(64), nullable=True)

    vendor_name = Column(String(255), nullable=True)
    vendor_gstin = Column(String(15), nullable=True)
    po_reference = Column(String(64), nullable=True, index=True)

    currency = Column(String(3), default="INR", nullable=False)
    subtotal_amount = Column(Numeric(15, 2), nullable=True)
    tax_amount = Column(Numeric(15, 2), nullable=True)
    total_amount = Column(Numeric(15, 2), nullable=True)
    net_payable_amount = Column(Numeric(15, 2), nullable=True)

    stage = Column(String(32), default="RECEIVED", nullable=False)
    decision = Column(String(32), default="NEEDS_REVIEW", nullable=False)
    decision_reason = Column(Text, nullable=True)
    workflow_substatus = Column(String(32), nullable=True)
    owner_user_id = Column(String(64), ForeignKey("users.id"), nullable=True)

    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow, nullable=False)

    legal_entity = relationship("LegalEntity", back_populates="invoices")
    lines = relationship(
        "InvoiceLine",
        back_populates="invoice",
        primaryjoin="and_(Invoice.id == InvoiceLine.invoice_id, Invoice.org_id == InvoiceLine.org_id)"
    )
    documents = relationship(
        "Document",
        back_populates="invoice",
        primaryjoin="and_(Invoice.id == Document.invoice_id, Invoice.org_id == Document.org_id)"
    )
    match_runs = relationship(
        "MatchRun",
        back_populates="invoice",
        primaryjoin="and_(Invoice.id == MatchRun.invoice_id, Invoice.org_id == MatchRun.org_id)"
    )
    audit_events = relationship(
        "AuditEvent",
        back_populates="invoice",
        primaryjoin="and_(Invoice.id == AuditEvent.invoice_id, Invoice.org_id == AuditEvent.org_id)"
    )

    __table_args__ = (
        UniqueConstraint("id", "org_id", name="uq_invoices_id_org"),
        Index("idx_invoices_org_invoice_date", "org_id", "invoice_date"),
    )


class InvoiceLine(Base):
    __tablename__ = "invoice_lines"

    id = Column(String(64), primary_key=True)
    org_id = Column(String(64), ForeignKey("organisations.id"), nullable=False, index=True)
    invoice_id = Column(String(64), ForeignKey("invoices.id"), nullable=False, index=True)
    line_number = Column(Integer, nullable=False)
    description = Column(Text, nullable=False)
    billed_quantity = Column(Numeric(12, 4), nullable=False)
    billed_unit_rate = Column(Numeric(12, 4), nullable=False)
    billed_line_total = Column(Numeric(15, 2), nullable=False)
    is_corrected = Column(Boolean, default=False, nullable=False)
    previous_unit_rate = Column(Numeric(12, 4), nullable=True)
    line_version = Column(Integer, default=1, nullable=False)

    invoice = relationship(
        "Invoice",
        back_populates="lines",
        primaryjoin="and_(Invoice.id == InvoiceLine.invoice_id, Invoice.org_id == InvoiceLine.org_id)"
    )

    __table_args__ = (
        ForeignKeyConstraint(["invoice_id", "org_id"], ["invoices.id", "invoices.org_id"], name="fk_invoice_lines_invoice_org"),
    )


class Document(Base):
    __tablename__ = "documents"

    id = Column(String(64), primary_key=True)
    org_id = Column(String(64), ForeignKey("organisations.id"), nullable=False, index=True)
    invoice_id = Column(String(64), ForeignKey("invoices.id"), nullable=True, index=True)
    filename = Column(String(255), nullable=False)
    mime_type = Column(String(64), nullable=False)
    file_size_bytes = Column(Integer, nullable=False)
    sha256_hash = Column(String(64), nullable=False, index=True)
    storage_provider = Column(String(32), nullable=False)
    storage_key = Column(String(512), nullable=False)
    is_original = Column(Boolean, default=True, nullable=False)
    is_deleted = Column(Boolean, default=False, nullable=False)
    deleted_at = Column(DateTime, nullable=True)
    deleted_by_user_id = Column(String(64), nullable=True)
    uploaded_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

    invoice = relationship(
        "Invoice",
        back_populates="documents",
        primaryjoin="and_(Invoice.id == Document.invoice_id, Invoice.org_id == Document.org_id)"
    )

    __table_args__ = (
        UniqueConstraint("id", "org_id", name="uq_documents_id_org"),
    )


# ------------------------------------------------------------------------------
# 6. Extraction Runs, Extracted Fields & Evidence Spans
# ------------------------------------------------------------------------------

class ExtractionRun(Base):
    __tablename__ = "extraction_runs"

    id = Column(String(64), primary_key=True)
    org_id = Column(String(64), ForeignKey("organisations.id"), nullable=False, index=True)
    document_id = Column(String(64), ForeignKey("documents.id"), nullable=False, index=True)
    parser_version = Column(String(32), nullable=False)
    overall_confidence = Column(Numeric(5, 4), nullable=True)
    extracted_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

    fields = relationship(
        "ExtractedField",
        back_populates="extraction_run",
        primaryjoin="and_(ExtractionRun.id == ExtractedField.extraction_run_id, ExtractionRun.org_id == ExtractedField.org_id)"
    )

    __table_args__ = (
        ForeignKeyConstraint(["document_id", "org_id"], ["documents.id", "documents.org_id"], name="fk_extraction_runs_doc_org"),
        UniqueConstraint("id", "org_id", name="uq_extraction_runs_id_org"),
    )


class ExtractedField(Base):
    __tablename__ = "extracted_fields"

    id = Column(String(64), primary_key=True)
    org_id = Column(String(64), ForeignKey("organisations.id"), nullable=False, index=True)
    extraction_run_id = Column(String(64), ForeignKey("extraction_runs.id"), nullable=False, index=True)
    field_name = Column(String(64), nullable=False)
    extracted_value = Column(Text, nullable=True)
    confidence_score = Column(Numeric(5, 4), nullable=True)
    source_page = Column(Integer, nullable=True)
    bounding_box = Column(JSON, nullable=True)

    extraction_run = relationship(
        "ExtractionRun",
        back_populates="fields",
        primaryjoin="and_(ExtractionRun.id == ExtractedField.extraction_run_id, ExtractionRun.org_id == ExtractedField.org_id)"
    )

    __table_args__ = (
        ForeignKeyConstraint(["extraction_run_id", "org_id"], ["extraction_runs.id", "extraction_runs.org_id"], name="fk_extracted_fields_run_org"),
    )


# ------------------------------------------------------------------------------
# 7. Match Runs, Rule Gates & Calculation Steps
# ------------------------------------------------------------------------------

class MatchRun(Base):
    __tablename__ = "match_runs"

    id = Column(String(64), primary_key=True)
    org_id = Column(String(64), ForeignKey("organisations.id"), nullable=False, index=True)
    invoice_id = Column(String(64), ForeignKey("invoices.id"), nullable=False, index=True)
    policy_version = Column(String(32), default="v1.0-default", nullable=False)
    overall_result = Column(String(32), nullable=False)  # PASS, NEEDS_REVIEW, REJECTED
    evaluated_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

    invoice = relationship(
        "Invoice",
        back_populates="match_runs",
        primaryjoin="and_(Invoice.id == MatchRun.invoice_id, Invoice.org_id == MatchRun.org_id)"
    )
    gates = relationship(
        "MatchGateCheck",
        back_populates="match_run",
        primaryjoin="and_(MatchRun.id == MatchGateCheck.match_run_id, MatchRun.org_id == MatchGateCheck.org_id)"
    )

    __table_args__ = (
        ForeignKeyConstraint(["invoice_id", "org_id"], ["invoices.id", "invoices.org_id"], name="fk_match_runs_invoice_org"),
        UniqueConstraint("id", "org_id", name="uq_match_runs_id_org"),
    )


class MatchGateCheck(Base):
    __tablename__ = "match_gate_checks"

    id = Column(String(64), primary_key=True)
    org_id = Column(String(64), ForeignKey("organisations.id"), nullable=False, index=True)
    match_run_id = Column(String(64), ForeignKey("match_runs.id"), nullable=False, index=True)
    gate_number = Column(Integer, nullable=False)
    gate_name = Column(String(64), nullable=False)
    status = Column(String(32), nullable=False)  # PASS, FAIL, UNKNOWN
    evidence_source_id = Column(String(128), nullable=True)
    evidence_notes = Column(Text, nullable=True)
    checked_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

    match_run = relationship(
        "MatchRun",
        back_populates="gates",
        primaryjoin="and_(MatchRun.id == MatchGateCheck.match_run_id, MatchRun.org_id == MatchGateCheck.org_id)"
    )

    __table_args__ = (
        ForeignKeyConstraint(["match_run_id", "org_id"], ["match_runs.id", "match_runs.org_id"], name="fk_match_gates_run_org"),
    )


# ------------------------------------------------------------------------------
# 8. Ingestion Jobs, Retries & Idempotency Keys
# ------------------------------------------------------------------------------

class IngestionJob(Base):
    __tablename__ = "ingestion_jobs"

    id = Column(String(64), primary_key=True)
    org_id = Column(String(64), ForeignKey("organisations.id"), nullable=False, index=True)
    idempotency_key = Column(String(128), nullable=False, index=True)
    source_channel = Column(String(32), nullable=False)
    status = Column(String(32), nullable=False)  # QUEUED, PROCESSING, COMPLETED, FAILED
    retry_count = Column(Integer, default=0, nullable=False)
    error_message = Column(Text, nullable=True)
    document_id = Column(String(64), ForeignKey("documents.id"), nullable=True, index=True)
    lock_token = Column(String(64), nullable=True)
    lease_expires_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    completed_at = Column(DateTime, nullable=True)

    __table_args__ = (
        UniqueConstraint("org_id", "idempotency_key", name="uq_ingestion_jobs_org_idempotency"),
    )


# ------------------------------------------------------------------------------
# 9. Exceptions, Assignments, Internal Tasks & Quarantine
# ------------------------------------------------------------------------------

class ExceptionRecord(Base):
    __tablename__ = "exceptions"

    id = Column(String(64), primary_key=True)
    org_id = Column(String(64), ForeignKey("organisations.id"), nullable=False, index=True)
    invoice_id = Column(String(64), ForeignKey("invoices.id"), nullable=False, index=True)
    blocking_gate_number = Column(Integer, nullable=False)
    blocking_gate_name = Column(String(64), nullable=False)
    exposure_amount_inr = Column(Numeric(15, 2), nullable=False)
    msme_statutory_deadline = Column(DateTime, nullable=True)
    assigned_user_id = Column(String(64), ForeignKey("users.id"), nullable=True)
    status = Column(String(32), default="OPEN", nullable=False)  # OPEN, IN_REVIEW, RESOLVED
    resolution_notes = Column(Text, nullable=True)
    resolved_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

    __table_args__ = (
        ForeignKeyConstraint(["invoice_id", "org_id"], ["invoices.id", "invoices.org_id"], name="fk_exceptions_invoice_org"),
    )


class QuarantinedDocument(Base):
    __tablename__ = "quarantined_documents"

    id = Column(String(64), primary_key=True)
    org_id = Column(String(64), ForeignKey("organisations.id"), nullable=False, index=True)
    document_id = Column(String(64), ForeignKey("documents.id"), nullable=False, index=True)
    quarantine_reason = Column(String(64), nullable=False)  # NO_READABLE_TEXT, MALFORMED_PDF, SECURITY_SCAN_FAILED
    details = Column(Text, nullable=True)
    status = Column(String(32), default="ACTIVE", nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

    __table_args__ = (
        ForeignKeyConstraint(["document_id", "org_id"], ["documents.id", "documents.org_id"], name="fk_quarantined_docs_doc_org"),
    )


# ------------------------------------------------------------------------------
# 10. Approval Requests, Steps & Append-Only Immutable Audit Events
# ------------------------------------------------------------------------------

class ApprovalRequest(Base):
    __tablename__ = "approval_requests"

    id = Column(String(64), primary_key=True)
    org_id = Column(String(64), ForeignKey("organisations.id"), nullable=False, index=True)
    invoice_id = Column(String(64), ForeignKey("invoices.id"), nullable=False, index=True)
    requires_dual_approval = Column(Boolean, default=False, nullable=False)
    first_approver_id = Column(String(64), ForeignKey("users.id"), nullable=True)
    first_approved_at = Column(DateTime, nullable=True)
    second_approver_id = Column(String(64), ForeignKey("users.id"), nullable=True)
    second_approved_at = Column(DateTime, nullable=True)
    status = Column(String(32), default="PENDING", nullable=False)

    __table_args__ = (
        ForeignKeyConstraint(["invoice_id", "org_id"], ["invoices.id", "invoices.org_id"], name="fk_approval_requests_invoice_org"),
    )


class AuditEvent(Base):
    """Append-only, immutable audit trail.

    Enforced by database-level triggers and ORM listeners.
    UPDATE and DELETE statements on this table are strictly prohibited.
    """
    __tablename__ = "audit_events"

    id = Column(String(64), primary_key=True)
    invoice_id = Column(String(64), ForeignKey("invoices.id"), nullable=True, index=True)
    org_id = Column(String(64), ForeignKey("organisations.id"), nullable=True, index=True)
    legal_entity_id = Column(String(64), nullable=True)
    actor_id = Column(String(64), nullable=False)
    actor_role = Column(String(64), nullable=False)
    action = Column(String(64), nullable=False)
    reason = Column(Text, nullable=True)
    correlation_id = Column(String(64), nullable=True, index=True)
    before_state = Column(JSON, nullable=True)
    after_state = Column(JSON, nullable=True)
    policy_version = Column(String(32), nullable=True)
    source_reference = Column(String(255), nullable=True)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow, nullable=False, index=True)

    invoice = relationship(
        "Invoice",
        back_populates="audit_events",
        primaryjoin="and_(Invoice.id == AuditEvent.invoice_id, Invoice.org_id == AuditEvent.org_id)"
    )


# ------------------------------------------------------------------------------
# Database-Level Append-Only Enforcement Listeners for AuditEvent
# ------------------------------------------------------------------------------

@event.listens_for(AuditEvent, "before_update")
def receive_before_update(mapper, connection, target):
    raise PermissionError("audit_events is strictly append-only: UPDATE operations are barred.")


@event.listens_for(AuditEvent, "before_delete")
def receive_before_delete(mapper, connection, target):
    raise PermissionError("audit_events is strictly append-only: DELETE operations are barred.")
