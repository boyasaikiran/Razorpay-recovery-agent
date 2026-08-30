"""
Centralized taxonomy definitions.

The spec requires cause/action/event taxonomies to remain "centralized
and configurable." Everything here is the single source of truth —
diagnosis (Phase 6), action recommendation (Phase 8), the policy engine
(Phase 9), and the frontend policy view all read from this module
instead of hardcoding strings elsewhere.

These are intentionally plain Python constants (not DB-native enums):
the DB columns that store them are `String`, validated at the
application/Pydantic layer. This means the taxonomy can be extended
without an Alembic migration.
"""
from enum import Enum


class EventType(str, Enum):
    SUBSCRIPTION_RENEWAL_FAILED = "subscription_renewal_failed"
    PAYMENT_FAILED = "payment_failed"
    CHECKOUT_ABANDONED = "checkout_abandoned"
    INVOICE_OVERDUE = "invoice_overdue"


class Cause(str, Enum):
    INSUFFICIENT_FUNDS = "insufficient_funds"
    EXPIRED_PAYMENT_METHOD = "expired_payment_method"
    TEMPORARY_BANK_FAILURE = "temporary_bank_failure"
    AUTH_OTP_FAILURE = "auth_otp_failure"
    CHECKOUT_ABANDONMENT = "checkout_abandonment"
    PRICE_SHOCK_ABANDONMENT = "price_shock_abandonment"
    BANK_DOWNTIME = "bank_downtime"
    OVERDUE_INVOICE = "overdue_invoice"
    RISK_BLOCK = "risk_block"
    REPEATED_FAILURE = "repeated_failure"
    UNKNOWN = "unknown"


class DiagnosisMethod(str, Enum):
    RULE_BASED = "rule_based"          # Path A
    XGBOOST = "xgboost"                # Path B
    LLM = "llm"                        # Path C


class RecoveryAction(str, Enum):
    RETRY_PAYMENT = "RETRY_PAYMENT"
    DELAYED_RETRY = "DELAYED_RETRY"
    CREATE_PAYMENT_LINK = "CREATE_PAYMENT_LINK"
    SEND_NOTIFICATION = "SEND_NOTIFICATION"
    LOG_PROMISE_TO_PAY = "LOG_PROMISE_TO_PAY"
    ESCALATE_TO_HUMAN = "ESCALATE_TO_HUMAN"
    STOP_RECOVERY = "STOP_RECOVERY"


class PolicyDecision(str, Enum):
    APPROVED = "APPROVED"
    DENIED = "DENIED"
    ROUTE_TO_HUMAN = "ROUTE_TO_HUMAN"


class OutcomeStatus(str, Enum):
    SUCCESS = "success"
    FAILURE = "failure"
    HUMAN_REVIEW = "human_review"
    STOPPED = "stopped"
    POLICY_DENIED = "policy_denied"


class AuditStage(str, Enum):
    EVENT_RECEIVED = "EVENT_RECEIVED"
    CONTEXT_RETRIEVED = "CONTEXT_RETRIEVED"
    CAUSE_CLASSIFIED = "CAUSE_CLASSIFIED"
    RECOVERY_PREDICTED = "RECOVERY_PREDICTED"
    ACTION_PROPOSED = "ACTION_PROPOSED"
    POLICY_CHECKED = "POLICY_CHECKED"
    ACTION_EXECUTED = "ACTION_EXECUTED"
    OUTCOME_RECORDED = "OUTCOME_RECORDED"
    HUMAN_ESCALATED = "HUMAN_ESCALATED"


class ConsentStatus(str, Enum):
    OPTED_IN = "opted_in"
    OPTED_OUT = "opted_out"
    UNKNOWN = "unknown"


class RecoveryCaseStatus(str, Enum):
    OPEN = "open"
    DIAGNOSED = "diagnosed"
    DECIDED = "decided"
    EXECUTED = "executed"
    CLOSED = "closed"


ALL_EVENT_TYPES = [e.value for e in EventType]
ALL_CAUSES = [c.value for c in Cause]
ALL_ACTIONS = [a.value for a in RecoveryAction]
