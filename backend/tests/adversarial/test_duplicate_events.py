"""
Adversarial tests for Phase 3: event ingestion.

Spec requirement:
  Test: duplicate webhook
  Expected: single processing

This validates Critical Safety Invariant #10 — duplicate events are
not processed twice.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import text

from app.core.taxonomy import EventType


def test_duplicate_event_processed_exactly_once_end_to_end(api_client, test_merchant, db):
    event_id = f"evt-adv-{uuid.uuid4()}"
    idempotency_key = f"idem-adv-{uuid.uuid4()}"
    payload = {
        "event_id": event_id,
        "event_type": EventType.PAYMENT_FAILED.value,
        "event_timestamp": datetime.now(timezone.utc).isoformat(),
        "payload": {"decline_code": "insufficient_funds"},
        "idempotency_key": idempotency_key,
        "merchant_id": str(test_merchant),
        "amount": 1000,
        "currency": "INR",
    }

    # Simulate the same webhook arriving 3 times (common in real payment
    # gateways due to at-least-once delivery / retries).
    responses = [
        api_client.post("/api/v1/simulate/events", json=payload) for _ in range(3)
    ]

    for r in responses:
        assert r.status_code == 201

    assert responses[0].json()["idempotent_replay"] is False
    assert responses[1].json()["idempotent_replay"] is True
    assert responses[2].json()["idempotent_replay"] is True

    # All three responses point at the SAME underlying event and case.
    event_ids = {r.json()["payment_event_id"] for r in responses}
    case_ids = {r.json()["recovery_case_id"] for r in responses}
    assert len(event_ids) == 1
    assert len(case_ids) == 1

    # Prove it at the DB level too: exactly one payment_event row exists.
    count = db.execute(
        text("SELECT count(*) FROM payment_events WHERE event_id = :eid"),
        {"eid": event_id},
    ).scalar()
    assert count == 1

    # And exactly one recovery_case row exists for it.
    case_count = db.execute(
        text(
            "SELECT count(*) FROM recovery_cases rc "
            "JOIN payment_events pe ON pe.id = rc.payment_event_id "
            "WHERE pe.event_id = :eid"
        ),
        {"eid": event_id},
    ).scalar()
    assert case_count == 1
