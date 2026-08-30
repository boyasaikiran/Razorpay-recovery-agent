import pytest
from pydantic import ValidationError

from app.core.taxonomy import ALL_CAUSES
from app.llm.cause_classifier import DIAGNOSIS_TOOL_SCHEMA, LLMNotConfiguredError, diagnose_llm
from app.schemas.diagnosis import LLMDiagnosisOutput


def test_llm_raises_not_configured_when_no_api_key(monkeypatch):
    """
    LLM_API_KEY is blank in this environment (no credential was
    provided). Confirms the orchestrator degrades explicitly rather
    than silently returning a fabricated result.
    """
    from app.core.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "llm_api_key", "")

    with pytest.raises(LLMNotConfiguredError):
        diagnose_llm({"free_text_context": "customer said card was expired"})


def test_tool_schema_constrains_cause_to_taxonomy():
    cause_enum = DIAGNOSIS_TOOL_SCHEMA["input_schema"]["properties"]["cause"]["enum"]
    assert set(cause_enum) == set(ALL_CAUSES)


def test_tool_schema_requires_all_fields():
    required = DIAGNOSIS_TOOL_SCHEMA["input_schema"]["required"]
    assert set(required) == {"cause", "confidence", "reason", "signals"}


def test_llm_output_schema_rejects_invalid_cause():
    with pytest.raises(ValidationError):
        LLMDiagnosisOutput(
            cause="not_a_real_cause", confidence=0.8, reason="test", signals=[]
        )


def test_llm_output_schema_rejects_confidence_out_of_range():
    with pytest.raises(ValidationError):
        LLMDiagnosisOutput(
            cause=ALL_CAUSES[0], confidence=1.5, reason="test", signals=[]
        )


def test_llm_output_schema_accepts_valid_output():
    result = LLMDiagnosisOutput(
        cause=ALL_CAUSES[0], confidence=0.75, reason="clear signal", signals=["a", "b"]
    )
    assert result.cause == ALL_CAUSES[0]
