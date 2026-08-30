"""
GET /api/v1/metrics

Aggregates real data currently in the database: revenue at risk,
revenue recovered, recovery rate, automation/escalation rates, cause
distribution, recovery by cause, recovery by payment method, active
case count. Distinct from the Evaluation Engine (Phase 13), which
runs a batch backtest against synthetic data with a baseline
comparison -- this endpoint reflects whatever cases actually exist in
the database right now (empty until cases are ingested/run).
"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.taxonomy import OutcomeStatus, PolicyDecision, RecoveryCaseStatus
from app.database.session import get_db
from app.models.decision import Decision
from app.models.diagnosis import Diagnosis
from app.models.outcome import Outcome
from app.models.payment_event import PaymentEvent
from app.models.recovery_case import RecoveryCase
from app.repositories.policy_repository import PolicyRepository

router = APIRouter()


class CauseCount(BaseModel):
    cause: str
    count: int


class CauseRecovery(BaseModel):
    cause: str
    at_risk_amount: float
    recovered_amount: float


class PaymentMethodRecovery(BaseModel):
    payment_method: str
    recovered_amount: float


class MetricsResponse(BaseModel):
    revenue_at_risk: float
    revenue_recovered: float
    recovery_rate: float
    automation_rate: float
    escalation_rate: float
    policy_violations: int
    failed_recoveries: int
    active_cases: int
    total_cases: int
    cause_distribution: list[CauseCount]
    recovery_by_cause: list[CauseRecovery]
    recovery_by_payment_method: list[PaymentMethodRecovery]


@router.get("/metrics", response_model=MetricsResponse, tags=["metrics"])
async def get_metrics(db: Session = Depends(get_db)) -> MetricsResponse:
    total_cases = db.query(RecoveryCase).count()
    revenue_at_risk = db.query(func.coalesce(func.sum(RecoveryCase.amount_at_risk), 0.0)).scalar() or 0.0
    revenue_recovered = (
        db.query(func.coalesce(func.sum(Outcome.recovered_amount), 0.0))
        .filter(Outcome.status == OutcomeStatus.SUCCESS.value)
        .scalar()
        or 0.0
    )
    recovery_rate = float(revenue_recovered) / float(revenue_at_risk) if revenue_at_risk else 0.0

    n_decisions = db.query(Decision).count()
    n_approved = db.query(Decision).filter(Decision.policy_decision == PolicyDecision.APPROVED.value).count()
    n_route_to_human = (
        db.query(Decision).filter(Decision.policy_decision == PolicyDecision.ROUTE_TO_HUMAN.value).count()
    )
    automation_rate = n_approved / n_decisions if n_decisions else 0.0
    escalation_rate = n_route_to_human / n_decisions if n_decisions else 0.0

    active_cases = db.query(RecoveryCase).filter(RecoveryCase.status == RecoveryCaseStatus.OPEN.value).count()
    failed_recoveries = db.query(Outcome).filter(Outcome.status == OutcomeStatus.FAILURE.value).count()

    policy_violations = 0
    approved_decisions = (
        db.query(Decision, Diagnosis.cause)
        .join(Diagnosis, Diagnosis.recovery_case_id == Decision.recovery_case_id)
        .filter(Decision.policy_decision == PolicyDecision.APPROVED.value)
        .all()
    )
    policy_repo = PolicyRepository(db)
    policy_cache: dict = {}
    for decision, cause in approved_decisions:
        policy = policy_cache.get(cause)
        if policy is None:
            policy = policy_repo.get_by_cause(cause)
            policy_cache[cause] = policy
        if policy is not None:
            if (
                decision.proposed_action not in policy.allowed_actions
                or decision.proposed_action in policy.blocked_actions
            ):
                policy_violations += 1

    cause_rows = db.query(Diagnosis.cause, func.count(Diagnosis.id)).group_by(Diagnosis.cause).all()
    cause_distribution = [CauseCount(cause=c, count=n) for c, n in cause_rows]

    recovery_by_cause_rows = (
        db.query(
            Diagnosis.cause,
            func.coalesce(func.sum(RecoveryCase.amount_at_risk), 0.0),
            func.coalesce(func.sum(Outcome.recovered_amount), 0.0),
        )
        .join(RecoveryCase, RecoveryCase.id == Diagnosis.recovery_case_id)
        .outerjoin(Outcome, Outcome.recovery_case_id == RecoveryCase.id)
        .group_by(Diagnosis.cause)
        .all()
    )
    recovery_by_cause = [
        CauseRecovery(cause=c, at_risk_amount=float(at_risk), recovered_amount=float(recovered))
        for c, at_risk, recovered in recovery_by_cause_rows
    ]

    payment_method_rows = (
        db.query(PaymentEvent.payment_method, func.coalesce(func.sum(Outcome.recovered_amount), 0.0))
        .join(RecoveryCase, RecoveryCase.payment_event_id == PaymentEvent.id)
        .outerjoin(Outcome, Outcome.recovery_case_id == RecoveryCase.id)
        .filter(PaymentEvent.payment_method.isnot(None))
        .group_by(PaymentEvent.payment_method)
        .all()
    )
    recovery_by_payment_method = [
        PaymentMethodRecovery(payment_method=pm, recovered_amount=float(amt)) for pm, amt in payment_method_rows
    ]

    return MetricsResponse(
        revenue_at_risk=float(revenue_at_risk),
        revenue_recovered=float(revenue_recovered),
        recovery_rate=recovery_rate,
        automation_rate=automation_rate,
        escalation_rate=escalation_rate,
        policy_violations=policy_violations,
        failed_recoveries=failed_recoveries,
        active_cases=active_cases,
        total_cases=total_cases,
        cause_distribution=cause_distribution,
        recovery_by_cause=recovery_by_cause,
        recovery_by_payment_method=recovery_by_payment_method,
    )
