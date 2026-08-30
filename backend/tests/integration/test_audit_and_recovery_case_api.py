import uuid
from datetime import datetime, timezone


def _ingest(api_client, test_merchant, decline_code=None, amount=1500):
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
            "amount": amount,
            "currency": "INR",
            "decline_code": decline_code,
            "attempt_number": 1,
        },
    )
    assert resp.status_code == 201
    return resp.json()["recovery_case_id"]


def test_run_case_endpoint_executes_full_pipeline(api_client, test_merchant):
    case_id = _ingest(api_client, test_merchant, decline_code="EXPIRED_CARD")

    resp = api_client.post(f"/api/v1/recovery-cases/{case_id}/run")
    assert resp.status_code == 200
    body = resp.json()
    assert body["case_id"] == case_id
    assert body["diagnosis"]["cause"] == "expired_payment_method"
    assert body["proposed_action"] == "CREATE_PAYMENT_LINK"
    assert body["policy_decision"] == "APPROVED"
    assert body["executed"] is True
    assert body["outcome"] is not None


def test_run_case_endpoint_404_for_unknown_case(api_client):
    resp = api_client.post(f"/api/v1/recovery-cases/{uuid.uuid4()}/run")
    assert resp.status_code == 404


def test_get_case_detail_after_run(api_client, test_merchant):
    case_id = _ingest(api_client, test_merchant, decline_code="OTP_FAILED")
    api_client.post(f"/api/v1/recovery-cases/{case_id}/run")

    resp = api_client.get(f"/api/v1/recovery-cases/{case_id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == case_id
    assert body["diagnosis"]["cause"] == "auth_otp_failure"
    assert body["decision"] is not None


def test_get_case_detail_404_for_unknown_case(api_client):
    resp = api_client.get(f"/api/v1/recovery-cases/{uuid.uuid4()}")
    assert resp.status_code == 404


def test_list_recovery_cases_includes_ingested_case(api_client, test_merchant):
    case_id = _ingest(api_client, test_merchant, decline_code="NSF")

    resp = api_client.get("/api/v1/recovery-cases", params={"limit": 500})
    assert resp.status_code == 200
    body = resp.json()
    ids = {item["id"] for item in body["items"]}
    assert case_id in ids
    assert body["total"] >= 1


def test_list_recovery_cases_is_enriched_with_diagnosis_and_decision(api_client, test_merchant):
    case_id = _ingest(api_client, test_merchant, decline_code="EXPIRED_CARD")
    api_client.post(f"/api/v1/recovery-cases/{case_id}/run")

    resp = api_client.get("/api/v1/recovery-cases", params={"limit": 500})
    assert resp.status_code == 200
    body = resp.json()
    row = next(item for item in body["items"] if item["id"] == case_id)
    assert row["diagnosis"] is not None
    assert row["diagnosis"]["cause"] == "expired_payment_method"
    assert row["decision"] is not None
    assert row["decision"]["proposed_action"] == "CREATE_PAYMENT_LINK"


def test_trace_endpoint_returns_chronological_entries(api_client, test_merchant):
    case_id = _ingest(api_client, test_merchant, decline_code="ISSUER_UNAVAILABLE")
    api_client.post(f"/api/v1/recovery-cases/{case_id}/run")

    resp = api_client.get(f"/api/v1/recovery-cases/{case_id}/trace")
    assert resp.status_code == 200
    body = resp.json()
    assert body["case_id"] == case_id

    stages = [e["stage"] for e in body["entries"]]
    assert "EVENT_RECEIVED" in stages
    assert "CONTEXT_RETRIEVED" in stages
    assert "CAUSE_CLASSIFIED" in stages
    assert "RECOVERY_PREDICTED" in stages
    assert "ACTION_PROPOSED" in stages
    assert "POLICY_CHECKED" in stages

    timestamps = [e["timestamp"] for e in body["entries"]]
    assert timestamps == sorted(timestamps)


def test_trace_endpoint_404_for_unknown_case(api_client):
    resp = api_client.get(f"/api/v1/recovery-cases/{uuid.uuid4()}/trace")
    assert resp.status_code == 404


def test_audit_logs_endpoint_filters_by_case_id(api_client, test_merchant):
    case_id = _ingest(api_client, test_merchant, decline_code="EXPIRED_CARD")
    api_client.post(f"/api/v1/recovery-cases/{case_id}/run")

    resp = api_client.get("/api/v1/audit-logs", params={"case_id": case_id})
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] > 0
    assert all(item["recovery_case_id"] == case_id for item in body["items"])


def test_audit_logs_endpoint_filters_by_stage(api_client, test_merchant):
    case_id = _ingest(api_client, test_merchant, decline_code="EXPIRED_CARD")
    api_client.post(f"/api/v1/recovery-cases/{case_id}/run")

    resp = api_client.get("/api/v1/audit-logs", params={"case_id": case_id, "stage": "CAUSE_CLASSIFIED"})
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["items"]) == 1
    assert body["items"][0]["stage"] == "CAUSE_CLASSIFIED"


def test_audit_logs_endpoint_pagination(api_client, test_merchant):
    case_id = _ingest(api_client, test_merchant, decline_code="EXPIRED_CARD")
    api_client.post(f"/api/v1/recovery-cases/{case_id}/run")

    resp = api_client.get("/api/v1/audit-logs", params={"case_id": case_id, "limit": 2, "offset": 0})
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["items"]) <= 2
    assert body["limit"] == 2
    assert body["offset"] == 0
