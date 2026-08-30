# Security

## API authentication

`app/core/security.py`'s `require_api_key` dependency, applied to the
three state-changing endpoints: `POST /simulate/events`,
`POST /recovery-cases/{id}/run`, `POST /evaluation/run`.

**Fail-safe by design**, consistent with the policy engine's own
philosophy (`docs/policies.md`): if `API_KEY` is unset, protected
endpoints return `503`, never a silent bypass. Comparison uses
`hmac.compare_digest` to avoid timing side-channels.

Read endpoints (`GET /recovery-cases`, `/metrics`, `/audit-logs`,
`/policies`, `/models/performance`) are **deliberately left open** in
this configuration so the dashboard works without every fetch needing
a credential. This is a stated tradeoff, not an oversight -- confirmed
by `tests/security/test_api_auth_and_rate_limit.py::test_read_endpoints_remain_open_without_api_key`.

The Razorpay webhook is authenticated separately, via HMAC signature
(see `docs/razorpay.md`) -- Razorpay doesn't send our API key.

### The frontend's key isn't truly secret

`VITE_API_KEY` is baked into the built JS bundle at build time. Once
served to a browser, anyone can read it from the bundle. This is an
accepted tradeoff for an internal ops dashboard behind a private
network -- **not appropriate for a public-facing deployment**, which
would need session-based auth (login + short-lived token/cookie)
instead of a static shared key. Stated in the code itself
(`frontend/src/services/api.ts`), not just here.

## Rate limiting

`app/core/rate_limit.py` -- an in-memory, per-process, fixed-window
limiter. Per the spec's own MVP guidance ("do not prematurely
introduce Redis, Celery... FastAPI + PostgreSQL + background tasks is
enough"), this is the appropriate choice at this scale, **not**
appropriate for a multi-process/multi-instance deployment without a
shared store like Redis. Stated as a known limitation, not hidden.

Configured limits (per client IP, per 60-second window):
- `POST /simulate/events`: 300/min
- `POST /evaluation/run`: 10/min (expensive: runs the real pipeline
  per record)

Both configurable via env vars, and a global `RATE_LIMIT_ENABLED` flag
exists for environments (like this test suite) that need to bypass it.

## Webhook signature verification

Full HMAC-SHA256 verification over the raw request body, confirmed
against Razorpay's official documentation. See `docs/razorpay.md` for
what was and wasn't verified against live traffic.

## Structured LLM output validation

Diagnosis Path C forces structured output via Anthropic tool-use with
a JSON-schema `enum` constraint on `cause` (eliminating most malformed
output *by construction*), validates the result through Pydantic as a
second layer, retries once on failure, and falls back to
`cause=unknown, confidence=0.0` rather than raising. Chain-of-thought
is never surfaced -- only the `tool_use` block is read. See
`docs/ml.md` and `backend/app/llm/cause_classifier.py`.

## Secret management

- No hardcoded secrets anywhere in the codebase -- all sensitive
  config comes from environment variables via `Settings`
  (`app/core/config.py`).
- `.env` is gitignored (`.gitignore` matches `.env` at any depth,
  confirmed to cover `frontend/.env` too).
- `.env.example` documents every variable without real values.

## Safe logging

Audited by grepping for secret-adjacent log statements, then **proven
live**: `tests/security/test_safe_logging.py` injects fake
secret-shaped values into real code paths (app startup, Razorpay
client, LLM client) and asserts those values never appear in captured
log output -- not a source-code grep, an actual check of what gets
written to the log stream.

## CORS

Configured via `CORS_ALLOWED_ORIGINS` (comma-separated), applied in
`app/main.py` via `CORSMiddleware`. Defaults to
`http://localhost:5173,http://localhost:3000` for local dev.

## Error handling

Centralized exception handling (`app/core/exceptions.py`) ensures
every error response has a consistent, safe shape, is logged with its
`request_id` for traceability, and never leaks stack traces in
production (`settings.is_production` gate).

## Request IDs

Every response carries `X-Request-ID` (`app/core/middleware.py`),
reusing the caller's ID if provided -- needed for correlating a
request across the audit trail.

## Input validation

Every request body is a Pydantic schema with field-level validation.
`app/schemas/*.py` throughout.
