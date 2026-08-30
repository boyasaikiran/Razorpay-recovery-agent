"""
Data leakage protection test (spec requirement, explicit):
  "Build an explicit automated leakage test."

Verifies that ground_truth_* label columns can never end up in the
feature candidate list that Phase 6/7 ML training code will use.
"""
from app.ml.feature_schema import (
    ALL_COLUMNS,
    FEATURE_CANDIDATE_COLUMNS,
    ID_COLUMNS,
    LABEL_COLUMNS,
    TIMESTAMP_COLUMNS,
)


def test_label_columns_are_all_ground_truth():
    for col in LABEL_COLUMNS:
        assert col.startswith("ground_truth_"), f"{col} is in LABEL_COLUMNS but isn't a ground_truth_ column"


def test_no_ground_truth_column_in_feature_candidates():
    for col in FEATURE_CANDIDATE_COLUMNS:
        assert not col.startswith("ground_truth_"), (
            f"LEAKAGE: '{col}' looks like a label but is in FEATURE_CANDIDATE_COLUMNS"
        )


def test_feature_candidates_and_labels_are_disjoint():
    overlap = set(FEATURE_CANDIDATE_COLUMNS) & set(LABEL_COLUMNS)
    assert overlap == set(), f"LEAKAGE: columns in both feature and label sets: {overlap}"


def test_feature_candidates_and_ids_are_disjoint():
    overlap = set(FEATURE_CANDIDATE_COLUMNS) & set(ID_COLUMNS)
    assert overlap == set(), f"ID columns leaking into features: {overlap}"


def test_all_columns_is_the_union_of_the_parts():
    reconstructed = set(ID_COLUMNS) | set(FEATURE_CANDIDATE_COLUMNS) | set(LABEL_COLUMNS) | set(TIMESTAMP_COLUMNS)
    assert reconstructed == set(ALL_COLUMNS), (
        "ALL_COLUMNS has drifted from the sum of its parts — a column was "
        "added to one list but not reflected in ALL_COLUMNS, or vice versa."
    )


def test_generated_dataset_labels_match_schema():
    """
    End-to-end check: generate real data and confirm none of the
    declared FEATURE_CANDIDATE_COLUMNS values are suspiciously
    identical to a label column (a common real-world leakage bug:
    accidentally duplicating a label into a feature column under a
    different name during feature engineering).
    """
    import sys
    from pathlib import Path

    generator_dir = Path(__file__).resolve().parents[3] / "data" / "synthetic_generator"
    if str(generator_dir) not in sys.path:
        sys.path.insert(0, str(generator_dir))
    from generate import generate_dataset

    df = generate_dataset(n_records=200, n_merchants=15, seed=7)

    feature_df = df[FEATURE_CANDIDATE_COLUMNS]
    label_df = df[LABEL_COLUMNS]

    # No feature column should be perfectly identical to a label column
    # (would indicate the label leaked in under an alias).
    for feature_col in feature_df.columns:
        for label_col in label_df.columns:
            if feature_df[feature_col].dtype == label_df[label_col].dtype:
                identical = (feature_df[feature_col] == label_df[label_col]).all()
                assert not identical, f"LEAKAGE: feature '{feature_col}' is identical to label '{label_col}'"
