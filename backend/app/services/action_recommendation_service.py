"""
Action recommendation (Phase 8).

Proposes exactly one action from the fixed 7-action set (RETRY_PAYMENT,
DELAYED_RETRY, CREATE_PAYMENT_LINK, SEND_NOTIFICATION,
LOG_PROMISE_TO_PAY, ESCALATE_TO_HUMAN, STOP_RECOVERY). Cannot invent a
new action -- the return type is validated against ALL_ACTIONS via
ActionRecommendation's Pydantic validator, and the mapping this reads
from (CAUSE_TO_DEFAULT_ACTION) only contains values from that same
enum, so an unrecognized action is structurally unreachable, not just
policy-forbidden.

This is a pure function over (cause, confidence, recovery_probability)
-- no DB access, no LLM call. In the full agent loop (Phase 10), the
LLM decides WHEN to call the select_action tool and interprets its
result; this function IS what select_action executes. The LLM does
not freely choose an action string.
"""
from typing import Optional

from app.core.action_mapping import CAUSE_TO_DEFAULT_ACTION, LOW_RECOVERY_PROBABILITY_THRESHOLD
from app.core.taxonomy import RecoveryAction
from app.schemas.action_recommendation import ActionRecommendation
from app.schemas.diagnosis import DiagnosisResult
from app.services.diagnosis_service import DIAGNOSIS_CONFIDENCE_THRESHOLD, requires_human_review


def recommend_action(
    diagnosis: DiagnosisResult, recovery_probability: Optional[float]
) -> ActionRecommendation:
    if requires_human_review(diagnosis):
        return ActionRecommendation(
            action=RecoveryAction.ESCALATE_TO_HUMAN.value,
            reason=(
                f"Diagnosis confidence {diagnosis.confidence:.2f} is below the "
                f"{DIAGNOSIS_CONFIDENCE_THRESHOLD} threshold; recommending human review "
                f"rather than an automated action."
            ),
        )

    if recovery_probability is not None and recovery_probability < LOW_RECOVERY_PROBABILITY_THRESHOLD:
        return ActionRecommendation(
            action=RecoveryAction.STOP_RECOVERY.value,
            reason=(
                f"Recovery probability {recovery_probability:.2f} is below the "
                f"{LOW_RECOVERY_PROBABILITY_THRESHOLD} threshold; recommending no further "
                f"automated recovery attempts for cause '{diagnosis.cause}'."
            ),
        )

    default_action = CAUSE_TO_DEFAULT_ACTION.get(diagnosis.cause, RecoveryAction.ESCALATE_TO_HUMAN.value)
    return ActionRecommendation(
        action=default_action,
        reason=f"Default action for diagnosed cause '{diagnosis.cause}' "
        f"(confidence={diagnosis.confidence:.2f}, "
        f"recovery_probability={recovery_probability if recovery_probability is not None else 'unavailable'}).",
    )


def recommend_action_for_case(db, case, diagnosis_row, prediction_row) -> ActionRecommendation:
    """
    DB-touching wrapper: builds a DiagnosisResult from the persisted
    Diagnosis row, calls recommend_action(), writes the ACTION_PROPOSED
    audit entry. Does NOT create a Decision row -- that happens in
    Phase 9 once the policy engine has also run, since Decision couples
    proposed_action and policy_decision in a single (both NOT NULL) row
    by design.
    """
    from app.core.taxonomy import AuditStage
    from app.repositories.audit_log_repository import AuditLogRepository

    diagnosis_result = DiagnosisResult(
        cause=diagnosis_row.cause,
        confidence=diagnosis_row.confidence,
        reason=diagnosis_row.reason or "",
        signals=diagnosis_row.signals or [],
        method=diagnosis_row.method,
    )
    recovery_probability = prediction_row.recovery_probability if prediction_row else None

    recommendation = recommend_action(diagnosis_result, recovery_probability)

    audit_repo = AuditLogRepository(db)
    audit_repo.write(
        stage=AuditStage.ACTION_PROPOSED.value,
        actor="action_recommendation_service",
        recovery_case_id=case.id,
        decision=recommendation.action,
        reason=recommendation.reason,
        simulation_status=True,
    )
    db.commit()

    return recommendation
