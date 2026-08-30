"""
Column schema for the synthetic dataset and, later, real ingested
events shaped the same way.

This is the single source of truth for which columns are LABELS
(ground truth, must never be used as model features) vs which are
FEATURE CANDIDATES (available at inference time, before diagnosis).

Phase 6/7 ML training code imports FEATURE_CANDIDATE_COLUMNS from
here rather than hardcoding a column list — that's what makes the
leakage test in backend/tests/unit/test_data_leakage.py meaningful:
it checks the same list the model training code actually uses.
"""

# Identifiers — never used as model features (no predictive meaning,
# and customer_id/merchant_id at near-1-per-row cardinality would leak
# identity, not signal).
ID_COLUMNS = [
    "record_id",
    "merchant_id",
    "customer_id",
]

# Labels — computed only because this is synthetic data with known
# ground truth. In production these become known ONLY after a human
# or the recovery pipeline itself resolves the case. They MUST NOT
# enter the feature set for cause classification (Phase 6) or
# recovery-probability prediction (Phase 7).
LABEL_COLUMNS = [
    "ground_truth_cause",
    "ground_truth_recoverable",
    "ground_truth_recovered_amount",
]

# Timestamp — used for train/val/test split construction and for
# deriving time-aware features (days_since_last_success is already
# precomputed as a feature), but the raw timestamp itself is not fed
# to the model directly.
TIMESTAMP_COLUMNS = [
    "created_at",
]

# Everything else: available at inference time (the moment a
# payment/checkout/invoice event fails), safe to use as model input.
FEATURE_CANDIDATE_COLUMNS = [
    "event_type",
    "amount",
    "currency",
    "payment_method",
    "decline_code",
    "attempt_number",
    "days_since_last_success",
    "customer_lifetime_value",
    "subscription_value",
    "customer_segment",
    "previous_recovery_rate",
    "session_duration_seconds",
    "otp_attempted",
    "free_text_context",
    "b2b_invoice_days_overdue",
    "b2b_promise_count",
    "b2b_broken_promise_count",
    "risk_flag",
    "consent_status",
    "channel_history",
    "card_age_days",
    "network",
    "issuer_bank_code",
    "geo_region",
    "device_type",
    "is_recurring",
]

ALL_COLUMNS = ID_COLUMNS + FEATURE_CANDIDATE_COLUMNS + LABEL_COLUMNS + TIMESTAMP_COLUMNS

# Sanity check executed at import time: catches a maintenance mistake
# (e.g. someone accidentally adding a ground_truth_* column to the
# feature list) immediately rather than silently at training time.
_overlap = set(FEATURE_CANDIDATE_COLUMNS) & set(LABEL_COLUMNS)
if _overlap:
    raise RuntimeError(f"Data leakage in schema definition itself: {_overlap}")
