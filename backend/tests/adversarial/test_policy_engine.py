"""
Adversarial tests matching the spec's explicit list under "ADVERSARIAL
TESTING":

  Test: LLM proposes RETRY_PAYMENT but risk_flag=true -> ROUTE_TO_HUMAN
  Test: LLM proposes notification but consent_status=opted_out -> DENIED
  Test: attempt_number >= max_attempts -> STOP_RECOVERY
  Test: LLM proposes action outside allowed action set -> REJECTED
  Test: LLM confidence < threshold -> human review

These use the REAL seeded DB policies (app/policies/default_policies.py
via seed_policies.py), proving the actual deployed configuration
enforces these invariants -- not just the engine's logic in isolation
(that's covered separately in test_policy_engine.py).
"""
from app.core.taxonomy import PolicyDecision, RecoveryAction
from app.policies.policy_engine import evaluate_policy
from app.repositories.policy_repository import PolicyRepository


def test_adversarial_retry_with_risk_flag_routes_to_human(db):
    policy = PolicyRepository(db).get_by_cause("insufficient_funds")
    assert policy is not None, "insufficient_funds policy must be seeded"

    result = evaluate_policy(
        RecoveryAction.RETRY_PAYMENT.value, "insufficient_funds", 0.9, 1, True,
        "opted_in", [], 1000.0, policy,
    )
    assert result.decision == PolicyDecision.ROUTE_TO_HUMAN.value


def test_adversarial_notification_with_opted_out_consent_is_denied(db):
    policy = PolicyRepository(db).get_by_cause("checkout_abandonment")
    assert policy is not None

    result = evaluate_policy(
        RecoveryAction.SEND_NOTIFICATION.value, "checkout_abandonment", 0.9, 1, False,
        "opted_out", [], 500.0, policy,
    )
    assert result.decision == PolicyDecision.DENIED.value


def test_adversarial_attempt_number_at_max_denies_retry_enabling_stop_recovery(db):
    """
    Our decision space is APPROVED/DENIED/ROUTE_TO_HUMAN -- STOP_RECOVERY
    is an ACTION, not a policy decision. Proves the two-step realization
    of "Expected: STOP_RECOVERY": (1) a retry at max attempts is DENIED,
    (2) STOP_RECOVERY itself is then always APPROVED. See
    policy_engine.py's docstring for the full reasoning.
    """
    policy = PolicyRepository(db).get_by_cause("insufficient_funds")
    max_retries = policy.max_retries

    retry_result = evaluate_policy(
        RecoveryAction.DELAYED_RETRY.value, "insufficient_funds", 0.9, max_retries, False,
        "opted_in", [], 1000.0, policy,
    )
    assert retry_result.decision == PolicyDecision.DENIED.value
    assert retry_result.rule_triggered == "max_retries_exceeded"

    stop_result = evaluate_policy(
        RecoveryAction.STOP_RECOVERY.value, "insufficient_funds", 0.9, max_retries, False,
        "opted_in", [], 1000.0, policy,
    )
    assert stop_result.decision == PolicyDecision.APPROVED.value


def test_adversarial_action_outside_allowed_set_is_rejected(db):
    policy = PolicyRepository(db).get_by_cause("risk_block")
    assert policy is not None
    assert RecoveryAction.RETRY_PAYMENT.value not in policy.allowed_actions

    result = evaluate_policy(
        RecoveryAction.RETRY_PAYMENT.value, "risk_block", 0.95, 1, False,
        "opted_in", [], 1000.0, policy,
    )
    assert result.decision == PolicyDecision.DENIED.value
    assert result.rule_triggered == "action_not_permitted_for_cause"


def test_adversarial_low_confidence_routes_to_human_review(db):
    policy = PolicyRepository(db).get_by_cause("insufficient_funds")

    result = evaluate_policy(
        RecoveryAction.DELAYED_RETRY.value, "insufficient_funds", 0.1, 1, False,
        "opted_in", [], 1000.0, policy,
    )
    assert result.decision == PolicyDecision.ROUTE_TO_HUMAN.value


def test_adversarial_malformed_action_string_is_rejected():
    from types import SimpleNamespace

    fake_policy = SimpleNamespace(
        allowed_actions=[RecoveryAction.DELAYED_RETRY.value],
        blocked_actions=[],
        confidence_threshold=0.5,
        max_retries=3,
        cooldown_seconds=3600,
        requires_consent=True,
        blocks_on_risk_flag=True,
        max_amount=None,
    )
    result = evaluate_policy(
        "DELETE_ALL_CUSTOMER_DATA", "insufficient_funds", 0.9, 1, False,
        "opted_in", [], 1000.0, fake_policy,
    )
    assert result.decision == PolicyDecision.DENIED.value


def test_zero_policy_violations_across_full_cause_x_action_matrix(db):
    """
    Critical Safety Invariant #6: "Policy violations must be ZERO."
    Exhaustively checks every (cause, action) pair against the REAL
    seeded policies -- whenever an action is APPROVED, it must actually
    be allowed and not blocked for that cause.
    """
    from app.core.taxonomy import ALL_ACTIONS, ALL_CAUSES

    violations = []
    for cause in ALL_CAUSES:
        policy = PolicyRepository(db).get_by_cause(cause)
        assert policy is not None, f"missing seeded policy for {cause}"
        for action in ALL_ACTIONS:
            result = evaluate_policy(action, cause, 0.95, 0, False, "opted_in", [], 100.0, policy)
            if result.decision == PolicyDecision.APPROVED.value:
                if action not in policy.allowed_actions or action in policy.blocked_actions:
                    violations.append((cause, action, result.decision))

    assert violations == [], f"Policy violations found: {violations}"


def test_risk_flagged_case_never_auto_retries_across_all_causes(db):
    """Critical Safety Invariant #3: risk-flagged cases cannot auto-retry."""
    from app.core.taxonomy import ALL_CAUSES

    for cause in ALL_CAUSES:
        policy = PolicyRepository(db).get_by_cause(cause)
        for action in [RecoveryAction.RETRY_PAYMENT.value, RecoveryAction.DELAYED_RETRY.value]:
            result = evaluate_policy(action, cause, 0.95, 0, True, "opted_in", [], 100.0, policy)
            assert result.decision != PolicyDecision.APPROVED.value, (
                f"Risk-flagged {cause}/{action} was APPROVED"
            )


def test_opted_out_customer_never_receives_automated_notification_across_all_causes(db):
    """Critical Safety Invariant #4."""
    from app.core.taxonomy import ALL_CAUSES

    for cause in ALL_CAUSES:
        policy = PolicyRepository(db).get_by_cause(cause)
        result = evaluate_policy(
            RecoveryAction.SEND_NOTIFICATION.value, cause, 0.95, 0, False, "opted_out", [], 100.0, policy
        )
        assert result.decision != PolicyDecision.APPROVED.value, (
            f"opted_out notification for {cause} was APPROVED"
        )
