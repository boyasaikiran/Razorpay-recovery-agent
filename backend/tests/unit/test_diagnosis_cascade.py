from app.core.taxonomy import ALL_CAUSES, Cause, DiagnosisMethod
from app.services.diagnosis_service import (
    DIAGNOSIS_CONFIDENCE_THRESHOLD,
    diagnose_from_features,
    requires_human_review,
)
from app.schemas.diagnosis import DiagnosisResult


def test_path_a_takes_precedence_when_decline_code_mapped():
    features = {
        "decline_code": "INSUFFICIENT_FUNDS",
        "free_text_context": "",  # even if present, Path A wins
    }
    result = diagnose_from_features(features)
    assert result.method == DiagnosisMethod.RULE_BASED.value
    assert result.cause == Cause.INSUFFICIENT_FUNDS.value


def test_falls_to_xgboost_when_no_decline_code_and_no_free_text():
    features = {
        "decline_code": None,
        "free_text_context": "",
        "event_type": "checkout_abandoned",
        "amount": 800.0,
        "currency": "INR",
        "payment_method": "none",
        "attempt_number": 1,
        "customer_segment": "consumer",
        "consent_status": "opted_in",
        "channel_history": "[]",
        "geo_region": "South",
        "device_type": "mobile",
        "is_recurring": False,
    }
    result = diagnose_from_features(features)
    assert result.method == DiagnosisMethod.XGBOOST.value
    assert result.cause in ALL_CAUSES


def test_free_text_prefers_llm_but_falls_back_to_xgboost_when_unconfigured():
    """
    LLM_API_KEY is not configured in this environment. Confirms the
    cascade degrades to Path B rather than crashing when Path C is
    preferred (free text present) but unavailable.
    """
    features = {
        "decline_code": None,
        "free_text_context": "customer said the price was a shock and they left",
        "event_type": "checkout_abandoned",
        "amount": 3000.0,
        "currency": "INR",
        "payment_method": "none",
        "attempt_number": 1,
        "customer_segment": "consumer",
        "consent_status": "opted_in",
        "channel_history": "[]",
        "geo_region": "West",
        "device_type": "desktop",
        "is_recurring": False,
    }
    result = diagnose_from_features(features)
    # Falls back to Path B since LLM isn't configured.
    assert result.method == DiagnosisMethod.XGBOOST.value


def test_unrecognized_decline_code_falls_through_to_xgboost():
    features = {
        "decline_code": "SOME_UNRECOGNIZED_CODE",
        "free_text_context": "",
        "event_type": "payment_failed",
        "amount": 500.0,
        "currency": "INR",
        "payment_method": "card",
        "attempt_number": 2,
        "customer_segment": "smb",
        "consent_status": "opted_in",
        "channel_history": "[]",
        "geo_region": "East",
        "device_type": "desktop",
        "is_recurring": True,
    }
    result = diagnose_from_features(features)
    assert result.method == DiagnosisMethod.XGBOOST.value


def test_requires_human_review_below_threshold():
    result = DiagnosisResult(
        cause=Cause.UNKNOWN.value,
        confidence=DIAGNOSIS_CONFIDENCE_THRESHOLD - 0.01,
        reason="low confidence",
        signals=[],
        method=DiagnosisMethod.XGBOOST.value,
    )
    assert requires_human_review(result) is True


def test_does_not_require_human_review_above_threshold():
    result = DiagnosisResult(
        cause=Cause.INSUFFICIENT_FUNDS.value,
        confidence=DIAGNOSIS_CONFIDENCE_THRESHOLD + 0.1,
        reason="high confidence",
        signals=[],
        method=DiagnosisMethod.RULE_BASED.value,
    )
    assert requires_human_review(result) is False
