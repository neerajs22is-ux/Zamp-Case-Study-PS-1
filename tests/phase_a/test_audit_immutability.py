"""Tests for Database-Level Append-Only Audit Immutability."""

import datetime
import pytest
from sqlalchemy import text
from backend.models.domain import AuditEvent


def test_audit_event_insertion(db_session):
    """Verifies that new audit records can be appended cleanly."""
    evt = AuditEvent(
        id="evt_test_insert_01",
        invoice_id="inv_test_01",
        org_id="org_default",
        actor_id="user_test_01",
        actor_role="AP_ASSOCIATE",
        action="INVOICE_INGESTED",
        reason="Initial ingestion",
        timestamp=datetime.datetime.utcnow(),
    )
    db_session.add(evt)
    db_session.flush()

    retrieved = db_session.get(AuditEvent, "evt_test_insert_01")
    assert retrieved is not None
    assert retrieved.action == "INVOICE_INGESTED"


def test_audit_event_update_rejected_by_orm_and_db(db_session):
    """Verifies that UPDATE on audit_events raises an exception and fails."""
    evt = AuditEvent(
        id="evt_test_update_01",
        invoice_id="inv_test_01",
        org_id="org_default",
        actor_id="user_test_01",
        actor_role="AP_ASSOCIATE",
        action="ORIGINAL_ACTION",
        reason="Original reason",
        timestamp=datetime.datetime.utcnow(),
    )
    db_session.add(evt)
    db_session.flush()

    # Attempt 1: ORM-level update
    with pytest.raises(PermissionError, match="audit_events is strictly append-only: UPDATE"):
        evt.action = "TAMPERED_ACTION"
        db_session.flush()

    db_session.rollback()

    # Re-insert for SQL level trigger test
    evt2 = AuditEvent(
        id="evt_test_update_02",
        invoice_id="inv_test_01",
        org_id="org_default",
        actor_id="user_test_01",
        actor_role="AP_ASSOCIATE",
        action="ORIGINAL_ACTION",
        timestamp=datetime.datetime.utcnow(),
    )
    db_session.add(evt2)
    db_session.flush()

    # Attempt 2: Direct SQL UPDATE statement
    with pytest.raises(Exception, match="audit_events is strictly append-only"):
        db_session.execute(
            text("UPDATE audit_events SET action = 'TAMPERED_SQL' WHERE id = 'evt_test_update_02'")
        )
        db_session.flush()


def test_audit_event_delete_rejected_by_orm_and_db(db_session):
    """Verifies that DELETE on audit_events raises an exception and fails."""
    evt = AuditEvent(
        id="evt_test_delete_01",
        invoice_id="inv_test_01",
        org_id="org_default",
        actor_id="user_test_01",
        actor_role="AP_ASSOCIATE",
        action="ACTION_TO_DELETE",
        timestamp=datetime.datetime.utcnow(),
    )
    db_session.add(evt)
    db_session.flush()

    # Attempt 1: ORM-level delete
    with pytest.raises(PermissionError, match="audit_events is strictly append-only: DELETE"):
        db_session.delete(evt)
        db_session.flush()

    db_session.rollback()

    # Re-insert for SQL level trigger test
    evt2 = AuditEvent(
        id="evt_test_delete_02",
        invoice_id="inv_test_01",
        org_id="org_default",
        actor_id="user_test_01",
        actor_role="AP_ASSOCIATE",
        action="ACTION_TO_DELETE_SQL",
        timestamp=datetime.datetime.utcnow(),
    )
    db_session.add(evt2)
    db_session.flush()

    # Attempt 2: Direct SQL DELETE statement
    with pytest.raises(Exception, match="audit_events is strictly append-only"):
        db_session.execute(
            text("DELETE FROM audit_events WHERE id = 'evt_test_delete_02'")
        )
        db_session.flush()
