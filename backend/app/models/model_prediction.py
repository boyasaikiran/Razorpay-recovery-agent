import uuid
from typing import Optional

from sqlalchemy import Float, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.models.mixins import TimestampMixin, UUIDPKMixin


class ModelPrediction(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "model_predictions"

    recovery_case_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("recovery_cases.id"), nullable=False
    )

    model_name: Mapped[str] = mapped_column(String(100), nullable=False)
    model_version: Mapped[str] = mapped_column(String(50), nullable=False)
    recovery_probability: Mapped[float] = mapped_column(Float, nullable=False)
    feature_snapshot: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    recovery_case: Mapped["RecoveryCase"] = relationship(back_populates="model_predictions")
