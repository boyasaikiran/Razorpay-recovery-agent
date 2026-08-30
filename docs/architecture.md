# Architecture

## Pipeline

```
payment_event
    |
    v
recovery_case  (created 1:1 with payment_event)
    |
    v
diagnosis      (Phase 6: rule-based -> XGBoost -> LLM cascade)
    |
    v
model_prediction  (Phase 7: recovery probability, XGBoost)
    |
    v
decision       (Phase 8 proposed_action + Phase 9 policy_decision, one row)
    |
    v
action         (Phase 10-11: only created if policy_decision == APPROVED)
    |
    v
outcome        (Phase 11: simulated success/failure/human_review/stopped)
```

Every stage writes to `audit_logs` (Phase 12), append-only, queryable
via `GET /api/v1/audit-logs` and `GET /api/v1/recovery-cases/{id}/trace`.

## Core safety principle

**LLM proposes. Policy engine disposes.**

`app/agents/tools.py`'s `tool_execute_recovery` contains the actual
enforcement: it raises `ExecutionNotApprovedError` and writes zero
rows to the `actions` table unless `decision.policy_decision ==
APPROVED`. This is a Python equality check, not a system-prompt
instruction -- it cannot be bypassed by an LLM's output, a prompt
injection, or a caller bug. See `docs/agent.md` for the full
enforcement chain and `docs/policies.md` for what the policy engine
itself does.

## Tech stack (as actually used, not aspirational)

| Layer | Choice | Notes |
|---|---|---|
| Backend | FastAPI + Pydantic | `backend/app/main.py` |
| ORM / migrations | SQLAlchemy 2.0 + Alembic | `backend/app/models/`, `backend/alembic/` |
| Database | PostgreSQL 16 | 14 tables |
| ML | XGBoost + scikit-learn | Two models: cause classifier, recovery probability |
| LLM | Anthropic SDK (tool-use) | Built, never exercised (no API key available) |
| Frontend | React 18 + TypeScript + Vite | 8 dashboard pages |
| Charts | Recharts | Pie/bar/line charts across the dashboard |
| Infra | Docker + Docker Compose | Written, not run in the build environment |
| Testing | pytest | 175 tests, all passing |

## Repository structure

```
recovery-orchestrator/
|-- backend/
|   |-- app/
|   |   |-- api/v1/          # FastAPI route handlers
|   |   |-- agents/          # Tool contracts, tool implementations, agent loop
|   |   |-- core/            # Config, logging, security, rate limiting, taxonomy
|   |   |-- database/        # SQLAlchemy engine/session
|   |   |-- models/          # ORM models (13 entities)
|   |   |-- schemas/         # Pydantic request/response schemas
|   |   |-- repositories/    # Data access layer, one per entity
|   |   |-- services/        # Business logic (diagnosis, policy, execution, etc.)
|   |   |-- policies/        # Policy engine + default seeded config
|   |   |-- ml/               # Model training scripts + inference wrappers
|   |   |-- llm/               # LLM client + cause classifier (Path C)
|   |   |-- evaluation/       # Batch evaluation engine + baseline strategy
|   |   |-- webhooks/         # Razorpay webhook parsing + endpoint
|   |   `-- main.py
|   |-- tests/
|   |   |-- unit/             # Pure-function tests, no DB
|   |   |-- integration/      # Real DB, real HTTP via TestClient
|   |   |-- security/         # Auth, rate limiting, safe logging, signatures
|   |   `-- adversarial/      # Explicit spec-required safety invariant tests
|   |-- alembic/              # DB migrations
|   |-- requirements.txt
|   `-- Dockerfile
|-- frontend/
|   |-- src/
|   |   |-- pages/            # 8 dashboard pages
|   |   |-- components/       # Shared UI (Card, Badge, PipelineTrace, ...)
|   |   |-- services/api.ts   # Typed API client
|   |   |-- types/api.ts      # TypeScript types mirroring backend schemas
|   |   `-- layouts/
|   `-- Dockerfile
|-- data/
|   |-- synthetic_generator/  # Cause-driven synthetic data generator
|   |-- raw/, processed/      # Generated CSVs (train/val/test/evaluation)
|   `-- models/               # Trained model artifacts + metadata JSON
|-- docs/                     # This directory
`-- docker-compose.yml
```

## Design decisions worth knowing about

A few places where the spec left room for judgment and a specific
choice was made and documented in the code itself (not just here):

- **Diagnosis path precedence** (`app/services/diagnosis_service.py`):
  rule-based first, then LLM if free text is present, then XGBoost,
  then unknown-fallback. Stated explicitly since the spec didn't pin
  down an exact order.
- **Policy decision space is 3-valued** (APPROVED/DENIED/ROUTE_TO_HUMAN)
  while the spec's adversarial test list phrases one case in terms of
  a 7-valued action (`attempt_number >= max -> STOP_RECOVERY`).
  Resolved in `app/policies/policy_engine.py`'s docstring: a retry at
  max attempts is DENIED, and STOP_RECOVERY is always APPROVED,
  giving the agent a guaranteed safe next move.
- **Recovery-probability training uses diagnosed cause, not ground
  truth** (`app/ml/train_recovery_probability.py`) -- to avoid
  leaking the synthetic generator's own cause->recoverability table
  into the model.
- **Cooldown is count-based, not time-based** (`app/policies/policy_engine.py`
  rule 7) -- the schema doesn't yet store per-channel contact
  timestamps.
