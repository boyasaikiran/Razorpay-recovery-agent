"""
GET /api/v1/models/performance

Reads the REAL metadata files written by app/ml/train_cause_classifier.py
and app/ml/train_recovery_probability.py at training time. Nothing here
is recomputed or fabricated -- if the metadata files don't exist, the
endpoint says so explicitly rather than inventing numbers.
"""
import json
from pathlib import Path
from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()

_MODELS_DIR = Path(__file__).resolve().parents[4] / "data" / "models"


class CauseClassifierPerformance(BaseModel):
    available: bool
    model_version: Optional[str] = None
    classes: Optional[list[str]] = None
    val_accuracy: Optional[float] = None
    val_f1_macro: Optional[float] = None
    n_train: Optional[int] = None
    n_val: Optional[int] = None


class CalibrationCurve(BaseModel):
    prob_true: list[float]
    prob_pred: list[float]


class RecoveryProbabilityPerformance(BaseModel):
    available: bool
    model_version: Optional[str] = None
    val_precision: Optional[float] = None
    val_recall: Optional[float] = None
    val_f1: Optional[float] = None
    val_roc_auc: Optional[float] = None
    calibration_curve: Optional[CalibrationCurve] = None
    feature_importance: Optional[dict[str, float]] = None
    n_train: Optional[int] = None
    n_val: Optional[int] = None


class ModelsPerformanceResponse(BaseModel):
    cause_classifier: CauseClassifierPerformance
    recovery_probability: RecoveryProbabilityPerformance


def _read_json(path: Path) -> Optional[dict]:
    if not path.exists():
        return None
    with open(path) as f:
        return json.load(f)


@router.get("/models/performance", response_model=ModelsPerformanceResponse, tags=["models"])
async def get_models_performance() -> ModelsPerformanceResponse:
    cause_meta = _read_json(_MODELS_DIR / "cause_classifier_metadata.json")
    recovery_meta = _read_json(_MODELS_DIR / "recovery_probability_metadata.json")

    cause_perf = (
        CauseClassifierPerformance(
            available=True,
            model_version=cause_meta["model_version"],
            classes=cause_meta["classes"],
            val_accuracy=cause_meta["val_accuracy"],
            val_f1_macro=cause_meta["val_f1_macro"],
            n_train=cause_meta["n_train"],
            n_val=cause_meta["n_val"],
        )
        if cause_meta
        else CauseClassifierPerformance(available=False)
    )

    recovery_perf = (
        RecoveryProbabilityPerformance(
            available=True,
            model_version=recovery_meta["model_version"],
            val_precision=recovery_meta["val_precision"],
            val_recall=recovery_meta["val_recall"],
            val_f1=recovery_meta["val_f1"],
            val_roc_auc=recovery_meta["val_roc_auc"],
            calibration_curve=CalibrationCurve(**recovery_meta["calibration_curve"]),
            feature_importance=recovery_meta["feature_importance"],
            n_train=recovery_meta["n_train"],
            n_val=recovery_meta["n_val"],
        )
        if recovery_meta
        else RecoveryProbabilityPerformance(available=False)
    )

    return ModelsPerformanceResponse(cause_classifier=cause_perf, recovery_probability=recovery_perf)
