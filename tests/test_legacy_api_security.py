"""Regression tests for Legacy Demo API environment gating (P1-1 Security Audit).

Verifies that:
1. When APP_ENV == AppEnv.PRODUCTION, unauthenticated legacy engine routes
   (/legacy-api, /engine-api) and the legacy UI (/legacy) are strictly unavailable (HTTP 404),
   preventing anonymous state mutations, in-memory ERP resets, or arbitrary PDF parsing.
2. When APP_ENV == AppEnv.DEVELOPMENT, the legacy demonstration UI and APIs
   remain available for local offline demonstration parity.
"""

import importlib
import pytest
from fastapi.testclient import TestClient


def test_legacy_endpoints_disabled_in_production(monkeypatch):
    """In production mode, /legacy-api, /engine-api, and /legacy must return 404."""
    import backend.core.config as config_mod
    import backend.main as main_mod

    try:
        monkeypatch.setenv("APP_ENV", "production")
        monkeypatch.setenv("SECRET_KEY", "a-very-secure-random-secret-key-32chars-long-prod")
        monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@ep-live.aws.supabase.com:6543/postgres")
        monkeypatch.setenv("STORAGE_BUCKET_NAME", "invoices")
        
        # Reload config and main app under production environment
        importlib.reload(config_mod)
        importlib.reload(main_mod)
        
        client = TestClient(main_mod.app)
        
        # 1. State-changing reset endpoint must return 404
        resp_reset = client.post("/legacy-api/api/reset-data")
        assert resp_reset.status_code == 404, f"Expected 404 for reset-data in production, got {resp_reset.status_code}"
        
        # 2. State-changing upload endpoint must return 404
        resp_upload = client.post("/legacy-api/api/upload-invoice")
        assert resp_upload.status_code == 404, f"Expected 404 for upload-invoice in production, got {resp_upload.status_code}"
        
        # 3. Engine-api alias must return 404
        resp_engine = client.post("/engine-api/api/reset-data")
        assert resp_engine.status_code == 404, f"Expected 404 for engine-api in production, got {resp_engine.status_code}"
        
        # 4. Legacy UI template must return 404
        resp_ui = client.get("/legacy")
        assert resp_ui.status_code == 404, f"Expected 404 for /legacy in production, got {resp_ui.status_code}"
    finally:
        # Restore development environment so subsequent tests and conftest fixtures run cleanly
        monkeypatch.setenv("APP_ENV", "development")
        monkeypatch.setenv("SECRET_KEY", "dev-secret-key-must-be-changed-in-production-32chars")
        importlib.reload(config_mod)
        importlib.reload(main_mod)


def test_legacy_endpoints_available_in_development(monkeypatch):
    """In development mode, /legacy and /legacy-api remain functional for local inspection."""
    import backend.core.config as config_mod
    import backend.main as main_mod

    monkeypatch.setenv("APP_ENV", "development")
    
    # Reload config and main app under development environment
    importlib.reload(config_mod)
    importlib.reload(main_mod)
    
    client = TestClient(main_mod.app)
    
    # 1. Legacy UI must be served
    resp_ui = client.get("/legacy")
    assert resp_ui.status_code == 200
    assert "html" in resp_ui.headers.get("content-type", "").lower()
    
    # 2. Legacy scenarios API must return 200
    resp_scenarios = client.get("/legacy-api/api/scenarios")
    assert resp_scenarios.status_code == 200
    data = resp_scenarios.json()
    assert isinstance(data, list)
    assert len(data) > 0
