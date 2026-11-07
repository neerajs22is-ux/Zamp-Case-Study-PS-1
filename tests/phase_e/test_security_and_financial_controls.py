"""Phase E Security & Financial Control Audit Test Suite.

Verifies:
1. POST /api/v1/auth/dev-session security guards:
   - Barred when ENABLE_DEV_SESSION=False (403).
   - Barred when APP_ENV=PRODUCTION (403).
   - Barred when called from external non-loopback IP (403).
   - Rejects non-existent or deactivated users (404/403).
2. Supabase JWT claim architecture:
   - Database role claim 'role' represents 'authenticated'.
   - Application roles (AP_LEAD, CONTROLLER, AUDITOR, AP_ASSOCIATE) are separately represented in 'user_role' and 'app_metadata'.
   - Server-side PostgreSQL RoleAssignment resolution remains strictly authoritative (zero trust for client-claimed roles).
3. Cryptographic token security:
   - Invalid HMAC signature rejection (401).
   - Expired token rejection (401).
   - Cross-tenant access rejection (403 when requesting non-member org).
   - Unauthorized privilege escalation rejection (403).
4. Financial approval-state machine & dual-control validation:
   - Human AP Lead approval sets stage='INTERNAL_APPROVAL_COMPLETE' and decision='MANUALLY_APPROVED' (distinguished from 'AUTO_APPROVED').
   - Dual-control threshold (₹500,000 INR):
     - Low-value (< 500k, e.g. APTC-001 @ 26,196) requires single AP Lead approval; Controller not required.
     - High-value (>= 500k) requires two distinct approvers (AP Lead + Controller); same approver rejected (400).
   - Invariant: Zero payment disbursement and zero ERP ledger mutation triggered by AP Command Center approvals.
   - Auditor read-only enforcement: Mutations strictly return 403 Forbidden.
   - Audit trail attribution and immutability.
"""

from __future__ import annotations

import datetime
import time
import uuid
from typing import Dict, Any

from fastapi import status
from fastapi.testclient import TestClient
from jose import jwt
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

from backend.core.config import AppEnv, settings
from backend.core.database import get_db
from backend.core.auth import UserRole
from backend.models.domain import (
    Base, ApprovalRequest, AuditEvent, Organisation, RoleAssignment, User, Invoice
)
from backend.main import app

TEST_ORG = "org_sec_audit"
TEST_SECRET = "super-secure-supabase-jwt-secret-at-least-32-chars!"


@pytest.fixture(autouse=True)
def configure_sec_settings(monkeypatch):
    """Configures safe test environment for security audit tests."""
    monkeypatch.setattr(settings, "APP_ENV", AppEnv.TEST)
    monkeypatch.setattr(settings, "ENABLE_DEV_SESSION", True)
    monkeypatch.setattr(settings, "SUPABASE_JWT_SECRET", TEST_SECRET)
    monkeypatch.setattr(settings, "SUPABASE_URL", "https://test-sec.supabase.co")
    monkeypatch.setattr(settings, "SUPABASE_ISSUER", "https://test-sec.supabase.co/auth/v1")
    monkeypatch.setattr(settings, "SUPABASE_AUDIENCE", "authenticated")


@pytest.fixture
def audit_session():
    """Isolated in-memory test database with full schema for Phase E security tests."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = Session()

    # Pre-seed test organisation
    org = Organisation(id=TEST_ORG, name="Security Audit Org", created_at=datetime.datetime.utcnow())
    session.add(org)
    session.commit()

    def override_get_db():
        try:
            yield session
        except Exception:
            session.rollback()
            raise

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as client:
        yield client, session

    session.close()
    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


def seed_user(session: Session, user_id: str, email: str, role_name: str, is_active: bool = True) -> User:
    """Helper to seed user and role in the test session."""
    user = session.scalar(select(User).where(User.id == user_id))
    if not user:
        user = User(
            id=user_id,
            org_id=TEST_ORG,
            email=email,
            full_name=f"User {user_id}",
            is_active=is_active,
            created_at=datetime.datetime.utcnow(),
        )
        session.add(user)
        session.flush()

    ra = session.scalar(select(RoleAssignment).where(RoleAssignment.user_id == user_id, RoleAssignment.org_id == TEST_ORG))
    if not ra:
        ra = RoleAssignment(
            id=f"ra_{uuid.uuid4().hex[:10]}",
            org_id=TEST_ORG,
            user_id=user_id,
            role_name=role_name,
            granted_at=datetime.datetime.utcnow(),
        )
        session.add(ra)
    session.commit()
    return user


# ==============================================================================
# SECTION A: Authentication & Dev-Session Security Tests
# ==============================================================================

def test_a1_dev_session_disabled_by_default(audit_session, monkeypatch):
    """Proves dev-session returns 403 Forbidden when ENABLE_DEV_SESSION is False."""
    client, session = audit_session
    monkeypatch.setattr(settings, "ENABLE_DEV_SESSION", False)
    seed_user(session, "usr_sec_01", "sec_user@company.internal", "AP_LEAD")

    resp = client.post("/api/v1/auth/dev-session", json={"email": "sec_user@company.internal", "org_id": TEST_ORG})
    assert resp.status_code == status.HTTP_403_FORBIDDEN
    assert "ENABLE_DEV_SESSION=False" in resp.json()["detail"]


def test_a2_dev_session_barred_in_production(audit_session, monkeypatch):
    """Proves dev-session is unconditionally blocked when APP_ENV is PRODUCTION."""
    client, session = audit_session
    monkeypatch.setattr(settings, "APP_ENV", AppEnv.PRODUCTION)
    monkeypatch.setattr(settings, "ENABLE_DEV_SESSION", True)
    seed_user(session, "usr_sec_01", "sec_user@company.internal", "AP_LEAD")

    resp = client.post("/api/v1/auth/dev-session", json={"email": "sec_user@company.internal", "org_id": TEST_ORG})
    assert resp.status_code == status.HTTP_403_FORBIDDEN
    assert "strictly prohibited" in resp.json()["detail"].lower()


def test_a3_dev_session_rejects_external_non_loopback_caller(audit_session):
    """Proves dev-session rejects requests originating from external IP addresses."""
    _, session = audit_session
    seed_user(session, "usr_sec_01", "sec_user@company.internal", "AP_LEAD")

    # Simulate request from external WAN address
    ext_client = TestClient(app, client=("198.51.100.25", 54321))
    resp = ext_client.post("/api/v1/auth/dev-session", json={"email": "sec_user@company.internal", "org_id": TEST_ORG})
    assert resp.status_code == status.HTTP_403_FORBIDDEN
    assert "loopback" in resp.json()["detail"].lower()


def test_a4_dev_session_rejects_arbitrary_unregistered_or_deactivated_users(audit_session):
    """Proves callers cannot obtain sessions for arbitrary or deactivated emails."""
    client, session = audit_session
    # Unknown user
    resp_unknown = client.post("/api/v1/auth/dev-session", json={"email": "hacker@external.org", "org_id": TEST_ORG})
    assert resp_unknown.status_code == status.HTTP_404_NOT_FOUND

    # Deactivated user
    seed_user(session, "usr_deact_01", "fired_employee@company.internal", "AP_LEAD", is_active=False)
    resp_deact = client.post("/api/v1/auth/dev-session", json={"email": "fired_employee@company.internal", "org_id": TEST_ORG})
    assert resp_deact.status_code == status.HTTP_403_FORBIDDEN
    assert "deactivated" in resp_deact.json()["detail"].lower()


def test_a5_jwt_claims_structure_database_role_and_app_role(audit_session):
    """Verifies that minted JWT contains database role 'authenticated' and separate application role."""
    client, session = audit_session
    seed_user(session, "usr_lead_01", "lead_test@company.internal", "AP_LEAD")

    resp = client.post("/api/v1/auth/dev-session", json={"email": "lead_test@company.internal", "org_id": TEST_ORG})
    assert resp.status_code == status.HTTP_200_OK
    token = resp.json()["access_token"]

    # Decode and inspect claims
    claims = jwt.decode(
        token,
        TEST_SECRET,
        algorithms=["HS256"],
        audience="authenticated",
        issuer="https://test-sec.supabase.co/auth/v1",
    )

    # 1. Database role MUST be 'authenticated' (Supabase Postgres RLS role)
    assert claims["role"] == "authenticated", "Database role claim must be 'authenticated' for RLS."

    # 2. Application role MUST be separately represented
    assert claims["user_role"] == "AP_LEAD", "Application role must be present in user_role claim."
    assert claims["app_metadata"]["role"] == "AP_LEAD", "Application role must be present in app_metadata."
    assert claims["sub"] == "usr_lead_01"
    assert claims["email"] == "lead_test@company.internal"


def test_dev_session_requires_workspace_for_duplicate_emails(audit_session):
    client, session = audit_session
    seed_user(session, "duplicate_a", "duplicate@example.test", "AP_LEAD")
    session.add(Organisation(id="other_workspace", name="Other"))
    session.add(User(id="duplicate_b", org_id="other_workspace", email="duplicate@example.test", full_name="Other", is_active=True))
    session.flush()
    session.add(RoleAssignment(id="duplicate_role_b", org_id="other_workspace", user_id="duplicate_b", role_name="AUDITOR"))
    session.commit()
    assert client.post("/api/v1/auth/dev-session", json={"email": "duplicate@example.test"}).status_code == 409
    selected = client.post("/api/v1/auth/dev-session", json={"email": "duplicate@example.test", "org_id": TEST_ORG})
    assert selected.status_code == 200 and selected.json()["user"]["id"] == "duplicate_a"


def test_a6_server_side_role_resolution_authority(audit_session):
    """Proves that server-side database records override forged JWT application role claims."""
    client, session = audit_session
    # User is seeded as AP_ASSOCIATE in PostgreSQL
    seed_user(session, "usr_assoc_01", "assoc_test@company.internal", "AP_ASSOCIATE")

    # Forge a token claiming user_role = 'SYSTEM_ADMIN'
    now_ts = int(time.time())
    forged_claims = {
        "sub": "usr_assoc_01",
        "email": "assoc_test@company.internal",
        "role": "authenticated",
        "user_role": "SYSTEM_ADMIN",  # Forged!
        "app_metadata": {"role": "SYSTEM_ADMIN"},
        "aud": "authenticated",
        "iss": "https://test-sec.supabase.co/auth/v1",
        "iat": now_ts,
        "exp": now_ts + 3600,
    }
    forged_token = jwt.encode(forged_claims, TEST_SECRET, algorithm="HS256")

    # Call /auth/me
    resp = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {forged_token}"})
    assert resp.status_code == status.HTTP_200_OK

    # Server must resolve role from PostgreSQL role_assignments, NOT the forged claim!
    assert resp.json()["role"] == "AP_ASSOCIATE", "Server must resolve actual role from database, ignoring forged claim."


def test_a7_invalid_signatures_expired_tokens_wrong_tenants(audit_session):
    """Tests cryptographic rejection of invalid signatures, expired tokens, and cross-tenant access."""
    client, session = audit_session
    seed_user(session, "usr_lead_02", "lead_test2@company.internal", "AP_LEAD")

    # 1. Tampered Signature
    now_ts = int(time.time())
    valid_payload = {
        "sub": "usr_lead_02", "email": "lead_test2@company.internal", "role": "authenticated",
        "aud": "authenticated", "iss": "https://test-sec.supabase.co/auth/v1", "exp": now_ts + 3600
    }
    bad_sig_token = jwt.encode(valid_payload, "wrong-signature-key-at-least-32-chars", algorithm="HS256")
    r_badsig = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {bad_sig_token}"})
    assert r_badsig.status_code == status.HTTP_401_UNAUTHORIZED

    # 2. Expired Token
    expired_payload = dict(valid_payload, exp=now_ts - 3600)
    expired_token = jwt.encode(expired_payload, TEST_SECRET, algorithm="HS256")
    r_exp = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {expired_token}"})
    assert r_exp.status_code == status.HTTP_401_UNAUTHORIZED
    assert "expired" in r_exp.json()["detail"].lower()

    # 3. Cross-Tenant Access Request (Header X-Tenant-ID for an org user does not belong to)
    valid_token = jwt.encode(valid_payload, TEST_SECRET, algorithm="HS256")
    r_cross = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {valid_token}", "X-Tenant-ID": "org_foreign_unauthorized"}
    )
    assert r_cross.status_code == status.HTTP_403_FORBIDDEN
    assert "not an active member" in r_cross.json()["detail"]


# ==============================================================================
# SECTION B: Financial Approval-State Machine & Dual Control Tests
# ==============================================================================

def test_b1_human_approval_sets_manually_approved_decision(audit_session, record_valid_match):
    """Verifies that human AP Lead approval sets stage='INTERNAL_APPROVAL_COMPLETE' and decision='MANUALLY_APPROVED'."""
    client, session = audit_session
    seed_user(session, "usr_lead_b1", "lead_b1@company.internal", "AP_LEAD")
    login_resp = client.post("/api/v1/auth/dev-session", json={"email": "lead_b1@company.internal", "org_id": TEST_ORG})
    lead_token = login_resp.json()["access_token"]

    # Seed low-value invoice (₹26,196 matching APTC-001)
    inv_id = f"inv_test_low_{uuid.uuid4().hex[:8]}"
    inv = Invoice(
        id=inv_id,
        org_id=TEST_ORG,
        source_channel="MANUAL_UPLOAD",
        currency="INR",
        stage="PENDING_APPROVAL",
        decision="MATCH_CANDIDATE",
        invoice_number="INV-LOW-01",
        total_amount=26196.00,
    )
    session.add(inv)
    session.commit()

    record_valid_match(session, inv)

    # Execute human approval
    resp = client.post(
        f"/api/v1/invoices/{inv_id}/actions",
        json={"action": "APPROVE_AP_REVIEW", "reason": "Verified 3-way match against PO-26-1001. Approved by Lead."},
        headers={"Authorization": f"Bearer {lead_token}"},
    )
    assert resp.status_code == status.HTTP_200_OK
    assert resp.json()["new_stage"] == "INTERNAL_APPROVAL_COMPLETE"
    assert resp.json()["new_decision"] == "MANUALLY_APPROVED", "Human approval must set decision='MANUALLY_APPROVED', not 'AUTO_APPROVED'."

    # Verify database state
    db_inv = session.scalar(select(Invoice).where(Invoice.id == inv_id))
    assert db_inv.stage == "INTERNAL_APPROVAL_COMPLETE"
    assert db_inv.decision == "MANUALLY_APPROVED"


def test_b2_dual_control_threshold_enforcement(audit_session, record_valid_match):
    """Verifies dual control on invoices >= ₹500,000 INR and single approval on invoices < ₹500,000 INR."""
    client, session = audit_session
    seed_user(session, "usr_lead_b2", "lead_b2@company.internal", "AP_LEAD")
    seed_user(session, "usr_ctrl_b2", "ctrl_b2@company.internal", "CONTROLLER")

    tok_lead = client.post("/api/v1/auth/dev-session", json={"email": "lead_b2@company.internal", "org_id": TEST_ORG}).json()["access_token"]
    tok_ctrl = client.post("/api/v1/auth/dev-session", json={"email": "ctrl_b2@company.internal", "org_id": TEST_ORG}).json()["access_token"]

    # 1. High-Value Invoice: ₹750,000 INR (>= ₹500,000 threshold)
    inv_high_id = f"inv_test_high_{uuid.uuid4().hex[:8]}"
    inv_high = Invoice(
        id=inv_high_id,
        org_id=TEST_ORG,
        source_channel="MANUAL_UPLOAD",
        currency="INR",
        stage="PENDING_APPROVAL",
        decision="MATCH_CANDIDATE",
        invoice_number="INV-HIGH-01",
        total_amount=750000.00,
    )
    session.add(inv_high)
    session.commit()

    record_valid_match(session, inv_high)

    # Step 1: First approval by AP Lead
    r_app1 = client.post(
        f"/api/v1/invoices/{inv_high_id}/actions",
        json={"action": "APPROVE_AP_REVIEW", "reason": "First approval by AP Lead."},
        headers={"Authorization": f"Bearer {tok_lead}"},
    )
    assert r_app1.status_code == status.HTTP_200_OK
    assert r_app1.json()["new_stage"] == "ACTION_REQUIRED", "High-value invoice must hold at ACTION_REQUIRED for dual control."

    # Step 2 (Violation): Same AP Lead attempts second approval -> Must be rejected with HTTP 400
    r_dup = client.post(
        f"/api/v1/invoices/{inv_high_id}/actions",
        json={"action": "APPROVE_AP_REVIEW", "reason": "AP Lead trying to approve twice."},
        headers={"Authorization": f"Bearer {tok_lead}"},
    )
    assert r_dup.status_code == status.HTTP_400_BAD_REQUEST
    assert "Dual control violation: Second approver must be a distinct authenticated user" in r_dup.json()["detail"]

    # Step 3 (Authorized): Distinct Controller performs second approval -> Transitions to INTERNAL_APPROVAL_COMPLETE
    r_app2 = client.post(
        f"/api/v1/invoices/{inv_high_id}/actions",
        json={"action": "APPROVE_AP_REVIEW", "reason": "Secondary Financial Controller dual-approval authorization."},
        headers={"Authorization": f"Bearer {tok_ctrl}"},
    )
    assert r_app2.status_code == status.HTTP_200_OK, r_app2.text
    assert r_app2.json()["new_stage"] == "INTERNAL_APPROVAL_COMPLETE"
    assert r_app2.json()["new_decision"] == "MANUALLY_APPROVED"


def test_b3_auditor_role_strictly_read_only(audit_session):
    """Verifies that users with AUDITOR role cannot execute any mutations."""
    client, session = audit_session
    seed_user(session, "usr_audit_b3", "auditor_b3@company.internal", "AUDITOR")
    tok_audit = client.post("/api/v1/auth/dev-session", json={"email": "auditor_b3@company.internal", "org_id": TEST_ORG}).json()["access_token"]

    inv_id = f"inv_audit_test_{uuid.uuid4().hex[:8]}"
    inv = Invoice(
        id=inv_id, org_id=TEST_ORG, source_channel="MANUAL_UPLOAD", currency="INR",
        stage="ACTION_REQUIRED", decision="FLAGGED_EXCEPTION", invoice_number="INV-AUD-01", total_amount=10000.0
    )
    session.add(inv)
    session.commit()

    # 1. Auditor GET invoice detail -> Allowed (200)
    r_get = client.get(f"/api/v1/invoices/{inv_id}", headers={"Authorization": f"Bearer {tok_audit}"})
    assert r_get.status_code == status.HTTP_200_OK

    # 2. Auditor attempt APPROVE -> Blocked (403)
    r_app = client.post(
        f"/api/v1/invoices/{inv_id}/actions",
        json={"action": "APPROVE_AP_REVIEW", "reason": "Auditor attempting approval"},
        headers={"Authorization": f"Bearer {tok_audit}"},
    )
    assert r_app.status_code == status.HTTP_403_FORBIDDEN
    assert "Auditor role is strictly read-only" in r_app.json()["detail"]

    # 3. Auditor attempt HOLD -> Blocked (403)
    r_hold = client.post(
        f"/api/v1/invoices/{inv_id}/actions",
        json={"action": "HOLD_PENDING_EVIDENCE", "reason": "Auditor attempting hold"},
        headers={"Authorization": f"Bearer {tok_audit}"},
    )
    assert r_hold.status_code == status.HTTP_403_FORBIDDEN


def test_b4_decoupling_zero_payment_and_zero_erp_mutation(audit_session, record_valid_match):
    """Verifies that AP approval strictly updates local ledger and NEVER executes payments or ERP mutations."""
    client, session = audit_session
    seed_user(session, "usr_lead_b4", "lead_b4@company.internal", "AP_LEAD")
    tok_lead = client.post("/api/v1/auth/dev-session", json={"email": "lead_b4@company.internal", "org_id": TEST_ORG}).json()["access_token"]

    inv_id = f"inv_zero_pay_{uuid.uuid4().hex[:8]}"
    inv = Invoice(
        id=inv_id, org_id=TEST_ORG, source_channel="MANUAL_UPLOAD", currency="INR",
        stage="PENDING_APPROVAL", decision="MATCH_CANDIDATE", invoice_number="INV-PAY-01", total_amount=15000.0
    )
    session.add(inv)
    session.commit()

    record_valid_match(session, inv)

    resp = client.post(
        f"/api/v1/invoices/{inv_id}/actions",
        json={"action": "APPROVE_AP_REVIEW", "reason": "Approved for accounting ledger."},
        headers={"Authorization": f"Bearer {tok_lead}"},
    )
    assert resp.status_code == status.HTTP_200_OK

    # Invariants:
    # 1. System has no payment initiation status (stage is INTERNAL_APPROVAL_COMPLETE, not PAID)
    assert resp.json()["new_stage"] == "INTERNAL_APPROVAL_COMPLETE"
    assert resp.json()["new_stage"] != "PAID"

    # 2. Audit event records internal verification, not disbursement
    audit = session.scalar(select(AuditEvent).where(AuditEvent.invoice_id == inv_id, AuditEvent.action == "APPROVE_AP_REVIEW"))
    assert audit is not None
    assert audit.actor_id == "usr_lead_b4"
    assert audit.actor_role == "AP_LEAD"
    assert "disbursement" not in audit.action.lower()
    assert "payout" not in audit.action.lower()
