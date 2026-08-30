import random
import uuid
from datetime import datetime, timezone

from app.agents.agent_loop import run_case_pipeline
from app.core.taxonomy import OutcomeStatus, RecoveryAction
from app.models.recovery_case import RecoveryCase
from app.services.execution_simulator import simulate_execution


def _ingest(api_client, test_merchant, decline_code=None, amount=2500, extra_payload=None):
    event_id = f"evt-{uuid.uuid4()}"
    payload = {
        "event_id": event_id,
        "event_type": "payment_failed",
        "event_timestamp": datetime.now(timezone.utc).isoformat(),
        "payload": {
            "customer_segment": "consumer",
            "consent_status": "opted_in",
            "channel_history": "[]",
            **(extra_payload or {}),
        },
        "idempotency_key": f"idem-{event_id}",
        "merchant_id": str(test_merchant),
        "amount": amount,
        "currency": "INR",
        "payment_method": "card",
        "decline_code": decline_code,
        "attempt_number": 1,
    }
    resp = api_client.post("/api/v1/simulate/events", json=payload)
    assert resp.status_code == 201
    return resp.json()["recovery_case_id"]


def test_full_pipeline_produces_outcome_when_executed(api_client, test_merchant, db):
    case_id = _ingest(api_client, test_merchant, decline_code="EXPIRED_CARD")
    case = db.query(RecoveryCase).filter_by(id=case_id).one()

    result = run_case_pipeline(db, case)

    assert result.executed is True
    assert result.outcome is not None
    assert result.outcome.status in (OutcomeStatus.SUCCESS.value, OutcomeStatus.FAILURE.value)
    assert result.action.status == result.outcome.status


def test_escalate_to_human_resolves_to_human_review(api_client, test_merchant, db):
    case_id = _ingest(api_client, test_merchant, decline_code="RISK_BLOCKED")
    case = db.query(RecoveryCase).filter_by(id=case_id).one()

    result = run_case_pipeline(db, case)

    if result.recommendation.action == RecoveryAction.ESCALATE_TO_HUMAN.value:
        assert result.executed is True
        assert result.outcome.status == OutcomeStatus.HUMAN_REVIEW.value
        assert result.outcome.recovered_amount == 0.0


def test_stochastic_outcome_respects_high_recovery_probability(api_client, test_merchant, db):
    from app.agents.tools import tool_check_policy, tool_classify_cause, tool_execute_recovery

    case_id = _ingest(api_client, test_merchant, decline_code="ISSUER_UNAVAILABLE")
    case = db.query(RecoveryCase).filter_by(id=case_id).one()

    diagnosis = tool_classify_cause(db, case)
    decision = tool_check_policy(
        db, case, diagnosis, RecoveryAction.DELAYED_RETRY.value,
        1, False, "opted_in", [], 2500.0,
    )
    if decision.policy_decision != "APPROVED":
        return
    action = tool_execute_recovery(db, decision)

    seeded_rng = random.Random(1)
    outcome = simulate_execution(
        db, action, amount_at_risk=2500, currency="INR",
        recovery_probability=0.999, rng=seeded_rng,
    )
    assert outcome.status == OutcomeStatus.SUCCESS.value
    assert outcome.recovered_amount > 0


def test_stochastic_outcome_respects_low_recovery_probability(api_client, test_merchant, db):
    from app.agents.tools import tool_check_policy, tool_classify_cause, tool_execute_recovery

    case_id = _ingest(api_client, test_merchant, decline_code="ISSUER_UNAVAILABLE")
    case = db.query(RecoveryCase).filter_by(id=case_id).one()

    diagnosis = tool_classify_cause(db, case)
    decision = tool_check_policy(
        db, case, diagnosis, RecoveryAction.DELAYED_RETRY.value,
        1, False, "opted_in", [], 2500.0,
    )
    if decision.policy_decision != "APPROVED":
        return
    action = tool_execute_recovery(db, decision)

    seeded_rng = random.Random(1)
    outcome = simulate_execution(
        db, action, amount_at_risk=2500, currency="INR",
        recovery_probability=0.001, rng=seeded_rng,
    )
    assert outcome.status == OutcomeStatus.FAILURE.value
    assert outcome.recovered_amount == 0.0


def test_recovered_amount_never_exceeds_amount_at_risk_on_success(api_client, test_merchant, db):
    case_id = _ingest(api_client, test_merchant, decline_code="EXPIRED_CARD", amount=5000)
    case = db.query(RecoveryCase).filter_by(id=case_id).one()
    result = run_case_pipeline(db, case)

    if result.executed and result.outcome.status == OutcomeStatus.SUCCESS.value:
        assert result.outcome.recovered_amount <= 5000
        assert result.outcome.recovered_amount > 0


def test_all_executed_actions_are_marked_simulated(api_client, test_merchant, db):
    case_id = _ingest(api_client, test_merchant, decline_code="NSF")
    case = db.query(RecoveryCase).filter_by(id=case_id).one()
    result = run_case_pipeline(db, case)

    if result.executed:
        assert result.action.simulated is True


def test_deterministic_outcomes_dict_covers_the_expected_actions():
    from app.services.execution_simulator import _DETERMINISTIC_OUTCOMES

    assert _DETERMINISTIC_OUTCOMES[RecoveryAction.ESCALATE_TO_HUMAN.value] == OutcomeStatus.HUMAN_REVIEW.value
    assert _DETERMINISTIC_OUTCOMES[RecoveryAction.LOG_PROMISE_TO_PAY.value] == OutcomeStatus.HUMAN_REVIEW.value
    assert _DETERMINISTIC_OUTCOMES[RecoveryAction.STOP_RECOVERY.value] == OutcomeStatus.STOPPED.value
