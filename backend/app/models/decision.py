import uuid
from typing import Optional

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.models.mixins import TimestampMixin, UUIDPKMixin


class Decision(Base, UUIDPKMixin, TimestampMixin):
    """
    Records what the agent/LLM proposed AND what the deterministic
    policy engine decided. This is the auditable proof that the LLM
    proposes and the policy engine disposes.
    """

    __tablename__ = "decisions"

    recovery_case_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("recovery_cases.id"), nullable=False
    )

    proposed_action: Mapped[str] = mapped_column(String(50), nullable=False)  # RecoveryAction value
    policy_decision: Mapped[str] = mapped_column(String(50), nullable=False)  # PolicyDecision value
    policy_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    policy_rule_triggered: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    recovery_case: Mapped["RecoveryCase"] = relationship(back_populates="decisions")
    actions: Mapped[list["Action"]] = relationship(back_populates="decision")
