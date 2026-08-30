"""
Event ingestion service (Phase 3, extended in Phase 4).

Owns the idempotency contract described in the spec: if an event_id
(or idempotency_key) has already been processed, it must NOT be
processed again — the caller gets back a response describing the
existing result instead.

Both /simulate/events and /webhooks/razorpay converge on
ingest_event() below, so idempotency and case-creation logic exists
in exactly one place regardless of source.
"""
from fastapi import status
from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.core.taxonomy import AuditStage
from app.repositories.audit_log_repository import AuditLogRepository
from app.repositories.customer_repository import CustomerRepository
from app.repositories.merchant_repository import MerchantRepository
from app.repositories.payment_event_repository import PaymentEventRepository
from app.repositories.recovery_case_repository import RecoveryCaseRepository
from app.schemas.event import IngestionResponse, SimulatedEventRequest
from app.schemas.normalized_event import NormalizedEvent


def ingest_event(db: Session, event: NormalizedEvent) -> IngestionResponse:
    merchant_repo = MerchantRepository(db)
    customer_repo = CustomerRepository(db)
    event_repo = PaymentEventRepository(db)
    case_repo = RecoveryCaseRepository(db)
    audit_repo = AuditLogRepository(db)

    merchant = merchant_repo.get_by_id(event.merchant_id)
    if merchant is None:
        raise AppError(
            f"Merchant {event.merchant_id} not found.",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    # --- Idempotency check #1: idempotency_key ---
    existing_by_key = event_repo.get_by_idempotency_key(event.idempotency_key)
    if existing_by_key is not None:
        case = case_repo.get_by_payment_event_id(existing_by_key.id)
        audit_repo.write(
            stage=AuditStage.EVENT_RECEIVED.value,
            actor="system",
            recovery_case_id=case.id if case else None,
            decision="idempotent_replay",
            reason=f"idempotency_key '{event.idempotency_key}' already processed; skipped reprocessing.",
            input_reference=event.event_id,
            output_reference=str(existing_by_key.id),
            simulation_status=event.simulation_status,
        )
        db.commit()
        return IngestionResponse(
            payment_event_id=existing_by_key.id,
            recovery_case_id=case.id if case else None,
            idempotent_replay=True,
            status="already_processed",
        )

    # --- Idempotency check #2: event_id reused with a different idempotency_key ---
    existing_by_event_id = event_repo.get_by_event_id(event.event_id)
    if existing_by_event_id is not None:
        raise AppError(
            f"event_id '{event.event_id}' was already processed under a "
            f"different idempotency_key. Refusing to reprocess.",
            status_code=status.HTTP_409_CONFLICT,
        )

    # --- Not a duplicate: process as new ---
    customer = customer_repo.get_or_create(event.merchant_id, event.customer_external_id)

    db_event = event_repo.create(
        merchant_id=event.merchant_id,
        customer_id=customer.id if customer else None,
        event_id=event.event_id,
        event_type=event.event_type,
        event_timestamp=event.event_timestamp,
        source=event.source,
        payload=event.payload,
        simulation_status=event.simulation_status,
        idempotency_key=event.idempotency_key,
        amount=event.amount,
        currency=event.currency,
        payment_method=event.payment_method,
        decline_code=event.decline_code,
        attempt_number=event.attempt_number,
    )

    case = case_repo.create(
        merchant_id=event.merchant_id,
        customer_id=customer.id if customer else None,
        payment_event_id=db_event.id,
        case_type=event.event_type,
        amount_at_risk=event.amount,
        currency=event.currency,
    )

    audit_repo.write(
        stage=AuditStage.EVENT_RECEIVED.value,
        actor="system",
        recovery_case_id=case.id,
        decision="ingested",
        reason=f"New event '{event.event_id}' ingested from source='{event.source}'; recovery case opened.",
        input_reference=event.event_id,
        output_reference=str(db_event.id),
        simulation_status=event.simulation_status,
    )

    db.commit()

    return IngestionResponse(
        payment_event_id=db_event.id,
        recovery_case_id=case.id,
        idempotent_replay=False,
        status="ingested",
    )


def ingest_simulated_event(db: Session, request: SimulatedEventRequest) -> IngestionResponse:
    normalized = NormalizedEvent(
        event_id=request.event_id,
        event_type=request.event_type,
        event_timestamp=request.event_timestamp,
        source="simulated",
        payload=request.payload,
        simulation_status=True,
        idempotency_key=request.idempotency_key,
        merchant_id=request.merchant_id,
        customer_external_id=request.customer_external_id,
        amount=request.amount,
        currency=request.currency,
        payment_method=request.payment_method,
        decline_code=request.decline_code,
        attempt_number=request.attempt_number,
    )
    return ingest_event(db, normalized)
