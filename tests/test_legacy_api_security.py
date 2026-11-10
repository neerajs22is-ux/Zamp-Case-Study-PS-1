"""Regression tests for Legacy Demo API environment gating (P1-1 Security Audit).

Verifies that:
1. When APP_ENV == AppEnv.PRODUCTION, unauthenticated legacy engine routes
   (/legacy-api, /engine-api) and the legacy UI (/legacy) are strictly unavailable (HTTP 404),
   preventing anonymous state mutations, in-memory ERP resets, or arbitrary PDF parsing.
2. When APP_ENV == AppEnv.DEVELOPMENT, the legacy demonstration UI and APIs
   remain available for local offline demonstration parity.

Test isolation: ``backend.main`` decides at *import time* whether the legacy engine is mounted, so
each environment is exercised in a fresh interpreter. The previous implementation called
``importlib.reload`` on ``backend.core.config`` and ``backend.main`` inside the pytest process, which
replaced the shared ``settings`` singleton and the ``AppEnv`` enum class for every later test
(stale ``settings``/``AppEnv`` references, enum identity mismatches, wrong ``APP_ENV``).
"""

import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

_PROBE = textwrap.dedent(
    """
    import json, sys
    from fastapi.testclient import TestClient
    import backend.main as main_mod

    probes = json.loads(sys.argv[1])
    client = TestClient(main_mod.app)
    results = []
    for method, path in probes:
        resp = client.request(method, path)
        entry = {"status": resp.status_code, "content_type": resp.headers.get("content-type", "")}
        if path.endswith("/scenarios"):
            try:
                entry["json"] = resp.json()
            except Exception:
                entry["json"] = None
        results.append(entry)
    print("PROBE_RESULT=" + json.dumps(results))
    """
)


def _probe(env_overrides, probes):
    """Import the app in a fresh interpreter under ``env_overrides`` and replay ``probes``."""
    env = os.environ.copy()
    env.update(env_overrides)
    proc = subprocess.run(
        [sys.executable, "-c", _PROBE, json.dumps(probes)],
        cwd=str(REPO_ROOT),
        env=env,
        capture_output=True,
        text=True,
        timeout=180,
    )
    assert proc.returncode == 0, (
        f"Isolated app probe failed (rc={proc.returncode}).\nSTDOUT:\n{proc.stdout[-2000:]}\nSTDERR:\n{proc.stderr[-4000:]}"
    )
    marker = [line for line in proc.stdout.splitlines() if line.startswith("PROBE_RESULT=")]
    assert marker, f"Probe produced no result.\nSTDOUT:\n{proc.stdout[-2000:]}\nSTDERR:\n{proc.stderr[-2000:]}"
    return json.loads(marker[-1][len("PROBE_RESULT="):])


def test_legacy_endpoints_disabled_in_production():
    """In production mode, /legacy-api, /engine-api, and /legacy must return 404."""
    probes = [
        ["POST", "/legacy-api/api/reset-data"],      # state-changing reset endpoint
        ["POST", "/legacy-api/api/upload-invoice"],  # state-changing upload endpoint
        ["POST", "/engine-api/api/reset-data"],      # engine-api alias
        ["GET", "/legacy"],                          # legacy UI template
    ]
    labels = ["reset-data", "upload-invoice", "engine-api reset-data", "/legacy UI"]
    results = _probe(
        {
            "APP_ENV": "production",
            "SECRET_KEY": "a-very-secure-random-secret-key-32chars-long-prod",
            "DATABASE_URL": "postgresql://user:pass@ep-live.aws.supabase.com:6543/postgres",
            "STORAGE_BUCKET_NAME": "invoices",
        },
        probes,
    )
    for label, result in zip(labels, results):
        assert result["status"] == 404, f"Expected 404 for {label} in production, got {result['status']}"


def test_legacy_endpoints_available_in_development():
    """In development mode, /legacy and /legacy-api remain functional for local inspection."""
    results = _probe(
        {
            "APP_ENV": "development",
            "SECRET_KEY": "dev-secret-key-must-be-changed-in-production-32chars",
        },
        [["GET", "/legacy"], ["GET", "/legacy-api/api/scenarios"]],
    )
    ui, scenarios = results

    # 1. Legacy UI must be served
    assert ui["status"] == 200
    assert "html" in ui["content_type"].lower()

    # 2. Legacy scenarios API must return 200
    assert scenarios["status"] == 200
    assert isinstance(scenarios["json"], list)
    assert len(scenarios["json"]) > 0
