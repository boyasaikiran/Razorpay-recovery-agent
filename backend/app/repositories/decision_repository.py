import uuid

from sqlalchemy.orm import Session

from app.models.decision import Decision


class DecisionRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(
        self,
        recovery_case_id: uuid.UUID,
        proposed_action: str,
        policy_decision: str,
        policy_reason: str = None,
        policy_rule_triggered: str = None,
    ) -> Decision:
        decision = Decision(
            recovery_case_id=recovery_case_id,
            proposed_action=proposed_action,
            policy_decision=policy_decision,
            policy_reason=policy_reason,
            policy_rule_triggered=policy_rule_triggered,
        )
        self.db.add(decision)
        self.db.flush()
        return decision
