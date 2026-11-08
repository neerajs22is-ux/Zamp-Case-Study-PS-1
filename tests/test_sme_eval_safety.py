"""Tests for SME Acceptance Seeding Environment Safety Guards.

Verifies:
1. Synthetic seeding is strictly barred in production and staging environments.
2. Unrecognized or unconfigured environments fail closed.
3. Every public entry point in engine/sme_eval_setup.py evaluates the guard before database writes.
4. No real access tokens are minted and no database calls occur when blocked.
5. Seeding is cleanly permitted in development and test environments.
"""

from unittest.mock import MagicMock
import pytest

from backend.core.config import AppEnv, settings
from engine.sme_eval_setup import (
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
