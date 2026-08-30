import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.models.mixins import TimestampMixin, UUIDPKMixin


class Action(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "actions"

    decision_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("decisions.id"), nullable=False
    )
    recovery_case_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("recovery_cases.id"), nullable=False
    )

    action_type: Mapped[str] = mapped_column(String(50), nullable=False)  # RecoveryAction value
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="pending")
    simulated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    executed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    decision: Mapped["Decision"] = relationship(back_populates="actions")
    outcome: Mapped[Optional["Outcome"]] = relationship(back_populates="action", uselist=False)
