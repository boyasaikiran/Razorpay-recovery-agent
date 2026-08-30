from app.core.decline_code_mapping import RULE_BASED_CONFIDENCE, RULE_BASED_DECLINE_CODE_MAP
from app.core.taxonomy import DiagnosisMethod
from app.services.diagnosis_rule_based import diagnose_rule_based


def test_every_mapped_decline_code_resolves_correctly():
    for decline_code, expected_cause in RULE_BASED_DECLINE_CODE_MAP.items():
        result = diagnose_rule_based(decline_code)
        assert result is not None
        assert result.cause == expected_cause
        assert result.method == DiagnosisMethod.RULE_BASED.value
        assert result.confidence == RULE_BASED_CONFIDENCE


def test_none_decline_code_returns_none():
    assert diagnose_rule_based(None) is None


def test_empty_string_decline_code_returns_none():
    assert diagnose_rule_based("") is None


def test_unrecognized_decline_code_returns_none():
    assert diagnose_rule_based("SOME_CODE_NOT_IN_THE_MAP") is None
