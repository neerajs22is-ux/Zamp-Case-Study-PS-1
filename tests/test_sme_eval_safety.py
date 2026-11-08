"""Tests for SME Acceptance Seeding Environment & Database Safety Guards.

Verifies:
1. Synthetic seeding is strictly barred in production and staging environments.
2. Unrecognized or unconfigured environments fail closed.
3. Every public entry point in engine/sme_eval_setup.py evaluates the guard before database writes.
4. No real access tokens are minted and no database calls occur when blocked.
5. Seeding is cleanly permitted in development and test environments only when target database is verified safe.
6. Target database identity verification fails closed on unverified, non-isolated, or multi-tenant databases.
7. Database credentials and connection secrets are never logged or leaked.
"""

from unittest.mock import MagicMock
import pytest

from backend.core.config import AppEnv, settings
from engine.sme_eval_setup import (
    assert_database_target_safe,
    assert_seeding_permitted,
    process_scenario_document,
    provision_synthetic_goods_receipts,
    provision_synthetic_purchase_orders,
    provision_synthetic_quality_controls,
    provision_synthetic_vendors,
    provision_tenant_and_users,
    run_sme_eval_setup,
)


def test_assert_seeding_permitted_blocks_production(monkeypatch):
    """Synthetic seeding must raise RuntimeError in production."""
    monkeypatch.setattr(settings, "APP_ENV", AppEnv.PRODUCTION)
    with pytest.raises(RuntimeError, match="CRITICAL SAFETY VIOLATION.*production"):
        assert_seeding_permitted()


def test_assert_seeding_permitted_blocks_staging(monkeypatch):
    """Synthetic seeding must raise RuntimeError in staging."""
    monkeypatch.setattr(settings, "APP_ENV", AppEnv.STAGING)
    with pytest.raises(RuntimeError, match="CRITICAL SAFETY VIOLATION.*staging"):
        assert_seeding_permitted()


def test_assert_seeding_permitted_blocks_string_production_and_staging(monkeypatch):
    """Guard must handle string environment representations defensively."""
    monkeypatch.setattr(settings, "APP_ENV", "production")
    with pytest.raises(RuntimeError, match="CRITICAL SAFETY VIOLATION.*production"):
        assert_seeding_permitted()

    monkeypatch.setattr(settings, "APP_ENV", "staging")
    with pytest.raises(RuntimeError, match="CRITICAL SAFETY VIOLATION.*staging"):
        assert_seeding_permitted()


def test_assert_seeding_permitted_fails_closed_on_unsupported_env(monkeypatch):
    """Unrecognized environments (e.g. qa, preview, custom) must fail closed."""
    monkeypatch.setattr(settings, "APP_ENV", "qa-environment")
    with pytest.raises(RuntimeError, match="Unrecognized or unsupported environment 'qa-environment'"):
        assert_seeding_permitted()


def test_assert_seeding_permitted_fails_closed_on_none_env(monkeypatch):
    """Missing or None APP_ENV must fail closed."""
    monkeypatch.setattr(settings, "APP_ENV", None)
    with pytest.raises(RuntimeError, match="APP_ENV is not configured"):
        assert_seeding_permitted()


def test_assert_seeding_permitted_allows_development_and_test(monkeypatch):
    """Synthetic seeding is permitted only in DEVELOPMENT and TEST."""
    monkeypatch.setattr(settings, "APP_ENV", AppEnv.DEVELOPMENT)
    assert_seeding_permitted()  # Must not raise

    monkeypatch.setattr(settings, "APP_ENV", AppEnv.TEST)
    assert_seeding_permitted()  # Must not raise


def test_assert_database_target_safe_blocks_when_allow_flag_missing(monkeypatch):
    """Even in DEVELOPMENT, seeding fails closed without explicit ALLOW_SYNTHETIC_SEEDING=true."""
    monkeypatch.setattr(settings, "APP_ENV", AppEnv.DEVELOPMENT)
    monkeypatch.setattr(settings, "ALLOW_SYNTHETIC_SEEDING", False)
    mock_db = MagicMock()
    mock_db.info = {"is_isolated_test_db": True}

    with pytest.raises(RuntimeError, match="ALLOW_SYNTHETIC_SEEDING=true configuration"):
        assert_database_target_safe(mock_db)


def test_assert_database_target_safe_blocks_none_database_session(monkeypatch):
    """Missing or None db session fails closed immediately."""
    monkeypatch.setattr(settings, "APP_ENV", AppEnv.DEVELOPMENT)
    monkeypatch.setattr(settings, "ALLOW_SYNTHETIC_SEEDING", True)

    with pytest.raises(RuntimeError, match="Database session is unconfigured or None"):
        assert_database_target_safe(None)


def test_assert_database_target_safe_blocks_foreign_organisations(monkeypatch):
    """Target database containing non-evaluation tenants fails closed immediately."""
    monkeypatch.setattr(settings, "APP_ENV", AppEnv.DEVELOPMENT)
    monkeypatch.setattr(settings, "ALLOW_SYNTHETIC_SEEDING", True)
    mock_db = MagicMock()
    mock_db.info = {"is_isolated_test_db": True}
    # Simulate finding 2 real organisations in database
    mock_db.scalar.return_value = 2

    with pytest.raises(RuntimeError, match="Target database contains 2 non-evaluation organisation"):
        assert_database_target_safe(mock_db)


def test_assert_database_target_safe_blocks_missing_isolation_marker(monkeypatch):
    """Database lacking explicit isolation setting or session marker fails closed."""
    monkeypatch.setattr(settings, "APP_ENV", AppEnv.DEVELOPMENT)
    monkeypatch.setattr(settings, "ALLOW_SYNTHETIC_SEEDING", True)
    mock_db = MagicMock()
    mock_db.info = {}
    mock_db.scalar.return_value = 0  # 0 foreign orgs, but no isolation marker

    with pytest.raises(RuntimeError, match="Target database lacks verified isolation marker"):
        assert_database_target_safe(mock_db)


def test_assert_database_target_safe_passes_with_verified_isolated_session(monkeypatch):
    """Seeding succeeds when all 4 conditions are met: env, flag, 0 foreign orgs, and isolation marker."""
    monkeypatch.setattr(settings, "APP_ENV", AppEnv.DEVELOPMENT)
    monkeypatch.setattr(settings, "ALLOW_SYNTHETIC_SEEDING", True)
    mock_db = MagicMock()
    mock_db.info = {"is_isolated_test_db": True}
    mock_db.scalar.return_value = 0  # 0 foreign orgs

    assert_database_target_safe(mock_db)  # Must not raise


def test_database_safety_never_exposes_database_credentials(monkeypatch):
    """Safety violation exceptions must never leak connection secrets or credentials."""
    monkeypatch.setattr(settings, "APP_ENV", AppEnv.DEVELOPMENT)
    monkeypatch.setattr(settings, "ALLOW_SYNTHETIC_SEEDING", False)
    monkeypatch.setattr(
        settings,
        "DATABASE_URL",
        "postgresql://secret_admin_user:super_secret_prod_password@aws-0-prod.pooler.supabase.com:6543/postgres",
    )
    mock_db = MagicMock()
    mock_db.info = {}

    with pytest.raises(RuntimeError) as exc_info:
        assert_database_target_safe(mock_db)

    err_text = str(exc_info.value)
    assert "secret_admin_user" not in err_text
    assert "super_secret_prod_password" not in err_text
    assert "aws-0-prod.pooler.supabase.com" not in err_text


@pytest.mark.parametrize("env", [AppEnv.PRODUCTION, AppEnv.STAGING])
def test_all_seeding_entrypoints_fail_closed_before_db_writes(monkeypatch, env):
    """Verify all 6 database-writing entry points abort before any DB execution."""
    monkeypatch.setattr(settings, "APP_ENV", env)
    mock_db = MagicMock()

    # 1. provision_tenant_and_users
    with pytest.raises(RuntimeError, match="CRITICAL SAFETY VIOLATION"):
        provision_tenant_and_users(mock_db)

    # 2. provision_synthetic_vendors
    with pytest.raises(RuntimeError, match="CRITICAL SAFETY VIOLATION"):
        provision_synthetic_vendors(mock_db)

    # 3. provision_synthetic_purchase_orders
    with pytest.raises(RuntimeError, match="CRITICAL SAFETY VIOLATION"):
        provision_synthetic_purchase_orders(mock_db)

    # 4. provision_synthetic_goods_receipts
    with pytest.raises(RuntimeError, match="CRITICAL SAFETY VIOLATION"):
        provision_synthetic_goods_receipts(mock_db)

    # 5. provision_synthetic_quality_controls
    with pytest.raises(RuntimeError, match="CRITICAL SAFETY VIOLATION"):
        provision_synthetic_quality_controls(mock_db)

    # 6. process_scenario_document
    with pytest.raises(RuntimeError, match="CRITICAL SAFETY VIOLATION"):
        process_scenario_document(
            db=mock_db,
            extractor=MagicMock(),
            doc_id="APTC-001",
            filename="01_clean_3way_perfect_match_INV_26_009.pdf",
            scenario_type="CLEAN_3WAY_MATCH",
        )

    # Verify zero database interactions occurred
    assert mock_db.add.call_count == 0
    assert mock_db.commit.call_count == 0
    assert mock_db.flush.call_count == 0
    assert mock_db.execute.call_count == 0
    assert mock_db.scalar.call_count == 0


@pytest.mark.parametrize("env", [AppEnv.PRODUCTION, AppEnv.STAGING])
def test_run_sme_eval_setup_aborts_before_token_generation_or_session(monkeypatch, env):
    """run_sme_eval_setup must evaluate assert_seeding_permitted as line 1."""
    monkeypatch.setattr(settings, "APP_ENV", env)

    mock_ensure_secret = MagicMock()
    mock_generate_jwt = MagicMock()
    monkeypatch.setattr("engine.sme_eval_setup.ensure_jwt_secret", mock_ensure_secret)
    monkeypatch.setattr("engine.sme_eval_setup.generate_sme_jwt", mock_generate_jwt)

    with pytest.raises(RuntimeError, match="CRITICAL SAFETY VIOLATION"):
        run_sme_eval_setup()

    assert mock_ensure_secret.call_count == 0
    assert mock_generate_jwt.call_count == 0
