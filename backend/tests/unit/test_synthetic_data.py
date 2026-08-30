"""
Tests for the synthetic data generator (Phase 5).

Imports the generator module directly by adding data/synthetic_generator
to sys.path, rather than duplicating generation logic in the test.
"""
import sys
from pathlib import Path

import pytest
import pandas.testing as pdt

_GENERATOR_DIR = Path(__file__).resolve().parents[3] / "data" / "synthetic_generator"
if str(_GENERATOR_DIR) not in sys.path:
    sys.path.insert(0, str(_GENERATOR_DIR))

from generate import CAUSES, generate_dataset, split_by_merchant  # noqa: E402
from app.ml.feature_schema import ALL_COLUMNS, LABEL_COLUMNS  # noqa: E402


@pytest.fixture(scope="module")
def dataset():
    return generate_dataset(n_records=750, n_merchants=18, seed=42)


def test_record_count_in_spec_range(dataset):
    assert 500 <= len(dataset) <= 1000


def test_merchant_count_in_spec_range(dataset):
    assert 15 <= dataset["merchant_id"].nunique() <= 20


def test_all_required_columns_present(dataset):
    for col in ALL_COLUMNS:
        assert col in dataset.columns, f"missing required column: {col}"


def test_class_distribution_is_not_uniform(dataset):
    """
    Spec requires realistic class imbalance — explicitly NOT artificial
    balancing. Assert the distribution is meaningfully non-uniform
    (uniform over 11 causes would be ~9.1% each).
    """
    proportions = dataset["ground_truth_cause"].value_counts(normalize=True)
    assert proportions.max() > 0.15  # some cause is clearly dominant
    assert proportions.min() < 0.05  # some cause is clearly rare
    assert set(proportions.index) == set(CAUSES)


def test_decline_code_is_sometimes_absent(dataset):
    """
    Phase 6 needs cases with no decline code (routes to XGBoost/LLM
    path). Confirm the generator actually produces these, not just
    claims to.
    """
    null_fraction = dataset["decline_code"].isna().mean()
    assert 0.10 < null_fraction < 0.60


def test_free_text_context_present_for_some_ambiguous_causes(dataset):
    non_empty = dataset["free_text_context"].fillna("").str.len() > 0
    assert non_empty.sum() > 0
    assert non_empty.sum() < len(dataset)  # not universal


def test_seed_reproducibility():
    df1 = generate_dataset(n_records=200, n_merchants=15, seed=123)
    df2 = generate_dataset(n_records=200, n_merchants=15, seed=123)
    pdt.assert_frame_equal(df1, df2)


def test_different_seeds_produce_different_data():
    df1 = generate_dataset(n_records=200, n_merchants=15, seed=1)
    df2 = generate_dataset(n_records=200, n_merchants=15, seed=2)
    assert not df1["ground_truth_cause"].equals(df2["ground_truth_cause"])


def test_split_by_merchant_has_no_overlap(dataset):
    train_df, val_df, test_df = split_by_merchant(dataset, seed=42)
    train_merchants = set(train_df["merchant_id"])
    val_merchants = set(val_df["merchant_id"])
    test_merchants = set(test_df["merchant_id"])

    assert train_merchants.isdisjoint(val_merchants)
    assert train_merchants.isdisjoint(test_merchants)
    assert val_merchants.isdisjoint(test_merchants)


def test_split_proportions_approximate_70_15_15(dataset):
    train_df, val_df, test_df = split_by_merchant(dataset, seed=42)
    total = len(dataset)
    assert len(train_df) + len(val_df) + len(test_df) == total

    train_frac = len(train_df) / total
    val_frac = len(val_df) / total
    test_frac = len(test_df) / total

    # Merchant-level splitting with only 18 merchants means exact 70/15/15
    # by record count isn't guaranteed — allow reasonable tolerance.
    assert 0.55 < train_frac < 0.85
    assert 0.05 < val_frac < 0.30
    assert 0.05 < test_frac < 0.30


def test_recoverable_flag_correlates_with_cause(dataset):
    """
    Sanity check that ground truth isn't random noise: risk_block
    should have a much lower recovery rate than temporary_bank_failure.
    """
    risk_block_rate = dataset[dataset["ground_truth_cause"] == "risk_block"][
        "ground_truth_recoverable"
    ].mean()
    bank_failure_rate = dataset[dataset["ground_truth_cause"] == "temporary_bank_failure"][
        "ground_truth_recoverable"
    ].mean()
    assert risk_block_rate < bank_failure_rate
