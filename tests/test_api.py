"""Integration tests for FastAPI endpoints."""

import json
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
    assert "Autonomous AP Command Center" in res.text


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


def test_api_stream_scenario_incremental_sse():
    """F-01: Verify stream-scenario emits genuine progressive SSE events."""
    with client.stream("GET", "/api/stream-scenario/HP-01-Happy-Path") as res:
        assert res.status_code == 200
        events = []
        for line in res.iter_lines():
            if line.startswith("data: "):
                data = json.loads(line[6:])
                events.append(data)

        event_types = [e["event"] for e in events]
        assert "INIT" in event_types
        assert "STAGE_START" in event_types
        assert "STAGE_COMPLETE" in event_types
        assert "DECISION_FINAL" in event_types

        # Check final decision in stream
        final = next(e for e in events if e["event"] == "DECISION_FINAL")
        assert final["decision"] == "AUTO_APPROVED"
        assert len(final["audit"]["stage_timings"]) == 5


def test_api_operator_action_endpoints():
    """F-36/HITL: Human operator can override, reject, or record clarification."""
    # 1. Run EC-01 which yields FLAGGED_HITL_REVIEW
    res1 = client.post("/api/run-scenario/EC-01-Split-PO-Overrun")
    assert res1.status_code == 200
    audit1 = res1.json()
    assert audit1["decision"] == "FLAGGED_HITL_REVIEW"
    run_id = audit1["run_id"]

    # 2. Operator overrides tolerance
    res_override = client.post(
        f"/api/invoices/{run_id}/action",
        json={"action": "APPROVE", "notes": "Controller signed off on split-PO allocation"}
    )
    assert res_override.status_code == 200
    updated = res_override.json()
    assert updated["status"] == "SUCCESS"
    assert updated["decision"] == "AUTO_APPROVED"
    assert "operator_override" in updated["audit"]["discrepancy_details"]
