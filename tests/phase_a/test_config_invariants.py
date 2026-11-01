"""Tests for Environment & Production Invariant Enforcement."""

import pytest
from pydantic import ValidationError
from backend.core.config import AppEnv, ConfigurationError, Settings


def test_production_rejects_missing_database_url(monkeypatch):
    """Production must raise error if DATABASE_URL is not provided."""
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises((ConfigurationError, ValidationError), match="DATABASE_URL must be configured"):
        Settings(
            APP_ENV=AppEnv.PRODUCTION,
            DATABASE_URL=None,
            STORAGE_BUCKET_NAME="company-ap-originals",
            _env_file=None,
        )


def test_production_rejects_sqlite(monkeypatch):
    """Production must reject SQLite URLs."""
    monkeypatch.setenv("DATABASE_URL", "sqlite:///production.db")
    with pytest.raises((ConfigurationError, ValidationError), match="PostgreSQL is mandatory"):
        Settings(
            APP_ENV=AppEnv.PRODUCTION,
            STORAGE_BUCKET_NAME="company-ap-originals",
            _env_file=None,
        )


def test_staging_rejects_in_memory_db(monkeypatch):
    """Staging must reject in-memory SQLite databases."""
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    with pytest.raises((ConfigurationError, ValidationError), match="PostgreSQL is mandatory"):
        Settings(
            APP_ENV=AppEnv.STAGING,
            STORAGE_BUCKET_NAME="company-ap-staging",
            _env_file=None,
        )


def test_production_rejects_local_auth_bypass(monkeypatch):
    """Production must reject LOCAL_AUTH_BYPASS=True."""
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@localhost:5432/ap_db")
    monkeypatch.setenv("LOCAL_AUTH_BYPASS", "true")
    with pytest.raises((ConfigurationError, ValidationError), match="LOCAL_AUTH_BYPASS cannot be enabled"):
        Settings(
            APP_ENV=AppEnv.PRODUCTION,
            STORAGE_BUCKET_NAME="company-ap-originals",
            LOCAL_AUTH_BYPASS=True,
            _env_file=None,
        )


def test_production_rejects_missing_storage_bucket(monkeypatch):
    """Production must reject missing STORAGE_BUCKET_NAME."""
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@localhost:5432/ap_db")
    monkeypatch.delenv("STORAGE_BUCKET_NAME", raising=False)
    with pytest.raises((ConfigurationError, ValidationError), match="STORAGE_BUCKET_NAME is required"):
        Settings(
            APP_ENV=AppEnv.PRODUCTION,
            STORAGE_BUCKET_NAME=None,
            _env_file=None,
        )


def test_redacted_dict_masks_secrets():
    """Configuration serializer must mask sensitive tokens and passwords."""
    s = Settings(
        APP_ENV=AppEnv.DEVELOPMENT,
        SECRET_KEY="super-secret-key-that-must-be-hidden",
        OIDC_CLIENT_SECRET="oidc-client-secret-12345",
        DATABASE_URL="postgresql://user:super_secret_pw@db.internal:5432/ap_db",
        _env_file=None,
    )
    redacted = s.redacted_dict()
    assert redacted["SECRET_KEY"] == "********"
    assert redacted["OIDC_CLIENT_SECRET"] == "********"
    assert "super_secret_pw" not in redacted["DATABASE_URL"]
    assert "********" in redacted["DATABASE_URL"]
