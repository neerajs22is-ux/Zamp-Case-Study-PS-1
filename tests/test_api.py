"""Integration tests for FastAPI endpoints."""

from fastapi.testclient import TestClient
from engine.server import app

client = TestClient(app)


def test_api_health():
    res = client.get("/api/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "healthy"
    assert data["active_vendors"] >= 3
    assert data["open_pos"] >= 4


def test_serve_dashboard():
    res = client.get("/")
    assert res.status_code == 200
    assert "text/html" in res.headers["content-type"]
    assert "Zamp Pace" in res.text


def test_api_scenarios_list():
    res = client.get("/api/scenarios")
    assert res.status_code == 200
    scenarios = res.json()
    assert len(scenarios) == 5
    scenario_ids = [s["id"] for s in scenarios]
    assert "HP-01-Happy-Path" in scenario_ids
    assert "EC-01-Split-PO-Overrun" in scenario_ids
    assert "EC-02-Duplicate-Submission" in scenario_ids
    assert "EC-03-Price-Spike-Variance" in scenario_ids
    assert "EC-04-Low-Res-Missing-PO" in scenario_ids


def test_api_run_happy_path():
    res = client.post("/api/run-scenario/HP-01-Happy-Path")
    assert res.status_code == 200
    data = res.json()
    assert data["decision"] == "AUTO_APPROVED"
    assert data["erp_voucher_id"] is not None


def test_api_run_edge_case_split_po():
    res = client.post("/api/run-scenario/EC-01-Split-PO-Overrun")
    assert res.status_code == 200
    data = res.json()
    assert data["decision"] == "FLAGGED_HITL_REVIEW"
    assert "split_po_overrun" in data["discrepancy_details"]


def test_api_runs_history_and_metrics():
    res = client.get("/api/runs")
    assert res.status_code == 200
    data = res.json()
    assert "metrics" in data
    assert "runs" in data
    assert data["metrics"]["total_runs"] >= 2
