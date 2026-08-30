"""
POST /api/v1/simulate/events

Schema-compatible simulated event ingestion (Phase 3). Real Razorpay
webhook ingestion is a separate endpoint (Phase 4).
"""
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.rate_limit import rate_limit_simulate_events
from app.core.security import require_api_key
from app.database.session import get_db
from app.schemas.event import IngestionResponse, SimulatedEventRequest
from app.services.ingestion_service import ingest_simulated_event

router = APIRouter()


@router.post(
    "/simulate/events",
    response_model=IngestionResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["ingestion"],
    dependencies=[Depends(require_api_key), Depends(rate_limit_simulate_events)],
)
async def simulate_event(
    request: SimulatedEventRequest, db: Session = Depends(get_db)
) -> IngestionResponse:
    return ingest_simulated_event(db, request)
