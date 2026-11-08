"""Tests for Evaluator Authentication, Account Creation Rejection & Dual-Control Approval.

Verifies:
1. Unknown emails with valid IdP credentials do NOT automatically gain org_sme_eval access (HTTP 403 / unprovisioned).
2. Unprovisioned users are restricted from tenant workspace data.
3. Dual-control threshold enforcement: High-value invoices (>= 500,000 INR) require two distinct approvers.
4. AP Lead cannot complete Step 2 Controller sign-off on high-value invoices.
5. First approver cannot self-approve Step 2 (anti-self-approval protection).
"""

from decimal import Decimal
from unittest.mock import MagicMock
import pytest
from fastapi import HTTPException

from backend.core.auth import AuthenticatedUser, UserRole, resolve_server_side_membership
from backend.core.config import AppEnv, settings
from backend.models.domain import ApprovalRequest, Invoice, WorkOrderSnapshot


def test_unknown_email_does_not_gain_org_sme_eval_access(monkeypatch):
    """An identity authenticated at the IdP whose subject is not in identity_memberships is barred from org_sme_eval."""
    monkeypatch.setattr(settings, "APP_ENV", AppEnv.DEVELOPMENT)

    mock_db = MagicMock()
    mock_db.bind.dialect.name = "sqlite"
    mock_db.execute.return_value.fetchall.return_value = []
    mock_db.scalars.return_value.all.return_value = []
    mock_db.scalar.return_value = None

    # Case A: Requesting org_sme_eval explicitly raises HTTP 403 Forbidden
    with pytest.raises(HTTPException) as exc_info:
        resolve_server_side_membership(
            auth_user_id="auth0|unauthorized-visitor-12345",
            email="unauthorized_visitor@external.com",
            requested_org_id="org_sme_eval",
            db=mock_db,
        )
    assert exc_info.value.status_code == 403
    assert "no active membership in the selected workspace" in exc_info.value.detail

    # Case B: Requesting without specific workspace returns unprovisioned (is_provisioned=False)
    org_id, org_name, role, is_provisioned, available_orgs, member_id, is_owner = resolve_server_side_membership(
        auth_user_id="auth0|unauthorized-visitor-12345",
        email="unauthorized_visitor@external.com",
        requested_org_id=None,
        db=mock_db,
    )
    assert is_provisioned is False
    assert org_id is None
    assert role is None
    assert len(available_orgs) == 0


def test_dual_control_blocks_ap_lead_from_granting_second_approval(monkeypatch):
    """On high-value invoices (>= 500k INR), Step 2 Controller sign-off requires CONTROLLER or SYSTEM_ADMIN role."""
    from backend.api.v1.invoices import execute_invoice_action, ActionPayload

    ap_lead_user = AuthenticatedUser(
        id="usr_lead_02",
        auth_subject="sub_lead_02",
        email="ap_lead_two@company.internal",
        name="Second AP Lead",
        role=UserRole.AP_LEAD,
        org_id="org_sme_eval",
        org_name="SME Eval",
        is_provisioned=True,
    )

    mock_db = MagicMock()
    mock_inv = MagicMock(spec=Invoice)
    mock_inv.id = "inv_high_value_01"
    mock_inv.org_id = "org_sme_eval"
    mock_inv.stage = "ACTION_REQUIRED"
    mock_inv.decision = "PENDING_SECOND_APPROVAL"
    mock_inv.workflow_substatus = "PENDING_SECOND_APPROVAL"
    mock_inv.currency = "INR"
    mock_inv.total_amount = Decimal("750000.00")  # >= 500k threshold
    mock_inv.net_payable_amount = Decimal("750000.00")
    mock_inv.po_reference = "PO-26-2001"

    mock_approval_req = MagicMock(spec=ApprovalRequest)
    mock_approval_req.status = "PENDING_SECOND_APPROVAL"
    mock_approval_req.first_approver_id = "usr_lead_01"
    mock_approval_req.requires_dual_approval = True

    mock_db.scalar.side_effect = [
        mock_inv,
        mock_approval_req,
        MagicMock(spec=WorkOrderSnapshot),
        MagicMock(overall_result="PASS"),
    ]

    payload = ActionPayload(action="APPROVE_AP_REVIEW", reason="Lead attempting second sign-off")

    with pytest.raises(HTTPException) as exc_info:
        execute_invoice_action(
            invoice_id="inv_high_value_01",
            payload=payload,
            current_user=ap_lead_user,
            db=mock_db,
        )

    assert exc_info.value.status_code in (400, 403)


def test_dual_control_blocks_first_approver_self_approval(monkeypatch):
    """The first approver cannot approve Step 2 even if they hold Controller privileges (anti-self-approval)."""
    from backend.api.v1.invoices import execute_invoice_action, ActionPayload

    controller_user = AuthenticatedUser(
        id="usr_controller_01",
        auth_subject="sub_controller_01",
        email="controller@company.internal",
        name="Financial Controller",
        role=UserRole.CONTROLLER,
        org_id="org_sme_eval",
        org_name="SME Eval",
        is_provisioned=True,
    )

    mock_db = MagicMock()
    mock_inv = MagicMock(spec=Invoice)
    mock_inv.id = "inv_high_value_01"
    mock_inv.org_id = "org_sme_eval"
    mock_inv.stage = "ACTION_REQUIRED"
    mock_inv.decision = "PENDING_SECOND_APPROVAL"
    mock_inv.workflow_substatus = "PENDING_SECOND_APPROVAL"
    mock_inv.currency = "INR"
    mock_inv.total_amount = Decimal("600000.00")
    mock_inv.net_payable_amount = Decimal("600000.00")
    mock_inv.po_reference = "PO-26-2001"

    mock_approval_req = MagicMock(spec=ApprovalRequest)
    mock_approval_req.status = "PENDING_SECOND_APPROVAL"
    mock_approval_req.first_approver_id = "usr_controller_01"  # Same user
    mock_approval_req.requires_dual_approval = True

    mock_db.scalar.side_effect = [
        mock_inv,
        mock_approval_req,
        MagicMock(spec=WorkOrderSnapshot),
        MagicMock(overall_result="PASS"),
    ]

    payload = ActionPayload(action="APPROVE_AP_REVIEW", reason="Attempting self approval")

    with pytest.raises(HTTPException) as exc_info:
        execute_invoice_action(
            invoice_id="inv_high_value_01",
            payload=payload,
            current_user=controller_user,
            db=mock_db,
        )

    assert exc_info.value.status_code in (400, 403)
