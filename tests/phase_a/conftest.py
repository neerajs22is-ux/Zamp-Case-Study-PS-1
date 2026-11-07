"""Pytest Fixtures for Phase A Verification Suite."""

import os
import sys
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Set test environment
os.environ["APP_ENV"] = "test"
# DATABASE_URL preserved from settings
os.environ["STORAGE_BUCKET_NAME"] = "test-bucket"
os.environ["SECRET_KEY"] = "test-secret-key-32-characters-minimum"

from backend.core.config import settings, AppEnv
settings.APP_ENV = AppEnv.TEST
from backend.core.database import Base, get_db
from backend.main import app

# In-memory test engine for unit test isolation
test_engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    """Create all tables and SQLite triggers for test isolation."""
    Base.metadata.create_all(bind=test_engine)
    with test_engine.connect() as conn:
        conn.exec_driver_sql("""
            CREATE TRIGGER IF NOT EXISTS trg_audit_events_no_update
            BEFORE UPDATE ON audit_events
            BEGIN
                SELECT RAISE(ABORT, 'audit_events is strictly append-only: UPDATE operations are prohibited.');
            END;
        """)
        conn.exec_driver_sql("""
            CREATE TRIGGER IF NOT EXISTS trg_audit_events_no_delete
            BEFORE DELETE ON audit_events
            BEGIN
                SELECT RAISE(ABORT, 'audit_events is strictly append-only: DELETE operations are prohibited.');
            END;
        """)
        conn.commit()
    yield
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture
def db_session():
    """Isolated transactional test session with rollback."""
    connection = test_engine.connect()
    transaction = connection.begin()
    # SQLite must begin a real outer transaction before the first SAVEPOINT.
    connection.exec_driver_sql("BEGIN")
    session = TestingSessionLocal(bind=connection, join_transaction_mode="create_savepoint")

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def client(db_session):
    def override_get_db():
        try:
            yield db_session
        except Exception:
            db_session.rollback()
            raise

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
