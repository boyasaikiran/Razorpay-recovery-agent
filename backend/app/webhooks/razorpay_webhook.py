"""
POST /api/v1/webhooks/razorpay

Real Razorpay webhook ingestion (Phase 4). Verifies X-Razorpay-Signature
per the official algorithm before touching the payload, deduplicates on
x-razorpay-event-id, maps only doc-verified event types, and converges
on the same ingest_event() core used by /simulate/events.
"""
import json

from fastapi import APIRouter, Depends, Header, Request, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import AppError
from app.core.logging import get_logger
from app.database.session import get_db
from app.repositories.merchant_repository import MerchantRepository
from app.schemas.event import IngestionResponse
from app.schemas.normalized_event import NormalizedEvent
from app.services.ingestion_service import ingest_event
from app.services.razorpay_client import get_razorpay_client
from app.webhooks.razorpay_parser import UnmappedWebhookEvent, parse_razorpay_webhook

logger = get_logger(__name__)
router = APIRouter()


@router.post(
    "/webhooks/razorpay",
    status_code=status.HTTP_200_OK,
    tags=["webhooks"],
)
async def razorpay_webhook(
    request: Request,
    db: Session = Depends(get_db),
    x_razorpay_signature: str = Header(None, alias="X-Razorpay-Signature"),
    x_razorpay_event_id: str = Header(None, alias="x-razorpay-event-id"),
):
    settings = get_settings()
    raw_body = await request.body()

    # --- Signature verification (over the RAW body, per Razorpay docs) ---
    client = get_razorpay_client()
    if not client.verify_webhook_signature(
        raw_body, x_razorpay_signature, settings.razorpay_webhook_secret
    ):
        raise AppError(
            "Webhook signature verification failed.",
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    body = json.loads(raw_body)

    # --- Map to internal taxonomy; honestly skip what isn't verified ---
    try:
        parsed = parse_razorpay_webhook(body)
    except UnmappedWebhookEvent as e:
        logger.info("Unmapped Razorpay webhook event acknowledged: %s", e.razorpay_event_type)
        return {"status": "acknowledged", "mapped": False, "razorpay_event_type": e.razorpay_event_type}

    merchant = MerchantRepository(db).get_by_razorpay_merchant_id(parsed["account_id"])
    if merchant is None:
        raise AppError(
            f"No merchant found for Razorpay account_id '{parsed['account_id']}'.",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    # Razorpay guarantees x-razorpay-event-id is unique per event; use it
    # as both event_id and idempotency_key if the payload has no more
    # specific ID (e.g. the payment ID) to key on.
    event_id = parsed.get("razorpay_payment_id") or x_razorpay_event_id
    idempotency_key = x_razorpay_event_id or event_id

    normalized = NormalizedEvent(
        event_id=event_id,
        event_type=parsed["event_type"],
        event_timestamp=parsed["event_timestamp"],
        source="razorpay",
        payload=body,
        simulation_status=False,
        idempotency_key=idempotency_key,
        merchant_id=merchant.id,
        customer_external_id=parsed.get("customer_external_id"),
        amount=parsed.get("amount"),
        currency=parsed.get("currency"),
        payment_method=parsed.get("payment_method"),
        decline_code=parsed.get("decline_code"),
    )

    result: IngestionResponse = ingest_event(db, normalized)
    return result
