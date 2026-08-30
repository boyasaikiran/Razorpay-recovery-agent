# Recovery Orchestrator

An AI-native revenue recovery platform: it diagnoses **why** a payment,
checkout, or invoice failed, estimates whether the revenue is
recoverable, proposes a cause-specific recovery action, validates that
action through a deterministic policy engine, executes only approved
actions, records the result, and measures exactly how much revenue was
recovered — and how much wasn't.

Built as a 16-phase implementation (Phase 0 environment inspection
through Phase 16 Docker), with every phase actually run and tested
against real infrastructure (a live PostgreSQL database, real trained
XGBoost models, a real evaluation run over 600 independent synthetic
records) rather than written speculatively. See [Limitations](#limitations)
for what was **not** possible to verify in the environment this was
built in.

---

## Problem

Failed payments, abandoned checkouts, and overdue invoices are usually
handled the same way regardless of cause: retry once, on a fixed
schedule, with no awareness of *why* the payment failed. Retrying an
expired card can never succeed. Contacting an opted-out customer is a
compliance risk. Retrying indefinitely on a risk-blocked payment is
dangerous. A blind, cause-unaware strategy leaves recoverable revenue
on the table and creates real risk on cases it shouldn't touch at all.

## Solution

Recovery Orchestrator replaces blind retry with a diagnosed, policy-
gated pipeline:

```
EVENT -> INGESTION -> CONTEXT -> CAUSE DIAGNOSIS -> RECOVERY PROBABILITY
  -> ACTION RECOMMENDATION -> DETERMINISTIC POLICY -> EXECUTION
  -> OUTCOME -> RECOVERY METRICS -> AUDIT
```

The central safety principle, enforced in code rather than by
convention: **the LLM proposes, the deterministic policy engine
disposes.** No action — retrying a payment, sending a customer
notification, creating a payment link — is ever executed without
first passing through policy evaluation and receiving `APPROVED`. This
is not a guideline; it's a structural guarantee (see
`docs/agent.md` for how it's enforced at the code level, independent
of what any LLM proposes).

See `docs/architecture.md` for the full pipeline and repo structure,
and the phase-by-phase docs below for how each component works and
what it's actually been verified to do.

## Documentation Index

| Doc | Covers |
|---|---|
| `docs/architecture.md` | Full pipeline, repo structure, tech stack |
| `docs/cause-taxonomy.md` | The 11 failure causes, event types, action set |
| `docs/agent.md` | Tool contracts, the agent loop, the execution guard |
| `docs/policies.md` | The deterministic policy engine and real seeded config |
| `docs/ml.md` | Both trained models, real metrics, leakage protection |
| `docs/razorpay.md` | Real vs. simulated Razorpay integration |
| `docs/security.md` | Auth, rate limiting, secret handling |
| `docs/evaluation.md` | Real evaluation methodology and results |

## AI Role, Agent Role, Policy Engine -- Summary

- **AI (LLM/ML) role**: diagnoses cause (three-path cascade: rule-based
  -> XGBoost -> LLM), predicts recovery probability, proposes exactly
  one action from a fixed set. It never touches money or contacts a
  customer directly.
- **Agent role**: orchestrates the pipeline in a fixed tool-calling
  sequence (`classify_cause -> select_action -> check_policy ->
  execute_recovery -> log_audit`). Currently deterministic (no LLM
  configured in this environment -- see below), but the safety
  guarantees don't change if one is wired in.
- **Policy engine role**: plain, deterministic Python. No model call,
  no randomness. The only component that can turn a proposal into an
  actual execution.

## Real vs. Simulated

Every action in this system is simulated -- this MVP has never been
tested against a live Razorpay account or real payment traffic. This
is stated explicitly, everywhere it matters:
- The database marks every event and action with `simulation_status: true`.
- The dashboard visibly badges `SIMULATED` on every relevant row.
- `docs/razorpay.md` states exactly which parts of the Razorpay
  integration were verified against official documentation vs. never
  exercised against a live account.

## LLM Configuration

`LLM_API_KEY` is **not configured** in the environment this was built
in. Diagnosis Path C (the LLM classifier) and any LLM-driven agent
behavior were built correctly against the real Anthropic SDK -- forced
structured tool-use output, Pydantic validation, retry-once,
fallback -- but genuinely never exercised against a live model. Every
test that could run without a live LLM call (schema validation,
control flow, fallback behavior) does run and pass; the actual API
round-trip does not. Configure `LLM_API_KEY` and `LLM_MODEL` in `.env`
to enable it.

## Installation

### Local (without Docker)

```bash
# Backend
cd backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# Database (adjust to your local Postgres, or see Docker section below)
createdb recovery_orchestrator
cp ../.env.example ../.env   # fill in DATABASE_URL, API_KEY at minimum
.venv/bin/alembic upgrade head
.venv/bin/python -m app.policies.seed_policies

# Train the ML models (writes to data/models/)
.venv/bin/python -m app.ml.train_cause_classifier
.venv/bin/python -m app.ml.train_recovery_probability

# Run the backend
.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000

# Frontend (separate terminal)
cd frontend
npm install
cp .env.example .env   # VITE_API_KEY must match backend's API_KEY
npm run dev
```

Generate the synthetic datasets first if `data/processed/*.csv` don't
already exist:

```bash
cd data/synthetic_generator
python generate.py --n-records 750 --n-merchants 18 --seed 42
```

The independent evaluation set (`data/processed/evaluation.csv`) is
generated the same way with `--n-records 600 --seed 999`; see
`docs/evaluation.md` for exactly how it was produced.

### Docker

```bash
cp .env.example .env   # fill in a real API_KEY
docker compose up --build
```

**This has not been run in the environment that built this repo** (no
Docker daemon was available there). The Dockerfiles and
`docker-compose.yml` were written and extensively cross-checked
against the real dependency lists, real path resolution logic, and
real environment variable names -- but the actual container build/run
needs to be verified by you. See `docker-compose.yml`'s comments for
exactly what was and wasn't checked.

- Backend: http://localhost:8000 (docs at `/docs`)
- Frontend: http://localhost:3000
- Postgres: localhost:5432

## API

Full interactive docs at `/docs` (Swagger UI) once the backend is
running. Key endpoints:

| Method | Path | Auth | Purpose |
|---|---|---|---|
| GET | `/api/v1/health` | none | Liveness check |
| POST | `/api/v1/simulate/events` | API key | Ingest a simulated event |
| POST | `/api/v1/webhooks/razorpay` | HMAC signature | Real Razorpay webhook |
| GET | `/api/v1/recovery-cases` | none | List cases (enriched) |
| GET | `/api/v1/recovery-cases/{id}` | none | Case detail |
| GET | `/api/v1/recovery-cases/{id}/trace` | none | Full audit trail for a case |
| POST | `/api/v1/recovery-cases/{id}/run` | API key | Run the pipeline for a case |
| GET | `/api/v1/audit-logs` | none | Filterable audit log query |
| GET | `/api/v1/metrics` | none | Live aggregate metrics |
| GET | `/api/v1/policies` | none | Real seeded policy config |
| GET | `/api/v1/models/performance` | none | Real training metrics |
| POST | `/api/v1/evaluation/run` | API key | Run the batch evaluation engine |

## Demo

1. `docker compose up` (or run backend + frontend locally)
2. Open the dashboard, go to **Recovery Cases**
3. POST a few events via `/api/v1/simulate/events` (see `docs/cause-taxonomy.md`
   for `decline_code` values that trigger each diagnosis path), or run
   the seeded evaluation set through `POST /api/v1/evaluation/run`
4. Click into **Agent Trace** for any case to see the full pipeline
5. Check **Policies** to see the AI cannot bypass policy
6. Check **Model Performance** for real training metrics

## Limitations

Stated plainly, not buried:

1. **No Docker daemon was available** in the build environment -- the
   full container stack has never been run end-to-end. See
   `docker-compose.yml`'s header comment for exactly what static
   verification was and wasn't possible.
2. **No live Razorpay account or credentials** were available --
   `REAL_RAZORPAY` code paths are implemented against the documented
   SDK but never exercised against a live account. Only
   `payment.failed` webhook events are mapped; other event types are
   explicitly left unmapped rather than guessed at (see `docs/razorpay.md`).
3. **No LLM API key was available** -- Diagnosis Path C and any
   LLM-driven agent behavior are built correctly but never tested
   against a live model.
4. **Feature richness gap**: the relational schema stores a subset of
   the full synthetic feature set as dedicated columns; the rest is
   read from `payload` JSONB when the caller supplies it. Documented
   in `app/services/feature_extraction.py`.
5. **Rate limiting is in-memory/single-process** -- won't work
   correctly across multiple backend instances without a shared store.
6. **The frontend's API key is bundled into client JS** -- not truly
   secret once served to a browser; acceptable for an internal demo
   tool, not for a public-facing deployment.
7. Training data scale is modest (750 records for train/val, 600 for
   the independent evaluation set) -- real metrics reported throughout
   the docs reflect this scale honestly, including where the models'
   performance is imperfect.

## Future Work

- Wire and test the LLM diagnosis path (Path C) against a live model
- Verify the full Docker stack end-to-end
- Real Razorpay test-mode integration testing
- Expand the decline-code -> cause rule-based mapping using Razorpay's
  actual error-code reference
- Time-based cooldown enforcement (currently count-based -- see
  `app/policies/policy_engine.py`)
- Session-based auth for a public-facing deployment
- Confusion matrix persistence for the cause classifier
