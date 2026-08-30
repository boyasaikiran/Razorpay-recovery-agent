"""
Thin wrapper around the official Razorpay Python SDK (pip package
`razorpay`, confirmed current as of this writing via
https://github.com/razorpay/razorpay-python).

CRITICAL SEPARATION (per spec Phase 4):
  REAL_RAZORPAY      -> actual calls through razorpay.Client, used only
                         when RAZORPAY_KEY_ID/SECRET are configured and
                         razorpay_mode is "test" or "live".
  SIMULATED_RAZORPAY -> no network call at all; returns a locally
                         generated response shaped like Razorpay's, with
                         "simulated": true always present.

No other module should import `razorpay` directly or call Razorpay's
API — everything routes through this wrapper so the REAL/SIMULATED
boundary is enforced in exactly one place.

VERIFIED FACTS (confirmed against https://razorpay.com/docs/webhooks/
validate-test/ and https://github.com/razorpay/razorpay-python on this
date):
  - Signature header: X-Razorpay-Signature
  - Signature scheme: HMAC-SHA256(hex), keyed with the webhook secret,
    computed over the RAW request body (never the parsed/re-serialized
    body).
  - Duplicate-delivery detection header: x-razorpay-event-id (unique
    per event).

NOT VERIFIED / NOT IMPLEMENTED YET:
  This sandbox has no network path to api.razorpay.com (not on the
  outbound allowlist) and no real Razorpay test-mode credentials were
  provided. REAL_RAZORPAY methods below are implemented against the
  documented SDK interface but have NOT been exercised against a live
  Razorpay account. Only the signature-verification logic (pure HMAC,
  no network) has been exercised end-to-end against real, correct and
  tampered inputs.
"""
import hashlib
import hmac
from typing import Any, Optional

import razorpay

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class RazorpayMode:
    REAL = "REAL_RAZORPAY"
    SIMULATED = "SIMULATED_RAZORPAY"


class RazorpayClientWrapper:
    def __init__(self):
        settings = get_settings()
        self._settings = settings
        self._has_credentials = bool(settings.razorpay_key_id and settings.razorpay_key_secret)
        self._configured_mode = settings.razorpay_mode  # "simulated" | "test" | "live"

        if self._configured_mode in ("test", "live") and self._has_credentials:
            self.mode = RazorpayMode.REAL
            self._sdk_client: Optional[razorpay.Client] = razorpay.Client(
                auth=(settings.razorpay_key_id, settings.razorpay_key_secret)
            )
        else:
            self.mode = RazorpayMode.SIMULATED
            self._sdk_client = None

    @property
    def is_real(self) -> bool:
        return self.mode == RazorpayMode.REAL

    # ------------------------------------------------------------------
    # Webhook signature verification — pure HMAC, no network call.
    # Algorithm confirmed directly against Razorpay's official docs and
    # the official SDK's implementation.
    # ------------------------------------------------------------------
    def verify_webhook_signature(self, raw_body: bytes, signature: str, secret: str) -> bool:
        if not secret:
            logger.warning("verify_webhook_signature called with empty secret")
            return False
        expected = hmac.new(
            key=secret.encode("utf-8"), msg=raw_body, digestmod=hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(expected, signature or "")

    # ------------------------------------------------------------------
    # Orders / Payments / Subscriptions / Invoices / Payment Links
    #
    # Each method: REAL mode delegates to the SDK; SIMULATED mode
    # returns a locally built, clearly-labeled stand-in. NOT exercised
    # against a live account in this environment (see module docstring).
    # ------------------------------------------------------------------
    def fetch_payment(self, payment_id: str) -> dict[str, Any]:
        if self.is_real:
            return self._sdk_client.payment.fetch(payment_id)
        return {
            "id": payment_id,
            "entity": "payment",
            "status": "failed",
            "simulated": True,
        }

    def create_payment_link(self, *, amount: int, currency: str, description: str) -> dict[str, Any]:
        if self.is_real:
            return self._sdk_client.payment_link.create(
                {"amount": amount, "currency": currency, "description": description}
            )
        return {
            "id": "plink_simulated_0000000000",
            "entity": "payment_link",
            "short_url": "https://rzp.io/simulated-link",
            "amount": amount,
            "currency": currency,
            "status": "created",
            "simulated": True,
        }

    def fetch_subscription(self, subscription_id: str) -> dict[str, Any]:
        if self.is_real:
            return self._sdk_client.subscription.fetch(subscription_id)
        return {
            "id": subscription_id,
            "entity": "subscription",
            "status": "active",
            "simulated": True,
        }

    def fetch_invoice(self, invoice_id: str) -> dict[str, Any]:
        if self.is_real:
            return self._sdk_client.invoice.fetch(invoice_id)
        return {
            "id": invoice_id,
            "entity": "invoice",
            "status": "issued",
            "simulated": True,
        }


_client_singleton: Optional[RazorpayClientWrapper] = None


def get_razorpay_client() -> RazorpayClientWrapper:
    global _client_singleton
    if _client_singleton is None:
        _client_singleton = RazorpayClientWrapper()
    return _client_singleton
