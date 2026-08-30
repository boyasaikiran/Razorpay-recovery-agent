import uuid
from typing import Optional

from sqlalchemy import Float, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.models.mixins import TimestampMixin, UUIDPKMixin


class Diagnosis(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "diagnoses"

    recovery_case_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("recovery_cases.id"), nullable=False
    )

    cause: Mapped[str] = mapped_column(String(100), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    method: Mapped[str] = mapped_column(String(50), nullable=False)  # rule_based | xgboost | llm
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    signals: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)
    raw_llm_output: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    recovery_case: Mapped["RecoveryCase"] = relationship(back_populates="diagnoses")
