"""
Baseline strategy for Phase 13 evaluation: fixed retry, once, no cause
awareness, fixed timing -- per spec's exact definition.

DESIGN DECISION (stated explicitly): a baseline that blindly retries a
failed payment cannot succeed for causes where the underlying problem
isn't transient -- retrying the SAME expired card, the SAME abandoned
checkout, or a risk-blocked payment cannot mechanically fix anything.
This isn't a probabilistic assumption tuned to make the baseline look
artificially bad; it's a structural fact about what "retry" means.

  BASELINE_RETRY_PLAUSIBLE: transient-failure causes where blindly
    retrying at least COULD work. Even for these, blind immediate
    retry succeeds less often than a well-timed, cause-aware
    DELAYED_RETRY -- modeled via BASELINE_TIMING_DISCOUNT.

  BASELINE_RETRY_IMPOSSIBLE: causes where retrying the identical failed
    attempt cannot mechanically succeed. Baseline always fails these.

ground_truth_recoverable represents "recoverable in principle under
correct handling for this cause." For plausible causes, baseline
succeeds with probability BASELINE_TIMING_DISCOUNT when
ground_truth_recoverable is True (never when False).
"""
import random
from typing import Optional

BASELINE_RETRY_PLAUSIBLE = {
    "insufficient_funds",
    "temporary_bank_failure",
    "bank_downtime",
    "auth_otp_failure",
    "repeated_failure",
    "unknown",
}

BASELINE_RETRY_IMPOSSIBLE = {
    "expired_payment_method",
    "checkout_abandonment",
    "price_shock_abandonment",
    "overdue_invoice",
    "risk_block",
}

# Illustrative assumption (documented, not hidden): immediate fixed-
# timing blind retry succeeds at ~60% the rate of a well-timed,
# cause-aware retry, for causes where retry is mechanically plausible.
BASELINE_TIMING_DISCOUNT = 0.6


def baseline_outcome(
    cause: str, ground_truth_recoverable: bool, amount: float, rng: Optional[random.Random] = None
) -> tuple[str, float]:
    rng = rng or random.Random()

    if cause in BASELINE_RETRY_IMPOSSIBLE:
        return "failure", 0.0
    if not ground_truth_recoverable:
        return "failure", 0.0
    if rng.random() < BASELINE_TIMING_DISCOUNT:
        return "success", float(amount)
    return "failure", 0.0
