"""
Bridges the relational schema (Phase 2) to the feature dict shape
diagnosis Path B/C expect (matching app/ml/feature_schema.py's
FEATURE_CANDIDATE_COLUMNS).

KNOWN LIMITATION (stated plainly): our PaymentEvent/Customer tables
store a subset of the full synthetic-data feature set as dedicated
columns (decline_code, amount, currency, payment_method,
attempt_number, event_type from PaymentEvent; customer_segment,
customer_lifetime_value, consent_status from Customer). The richer
behavioral/B2B fields (session_duration_seconds, b2b_*, network,
issuer_bank_code, geo_region, device_type, channel_history,
otp_attempted, is_recurring, previous_recovery_rate,
days_since_last_success, card_age_days, subscription_value) are not
modeled as dedicated columns — a real system would need to either add
those columns or reliably populate them via the ingestion payload.
For MVP, this function reads them from PaymentEvent.payload (JSONB)
when the caller supplied them there (both /simulate/events and the
Razorpay webhook accept arbitrary payload content), defaulting to None
otherwise. XGBoost handles missing values natively (see Path B), so
this degrades gracefully rather than breaking.
"""
from typing import Any

from app.models.customer import Customer
from app.models.payment_event import PaymentEvent
from app.models.recovery_case import RecoveryCase


def extract_features_for_case(case: RecoveryCase) -> dict[str, Any]:
    event: PaymentEvent = case.payment_event
    customer: Customer | None = None
    # RecoveryCase.customer_id is set; the ORM relationship isn't
    # defined on RecoveryCase for Customer directly (only via
    # payment_event.customer_id), so callers must load it explicitly
    # if needed. Payload-sourced fields are the primary path for MVP.
    payload = event.payload or {}

    features: dict[str, Any] = {
        "event_type": event.event_type,
        "amount": float(event.amount) if event.amount is not None else None,
        "currency": event.currency,
        "payment_method": event.payment_method,
        "decline_code": event.decline_code,
        "attempt_number": event.attempt_number,
        "days_since_last_success": payload.get("days_since_last_success"),
        "customer_lifetime_value": payload.get("customer_lifetime_value"),
        "subscription_value": payload.get("subscription_value"),
        "customer_segment": payload.get("customer_segment"),
        "previous_recovery_rate": payload.get("previous_recovery_rate"),
        "session_duration_seconds": payload.get("session_duration_seconds"),
        "otp_attempted": payload.get("otp_attempted", False),
        "free_text_context": payload.get("free_text_context", ""),
        "b2b_invoice_days_overdue": payload.get("b2b_invoice_days_overdue"),
        "b2b_promise_count": payload.get("b2b_promise_count"),
        "b2b_broken_promise_count": payload.get("b2b_broken_promise_count"),
        "risk_flag": payload.get("risk_flag", False),
        "consent_status": payload.get("consent_status"),
        "channel_history": payload.get("channel_history", "[]"),
        "card_age_days": payload.get("card_age_days"),
        "network": payload.get("network"),
        "issuer_bank_code": payload.get("issuer_bank_code"),
        "geo_region": payload.get("geo_region"),
        "device_type": payload.get("device_type"),
        "is_recurring": payload.get("is_recurring", event.event_type == "subscription_renewal_failed"),
    }
    return features
