# Policy Engine

The most safety-critical component in this system. Plain, deterministic
Python (`backend/app/policies/policy_engine.py`) -- no model call, no
randomness, no I/O. Given the same inputs it always returns the same
decision.

## Rule precedence (evaluated in this exact order; first match wins)

0. `proposed_action` in `{ESCALATE_TO_HUMAN, STOP_RECOVERY}` -> **APPROVED**
   immediately. Always safe -- these never move money or contact a
   customer, and this guarantees a safe way out of any DENY/ROUTE_TO_HUMAN
   state.
1. `risk_flag` AND `policy.blocks_on_risk_flag` -> **ROUTE_TO_HUMAN**
2. `confidence < policy.confidence_threshold` -> **ROUTE_TO_HUMAN**
3. `proposed_action` not in `policy.allowed_actions`, or in
   `policy.blocked_actions` -> **DENIED**
4. Communication action AND `policy.requires_consent` AND
   `consent_status == "opted_out"` -> **DENIED**
5. Retry-type action AND `attempt_number >= policy.max_retries` ->
   **DENIED** (the agent is expected to next propose `STOP_RECOVERY`,
   which rule 0 always approves)
6. `amount` exceeds `policy.max_amount` (when set) -> **ROUTE_TO_HUMAN**
7. `SEND_NOTIFICATION` AND the customer has already been contacted via
   3+ channels -> **ROUTE_TO_HUMAN**
8. Otherwise -> **APPROVED**

### Why the decision space is 3-valued, not 7-valued

The spec's adversarial test list includes "attempt_number >= max ->
Expected: STOP_RECOVERY" -- but `STOP_RECOVERY` is an *action*, and
this engine's decision space is `APPROVED`/`DENIED`/`ROUTE_TO_HUMAN`.
The two-step realization: a retry proposal at max attempts is
**DENIED** (rule 5); `STOP_RECOVERY` itself is then always **APPROVED**
(rule 0). Verified directly in
`tests/adversarial/test_policy_engine.py::test_adversarial_attempt_number_at_max_denies_retry_enabling_stop_recovery`.

### Known simplification: count-based, not time-based, cooldown

Rule 7 approximates a "cooldown" using contact *count*
(`len(channel_history)`) rather than elapsed time, since the schema
doesn't yet store per-channel contact timestamps.
`policy.cooldown_seconds` is persisted and ready for a real
implementation once that data exists -- not enforced yet. Stated here
and in the engine's own docstring, not silently ignored.

## Fail-safe default

If no `Policy` row exists in the database for a diagnosed cause, the
system does **not** fall back to a permissive default. It returns
`ROUTE_TO_HUMAN` with `rule_triggered="no_policy_configured"`. Missing
configuration is a reason for caution, never a bypass. Verified in
`tests/integration/test_policy_service.py::test_policy_check_fails_safe_when_no_policy_configured`.

## Real seeded policy configuration

Pulled directly from the live database (`app/policies/default_policies.py`,
seeded via `python -m app.policies.seed_policies`). These are
illustrative MVP defaults, not audited business/compliance thresholds
-- a real deployment would tune these per-merchant and per-regulatory-regime.

| Cause | Allowed actions | Blocked actions | Confidence threshold | Max retries | Cooldown | Consent required | Blocks on risk | Max amount |
|---|---|---|---|---|---|---|---|---|
| `auth_otp_failure` | RETRY_PAYMENT, SEND_NOTIFICATION, ESCALATE_TO_HUMAN, STOP_RECOVERY | -- | 0.55 | 3 | 1800s | yes | yes | -- |
| `bank_downtime` | DELAYED_RETRY, ESCALATE_TO_HUMAN, STOP_RECOVERY | RETRY_PAYMENT | 0.50 | 5 | 1800s | no | yes | -- |
| `checkout_abandonment` | SEND_NOTIFICATION, ESCALATE_TO_HUMAN, STOP_RECOVERY | RETRY_PAYMENT, DELAYED_RETRY | 0.40 | 2 | 43200s | yes | yes | -- |
| `expired_payment_method` | CREATE_PAYMENT_LINK, SEND_NOTIFICATION, ESCALATE_TO_HUMAN, STOP_RECOVERY | RETRY_PAYMENT, DELAYED_RETRY | 0.50 | 2 | 172800s | yes | yes | -- |
| `insufficient_funds` | DELAYED_RETRY, SEND_NOTIFICATION, ESCALATE_TO_HUMAN, STOP_RECOVERY | RETRY_PAYMENT | 0.50 | 3 | 86400s | yes | yes | -- |
| `overdue_invoice` | SEND_NOTIFICATION, LOG_PROMISE_TO_PAY, ESCALATE_TO_HUMAN, STOP_RECOVERY | RETRY_PAYMENT, DELAYED_RETRY | 0.50 | 5 | 259200s | yes | yes | 1,000,000 |
| `price_shock_abandonment` | SEND_NOTIFICATION, ESCALATE_TO_HUMAN, STOP_RECOVERY | RETRY_PAYMENT, DELAYED_RETRY | 0.40 | 1 | 86400s | yes | yes | -- |
| `repeated_failure` | SEND_NOTIFICATION, ESCALATE_TO_HUMAN, STOP_RECOVERY | RETRY_PAYMENT, DELAYED_RETRY | 0.60 | 1 | 86400s | yes | yes | -- |
| `risk_block` | ESCALATE_TO_HUMAN, STOP_RECOVERY | RETRY_PAYMENT, DELAYED_RETRY, CREATE_PAYMENT_LINK, SEND_NOTIFICATION, LOG_PROMISE_TO_PAY | 0.80 | 0 | 0s | yes | yes | 0 (no automated monetary action, ever) |
| `temporary_bank_failure` | DELAYED_RETRY, RETRY_PAYMENT, ESCALATE_TO_HUMAN, STOP_RECOVERY | -- | 0.50 | 4 | 3600s | no | yes | -- |
| `unknown` | ESCALATE_TO_HUMAN, STOP_RECOVERY | RETRY_PAYMENT, DELAYED_RETRY, CREATE_PAYMENT_LINK, SEND_NOTIFICATION | 0.90 | 0 | 0s | yes | yes | -- |

(`--` = not set / no cap. Pulled live via
`psql -d recovery_orchestrator -c "SELECT ... FROM policies"` --
not hand-typed.)

## Verification

Every rule above is tested, including the spec's exact adversarial
list, run against these real seeded rows (not synthetic test fixtures):
`tests/adversarial/test_policy_engine.py`. One test
(`test_zero_policy_violations_across_full_cause_x_action_matrix`)
exhaustively checks all 11 causes x 7 actions = 77 combinations and
asserts zero violations.
