"""
GET /api/v1/policies

Exposes the real seeded policy configuration per cause (Phase 9).
This is what proves to a viewer that the AI cannot bypass policy --
the frontend Policy View renders exactly this data.
"""
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.models.policy import Policy

router = APIRouter()


class PolicyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    cause: str
    allowed_actions: list[str]
    blocked_actions: list[str]
    confidence_threshold: float
    max_retries: int
    cooldown_seconds: int
    requires_consent: bool
    blocks_on_risk_flag: bool
    max_amount: Optional[float]


class PolicyListResponse(BaseModel):
    items: list[PolicyResponse]


@router.get("/policies", response_model=PolicyListResponse, tags=["policies"])
async def list_policies(db: Session = Depends(get_db)) -> PolicyListResponse:
    rows = db.query(Policy).order_by(Policy.cause.asc()).all()
    return PolicyListResponse(items=[PolicyResponse.model_validate(r) for r in rows])
