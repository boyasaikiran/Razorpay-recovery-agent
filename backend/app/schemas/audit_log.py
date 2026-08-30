import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class AuditLogEntry(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    recovery_case_id: Optional[uuid.UUID]
    timestamp: datetime
    stage: str
    actor: str
    decision: Optional[str]
    reason: Optional[str]
    input_reference: Optional[str]
    output_reference: Optional[str]
    simulation_status: bool


class AuditLogListResponse(BaseModel):
    items: list[AuditLogEntry]
    total: int
    limit: int
    offset: int
