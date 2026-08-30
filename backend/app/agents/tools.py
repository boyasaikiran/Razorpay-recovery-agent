"""
Agent tool implementations (Phase 10).

These wrap the domain services built in Phases 6-9. tool_execute_recovery
contains THE critical safety guard of this entire codebase: it
structurally refuses to run against anything but an APPROVED Decision.
Read its docstring before touching this file.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.taxonomy import AuditStage, PolicyDecision
from app.models.action import Action
from app.models.decision import Decision
from app.models.diagnosis import Diagnosis
from app.models.model_prediction import ModelPrediction
from app.models.recovery_case import RecoveryCase
from app.repositories.audit_log_repository import AuditLogRepository
from app.schemas.action_recommendation import ActionRecommendation
from app.services.action_recommendation_service import recommend_action_for_case
from app.services.diagnosis_service import diagnose_case
from app.services.policy_service import check_policy_for_case


def tool_classify_cause(db: Session, case: RecoveryCase) -> Diagnosis:
    """See TOOL_CONTRACTS["classify_cause"]. Wraps Phase 6's diagnose_case."""
    return diagnose_case(db, case)


def tool_select_action(
    db: Session, case: RecoveryCase, diagnosis_row: Diagnosis, prediction_row: ModelPrediction
) -> ActionRecommendation:
    """See TOOL_CONTRACTS["select_action"]. Wraps Phase 8's recommend_action_for_case."""
    return recommend_action_for_case(db, case, diagnosis_row, prediction_row)


def tool_check_policy(
    db: Session,
    case: RecoveryCase,
    diagnosis_row: Diagnosis,
    proposed_action: str,
    attempt_number,
    risk_flag,
    consent_status,
    channel_history,
    amount,
) -> Decision:
    """See TOOL_CONTRACTS["check_policy"]. Wraps Phase 9's check_policy_for_case."""
    return check_policy_for_case(
        db, case, diagnosis_row, proposed_action,
        attempt_number, risk_flag, consent_status, channel_history, amount,
    )


class ExecutionNotApprovedError(PermissionError):
    """
    Raised when tool_execute_recovery is called against a Decision that
    was not APPROVED by the policy engine. This is the structural
    enforcement of "LLM proposes, policy engine disposes" -- a Python
    exception, not a system-prompt instruction, so no LLM output,
    prompt injection, or caller bug can bypass it.
    """


def tool_execute_recovery(db: Session, decision: Decision) -> Action:
    """
    See TOOL_CONTRACTS["execute_recovery"].

    CRITICAL GUARD: only proceeds if decision.policy_decision ==
    PolicyDecision.APPROVED.value. Any other value raises
    ExecutionNotApprovedError and writes NOTHING to the actions table.

    Creates the Action row (status="pending_execution"). Does NOT yet
    simulate a success/failure outcome -- that is Phase 11's job.
    Phase 10's scope is the tool-calling loop and its safety guard;
    Phase 11 fills in what "executing" each action type produces.
    """
    if decision.policy_decision != PolicyDecision.APPROVED.value:
        audit_repo = AuditLogRepository(db)
        audit_repo.write(
            stage=AuditStage.ACTION_EXECUTED.value,
            actor="agent_loop",
            recovery_case_id=decision.recovery_case_id,
            decision="execution_refused",
            reason=f"Refused to execute: Decision {decision.id} has policy_decision="
            f"'{decision.policy_decision}', not APPROVED.",
            simulation_status=True,
        )
        db.commit()
        raise ExecutionNotApprovedError(
            f"Cannot execute: Decision {decision.id} policy_decision is "
            f"'{decision.policy_decision}', not APPROVED."
        )

    action = Action(
        decision_id=decision.id,
        recovery_case_id=decision.recovery_case_id,
        action_type=decision.proposed_action,
        status="pending_execution",
        simulated=True,
        executed_at=datetime.now(timezone.utc),
    )
    db.add(action)
    db.flush()

    audit_repo = AuditLogRepository(db)
    audit_repo.write(
        stage=AuditStage.ACTION_EXECUTED.value,
        actor="agent_loop",
        recovery_case_id=decision.recovery_case_id,
        decision=decision.proposed_action,
        reason=f"Executed approved action '{decision.proposed_action}' for Decision {decision.id}.",
        output_reference=str(action.id),
        simulation_status=True,
    )
    db.commit()
    return action


def tool_log_audit(
    db: Session,
    stage: str,
    actor: str,
    recovery_case_id: uuid.UUID = None,
    decision: str = None,
    reason: str = None,
    simulation_status: bool = True,
):
    """See TOOL_CONTRACTS["log_audit"]. Direct pass-through to AuditLogRepository.write."""
    audit_repo = AuditLogRepository(db)
    entry = audit_repo.write(
        stage=stage,
        actor=actor,
        recovery_case_id=recovery_case_id,
        decision=decision,
        reason=reason,
        simulation_status=simulation_status,
    )
    db.commit()
    return entry
