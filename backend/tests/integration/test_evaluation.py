from pathlib import Path

from app.evaluation.run_evaluation import run_evaluation

_EVAL_CSV = Path(__file__).resolve().parents[3] / "data" / "processed" / "evaluation.csv"


def test_run_evaluation_on_small_sample_produces_sane_report(db):
    report = run_evaluation(db, _EVAL_CSV, n_records=20, cleanup=True)

    assert report.n_records_evaluated == 20
    assert report.total_revenue_at_risk > 0
    assert 0.0 <= report.baseline_recovery_rate <= 1.0
    assert 0.0 <= report.orchestrator_recovery_rate <= 1.0
    assert report.tool_success_rate == 1.0
    assert report.policy_violation_rate == 0.0
    assert report.unauthorized_action_rate == 0.0
    assert report.llm_calls_made == 0
    assert report.cause_classification_accuracy >= 0.0

    assert abs(
        report.incremental_recovery
        - (report.orchestrator_revenue_recovered - report.baseline_revenue_recovered)
    ) < 0.01


def test_evaluation_cleanup_leaves_no_residue(db):
    from sqlalchemy import text

    run_evaluation(db, _EVAL_CSV, n_records=10, cleanup=True)

    count = db.execute(
        text("SELECT count(*) FROM payment_events WHERE event_id LIKE 'eval-%'")
    ).scalar()
    assert count == 0


def test_evaluation_endpoint_returns_report(api_client):
    resp = api_client.post("/api/v1/evaluation/run", params={"n_records": 15})
    assert resp.status_code == 200
    body = resp.json()
    assert body["n_records_evaluated"] == 15
    assert "incremental_recovery" in body
    assert "notes" in body
