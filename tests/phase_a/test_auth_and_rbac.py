"""Tests for Authentication & Server-Side RBAC Enforcement."""

import pytest
from fastapi import status


def test_unauthenticated_request_rejected_on_protected_routes(client):
    """Protected endpoints must reject requests lacking Bearer authorization with HTTP 401."""
    protected_endpoints = [
        ("GET", "/api/v1/auth/me"),
        ("GET", "/api/v1/dashboard/metrics"),
        ("GET", "/api/v1/connections"),
        ("GET", "/api/v1/inbox"),
        ("GET", "/api/v1/invoices/inv_123"),
        ("GET", "/api/v1/exceptions"),
        ("GET", "/api/v1/source-records"),
        ("GET", "/api/v1/audit"),
    ]
    for method, endpoint in protected_endpoints:
        if method == "GET":
            resp = client.get(endpoint)
        else:
            resp = client.post(endpoint)
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED, f"Expected 401 on {endpoint}, got {resp.status_code}"


def test_authenticated_user_access_succeeds(client):
    """Requests with valid Bearer tokens succeed and resolve actor profile."""
    headers = {"Authorization": "Bearer test_token:AP_ASSOCIATE:user_01:associate@company.internal"}
    resp = client.get("/api/v1/auth/me", headers=headers)
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()
    assert data["email"] == "associate@company.internal"
    assert data["role"] == "AP_ASSOCIATE"


def test_auditor_role_barred_from_executing_mutations(client, db_session):
    """Auditors are strictly read-only and cannot mutate invoice state (returns 403 Forbidden)."""
    from backend.models.domain import Invoice
    inv = Invoice(
        id="inv_test_audit_role",
        org_id="org_default",
        source_channel="MANUAL_UPLOAD",
        stage="RECEIVED",
        decision="NEEDS_REVIEW",
    )
    db_session.add(inv)
    db_session.commit()

    headers = {"Authorization": "Bearer test_token:AUDITOR:auditor_01:auditor@company.internal"}
    resp = client.post(
        "/api/v1/invoices/inv_test_audit_role/actions",
        json={"action": "APPROVE_AP_REVIEW", "reason": "Attempted unauthorized auditor approval"},
        headers=headers,
    )
    assert resp.status_code == status.HTTP_403_FORBIDDEN
    assert "read-only and cannot execute mutations" in resp.json()["detail"]


def test_dual_control_rejects_self_approval(client, db_session, record_valid_match):
    """High-value invoices require two distinct approvers. First approver cannot approve twice."""
    from backend.models.domain import Invoice
    # Create invoice exceeding dual approval threshold (₹5,00,000)
    inv = Invoice(
        id="inv_high_val_01",
        org_id="org_default",
        source_channel="MANUAL_UPLOAD",
        stage="RECEIVED",
        decision="NEEDS_REVIEW",
        total_amount=650000.00,
    )
    db_session.add(inv)
    db_session.commit()

    lead_headers = {"Authorization": "Bearer test_token:AP_LEAD:lead_user_01:lead@company.internal"}
    record_valid_match(db_session, inv)

    # First approval succeeds and sets status to PENDING_SECOND_APPROVAL
    resp1 = client.post(
        "/api/v1/invoices/inv_high_val_01/actions",
        json={"action": "APPROVE_AP_REVIEW", "reason": "First level AP Lead review passed."},
        headers=lead_headers,
    )
    assert resp1.status_code == status.HTTP_200_OK

    # Second approval attempt by SAME user must fail with HTTP 400
    resp2 = client.post(
        "/api/v1/invoices/inv_high_val_01/actions",
        json={"action": "APPROVE_AP_REVIEW", "reason": "Attempting second approval with same actor."},
        headers=lead_headers,
    )
    assert resp2.status_code == status.HTTP_400_BAD_REQUEST
    assert "Dual control violation: Second approver must be a distinct authenticated user" in resp2.json()["detail"]

    # Second approval by DISTINCT user (Controller) succeeds
    controller_headers = {"Authorization": "Bearer test_token:CONTROLLER:controller_user_02:controller@company.internal"}
    resp3 = client.post(
        "/api/v1/invoices/inv_high_val_01/actions",
        json={"action": "APPROVE_AP_REVIEW", "reason": "Secondary Controller sign-off granted."},
        headers=controller_headers,
    )
    assert resp3.status_code == status.HTTP_200_OK
    assert resp3.json()["new_stage"] == "INTERNAL_APPROVAL_COMPLETE"
    assert resp3.json()["new_decision"] in ("MANUALLY_APPROVED", "AUTO_APPROVED")
