"""
Parameterized synthetic data generator for Recovery Orchestrator.

Generates records with a KNOWN ground_truth_cause, then generates all
other fields to be *consistent* with that cause (e.g. risk_block ->
risk_flag=True most of the time; checkout_abandonment -> no decline
code, since nothing was ever attempted). This is what makes the
dataset usable for both the rule-based mapper (Phase 6 Path A, needs
decline_code -> cause pairs) and the XGBoost/LLM paths (Phase 6 Path
B/C, needs cases where decline_code is absent/ambiguous).

Usage:
    python generate.py [--n-records 750] [--n-merchants 18] [--seed 42]

Writes:
    data/raw/synthetic_events.csv        (full dataset, one row per record)
    data/processed/train.csv
    data/processed/val.csv
    data/processed/test.csv
"""
import argparse
import json
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd

# Make the schema module importable regardless of cwd.
_BACKEND_DIR = Path(__file__).resolve().parents[2] / "backend"
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from app.ml.feature_schema import ALL_COLUMNS  # noqa: E402


# ----------------------------------------------------------------------
# Cause taxonomy with REALISTIC (non-uniform) class weights.
# These are illustrative weights for a synthetic demo dataset, not
# derived from any real merchant's actual failure distribution.
# ----------------------------------------------------------------------
CAUSE_WEIGHTS = {
    "insufficient_funds": 0.22,
    "expired_payment_method": 0.15,
    "checkout_abandonment": 0.14,
    "temporary_bank_failure": 0.10,
    "overdue_invoice": 0.10,
    "auth_otp_failure": 0.08,
    "price_shock_abandonment": 0.06,
    "bank_downtime": 0.05,
    "risk_block": 0.04,
    "repeated_failure": 0.04,
    "unknown": 0.02,
}
assert abs(sum(CAUSE_WEIGHTS.values()) - 1.0) < 1e-9

CAUSES = list(CAUSE_WEIGHTS.keys())
CAUSE_P = list(CAUSE_WEIGHTS.values())

# decline_code is only meaningful for causes that reached a payment
# attempt. Deliberately left None for causes where a rule-based
# decline-code mapper would have nothing to go on (checkout
# abandonment, overdue invoices, unknown, some risk blocks) — this is
# exactly what forces Phase 6 to fall through to Path B/C.
DECLINE_CODES_BY_CAUSE = {
    "insufficient_funds": ["INSUFFICIENT_FUNDS", "NSF", "FUNDS_INSUFFICIENT"],
    "expired_payment_method": ["EXPIRED_CARD", "CARD_EXPIRED"],
    "temporary_bank_failure": ["ISSUER_UNAVAILABLE", "BANK_TIMEOUT"],
    "auth_otp_failure": ["OTP_FAILED", "AUTH_FAILED_3DS"],
    "bank_downtime": ["ISSUER_DOWNTIME", "GATEWAY_DOWNTIME"],
    "risk_block": ["RISK_BLOCKED", None],
    "repeated_failure": ["GENERIC_DECLINE", "DO_NOT_HONOR"],
    "unknown": [None, "UNKNOWN_ERROR"],
    "checkout_abandonment": [None],
    "price_shock_abandonment": [None],
    "overdue_invoice": [None],
}

EVENT_TYPE_BY_CAUSE = {
    "insufficient_funds": ["payment_failed", "subscription_renewal_failed"],
    "expired_payment_method": ["subscription_renewal_failed", "payment_failed"],
    "temporary_bank_failure": ["payment_failed", "subscription_renewal_failed"],
    "auth_otp_failure": ["payment_failed"],
    "bank_downtime": ["payment_failed", "subscription_renewal_failed"],
    "risk_block": ["payment_failed"],
    "repeated_failure": ["payment_failed", "subscription_renewal_failed"],
    "unknown": ["payment_failed", "checkout_abandoned"],
    "checkout_abandonment": ["checkout_abandoned"],
    "price_shock_abandonment": ["checkout_abandoned"],
    "overdue_invoice": ["invoice_overdue"],
}

PAYMENT_METHODS = ["card", "upi", "netbanking", "wallet", "emi"]
NETWORKS = ["Visa", "Mastercard", "RuPay", "Amex"]
BANK_CODES = ["HDFC", "ICIC", "SBIN", "AXIS", "KOTAK", "YESB", "IDFB"]
GEO_REGIONS = ["North", "South", "East", "West", "Central"]
DEVICE_TYPES = ["mobile", "desktop", "tablet"]
CUSTOMER_SEGMENTS = ["consumer", "smb", "enterprise"]
CONSENT_STATUSES = ["opted_in", "opted_in", "opted_in", "unknown", "opted_out"]  # weighted
CHANNELS = ["email", "sms", "whatsapp", "ivr", "push"]

FREE_TEXT_SNIPPETS_BY_CAUSE = {
    "price_shock_abandonment": [
        "customer said the total was more than expected at checkout",
        "user commented shipping fees were too high, left cart",
        "chat log: 'this got expensive fast, I'll think about it'",
    ],
    "checkout_abandonment": [
        "session ended after payment page loaded, no attempt made",
        "user navigated away during address entry",
        "cart abandoned, no support contact",
    ],
    "risk_block": [
        "flagged by fraud review, multiple cards tried in short window",
        "support ticket: customer disputes the risk block, requests manual review",
    ],
    "repeated_failure": [
        "customer support chat: 'card keeps getting declined, not sure why'",
        "third failed attempt this week, customer frustrated in chat",
    ],
}


def _rng(seed: int) -> np.random.Generator:
    return np.random.default_rng(seed)


def _weighted_choice(rng: np.random.Generator, options, weights=None):
    if weights is None:
        return options[rng.integers(0, len(options))]
    return rng.choice(options, p=np.array(weights) / np.sum(weights))


def generate_merchants(rng: np.random.Generator, n_merchants: int) -> list[dict]:
    merchants = []
    for i in range(n_merchants):
        merchants.append(
            {
                "merchant_id": f"merch_{i:03d}",
                "merchant_index": i,
            }
        )
    return merchants


def _allocate_records_to_merchants(rng: np.random.Generator, n_records: int, n_merchants: int) -> np.ndarray:
    """
    Dirichlet allocation so some merchants have more failed events than
    others (realistic: bigger merchants generate more failures), rather
    than an artificially uniform split.
    """
    proportions = rng.dirichlet(np.ones(n_merchants) * 2.0)
    counts = np.floor(proportions * n_records).astype(int)
    # Fix rounding so counts sum exactly to n_records.
    deficit = n_records - counts.sum()
    for i in range(abs(deficit)):
        idx = i % n_merchants
        counts[idx] += 1 if deficit > 0 else -1
    counts = np.clip(counts, 0, None)
    return counts


def generate_dataset(n_records: int, n_merchants: int, seed: int) -> pd.DataFrame:
    rng = _rng(seed)
    merchants = generate_merchants(rng, n_merchants)
    counts_per_merchant = _allocate_records_to_merchants(rng, n_records, n_merchants)

    base_time = datetime(2026, 1, 1, tzinfo=timezone.utc)
    rows = []
    record_idx = 0

    for m_idx, merchant in enumerate(merchants):
        n_for_merchant = int(counts_per_merchant[m_idx])
        if n_for_merchant == 0:
            continue

        # Repeat customers within a merchant (needed for repeated_failure
        # cause and previous_recovery_rate to be meaningful).
        n_customers = max(1, int(n_for_merchant * 0.65))
        customer_ids = [f"cust_{m_idx:03d}_{c:04d}" for c in range(n_customers)]

        for _ in range(n_for_merchant):
            cause = _weighted_choice(rng, CAUSES, CAUSE_P)
            event_type = _weighted_choice(rng, EVENT_TYPE_BY_CAUSE[cause])
            decline_code = _weighted_choice(rng, DECLINE_CODES_BY_CAUSE[cause])
            customer_id = customer_ids[rng.integers(0, len(customer_ids))]

            is_b2b = event_type == "invoice_overdue"
            is_checkout = event_type == "checkout_abandoned"

            amount = float(round(rng.lognormal(mean=7.5, sigma=1.0), 2))
            amount = min(amount, 500000.0)

            attempt_number = int(rng.integers(1, 5)) if cause == "repeated_failure" else int(
                rng.integers(1, 3)
            )
            days_since_last_success = int(rng.integers(0, 120))

            customer_lifetime_value = float(round(rng.lognormal(mean=9.0, sigma=1.2), 2))
            subscription_value = (
                float(round(rng.lognormal(mean=6.5, sigma=0.8), 2))
                if event_type == "subscription_renewal_failed"
                else None
            )

            customer_segment = _weighted_choice(rng, CUSTOMER_SEGMENTS, [0.6, 0.3, 0.1])
            previous_recovery_rate = float(round(rng.beta(2, 3), 3))

            session_duration_seconds = (
                int(rng.integers(5, 900)) if is_checkout else int(rng.integers(0, 300))
            )
            otp_attempted = bool(rng.random() < 0.6) if cause == "auth_otp_failure" else bool(
                rng.random() < 0.15
            )

            free_text_pool = FREE_TEXT_SNIPPETS_BY_CAUSE.get(cause)
            free_text_context = (
                str(_weighted_choice(rng, free_text_pool)) if free_text_pool and rng.random() < 0.7 else ""
            )

            b2b_invoice_days_overdue = int(rng.integers(1, 90)) if is_b2b else 0
            b2b_promise_count = int(rng.integers(0, 4)) if is_b2b else 0
            b2b_broken_promise_count = (
                int(rng.integers(0, b2b_promise_count + 1)) if is_b2b and b2b_promise_count > 0 else 0
            )

            risk_flag = bool(rng.random() < 0.85) if cause == "risk_block" else bool(rng.random() < 0.03)

            consent_status = _weighted_choice(rng, CONSENT_STATUSES)

            n_channels = int(rng.integers(0, 3))
            channel_history = list(rng.choice(CHANNELS, size=n_channels, replace=False)) if n_channels else []

            card_age_days = (
                int(rng.integers(1, 2000)) if decline_code and "CARD" in str(decline_code) else (
                    int(rng.integers(1, 2000)) if _weighted_choice(rng, PAYMENT_METHODS) == "card" else None
                )
            )
            payment_method = "invoice" if is_b2b else ("none" if is_checkout else _weighted_choice(rng, PAYMENT_METHODS))
            network = str(_weighted_choice(rng, NETWORKS)) if payment_method == "card" else None
            issuer_bank_code = (
                str(_weighted_choice(rng, BANK_CODES)) if payment_method in ("card", "netbanking") else None
            )
            geo_region = str(_weighted_choice(rng, GEO_REGIONS))
            device_type = str(_weighted_choice(rng, DEVICE_TYPES, [0.55, 0.35, 0.10]))
            is_recurring = bool(event_type == "subscription_renewal_failed")

            # --- Ground truth (label columns; see app/ml/feature_schema.py) ---
            recoverable_base_prob = {
                "insufficient_funds": 0.55,
                "expired_payment_method": 0.60,
                "temporary_bank_failure": 0.80,
                "auth_otp_failure": 0.65,
                "bank_downtime": 0.75,
                "risk_block": 0.10,
                "repeated_failure": 0.25,
                "unknown": 0.30,
                "checkout_abandonment": 0.35,
                "price_shock_abandonment": 0.20,
                "overdue_invoice": 0.45,
            }[cause]
            ground_truth_recoverable = bool(rng.random() < recoverable_base_prob)
            ground_truth_recovered_amount = (
                float(round(amount * rng.uniform(0.5, 1.0), 2)) if ground_truth_recoverable else 0.0
            )

            created_at = base_time + timedelta(
                days=int(rng.integers(0, 180)), seconds=int(rng.integers(0, 86400))
            )

            rows.append(
                {
                    "record_id": f"rec_{record_idx:06d}",
                    "merchant_id": merchant["merchant_id"],
                    "customer_id": customer_id,
                    "event_type": event_type,
                    "amount": amount,
                    "currency": "INR",
                    "payment_method": payment_method,
                    "decline_code": decline_code,
                    "attempt_number": attempt_number,
                    "days_since_last_success": days_since_last_success,
                    "customer_lifetime_value": customer_lifetime_value,
                    "subscription_value": subscription_value,
                    "customer_segment": customer_segment,
                    "previous_recovery_rate": previous_recovery_rate,
                    "session_duration_seconds": session_duration_seconds,
                    "otp_attempted": otp_attempted,
                    "free_text_context": free_text_context,
                    "b2b_invoice_days_overdue": b2b_invoice_days_overdue,
                    "b2b_promise_count": b2b_promise_count,
                    "b2b_broken_promise_count": b2b_broken_promise_count,
                    "risk_flag": risk_flag,
                    "consent_status": consent_status,
                    "channel_history": json.dumps(channel_history),
                    "card_age_days": card_age_days,
                    "network": network,
                    "issuer_bank_code": issuer_bank_code,
                    "geo_region": geo_region,
                    "device_type": device_type,
                    "is_recurring": is_recurring,
                    "ground_truth_cause": cause,
                    "ground_truth_recoverable": ground_truth_recoverable,
                    "ground_truth_recovered_amount": ground_truth_recovered_amount,
                    "created_at": created_at.isoformat(),
                }
            )
            record_idx += 1

    df = pd.DataFrame(rows, columns=ALL_COLUMNS)
    return df


def split_by_merchant(df: pd.DataFrame, seed: int, train_frac=0.70, val_frac=0.15):
    """
    Splits by MERCHANT (not by record) per spec: no merchant's records
    appear in more than one split. Merchants are ordered randomly, then
    assigned to splits greedily by cumulative record count so the
    resulting record-level proportions land close to 70/15/15 despite
    merchants having unequal record counts.
    """
    rng = _rng(seed + 1)  # different stream from record generation
    merchant_counts = df.groupby("merchant_id").size().to_dict()
    merchant_ids = list(merchant_counts.keys())
    rng.shuffle(merchant_ids)

    total = len(df)
    train_target = total * train_frac
    val_target = total * (train_frac + val_frac)

    train_ids, val_ids, test_ids = [], [], []
    running = 0
    for mid in merchant_ids:
        running += merchant_counts[mid]
        if running <= train_target or not train_ids:
            train_ids.append(mid)
        elif running <= val_target or not val_ids:
            val_ids.append(mid)
        else:
            test_ids.append(mid)
    # Guard: if every merchant landed in train (possible with very few
    # merchants), force at least one into val/test.
    if not val_ids and len(train_ids) > 1:
        val_ids.append(train_ids.pop())
    if not test_ids and len(train_ids) > 1:
        test_ids.append(train_ids.pop())

    train_df = df[df["merchant_id"].isin(train_ids)].reset_index(drop=True)
    val_df = df[df["merchant_id"].isin(val_ids)].reset_index(drop=True)
    test_df = df[df["merchant_id"].isin(test_ids)].reset_index(drop=True)
    return train_df, val_df, test_df


def main():
    parser = argparse.ArgumentParser(description="Generate synthetic Recovery Orchestrator data.")
    parser.add_argument("--n-records", type=int, default=750)
    parser.add_argument("--n-merchants", type=int, default=18)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--output-dir",
        type=str,
        default=str(Path(__file__).resolve().parents[2] / "data"),
    )
    args = parser.parse_args()

    if not (500 <= args.n_records <= 1000):
        print(f"WARNING: n_records={args.n_records} is outside the spec'd 500-1000 range.")
    if not (15 <= args.n_merchants <= 20):
        print(f"WARNING: n_merchants={args.n_merchants} is outside the spec'd 15-20 range.")

    df = generate_dataset(args.n_records, args.n_merchants, args.seed)

    output_dir = Path(args.output_dir)
    raw_dir = output_dir / "raw"
    processed_dir = output_dir / "processed"
    raw_dir.mkdir(parents=True, exist_ok=True)
    processed_dir.mkdir(parents=True, exist_ok=True)

    raw_path = raw_dir / "synthetic_events.csv"
    df.to_csv(raw_path, index=False)

    train_df, val_df, test_df = split_by_merchant(df, args.seed)
    train_df.to_csv(processed_dir / "train.csv", index=False)
    val_df.to_csv(processed_dir / "val.csv", index=False)
    test_df.to_csv(processed_dir / "test.csv", index=False)

    print(f"Generated {len(df)} records across {df['merchant_id'].nunique()} merchants -> {raw_path}")
    print(f"Split: train={len(train_df)} ({len(train_df)/len(df):.1%}), "
          f"val={len(val_df)} ({len(val_df)/len(df):.1%}), "
          f"test={len(test_df)} ({len(test_df)/len(df):.1%})")
    print("\nCause distribution (ground_truth_cause):")
    print(df["ground_truth_cause"].value_counts(normalize=True).round(3).to_string())


if __name__ == "__main__":
    main()
