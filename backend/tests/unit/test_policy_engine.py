from types import SimpleNamespace

from app.core.taxonomy import PolicyDecision, RecoveryAction
from app.policies.policy_engine import evaluate_policy


def _policy(**overrides):
    defaults = dict(
        allowed_actions=[RecoveryAction.DELAYED_RETRY.value, RecoveryAction.SEND_NOTIFICATION.value,
                          RecoveryAction.ESCALATE_TO_HUMAN.value, RecoveryAction.STOP_RECOVERY.value],
        blocked_actions=[],
        confidence_threshold=0.5,
        max_retries=3,
        cooldown_seconds=3600,
        requires_consent=True,
        blocks_on_risk_flag=True,
        max_amount=None,
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def _eval(**kwargs):
    base = dict(
        proposed_action=RecoveryAction.DELAYED_RETRY.value,
        cause="insufficient_funds",
        confidence=0.9,
        attempt_number=1,
        risk_flag=False,
        consent_status="opted_in",
        channel_history=[],
        amount=1000.0,
        policy=_policy(),
    )
    base.update(kwargs)
    return evaluate_policy(**base)


def test_always_safe_actions_are_always_approved_even_with_risk_flag():
    result = _eval(proposed_action=RecoveryAction.ESCALATE_TO_HUMAN.value, risk_flag=True, confidence=0.0)
    assert result.decision == PolicyDecision.APPROVED.value

    result = _eval(proposed_action=RecoveryAction.STOP_RECOVERY.value, risk_flag=True, confidence=0.0)
    assert result.decision == PolicyDecision.APPROVED.value


def test_risk_flag_routes_to_human():
    result = _eval(proposed_action=RecoveryAction.RETRY_PAYMENT.value, risk_flag=True,
                    policy=_policy(allowed_actions=[RecoveryAction.RETRY_PAYMENT.value,
                                                     RecoveryAction.ESCALATE_TO_HUMAN.value,
                                                     RecoveryAction.STOP_RECOVERY.value]))
    assert result.decision == PolicyDecision.ROUTE_TO_HUMAN.value
    assert result.rule_triggered == "risk_flag_block"


def test_low_confidence_routes_to_human():
    result = _eval(confidence=0.1, policy=_policy(confidence_threshold=0.5))
    assert result.decision == PolicyDecision.ROUTE_TO_HUMAN.value
    assert result.rule_triggered == "confidence_below_threshold"


def test_action_not_in_allowed_list_is_denied():
    result = _eval(
        proposed_action=RecoveryAction.CREATE_PAYMENT_LINK.value,
        policy=_policy(allowed_actions=[RecoveryAction.DELAYED_RETRY.value]),
    )
    assert result.decision == PolicyDecision.DENIED.value
    assert result.rule_triggered == "action_not_permitted_for_cause"


def test_action_in_blocked_list_is_denied_even_if_also_allowed():
    result = _eval(
        proposed_action=RecoveryAction.RETRY_PAYMENT.value,
        policy=_policy(
            allowed_actions=[RecoveryAction.RETRY_PAYMENT.value],
            blocked_actions=[RecoveryAction.RETRY_PAYMENT.value],
        ),
    )
    assert result.decision == PolicyDecision.DENIED.value
    assert result.rule_triggered == "action_not_permitted_for_cause"


def test_notification_denied_when_opted_out():
    result = _eval(
        proposed_action=RecoveryAction.SEND_NOTIFICATION.value,
        consent_status="opted_out",
        policy=_policy(requires_consent=True),
    )
    assert result.decision == PolicyDecision.DENIED.value
    assert result.rule_triggered == "consent_opted_out"


def test_notification_allowed_when_opted_in():
    result = _eval(proposed_action=RecoveryAction.SEND_NOTIFICATION.value, consent_status="opted_in")
    assert result.decision == PolicyDecision.APPROVED.value


def test_notification_not_blocked_by_consent_when_policy_does_not_require_it():
    result = _eval(
        proposed_action=RecoveryAction.SEND_NOTIFICATION.value,
        consent_status="opted_out",
        policy=_policy(requires_consent=False),
    )
    assert result.decision == PolicyDecision.APPROVED.value


def test_retry_denied_when_attempt_number_reaches_max():
    result = _eval(proposed_action=RecoveryAction.DELAYED_RETRY.value, attempt_number=3,
                    policy=_policy(max_retries=3))
    assert result.decision == PolicyDecision.DENIED.value
    assert result.rule_triggered == "max_retries_exceeded"


def test_retry_approved_when_attempt_number_below_max():
    result = _eval(proposed_action=RecoveryAction.DELAYED_RETRY.value, attempt_number=1,
                    policy=_policy(max_retries=3))
    assert result.decision == PolicyDecision.APPROVED.value


def test_amount_exceeding_max_routes_to_human():
    result = _eval(amount=50000.0, policy=_policy(max_amount=10000.0))
    assert result.decision == PolicyDecision.ROUTE_TO_HUMAN.value
    assert result.rule_triggered == "monetary_limit_exceeded"


def test_amount_within_max_is_approved():
    result = _eval(amount=5000.0, policy=_policy(max_amount=10000.0))
    assert result.decision == PolicyDecision.APPROVED.value


def test_communication_limit_routes_to_human():
    result = _eval(
        proposed_action=RecoveryAction.SEND_NOTIFICATION.value,
        channel_history=["email", "sms", "whatsapp"],
    )
    assert result.decision == PolicyDecision.ROUTE_TO_HUMAN.value
    assert result.rule_triggered == "communication_limit_reached"


def test_missing_attempt_number_defaults_to_zero_not_crash():
    result = _eval(attempt_number=None)
    assert result.decision == PolicyDecision.APPROVED.value


def test_missing_channel_history_defaults_to_empty_not_crash():
    result = _eval(proposed_action=RecoveryAction.SEND_NOTIFICATION.value, channel_history=None)
    assert result.decision == PolicyDecision.APPROVED.value


def test_rule_precedence_risk_flag_before_action_not_allowed():
    result = _eval(
        proposed_action=RecoveryAction.CREATE_PAYMENT_LINK.value,
        risk_flag=True,
        policy=_policy(allowed_actions=[RecoveryAction.DELAYED_RETRY.value]),
    )
    assert result.decision == PolicyDecision.ROUTE_TO_HUMAN.value
    assert result.rule_triggered == "risk_flag_block"
