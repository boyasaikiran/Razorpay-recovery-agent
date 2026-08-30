"""
Default per-cause policy configuration, seeded into the `policies` DB
table (app/models/policy.py). These are ILLUSTRATIVE defaults for a
demo/MVP -- not audited real business/compliance thresholds. A real
deployment would tune these per-merchant and per-regulatory-regime.

Kept centralized (not hardcoded in the policy engine) so policy.md
(Phase 16 docs) and the frontend Policy View (Phase 14) can both read
from the same source of truth, and so policies can be changed via DB
update without a code deploy.
"""
from app.core.taxonomy import Cause, RecoveryAction

_ALWAYS_SAFE_ACTIONS = [RecoveryAction.ESCALATE_TO_HUMAN.value, RecoveryAction.STOP_RECOVERY.value]

# Each entry: allowed_actions, blocked_actions, confidence_threshold,
# max_retries, cooldown_seconds, requires_consent, blocks_on_risk_flag,
# max_amount (None = no monetary cap for this cause).
DEFAULT_POLICIES: dict[str, dict] = {
    Cause.INSUFFICIENT_FUNDS.value: {
        "allowed_actions": [RecoveryAction.DELAYED_RETRY.value, RecoveryAction.SEND_NOTIFICATION.value] + _ALWAYS_SAFE_ACTIONS,
        "blocked_actions": [RecoveryAction.RETRY_PAYMENT.value],  # immediate retry pointless for NSF
        "confidence_threshold": 0.5,
        "max_retries": 3,
        "cooldown_seconds": 86400,  # 1 day
        "requires_consent": True,
        "blocks_on_risk_flag": True,
        "max_amount": None,
    },
    Cause.EXPIRED_PAYMENT_METHOD.value: {
        "allowed_actions": [RecoveryAction.CREATE_PAYMENT_LINK.value, RecoveryAction.SEND_NOTIFICATION.value] + _ALWAYS_SAFE_ACTIONS,
        "blocked_actions": [RecoveryAction.RETRY_PAYMENT.value, RecoveryAction.DELAYED_RETRY.value],
        "confidence_threshold": 0.5,
        "max_retries": 2,
        "cooldown_seconds": 172800,
        "requires_consent": True,
        "blocks_on_risk_flag": True,
        "max_amount": None,
    },
    Cause.TEMPORARY_BANK_FAILURE.value: {
        "allowed_actions": [RecoveryAction.DELAYED_RETRY.value, RecoveryAction.RETRY_PAYMENT.value] + _ALWAYS_SAFE_ACTIONS,
        "blocked_actions": [],
        "confidence_threshold": 0.5,
        "max_retries": 4,
        "cooldown_seconds": 3600,
        "requires_consent": False,  # a retry itself doesn't contact the customer
        "blocks_on_risk_flag": True,
        "max_amount": None,
    },
    Cause.AUTH_OTP_FAILURE.value: {
        "allowed_actions": [RecoveryAction.RETRY_PAYMENT.value, RecoveryAction.SEND_NOTIFICATION.value] + _ALWAYS_SAFE_ACTIONS,
        "blocked_actions": [],
        "confidence_threshold": 0.55,
        "max_retries": 3,
        "cooldown_seconds": 1800,
        "requires_consent": True,
        "blocks_on_risk_flag": True,
        "max_amount": None,
    },
    Cause.CHECKOUT_ABANDONMENT.value: {
        "allowed_actions": [RecoveryAction.SEND_NOTIFICATION.value] + _ALWAYS_SAFE_ACTIONS,
        "blocked_actions": [RecoveryAction.RETRY_PAYMENT.value, RecoveryAction.DELAYED_RETRY.value],
        "confidence_threshold": 0.4,
        "max_retries": 2,
        "cooldown_seconds": 43200,
        "requires_consent": True,
        "blocks_on_risk_flag": True,
        "max_amount": None,
    },
    Cause.PRICE_SHOCK_ABANDONMENT.value: {
        "allowed_actions": [RecoveryAction.SEND_NOTIFICATION.value] + _ALWAYS_SAFE_ACTIONS,
        "blocked_actions": [RecoveryAction.RETRY_PAYMENT.value, RecoveryAction.DELAYED_RETRY.value],
        "confidence_threshold": 0.4,
        "max_retries": 1,
        "cooldown_seconds": 86400,
        "requires_consent": True,
        "blocks_on_risk_flag": True,
        "max_amount": None,
    },
    Cause.BANK_DOWNTIME.value: {
        "allowed_actions": [RecoveryAction.DELAYED_RETRY.value] + _ALWAYS_SAFE_ACTIONS,
        "blocked_actions": [RecoveryAction.RETRY_PAYMENT.value],
        "confidence_threshold": 0.5,
        "max_retries": 5,
        "cooldown_seconds": 1800,
        "requires_consent": False,
        "blocks_on_risk_flag": True,
        "max_amount": None,
    },
    Cause.OVERDUE_INVOICE.value: {
        "allowed_actions": [
            RecoveryAction.SEND_NOTIFICATION.value,
            RecoveryAction.LOG_PROMISE_TO_PAY.value,
        ] + _ALWAYS_SAFE_ACTIONS,
        "blocked_actions": [RecoveryAction.RETRY_PAYMENT.value, RecoveryAction.DELAYED_RETRY.value],
        "confidence_threshold": 0.5,
        "max_retries": 5,  # B2B collections tolerate more contact attempts
        "cooldown_seconds": 259200,  # 3 days
        "requires_consent": True,
        "blocks_on_risk_flag": True,
        "max_amount": 1000000.0,  # very large invoices route to human regardless
    },
    Cause.RISK_BLOCK.value: {
        "allowed_actions": list(_ALWAYS_SAFE_ACTIONS),  # only escalate or stop -- ever
        "blocked_actions": [
            RecoveryAction.RETRY_PAYMENT.value,
            RecoveryAction.DELAYED_RETRY.value,
            RecoveryAction.CREATE_PAYMENT_LINK.value,
            RecoveryAction.SEND_NOTIFICATION.value,
            RecoveryAction.LOG_PROMISE_TO_PAY.value,
        ],
        "confidence_threshold": 0.8,
        "max_retries": 0,
        "cooldown_seconds": 0,
        "requires_consent": True,
        "blocks_on_risk_flag": True,
        "max_amount": 0.0,  # no automated monetary action ever
    },
    Cause.REPEATED_FAILURE.value: {
        "allowed_actions": [RecoveryAction.SEND_NOTIFICATION.value] + _ALWAYS_SAFE_ACTIONS,
        "blocked_actions": [RecoveryAction.RETRY_PAYMENT.value, RecoveryAction.DELAYED_RETRY.value],
        "confidence_threshold": 0.6,
        "max_retries": 1,  # already failed repeatedly -- very conservative
        "cooldown_seconds": 86400,
        "requires_consent": True,
        "blocks_on_risk_flag": True,
        "max_amount": None,
    },
    Cause.UNKNOWN.value: {
        "allowed_actions": list(_ALWAYS_SAFE_ACTIONS),
        "blocked_actions": [
            RecoveryAction.RETRY_PAYMENT.value,
            RecoveryAction.DELAYED_RETRY.value,
            RecoveryAction.CREATE_PAYMENT_LINK.value,
            RecoveryAction.SEND_NOTIFICATION.value,
        ],
        "confidence_threshold": 0.9,  # essentially always routes to human
        "max_retries": 0,
        "cooldown_seconds": 0,
        "requires_consent": True,
        "blocks_on_risk_flag": True,
        "max_amount": None,
    },
}

# Sanity check at import time: every action referenced must be a real
# action, every cause a real cause.
from app.core.taxonomy import ALL_ACTIONS, ALL_CAUSES  # noqa: E402

for _cause, _cfg in DEFAULT_POLICIES.items():
    assert _cause in ALL_CAUSES, f"Unknown cause in DEFAULT_POLICIES: {_cause}"
    for _a in _cfg["allowed_actions"] + _cfg["blocked_actions"]:
        assert _a in ALL_ACTIONS, f"Unknown action in DEFAULT_POLICIES[{_cause}]: {_a}"
assert set(DEFAULT_POLICIES.keys()) == set(ALL_CAUSES), "DEFAULT_POLICIES must cover every cause"
