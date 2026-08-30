import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.models.mixins import UUIDPKMixin


class AuditLog(Base, UUIDPKMixin):
    """
    Append-oriented audit trail (Phase 12). Deliberately has no
    updated_at / no update path in the repository layer — audit
    records are write-once. An audit write failure must surface loudly
    (Phase 12/adversarial tests), never be silently swallowed.
    """

    __tablename__ = "audit_logs"

    recovery_case_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("recovery_cases.id"), nullable=True
    )

    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    stage: Mapped[str] = mapped_column(String(50), nullable=False)  # AuditStage value
    actor: Mapped[str] = mapped_column(String(100), nullable=False)  # e.g. "system", "llm", "policy_engine"
    decision: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    input_reference: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    output_reference: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    simulation_status: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    recovery_case: Mapped[Optional["RecoveryCase"]] = relationship(back_populates="audit_logs")
