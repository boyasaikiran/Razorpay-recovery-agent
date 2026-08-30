import uuid
from typing import Optional

from sqlalchemy.orm import Session

from app.models.outcome import Outcome


class OutcomeRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(
        self,
        action_id: uuid.UUID,
        recovery_case_id: uuid.UUID,
        status: str,
        recovered_amount: Optional[float] = None,
        currency: Optional[str] = None,
    ) -> Outcome:
        outcome = Outcome(
            action_id=action_id,
            recovery_case_id=recovery_case_id,
            status=status,
            recovered_amount=recovered_amount,
            currency=currency,
        )
        self.db.add(outcome)
        self.db.flush()
        return outcome
