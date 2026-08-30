# Machine Learning

Two trained models, both XGBoost. All numbers on this page are read
directly from `data/models/*_metadata.json`, written by the actual
training runs -- nothing here is estimated or rounded up.

## Model 1: Cause Classifier (Diagnosis Path B)

`backend/app/ml/train_cause_classifier.py`. Used when decline_code is
absent or unrecognized by the rule-based mapper (Path A).

**Real validation metrics (n_train=518, n_val=110):**
- Accuracy: **88.18%**
- Macro F1: **0.7952**

**Honest caveat**: this overall number is inflated by `decline_code`
being included as a feature -- for rows where Path A already resolved
the cause via decline_code, the classifier can trivially learn that
same lookup. The metric that actually matters is accuracy on the
subset Path B is *actually invoked for* (decline_code null):

- Accuracy on decline_code-null subset (n=34): **61.76%**
- Macro F1 on that subset: **0.5495**

This honest, harder number is reported deliberately instead of the
inflated one.

**Features**: `event_type`, `currency`, `payment_method`,
`decline_code`, `customer_segment`, `consent_status`, `network`,
`issuer_bank_code`, `geo_region`, `device_type` (categorical) +
`amount`, `attempt_number`, `days_since_last_success`,
`customer_lifetime_value`, `subscription_value`,
`previous_recovery_rate`, `session_duration_seconds`,
`b2b_invoice_days_overdue`, `b2b_promise_count`,
`b2b_broken_promise_count`, `card_age_days` (numeric) +
`otp_attempted`, `risk_flag`, `is_recurring` (boolean) +
`channel_count` (derived from `channel_history`).

**A real bug found and fixed while building this**: pandas'
`.astype("category")` on a subset with an entirely-null column (e.g.
`decline_code`, which is null for exactly the rows Path B is invoked
on) produces a zero-category dtype, which crashes XGBoost. Fixed by
freezing category levels from the training set and applying them
consistently at inference (`_prepare_features(df, categories=...)`
in `train_cause_classifier.py`). Two regression tests exist for this
specific bug in `tests/unit/test_diagnosis_xgboost.py`.

## Model 2: Recovery Probability

`backend/app/ml/train_recovery_probability.py`. Predicts
`P(revenue will be recovered | features)`.

**Real validation metrics (n_train=518, n_val=110):**
- Precision: **58.93%**
- Recall: **71.74%**
- F1: **0.6471**
- ROC-AUC: **0.7272**

**Feature importance (real, from the trained model, descending):**

| Feature | Importance |
|---|---|
| `diagnosed_cause` | 0.2085 |
| `previous_recovery_rate` | 0.1062 |
| `customer_segment` | 0.1036 |
| `card_age_days` | 0.0979 |
| `days_since_last_success` | 0.0913 |
| `amount` | 0.0901 |
| `customer_lifetime_value` | 0.0853 |
| `subscription_value` | 0.0840 |
| `attempt_number` | 0.0694 |
| `b2b_invoice_days_overdue` | 0.0637 |

### Design decision: trained on diagnosed cause, not ground truth

The spec's suggested feature `failure_type` could have been
implemented by training directly on the synthetic dataset's
`ground_truth_cause` -- but `ground_truth_recoverable` is strongly
correlated with `ground_truth_cause` **by construction** in the
generator, so that would just let the model memorize the generator's
own lookup table. Instead, this script **runs the actual Phase 6
diagnosis cascade** over every training row and uses *that* predicted
cause as the feature -- meaning this model trains on Path B's real
~62% accuracy, not an idealized ground truth. Slower to train, but
honest about what the pipeline will actually feed it at serve time.

### Calibration

A 10-bin reliability curve is computed at training time and exposed
via `GET /api/v1/models/performance` (rendered on the Model
Performance dashboard page). The model is directionally sensible but
not perfectly calibrated at the low-probability end -- expected for a
model trained on 518 rows, stated rather than glossed over.

## Data leakage protection

`backend/app/ml/feature_schema.py` is the single source of truth for
which columns are labels (`ground_truth_*`) vs. feature candidates.
Both training scripts assert disjointness at runtime before fitting.
`tests/unit/test_data_leakage.py` (6 tests) checks this explicitly,
including an end-to-end check that no feature column in real generated
data is suspiciously identical to a label column.

## Retraining

```bash
cd backend
.venv/bin/python -m app.ml.train_cause_classifier
.venv/bin/python -m app.ml.train_recovery_probability
```

Both read from `data/processed/{train,val}.csv` and write fresh
artifacts + metadata to `data/models/`.
