"""
Centralized decline_code -> cause mapping for Diagnosis Path A
(deterministic rule-based mapper).

Kept as a plain dict (not hardcoded inline in the diagnosis service) so
it stays "centralized and configurable" per the spec, matching the
same principle applied to app/core/taxonomy.py. Extend this dict to
add support for new decline codes without touching diagnosis logic.

This mirrors the synthetic data generator's DECLINE_CODES_BY_CAUSE
(data/synthetic_generator/generate.py) by construction, so Path A
should recover ground truth exactly for any record whose decline_code
appears here — that correspondence is what test_diagnosis.py verifies.
"""
from app.core.taxonomy import Cause

RULE_BASED_DECLINE_CODE_MAP: dict[str, str] = {
    "INSUFFICIENT_FUNDS": Cause.INSUFFICIENT_FUNDS.value,
    "NSF": Cause.INSUFFICIENT_FUNDS.value,
    "FUNDS_INSUFFICIENT": Cause.INSUFFICIENT_FUNDS.value,
    "EXPIRED_CARD": Cause.EXPIRED_PAYMENT_METHOD.value,
    "CARD_EXPIRED": Cause.EXPIRED_PAYMENT_METHOD.value,
    "ISSUER_UNAVAILABLE": Cause.TEMPORARY_BANK_FAILURE.value,
    "BANK_TIMEOUT": Cause.TEMPORARY_BANK_FAILURE.value,
    "OTP_FAILED": Cause.AUTH_OTP_FAILURE.value,
    "AUTH_FAILED_3DS": Cause.AUTH_OTP_FAILURE.value,
    "ISSUER_DOWNTIME": Cause.BANK_DOWNTIME.value,
    "GATEWAY_DOWNTIME": Cause.BANK_DOWNTIME.value,
    "RISK_BLOCKED": Cause.RISK_BLOCK.value,
    "GENERIC_DECLINE": Cause.REPEATED_FAILURE.value,
    "DO_NOT_HONOR": Cause.REPEATED_FAILURE.value,
    "UNKNOWN_ERROR": Cause.UNKNOWN.value,
    # Real Razorpay error_code values (BAD_REQUEST_ERROR, GATEWAY_ERROR,
    # etc., confirmed in Phase 4's webhook payload) are deliberately NOT
    # mapped here yet — Razorpay's error_code taxonomy is broader and
    # less specific than these synthetic codes, and mapping it correctly
    # requires consulting Razorpay's error code reference directly
    # rather than guessing. Unmapped codes fall through to Path B/C.
}

# Confidence assigned to any Path A match. High because the mapping is
# deterministic and, for the synthetic codes above, correct by
# construction — not a probabilistic estimate.
RULE_BASED_CONFIDENCE = 0.95
