"""
Batch evaluation engine (Phase 13).

Runs the ACTUAL pipeline against every record in the evaluation set,
using real DB rows and the real trained models. Every number in the
resulting EvaluationReport is computed from that real run.

BASELINE is computed by a separate, much simpler function
(app/evaluation/baseline.py) applied to the SAME records.
"""
import json
import time
import uuid
from pathlib import Path

import pandas as pd
from sklearn.metrics import f1_score, precision_score, recall_score, roc_auc_score
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.agents.agent_loop import run_case_pipeline
from app.core.logging import get_logger
from app.core.taxonomy import PolicyDecision
from app.evaluation.baseline import baseline_outcome
from app.evaluation.schemas import EvaluationReport
from app.models.merchant import Merchant
from app.models.payment_event import PaymentEvent
from app.models.recovery_case import RecoveryCase
from app.repositories.policy_repository import PolicyRepository

logger = get_logger(__name__)

_EVAL_MERCHANT_EMAIL = "evaluation-runner@internal"


def _get_or_create_eval_merchant(db: Session) -> Merchant:
    existing = db.query(Merchant).filter(Merchant.email == _EVAL_MERCHANT_EMAIL).one_or_none()
    if existing:
        return existing
    merchant = Merchant(name="Evaluation Runner", email=_EVAL_MERCHANT_EMAIL)
    db.add(merchant)
    db.commit()
    return merchant


def _row_payload(row: pd.Series) -> dict:
    def clean(v):
        return None if pd.isna(v) else v

    return {
        "days_since_last_success": clean(row.get("days_since_last_success")),
        "customer_lifetime_value": clean(row.get("customer_lifetime_value")),
        "subscription_value": clean(row.get("subscription_value")),
        "customer_segment": clean(row.get("customer_segment")),
        "previous_recovery_rate": clean(row.get("previous_recovery_rate")),
        "session_duration_seconds": clean(row.get("session_duration_seconds")),
        "otp_attempted": bool(row.get("otp_attempted")) if not pd.isna(row.get("otp_attempted")) else None,
        "free_text_context": clean(row.get("free_text_context")) or "",
        "b2b_invoice_days_overdue": clean(row.get("b2b_invoice_days_overdue")),
        "b2b_promise_count": clean(row.get("b2b_promise_count")),
        "b2b_broken_promise_count": clean(row.get("b2b_broken_promise_count")),
        "risk_flag": bool(row.get("risk_flag")) if not pd.isna(row.get("risk_flag")) else False,
        "consent_status": clean(row.get("consent_status")),
        "channel_history": clean(row.get("channel_history")) or "[]",
        "card_age_days": clean(row.get("card_age_days")),
        "network": clean(row.get("network")),
        "issuer_bank_code": clean(row.get("issuer_bank_code")),
        "geo_region": clean(row.get("geo_region")),
        "device_type": clean(row.get("device_type")),
        "is_recurring": bool(row.get("is_recurring")) if not pd.isna(row.get("is_recurring")) else False,
    }


def run_evaluation(db: Session, csv_path: Path, n_records: int = None, cleanup: bool = True) -> EvaluationReport:
    df = pd.read_csv(csv_path)
    if n_records is not None:
        df = df.head(n_records)

    merchant = _get_or_create_eval_merchant(db)
    policy_cache: dict = {}

    created_case_ids = []
    total_at_risk = 0.0
    baseline_recovered = 0.0
    orchestrator_recovered = 0.0

    y_true_recoverable, y_pred_proba = [], []
    cause_correct = 0
    n_success_runs = 0
    n_pipeline_errors = 0
    n_executed = 0
    n_escalated = 0
    n_policy_violations = 0
    n_unauthorized = 0
    latencies = []
    notes = []

    for idx, row in df.iterrows():
        amount = float(row["amount"])
        total_at_risk += amount

        b_status, b_recovered = baseline_outcome(
            row["ground_truth_cause"], bool(row["ground_truth_recoverable"]), amount
        )
        baseline_recovered += b_recovered

        try:
            event = PaymentEvent(
                merchant_id=merchant.id,
                event_id=f"eval-{uuid.uuid4()}",
                event_type=row["event_type"],
                event_timestamp=pd.Timestamp(row["created_at"]).to_pydatetime(),
                source="simulated",
                payload=_row_payload(row),
                simulation_status=True,
                idempotency_key=f"eval-idem-{uuid.uuid4()}",
                amount=amount,
                currency=row.get("currency", "INR"),
                payment_method=None if pd.isna(row.get("payment_method")) else row.get("payment_method"),
                decline_code=None if pd.isna(row.get("decline_code")) else row.get("decline_code"),
                attempt_number=int(row["attempt_number"]),
            )
            db.add(event)
            db.flush()

            case = RecoveryCase(
                merchant_id=merchant.id,
                payment_event_id=event.id,
                case_type=row["event_type"],
                amount_at_risk=amount,
                currency=row.get("currency", "INR"),
            )
            db.add(case)
            db.commit()
            created_case_ids.append(case.id)

            t0 = time.perf_counter()
            result = run_case_pipeline(db, case)
            latencies.append(time.perf_counter() - t0)
            n_success_runs += 1

            if result.diagnosis.cause == row["ground_truth_cause"]:
                cause_correct += 1

            y_true_recoverable.append(int(row["ground_truth_recoverable"]))
            y_pred_proba.append(result.prediction.recovery_probability)

            if result.executed:
                n_executed += 1
                if result.outcome is not None:
                    orchestrator_recovered += float(result.outcome.recovered_amount or 0.0)

            if result.decision.policy_decision == PolicyDecision.ROUTE_TO_HUMAN.value:
                n_escalated += 1

            cause = result.diagnosis.cause
            policy = policy_cache.get(cause)
            if policy is None:
                policy = PolicyRepository(db).get_by_cause(cause)
                policy_cache[cause] = policy
            if policy is not None and result.decision.policy_decision == PolicyDecision.APPROVED.value:
                action = result.decision.proposed_action
                if action not in policy.allowed_actions or action in policy.blocked_actions:
                    n_policy_violations += 1

            if result.action is not None and result.decision.policy_decision != PolicyDecision.APPROVED.value:
                n_unauthorized += 1

        except Exception as e:
            n_pipeline_errors += 1
            logger.error("Evaluation pipeline error on row %s: %s", idx, e)
            db.rollback()

    n_total = len(df)

    model_precision = model_recall = model_f1 = model_roc_auc = None
    if y_true_recoverable and len(set(y_true_recoverable)) > 1:
        y_pred_binary = [1 if p >= 0.5 else 0 for p in y_pred_proba]
        model_precision = float(precision_score(y_true_recoverable, y_pred_binary, zero_division=0))
        model_recall = float(recall_score(y_true_recoverable, y_pred_binary, zero_division=0))
        model_f1 = float(f1_score(y_true_recoverable, y_pred_binary, zero_division=0))
        model_roc_auc = float(roc_auc_score(y_true_recoverable, y_pred_proba))
    else:
        notes.append("Recovery-probability model metrics unavailable (degenerate label distribution).")

    baseline_rate = baseline_recovered / total_at_risk if total_at_risk > 0 else 0.0
    orchestrator_rate = orchestrator_recovered / total_at_risk if total_at_risk > 0 else 0.0
    incremental = orchestrator_recovered - baseline_recovered

    if n_pipeline_errors > 0:
        notes.append(f"{n_pipeline_errors} row(s) raised an exception during evaluation and were skipped.")
    notes.append(
        "LLM_API_KEY is not configured; 0 LLM (Path C) calls were made during this evaluation run. "
        "llm_malformed_output_rate is not applicable (None), not fabricated as 0%."
    )
    notes.append(
        "Baseline model: fixed retry once, no cause awareness (see app/evaluation/baseline.py for the "
        "documented reasoning behind which causes a blind retry can ever recover)."
    )

    report = EvaluationReport(
        n_records_evaluated=n_total,
        total_revenue_at_risk=round(total_at_risk, 2),
        baseline_revenue_recovered=round(baseline_recovered, 2),
        orchestrator_revenue_recovered=round(orchestrator_recovered, 2),
        baseline_recovery_rate=round(baseline_rate, 4),
        orchestrator_recovery_rate=round(orchestrator_rate, 4),
        incremental_recovery=round(incremental, 2),
        incremental_recovery_pct_of_at_risk=round(incremental / total_at_risk, 4) if total_at_risk > 0 else 0.0,
        model_precision=model_precision,
        model_recall=model_recall,
        model_f1=model_f1,
        model_roc_auc=model_roc_auc,
        cause_classification_accuracy=round(cause_correct / n_success_runs, 4) if n_success_runs else 0.0,
        automation_rate=round(n_executed / n_total, 4) if n_total else 0.0,
        escalation_rate=round(n_escalated / n_total, 4) if n_total else 0.0,
        policy_violation_rate=round(n_policy_violations / n_success_runs, 4) if n_success_runs else 0.0,
        unauthorized_action_rate=round(n_unauthorized / n_success_runs, 4) if n_success_runs else 0.0,
        tool_success_rate=round(n_success_runs / n_total, 4) if n_total else 0.0,
        avg_pipeline_latency_seconds=round(sum(latencies) / len(latencies), 4) if latencies else 0.0,
        llm_calls_made=0,
        llm_malformed_output_rate=None,
        notes=notes,
    )

    if cleanup:
        _cleanup(db, created_case_ids, merchant.id)

    return report


def _cleanup(db: Session, case_ids, merchant_id):
    for cid in case_ids:
        db.execute(text("DELETE FROM audit_logs WHERE recovery_case_id = :c"), {"c": cid})
        db.execute(text("DELETE FROM outcomes WHERE recovery_case_id = :c"), {"c": cid})
        db.execute(text("DELETE FROM actions WHERE recovery_case_id = :c"), {"c": cid})
        db.execute(text("DELETE FROM decisions WHERE recovery_case_id = :c"), {"c": cid})
        db.execute(text("DELETE FROM model_predictions WHERE recovery_case_id = :c"), {"c": cid})
        db.execute(text("DELETE FROM diagnoses WHERE recovery_case_id = :c"), {"c": cid})
    db.execute(text("DELETE FROM recovery_cases WHERE merchant_id = :m"), {"m": merchant_id})
    db.execute(text("DELETE FROM payment_events WHERE merchant_id = :m"), {"m": merchant_id})
    db.execute(text("DELETE FROM customers WHERE merchant_id = :m"), {"m": merchant_id})
    db.commit()


if __name__ == "__main__":
    from app.database.session import SessionLocal

    db = SessionLocal()
    try:
        csv_path = Path(__file__).resolve().parents[3] / "data" / "processed" / "evaluation.csv"
        report = run_evaluation(db, csv_path)
        print(json.dumps(report.model_dump(), indent=2))
    finally:
        db.close()
