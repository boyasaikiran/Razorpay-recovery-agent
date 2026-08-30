"""
Diagnosis orchestrator (Phase 6).

PATH PRECEDENCE (a design decision not fully pinned down by the spec's
prose — stated explicitly here rather than left implicit):

  1. Path A (rule-based): if decline_code is present AND recognized by
     RULE_BASED_DECLINE_CODE_MAP, use it. Deterministic, high
     confidence, no model call needed.
  2. Path C (LLM): if Path A didn't resolve it AND free_text_context is
     non-empty (rich unstructured signal available — support chat,
     session notes), prefer the LLM since it's the only path that can
     read free text.
  3. Path B (XGBoost): otherwise — decline_code absent/unrecognized and
     no free text, i.e. purely structured signals.
  4. If Path C is selected but LLM_API_KEY isn't configured, fall back
     to Path B rather than crashing the pipeline (logged clearly).

Confidence threshold: results below DIAGNOSIS_CONFIDENCE_THRESHOLD are
flagged via requires_human_review() but NOT blocked here — Phase 6's
job is accurate diagnosis; refusing to execute a risky action on low
confidence is the deterministic POLICY ENGINE's job (Phase 9), per the
spec's core safety principle ("LLM proposes, policy engine disposes").
"""
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.core.taxonomy import AuditStage
from app.llm.cause_classifier import LLMNotConfiguredError, diagnose_llm
from app.ml.cause_classifier_inference import diagnose_xgboost
from app.models.diagnosis import Diagnosis
from app.models.recovery_case import RecoveryCase
from app.repositories.audit_log_repository import AuditLogRepository
from app.repositories.diagnosis_repository import DiagnosisRepository
from app.schemas.diagnosis import DiagnosisResult
from app.services.diagnosis_rule_based import diagnose_rule_based
from app.services.feature_extraction import extract_features_for_case

logger = get_logger(__name__)

DIAGNOSIS_CONFIDENCE_THRESHOLD = 0.6


def requires_human_review(result: DiagnosisResult) -> bool:
    return result.confidence < DIAGNOSIS_CONFIDENCE_THRESHOLD


def diagnose_from_features(feature_dict: dict[str, Any]) -> DiagnosisResult:
    """
    Pure function: given a feature dict, runs the Path A/B/C cascade
    and returns a DiagnosisResult. No DB access — testable directly
    without a database.
    """
    decline_code = feature_dict.get("decline_code")
    raw_free_text = feature_dict.get("free_text_context")
    # Defends against pandas NaN (a float, truthy in Python) as well as
    # None/missing — both are legitimate "no free text" inputs when
    # feature dicts are built from DataFrame rows (see
    # app/ml/train_recovery_probability.py).
    free_text = "" if raw_free_text is None or (isinstance(raw_free_text, float) and raw_free_text != raw_free_text) else str(raw_free_text)

    # Path A
    rule_result = diagnose_rule_based(decline_code)
    if rule_result is not None:
        return rule_result

    # Path C preferred when there's free text to read
    if free_text.strip():
        try:
            return diagnose_llm(feature_dict)
        except LLMNotConfiguredError as e:
            logger.info("Path C unavailable (%s); falling back to Path B.", e)

    # Path B
    xgb_result = diagnose_xgboost(feature_dict)
    if xgb_result is not None:
        return xgb_result

    # Nothing worked (no rule match, no LLM, no trained model available).
    from app.core.taxonomy import Cause, DiagnosisMethod

    logger.error("All diagnosis paths unavailable; returning unknown/0 confidence.")
    return DiagnosisResult(
        cause=Cause.UNKNOWN.value,
        confidence=0.0,
        reason="No diagnosis path was able to produce a result (Path A no match, "
        "Path C unavailable/skipped, Path B model not trained).",
        signals=[],
        method=DiagnosisMethod.RULE_BASED.value,
    )


def diagnose_case(db: Session, case: RecoveryCase) -> Diagnosis:
    """
    Full pipeline: extract features from the case, run the diagnosis
    cascade, persist the result, write the audit log entry. Returns
    the persisted Diagnosis DB row.
    """
    features = extract_features_for_case(case)
    result = diagnose_from_features(features)

    diagnosis_repo = DiagnosisRepository(db)
    audit_repo = AuditLogRepository(db)

    # Spec's audit stage list explicitly includes CONTEXT_RETRIEVED --
    # feature extraction from payment_event/customer/payload IS the
    # "context" being retrieved for diagnosis. Logged before
    # classification so the trace shows what was known before the
    # diagnosis was made.
    audit_repo.write(
        stage=AuditStage.CONTEXT_RETRIEVED.value,
        actor="feature_extraction",
        recovery_case_id=case.id,
        decision=None,
        reason=f"Extracted {sum(1 for v in features.values() if v not in (None, '', []))} "
        f"non-null feature(s) for cause classification.",
        simulation_status=True,
    )

    diagnosis = diagnosis_repo.create(recovery_case_id=case.id, result=result)

    audit_repo.write(
        stage=AuditStage.CAUSE_CLASSIFIED.value,
        actor=f"diagnosis:{result.method}",
        recovery_case_id=case.id,
        decision=result.cause,
        reason=result.reason,
        output_reference=str(diagnosis.id),
        simulation_status=True,
    )

    if requires_human_review(result):
        audit_repo.write(
            stage=AuditStage.HUMAN_ESCALATED.value,
            actor="diagnosis_service",
            recovery_case_id=case.id,
            decision="route_to_human",
            reason=f"Diagnosis confidence {result.confidence:.2f} below threshold "
            f"{DIAGNOSIS_CONFIDENCE_THRESHOLD}.",
            simulation_status=True,
        )

    db.commit()
    return diagnosis
