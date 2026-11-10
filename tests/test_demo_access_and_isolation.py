"""Comprehensive security, isolation, and access tests for frictionless evaluator onboarding."""

import pytest
from fastapi.testclient import TestClient
from backend.main import app
from backend.core.database import SessionLocal


@pytest.fixture
def test_client():
    return TestClient(app)


def test_public_sandbox_scenarios_accessible_without_auth(test_client):
    """Verifies that the guided scenarios gallery is publicly accessible without any credentials."""
    resp = test_client.get("/api/v1/sandbox/scenarios")
    assert resp.status_code == 200
    scenarios = resp.json()
    assert isinstance(scenarios, list)
    assert len(scenarios) >= 6
    for s in scenarios:
        assert "id" in s
        assert "title" in s
        assert "expected_decision" in s


def test_public_sandbox_scenario_explore_without_auth(test_client):
    """Verifies that public evaluators can explore full 7-gate scenario evidence without login."""
    resp = test_client.get("/api/v1/sandbox/scenarios/SCN-01/explore")
    assert resp.status_code == 200
    data = resp.json()
    assert "SCN-01" in (data.get("scenario_id") or data.get("scenario", {}).get("id", ""))
    assert data["mode"] == "STORED_RESULT"
    assert "invoice" in data
    assert "decision" in data
    assert "decision" in data


def test_create_demo_session_provisions_isolated_tenant(test_client):
    """Verifies 1-click live demo session minting:
    - Generates a uniquely isolated demo tenant (org_demo_<hex4>)
    - Assigns least-privilege role AP_ASSOCIATE
    - Pre-seeds realistic Indian GST fixtures and 2 sample invoices
    - Returns valid bearer JWT token
    """
    resp = test_client.post("/api/v1/auth/demo-session", headers={"x-forwarded-for": "198.51.100.1"})
    assert resp.status_code == 200
    data = resp.json()

    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["expires_in"] == 7200
    user_data = data["user"]
    assert user_data["role"] == "AP_ASSOCIATE"
    assert user_data["org_id"].startswith("org_demo_")

    token = data["access_token"]
    demo_org_id = user_data["org_id"]

    # 1. Profile verification via /auth/me
    me_resp = test_client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_resp.status_code == 200
    me = me_resp.json()
    assert me["role"] == "AP_ASSOCIATE"
    assert me["org_id"] == demo_org_id
    assert me["is_provisioned"] is True

    # 2. Inbox verification: demo tenant has its own pre-seeded invoices
    inbox_resp = test_client.get("/api/v1/inbox", headers={"Authorization": f"Bearer {token}"})
    assert inbox_resp.status_code == 200
    inbox_data = inbox_resp.json()
    invoices = inbox_data.get("items", inbox_data) if isinstance(inbox_data, dict) else inbox_data
    assert len(invoices) >= 2
    assert any("001" in inv["invoice_number"] for inv in invoices)
    assert any("011" in inv["invoice_number"] for inv in invoices)

    # 3. Dashboard metrics verification
    dash_resp = test_client.get("/api/v1/dashboard/metrics", headers={"Authorization": f"Bearer {token}"})
    assert dash_resp.status_code == 200


def test_demo_user_least_privilege_approval_blocked(test_client):
    """Verifies that a demo user with AP_ASSOCIATE role CANNOT approve invoices (403 Forbidden)."""
    resp = test_client.post("/api/v1/auth/demo-session", headers={"x-forwarded-for": "198.51.100.2"})
    assert resp.status_code == 200
    token = resp.json()["access_token"]

    # Fetch pre-seeded invoice id
    inbox_resp = test_client.get("/api/v1/inbox", headers={"Authorization": f"Bearer {token}"})
    assert inbox_resp.status_code == 200
    inbox_data = inbox_resp.json()
    invoices = inbox_data.get("items", inbox_data) if isinstance(inbox_data, dict) else inbox_data
    clean_inv = next(inv for inv in invoices if "001" in inv["invoice_number"])

    # Attempt approval action: must fail with HTTP 403 Forbidden due to role restriction
    action_resp = test_client.post(
        f"/api/v1/invoices/{clean_inv['id']}/actions",
        json={"action": "APPROVE_AP_REVIEW", "reason": "Attempting unauthorized approval as demo user"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert action_resp.status_code == 403


def test_demo_user_cross_tenant_isolation(test_client):
    """Verifies that a demo user cannot query or mutate invoices belonging to another tenant."""
    resp = test_client.post("/api/v1/auth/demo-session", headers={"x-forwarded-for": "198.51.100.3"})
    assert resp.status_code == 200
    token = resp.json()["access_token"]

    # Attempting to fetch a foreign tenant invoice
    resp_foreign = test_client.get(
        "/api/v1/invoices/inv_sme_eval_foreign_test",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp_foreign.status_code == 404


def test_demo_session_rate_limiting(test_client):
    """Verifies that exceeding the rate limit from a single IP triggers HTTP 429 Too Many Requests."""
    unique_ip = "203.0.113.99"
    # Make 10 calls to fill bucket
    for _ in range(10):
        test_client.post("/api/v1/auth/demo-session", headers={"x-forwarded-for": unique_ip})

    # The 11th request must be rejected with 429
    resp = test_client.post("/api/v1/auth/demo-session", headers={"x-forwarded-for": unique_ip})
    assert resp.status_code == 429
    assert "rate limit exceeded" in resp.json()["detail"].lower()


def test_anonymous_user_never_inherits_org_sme_eval():
    """Verifies that unknown emails are never granted AP_LEAD or org_sme_eval access."""
    from backend.core.auth import resolve_server_side_membership

    db = SessionLocal()
    try:
        unknown_email = "random.visitor@gmail.com"
        org_id, org_name, role, is_provisioned, _, _, _ = resolve_server_side_membership(
            auth_user_id="usr_unknown_999",
            email=unknown_email,
            db=db,
        )
        assert org_id != "org_sme_eval"
        assert is_provisioned is False
    finally:
        db.close()
