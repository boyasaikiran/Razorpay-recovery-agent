"""
Centralized cause -> default action mapping for Phase 8 (Action
Recommendation). Kept as a plain dict (not hardcoded inline) for the
same "centralized and configurable" reason as taxonomy.py and
decline_code_mapping.py.

This is a heuristic starting point per cause, illustrated by the
spec's demo mode section:
    INSUFFICIENT_FUNDS      -> delayed retry
    EXPIRED_CARD             -> payment-link / update-payment-method notification
    CHECKOUT_ABANDONMENT     -> contextual notification
    RISK_BLOCK               -> human review
    LOW CONFIDENCE           -> human review

The action_recommendation_service overrides this mapping when:
  - diagnosis confidence is below threshold -> ESCALATE_TO_HUMAN
  - recovery_probability is very low -> STOP_RECOVERY
regardless of what this table says for the cause.
"""
from app.core.taxonomy import Cause, RecoveryAction

CAUSE_TO_DEFAULT_ACTION: dict[str, str] = {
    Cause.INSUFFICIENT_FUNDS.value: RecoveryAction.DELAYED_RETRY.value,
    Cause.EXPIRED_PAYMENT_METHOD.value: RecoveryAction.CREATE_PAYMENT_LINK.value,
    Cause.TEMPORARY_BANK_FAILURE.value: RecoveryAction.DELAYED_RETRY.value,
    Cause.AUTH_OTP_FAILURE.value: RecoveryAction.RETRY_PAYMENT.value,
    Cause.CHECKOUT_ABANDONMENT.value: RecoveryAction.SEND_NOTIFICATION.value,
    Cause.PRICE_SHOCK_ABANDONMENT.value: RecoveryAction.SEND_NOTIFICATION.value,
    Cause.BANK_DOWNTIME.value: RecoveryAction.DELAYED_RETRY.value,
    Cause.OVERDUE_INVOICE.value: RecoveryAction.SEND_NOTIFICATION.value,
    Cause.RISK_BLOCK.value: RecoveryAction.ESCALATE_TO_HUMAN.value,
    Cause.REPEATED_FAILURE.value: RecoveryAction.ESCALATE_TO_HUMAN.value,
    Cause.UNKNOWN.value: RecoveryAction.ESCALATE_TO_HUMAN.value,
}

# Below this recovery probability, recommend stopping automated
# recovery regardless of cause -- continuing to retry/contact a
# customer who is very unlikely to pay is poor practice and wastes
# communication budget/goodwill. This is a RECOMMENDATION signal, not
# a hard rule -- the deterministic policy engine (Phase 9) is what
# actually enforces stopping rules.
LOW_RECOVERY_PROBABILITY_THRESHOLD = 0.15
