from typing import Optional

from pydantic import BaseModel, field_validator

from app.core.taxonomy import PolicyDecision


class PolicyEvaluationResult(BaseModel):
    decision: str  # PolicyDecision value
    reason: str
    rule_triggered: Optional[str] = None

    @field_validator("decision")
    @classmethod
    def validate_decision(cls, v: str) -> str:
        valid = {d.value for d in PolicyDecision}
        if v not in valid:
            raise ValueError(f"decision must be one of {valid}, got '{v}'")
        return v
