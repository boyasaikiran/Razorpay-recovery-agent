"""
Request/response schemas for event ingestion (Phase 3).

Every event must carry: event_id, event_type, timestamp, source,
payload, simulation_status, idempotency_key — per spec Phase 3.
"""
import uuid
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator

from app.core.taxonomy import ALL_EVENT_TYPES


class SimulatedEventRequest(BaseModel):
    event_id: str = Field(..., min_length=1, max_length=255)
    event_type: str
    event_timestamp: datetime
    payload: dict[str, Any] = Field(default_factory=dict)
    idempotency_key: str = Field(..., min_length=1, max_length=255)

    merchant_id: uuid.UUID
    customer_external_id: Optional[str] = None

    amount: Optional[float] = None
    currency: Optional[str] = "INR"
    payment_method: Optional[str] = None
    decline_code: Optional[str] = None
    attempt_number: Optional[int] = None

    @field_validator("event_type")
    @classmethod
    def validate_event_type(cls, v: str) -> str:
        if v not in ALL_EVENT_TYPES:
            raise ValueError(
                f"event_type must be one of {ALL_EVENT_TYPES}, got '{v}'"
            )
        return v


class IngestionResponse(BaseModel):
    payment_event_id: uuid.UUID
    recovery_case_id: uuid.UUID
    idempotent_replay: bool
    status: str
