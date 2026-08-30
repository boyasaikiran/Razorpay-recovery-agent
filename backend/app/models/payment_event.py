import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.models.mixins import TimestampMixin, UUIDPKMixin


class PaymentEvent(Base, UUIDPKMixin, TimestampMixin):
    """
    Raw ingested event (Phase 3). event_id is the external/source ID;
    idempotency_key is what protects against duplicate processing.
    """

    __tablename__ = "payment_events"

    merchant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("merchants.id"), nullable=False
    )
    customer_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("customers.id"), nullable=True
    )

    event_id: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    event_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    source: Mapped[str] = mapped_column(String(50), nullable=False)  # "razorpay" | "simulated"
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)

    simulation_status: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)

    amount: Mapped[Optional[float]] = mapped_column(Numeric(14, 2), nullable=True)
    currency: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    payment_method: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    decline_code: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    attempt_number: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    recovery_case: Mapped[Optional["RecoveryCase"]] = relationship(back_populates="payment_event")
