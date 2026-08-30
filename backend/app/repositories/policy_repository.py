from typing import Optional

from sqlalchemy.orm import Session

from app.models.policy import Policy


class PolicyRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_cause(self, cause: str) -> Optional[Policy]:
        return self.db.query(Policy).filter(Policy.cause == cause).one_or_none()
