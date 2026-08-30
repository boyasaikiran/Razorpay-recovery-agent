from app.ml.recovery_probability_inference import is_available, predict_recovery_probability


def test_model_artifacts_are_available():
    assert is_available() is True


def test_predict_returns_probability_in_valid_range():
    features = {
        "customer_segment": "consumer",
        "amount": 2000.0,
        "customer_lifetime_value": 8000.0,
        "subscription_value": None,
        "attempt_number": 1,
        "days_since_last_success": 15,
        "card_age_days": 400,
        "previous_recovery_rate": 0.4,
        "b2b_invoice_days_overdue": 0,
    }
    probability = predict_recovery_probability(features, diagnosed_cause="temporary_bank_failure")
    assert probability is not None
    assert 0.0 <= probability <= 1.0


def test_predict_with_all_none_features_does_not_crash():
    features = {k: None for k in [
        "customer_segment", "amount", "customer_lifetime_value", "subscription_value",
        "attempt_number", "days_since_last_success", "card_age_days",
        "previous_recovery_rate", "b2b_invoice_days_overdue",
    ]}
    probability = predict_recovery_probability(features, diagnosed_cause="unknown")
    assert probability is not None
    assert 0.0 <= probability <= 1.0


def test_high_risk_cause_predicts_lower_than_recoverable_cause():
    """
    Sanity check consistent with the generator's design: risk_block
    should predict meaningfully lower recovery probability than
    temporary_bank_failure, all else equal.
    """
    base_features = {
        "customer_segment": "consumer",
        "amount": 1500.0,
        "customer_lifetime_value": 6000.0,
        "subscription_value": None,
        "attempt_number": 1,
        "days_since_last_success": 20,
        "card_age_days": 300,
        "previous_recovery_rate": 0.3,
        "b2b_invoice_days_overdue": 0,
    }
    risk_block_proba = predict_recovery_probability(base_features, diagnosed_cause="risk_block")
    bank_failure_proba = predict_recovery_probability(base_features, diagnosed_cause="temporary_bank_failure")

    assert risk_block_proba < bank_failure_proba
