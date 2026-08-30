"""
Recovery-probability inference (Phase 7).

Loads the artifacts trained by app/ml/train_recovery_probability.py.
Takes the SAME feature dict shape diagnosis uses, PLUS the already-
diagnosed cause (from Phase 6's DiagnosisResult) as an explicit
argument -- this function does not run diagnosis itself, since in the
real pipeline diagnosis has already happened by this point.
"""
from pathlib import Path
from typing import Any, Optional

import joblib
import pandas as pd

from app.core.logging import get_logger
from app.ml.train_recovery_probability import MODEL_FEATURE_COLUMNS, _prepare_features

logger = get_logger(__name__)

_MODELS_DIR = Path(__file__).resolve().parents[3] / "data" / "models"
_MODEL_PATH = _MODELS_DIR / "recovery_probability.joblib"
_CATEGORIES_PATH = _MODELS_DIR / "recovery_probability_categories.joblib"

_model = None
_categories = None


class RecoveryProbabilityModelNotAvailable(Exception):
    pass


def _load():
    global _model, _categories
    if _model is not None:
        return
    if not (_MODEL_PATH.exists() and _CATEGORIES_PATH.exists()):
        raise RecoveryProbabilityModelNotAvailable(
            f"Recovery probability model not found under {_MODELS_DIR}. "
            f"Run `python -m app.ml.train_recovery_probability` first."
        )
    _model = joblib.load(_MODEL_PATH)
    _categories = joblib.load(_CATEGORIES_PATH)
    logger.info("Loaded recovery_probability artifacts from %s", _MODELS_DIR)


def is_available() -> bool:
    try:
        _load()
        return True
    except RecoveryProbabilityModelNotAvailable:
        return False


def predict_recovery_probability(feature_dict: dict[str, Any], diagnosed_cause: str) -> Optional[float]:
    """
    Returns P(revenue will be recovered) in [0, 1], or None if the
    model artifacts aren't available (caller should handle gracefully
    -- this probability feeds the policy layer, it is NOT itself a
    final decision, per spec).
    """
    try:
        _load()
    except RecoveryProbabilityModelNotAvailable as e:
        logger.warning("Recovery probability model unavailable: %s", e)
        return None

    row = {
        "diagnosed_cause": diagnosed_cause,
        "customer_segment": feature_dict.get("customer_segment"),
        "amount": feature_dict.get("amount"),
        "customer_lifetime_value": feature_dict.get("customer_lifetime_value"),
        "subscription_value": feature_dict.get("subscription_value"),
        "attempt_number": feature_dict.get("attempt_number"),
        "days_since_last_success": feature_dict.get("days_since_last_success"),
        "card_age_days": feature_dict.get("card_age_days"),
        "previous_recovery_rate": feature_dict.get("previous_recovery_rate"),
        "b2b_invoice_days_overdue": feature_dict.get("b2b_invoice_days_overdue"),
    }
    df = pd.DataFrame([row])
    X = _prepare_features(df, categories=_categories)
    proba = _model.predict_proba(X)[0][1]
    return float(proba)
