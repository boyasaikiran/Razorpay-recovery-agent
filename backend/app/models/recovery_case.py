import uuid
from typing import Optional

from sqlalchemy import ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.taxonomy import RecoveryCaseStatus
from app.database.base import Base
from app.models.mixins import TimestampMixin, UUIDPKMixin, UpdatedAtMixin


class RecoveryCase(Base, UUIDPKMixin, TimestampMixin, UpdatedAtMixin):
    """
    The central pipeline entity. One recovery case is created per
    at-risk payment_event and threads through diagnosis -> prediction
    -> decision -> action -> outcome.
    """

    __tablename__ = "recovery_cases"

    merchant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("merchants.id"), nullable=False
    )
    customer_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("customers.id"), nullable=True
    )
    payment_event_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("payment_events.id"), nullable=False, unique=True
    )

    case_type: Mapped[str] = mapped_column(String(50), nullable=False)  # matches EventType
    amount_at_risk: Mapped[Optional[float]] = mapped_column(Numeric(14, 2), nullable=True)
    currency: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, default=RecoveryCaseStatus.OPEN.value
    )

    payment_event: Mapped["PaymentEvent"] = relationship(back_populates="recovery_case")
    diagnoses: Mapped[list["Diagnosis"]] = relationship(back_populates="recovery_case")
    model_predictions: Mapped[list["ModelPrediction"]] = relationship(back_populates="recovery_case")
    decisions: Mapped[list["Decision"]] = relationship(back_populates="recovery_case")
    audit_logs: Mapped[list["AuditLog"]] = relationship(back_populates="recovery_case")
