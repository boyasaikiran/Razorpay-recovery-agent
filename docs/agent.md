# Agent

## The tool-calling loop

```
LLM (or, currently, the deterministic fallback below)
 |
 v
classify_cause    -- Phase 6 diagnosis cascade
 |
 v
select_action     -- Phase 8 fixed-action-set recommendation
 |
 v
check_policy      -- Phase 9 deterministic policy engine
 |
 v
execute_recovery  -- ONLY reachable if check_policy returned APPROVED
 |
 v
log_audit         -- write-once audit trail
```

`backend/app/agents/agent_loop.py`'s `run_case_pipeline` is the
current implementation. It is a **deterministic orchestrator**, not
an LLM-driven loop -- stated honestly, not dressed up: `LLM_API_KEY`
is not configured in this environment. Diagnosis Path C (the one part
of this pipeline that would consult an LLM) already attempts it and
falls back cleanly when unconfigured, so this loop is the correct MVP
behavior right now, not a placeholder standing in for something else.
The safety guarantees below do not change if an LLM is wired into
`select_action` or the loop's control flow later.

## The five tools

Formally documented (input/output/permissions/failure behavior/audit
requirements) in `backend/app/agents/tool_contracts.py`:

| Tool | Does | Can it move money or contact a customer? |
|---|---|---|
| `classify_cause` | Diagnoses the failure cause | No |
| `select_action` | Proposes one action from the fixed 7-action set | No |
| `check_policy` | Decides APPROVED/DENIED/ROUTE_TO_HUMAN | No -- decides, never acts |
| `execute_recovery` | Executes the approved action (simulated) | **Yes -- the only one** |
| `log_audit` | Appends to the write-once audit trail | No |

## The critical guarantee: LLM cannot directly call execute_recovery

`tool_execute_recovery` (`backend/app/agents/tools.py`) contains the
actual enforcement:

```python
if decision.policy_decision != PolicyDecision.APPROVED.value:
    # ... write an audit entry recording the refusal ...
    raise ExecutionNotApprovedError(...)
```

This is a **Python equality check**, not a system-prompt instruction.
It cannot be bypassed by:
- An LLM's tool_use output (the LLM never calls this tool directly --
  only the agent loop does, and only after observing check_policy's
  own result)
- A prompt injection
- A caller mistake (a forged or tampered `Decision` object with
  `policy_decision` manually set to anything other than `APPROVED`
  is still refused)

**Defense in depth**: the guarantee is enforced *twice* -- once in the
agent loop (which simply doesn't call `execute_recovery` unless it
observed `APPROVED`), and again independently inside
`tool_execute_recovery` itself. A bug in the loop's `if` statement
would still be caught by the tool's own guard.

Verified directly in `tests/adversarial/test_execute_recovery_guard.py`
(6 tests: DENIED, ROUTE_TO_HUMAN, a forged arbitrary string, an empty
string, confirms zero Action rows are created on any refusal, and a
DB-level FK defense-in-depth check for a completely fabricated
`recovery_case_id`) and exercised end-to-end through the real pipeline
in `tests/integration/test_agent_loop.py`.

## What happens on DENIED or ROUTE_TO_HUMAN

Per the spec: "If policy rejects: DO NOT execute. If policy routes to
human: DO NOT execute automatically." The agent loop satisfies this
by simply not calling `execute_recovery` in either case -- there is no
special-case bypass logic. The `Decision` row is still always
persisted (the proposal is always recorded, whatever the verdict).
