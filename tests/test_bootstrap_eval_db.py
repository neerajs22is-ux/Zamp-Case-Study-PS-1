"""Tests for Dedicated Evaluation Database Bootstrap Utility & Isolation Safety Guards.

Verifies:
1. Short or missing EVAL_BOOTSTRAP_SECRET_KEY fails closed.
2. Database containing foreign organisations fails closed.
3. Database containing foreign users fails closed.
4. Database lacking Alembic migrations fails closed.
5. Query or permission errors during safety checks fail closed.
6. Authorized bootstrap succeeds against isolated target with valid 32+ char secret.
7. Cloud host blocklist override requires BOTH IS_DEDICATED_EVALUATION_DATABASE=true and valid secret.
"""

from unittest.mock import MagicMock
import pytest

from backend.core.config import AppEnv, settings
from engine.bootstrap_eval_db import verify_evaluation_database_safety
from engine.sme_eval_setup import assert_database_target_safe, assert_seeding_permitted


def test_bootstrap_safety_fails_closed_on_short_or_missing_auth_key():
    """Bootstrap fails closed if secret key is less than 32 characters."""
    mock_session = MagicMock()
    with pytest.raises(RuntimeError, match="EVAL_BOOTSTRAP_SECRET_KEY must be provided and be at least 32 characters"):
        verify_evaluation_database_safety(mock_session, "short-key-15c")

    with pytest.raises(RuntimeError, match="EVAL_BOOTSTRAP_SECRET_KEY must be provided and be at least 32 characters"):
        verify_evaluation_database_safety(mock_session, "")


def test_bootstrap_safety_fails_closed_if_alembic_migrations_missing():
    """Bootstrap fails closed if alembic_version table does not return a migration revision."""
    mock_session = MagicMock()
    mock_session.execute.return_value.scalar.return_value = None

    valid_key = "secure-bootstrap-authorization-token-32chars"
    with pytest.raises(RuntimeError, match="Database has not been initialized with Alembic migrations"):
        verify_evaluation_database_safety(mock_session, valid_key)


def test_bootstrap_safety_fails_closed_on_unexpected_query_error():
    """Bootstrap fails closed if unexpected database error occurs during inspection."""
    mock_session = MagicMock()
    mock_session.execute.side_effect = RuntimeError("Database connection reset by peer")

    valid_key = "secure-bootstrap-authorization-token-32chars"
    with pytest.raises(RuntimeError, match="Could not verify database migration status"):
        verify_evaluation_database_safety(mock_session, valid_key)


def test_bootstrap_safety_blocks_foreign_organisations():
    """Bootstrap fails closed if organisations other than org_sme_eval exist."""
    mock_session = MagicMock()
    mock_session.execute.return_value.scalar.return_value = "013_revoke_access_tokens"
    mock_session.scalars.return_value.all.return_value = ["org_customer_corp_01"]

    valid_key = "secure-bootstrap-authorization-token-32chars"
    with pytest.raises(RuntimeError, match="Target database contains non-evaluation organisations"):
        verify_evaluation_database_safety(mock_session, valid_key)


def test_bootstrap_safety_blocks_foreign_users():
    """Bootstrap fails closed if users not belonging to org_sme_eval exist."""
    mock_session = MagicMock()
    mock_session.execute.return_value.scalar.return_value = "013_revoke_access_tokens"
    # First scalars call (organisations) returns empty, second (users) returns foreign user
    mock_session.scalars.return_value.all.side_effect = [
        [],  # 0 foreign orgs
        ["real_cfo@customer.com"],  # 1 foreign user
    ]

    valid_key = "secure-bootstrap-authorization-token-32chars"
    with pytest.raises(RuntimeError, match="Target database contains foreign users"):
        verify_evaluation_database_safety(mock_session, valid_key)


def test_bootstrap_safety_passes_on_clean_isolated_database():
    """Bootstrap passes when database has migrations and zero foreign orgs or users."""
    mock_session = MagicMock()
    mock_session.execute.return_value.scalar.return_value = "013_revoke_access_tokens"
    mock_session.scalars.return_value.all.side_effect = [
        [],  # 0 foreign orgs
        [],  # 0 foreign users
    ]

    valid_key = "secure-bootstrap-authorization-token-32chars"
    verify_evaluation_database_safety(mock_session, valid_key)  # Must not raise


def test_assert_database_target_safe_allows_cloud_host_with_dedicated_bootstrap_credentials(monkeypatch):
    """Cloud host (e.g. Supabase) is permitted for bootstrap ONLY when IS_DEDICATED_EVALUATION_DATABASE and 32+ char key are present."""
    monkeypatch.setattr(settings, "APP_ENV", AppEnv.PRODUCTION)
    monkeypatch.setattr(settings, "ALLOW_SYNTHETIC_SEEDING", True)
    monkeypatch.setattr(settings, "IS_DEDICATED_EVALUATION_DATABASE", True)
    monkeypatch.setattr(settings, "EVAL_BOOTSTRAP_SECRET_KEY", "operator-authorized-eval-bootstrap-key-32c")

    mock_db = MagicMock()
    mock_db.bind.dialect.name = "postgresql"
    mock_db.bind.url.host = "aws-0-ap-south-1.pooler.supabase.com"
    mock_db.scalar.return_value = 0

    assert_database_target_safe(mock_db)  # Must not raise


def test_assert_database_target_safe_blocks_cloud_host_if_bootstrap_key_too_short(monkeypatch):
    """Cloud host fails closed if operator secret key is shorter than 32 characters."""
    monkeypatch.setattr(settings, "APP_ENV", AppEnv.DEVELOPMENT)
    monkeypatch.setattr(settings, "ALLOW_SYNTHETIC_SEEDING", True)
    monkeypatch.setattr(settings, "IS_DEDICATED_EVALUATION_DATABASE", True)
    monkeypatch.setattr(settings, "EVAL_BOOTSTRAP_SECRET_KEY", "too-short")

    mock_db = MagicMock()
    mock_db.bind.dialect.name = "postgresql"
    mock_db.bind.url.host = "aws-0-ap-south-1.pooler.supabase.com"
    mock_db.scalar.return_value = 0

    with pytest.raises(RuntimeError, match="Bootstrap of a dedicated evaluation database requires explicit IS_DEDICATED_EVALUATION_DATABASE=true and a valid EVAL_BOOTSTRAP_SECRET_KEY"):
        assert_database_target_safe(mock_db)
