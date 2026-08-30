"""
Agent loop (Phase 10).

CORRECT FLOW (per spec):
    LLM -> classify_cause -> select_action -> check_policy ->
    execute_recovery (ONLY if APPROVED) -> log_audit

WHY THIS IS DETERMINISTIC RIGHT NOW: LLM_API_KEY is not configured in
this environment. classify_cause already attempts the LLM path
(Phase 6 Path C) when free text is present and falls back cleanly
when unconfigured -- so "the LLM" in this flow is currently inactive,
and this loop is the honest MVP fallback: a deterministic orchestrator
calling the same 5 tools in the same mandated order, with the same
safety guarantees. The tool contracts/guards do not change if an LLM
is wired in later.

THE INVARIANT THIS LOOP EXISTS TO ENFORCE: execute_recovery is called
if and only if check_policy's result was APPROVED. Enforced TWICE:
once here (the loop simply doesn't call it otherwise), and again
inside tool_execute_recovery itself (independent re-check). Defense
in depth -- a bug in this loop's if-statement would still be caught
by the tool's own guard.
"""
import json
from dataclasses import dataclass
from typing import Optional

from sqlalchemy.orm import Session

from app.agents.tools import tool_check_policy, tool_classify_cause, tool_execute_recovery, tool_select_action
from app.core.logging import get_logger
from app.core.taxonomy import PolicyDecision
from app.models.action import Action
from app.models.decision import Decision
from app.models.diagnosis import Diagnosis
from app.models.model_prediction import ModelPrediction
from app.models.outcome import Outcome
from app.models.recovery_case import RecoveryCase
from app.schemas.action_recommendation import ActionRecommendation
from app.services.execution_simulator import simulate_execution
from app.services.feature_extraction import extract_features_for_case
from app.services.recovery_probability_service import predict_for_case

logger = get_logger(__name__)


@dataclass
class AgentRunResult:
    case_id: str
    diagnosis: Diagnosis
    prediction: ModelPrediction
    recommendation: ActionRecommendation
    decision: Decision
    action: Optional[Action]
    outcome: Optional[Outcome]
    executed: bool


def _parse_channel_history(raw) -> list:
    if raw is None:
        return []
    if isinstance(raw, list):
        return raw
    try:
        return json.loads(raw)
    except (TypeError, ValueError):
        return []


def run_case_pipeline(db: Session, case: RecoveryCase) -> AgentRunResult:
    """
    Runs the full pipeline for a single recovery_case end to end:
    classify_cause -> recovery probability -> select_action ->
    check_policy -> execute_recovery (only if APPROVED).
    """
    diagnosis = tool_classify_cause(db, case)
    prediction = predict_for_case(db, case, diagnosis)
    recommendation = tool_select_action(db, case, diagnosis, prediction)

    features = extract_features_for_case(case)
    decision = tool_check_policy(
        db, case, diagnosis, recommendation.action,
        features.get("attempt_number"),
        bool(features.get("risk_flag")),
        features.get("consent_status"),
        _parse_channel_history(features.get("channel_history")),
        features.get("amount"),
    )

    action: Optional[Action] = None
    outcome: Optional[Outcome] = None
    executed = False
    if decision.policy_decision == PolicyDecision.APPROVED.value:
        action = tool_execute_recovery(db, decision)
        executed = True
        outcome = simulate_execution(
            db, action,
            amount_at_risk=case.amount_at_risk,
            currency=case.currency,
            recovery_probability=prediction.recovery_probability,
        )
    else:
        logger.info(
            "Case %s: NOT executing '%s' -- policy_decision=%s (rule=%s)",
            case.id, decision.proposed_action, decision.policy_decision, decision.policy_rule_triggered,
        )

    return AgentRunResult(
        case_id=str(case.id),
        diagnosis=diagnosis,
        prediction=prediction,
        recommendation=recommendation,
        decision=decision,
        action=action,
        outcome=outcome,
        executed=executed,
    )
