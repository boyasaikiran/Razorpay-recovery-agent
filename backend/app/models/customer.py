import uuid
from typing import Optional

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.taxonomy import ConsentStatus
from app.database.base import Base
from app.models.mixins import TimestampMixin, UUIDPKMixin


class Customer(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "customers"

    merchant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("merchants.id"), nullable=False
    )
    external_customer_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    consent_status: Mapped[str] = mapped_column(
        String(50), nullable=False, default=ConsentStatus.UNKNOWN.value
    )
    customer_segment: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    customer_lifetime_value: Mapped[Optional[float]] = mapped_column(nullable=True)

    merchant: Mapped["Merchant"] = relationship(back_populates="customers")
