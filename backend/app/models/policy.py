from typing import Optional

from sqlalchemy import Boolean, Float, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base
from app.models.mixins import TimestampMixin, UUIDPKMixin, UpdatedAtMixin


class Policy(Base, UUIDPKMixin, TimestampMixin, UpdatedAtMixin):
    """
    Configurable policy rules per cause. The policy ENGINE (Phase 9) is
    deterministic code, not an LLM — but its thresholds/limits are
    data-driven from this table so they can change without a code
    deploy. Seeded with sane defaults in Phase 9.
    """

    __tablename__ = "policies"

    cause: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    allowed_actions: Mapped[list] = mapped_column(JSONB, nullable=False)
    blocked_actions: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    confidence_threshold: Mapped[float] = mapped_column(Float, nullable=False, default=0.6)
    max_retries: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    cooldown_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=3600)
    requires_consent: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    blocks_on_risk_flag: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    max_amount: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
