import uuid
from datetime import datetime, timezone

from app.agents.agent_loop import run_case_pipeline
from app.core.taxonomy import PolicyDecision
from app.models.recovery_case import RecoveryCase


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


def test_pipeline_executes_when_policy_approves(api_client, test_merchant, db):
    case_id = _ingest(api_client, test_merchant, decline_code="EXPIRED_CARD")
    case = db.query(RecoveryCase).filter_by(id=case_id).one()

    result = run_case_pipeline(db, case)

    assert result.decision.policy_decision == PolicyDecision.APPROVED.value
    assert result.executed is True
    assert result.action is not None
    assert result.action.action_type == result.decision.proposed_action


def test_pipeline_never_auto_retries_a_risk_flagged_case(api_client, test_merchant, db):
    """
    Critical Safety Invariant #3: risk-flagged cases cannot auto-retry.
    NOTE: this does NOT mean nothing executes -- risk_block's default
    action is ESCALATE_TO_HUMAN (Phase 8), and policy rule 0 always
    approves escalation (it's always safe). "Executing an escalation"
    is the correct, safe outcome. The actual invariant under test is
    that the EXECUTED action, whatever it is, is never a retry/payment/
    communication action -- only ESCALATE_TO_HUMAN or STOP_RECOVERY.
    """
    case_id = _ingest(
        api_client, test_merchant, decline_code="RISK_BLOCKED",
        extra_payload={"risk_flag": True},
    )
    case = db.query(RecoveryCase).filter_by(id=case_id).one()

    result = run_case_pipeline(db, case)

    if result.executed:
        assert result.action.action_type in ("ESCALATE_TO_HUMAN", "STOP_RECOVERY"), (
            f"Risk-flagged case executed a non-safe action: {result.action.action_type}"
        )


def test_pipeline_execution_is_consistent_with_policy_decision(api_client, test_merchant, db):
    """
    IF diagnosis confidence ends up below policy threshold (real model
    confidence varies by input), THEN execution must not happen. We
    assert the implication holds rather than a specific outcome.
    """
    case_id = _ingest(api_client, test_merchant, decline_code=None)
    case = db.query(RecoveryCase).filter_by(id=case_id).one()

    result = run_case_pipeline(db, case)

    if result.decision.policy_decision != PolicyDecision.APPROVED.value:
        assert result.executed is False
        assert result.action is None
    else:
        assert result.executed is True


def test_pipeline_never_executes_for_opted_out_customer_notification(api_client, test_merchant, db):
    case_id = _ingest(
        api_client, test_merchant, decline_code=None,
        extra_payload={"consent_status": "opted_out", "customer_segment": "consumer"},
    )
    case = db.query(RecoveryCase).filter_by(id=case_id).one()

    result = run_case_pipeline(db, case)

    if result.recommendation.action == "SEND_NOTIFICATION":
        assert result.decision.policy_decision == PolicyDecision.DENIED.value
        assert result.executed is False


def test_pipeline_routes_to_human_when_retry_proposed_under_risk_flag(api_client, test_merchant, db, monkeypatch):
    """
    Forces select_action to propose a retry-type action (bypassing
    Phase 8's own risk-aware default) specifically to prove check_policy
    -- not action recommendation -- is the actual enforcement point for
    "risk-flagged cases cannot auto-retry". This is what actually
    exercises the ROUTE_TO_HUMAN path end-to-end through the real loop.
    """
    import app.agents.tools as tools_module
    from app.schemas.action_recommendation import ActionRecommendation

    def _force_retry(db, case, diagnosis_row, prediction_row):
        return ActionRecommendation(action="RETRY_PAYMENT", reason="forced for test")

    monkeypatch.setattr(tools_module, "recommend_action_for_case", _force_retry)

    case_id = _ingest(
        api_client, test_merchant, decline_code="RISK_BLOCKED",
        extra_payload={"risk_flag": True},
    )
    case = db.query(RecoveryCase).filter_by(id=case_id).one()

    result = run_case_pipeline(db, case)

    assert result.decision.policy_decision == PolicyDecision.ROUTE_TO_HUMAN.value
    assert result.executed is False
    assert result.action is None


def test_pipeline_result_always_has_a_persisted_decision_row(api_client, test_merchant, db):
    case_id = _ingest(api_client, test_merchant, decline_code="OTP_FAILED")
    case = db.query(RecoveryCase).filter_by(id=case_id).one()

    result = run_case_pipeline(db, case)

    assert result.decision.id is not None
    assert result.decision.recovery_case_id == case.id
