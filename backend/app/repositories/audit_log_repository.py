import uuid
from typing import Optional

from sqlalchemy import and_
from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog


class AuditLogRepository:
    """
    Append-only writes. No update/delete methods are exposed
    deliberately -- the audit trail (Phase 12) must be write-once.
    Query methods below are read-only and add nothing that could
    mutate history.
    """

    def __init__(self, db: Session):
        self.db = db

    def write(
        self,
        *,
        stage: str,
        actor: str,
        recovery_case_id: Optional[uuid.UUID] = None,
        decision: Optional[str] = None,
        reason: Optional[str] = None,
        input_reference: Optional[str] = None,
        output_reference: Optional[str] = None,
        simulation_status: bool = False,
    ) -> AuditLog:
        entry = AuditLog(
            recovery_case_id=recovery_case_id,
            stage=stage,
            actor=actor,
            decision=decision,
            reason=reason,
            input_reference=input_reference,
            output_reference=output_reference,
            simulation_status=simulation_status,
        )
        self.db.add(entry)
        self.db.flush()
        return entry

    def list_for_case(self, recovery_case_id: uuid.UUID) -> list[AuditLog]:
        """Full chronological trace for one case -- the 'Agent Trace' view."""
        return (
            self.db.query(AuditLog)
            .filter(AuditLog.recovery_case_id == recovery_case_id)
            .order_by(AuditLog.timestamp.asc())
            .all()
        )

    def list_filtered(
        self,
        *,
        recovery_case_id: Optional[uuid.UUID] = None,
        stage: Optional[str] = None,
        actor: Optional[str] = None,
        simulation_status: Optional[bool] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[AuditLog], int]:
        """Returns (page of results, total matching count) for the general audit-logs API."""
        query = self.db.query(AuditLog)
        filters = []
        if recovery_case_id is not None:
            filters.append(AuditLog.recovery_case_id == recovery_case_id)
        if stage is not None:
            filters.append(AuditLog.stage == stage)
        if actor is not None:
            filters.append(AuditLog.actor == actor)
        if simulation_status is not None:
            filters.append(AuditLog.simulation_status == simulation_status)
        if filters:
            query = query.filter(and_(*filters))

        total = query.count()
        items = (
            query.order_by(AuditLog.timestamp.desc())
            .limit(limit)
            .offset(offset)
            .all()
        )
        return items, total
