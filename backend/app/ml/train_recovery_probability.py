"""
Trains the recovery-probability model (Phase 7).

P(revenue will be recovered | available features)

DESIGN DECISION (stated explicitly, not left implicit): the spec's
suggested feature list includes "failure_type." In a real pipeline,
recovery-probability prediction runs AFTER diagnosis (Phase 6), so the
cause available to this model is the PIPELINE'S DIAGNOSED cause, not
the synthetic dataset's ground_truth_cause. Using ground_truth_cause
directly as a training feature would violate the leakage-protection
invariant established in Phase 5 (app/ml/feature_schema.py) even
though it's technically a different target -- ground_truth_cause is
strongly correlated with ground_truth_recoverable by construction in
the generator, so training on it directly would just let the model
memorize the generator's own lookup table rather than learn from
realistic signal.

Instead, this script RUNS THE ACTUAL Phase 6 diagnosis cascade
(diagnose_from_features) over every training/validation row and uses
that as the "failure_type" feature. This means:
  - Path A cases get the deterministic rule-based cause.
  - Path B cases get the REAL trained XGBoost cause classifier's
    prediction -- including its actual ~62% accuracy on that subset
    (see Phase 6 report) -- not the true label.
  - Path C would apply where free_text_context is present, but since
    LLM_API_KEY isn't configured, those rows fall back to Path B
    automatically (verified behavior from Phase 6's cascade tests).

Other features map to the spec's suggested list with documented
substitutions where our schema doesn't have an exact match:
  failure_count / number_of_attempts -> attempt_number
  payment_method_age                 -> card_age_days
  days_overdue                       -> b2b_invoice_days_overdue
`amount` is added beyond the spec's literal list since deal size is
obviously relevant to recoverability.

Run:
    python -m app.ml.train_recovery_probability
"""
import json
from pathlib import Path

import joblib
import pandas as pd
from sklearn.calibration import calibration_curve
from sklearn.metrics import f1_score, precision_score, recall_score, roc_auc_score
from xgboost import XGBClassifier

from app.core.logging import get_logger
from app.ml.feature_schema import LABEL_COLUMNS
from app.services.diagnosis_service import diagnose_from_features

logger = get_logger(__name__)

_DATA_DIR = Path(__file__).resolve().parents[3] / "data"
_MODELS_DIR = _DATA_DIR / "models"

CATEGORICAL_FEATURES = ["diagnosed_cause", "customer_segment"]

NUMERIC_FEATURES = [
    "amount",
    "customer_lifetime_value",
    "subscription_value",
    "attempt_number",
    "days_since_last_success",
    "card_age_days",
    "previous_recovery_rate",
    "b2b_invoice_days_overdue",
]

MODEL_FEATURE_COLUMNS = CATEGORICAL_FEATURES + NUMERIC_FEATURES


def _row_to_diagnosis_features(row: pd.Series) -> dict:
    def _clean(value):
        # pandas reads empty CSV cells as NaN (a float). NaN is truthy
        # in Python, so `value or default` doesn't catch it — confirmed
        # by reproducing the actual crash this fixes.
        return None if pd.isna(value) else value

    free_text = _clean(row.get("free_text_context"))
    return {
        "decline_code": _clean(row.get("decline_code")),
        "free_text_context": free_text if free_text is not None else "",
        "event_type": _clean(row.get("event_type")),
        "amount": _clean(row.get("amount")),
        "currency": _clean(row.get("currency")),
        "payment_method": _clean(row.get("payment_method")),
        "attempt_number": _clean(row.get("attempt_number")),
        "days_since_last_success": _clean(row.get("days_since_last_success")),
        "customer_lifetime_value": _clean(row.get("customer_lifetime_value")),
        "subscription_value": _clean(row.get("subscription_value")),
        "customer_segment": _clean(row.get("customer_segment")),
        "previous_recovery_rate": _clean(row.get("previous_recovery_rate")),
        "session_duration_seconds": _clean(row.get("session_duration_seconds")),
        "otp_attempted": _clean(row.get("otp_attempted")),
        "b2b_invoice_days_overdue": _clean(row.get("b2b_invoice_days_overdue")),
        "b2b_promise_count": _clean(row.get("b2b_promise_count")),
        "b2b_broken_promise_count": _clean(row.get("b2b_broken_promise_count")),
        "risk_flag": _clean(row.get("risk_flag")),
        "consent_status": _clean(row.get("consent_status")),
        "channel_history": _clean(row.get("channel_history")),
        "card_age_days": _clean(row.get("card_age_days")),
        "network": _clean(row.get("network")),
        "issuer_bank_code": _clean(row.get("issuer_bank_code")),
        "geo_region": _clean(row.get("geo_region")),
        "device_type": _clean(row.get("device_type")),
        "is_recurring": _clean(row.get("is_recurring")),
    }


def _add_diagnosed_cause_column(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    diagnosed_causes = []
    for _, row in out.iterrows():
        features = _row_to_diagnosis_features(row)
        result = diagnose_from_features(features)
        diagnosed_causes.append(result.cause)
    out["diagnosed_cause"] = diagnosed_causes
    return out


def _prepare_features(df: pd.DataFrame, categories: dict = None) -> pd.DataFrame:
    out = df.copy()

    for col in CATEGORICAL_FEATURES:
        if categories is not None:
            known = set(categories[col])
            safe_values = out[col].where(out[col].isin(known), other=None)
            out[col] = pd.Categorical(safe_values, categories=categories[col])
        else:
            out[col] = out[col].astype("category")

    for col in NUMERIC_FEATURES:
        out[col] = pd.to_numeric(out[col], errors="coerce").astype(float)

    return out[MODEL_FEATURE_COLUMNS]


def _extract_categories(df: pd.DataFrame) -> dict:
    return {col: sorted(df[col].dropna().unique().tolist()) for col in CATEGORICAL_FEATURES}


def train(train_csv: Path, val_csv: Path, output_dir: Path = _MODELS_DIR, model_version: str = "0.1.0") -> dict:
    train_df = pd.read_csv(train_csv)
    val_df = pd.read_csv(val_csv)

    assert set(NUMERIC_FEATURES).isdisjoint(set(LABEL_COLUMNS)), "LEAKAGE in Phase 7 numeric feature set"

    logger.info("Running Phase 6 diagnosis cascade over %d train + %d val rows...", len(train_df), len(val_df))
    train_df = _add_diagnosed_cause_column(train_df)
    val_df = _add_diagnosed_cause_column(val_df)

    categories = _extract_categories(train_df)
    X_train = _prepare_features(train_df, categories=categories)
    X_val = _prepare_features(val_df, categories=categories)

    y_train = train_df["ground_truth_recoverable"].astype(int)
    y_val = val_df["ground_truth_recoverable"].astype(int)

    model = XGBClassifier(
        n_estimators=200,
        max_depth=4,
        learning_rate=0.1,
        objective="binary:logistic",
        enable_categorical=True,
        tree_method="hist",
        eval_metric="logloss",
        random_state=42,
    )
    model.fit(X_train, y_train, eval_set=[(X_val, y_val)], verbose=False)

    val_proba = model.predict_proba(X_val)[:, 1]
    val_pred = (val_proba >= 0.5).astype(int)

    precision = float(precision_score(y_val, val_pred, zero_division=0))
    recall = float(recall_score(y_val, val_pred, zero_division=0))
    f1 = float(f1_score(y_val, val_pred, zero_division=0))
    roc_auc = float(roc_auc_score(y_val, val_proba)) if len(set(y_val)) > 1 else None

    prob_true, prob_pred = calibration_curve(y_val, val_proba, n_bins=10, strategy="uniform")

    feature_importance = dict(zip(MODEL_FEATURE_COLUMNS, [float(x) for x in model.feature_importances_]))

    output_dir.mkdir(parents=True, exist_ok=True)
    model_path = output_dir / "recovery_probability.joblib"
    categories_path = output_dir / "recovery_probability_categories.joblib"
    metadata_path = output_dir / "recovery_probability_metadata.json"

    joblib.dump(model, model_path)
    joblib.dump(categories, categories_path)

    metadata = {
        "model_version": model_version,
        "feature_columns": MODEL_FEATURE_COLUMNS,
        "categorical_features": CATEGORICAL_FEATURES,
        "val_precision": precision,
        "val_recall": recall,
        "val_f1": f1,
        "val_roc_auc": roc_auc,
        "calibration_curve": {
            "prob_true": [float(x) for x in prob_true],
            "prob_pred": [float(x) for x in prob_pred],
        },
        "feature_importance": feature_importance,
        "n_train": len(train_df),
        "n_val": len(val_df),
        "positive_rate_train": float(y_train.mean()),
        "positive_rate_val": float(y_val.mean()),
    }
    with open(metadata_path, "w") as f:
        json.dump(metadata, f, indent=2)

    logger.info(
        "Trained recovery_probability v%s: precision=%.4f recall=%.4f f1=%.4f roc_auc=%s",
        model_version, precision, recall, f1, roc_auc,
    )

    return {
        "val_precision": precision,
        "val_recall": recall,
        "val_f1": f1,
        "val_roc_auc": roc_auc,
        "feature_importance": feature_importance,
        "calibration_curve": metadata["calibration_curve"],
        "model_path": str(model_path),
        "categories_path": str(categories_path),
        "metadata_path": str(metadata_path),
    }


if __name__ == "__main__":
    processed_dir = _DATA_DIR / "processed"
    result = train(processed_dir / "train.csv", processed_dir / "val.csv")
    print(f"precision={result['val_precision']:.4f} recall={result['val_recall']:.4f} "
          f"f1={result['val_f1']:.4f} roc_auc={result['val_roc_auc']}")
    print("\nFeature importance:")
    for feat, imp in sorted(result["feature_importance"].items(), key=lambda x: -x[1]):
        print(f"  {feat}: {imp:.4f}")
    print(f"\nModel saved to {result['model_path']}")
