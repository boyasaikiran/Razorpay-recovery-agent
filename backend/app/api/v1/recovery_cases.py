"""
GET  /api/v1/recovery-cases
GET  /api/v1/recovery-cases/{case_id}
GET  /api/v1/recovery-cases/{case_id}/trace
POST /api/v1/recovery-cases/{case_id}/run
"""
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.agents.agent_loop import run_case_pipeline
from app.core.exceptions import AppError
from app.core.security import require_api_key
from app.database.session import get_db
from app.models.action import Action
from app.models.decision import Decision
from app.models.diagnosis import Diagnosis
from app.models.model_prediction import ModelPrediction
from app.models.outcome import Outcome
from app.repositories.audit_log_repository import AuditLogRepository
from app.repositories.recovery_case_repository import RecoveryCaseRepository
from app.schemas.recovery_case import (
    ActionSummary,
    DecisionSummary,
    DiagnosisSummary,
    ModelPredictionSummary,
    OutcomeSummary,
    RecoveryCaseDetail,
    RecoveryCaseListResponse,
    RecoveryCaseTraceResponse,
    RunCaseResponse,
)

router = APIRouter()


@router.get("/recovery-cases", response_model=RecoveryCaseListResponse, tags=["recovery-cases"])
async def list_recovery_cases(
    status_filter: Optional[str] = Query(None, alias="status"),
    case_type: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> RecoveryCaseListResponse:
    """
    Returns enriched rows (diagnosis/prediction/decision/action/outcome
    inlined) so the dashboard table doesn't need N follow-up requests.
    Implemented as one extra query per relationship per case on the
    current page (bounded by `limit`, default 50) -- an MVP-scale
    simplification. A production version at real scale would use a
    single joined/materialized query instead; stated plainly rather
    than pretending this is production-grade.
    """
    repo = RecoveryCaseRepository(db)
    cases, total = repo.list_filtered(status=status_filter, case_type=case_type, limit=limit, offset=offset)
    items = [_build_detail(db, case) for case in cases]
    return RecoveryCaseListResponse(items=items, total=total, limit=limit, offset=offset)


def _build_detail(db: Session, case) -> RecoveryCaseDetail:
    diagnosis = (
        db.query(Diagnosis).filter_by(recovery_case_id=case.id).order_by(Diagnosis.created_at.desc()).first()
    )
    prediction = (
        db.query(ModelPrediction)
        .filter_by(recovery_case_id=case.id)
        .order_by(ModelPrediction.created_at.desc())
        .first()
    )
    decision = (
        db.query(Decision).filter_by(recovery_case_id=case.id).order_by(Decision.created_at.desc()).first()
    )
    action = db.query(Action).filter_by(recovery_case_id=case.id).order_by(Action.created_at.desc()).first()
    outcome = (
        db.query(Outcome).filter_by(recovery_case_id=case.id).order_by(Outcome.created_at.desc()).first()
        if action
        else None
    )

    return RecoveryCaseDetail(
        id=case.id,
        merchant_id=case.merchant_id,
        customer_id=case.customer_id,
        case_type=case.case_type,
        amount_at_risk=float(case.amount_at_risk) if case.amount_at_risk is not None else None,
        currency=case.currency,
        status=case.status,
        created_at=case.created_at,
        updated_at=case.updated_at,
        diagnosis=DiagnosisSummary.model_validate(diagnosis) if diagnosis else None,
        prediction=ModelPredictionSummary.model_validate(prediction) if prediction else None,
        decision=DecisionSummary.model_validate(decision) if decision else None,
        action=ActionSummary.model_validate(action) if action else None,
        outcome=OutcomeSummary.model_validate(outcome) if outcome else None,
    )


@router.get("/recovery-cases/{case_id}", response_model=RecoveryCaseDetail, tags=["recovery-cases"])
async def get_recovery_case(case_id: uuid.UUID, db: Session = Depends(get_db)) -> RecoveryCaseDetail:
    case = RecoveryCaseRepository(db).get_by_id(case_id)
    if case is None:
        raise AppError(f"Recovery case {case_id} not found.", status_code=status.HTTP_404_NOT_FOUND)
    return _build_detail(db, case)


@router.get(
    "/recovery-cases/{case_id}/trace", response_model=RecoveryCaseTraceResponse, tags=["recovery-cases"]
)
async def get_recovery_case_trace(case_id: uuid.UUID, db: Session = Depends(get_db)) -> RecoveryCaseTraceResponse:
    case = RecoveryCaseRepository(db).get_by_id(case_id)
    if case is None:
        raise AppError(f"Recovery case {case_id} not found.", status_code=status.HTTP_404_NOT_FOUND)

    entries = AuditLogRepository(db).list_for_case(case_id)
    return RecoveryCaseTraceResponse(case_id=case_id, entries=entries)


@router.post(
    "/recovery-cases/{case_id}/run",
    response_model=RunCaseResponse,
    tags=["recovery-cases"],
    dependencies=[Depends(require_api_key)],
)
async def run_recovery_case(case_id: uuid.UUID, db: Session = Depends(get_db)) -> RunCaseResponse:
    case = RecoveryCaseRepository(db).get_by_id(case_id)
    if case is None:
        raise AppError(f"Recovery case {case_id} not found.", status_code=status.HTTP_404_NOT_FOUND)

    result = run_case_pipeline(db, case)

    return RunCaseResponse(
        case_id=case_id,
        diagnosis=DiagnosisSummary.model_validate(result.diagnosis),
        prediction=ModelPredictionSummary.model_validate(result.prediction),
        proposed_action=result.decision.proposed_action,
        policy_decision=result.decision.policy_decision,
        executed=result.executed,
        outcome=OutcomeSummary.model_validate(result.outcome) if result.outcome else None,
    )
