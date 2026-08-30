import uuid
from typing import Optional

from sqlalchemy import and_
from sqlalchemy.orm import Session

from app.core.taxonomy import RecoveryCaseStatus
from app.models.recovery_case import RecoveryCase


class RecoveryCaseRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_payment_event_id(self, payment_event_id: uuid.UUID) -> Optional[RecoveryCase]:
        return (
            self.db.query(RecoveryCase)
            .filter(RecoveryCase.payment_event_id == payment_event_id)
            .one_or_none()
        )

    def get_by_id(self, case_id: uuid.UUID) -> Optional[RecoveryCase]:
        return self.db.query(RecoveryCase).filter(RecoveryCase.id == case_id).one_or_none()

    def list_filtered(
        self,
        *,
        status: Optional[str] = None,
        case_type: Optional[str] = None,
        merchant_id: Optional[uuid.UUID] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[RecoveryCase], int]:
        query = self.db.query(RecoveryCase)
        filters = []
        if status is not None:
            filters.append(RecoveryCase.status == status)
        if case_type is not None:
            filters.append(RecoveryCase.case_type == case_type)
        if merchant_id is not None:
            filters.append(RecoveryCase.merchant_id == merchant_id)
        if filters:
            query = query.filter(and_(*filters))

        total = query.count()
        items = (
            query.order_by(RecoveryCase.created_at.desc())
            .limit(limit)
            .offset(offset)
            .all()
        )
        return items, total

    def create(
        self,
        *,
        merchant_id: uuid.UUID,
        customer_id: Optional[uuid.UUID],
        payment_event_id: uuid.UUID,
        case_type: str,
        amount_at_risk: Optional[float] = None,
        currency: Optional[str] = None,
    ) -> RecoveryCase:
        case = RecoveryCase(
            merchant_id=merchant_id,
            customer_id=customer_id,
            payment_event_id=payment_event_id,
            case_type=case_type,
            amount_at_risk=amount_at_risk,
            currency=currency,
            status=RecoveryCaseStatus.OPEN.value,
        )
        self.db.add(case)
        self.db.flush()
        return case
