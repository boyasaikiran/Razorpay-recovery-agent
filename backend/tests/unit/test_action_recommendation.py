import pytest
from pydantic import ValidationError

from app.core.taxonomy import ALL_ACTIONS, Cause, DiagnosisMethod, RecoveryAction
from app.schemas.action_recommendation import ActionRecommendation
from app.schemas.diagnosis import DiagnosisResult
from app.services.action_recommendation_service import recommend_action
from app.services.diagnosis_service import DIAGNOSIS_CONFIDENCE_THRESHOLD


def _diagnosis(cause: str, confidence: float = 0.9) -> DiagnosisResult:
    return DiagnosisResult(
        cause=cause,
        confidence=confidence,
        reason="test",
        signals=[],
        method=DiagnosisMethod.RULE_BASED.value,
    )


def test_low_confidence_always_escalates_to_human_regardless_of_cause():
    diagnosis = _diagnosis(Cause.INSUFFICIENT_FUNDS.value, confidence=DIAGNOSIS_CONFIDENCE_THRESHOLD - 0.1)
    result = recommend_action(diagnosis, recovery_probability=0.9)
    assert result.action == RecoveryAction.ESCALATE_TO_HUMAN.value


def test_very_low_recovery_probability_recommends_stop():
    diagnosis = _diagnosis(Cause.INSUFFICIENT_FUNDS.value, confidence=0.95)
    result = recommend_action(diagnosis, recovery_probability=0.05)
    assert result.action == RecoveryAction.STOP_RECOVERY.value


def test_insufficient_funds_maps_to_delayed_retry():
    diagnosis = _diagnosis(Cause.INSUFFICIENT_FUNDS.value)
    result = recommend_action(diagnosis, recovery_probability=0.6)
    assert result.action == RecoveryAction.DELAYED_RETRY.value


def test_expired_payment_method_maps_to_payment_link():
    diagnosis = _diagnosis(Cause.EXPIRED_PAYMENT_METHOD.value)
    result = recommend_action(diagnosis, recovery_probability=0.6)
    assert result.action == RecoveryAction.CREATE_PAYMENT_LINK.value


def test_checkout_abandonment_maps_to_notification():
    diagnosis = _diagnosis(Cause.CHECKOUT_ABANDONMENT.value)
    result = recommend_action(diagnosis, recovery_probability=0.6)
    assert result.action == RecoveryAction.SEND_NOTIFICATION.value


def test_risk_block_maps_to_human_escalation():
    diagnosis = _diagnosis(Cause.RISK_BLOCK.value)
    result = recommend_action(diagnosis, recovery_probability=0.6)
    assert result.action == RecoveryAction.ESCALATE_TO_HUMAN.value


def test_recommendation_when_recovery_probability_unavailable():
    diagnosis = _diagnosis(Cause.INSUFFICIENT_FUNDS.value)
    result = recommend_action(diagnosis, recovery_probability=None)
    assert result.action == RecoveryAction.DELAYED_RETRY.value


def test_every_cause_maps_to_a_valid_action():
    for cause in [c.value for c in Cause]:
        diagnosis = _diagnosis(cause)
        result = recommend_action(diagnosis, recovery_probability=0.6)
        assert result.action in ALL_ACTIONS


def test_action_recommendation_schema_rejects_invalid_action():
    with pytest.raises(ValidationError):
        ActionRecommendation(action="DELETE_EVERYTHING", reason="not a real action")
