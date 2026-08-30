import hashlib
import hmac
import json
import time
import uuid

from app.core.config import get_settings


def _sign(body: bytes, secret: str) -> str:
    return hmac.new(key=secret.encode("utf-8"), msg=body, digestmod=hashlib.sha256).hexdigest()


def _payment_failed_body(account_id: str, payment_id: str = None) -> dict:
    payment_id = payment_id or f"pay_{uuid.uuid4().hex[:14]}"
    return {
        "entity": "event",
        "account_id": account_id,
        "event": "payment.failed",
        "contains": ["payment"],
        "payload": {
            "payment": {
                "entity": {
                    "id": payment_id,
                    "entity": "payment",
                    "amount": 50000,
                    "currency": "INR",
                    "status": "failed",
                    "order_id": None,
                    "invoice_id": None,
                    "method": "card",
                    "customer_id": "cust_webhooktest",
                    "error_code": "BAD_REQUEST_ERROR",
                    "error_description": "Payment failed",
                }
            }
        },
        "created_at": int(time.time()),
    }


def test_webhook_with_valid_signature_ingests_event(api_client, test_merchant, db, monkeypatch):
    from sqlalchemy import text

    webhook_secret = "test_whsec_123"
    settings = get_settings()
    monkeypatch.setattr(settings, "razorpay_webhook_secret", webhook_secret)

    razorpay_account_id = f"acc_{uuid.uuid4().hex[:14]}"
    db.execute(
        text("UPDATE merchants SET razorpay_merchant_id = :rzp_id WHERE id = :mid"),
        {"rzp_id": razorpay_account_id, "mid": test_merchant},
    )
    db.commit()

    body_dict = _payment_failed_body(razorpay_account_id)
    raw_body = json.dumps(body_dict).encode("utf-8")
    signature = _sign(raw_body, webhook_secret)
    event_id_header = f"evt_{uuid.uuid4().hex[:14]}"

    resp = api_client.post(
        "/api/v1/webhooks/razorpay",
        content=raw_body,
        headers={
            "Content-Type": "application/json",
            "X-Razorpay-Signature": signature,
            "x-razorpay-event-id": event_id_header,
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["idempotent_replay"] is False
    assert body["status"] == "ingested"


def test_webhook_with_invalid_signature_is_rejected(api_client, test_merchant, monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "razorpay_webhook_secret", "real_secret")

    body_dict = _payment_failed_body("acc_doesnotmatter")
    raw_body = json.dumps(body_dict).encode("utf-8")
    wrong_signature = _sign(raw_body, "wrong_secret")

    resp = api_client.post(
        "/api/v1/webhooks/razorpay",
        content=raw_body,
        headers={
            "Content-Type": "application/json",
            "X-Razorpay-Signature": wrong_signature,
            "x-razorpay-event-id": f"evt_{uuid.uuid4().hex[:14]}",
        },
    )
    assert resp.status_code == 400


def test_webhook_duplicate_event_id_processed_once(api_client, test_merchant, db, monkeypatch):
    from sqlalchemy import text

    webhook_secret = "test_whsec_dup"
    settings = get_settings()
    monkeypatch.setattr(settings, "razorpay_webhook_secret", webhook_secret)

    razorpay_account_id = f"acc_{uuid.uuid4().hex[:14]}"
    db.execute(
        text("UPDATE merchants SET razorpay_merchant_id = :rzp_id WHERE id = :mid"),
        {"rzp_id": razorpay_account_id, "mid": test_merchant},
    )
    db.commit()

    payment_id = f"pay_{uuid.uuid4().hex[:14]}"
    body_dict = _payment_failed_body(razorpay_account_id, payment_id=payment_id)
    raw_body = json.dumps(body_dict).encode("utf-8")
    signature = _sign(raw_body, webhook_secret)
    event_id_header = f"evt_{uuid.uuid4().hex[:14]}"
    headers = {
        "Content-Type": "application/json",
        "X-Razorpay-Signature": signature,
        "x-razorpay-event-id": event_id_header,
    }

    first = api_client.post("/api/v1/webhooks/razorpay", content=raw_body, headers=headers)
    second = api_client.post("/api/v1/webhooks/razorpay", content=raw_body, headers=headers)

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["idempotent_replay"] is False
    assert second.json()["idempotent_replay"] is True


def test_webhook_unmapped_event_type_is_acknowledged_not_guessed(api_client, monkeypatch):
    webhook_secret = "test_whsec_unmapped"
    settings = get_settings()
    monkeypatch.setattr(settings, "razorpay_webhook_secret", webhook_secret)

    body_dict = {
        "entity": "event",
        "account_id": "acc_whatever",
        "event": "subscription.charged",  # not in the verified map
        "contains": ["subscription"],
        "payload": {},
        "created_at": int(time.time()),
    }
    raw_body = json.dumps(body_dict).encode("utf-8")
    signature = _sign(raw_body, webhook_secret)

    resp = api_client.post(
        "/api/v1/webhooks/razorpay",
        content=raw_body,
        headers={
            "Content-Type": "application/json",
            "X-Razorpay-Signature": signature,
            "x-razorpay-event-id": f"evt_{uuid.uuid4().hex[:14]}",
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["mapped"] is False
    assert body["razorpay_event_type"] == "subscription.charged"


def test_webhook_unknown_merchant_account_id_returns_404(api_client, monkeypatch):
    webhook_secret = "test_whsec_unknown_merchant"
    settings = get_settings()
    monkeypatch.setattr(settings, "razorpay_webhook_secret", webhook_secret)

    body_dict = _payment_failed_body(f"acc_{uuid.uuid4().hex[:14]}")
    raw_body = json.dumps(body_dict).encode("utf-8")
    signature = _sign(raw_body, webhook_secret)

    resp = api_client.post(
        "/api/v1/webhooks/razorpay",
        content=raw_body,
        headers={
            "Content-Type": "application/json",
            "X-Razorpay-Signature": signature,
            "x-razorpay-event-id": f"evt_{uuid.uuid4().hex[:14]}",
        },
    )
    assert resp.status_code == 404
