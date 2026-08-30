import uuid
from datetime import datetime, timezone

from app.core.taxonomy import EventType


def _event_payload(merchant_id, event_id=None, idempotency_key=None, event_type=None):
    event_id = event_id or f"evt-{uuid.uuid4()}"
    return {
        "event_id": event_id,
        "event_type": event_type or EventType.PAYMENT_FAILED.value,
        "event_timestamp": datetime.now(timezone.utc).isoformat(),
        "payload": {"decline_code": "insufficient_funds"},
        "idempotency_key": idempotency_key or f"idem-{event_id}",
        "merchant_id": str(merchant_id),
        "customer_external_id": "cust-ext-001",
        "amount": 2500,
        "currency": "INR",
        "payment_method": "card",
        "decline_code": "insufficient_funds",
        "attempt_number": 1,
    }


def test_ingest_new_event_creates_case(api_client, test_merchant):
    resp = api_client.post("/api/v1/simulate/events", json=_event_payload(test_merchant))
    assert resp.status_code == 201
    body = resp.json()
    assert body["idempotent_replay"] is False
    assert body["status"] == "ingested"
    assert body["payment_event_id"]
    assert body["recovery_case_id"]


def test_duplicate_idempotency_key_is_processed_once(api_client, test_merchant):
    payload = _event_payload(test_merchant)

    first = api_client.post("/api/v1/simulate/events", json=payload)
    assert first.status_code == 201
    first_body = first.json()

    second = api_client.post("/api/v1/simulate/events", json=payload)
    assert second.status_code == 201
    second_body = second.json()

    assert second_body["idempotent_replay"] is True
    assert second_body["payment_event_id"] == first_body["payment_event_id"]
    assert second_body["recovery_case_id"] == first_body["recovery_case_id"]


def test_reused_event_id_with_different_idempotency_key_is_rejected(api_client, test_merchant):
    shared_event_id = f"evt-{uuid.uuid4()}"

    first = api_client.post(
        "/api/v1/simulate/events",
        json=_event_payload(test_merchant, event_id=shared_event_id, idempotency_key="key-1"),
    )
    assert first.status_code == 201

    second = api_client.post(
        "/api/v1/simulate/events",
        json=_event_payload(test_merchant, event_id=shared_event_id, idempotency_key="key-2"),
    )
    assert second.status_code == 409


def test_unknown_merchant_returns_404(api_client):
    bogus_merchant = uuid.uuid4()
    resp = api_client.post("/api/v1/simulate/events", json=_event_payload(bogus_merchant))
    assert resp.status_code == 404


def test_invalid_event_type_returns_422(api_client, test_merchant):
    payload = _event_payload(test_merchant, event_type="not_a_real_cause")
    resp = api_client.post("/api/v1/simulate/events", json=payload)
    assert resp.status_code == 422


def test_ingested_event_has_audit_log_entry(api_client, test_merchant, db):
    from sqlalchemy import text

    resp = api_client.post("/api/v1/simulate/events", json=_event_payload(test_merchant))
    case_id = resp.json()["recovery_case_id"]

    row = db.execute(
        text("SELECT stage, actor, simulation_status FROM audit_logs WHERE recovery_case_id = :cid"),
        {"cid": case_id},
    ).fetchone()

    assert row is not None
    assert row[0] == "EVENT_RECEIVED"
    assert row[1] == "system"
    assert row[2] is True
