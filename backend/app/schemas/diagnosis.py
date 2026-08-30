"""
Diagnosis schemas.

DiagnosisResult is the unified output of ANY of the three diagnosis
paths (rule-based, xgboost, llm) so the orchestrator and downstream
phases (recovery probability, action recommendation, policy) don't
need to care which path produced it.

LLMDiagnosisOutput is the strict schema the LLM's structured tool-use
output is validated against (Phase 6 Path C requirement: "Validate
using Pydantic. If malformed: Retry once. If still malformed:
Fallback.").
"""
from pydantic import BaseModel, Field, field_validator

from app.core.taxonomy import ALL_CAUSES, DiagnosisMethod


class DiagnosisResult(BaseModel):
    cause: str
    confidence: float = Field(..., ge=0.0, le=1.0)
    reason: str
    signals: list[str] = Field(default_factory=list)
    method: str  # DiagnosisMethod value

    @field_validator("cause")
    @classmethod
    def validate_cause(cls, v: str) -> str:
        if v not in ALL_CAUSES:
            raise ValueError(f"cause must be one of {ALL_CAUSES}, got '{v}'")
        return v

    @field_validator("method")
    @classmethod
    def validate_method(cls, v: str) -> str:
        valid = {m.value for m in DiagnosisMethod} | {"llm_fallback"}
        if v not in valid:
            raise ValueError(f"method must be one of {valid}, got '{v}'")
        return v


class LLMDiagnosisOutput(BaseModel):
    """
    The exact shape the LLM must return via structured tool-use output.
    Schema per spec:
        { "cause": "...", "confidence": 0.0, "reason": "...", "signals": [] }
    """

    cause: str
    confidence: float = Field(..., ge=0.0, le=1.0)
    reason: str = Field(..., max_length=500)
    signals: list[str] = Field(default_factory=list)

    @field_validator("cause")
    @classmethod
    def validate_cause(cls, v: str) -> str:
        if v not in ALL_CAUSES:
            raise ValueError(f"cause must be one of {ALL_CAUSES}, got '{v}'")
        return v
