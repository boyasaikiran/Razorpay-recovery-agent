"""
Seeds the `policies` DB table from app/policies/default_policies.py.
Idempotent: running twice upserts by cause (unique) rather than
duplicating rows.

Run:
    python -m app.policies.seed_policies
"""
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.database.session import SessionLocal
from app.models.policy import Policy
from app.policies.default_policies import DEFAULT_POLICIES

logger = get_logger(__name__)


def seed_policies(db: Session) -> int:
    count = 0
    for cause, cfg in DEFAULT_POLICIES.items():
        existing = db.query(Policy).filter(Policy.cause == cause).one_or_none()
        if existing is not None:
            existing.allowed_actions = cfg["allowed_actions"]
            existing.blocked_actions = cfg["blocked_actions"]
            existing.confidence_threshold = cfg["confidence_threshold"]
            existing.max_retries = cfg["max_retries"]
            existing.cooldown_seconds = cfg["cooldown_seconds"]
            existing.requires_consent = cfg["requires_consent"]
            existing.blocks_on_risk_flag = cfg["blocks_on_risk_flag"]
            existing.max_amount = cfg["max_amount"]
        else:
            db.add(Policy(cause=cause, **cfg))
        count += 1
    db.commit()
    logger.info("Seeded/updated %d policy rows.", count)
    return count


if __name__ == "__main__":
    db = SessionLocal()
    try:
        n = seed_policies(db)
        print(f"Seeded {n} policies.")
    finally:
        db.close()
