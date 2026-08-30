import random

from app.evaluation.baseline import (
    BASELINE_RETRY_IMPOSSIBLE,
    BASELINE_RETRY_PLAUSIBLE,
    baseline_outcome,
)


def test_retry_impossible_causes_always_fail_even_if_ground_truth_recoverable():
    for cause in BASELINE_RETRY_IMPOSSIBLE:
        status, amount = baseline_outcome(cause, ground_truth_recoverable=True, amount=1000.0)
        assert status == "failure"
        assert amount == 0.0


def test_not_recoverable_ground_truth_always_fails_baseline_regardless_of_cause():
    for cause in BASELINE_RETRY_PLAUSIBLE:
        status, amount = baseline_outcome(cause, ground_truth_recoverable=False, amount=1000.0)
        assert status == "failure"
        assert amount == 0.0


def test_plausible_cause_with_recoverable_ground_truth_sometimes_succeeds():
    rng = random.Random(1)
    outcomes = [
        baseline_outcome("insufficient_funds", ground_truth_recoverable=True, amount=1000.0, rng=rng)[0]
        for _ in range(200)
    ]
    successes = outcomes.count("success")
    assert 100 < successes < 160


def test_successful_baseline_recovers_full_amount():
    rng = random.Random(1)
    for _ in range(50):
        status, amount = baseline_outcome(
            "temporary_bank_failure", ground_truth_recoverable=True, amount=2500.0, rng=rng
        )
        if status == "success":
            assert amount == 2500.0
            return
    assert False, "expected at least one success in 50 trials at 60% rate"


def test_every_taxonomy_cause_is_categorized():
    from app.core.taxonomy import ALL_CAUSES

    covered = BASELINE_RETRY_PLAUSIBLE | BASELINE_RETRY_IMPOSSIBLE
    assert covered == set(ALL_CAUSES)
