"""
Policy service (Phase 9): wires the pure evaluate_policy() engine to
the database. Resolves the Policy config for a cause, evaluates,
persists the Decision row (proposed_action + policy_decision together,
per the schema), and writes the POLICY_CHECKED audit entry.

FAIL-SAFE DEFAULT: if no Policy row exists in the DB for a cause, this
does NOT fall back to permissive defaults or silently approve. It
returns ROUTE_TO_HUMAN with rule_triggered="no_policy_configured".
Missing configuration is a reason for caution, not a bypass.
"""
from app.core.taxonomy import AuditStage, PolicyDecision
from app.policies.policy_engine import evaluate_policy
from app.repositories.audit_log_repository import AuditLogRepository
from app.repositories.decision_repository import DecisionRepository
from app.repositories.policy_repository import PolicyRepository
from app.schemas.policy import PolicyEvaluationResult


def check_policy_for_case(
    db,
    case,
    diagnosis_row,
    proposed_action,
    attempt_number,
    risk_flag,
    consent_status,
    channel_history,
    amount,
):
    policy_repo = PolicyRepository(db)
    decision_repo = DecisionRepository(db)
    audit_repo = AuditLogRepository(db)

    policy = policy_repo.get_by_cause(diagnosis_row.cause)

    if policy is None:
        result = PolicyEvaluationResult(
            decision=PolicyDecision.ROUTE_TO_HUMAN.value,
            reason=f"No policy is configured for cause '{diagnosis_row.cause}'; failing safe "
            f"to human review rather than approving without a policy.",
            rule_triggered="no_policy_configured",
        )
    else:
        result = evaluate_policy(
            proposed_action,
            diagnosis_row.cause,
            diagnosis_row.confidence,
            attempt_number,
            risk_flag,
            consent_status,
            channel_history,
            amount,
            policy,
        )

    decision = decision_repo.create(
        recovery_case_id=case.id,
        proposed_action=proposed_action,
        policy_decision=result.decision,
        policy_reason=result.reason,
        policy_rule_triggered=result.rule_triggered,
    )

    audit_repo.write(
        stage=AuditStage.POLICY_CHECKED.value,
        actor="policy_engine",
        recovery_case_id=case.id,
        decision=result.decision,
        reason=result.reason,
        input_reference=proposed_action,
        output_reference=str(decision.id),
        simulation_status=True,
    )

    if result.decision == PolicyDecision.ROUTE_TO_HUMAN.value:
        audit_repo.write(
            stage=AuditStage.HUMAN_ESCALATED.value,
            actor="policy_engine",
            recovery_case_id=case.id,
            decision="route_to_human",
            reason=result.reason,
            simulation_status=True,
        )

    db.commit()
    return decision
