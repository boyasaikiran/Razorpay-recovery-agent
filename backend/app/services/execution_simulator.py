"""
Execution simulator (Phase 11).

Only ever runs against Action rows that already exist -- which, per
Phase 10's structural guard, can only exist for APPROVED decisions.
There is therefore no DENIED/ROUTE_TO_HUMAN path through this module;
those cases are fully represented by their Decision row's
policy_decision field (populated regardless of approval) and never
reach here.

SIMULATION LOGIC: outcomes for money/contact-moving actions
(RETRY_PAYMENT, DELAYED_RETRY, CREATE_PAYMENT_LINK, SEND_NOTIFICATION)
are stochastic, weighted by the case's ACTUAL recovery_probability
from Phase 7's model -- so a case rated 80% likely-to-recover succeeds
roughly 80% of the time in simulation, not at a fixed rate disconnected
from the prediction. This makes Phase 13's evaluation meaningful.

ESCALATE_TO_HUMAN and LOG_PROMISE_TO_PAY resolve to HUMAN_REVIEW
(follow-up required, no money recovered yet in simulation).
STOP_RECOVERY resolves to STOPPED.

CREATE_PAYMENT_LINK actually calls the Phase 4 RazorpayClientWrapper,
which in SIMULATED_RAZORPAY mode returns a locally-generated stand-in
clearly marked simulated: true -- never presented as a real link.
"""
import random
from typing import Optional

from sqlalchemy.orm import Session

from app.core.taxonomy import AuditStage, OutcomeStatus, RecoveryAction
from app.models.action import Action
from app.repositories.audit_log_repository import AuditLogRepository
from app.repositories.outcome_repository import OutcomeRepository
from app.services.razorpay_client import get_razorpay_client

_STOCHASTIC_ACTIONS = {
    RecoveryAction.RETRY_PAYMENT.value,
    RecoveryAction.DELAYED_RETRY.value,
    RecoveryAction.CREATE_PAYMENT_LINK.value,
    RecoveryAction.SEND_NOTIFICATION.value,
}

_DETERMINISTIC_OUTCOMES = {
    RecoveryAction.ESCALATE_TO_HUMAN.value: OutcomeStatus.HUMAN_REVIEW.value,
    RecoveryAction.LOG_PROMISE_TO_PAY.value: OutcomeStatus.HUMAN_REVIEW.value,
    RecoveryAction.STOP_RECOVERY.value: OutcomeStatus.STOPPED.value,
}


def simulate_execution(
    db: Session,
    action: Action,
    amount_at_risk: Optional[float],
    currency: Optional[str],
    recovery_probability: Optional[float],
    rng: Optional[random.Random] = None,
):
    """
    Simulates the outcome of an already-executed (Phase 10-approved)
    Action, persists an Outcome row, updates the Action's status, and
    writes the OUTCOME_RECORDED audit entry.

    rng: injectable random source for deterministic testing. Defaults
    to a fresh random.Random() for real demo runs.
    """
    rng = rng or random.Random()
    outcome_repo = OutcomeRepository(db)
    audit_repo = AuditLogRepository(db)

    # DB Numeric columns map to Decimal in Python; Decimal * float
    # raises TypeError. Coerce once, up front. Confirmed by reproducing
    # the actual crash via the real pipeline before adding this line.
    amount_at_risk = float(amount_at_risk) if amount_at_risk is not None else 0.0

    action_type = action.action_type

    if action_type in _DETERMINISTIC_OUTCOMES:
        status = _DETERMINISTIC_OUTCOMES[action_type]
        recovered_amount = 0.0
        detail = f"'{action_type}' resolved deterministically to '{status}' (no stochastic element)."
    elif action_type in _STOCHASTIC_ACTIONS:
        p_success = recovery_probability if recovery_probability is not None else 0.3
        succeeded = rng.random() < p_success

        detail_link = ""
        if action_type == RecoveryAction.CREATE_PAYMENT_LINK.value:
            client = get_razorpay_client()
            link = client.create_payment_link(
                amount=int((amount_at_risk or 0) * 100),
                currency=currency or "INR",
                description=f"Recovery payment link for case {action.recovery_case_id}",
            )
            detail_link = f" [SIMULATED payment link: {link.get('short_url')}]"

        if succeeded:
            status = OutcomeStatus.SUCCESS.value
            recovered_amount = round((amount_at_risk or 0) * rng.uniform(0.85, 1.0), 2)
            detail = f"'{action_type}' simulated SUCCESS (p={p_success:.2f}).{detail_link}"
        else:
            status = OutcomeStatus.FAILURE.value
            recovered_amount = 0.0
            detail = f"'{action_type}' simulated FAILURE (p={p_success:.2f})."
    else:
        status = OutcomeStatus.FAILURE.value
        recovered_amount = 0.0
        detail = f"Unrecognized action_type '{action_type}' -- defaulted to FAILURE."

    outcome = outcome_repo.create(
        action_id=action.id,
        recovery_case_id=action.recovery_case_id,
        status=status,
        recovered_amount=recovered_amount,
        currency=currency,
    )

    action.status = status
    db.flush()

    audit_repo.write(
        stage=AuditStage.OUTCOME_RECORDED.value,
        actor="execution_simulator",
        recovery_case_id=action.recovery_case_id,
        decision=status,
        reason=detail,
        output_reference=str(outcome.id),
        simulation_status=True,
    )

    db.commit()
    return outcome
