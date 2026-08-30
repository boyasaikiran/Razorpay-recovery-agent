# Cause Taxonomy

Centralized in `backend/app/core/taxonomy.py` -- every other module
(diagnosis, action recommendation, policy engine, synthetic generator,
frontend) imports from here rather than hardcoding strings, per the
spec's "centralized and configurable" requirement.

## Event types

| Event type | Meaning |
|---|---|
| `subscription_renewal_failed` | A recurring subscription charge failed |
| `payment_failed` | A one-off payment attempt failed |
| `checkout_abandoned` | Customer left checkout without attempting payment |
| `invoice_overdue` | A B2B invoice has passed its due date |

## Causes (11)

| Cause | Meaning |
|---|---|
| `insufficient_funds` | Card/account had insufficient funds at time of attempt |
| `expired_payment_method` | Card or payment method had expired |
| `temporary_bank_failure` | Transient issuer-side failure, likely recoverable |
| `auth_otp_failure` | 3DS/OTP authentication step failed |
| `checkout_abandonment` | No payment was attempted; cart abandoned |
| `price_shock_abandonment` | Abandonment specifically tied to price/fees at checkout |
| `bank_downtime` | Issuer or gateway was down |
| `overdue_invoice` | B2B invoice payment overdue |
| `risk_block` | Blocked by risk/fraud rules |
| `repeated_failure` | Multiple consecutive failures, same root cause unclear |
| `unknown` | None of the above; insufficient signal to diagnose |

## Fixed action set (7)

The agent can propose exactly one of these -- never anything else.
Enforced structurally: `ActionRecommendation`'s Pydantic validator
rejects any string outside this set (`app/schemas/action_recommendation.py`).

`RETRY_PAYMENT`, `DELAYED_RETRY`, `CREATE_PAYMENT_LINK`,
`SEND_NOTIFICATION`, `LOG_PROMISE_TO_PAY`, `ESCALATE_TO_HUMAN`,
`STOP_RECOVERY`

## Rule-based decline-code -> cause mapping (Diagnosis Path A)

From `app/core/decline_code_mapping.py`. Mirrors the synthetic
generator's own mapping by construction, so Path A recovers ground
truth exactly for any of these codes.

| decline_code | -> cause |
|---|---|
| `INSUFFICIENT_FUNDS`, `NSF`, `FUNDS_INSUFFICIENT` | `insufficient_funds` |
| `EXPIRED_CARD`, `CARD_EXPIRED` | `expired_payment_method` |
| `ISSUER_UNAVAILABLE`, `BANK_TIMEOUT` | `temporary_bank_failure` |
| `OTP_FAILED`, `AUTH_FAILED_3DS` | `auth_otp_failure` |
| `ISSUER_DOWNTIME`, `GATEWAY_DOWNTIME` | `bank_downtime` |
| `RISK_BLOCKED` | `risk_block` |
| `GENERIC_DECLINE`, `DO_NOT_HONOR` | `repeated_failure` |
| `UNKNOWN_ERROR` | `unknown` |

Codes not in this table (including real Razorpay `error_code` values
like `BAD_REQUEST_ERROR`, `GATEWAY_ERROR` seen in Phase 4's webhook
testing) fall through to Path B (XGBoost) or Path C (LLM) --
deliberately not guessed at, since Razorpay's error taxonomy wasn't
fully cross-referenced against this mapping.

## Default cause -> action mapping (Phase 8)

From `app/core/action_mapping.py`. This is the *default*; the actual
action recommendation service overrides it when diagnosis confidence
is low (-> `ESCALATE_TO_HUMAN`) or recovery probability is very low
(-> `STOP_RECOVERY`).

| Cause | Default action |
|---|---|
| `insufficient_funds` | `DELAYED_RETRY` |
| `expired_payment_method` | `CREATE_PAYMENT_LINK` |
| `temporary_bank_failure` | `DELAYED_RETRY` |
| `auth_otp_failure` | `RETRY_PAYMENT` |
| `checkout_abandonment` | `SEND_NOTIFICATION` |
| `price_shock_abandonment` | `SEND_NOTIFICATION` |
| `bank_downtime` | `DELAYED_RETRY` |
| `overdue_invoice` | `SEND_NOTIFICATION` |
| `risk_block` | `ESCALATE_TO_HUMAN` |
| `repeated_failure` | `ESCALATE_TO_HUMAN` |
| `unknown` | `ESCALATE_TO_HUMAN` |

See `docs/policies.md` for what the policy engine actually *allows*
per cause -- the default action above is a proposal, not a guarantee
of execution.
