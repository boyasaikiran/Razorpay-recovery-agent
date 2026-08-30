"""
POST /api/v1/evaluation/run

Defaults to a modest n_records (100) to stay responsive over HTTP --
the full 600-record report used for reporting real numbers is
generated via `python -m app.evaluation.run_evaluation`.
"""
from pathlib import Path

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.rate_limit import rate_limit_evaluation
from app.core.security import require_api_key
from app.database.session import get_db
from app.evaluation.run_evaluation import run_evaluation
from app.evaluation.schemas import EvaluationReport

router = APIRouter()

_EVAL_CSV_PATH = Path(__file__).resolve().parents[4] / "data" / "processed" / "evaluation.csv"


@router.post(
    "/evaluation/run",
    response_model=EvaluationReport,
    tags=["evaluation"],
    dependencies=[Depends(require_api_key), Depends(rate_limit_evaluation)],
)
async def run_evaluation_endpoint(
    n_records: int = Query(100, ge=1, le=600, description="Number of evaluation records to run (max 600)"),
    db: Session = Depends(get_db),
) -> EvaluationReport:
    return run_evaluation(db, _EVAL_CSV_PATH, n_records=n_records, cleanup=True)
