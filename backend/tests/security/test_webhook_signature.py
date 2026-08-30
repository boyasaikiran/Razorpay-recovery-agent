"""
Security tests for webhook signature verification.

This is the one part of Phase 4 fully testable in this sandbox without
live Razorpay credentials: the signature scheme is pure HMAC-SHA256,
confirmed directly against https://razorpay.com/docs/webhooks/
validate-test/ and the official razorpay-python SDK's implementation.
"""
import hashlib
import hmac
import json

from app.services.razorpay_client import RazorpayClientWrapper


def _sign(body: bytes, secret: str) -> str:
    return hmac.new(key=secret.encode("utf-8"), msg=body, digestmod=hashlib.sha256).hexdigest()


def test_valid_signature_is_accepted():
    client = RazorpayClientWrapper()
    body = json.dumps({"event": "payment.failed"}).encode("utf-8")
    secret = "whsec_test_secret"
    signature = _sign(body, secret)

    assert client.verify_webhook_signature(body, signature, secret) is True


def test_tampered_body_is_rejected():
    client = RazorpayClientWrapper()
    secret = "whsec_test_secret"
    original_body = json.dumps({"event": "payment.failed", "amount": 100}).encode("utf-8")
    signature = _sign(original_body, secret)

    tampered_body = json.dumps({"event": "payment.failed", "amount": 999999}).encode("utf-8")

    assert client.verify_webhook_signature(tampered_body, signature, secret) is False


def test_tampered_signature_is_rejected():
    client = RazorpayClientWrapper()
    secret = "whsec_test_secret"
    body = json.dumps({"event": "payment.failed"}).encode("utf-8")
    real_signature = _sign(body, secret)
    tampered_signature = real_signature[:-4] + "0000"

    assert client.verify_webhook_signature(body, tampered_signature, secret) is False


def test_wrong_secret_is_rejected():
    client = RazorpayClientWrapper()
    body = json.dumps({"event": "payment.failed"}).encode("utf-8")
    signature = _sign(body, "correct_secret")

    assert client.verify_webhook_signature(body, signature, "wrong_secret") is False


def test_missing_signature_is_rejected():
    client = RazorpayClientWrapper()
    body = json.dumps({"event": "payment.failed"}).encode("utf-8")

    assert client.verify_webhook_signature(body, None, "any_secret") is False


def test_empty_secret_is_rejected():
    client = RazorpayClientWrapper()
    body = json.dumps({"event": "payment.failed"}).encode("utf-8")
    signature = _sign(body, "some_secret")

    assert client.verify_webhook_signature(body, signature, "") is False
