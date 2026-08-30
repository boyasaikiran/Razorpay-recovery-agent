from pydantic import BaseModel, field_validator

from app.core.taxonomy import ALL_ACTIONS


class ActionRecommendation(BaseModel):
    action: str
    reason: str

    @field_validator("action")
    @classmethod
    def validate_action(cls, v: str) -> str:
        if v not in ALL_ACTIONS:
            raise ValueError(f"action must be one of {ALL_ACTIONS}, got '{v}'")
        return v
