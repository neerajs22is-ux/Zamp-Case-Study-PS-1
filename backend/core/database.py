"""Database Engine and Session Management (SQLAlchemy 2.0).

Enforces:
1. PostgreSQL engine in production/staging.
2. Connection health verification.
3. Transactional session lifecycle with atomic rollbacks on error.
"""

from __future__ import annotations

import logging
from typing import Generator, Optional
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from sqlalchemy.pool import QueuePool, StaticPool

from backend.core.config import AppEnv, settings

logger = logging.getLogger("ap_command_center.db")

Base = declarative_base()

def get_engine():
    db_url = settings.DATABASE_URL
    if db_url and db_url.startswith("postgres://"):
        db_url = "postgresql://" + db_url[len("postgres://"):]
    if not db_url:
        if settings.APP_ENV == AppEnv.TEST:
            db_url = "sqlite:///:memory:"
        else:
            # In development when no PostgreSQL is configured, return None
            # causing health checks to truthfully report UNCONFIGURED / BLOCKED
            return None

    connect_args = {}
    if db_url.startswith("sqlite"):
        connect_args["check_same_thread"] = False
        return create_engine(
            db_url,
            connect_args=connect_args,
            poolclass=StaticPool,
            echo=False,
        )

    # PostgreSQL configuration
    # Note: When using transaction poolers like PgBouncer (e.g. Supabase port 6543),
    # prepared statements can cause DuplicatePreparedStatement errors across re-used pooled connections.
    # Setting prepare_threshold=None for psycopg v3 disables client-side prepared statement caching cleanly.
    pg_connect_args = {}
    if "psycopg" in db_url and "psycopg2" not in db_url:
        pg_connect_args["prepare_threshold"] = None

    return create_engine(
        db_url,
        connect_args=pg_connect_args,
        poolclass=QueuePool,
        pool_size=settings.DB_POOL_SIZE,
        max_overflow=settings.DB_MAX_OVERFLOW,
        pool_timeout=settings.DB_TIMEOUT_SECONDS,
        pool_pre_ping=True,
        echo=False,
    )

engine = get_engine()

if engine:
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
else:
    SessionLocal = None


def get_db() -> Generator[Optional[Session], None, None]:
    """FastAPI dependency yielding an isolated transactional database session."""
    if SessionLocal is None:
        yield None
        return

    session = SessionLocal()
    try:
        yield session
    except Exception:
        session.rollback()
        raise
    finally:
        session.info.clear()
        session.close()


def set_tenant_context(session: Session, org_id: str) -> None:
    """Sets the tenant context for the current session and PostgreSQL transaction.

    In PostgreSQL: executes `SELECT set_config('app.current_org_id', :org_id, true)`
    where is_local=true guarantees strictly transaction-local scope.
    In SQLite (unit testing): records in session.info for test assertions.
    """
    clean_org_id = (org_id or "").strip()
    session.info["tenant_org_id"] = clean_org_id
    session.info["app.current_org_id"] = clean_org_id
    try:
        bind = session.get_bind()
        if bind and "postgresql" in bind.dialect.name:
            session.execute(
                text("SELECT set_config('app.current_org_id', :org_id, true)"),
                {"org_id": clean_org_id}
            )
    except Exception as exc:
        logger.exception("Could not set database tenant context")
        raise RuntimeError("Database tenant context could not be established") from exc


@event.listens_for(Session, "after_begin")
def enforce_transaction_tenant_context(session, transaction, connection):
    """Enforces transaction-local tenant context isolation on PostgreSQL connections."""
    if connection.dialect.name == "postgresql":
        org_id = session.info.get("tenant_org_id", "")
        connection.execute(
            text("SELECT set_config('app.current_org_id', :org_id, true)"),
            {"org_id": org_id or ""}
        )


@event.listens_for(QueuePool, "checkin")
def reset_connection_on_pool_checkin(dbapi_connection, connection_record):
    """Guarantees connection-level settings are wiped when connection returns to pool."""
    try:
        if hasattr(dbapi_connection, "pgconn") and dbapi_connection.pgconn.transaction_status != 0:
            dbapi_connection.rollback()
        with dbapi_connection.cursor() as cursor:
            cursor.execute("SELECT set_config('app.current_org_id', '', false);")
        if hasattr(dbapi_connection, "rollback"):
            dbapi_connection.rollback()
    except Exception:
        pass


def check_db_health() -> dict:
    """Verifies live database connectivity and returns truthful status."""
    if not settings.DATABASE_URL:
        return {
            "status": "NOT_CONFIGURED",
            "message": "DATABASE_URL is not configured. PostgreSQL instance required.",
            "database_type": None,
            "readiness": False,
        }

    if engine is None:
        return {
            "status": "BLOCKED",
            "message": "Database engine not initialized.",
            "database_type": None,
            "readiness": False,
        }

    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            row = result.scalar()
            if row == 1:
                db_type = "PostgreSQL" if "postgresql" in str(engine.url) else "SQLite (Test-Only)"
                return {
                    "status": "CONNECTED",
                    "message": "Database connectivity verified.",
                    "database_type": db_type,
                    "readiness": True,
                }
            return {
                "status": "DEGRADED",
                "message": "Unexpected response from database ping query.",
                "database_type": str(engine.url.drivername),
                "readiness": False,
            }
    except Exception as exc:
        logger.error(f"Database health check failed: {exc}")
        return {
            "status": "ERROR",
            "message": f"Database connection error: {exc.__class__.__name__}",
            "database_type": str(engine.url.drivername) if engine else None,
            "readiness": False,
        }
