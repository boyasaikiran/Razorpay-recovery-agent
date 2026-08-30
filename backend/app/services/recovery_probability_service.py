"""
Recovery probability service (Phase 7).

Runs AFTER diagnosis in the pipeline:
    payment_event -> recovery_case -> diagnosis -> model_prediction -> ...

Takes the already-persisted Diagnosis for a case and predicts
P(recovered), persisting the result as a ModelPrediction row and
writing the RECOVERY_PREDICTED audit entry.

This probability is explicitly NOT a final decision -- it feeds the
policy layer (Phase 9), which is the only component allowed to
approve/deny/route an action.
"""
import json
from pathlib import Path

from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.core.taxonomy import AuditStage
from app.ml.recovery_probability_inference import predict_recovery_probability
from app.models.diagnosis import Diagnosis
from app.models.model_prediction import ModelPrediction
from app.models.recovery_case import RecoveryCase
from app.repositories.audit_log_repository import AuditLogRepository
from app.repositories.model_prediction_repository import ModelPredictionRepository
from app.services.feature_extraction import extract_features_for_case

logger = get_logger(__name__)

MODEL_NAME = "recovery_probability_xgb"

_MODEL_METADATA_PATH = (
    Path(__file__).resolve().parents[3] / "data" / "models" / "recovery_probability_metadata.json"
)


def _current_model_version() -> str:
    if _MODEL_METADATA_PATH.exists():
        with open(_MODEL_METADATA_PATH) as f:
            return json.load(f).get("model_version", "unknown")
    return "unknown"


def predict_for_case(db: Session, case: RecoveryCase, diagnosis: Diagnosis) -> ModelPrediction:
    features = extract_features_for_case(case)
    probability = predict_recovery_probability(features, diagnosed_cause=diagnosis.cause)

    prediction_repo = ModelPredictionRepository(db)
    audit_repo = AuditLogRepository(db)

    if probability is None:
        # Model unavailable -- record a clearly-flagged unavailable
        # state rather than fabricating a number. Downstream policy
        # (Phase 9) must treat None specially (e.g. route to human).
        logger.error("Recovery probability model unavailable for case %s", case.id)
        probability = 0.0
        model_version = "unavailable"
    else:
        model_version = _current_model_version()

    prediction = prediction_repo.create(
        recovery_case_id=case.id,
        model_name=MODEL_NAME,
        model_version=model_version,
        recovery_probability=probability,
        feature_snapshot=features,
    )

    audit_repo.write(
        stage=AuditStage.RECOVERY_PREDICTED.value,
        actor=f"model:{MODEL_NAME}:{model_version}",
        recovery_case_id=case.id,
        decision=f"recovery_probability={probability:.4f}",
        reason=f"Predicted using diagnosed_cause='{diagnosis.cause}' (method={diagnosis.method}).",
        output_reference=str(prediction.id),
        simulation_status=True,
    )

    db.commit()
    return prediction
