"""
Parses a validated Razorpay webhook body into a NormalizedEvent.

Mapping honesty policy (per spec's "No Fake Claims" section):
  Only event types whose payload shape has been directly confirmed
  against official Razorpay documentation are mapped to our internal
  taxonomy. Everything else is acknowledged (200, so Razorpay doesn't
  retry-storm us) but recorded as UNMAPPED rather than guessed at.

VERIFIED (against https://razorpay.com/docs/webhooks/payments/ and
the Axis Bank / Razorpay docs mirror, both official Razorpay-published
sources, on this date):
  event = "payment.failed"
  payload.payment.entity: {
    id, entity, amount, currency, status, order_id, invoice_id,
    method, card_id, card, bank, wallet, vpa, email, contact,
    customer_id, notes, error_code, error_description, created_at, ...
  }
  Top-level envelope: { entity: "event", account_id, event, contains, payload, created_at }

NOT YET VERIFIED in this session (left unmapped rather than guessed):
  subscription.* events, invoice.* events, payment.captured,
  payment.authorized — these exist per Razorpay's docs index but their
  exact payload shapes were not fetched and confirmed in this session.
  Enabling them requires repeating the same doc-verification step
  before writing the mapping.
"""
from datetime import datetime, timezone
from typing import Any, Optional

from app.core.taxonomy import EventType

# Only event types confirmed against official docs in this session.
_VERIFIED_EVENT_TYPE_MAP = {
    "payment.failed": EventType.PAYMENT_FAILED.value,
}


class UnmappedWebhookEvent(Exception):
    """Raised when a webhook event type has no verified mapping yet."""

    def __init__(self, razorpay_event_type: str):
        self.razorpay_event_type = razorpay_event_type
        super().__init__(
            f"Razorpay event type '{razorpay_event_type}' has no doc-verified "
            f"mapping to our internal taxonomy yet."
        )


def parse_razorpay_webhook(body: dict[str, Any]) -> dict[str, Any]:
    """
    Returns a dict of fields suitable for constructing a NormalizedEvent
    (minus merchant_id/idempotency_key, which the caller supplies from
    the account_id lookup and the x-razorpay-event-id header).

    Raises UnmappedWebhookEvent for event types not in the verified map.
    """
    razorpay_event_type = body.get("event")
    if razorpay_event_type not in _VERIFIED_EVENT_TYPE_MAP:
        raise UnmappedWebhookEvent(razorpay_event_type or "<missing>")

    internal_event_type = _VERIFIED_EVENT_TYPE_MAP[razorpay_event_type]
    account_id = body.get("account_id")

    payment_entity = (
        body.get("payload", {}).get("payment", {}).get("entity", {})
    )

    amount_paise = payment_entity.get("amount")
    amount = (amount_paise / 100) if isinstance(amount_paise, (int, float)) else None

    created_at_epoch = body.get("created_at")
    event_timestamp = (
        datetime.fromtimestamp(created_at_epoch, tz=timezone.utc)
        if isinstance(created_at_epoch, (int, float))
        else datetime.now(timezone.utc)
    )

    return {
        "account_id": account_id,
        "event_type": internal_event_type,
        "event_timestamp": event_timestamp,
        "customer_external_id": payment_entity.get("customer_id"),
        "amount": amount,
        "currency": payment_entity.get("currency"),
        "payment_method": payment_entity.get("method"),
        "decline_code": payment_entity.get("error_code"),
        "razorpay_payment_id": payment_entity.get("id"),
    }
