"""Tests for Dedicated Evaluation Database Bootstrap Utility & Isolation Safety Guards.

Verifies:
1. Short or missing EVAL_BOOTSTRAP_SECRET_KEY fails closed.
2. Database lacking exact target migration 013_revoke_access_tokens fails closed.
3. Stale migration revision (e.g. 010) fails closed.
4. Query or permission errors during safety checks fail closed.
5. Database containing foreign organisations fails closed.
6. Database containing foreign users fails closed.
7. Database name mismatch or designated production database fails closed.
8. RLS disable permission failure fails closed.
9. Single-transaction atomic rollback on provisioning failure injection.
10. Teardown refuses in-place deletion when immutable audit events exist.
11. Teardown cleanly removes baseline fixtures when zero audit events exist.
12. Cloud host blocklist overrides require both IS_DEDICATED_EVALUATION_DATABASE=true and valid secret.
"""

from unittest.mock import MagicMock, patch
import pytest
from sqlalchemy.sql import text

from backend.core.config import AppEnv, settings
from engine.bootstrap_eval_db import (
    EXPECTED_MIGRATION_REVISION,
    bootstrap_evaluation_workspace,
    teardown_evaluation_workspace,
    verify_evaluation_database_safety,
)
from engine.sme_eval_setup import assert_database_target_safe, assert_seeding_permitted

VALID_KEY = "operator-authorized-eval-bootstrap-key-32c"


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

    with pytest.raises(RuntimeError, match="Database has not been initialized with Alembic migrations"):
        verify_evaluation_database_safety(mock_session, VALID_KEY)


def test_bootstrap_safety_fails_closed_on_stale_or_unexpected_migration():
    """Bootstrap fails closed if revision is not exactly 013_revoke_access_tokens."""
    mock_session = MagicMock()
    # Simulate DB still at revision 010_identity_memberships
    mock_session.execute.return_value.scalar.side_effect = [
        "eval_db",  # current_database
        "eval_user",  # current_user
        "010_identity_memberships",  # version_num
    ]

    with pytest.raises(RuntimeError, match="does not match expected target revision '013_revoke_access_tokens'"):
        verify_evaluation_database_safety(mock_session, VALID_KEY)


def test_bootstrap_safety_fails_closed_on_unexpected_query_error():
    """Bootstrap fails closed if unexpected database error occurs during inspection."""
    mock_session = MagicMock()
    mock_session.execute.side_effect = RuntimeError("Database connection reset by peer")

    with pytest.raises(RuntimeError, match="FATAL SAFETY VIOLATION"):
        verify_evaluation_database_safety(mock_session, VALID_KEY)


def test_bootstrap_safety_blocks_foreign_organisations():
    """Bootstrap fails closed if organisations other than org_sme_eval exist."""
    mock_session = MagicMock()
    mock_session.execute.return_value.scalar.side_effect = [
        "eval_db",
        "eval_user",
        EXPECTED_MIGRATION_REVISION,
    ]
    mock_session.scalars.return_value.all.return_value = ["org_customer_corp_01"]

    with pytest.raises(RuntimeError, match="Target database contains non-evaluation organisations"):
        verify_evaluation_database_safety(mock_session, VALID_KEY)


def test_bootstrap_safety_blocks_foreign_users():
    """Bootstrap fails closed if users not belonging to org_sme_eval exist."""
    mock_session = MagicMock()
    mock_session.execute.return_value.scalar.side_effect = [
        "eval_db",
        "eval_user",
        EXPECTED_MIGRATION_REVISION,
    ]
    mock_session.scalars.return_value.all.side_effect = [
        [],  # 0 foreign orgs
        ["real_cfo@customer.com"],  # 1 foreign user
    ]

    with pytest.raises(RuntimeError, match="Target database contains foreign users"):
        verify_evaluation_database_safety(mock_session, VALID_KEY)


def test_bootstrap_safety_rejects_db_name_mismatch():
    """Bootstrap fails closed if connected database name does not match expected_db_name."""
    mock_session = MagicMock()
    mock_session.execute.return_value.scalar.side_effect = [
        "different_db",
        "eval_user",
        EXPECTED_MIGRATION_REVISION,
    ]
    mock_session.scalars.return_value.all.side_effect = [[], []]

    with pytest.raises(RuntimeError, match="does not match expected evaluation database name"):
        verify_evaluation_database_safety(mock_session, VALID_KEY, expected_db_name="target_eval_db")


def test_bootstrap_safety_rejects_designated_production_db_name():
    """Bootstrap fails closed if database name is 'postgres' or 'production' without explicit confirmation."""
    mock_session = MagicMock()
    mock_session.execute.return_value.scalar.side_effect = [
        "postgres",
        "prod_user",
        EXPECTED_MIGRATION_REVISION,
    ]
    mock_session.scalars.return_value.all.side_effect = [[], []]

    with pytest.raises(RuntimeError, match="is a designated default/production identifier"):
        verify_evaluation_database_safety(mock_session, VALID_KEY, expected_db_name=None)


def test_bootstrap_safety_passes_with_matching_expected_db_name():
    """Bootstrap passes when connected database name exactly matches expected_db_name."""
    mock_session = MagicMock()
    mock_session.execute.return_value.scalar.side_effect = [
        "zamp_eval_isolated",
        "eval_user",
        EXPECTED_MIGRATION_REVISION,
    ]
    mock_session.scalars.return_value.all.side_effect = [[], []]

    verify_evaluation_database_safety(mock_session, VALID_KEY, expected_db_name="zamp_eval_isolated")


def test_bootstrap_safety_fails_if_postgresql_role_lacks_bypass_rls():
    """Bootstrap fails closed if PostgreSQL role lacks BYPASSRLS or superuser on RLS tables."""
    mock_session = MagicMock()
    mock_session.bind.dialect.name = "postgresql"

    def mock_execute(statement, *args, **kwargs):
        stmt_str = str(statement).strip()
        if "current_database" in stmt_str:
            ret = MagicMock()
            ret.scalar.return_value = "zamp_eval_isolated"
            return ret
        if "pg_roles" in stmt_str:
            ret = MagicMock()
            ret.first.return_value = (False, False)  # rolsuper=False, rolbypassrls=False
            return ret
        if "SELECT current_user" in stmt_str:
            ret = MagicMock()
            ret.scalar.return_value = "restricted_app_user"
            return ret
        if "alembic_version" in stmt_str:
            ret = MagicMock()
            ret.scalar.return_value = EXPECTED_MIGRATION_REVISION
            return ret
        if "pg_class" in stmt_str:
            ret = MagicMock()
            ret.first.return_value = (True, True)  # relrowsecurity=True, relforcerowsecurity=True
            return ret
        if "pg_tables" in stmt_str:
            ret = MagicMock()
            ret.scalar.return_value = "postgres_admin"  # table owner is not current_user
            return ret
        return MagicMock()

    mock_session.execute.side_effect = mock_execute

    with pytest.raises(RuntimeError, match="lacks BYPASSRLS or superuser privileges on table 'organisations'"):
        verify_evaluation_database_safety(mock_session, VALID_KEY)


def test_bootstrap_safety_fails_if_rls_disable_denied():
    """Bootstrap fails closed if PostgreSQL parameter row_security cannot be set."""
    mock_session = MagicMock()
    mock_session.bind.dialect.name = "postgresql"

    def mock_execute(statement, *args, **kwargs):
        stmt_str = str(statement).strip()
        if "current_database" in stmt_str:
            ret = MagicMock()
            ret.scalar.return_value = "zamp_eval_isolated"
            return ret
        if "pg_roles" in stmt_str:
            ret = MagicMock()
            ret.first.return_value = (True, True)
            return ret
        if "SELECT current_user" in stmt_str:
            ret = MagicMock()
            ret.scalar.return_value = "restricted_user"
            return ret
        if "alembic_version" in stmt_str:
            ret = MagicMock()
            ret.scalar.return_value = EXPECTED_MIGRATION_REVISION
            return ret
        if "pg_class" in stmt_str:
            ret = MagicMock()
            ret.first.return_value = (True, True)
            return ret
        if "pg_tables" in stmt_str:
            ret = MagicMock()
            ret.scalar.return_value = "restricted_user"
            return ret
        if "row_security" in stmt_str:
            raise RuntimeError("permission denied to set parameter row_security")
        return MagicMock()

    mock_session.execute.side_effect = mock_execute

    with pytest.raises(RuntimeError, match="Failed to verify RLS bypass permissions on role 'restricted_user'"):
        verify_evaluation_database_safety(mock_session, VALID_KEY)


def test_bootstrap_safety_passes_for_privileged_postgresql_role():
    """Bootstrap succeeds when connected role has rolbypassrls=True on PostgreSQL."""
    mock_session = MagicMock()
    mock_session.bind.dialect.name = "postgresql"

    def mock_execute(statement, *args, **kwargs):
        stmt_str = str(statement).strip()
        if "current_database" in stmt_str:
            ret = MagicMock()
            ret.scalar.return_value = "zamp_eval_isolated"
            return ret
        if "pg_roles" in stmt_str:
            ret = MagicMock()
            ret.first.return_value = (True, True)  # rolsuper=True, rolbypassrls=True
            return ret
        if "SELECT current_user" in stmt_str:
            ret = MagicMock()
            ret.scalar.return_value = "postgres_superuser"
            return ret
        if "alembic_version" in stmt_str:
            ret = MagicMock()
            ret.scalar.return_value = EXPECTED_MIGRATION_REVISION
            return ret
        if "pg_class" in stmt_str:
            ret = MagicMock()
            ret.first.return_value = (True, True)
            return ret
        if "pg_tables" in stmt_str:
            ret = MagicMock()
            ret.scalar.return_value = "postgres_superuser"
            return ret
        return MagicMock()

    mock_session.execute.side_effect = mock_execute
    mock_session.scalars.return_value.all.side_effect = [[], []]

    verify_evaluation_database_safety(mock_session, VALID_KEY, expected_db_name="zamp_eval_isolated")


def test_bootstrap_workspace_transactional_rollback_on_failure_injection():
    """Bootstrap rolls back all staged fixtures and leaves zero partial state if any step fails."""
    mock_session = MagicMock()
    mock_session.execute.return_value.scalar.side_effect = [
        "eval_db",
        "eval_user",
        EXPECTED_MIGRATION_REVISION,
    ]
    mock_session.scalars.return_value.all.side_effect = [[], []]

    with patch("engine.bootstrap_eval_db.provision_tenant_and_users") as m_users, \
         patch("engine.bootstrap_eval_db.provision_synthetic_vendors") as m_vendors, \
         patch("engine.bootstrap_eval_db.provision_synthetic_purchase_orders") as m_pos:
        
        # Inject failure in purchase order provisioning
        m_pos.side_effect = RuntimeError("Simulated transient network drop during PO insert")

        with pytest.raises(RuntimeError, match="Evaluation bootstrap aborted and rolled back cleanly"):
            bootstrap_evaluation_workspace(mock_session, VALID_KEY)

        # Assert users and vendors were called, but session rolled back and never committed
        m_users.assert_called_once()
        m_vendors.assert_called_once()
        mock_session.rollback.assert_called_once()
        mock_session.commit.assert_not_called()


def test_teardown_refused_when_immutable_audit_events_exist():
    """Teardown strictly refuses in-place deletion if immutable audit records exist."""
    mock_session = MagicMock()
    mock_session.execute.return_value.scalar.side_effect = [
        "eval_db",
        "eval_user",
        EXPECTED_MIGRATION_REVISION,
        5,  # 5 audit events recorded!
    ]
    mock_session.scalars.return_value.all.side_effect = [[], []]

    with pytest.raises(RuntimeError, match="In-place deletion of audit_events is strictly prohibited by database-level immutability trigger"):
        teardown_evaluation_workspace(mock_session, VALID_KEY)


def test_teardown_fails_closed_when_audit_count_query_errors():
    """Teardown fails closed immediately if inspecting audit_events count raises an error."""
    mock_session = MagicMock()
    mock_session.execute.return_value.scalar.side_effect = [
        "eval_db",
        "eval_user",
        EXPECTED_MIGRATION_REVISION,
        RuntimeError("Database connection lost during audit_events count query"),
    ]
    mock_session.scalars.return_value.all.side_effect = [[], []]

    with pytest.raises(RuntimeError, match="Failed to inspect audit_events count for teardown"):
        teardown_evaluation_workspace(mock_session, VALID_KEY)

    # Verify that NO delete statements were ever executed
    executed_statements = [str(call[0][0]) for call in mock_session.execute.call_args_list]
    for stmt in executed_statements:
        assert "DELETE FROM" not in stmt, "Teardown must not execute any deletions when audit query fails"


def test_teardown_cleans_up_when_zero_audit_events_exist():
    """Teardown proceeds cleanly when zero audit events exist, without mutating audit_events table."""
    mock_session = MagicMock()
    mock_session.execute.return_value.scalar.side_effect = [
        "eval_db",
        "eval_user",
        EXPECTED_MIGRATION_REVISION,
        0,  # 0 audit events
    ]
    mock_session.scalars.return_value.all.side_effect = [[], []]

    teardown_evaluation_workspace(mock_session, VALID_KEY)
    mock_session.commit.assert_called_once()

    # Verify that DELETE FROM audit_events was NEVER executed
    executed_statements = [str(call[0][0]) for call in mock_session.execute.call_args_list]
    for stmt in executed_statements:
        assert "DELETE FROM audit_events" not in stmt, "Teardown must never execute DELETE FROM audit_events"


def test_assert_database_target_safe_allows_cloud_host_with_dedicated_bootstrap_credentials(monkeypatch):
    """Cloud host is permitted for bootstrap ONLY when IS_DEDICATED_EVALUATION_DATABASE and 32+ char key are present."""
    monkeypatch.setattr(settings, "APP_ENV", AppEnv.PRODUCTION)
    monkeypatch.setattr(settings, "ALLOW_SYNTHETIC_SEEDING", True)
    monkeypatch.setattr(settings, "IS_DEDICATED_EVALUATION_DATABASE", True)
    monkeypatch.setattr(settings, "EVAL_BOOTSTRAP_SECRET_KEY", VALID_KEY)

    mock_db = MagicMock()
    mock_db.bind.dialect.name = "postgresql"
    mock_db.bind.url.host = "aws-0-ap-south-1.pooler.supabase.com"
    mock_db.scalar.return_value = 0

    assert_database_target_safe(mock_db)  # Must not raise

def test_bootstrap_workspace_with_seed_scenarios_invokes_golden_scenarios():
    """Bootstrap with seed_scenarios=True calls process_scenario_document for demonstration cases."""
    mock_session = MagicMock()
    mock_session.execute.return_value.scalar.side_effect = [
        "eval_db",
        "eval_user",
        EXPECTED_MIGRATION_REVISION,
    ]
    mock_session.scalars.return_value.all.side_effect = [[], []]

    with patch("engine.bootstrap_eval_db.provision_tenant_and_users") as m_users, \
         patch("engine.bootstrap_eval_db.provision_synthetic_vendors") as m_vendors, \
         patch("engine.bootstrap_eval_db.provision_synthetic_purchase_orders") as m_pos, \
         patch("engine.bootstrap_eval_db.provision_synthetic_goods_receipts") as m_grns, \
         patch("engine.bootstrap_eval_db.provision_synthetic_quality_controls") as m_qcs, \
         patch("engine.sme_eval_setup.process_scenario_document") as m_scenario:

        bootstrap_evaluation_workspace(mock_session, VALID_KEY, seed_scenarios=True)

        m_users.assert_called_once()
        m_vendors.assert_called_once()
        m_pos.assert_called_once()
        m_grns.assert_called_once()
        m_qcs.assert_called_once()
        mock_session.commit.assert_called_once()

        # Verify scenario invocations
        assert m_scenario.call_count == 4
        seeded_doc_ids = [call[0][2] for call in m_scenario.call_args_list]
        assert "APTC-009" in seeded_doc_ids
        assert "APTC-030" in seeded_doc_ids
        assert "APTC-036" in seeded_doc_ids
        assert "APTC-038" in seeded_doc_ids
        # Confirm APTC-001 is NOT seeded
        assert "APTC-001" not in seeded_doc_ids
