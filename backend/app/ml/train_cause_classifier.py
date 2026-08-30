"""
Trains the XGBoost structured cause pre-classifier (Diagnosis Path B).

Used when decline_code is absent or not recognized by the rule-based
mapper (Path A) and there's no rich free-text context to route to the
LLM (Path C) — i.e. structured numeric/categorical signals only.

Trains on FEATURE_CANDIDATE_COLUMNS except free_text_context (that's
Path C's signal) and channel_history (list-valued; reduced to a
derived channel_count feature instead). XGBoost's native categorical
support (enable_categorical=True) handles missing values (NaN) without
imputation — consistent with how Path B actually sees data at
inference (decline_code will typically be missing/None).

Run:
    python -m app.ml.train_cause_classifier
"""
import json
from pathlib import Path

import joblib
import pandas as pd
from sklearn.metrics import accuracy_score, classification_report, f1_score
from sklearn.preprocessing import LabelEncoder
from xgboost import XGBClassifier

from app.core.logging import get_logger
from app.ml.feature_schema import LABEL_COLUMNS

logger = get_logger(__name__)

_DATA_DIR = Path(__file__).resolve().parents[3] / "data"
_MODELS_DIR = _DATA_DIR / "models"

CATEGORICAL_FEATURES = [
    "event_type",
    "currency",
    "payment_method",
    "decline_code",
    "customer_segment",
    "consent_status",
    "network",
    "issuer_bank_code",
    "geo_region",
    "device_type",
]

NUMERIC_FEATURES = [
    "amount",
    "attempt_number",
    "days_since_last_success",
    "customer_lifetime_value",
    "subscription_value",
    "previous_recovery_rate",
    "session_duration_seconds",
    "b2b_invoice_days_overdue",
    "b2b_promise_count",
    "b2b_broken_promise_count",
    "card_age_days",
]

BOOLEAN_FEATURES = ["otp_attempted", "risk_flag", "is_recurring"]

DERIVED_FEATURE_NAME = "channel_count"

MODEL_FEATURE_COLUMNS = CATEGORICAL_FEATURES + NUMERIC_FEATURES + BOOLEAN_FEATURES + [DERIVED_FEATURE_NAME]


def _prepare_features(df: pd.DataFrame, categories: dict[str, list] = None) -> pd.DataFrame:
    """
    categories: optional dict of {column: [known category values]} from
    TRAINING data. Without this, pandas derives category levels from
    whatever subset is passed in — which breaks at inference time
    whenever a categorical column is entirely null in that subset
    (e.g. decline_code, which is null for exactly the rows Path B is
    actually invoked on). Confirmed by reproducing the crash directly:
    XGBoost raises "Categorical feature must have at least one
    category" when a column's category set is empty. Always pass
    `categories` (saved at train time) for inference; leave it None
    only when fitting on the full training set for the first time.
    """
    out = df.copy()

    out[DERIVED_FEATURE_NAME] = out["channel_history"].apply(
        lambda s: len(json.loads(s)) if isinstance(s, str) and s else 0
    )

    for col in CATEGORICAL_FEATURES:
        if categories is not None:
            # Values not in the frozen category set become NaN — this is
            # the desired behavior (an unrecognized decline_code, e.g.,
            # should be treated as "unknown to the model", not crash).
            # Filter explicitly first to avoid a pandas deprecation
            # warning about constructing Categorical with out-of-vocab
            # values (documented to become an error in a future pandas
            # version).
            known = set(categories[col])
            safe_values = out[col].where(out[col].isin(known), other=None)
            out[col] = pd.Categorical(safe_values, categories=categories[col])
        else:
            out[col] = out[col].astype("category")

    for col in NUMERIC_FEATURES:
        # Single-row DataFrames built from a Python dict (real inference
        # path) infer dtype 'object' for a column containing None, even
        # though CSV-read training data infers float64 correctly for the
        # same logical column. XGBoost rejects 'object' dtype outright.
        # Confirmed by reproducing this exact failure via an integration
        # test before adding this line.
        out[col] = pd.to_numeric(out[col], errors="coerce").astype(float)

    for col in BOOLEAN_FEATURES:
        # Same root cause as the numeric fix above: a dict-constructed
        # single row can have None here, and bool(None) / int(None)
        # raises. Missing boolean signal defaults to 0 (False) — a
        # reasonable choice for otp_attempted/risk_flag/is_recurring
        # when genuinely unknown.
        out[col] = pd.to_numeric(out[col], errors="coerce").fillna(0).astype(int)

    return out[MODEL_FEATURE_COLUMNS]


def _extract_categories(df: pd.DataFrame) -> dict[str, list]:
    """Category levels observed in the TRAINING set, to freeze for inference."""
    return {col: sorted(df[col].dropna().unique().tolist()) for col in CATEGORICAL_FEATURES}


def train(train_csv: Path, val_csv: Path, output_dir: Path = _MODELS_DIR, model_version: str = "0.1.0") -> dict:
    train_df = pd.read_csv(train_csv)
    val_df = pd.read_csv(val_csv)

    assert set(MODEL_FEATURE_COLUMNS).isdisjoint(set(LABEL_COLUMNS)), "LEAKAGE in Path B feature set"

    categories = _extract_categories(train_df)
    X_train = _prepare_features(train_df, categories=categories)
    X_val = _prepare_features(val_df, categories=categories)

    label_encoder = LabelEncoder()
    y_train = label_encoder.fit_transform(train_df["ground_truth_cause"])
    y_val = label_encoder.transform(val_df["ground_truth_cause"])

    model = XGBClassifier(
        n_estimators=200,
        max_depth=5,
        learning_rate=0.1,
        objective="multi:softprob",
        num_class=len(label_encoder.classes_),
        enable_categorical=True,
        tree_method="hist",
        eval_metric="mlogloss",
        random_state=42,
    )
    model.fit(X_train, y_train, eval_set=[(X_val, y_val)], verbose=False)

    val_pred = model.predict(X_val)
    val_accuracy = float(accuracy_score(y_val, val_pred))
    val_f1_macro = float(f1_score(y_val, val_pred, average="macro"))
    report = classification_report(
        y_val, val_pred, target_names=label_encoder.classes_, output_dict=True, zero_division=0
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    model_path = output_dir / "cause_classifier.joblib"
    encoder_path = output_dir / "cause_classifier_label_encoder.joblib"
    categories_path = output_dir / "cause_classifier_categories.joblib"
    metadata_path = output_dir / "cause_classifier_metadata.json"

    joblib.dump(model, model_path)
    joblib.dump(label_encoder, encoder_path)
    joblib.dump(categories, categories_path)

    metadata = {
        "model_version": model_version,
        "feature_columns": MODEL_FEATURE_COLUMNS,
        "categorical_features": CATEGORICAL_FEATURES,
        "classes": list(label_encoder.classes_),
        "val_accuracy": val_accuracy,
        "val_f1_macro": val_f1_macro,
        "n_train": len(train_df),
        "n_val": len(val_df),
    }
    with open(metadata_path, "w") as f:
        json.dump(metadata, f, indent=2)

    logger.info(
        "Trained cause_classifier v%s: val_accuracy=%.4f val_f1_macro=%.4f (n_train=%d n_val=%d)",
        model_version, val_accuracy, val_f1_macro, len(train_df), len(val_df),
    )

    return {
        "val_accuracy": val_accuracy,
        "val_f1_macro": val_f1_macro,
        "report": report,
        "model_path": str(model_path),
        "encoder_path": str(encoder_path),
        "categories_path": str(categories_path),
        "metadata_path": str(metadata_path),
    }


if __name__ == "__main__":
    processed_dir = _DATA_DIR / "processed"
    result = train(processed_dir / "train.csv", processed_dir / "val.csv")
    print(f"val_accuracy={result['val_accuracy']:.4f}  val_f1_macro={result['val_f1_macro']:.4f}")
    print(f"Model saved to {result['model_path']}")
