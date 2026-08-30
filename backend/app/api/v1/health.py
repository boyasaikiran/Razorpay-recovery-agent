"""
GET /api/v1/health

Basic liveness check. Deliberately has zero dependencies (no DB, no
external calls) so it can always answer even if downstream systems
(Phase 2+) are degraded.
"""
from fastapi import APIRouter
from pydantic import BaseModel

from app.core.config import get_settings

router = APIRouter()


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str


@router.get("/health", response_model=HealthResponse, tags=["health"])
async def health() -> HealthResponse:
    settings = get_settings()
    return HealthResponse(
        status="ok",
        service=settings.app_name,
        version=settings.app_version,
    )
