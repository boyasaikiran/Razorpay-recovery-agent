from app.core.taxonomy import ALL_CAUSES, DiagnosisMethod
from app.ml.cause_classifier_inference import diagnose_xgboost, is_available


def test_model_artifacts_are_available():
    assert is_available() is True


def test_diagnose_with_full_feature_dict():
    features = {
        "event_type": "checkout_abandoned",
        "amount": 1200.0,
        "currency": "INR",
        "payment_method": "none",
        "decline_code": None,
        "attempt_number": 1,
        "days_since_last_success": 10,
        "customer_lifetime_value": 5000.0,
        "subscription_value": None,
        "customer_segment": "consumer",
        "previous_recovery_rate": 0.3,
        "session_duration_seconds": 120,
        "otp_attempted": False,
        "b2b_invoice_days_overdue": 0,
        "b2b_promise_count": 0,
        "b2b_broken_promise_count": 0,
        "risk_flag": False,
        "consent_status": "opted_in",
        "channel_history": "[]",
        "card_age_days": None,
        "network": None,
        "issuer_bank_code": None,
        "geo_region": "North",
        "device_type": "mobile",
        "is_recurring": False,
    }
    result = diagnose_xgboost(features)
    assert result is not None
    assert result.cause in ALL_CAUSES
    assert 0.0 <= result.confidence <= 1.0
    assert result.method == DiagnosisMethod.XGBOOST.value


def test_diagnose_with_all_categorical_fields_null_does_not_crash():
    """
    Regression test: pandas .astype("category") on a single-row (or
    all-null) subset previously derived a zero-category dtype for any
    fully-null categorical column, which crashed XGBoost with
    "Categorical feature must have at least one category." This is
    exactly the shape of input Path B receives in its real invocation
    (decline_code null, often several other fields unknown). Fixed by
    freezing category levels from training data via _extract_categories
    / _prepare_features(categories=...). This test would have failed
    before that fix.
    """
    features = {
        "event_type": "payment_failed",
        "amount": 500.0,
        "currency": "INR",
        "payment_method": None,
        "decline_code": None,
        "attempt_number": 1,
        "days_since_last_success": None,
        "customer_lifetime_value": None,
        "subscription_value": None,
        "customer_segment": None,
        "previous_recovery_rate": None,
        "session_duration_seconds": None,
        "otp_attempted": None,
        "b2b_invoice_days_overdue": None,
        "b2b_promise_count": None,
        "b2b_broken_promise_count": None,
        "risk_flag": None,
        "consent_status": None,
        "channel_history": None,
        "card_age_days": None,
        "network": None,
        "issuer_bank_code": None,
        "geo_region": None,
        "device_type": None,
        "is_recurring": None,
    }
    result = diagnose_xgboost(features)
    assert result is not None
    assert result.cause in ALL_CAUSES


def test_diagnose_with_missing_keys_entirely_does_not_crash():
    # Caller supplies an incomplete dict (e.g. a real ingested event with
    # sparse payload) — diagnose_xgboost must fill in the gaps, not KeyError.
    result = diagnose_xgboost({"event_type": "payment_failed", "amount": 100.0})
    assert result is not None
    assert result.cause in ALL_CAUSES
