import uuid
from typing import Optional

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.models.mixins import TimestampMixin, UUIDPKMixin


class Merchant(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "merchants"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    razorpay_merchant_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    customers: Mapped[list["Customer"]] = relationship(back_populates="merchant")
