"""
Adversarial test matching the spec's explicit requirement:
  Test: audit write fails
  Expected: case fails loudly rather than silently continuing
"""
import uuid

import pytest
from sqlalchemy.exc import IntegrityError

from app.repositories.audit_log_repository import AuditLogRepository


def test_audit_write_failure_propagates_not_swallowed(db):
    """
    Directly forces the failure mode: AuditLogRepository.write() with a
    recovery_case_id that violates the FK constraint. No try/except
    exists anywhere in AuditLogRepository or its callers that would
    catch and discard this -- confirmed by the exception reaching this
    test unmodified.
    """
    repo = AuditLogRepository(db)
    bogus_case_id = uuid.uuid4()

    with pytest.raises(IntegrityError):
        repo.write(
            stage="CAUSE_CLASSIFIED",
            actor="test",
            recovery_case_id=bogus_case_id,
            decision="insufficient_funds",
            reason="this write should fail at the DB level",
            simulation_status=True,
        )
    db.rollback()


def test_diagnosis_service_aborts_when_audit_write_fails(api_client, test_merchant, db, monkeypatch):
    """
    Higher-level proof: if the audit write inside diagnose_case fails,
    the WHOLE diagnose_case call raises -- it does not return a
    "successful" Diagnosis while silently losing the audit trail.
    """
    import uuid as uuid_module
    from datetime import datetime, timezone

    import app.services.diagnosis_service as diagnosis_service_module
    from app.models.recovery_case import RecoveryCase

    event_id = f"evt-{uuid_module.uuid4()}"
    resp = api_client.post(
        "/api/v1/simulate/events",
        json={
            "event_id": event_id,
            "event_type": "payment_failed",
            "event_timestamp": datetime.now(timezone.utc).isoformat(),
            "payload": {},
            "idempotency_key": f"idem-{event_id}",
            "merchant_id": str(test_merchant),
            "amount": 1000,
            "currency": "INR",
            "decline_code": "EXPIRED_CARD",
            "attempt_number": 1,
        },
    )
    case_id = resp.json()["recovery_case_id"]
    case = db.query(RecoveryCase).filter_by(id=case_id).one()

    def _broken_write(self, **kwargs):
        raise RuntimeError("Simulated audit backend outage")

    monkeypatch.setattr(diagnosis_service_module.AuditLogRepository, "write", _broken_write)

    with pytest.raises(RuntimeError, match="Simulated audit backend outage"):
        diagnosis_service_module.diagnose_case(db, case)

    db.rollback()
    from app.models.diagnosis import Diagnosis

    leftover = db.query(Diagnosis).filter_by(recovery_case_id=case_id).all()
    assert leftover == [], (
        "A Diagnosis row was persisted even though its audit write failed -- "
        "this violates 'every execution has an audit record'."
    )
