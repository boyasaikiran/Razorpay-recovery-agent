"""
Internal, source-agnostic representation of an ingested event. Both the
/simulate/events endpoint and the /webhooks/razorpay endpoint build one
of these and hand it to the same ingestion core, so idempotency and
case-creation logic exists in exactly one place.
"""
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional


@dataclass
class NormalizedEvent:
    event_id: str
    event_type: str
    event_timestamp: datetime
    source: str  # "simulated" | "razorpay"
    payload: dict[str, Any]
    simulation_status: bool
    idempotency_key: str

    merchant_id: uuid.UUID
    customer_external_id: Optional[str] = None

    amount: Optional[float] = None
    currency: Optional[str] = None
    payment_method: Optional[str] = None
    decline_code: Optional[str] = None
    attempt_number: Optional[int] = None
