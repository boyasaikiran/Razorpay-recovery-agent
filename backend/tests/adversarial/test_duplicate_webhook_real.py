"""
Adversarial test for Phase 4: real Razorpay webhook duplicate delivery.

Razorpay's own docs state duplicate webhook delivery is expected
behavior (retries, at-least-once semantics) and instruct consumers to
dedupe on x-razorpay-event-id. This proves our webhook path does that
correctly under a burst of identical deliveries, matching the spec's
explicit adversarial requirement:
  Test: duplicate webhook
  Expected: single processing
"""
import hashlib
import hmac
import json
import time
import uuid

from sqlalchemy import text

from app.core.config import get_settings


def _sign(body: bytes, secret: str) -> str:
    return hmac.new(key=secret.encode("utf-8"), msg=body, digestmod=hashlib.sha256).hexdigest()


def test_duplicate_real_webhook_delivery_processed_exactly_once(
    api_client, test_merchant, db, monkeypatch
):
    webhook_secret = "adv_whsec_dup_real"
    settings = get_settings()
    monkeypatch.setattr(settings, "razorpay_webhook_secret", webhook_secret)

    razorpay_account_id = f"acc_{uuid.uuid4().hex[:14]}"
    db.execute(
        text("UPDATE merchants SET razorpay_merchant_id = :rzp_id WHERE id = :mid"),
        {"rzp_id": razorpay_account_id, "mid": test_merchant},
    )
    db.commit()

    payment_id = f"pay_{uuid.uuid4().hex[:14]}"
    body_dict = {
        "entity": "event",
        "account_id": razorpay_account_id,
        "event": "payment.failed",
        "contains": ["payment"],
        "payload": {
            "payment": {
                "entity": {
                    "id": payment_id,
                    "entity": "payment",
                    "amount": 250000,
                    "currency": "INR",
                    "status": "failed",
                    "method": "upi",
                    "customer_id": "cust_adversarial",
                    "error_code": "GATEWAY_ERROR",
                    "error_description": "Simulated gateway failure",
                }
            }
        },
        "created_at": int(time.time()),
    }
    raw_body = json.dumps(body_dict).encode("utf-8")
    signature = _sign(raw_body, webhook_secret)
    event_id_header = f"evt_{uuid.uuid4().hex[:14]}"
    headers = {
        "Content-Type": "application/json",
        "X-Razorpay-Signature": signature,
        "x-razorpay-event-id": event_id_header,
    }

    # Simulate Razorpay retrying the same webhook delivery 4 times.
    responses = [
        api_client.post("/api/v1/webhooks/razorpay", content=raw_body, headers=headers)
        for _ in range(4)
    ]

    for r in responses:
        assert r.status_code == 200

    replay_flags = [r.json()["idempotent_replay"] for r in responses]
    assert replay_flags == [False, True, True, True]

    case_ids = {r.json()["recovery_case_id"] for r in responses}
    assert len(case_ids) == 1

    count = db.execute(
        text("SELECT count(*) FROM payment_events WHERE event_id = :eid"),
        {"eid": payment_id},
    ).scalar()
    assert count == 1
