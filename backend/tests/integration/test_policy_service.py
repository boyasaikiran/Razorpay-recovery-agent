import uuid
from datetime import datetime, timezone

from sqlalchemy import text

from app.core.taxonomy import AuditStage, PolicyDecision
from app.models.recovery_case import RecoveryCase
from app.services.diagnosis_service import diagnose_case
from app.services.policy_service import check_policy_for_case


def _ingest_and_diagnose(api_client, test_merchant, db, *, decline_code=None, amount=2500):
    event_id = f"evt-{uuid.uuid4()}"
    payload = {
        "event_id": event_id,
        "event_type": "payment_failed",
        "event_timestamp": datetime.now(timezone.utc).isoformat(),
        "payload": {"customer_segment": "consumer", "consent_status": "opted_in", "channel_history": "[]"},
        "idempotency_key": f"idem-{event_id}",
        "merchant_id": str(test_merchant),
        "amount": amount,
        "currency": "INR",
        "payment_method": "card",
        "decline_code": decline_code,
        "attempt_number": 1,
    }
    resp = api_client.post("/api/v1/simulate/events", json=payload)
    case_id = resp.json()["recovery_case_id"]
    case = db.query(RecoveryCase).filter_by(id=case_id).one()
    diagnosis = diagnose_case(db, case)
    return case, diagnosis


def test_policy_check_creates_decision_row(api_client, test_merchant, db):
    case, diagnosis = _ingest_and_diagnose(api_client, test_merchant, db, decline_code="EXPIRED_CARD")

    decision = check_policy_for_case(
        db, case, diagnosis,
        proposed_action="CREATE_PAYMENT_LINK",
        attempt_number=1,
        risk_flag=False,
        consent_status="opted_in",
        channel_history=[],
        amount=2500,
    )

    assert decision.proposed_action == "CREATE_PAYMENT_LINK"
    assert decision.policy_decision == PolicyDecision.APPROVED.value


def test_policy_check_writes_policy_checked_audit_log(api_client, test_merchant, db):
    case, diagnosis = _ingest_and_diagnose(api_client, test_merchant, db, decline_code="NSF")

    check_policy_for_case(
        db, case, diagnosis,
        proposed_action="DELAYED_RETRY",
        attempt_number=1,
        risk_flag=False,
        consent_status="opted_in",
        channel_history=[],
        amount=1000,
    )

    row = db.execute(
        text("SELECT stage, decision FROM audit_logs WHERE recovery_case_id = :cid AND stage = :stage"),
        {"cid": case.id, "stage": AuditStage.POLICY_CHECKED.value},
    ).fetchone()
    assert row is not None
    assert row[1] == PolicyDecision.APPROVED.value


def test_policy_check_writes_human_escalated_log_on_route_to_human(api_client, test_merchant, db):
    case, diagnosis = _ingest_and_diagnose(api_client, test_merchant, db, decline_code="RISK_BLOCKED")

    check_policy_for_case(
        db, case, diagnosis,
        proposed_action="RETRY_PAYMENT",
        attempt_number=1,
        risk_flag=True,
        consent_status="opted_in",
        channel_history=[],
        amount=1000,
    )

    row = db.execute(
        text("SELECT stage FROM audit_logs WHERE recovery_case_id = :cid AND stage = :stage"),
        {"cid": case.id, "stage": AuditStage.HUMAN_ESCALATED.value},
    ).fetchone()
    assert row is not None


def test_policy_check_fails_safe_when_no_policy_configured(api_client, test_merchant, db, monkeypatch):
    """
    Critical fail-safe behavior: if a diagnosis somehow produces a cause
    with no seeded Policy row, the system must NOT default to permissive
    approval. Simulated by monkeypatching PolicyRepository.get_by_cause.
    """
    import app.services.policy_service as policy_service_module

    case, diagnosis = _ingest_and_diagnose(api_client, test_merchant, db, decline_code="EXPIRED_CARD")

    monkeypatch.setattr(
        policy_service_module.PolicyRepository, "get_by_cause", lambda self, cause: None
    )

    decision = check_policy_for_case(
        db, case, diagnosis,
        proposed_action="CREATE_PAYMENT_LINK",
        attempt_number=1,
        risk_flag=False,
        consent_status="opted_in",
        channel_history=[],
        amount=2500,
    )

    assert decision.policy_decision == PolicyDecision.ROUTE_TO_HUMAN.value
    assert decision.policy_rule_triggered == "no_policy_configured"
