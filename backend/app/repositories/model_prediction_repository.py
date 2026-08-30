import uuid
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.models.model_prediction import ModelPrediction


class ModelPredictionRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(
        self,
        recovery_case_id: uuid.UUID,
        model_name: str,
        model_version: str,
        recovery_probability: float,
        feature_snapshot: Optional[dict[str, Any]] = None,
    ) -> ModelPrediction:
        prediction = ModelPrediction(
            recovery_case_id=recovery_case_id,
            model_name=model_name,
            model_version=model_version,
            recovery_probability=recovery_probability,
            feature_snapshot=feature_snapshot,
        )
        self.db.add(prediction)
        self.db.flush()
        return prediction
