"""
GET /api/v1/audit-logs

General-purpose, filterable audit log query endpoint.
"""
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.repositories.audit_log_repository import AuditLogRepository
from app.schemas.audit_log import AuditLogListResponse

router = APIRouter()


@router.get("/audit-logs", response_model=AuditLogListResponse, tags=["audit"])
async def list_audit_logs(
    case_id: Optional[uuid.UUID] = Query(None, description="Filter by recovery_case_id"),
    stage: Optional[str] = Query(None, description="Filter by pipeline stage, e.g. CAUSE_CLASSIFIED"),
    actor: Optional[str] = Query(None, description="Filter by actor"),
    simulation_status: Optional[bool] = Query(None, description="Filter by simulated vs real"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> AuditLogListResponse:
    repo = AuditLogRepository(db)
    items, total = repo.list_filtered(
        recovery_case_id=case_id,
        stage=stage,
        actor=actor,
        simulation_status=simulation_status,
        limit=limit,
        offset=offset,
    )
    return AuditLogListResponse(items=items, total=total, limit=limit, offset=offset)
