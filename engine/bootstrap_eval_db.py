"""Administrative bootstrap utility for initializing or tearing down a dedicated evaluation database.

Guarantees:
1. Strictly Out-of-Band: CLI-only utility, never invoked automatically on container boot.
2. Operator Authorization: Requires explicit confirmation flag and an authorization key (min 32 chars).
3. Secret Exposure Safeguard: Auth key is read from environment variable (EVAL_BOOTSTRAP_SECRET_KEY)
   to prevent credential leakage in process lists, command logs, and shell history.
4. Independent Database Target Verification (Fail-Closed):
   - Validates target database name against --expected-db-name when supplied.
   - Any query failure inspecting database identity fails closed.
   - Strictly bars known default/production database names ("postgres", "production", "prod", "main", "live")
     unless explicitly confirmed by operator.
5. Migration Compatibility Enforcement:
   - Requires the exact target Alembic revision "013_revoke_access_tokens".
   - Stale, partial, or unexpected migration revisions are rejected immediately.
6. RLS Bypass & Multi-Tenant Isolation (Fail-Closed):
   - Verifies connection has privileges to disable Row-Level Security (RLS) so foreign tenants cannot be hidden.
   - Confirms target database contains zero non-evaluation organisations (organisations.id != 'org_sme_eval').
   - Confirms target database contains zero foreign users (users.org_id != 'org_sme_eval').
   - Any query or permission error fails closed immediately.
7. Atomic Single-Transaction Bootstrap:
   - All tenant, user, vendor, PO, GRN, and QC fixtures are staged in a single transaction.
   - Any failure during provisioning triggers complete session rollback with zero partial state.
8. Audit Immutability Protection & Disposable Database Lifecycle:
   - Teardown strictly respects the database trigger "trg_audit_events_immutable".
   - Refuses in-place deletion if immutable AuditEvent records exist, requiring a disposable database lifecycle
     (drop and recreate evaluation database clone) rather than mutating append-only audit ledgers.
9. Dry-Run / Verification Mode: Supports --dry-run / --verify-only to inspect target safety without writes.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from typing import Any, Optional

from sqlalchemy import create_engine, func, select, text
from sqlalchemy.orm import Session, sessionmaker

sys.path.insert(0, os.path.abspath("."))

from backend.core.config import settings
from backend.models.domain import (
    ApprovalRequest, AuditEvent, Document, ExceptionRecord,
    GoodsReceiptLineSnapshot, GoodsReceiptSnapshot, Invoice,
    InvoiceLine, MatchGateCheck, MatchRun, Organisation,
    QualityControlSnapshot, RoleAssignment, User, Vendor,
    WorkOrderLineSnapshot, WorkOrderSnapshot,
)
from engine.sme_eval_setup import (
    ORG_ID,
    ORG_NAME,
    provision_synthetic_goods_receipts,
    provision_synthetic_purchase_orders,
    provision_synthetic_quality_controls,
    provision_synthetic_vendors,
    provision_tenant_and_users,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("bootstrap_eval_db")

EXPECTED_MIGRATION_REVISION = "013_revoke_access_tokens"


def verify_evaluation_database_safety(
    session: Session,
    auth_key: str,
    expected_db_name: Optional[str] = None,
) -> None:
    """Verifies that the target database is an isolated evaluation instance.

    Fail-Closed Invariants:
    1. Auth Key: Minimum 32 characters required.
    2. Explicit Database Identity: Database name must match expected_db_name if supplied.
    3. Production Identifier Guard: Rejects default production database identifiers.
    4. Migration Version Gate: Requires exact target revision '013_revoke_access_tokens'.
    5. RLS Privilege Verification: Role must be able to verify absence of hidden tenants.
    6. Zero Foreign Organisations: If any organisation other than 'org_sme_eval' exists, abort immediately.
    7. Zero Foreign Users: If any user not belonging to 'org_sme_eval' exists, abort immediately.
    8. Any query or connection failure fails closed.
    """
    if not auth_key or len(auth_key.strip()) < 32:
        raise RuntimeError(
            "FATAL SAFETY VIOLATION: EVAL_BOOTSTRAP_SECRET_KEY must be provided and be at least 32 characters long."
        )

    session.info["skip_role_restriction"] = True
    session.info["tenant_org_id"] = ORG_ID
    dialect_name = getattr(getattr(session.bind, "dialect", None), "name", "")

    # 1. Independent Database Target & Role Inspection (Fail-Closed)
    try:
        db_name = session.execute(text("SELECT current_database()")).scalar()
        db_user = session.execute(text("SELECT current_user")).scalar()
        logger.info(f"Target database inspection: database='{db_name}', user='{db_user}'")

        if expected_db_name and db_name != expected_db_name:
            raise RuntimeError(
                f"FATAL SAFETY VIOLATION: Connected database '{db_name}' does not match expected evaluation database name '{expected_db_name}'."
            )

        if db_name in ("postgres", "production", "prod", "main", "live") and expected_db_name != db_name:
            raise RuntimeError(
                f"FATAL SAFETY VIOLATION: Database name '{db_name}' is a designated default/production identifier. "
                "Synthetic evaluation seeding is barred unless explicitly confirmed via --expected-db-name."
            )
    except Exception as exc:
        if "FATAL SAFETY VIOLATION" in str(exc):
            raise
        # If running on PostgreSQL or if expected_db_name was specified, failure to query identity must fail closed
        if dialect_name == "postgresql" or expected_db_name:
            raise RuntimeError(
                f"FATAL SAFETY VIOLATION: Failed to query database identity (current_database): {exc}. Aborting fails closed."
            ) from exc
        logger.debug(f"current_database inspection skipped on dialect '{dialect_name}'; continuing.")

    # 2. Strict Migration Compatibility Enforcement
    try:
        rev = session.execute(text("SELECT version_num FROM alembic_version")).scalar()
        if not rev:
            raise RuntimeError("FATAL SAFETY VIOLATION: Database has not been initialized with Alembic migrations.")
        if rev != EXPECTED_MIGRATION_REVISION:
            raise RuntimeError(
                f"FATAL SAFETY VIOLATION: Database migration revision '{rev}' does not match expected target revision '{EXPECTED_MIGRATION_REVISION}'. "
                "Rejecting stale or unexpected schema version."
            )
        logger.info(f"Target database Alembic migration revision verified: {rev}")
    except Exception as exc:
        if "FATAL SAFETY VIOLATION" in str(exc):
            raise
        raise RuntimeError(
            f"FATAL SAFETY VIOLATION: Could not verify database migration status: {exc}. Aborting fails closed."
        ) from exc

    # 3. Verify RLS bypass permissions and role authority
    if dialect_name == "postgresql":
        try:
            # Query role privileges from pg_roles
            role_row = session.execute(
                text("SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname = current_user")
            ).first()
            is_super = bool(role_row[0]) if role_row else False
            has_bypass = bool(role_row[1]) if role_row else False

            # Inspect table RLS settings from pg_class
            class_row = session.execute(
                text("SELECT relrowsecurity, relforcerowsecurity FROM pg_class WHERE relname = 'organisations'")
            ).first()
            rls_enabled = bool(class_row[0]) if class_row else False
            rls_forced = bool(class_row[1]) if class_row else False

            # Inspect table owner from pg_tables
            owner_row = session.execute(
                text("SELECT tableowner FROM pg_tables WHERE schemaname = 'public' AND tablename = 'organisations'")
            ).scalar()
            is_owner = (owner_row == db_user) if (owner_row and db_user) else False

            if rls_enabled:
                # When FORCE ROW LEVEL SECURITY is set, even table owners are subject to RLS
                can_bypass = is_super or has_bypass or (is_owner and not rls_forced)
                if not can_bypass:
                    raise RuntimeError(
                        f"FATAL SAFETY VIOLATION: Database role '{db_user}' lacks BYPASSRLS or superuser privileges on table 'organisations'. "
                        "Row-Level Security (RLS) is active (FORCE ROW LEVEL SECURITY) and could silently omit foreign tenant rows. "
                        "Bootstrap preflight must execute with a role possessing BYPASSRLS or superuser privileges."
                    )

            # Set row_security = OFF: under Postgres, if any query is affected by RLS for this role,
            # Postgres raises error 42501 ('query would be affected by row-level security policy')
            # rather than silently omitting rows.
            session.execute(text("SET LOCAL row_security = OFF;"))
        except Exception as exc:
            if "FATAL SAFETY VIOLATION" in str(exc):
                raise
            raise RuntimeError(
                f"FATAL SAFETY VIOLATION: Failed to verify RLS bypass permissions on role '{db_user}': {exc}. Aborting fails closed."
            ) from exc
    else:
        # SQLite or non-PostgreSQL dialect fallback
        try:
            session.execute(text("SET LOCAL row_security = OFF;"))
        except Exception:
            logger.debug(f"row_security parameter unsupported on dialect '{dialect_name}'; proceeding.")

    # 4. Check for foreign organisations (bypassing RLS with migration session)
    try:
        foreign_orgs = session.scalars(
            select(Organisation.id).where(Organisation.id != ORG_ID).limit(5)
        ).all()
        if foreign_orgs:
            raise RuntimeError(
                f"FATAL SAFETY VIOLATION: Target database contains non-evaluation organisations: {foreign_orgs}. "
                "Bootstrap utility cannot run on shared, customer, or multi-tenant databases."
            )
    except Exception as exc:
        raise RuntimeError(
            f"FATAL SAFETY VIOLATION: Failed to check organisation isolation: {exc}. Aborting fails closed."
        ) from exc

    # 5. Check for foreign users
    try:
        foreign_users = session.scalars(
            select(User.email).where(User.org_id != ORG_ID).limit(5)
        ).all()
        if foreign_users:
            raise RuntimeError(
                f"FATAL SAFETY VIOLATION: Target database contains foreign users: {foreign_users}. "
                "Bootstrap utility cannot mutate a database with non-evaluation users."
            )
    except Exception as exc:
        raise RuntimeError(
            f"FATAL SAFETY VIOLATION: Failed to check user isolation: {exc}. Aborting fails closed."
        ) from exc

    logger.info("Database safety verification passed: target is confirmed isolated for evaluation.")


def bootstrap_evaluation_workspace(
    session: Session,
    auth_key: str,
    expected_db_name: Optional[str] = None,
    seed_scenarios: bool = False,
) -> None:
    """Atomically initializes org_sme_eval reference fixtures for the evaluation scenarios in a single transaction."""
    verify_evaluation_database_safety(session, auth_key, expected_db_name)

    # Preserve environment and settings for clean restoration
    orig_env = {
        "ALLOW_SYNTHETIC_SEEDING": os.environ.get("ALLOW_SYNTHETIC_SEEDING"),
        "IS_DEDICATED_EVALUATION_DATABASE": os.environ.get("IS_DEDICATED_EVALUATION_DATABASE"),
        "EVAL_BOOTSTRAP_SECRET_KEY": os.environ.get("EVAL_BOOTSTRAP_SECRET_KEY"),
    }
    orig_settings = {
        "ALLOW_SYNTHETIC_SEEDING": getattr(settings, "ALLOW_SYNTHETIC_SEEDING", False),
        "IS_DEDICATED_EVALUATION_DATABASE": getattr(settings, "IS_DEDICATED_EVALUATION_DATABASE", False),
        "EVAL_BOOTSTRAP_SECRET_KEY": getattr(settings, "EVAL_BOOTSTRAP_SECRET_KEY", None),
    }

    # Configure runtime overrides for the session
    settings.ALLOW_SYNTHETIC_SEEDING = True
    settings.IS_DEDICATED_EVALUATION_DATABASE = True
    settings.EVAL_BOOTSTRAP_SECRET_KEY = auth_key
    os.environ["ALLOW_SYNTHETIC_SEEDING"] = "true"
    os.environ["IS_DEDICATED_EVALUATION_DATABASE"] = "true"
    os.environ["EVAL_BOOTSTRAP_SECRET_KEY"] = auth_key

    try:
        logger.info("Initializing tenant and SME evaluation users...")
        provision_tenant_and_users(session)

        logger.info("Initializing synthetic vendor master records...")
        provision_synthetic_vendors(session)

        logger.info("Initializing synthetic purchase orders...")
        provision_synthetic_purchase_orders(session)

        logger.info("Initializing synthetic goods receipts (GRNs)...")
        provision_synthetic_goods_receipts(session)

        logger.info("Initializing synthetic quality inspections (QCs)...")
        provision_synthetic_quality_controls(session)

        if seed_scenarios:
            logger.info("Initializing baseline demonstration invoice scenarios...")
            from engine.sme_eval_setup import (
                process_scenario_document, DuplicateDetector, IndianAPRuleEngine, HybridAPExtractor
            )
            duplicate_detector = DuplicateDetector()
            rule_engine = IndianAPRuleEngine()
            extractor = HybridAPExtractor(
                rule_engine=rule_engine,
                duplicate_detector=duplicate_detector,
            )
            process_scenario_document(session, extractor, "APTC-009", "09_invoice_AP_26_009.pdf", "CLEAN_3WAY_MATCH")
            process_scenario_document(session, extractor, "APTC-030", "30_invoice_AP_26_011.pdf", "RATE_QTY_VARIANCE")
            process_scenario_document(session, extractor, "APTC-036", "36_invoice_POS_26_112.pdf", "DEGRADED_SCAN")
            process_scenario_document(session, extractor, "APTC-038", "38_payment_receipt_RCPT_26_088.pdf", "NON_PAYABLE_RECEIPT")
            logger.info("Baseline demonstration scenarios initialized. Unseeded fresh acceptance sample: APTC-001 (01_invoice_AP_26_001.pdf).")

        session.commit()
        logger.info("Evaluation workspace bootstrap completed successfully in a single atomic transaction.")
    except Exception as exc:
        session.rollback()
        logger.error(f"FATAL: Bootstrap failed during transaction; rolling back all staged changes: {exc}")
        raise RuntimeError(f"FATAL: Evaluation bootstrap aborted and rolled back cleanly: {exc}") from exc
    finally:
        for k, v in orig_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        for k, v in orig_settings.items():
            setattr(settings, k, v)


def teardown_evaluation_workspace(
    session: Session,
    auth_key: str,
    expected_db_name: Optional[str] = None,
) -> None:
    """Tears down org_sme_eval baseline fixtures, strictly respecting immutable audit events.

    Invariants:
    - If any AuditEvent records exist for org_sme_eval, in-place deletion is REFUSED to preserve
      the database-level trigger 'trg_audit_events_immutable'. Evaluation environments must use
      a disposable database lifecycle (drop and recreate clone) once audit transactions are recorded.
    """
    verify_evaluation_database_safety(session, auth_key, expected_db_name)

    logger.warning("Inspecting evaluation workspace records for teardown...")

    try:
        audit_count = session.execute(
            text("SELECT count(*) FROM audit_events WHERE org_id = :org_id"),
            {"org_id": ORG_ID}
        ).scalar()
        if audit_count is None:
            audit_count = 0
    except Exception as exc:
        raise RuntimeError(
            f"FATAL SAFETY VIOLATION: Failed to inspect audit_events count for teardown: {exc}. "
            "Aborting teardown to protect audit trail immutability."
        ) from exc

    if audit_count > 0:
        raise RuntimeError(
            f"REFUSED: Evaluation workspace contains {audit_count} immutable AuditEvent records. "
            "In-place deletion of audit_events is strictly prohibited by database-level immutability trigger 'trg_audit_events_immutable'. "
            "Evaluation environments must follow a disposable database lifecycle: drop and recreate the dedicated evaluation database instance instead of mutating append-only audit ledgers."
        )

    # Delete dependent child tables in reverse dependency order (excluding audit_events)
    try:
        session.execute(text("DELETE FROM match_gate_checks WHERE org_id = :org_id"), {"org_id": ORG_ID})
        session.execute(text("DELETE FROM match_runs WHERE org_id = :org_id"), {"org_id": ORG_ID})
        session.execute(text("DELETE FROM approval_requests WHERE org_id = :org_id"), {"org_id": ORG_ID})
        session.execute(text("DELETE FROM exception_records WHERE org_id = :org_id"), {"org_id": ORG_ID})
        session.execute(text("DELETE FROM invoice_lines WHERE org_id = :org_id"), {"org_id": ORG_ID})
        session.execute(text("DELETE FROM invoices WHERE org_id = :org_id"), {"org_id": ORG_ID})
        session.execute(text("DELETE FROM goods_receipt_line_snapshots WHERE org_id = :org_id"), {"org_id": ORG_ID})
        session.execute(text("DELETE FROM goods_receipt_snapshots WHERE org_id = :org_id"), {"org_id": ORG_ID})
        session.execute(text("DELETE FROM quality_control_snapshots WHERE org_id = :org_id"), {"org_id": ORG_ID})
        session.execute(text("DELETE FROM work_order_line_snapshots WHERE org_id = :org_id"), {"org_id": ORG_ID})
        session.execute(text("DELETE FROM work_order_snapshots WHERE org_id = :org_id"), {"org_id": ORG_ID})
        session.execute(text("DELETE FROM vendors WHERE org_id = :org_id"), {"org_id": ORG_ID})
        session.execute(text("DELETE FROM role_assignments WHERE org_id = :org_id"), {"org_id": ORG_ID})
        session.execute(text("DELETE FROM identity_memberships WHERE org_id = :org_id"), {"org_id": ORG_ID})
        session.execute(text("DELETE FROM users WHERE org_id = :org_id"), {"org_id": ORG_ID})
        session.execute(text("DELETE FROM organisations WHERE id = :org_id"), {"org_id": ORG_ID})

        session.commit()
        logger.info("Evaluation workspace baseline fixtures torn down cleanly.")
    except Exception as exc:
        session.rollback()
        raise RuntimeError(f"FATAL: Teardown failed and was rolled back: {exc}") from exc


def main() -> None:
    parser = argparse.ArgumentParser(description="Dedicated Evaluation Database Bootstrap Utility")
    parser.add_argument(
        "--confirm-isolated-eval-database",
        action="store_true",
        required=True,
        help="Explicit confirmation that the target database is an isolated evaluation instance.",
    )
    parser.add_argument(
        "--auth-key",
        type=str,
        default="",
        help="(Optional) Authorization secret key. Prefer setting EVAL_BOOTSTRAP_SECRET_KEY env var.",
    )
    parser.add_argument(
        "--auth-key-env",
        type=str,
        default="EVAL_BOOTSTRAP_SECRET_KEY",
        help="Name of environment variable containing the authorization secret key.",
    )
    parser.add_argument(
        "--expected-db-name",
        type=str,
        default=os.environ.get("EXPECTED_EVAL_DATABASE_NAME"),
        help="Expected database name identifier to verify against current_database().",
    )
    parser.add_argument(
        "--database-url",
        type=str,
        default=os.environ.get("MIGRATION_DATABASE_URL") or os.environ.get("DATABASE_URL") or settings.DATABASE_URL,
        help="Direct database connection URL with table owner permissions.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Verifies database safety without modifying records (alias for --verify-only).",
    )
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="Verifies database safety without modifying records.",
    )
    parser.add_argument(
        "--teardown",
        action="store_true",
        help="Tears down baseline fixtures if no immutable audit events exist.",
    )
    parser.add_argument(
        "--seed-golden-scenarios",
        action="store_true",
        help="Pre-ingests baseline demonstration scenarios (APTC-009, APTC-030, APTC-036, APTC-038). Preserves APTC-001 unseeded for fresh acceptance.",
    )

    args = parser.parse_args()

    if not args.confirm_isolated_eval_database:
        logger.error("Refusing to run: --confirm-isolated-eval-database flag is required.")
        sys.exit(1)

    # Resolve authorization key safely
    if args.auth_key:
        logger.warning(
            "SECURITY WARNING: Passing --auth-key via command line exposes secrets in process lists and shell history. "
            f"Prefer using the {args.auth_key_env} environment variable."
        )
        auth_key = args.auth_key.strip()
    else:
        auth_key = os.environ.get(args.auth_key_env, "").strip()

    if not auth_key or len(auth_key) < 32:
        logger.error(f"Refusing to run: Authorization key in {args.auth_key_env} must be at least 32 characters long.")
        sys.exit(1)

    if not args.database_url:
        logger.error("Refusing to run: No database URL configured.")
        sys.exit(1)

    is_dry_run = args.dry_run or args.verify_only

    engine = create_engine(args.database_url)
    session_factory = sessionmaker(bind=engine)
    session = session_factory()

    try:
        if is_dry_run:
            logger.info("DRY-RUN / VERIFICATION MODE: Inspecting target database without modifying records.")
            verify_evaluation_database_safety(session, auth_key, args.expected_db_name)
            logger.info("Verification check succeeded: database is confirmed safe for evaluation bootstrap.")
        elif args.teardown:
            teardown_evaluation_workspace(session, auth_key, args.expected_db_name)
        else:
            bootstrap_evaluation_workspace(session, auth_key, args.expected_db_name, seed_scenarios=args.seed_golden_scenarios)
    finally:
        session.close()


if __name__ == "__main__":
    main()
