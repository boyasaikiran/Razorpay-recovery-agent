import uuid
from datetime import datetime, timezone


def test_metrics_endpoint_returns_zeros_with_no_data(api_client):
    resp = api_client.get("/api/v1/metrics")
    assert resp.status_code == 200
    body = resp.json()
    assert "revenue_at_risk" in body
    assert "cause_distribution" in body
    assert isinstance(body["cause_distribution"], list)


def test_metrics_reflect_a_real_run_case(api_client, test_merchant):
    event_id = f"evt-{uuid.uuid4()}"
    resp = api_client.post(
        "/api/v1/simulate/events",
        json={
            "event_id": event_id,
            "event_type": "payment_failed",
            "event_timestamp": datetime.now(timezone.utc).isoformat(),
            "payload": {"customer_segment": "consumer", "consent_status": "opted_in", "channel_history": "[]"},
            "idempotency_key": f"idem-{event_id}",
            "merchant_id": str(test_merchant),
            "amount": 3000,
            "currency": "INR",
            "decline_code": "EXPIRED_CARD",
            "attempt_number": 1,
        },
    )
    case_id = resp.json()["recovery_case_id"]
    api_client.post(f"/api/v1/recovery-cases/{case_id}/run")

    metrics_resp = api_client.get("/api/v1/metrics")
    assert metrics_resp.status_code == 200
    body = metrics_resp.json()
    assert body["revenue_at_risk"] >= 3000
    assert body["total_cases"] >= 1
    assert body["policy_violations"] == 0
    causes = {c["cause"] for c in body["cause_distribution"]}
    assert "expired_payment_method" in causes
