"""
Deterministic policy engine (Phase 9) -- THE most important safety
component in this system.

CORE PRINCIPLE: LLM PROPOSES. POLICY ENGINE DISPOSES.

This module is plain, deterministic Python. No model call, no
randomness, no I/O. Given the same inputs it always returns the same
decision.

RULE PRECEDENCE (evaluated in this exact order; first match wins):
  0. proposed_action in {ESCALATE_TO_HUMAN, STOP_RECOVERY} -> APPROVED
     immediately. Always safe.
  1. risk_flag AND policy.blocks_on_risk_flag -> ROUTE_TO_HUMAN.
  2. confidence < policy.confidence_threshold -> ROUTE_TO_HUMAN.
  3. proposed_action not in policy.allowed_actions, OR in
     policy.blocked_actions -> DENIED.
  4. proposed_action is a customer-communication action AND
     policy.requires_consent AND consent_status == "opted_out" ->
     DENIED.
  5. proposed_action is a retry-type action AND
     attempt_number >= policy.max_retries -> DENIED. (Caller/agent is
     expected to next propose STOP_RECOVERY, which rule 0 approves.)
  6. amount and policy.max_amount both set AND amount > max_amount ->
     ROUTE_TO_HUMAN.
  7. proposed_action == SEND_NOTIFICATION AND
     len(channel_history) >= COMMUNICATION_LIMIT -> ROUTE_TO_HUMAN.
  8. Otherwise -> APPROVED.

KNOWN SIMPLIFICATION: rule 7 approximates a "cooldown" using contact
COUNT rather than elapsed time, since our schema doesn't store
per-channel contact timestamps yet. policy.cooldown_seconds is
persisted for a real cooldown check once timestamps exist; it is not
enforced here. Stated plainly rather than silently ignored.
"""
from typing import Optional

from app.core.taxonomy import PolicyDecision, RecoveryAction
from app.schemas.policy import PolicyEvaluationResult

ALWAYS_SAFE_ACTIONS = {RecoveryAction.ESCALATE_TO_HUMAN.value, RecoveryAction.STOP_RECOVERY.value}
COMMUNICATION_ACTIONS = {RecoveryAction.SEND_NOTIFICATION.value}
RETRY_ACTIONS = {RecoveryAction.RETRY_PAYMENT.value, RecoveryAction.DELAYED_RETRY.value}
COMMUNICATION_LIMIT = 3


def evaluate_policy(
    proposed_action,
    cause,
    confidence,
    attempt_number,
    risk_flag,
    consent_status,
    channel_history,
    amount,
    policy,
) -> PolicyEvaluationResult:
    attempt_number = attempt_number or 0
    channel_history = channel_history or []

    if proposed_action in ALWAYS_SAFE_ACTIONS:
        return PolicyEvaluationResult(
            decision=PolicyDecision.APPROVED.value,
            reason=f"'{proposed_action}' is an always-safe action; approved unconditionally.",
            rule_triggered="always_safe_action",
        )

    if risk_flag and policy.blocks_on_risk_flag:
        return PolicyEvaluationResult(
            decision=PolicyDecision.ROUTE_TO_HUMAN.value,
            reason="risk_flag is set and this cause's policy blocks automated action on risk.",
            rule_triggered="risk_flag_block",
        )

    if confidence < policy.confidence_threshold:
        return PolicyEvaluationResult(
            decision=PolicyDecision.ROUTE_TO_HUMAN.value,
            reason=f"confidence {confidence:.2f} is below this cause's policy threshold "
            f"{policy.confidence_threshold:.2f}.",
            rule_triggered="confidence_below_threshold",
        )

    if proposed_action not in policy.allowed_actions or proposed_action in policy.blocked_actions:
        return PolicyEvaluationResult(
            decision=PolicyDecision.DENIED.value,
            reason=f"'{proposed_action}' is not permitted for cause '{cause}' by policy "
            f"(allowed={policy.allowed_actions}, blocked={policy.blocked_actions}).",
            rule_triggered="action_not_permitted_for_cause",
        )

    if (
        proposed_action in COMMUNICATION_ACTIONS
        and policy.requires_consent
        and consent_status == "opted_out"
    ):
        return PolicyEvaluationResult(
            decision=PolicyDecision.DENIED.value,
            reason="Customer has opted out of communication; cannot send an automated notification.",
            rule_triggered="consent_opted_out",
        )

    if proposed_action in RETRY_ACTIONS and attempt_number >= policy.max_retries:
        return PolicyEvaluationResult(
            decision=PolicyDecision.DENIED.value,
            reason=f"attempt_number {attempt_number} has reached this cause's max_retries "
            f"{policy.max_retries}; further automated retries are denied. Recommend "
            f"proposing STOP_RECOVERY next.",
            rule_triggered="max_retries_exceeded",
        )

    if amount is not None and policy.max_amount is not None and amount > policy.max_amount:
        return PolicyEvaluationResult(
            decision=PolicyDecision.ROUTE_TO_HUMAN.value,
            reason=f"amount {amount} exceeds this cause's policy max_amount {policy.max_amount}; "
            f"routing to human for manual review.",
            rule_triggered="monetary_limit_exceeded",
        )

    if proposed_action in COMMUNICATION_ACTIONS and len(channel_history) >= COMMUNICATION_LIMIT:
        return PolicyEvaluationResult(
            decision=PolicyDecision.ROUTE_TO_HUMAN.value,
            reason=f"Customer has already been contacted via {len(channel_history)} channels "
            f"(limit {COMMUNICATION_LIMIT}); routing to human rather than sending another "
            f"automated notification.",
            rule_triggered="communication_limit_reached",
        )

    return PolicyEvaluationResult(
        decision=PolicyDecision.APPROVED.value,
        reason=f"'{proposed_action}' is permitted for cause '{cause}' and all policy checks passed.",
        rule_triggered="approved",
    )
