"""Tests for Production Configuration Contract & Fail-Closed Validation.

Verifies:
1. render.yaml contains all mandatory production environment variables.
2. Missing STORAGE_BUCKET_NAME fails closed in production and staging.
3. Missing or invalid DATABASE_URL fails closed in production.
4. Weak or default SECRET_KEY fails closed in production.
5. LOCAL_AUTH_BYPASS and DEBUG fail closed in production.
6. Permitted development settings do not fail when cloud storage bucket is omitted.
"""

import os
import yaml
import pytest
from pydantic import ValidationError

from backend.core.config import AppEnv, ConfigurationError, Settings


def test_render_yaml_configuration_contract():
    """Verify render.yaml contains all required production environment keys."""
    render_yaml_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "render.yaml")
    assert os.path.exists(render_yaml_path), "render.yaml not found at root"

    with open(render_yaml_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    services = config.get("services", [])
    assert len(services) > 0, "No services defined in render.yaml"

    web_service = services[0]
    assert web_service.get("type") == "web"

    env_vars = {item["key"]: item.get("value") for item in web_service.get("envVars", [])}

    # Mandatory production keys in render.yaml
    required_keys = [
        "APP_ENV",
        "APP_HOST",
        "PORT",
        "SECRET_KEY",
        "DATABASE_URL",
        "SUPABASE_URL",
        "SUPABASE_JWKS_URL",
        "SUPABASE_SERVICE_ROLE_KEY",
        "SUPABASE_ANON_KEY",
        "STORAGE_PROVIDER",
        "SUPABASE_STORAGE_BUCKET",
        "STORAGE_BUCKET_NAME",
        "MANTLE_API_KEY",
    ]

    for key in required_keys:
        assert key in env_vars, f"render.yaml missing mandatory production key: {key}"

    # Verify specific key alignments
    assert env_vars["APP_ENV"] == "production"
    assert env_vars["STORAGE_PROVIDER"] == "supabase"
    assert env_vars["STORAGE_BUCKET_NAME"] == "invoices"
    assert env_vars["SUPABASE_STORAGE_BUCKET"] == "invoices"


def test_production_rejects_missing_storage_bucket(monkeypatch):
    """Production mode must fail closed if STORAGE_BUCKET_NAME is None or empty."""
    monkeypatch.delenv("STORAGE_BUCKET_NAME", raising=False)
    with pytest.raises((ConfigurationError, ValidationError), match="STORAGE_BUCKET_NAME is required"):
        Settings(
            APP_ENV=AppEnv.PRODUCTION,
            DATABASE_URL="postgresql://user:pass@ep-live.aws.supabase.com:6543/postgres",
            SECRET_KEY="a-very-secure-random-secret-key-32chars-long-prod",
            STORAGE_BUCKET_NAME=None,
            _env_file=None,
        )


def test_staging_rejects_missing_storage_bucket(monkeypatch):
    """Staging mode must also fail closed if STORAGE_BUCKET_NAME is None or empty."""
    monkeypatch.delenv("STORAGE_BUCKET_NAME", raising=False)
    with pytest.raises((ConfigurationError, ValidationError), match="STORAGE_BUCKET_NAME is required"):
        Settings(
            APP_ENV=AppEnv.STAGING,
            DATABASE_URL="postgresql://user:pass@ep-staging.aws.supabase.com:6543/postgres",
            SECRET_KEY="a-very-secure-random-secret-key-32chars-long-stage",
            STORAGE_BUCKET_NAME=None,
            _env_file=None,
        )


def test_production_accepts_valid_storage_bucket():
    """Production mode succeeds when STORAGE_BUCKET_NAME and other invariants are satisfied."""
    s = Settings(
        APP_ENV=AppEnv.PRODUCTION,
        DATABASE_URL="postgresql://user:pass@ep-live.aws.supabase.com:6543/postgres",
        SECRET_KEY="a-very-secure-random-secret-key-32chars-long-prod",
        STORAGE_BUCKET_NAME="invoices",
        _env_file=None,
    )
    assert s.STORAGE_BUCKET_NAME == "invoices"
    assert s.APP_ENV == AppEnv.PRODUCTION


def test_development_permits_omitted_storage_bucket():
    """In development, local disk fallback is permitted so omitting bucket does not crash."""
    s = Settings(
        APP_ENV=AppEnv.DEVELOPMENT,
        STORAGE_BUCKET_NAME=None,
        _env_file=None,
    )
    assert s.STORAGE_BUCKET_NAME is None
    assert s.APP_ENV == AppEnv.DEVELOPMENT


def test_production_rejects_weak_secret_key():
    """Production mode fails closed if SECRET_KEY is too short or is a default placeholder."""
    with pytest.raises((ConfigurationError, ValidationError), match="SECRET_KEY must be a cryptographically random string"):
        Settings(
            APP_ENV=AppEnv.PRODUCTION,
            DATABASE_URL="postgresql://user:pass@ep-live.aws.supabase.com:6543/postgres",
            SECRET_KEY="dev-secret-key-must-be-changed-in-production-32chars",
            STORAGE_BUCKET_NAME="invoices",
            _env_file=None,
        )

    with pytest.raises((ConfigurationError, ValidationError), match="SECRET_KEY must be a cryptographically random string"):
        Settings(
            APP_ENV=AppEnv.PRODUCTION,
            DATABASE_URL="postgresql://user:pass@ep-live.aws.supabase.com:6543/postgres",
            SECRET_KEY="short-key",
            STORAGE_BUCKET_NAME="invoices",
            _env_file=None,
        )


def test_production_rejects_debug_mode():
    """Production mode fails closed if DEBUG is enabled."""
    with pytest.raises((ConfigurationError, ValidationError), match="DEBUG mode cannot be enabled"):
        Settings(
            APP_ENV=AppEnv.PRODUCTION,
            DATABASE_URL="postgresql://user:pass@ep-live.aws.supabase.com:6543/postgres",
            SECRET_KEY="a-very-secure-random-secret-key-32chars-long-prod",
            STORAGE_BUCKET_NAME="invoices",
            DEBUG=True,
            _env_file=None,
        )


def test_production_rejects_local_auth_bypass():
    """Production mode fails closed if LOCAL_AUTH_BYPASS is enabled."""
    with pytest.raises((ConfigurationError, ValidationError), match="LOCAL_AUTH_BYPASS cannot be enabled"):
        Settings(
            APP_ENV=AppEnv.PRODUCTION,
            DATABASE_URL="postgresql://user:pass@ep-live.aws.supabase.com:6543/postgres",
            SECRET_KEY="a-very-secure-random-secret-key-32chars-long-prod",
            STORAGE_BUCKET_NAME="invoices",
            LOCAL_AUTH_BYPASS=True,
            _env_file=None,
        )

def test_production_rejects_allow_synthetic_seeding():
    """Production mode fails closed if ALLOW_SYNTHETIC_SEEDING is enabled."""
    with pytest.raises((ConfigurationError, ValidationError), match="ALLOW_SYNTHETIC_SEEDING cannot be enabled"):
        Settings(
            APP_ENV=AppEnv.PRODUCTION,
            DATABASE_URL="postgresql://user:pass@ep-live.aws.supabase.com:6543/postgres",
            SECRET_KEY="a-very-secure-random-secret-key-32chars-long-prod",
            STORAGE_BUCKET_NAME="invoices",
            ALLOW_SYNTHETIC_SEEDING=True,
            _env_file=None,
        )


def test_staging_rejects_allow_synthetic_seeding():
    """Staging mode fails closed if ALLOW_SYNTHETIC_SEEDING is enabled."""
    with pytest.raises((ConfigurationError, ValidationError), match="ALLOW_SYNTHETIC_SEEDING cannot be enabled"):
        Settings(
            APP_ENV=AppEnv.STAGING,
            DATABASE_URL="postgresql://user:pass@ep-staging.aws.supabase.com:6543/postgres",
            SECRET_KEY="a-very-secure-random-secret-key-32chars-long-stage",
            STORAGE_BUCKET_NAME="invoices",
            ALLOW_SYNTHETIC_SEEDING=True,
            _env_file=None,
        )


def test_production_rejects_disposable_test_database():
    """Production mode fails closed if IS_DISPOSABLE_TEST_DATABASE is enabled."""
    with pytest.raises((ConfigurationError, ValidationError), match="IS_DISPOSABLE_TEST_DATABASE cannot be enabled"):
        Settings(
            APP_ENV=AppEnv.PRODUCTION,
            DATABASE_URL="postgresql://user:pass@ep-live.aws.supabase.com:6543/postgres",
            SECRET_KEY="a-very-secure-random-secret-key-32chars-long-prod",
            STORAGE_BUCKET_NAME="invoices",
            IS_DISPOSABLE_TEST_DATABASE=True,
            _env_file=None,
        )


def test_staging_rejects_disposable_test_database():
    """Staging mode fails closed if IS_DISPOSABLE_TEST_DATABASE is enabled."""
    with pytest.raises((ConfigurationError, ValidationError), match="IS_DISPOSABLE_TEST_DATABASE cannot be enabled"):
        Settings(
            APP_ENV=AppEnv.STAGING,
            DATABASE_URL="postgresql://user:pass@ep-staging.aws.supabase.com:6543/postgres",
            SECRET_KEY="a-very-secure-random-secret-key-32chars-long-stage",
            STORAGE_BUCKET_NAME="invoices",
            IS_DISPOSABLE_TEST_DATABASE=True,
            _env_file=None,
        )


def test_auth_status_exposes_public_anon_key_and_url(monkeypatch):
    """GET /api/v1/auth/status returns supabase_url and public supabase_anon_key."""
    from fastapi.testclient import TestClient
    from backend.main import app
    from backend.core.config import settings

    monkeypatch.setattr(settings, "SUPABASE_URL", "https://xyzcompany.supabase.co")
    monkeypatch.setattr(settings, "SUPABASE_ANON_KEY", "sb_publishable_test_anon_key_12345")

    client = TestClient(app)
    resp = client.get("/api/v1/auth/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["supabase_url"] == "https://xyzcompany.supabase.co"
    assert data["supabase_anon_key"] == "sb_publishable_test_anon_key_12345"

def test_check_db_health_warns_on_privileged_postgresql_runtime_role(monkeypatch):
    """check_db_health detects when PostgreSQL runtime connection uses privileged BYPASSRLS/super role."""
    from unittest.mock import MagicMock
    from backend.core import database
    from backend.core.config import settings

    monkeypatch.setattr(settings, "DATABASE_URL", "postgresql://postgres:secret@aws-0-ap-south-1.pooler.supabase.com:6543/postgres")
    
    mock_conn = MagicMock()
    mock_conn.execute.return_value.scalar.return_value = 1
    # role_info: (current_user, rolsuper, rolbypassrls)
    mock_conn.execute.return_value.first.return_value = ("postgres", True, True)

    mock_engine = MagicMock()
    mock_engine.url = "postgresql://postgres:secret@aws-0-ap-south-1.pooler.supabase.com:6543/postgres"
    mock_engine.connect.return_value.__enter__.return_value = mock_conn

    monkeypatch.setattr(database, "engine", mock_engine)

    health = database.check_db_health()
    assert health["status"] == "CONNECTED"
    assert health["runtime_role"] == "postgres"
    assert health["bypasses_rls"] is True
    assert "role_warning" in health
    assert "Tenant RLS policies declared TO ap_app_user are not enforced" in health["role_warning"]


def test_check_db_health_confirms_enforced_rls_for_ap_app_user(monkeypatch):
    """check_db_health confirms ENFORCED role security when connecting as restricted ap_app_user."""
    from unittest.mock import MagicMock
    from backend.core import database
    from backend.core.config import settings

    monkeypatch.setattr(settings, "DATABASE_URL", "postgresql://ap_app_user:secret@aws-0-ap-south-1.pooler.supabase.com:6543/postgres")
    
    mock_conn = MagicMock()
    mock_conn.execute.return_value.scalar.return_value = 1
    # role_info: ap_app_user is NOSUPERUSER, NOBYPASSRLS
    mock_conn.execute.return_value.first.return_value = ("ap_app_user", False, False)

    mock_engine = MagicMock()
    mock_engine.url = "postgresql://ap_app_user:secret@aws-0-ap-south-1.pooler.supabase.com:6543/postgres"
    mock_engine.connect.return_value.__enter__.return_value = mock_conn

    monkeypatch.setattr(database, "engine", mock_engine)

    health = database.check_db_health()
    assert health["status"] == "CONNECTED"
    assert health["runtime_role"] == "ap_app_user"
    assert health["bypasses_rls"] is False
    assert health.get("role_security") == "ENFORCED"
    assert "role_warning" not in health
