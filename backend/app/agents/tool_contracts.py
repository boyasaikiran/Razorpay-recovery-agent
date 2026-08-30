"""
Tool contracts for the Recovery Orchestrator agent (Phase 10).

Exactly 5 tools, matching the spec precisely:
    classify_cause, select_action, check_policy, execute_recovery, log_audit

Each contract documents input, output, permissions, failure behavior,
and audit requirements.

CRITICAL INVARIANT: execute_recovery is a MONEY/COMMUNICATION-MOVING
tool. The agent loop (agent_loop.py) is the only caller, and it
enforces IN CODE (not prompt) that execute_recovery may only run
against a Decision whose policy_decision is APPROVED. See tools.py's
tool_execute_recovery for the actual guard.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class ToolContract:
    name: str
    description: str
    input_description: str
    output_description: str
    permissions: str
    failure_behavior: str
    audit_requirements: str


TOOL_CONTRACTS: dict[str, ToolContract] = {
    "classify_cause": ToolContract(
        name="classify_cause",
        description="Diagnoses why a payment/checkout/invoice event failed (Phase 6 cascade: "
        "rule-based -> XGBoost -> LLM).",
        input_description="recovery_case (with its linked payment_event)",
        output_description="Diagnosis row: cause, confidence, method, reason, signals",
        permissions="READ payment_event/customer data. WRITE a Diagnosis row. No money movement, "
        "no external communication.",
        failure_behavior="If all three diagnosis paths are unavailable, returns cause=unknown, "
        "confidence=0.0 rather than raising -- a failed diagnosis still needs a case record "
        "so it can route to human review, not disappear.",
        audit_requirements="Writes a CAUSE_CLASSIFIED audit entry. Writes a HUMAN_ESCALATED "
        "entry additionally if confidence is below threshold.",
    ),
    "select_action": ToolContract(
        name="select_action",
        description="Proposes exactly one action from the fixed 7-action set, given the "
        "diagnosis and recovery probability (Phase 8).",
        input_description="Diagnosis row, recovery_probability (float or None)",
        output_description="ActionRecommendation: action (validated against ALL_ACTIONS), reason",
        permissions="READ-ONLY. Cannot write to any execution-related table. Cannot invent an "
        "action outside the fixed set -- enforced by Pydantic validation on the return type.",
        failure_behavior="Never raises for a valid Diagnosis input -- always returns a "
        "structurally valid recommendation (worst case: ESCALATE_TO_HUMAN).",
        audit_requirements="Writes an ACTION_PROPOSED audit entry.",
    ),
    "check_policy": ToolContract(
        name="check_policy",
        description="Deterministically evaluates a proposed action against the cause's policy "
        "config (Phase 9). THE gatekeeper -- no action reaches execution without passing "
        "through this tool and receiving APPROVED.",
        input_description="proposed_action, cause/confidence (from Diagnosis), attempt_number, "
        "risk_flag, consent_status, channel_history, amount",
        output_description="Decision row: proposed_action + policy_decision "
        "(APPROVED/DENIED/ROUTE_TO_HUMAN) + reason + rule_triggered",
        permissions="READ policy config. WRITE a Decision row. No money movement, no external "
        "communication -- this tool only decides, it never acts.",
        failure_behavior="FAIL-SAFE: if no policy is configured for the cause, returns "
        "ROUTE_TO_HUMAN (rule_triggered=no_policy_configured), never silent approval.",
        audit_requirements="Writes a POLICY_CHECKED audit entry always. Writes an additional "
        "HUMAN_ESCALATED entry when the decision is ROUTE_TO_HUMAN.",
    ),
    "execute_recovery": ToolContract(
        name="execute_recovery",
        description="Executes the approved action (simulated in this MVP -- see Phase 11). "
        "THE ONLY tool that performs a money-moving or customer-communication side effect.",
        input_description="A Decision row whose policy_decision MUST already be APPROVED",
        output_description="Action row: action_type, status, simulated=True, executed_at",
        permissions="WRITE an Action row (and, once Phase 11's simulator runs, an Outcome row). "
        "This is the ONLY tool in the system permitted to represent a money-moving or "
        "customer-communication side effect.",
        failure_behavior="STRUCTURALLY REFUSES to run (raises PermissionError, writes no Action "
        "row) if decision.policy_decision != APPROVED. This is a hard code-level guard, not a "
        "prompt instruction -- it cannot be bypassed by an LLM's tool_use output, a prompt "
        "injection, or a caller mistake. The LLM never calls this tool directly; only the "
        "agent loop does, and only after observing an APPROVED check_policy result itself.",
        audit_requirements="Writes an ACTION_EXECUTED audit entry on success. A refused call "
        "(guard triggered) is itself audited, never silently dropped.",
    ),
    "log_audit": ToolContract(
        name="log_audit",
        description="Appends a record to the write-once audit trail (Phase 12).",
        input_description="stage, actor, recovery_case_id, decision, reason, references, "
        "simulation_status",
        output_description="AuditLog row",
        permissions="APPEND-ONLY. No update or delete path exists in the repository layer "
        "(AuditLogRepository has no update()/delete() methods).",
        failure_behavior="An audit write failure must surface loudly (propagates the DB "
        "exception) rather than being swallowed -- an unaudited case-affecting action must be "
        "impossible per Critical Safety Invariant #7.",
        audit_requirements="N/A -- this IS the audit tool.",
    ),
}
