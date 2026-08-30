import uuid
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.models.diagnosis import Diagnosis
from app.schemas.diagnosis import DiagnosisResult


class DiagnosisRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(
        self,
        recovery_case_id: uuid.UUID,
        result: DiagnosisResult,
        raw_llm_output: Optional[dict[str, Any]] = None,
    ) -> Diagnosis:
        diagnosis = Diagnosis(
            recovery_case_id=recovery_case_id,
            cause=result.cause,
            confidence=result.confidence,
            method=result.method,
            reason=result.reason,
            signals=result.signals,
            raw_llm_output=raw_llm_output,
        )
        self.db.add(diagnosis)
        self.db.flush()
        return diagnosis
