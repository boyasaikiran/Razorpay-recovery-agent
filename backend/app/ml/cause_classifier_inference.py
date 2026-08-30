"""
Diagnosis Path B: XGBoost structured cause pre-classifier — inference.

Loads the artifacts trained by app/ml/train_cause_classifier.py and
exposes a single predict function returning a DiagnosisResult. Model
artifacts are loaded once (module-level singleton) and reused.
"""
from pathlib import Path
from typing import Any, Optional

import joblib
import pandas as pd

from app.core.logging import get_logger
from app.core.taxonomy import DiagnosisMethod
from app.ml.train_cause_classifier import MODEL_FEATURE_COLUMNS, _prepare_features
from app.schemas.diagnosis import DiagnosisResult

logger = get_logger(__name__)

_MODELS_DIR = Path(__file__).resolve().parents[3] / "data" / "models"
_MODEL_PATH = _MODELS_DIR / "cause_classifier.joblib"
_ENCODER_PATH = _MODELS_DIR / "cause_classifier_label_encoder.joblib"
_CATEGORIES_PATH = _MODELS_DIR / "cause_classifier_categories.joblib"

_model = None
_label_encoder = None
_categories = None


class CauseClassifierNotAvailable(Exception):
    """Raised when the trained model artifacts aren't present on disk."""


def _load():
    global _model, _label_encoder, _categories
    if _model is not None:
        return
    if not (_MODEL_PATH.exists() and _ENCODER_PATH.exists() and _CATEGORIES_PATH.exists()):
        raise CauseClassifierNotAvailable(
            f"Cause classifier artifacts not found under {_MODELS_DIR}. "
            f"Run `python -m app.ml.train_cause_classifier` first."
        )
    _model = joblib.load(_MODEL_PATH)
    _label_encoder = joblib.load(_ENCODER_PATH)
    _categories = joblib.load(_CATEGORIES_PATH)
    logger.info("Loaded cause_classifier artifacts from %s", _MODELS_DIR)


def is_available() -> bool:
    try:
        _load()
        return True
    except CauseClassifierNotAvailable:
        return False


def diagnose_xgboost(feature_dict: dict[str, Any]) -> Optional[DiagnosisResult]:
    """
    feature_dict must contain (a subset of) FEATURE_CANDIDATE_COLUMNS
    keys; missing keys are treated as null, which XGBoost's categorical/
    missing-value handling deals with natively. Returns None if the
    model artifacts aren't available (caller should fall back).
    """
    try:
        _load()
    except CauseClassifierNotAvailable as e:
        logger.warning("Path B unavailable: %s", e)
        return None

    row = {col: feature_dict.get(col) for col in MODEL_FEATURE_COLUMNS if col != "channel_count"}
    row["channel_history"] = feature_dict.get("channel_history", "[]") or "[]"
    df = pd.DataFrame([row])

    X = _prepare_features(df, categories=_categories)
    proba = _model.predict_proba(X)[0]
    pred_idx = int(proba.argmax())
    confidence = float(proba[pred_idx])
    cause = str(_label_encoder.inverse_transform([pred_idx])[0])

    return DiagnosisResult(
        cause=cause,
        confidence=confidence,
        reason=f"XGBoost structured classifier predicted '{cause}' with {confidence:.1%} confidence.",
        signals=[f"model_confidence={confidence:.4f}"],
        method=DiagnosisMethod.XGBOOST.value,
    )
