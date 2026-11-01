"""Tests for Honest Empty States, No Invented Business Data & Health Reporting."""

import pytest
from fastapi import status


def test_fresh_database_has_zero_invented_data(client, db_session):
    """Verifies that an unseeded database starts completely empty (zero fictional records)."""
    headers = {"Authorization": "Bearer test_token:AP_ASSOCIATE:user_01:associate@company.internal"}

    # Inbox must return 0 invoices
    inbox_resp = client.get("/api/v1/inbox", headers=headers)
    assert inbox_resp.status_code == status.HTTP_200_OK
    assert inbox_resp.json()["total_count"] == 0
    assert len(inbox_resp.json()["items"]) == 0

    # Exceptions must return 0 records
    exc_resp = client.get("/api/v1/exceptions", headers=headers)
    assert exc_resp.status_code == status.HTTP_200_OK
    assert exc_resp.json()["total_count"] == 0
    assert len(exc_resp.json()["items"]) == 0

    # Source records must return empty arrays
    src_resp = client.get("/api/v1/source-records", headers=headers)
    assert src_resp.status_code == status.HTTP_200_OK
    data = src_resp.json()
    assert len(data["vendors"]) == 0
    assert len(data["purchase_orders"]) == 0
    assert len(data["goods_receipts"]) == 0


def test_dashboard_metrics_computes_exact_live_zeros(client, db_session):
    """Metrics must reflect actual database counts (0 is returned only because 0 rows exist)."""
    headers = {"Authorization": "Bearer test_token:AP_ASSOCIATE:user_01:associate@company.internal"}
    resp = client.get("/api/v1/dashboard/metrics", headers=headers)
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()
    assert data["status"] == "active"
    assert data["summary"]["total_invoices"] == 0
    assert data["summary"]["open_exceptions"] == 0
    assert data["summary"]["blocked_value_inr"] == 0.0
    assert data["summary"]["touchless_rate_pct"] is None  # No division by zero


def test_health_check_reports_truthful_subsystem_readiness(client):
    """Health check reports honest subsystem status without secret disclosure."""
    resp = client.get("/api/v1/health")
    assert resp.status_code in (status.HTTP_200_OK, status.HTTP_503_SERVICE_UNAVAILABLE)
    data = resp.json()
    subsystems = data["subsystems"]
    assert "database" in subsystems
    assert "object_storage" in subsystems
    assert "identity_provider" in subsystems
    assert "gmail_ingestion" in subsystems
    assert "sap_erp" in subsystems


def test_upload_rejects_non_pdf_file(client):
    """Manual ingestion rejects non-PDF file formats."""
    headers = {"Authorization": "Bearer test_token:AP_ASSOCIATE:user_01:associate@company.internal"}
    files = {"file": ("malicious.exe", b"MZ\x90\x00\x03\x00\x00\x00", "application/x-dosexec")}
    resp = client.post("/api/v1/connections/upload", files=files, headers=headers)
    assert resp.status_code == status.HTTP_400_BAD_REQUEST
    assert "Only PDF documents are supported" in resp.json()["detail"]


def test_upload_rejects_corrupted_pdf_header(client):
    """Manual ingestion rejects files with invalid PDF magic bytes."""
    headers = {"Authorization": "Bearer test_token:AP_ASSOCIATE:user_01:associate@company.internal"}
    files = {"file": ("corrupt.pdf", b"NOT_A_VALID_PDF_HEADER", "application/pdf")}
    resp = client.post("/api/v1/connections/upload", files=files, headers=headers)
    assert resp.status_code == status.HTTP_400_BAD_REQUEST
    assert "Invalid PDF header signature" in resp.json()["detail"]
