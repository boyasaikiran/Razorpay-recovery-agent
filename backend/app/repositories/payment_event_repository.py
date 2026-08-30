import uuid
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.models.payment_event import PaymentEvent


class PaymentEventRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_idempotency_key(self, idempotency_key: str) -> Optional[PaymentEvent]:
        return (
            self.db.query(PaymentEvent)
            .filter(PaymentEvent.idempotency_key == idempotency_key)
            .one_or_none()
        )

    def get_by_event_id(self, event_id: str) -> Optional[PaymentEvent]:
        return (
            self.db.query(PaymentEvent)
            .filter(PaymentEvent.event_id == event_id)
            .one_or_none()
        )

    def create(
        self,
        *,
        merchant_id: uuid.UUID,
        customer_id: Optional[uuid.UUID],
        event_id: str,
        event_type: str,
        event_timestamp,
        source: str,
        payload: dict[str, Any],
        simulation_status: bool,
        idempotency_key: str,
        amount: Optional[float] = None,
        currency: Optional[str] = None,
        payment_method: Optional[str] = None,
        decline_code: Optional[str] = None,
        attempt_number: Optional[int] = None,
    ) -> PaymentEvent:
        event = PaymentEvent(
            merchant_id=merchant_id,
            customer_id=customer_id,
            event_id=event_id,
            event_type=event_type,
            event_timestamp=event_timestamp,
            source=source,
            payload=payload,
            simulation_status=simulation_status,
            idempotency_key=idempotency_key,
            amount=amount,
            currency=currency,
            payment_method=payment_method,
            decline_code=decline_code,
            attempt_number=attempt_number,
        )
        self.db.add(event)
        self.db.flush()
        return event
