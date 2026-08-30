# ⚡ Recovery Orchestrator
### Autonomous, Policy-Governed Revenue Recovery Engine for Payment Failures

[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-009688?style=flat&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16+-336791?style=flat&logo=postgresql&logoColor=white)](https://www.postgresql.org)
[![XGBoost](https://img.shields.io/badge/XGBoost-2.0+-EB5424?style=flat)](https://xgboost.readthedocs.io)
[![Razorpay Webhooks](https://img.shields.io/badge/Razorpay-Live%20Webhooks%20Verified-0C2340?style=flat&logo=razorpay)](https://razorpay.com/docs)
[![Tests](https://img.shields.io/badge/Tests-175%20Passing-success?style=flat&logo=pytest)](https://docs.pytest.org)
[![Safety](https://img.shields.io/badge/Guardrails-Deterministic%20Policy%20Gate-red?style=flat)](docs/policies.md)

---

## Executive Summary

When payments fail, modern businesses typically rely on naive cron-based retries or manual review queues. This causes immediate revenue leakage, customer fatigue from repeated charges, and compliance risks on high-risk or opted-out transactions.

**Recovery Orchestrator** is an AI-native revenue recovery platform that replaces blind retries with an intelligent, policy-governed orchestration pipeline. It ingests live payment failure webhooks from **Razorpay**, classifies root causes across an 11-cause taxonomy, predicts recovery probabilities using machine learning, selects tailored recovery actions, and evaluates them against an unbypassable **Deterministic Policy Engine** before execution.

---

## 🏛️ Core Architectural Principle
```
                   ┌────────────────────────────────────────────────────────┐
                   │                   AGENTIC / ML LAYER                   │
                   │   • Root-Cause Diagnosis (Rule-based / XGBoost / LLM)  │
                   │   • Recovery Probability Prediction                    │
                   │   • Action Proposal (From fixed 7-action set)          │
                   └───────────────────────────┬────────────────────────────┘
                                               │ Proposes Action
                                               ▼
                   ┌────────────────────────────────────────────────────────┐
                   │               DETERMINISTIC POLICY ENGINE              │
                   │   • Hard invariant: Pure Python, 0% randomness, no LLM │
                   │   • Risk block validation & Opt-out enforcement        │
                   │   • Rate-limit / Max retry thresholds                  │
                   └───────────────────────────┬────────────────────────────┘
                                               │ Returns: APPROVED | DENIED | ROUTE_TO_HUMAN
                                               ▼
                   ┌────────────────────────────────────────────────────────┐
                   │                   EXECUTION & LEDGER                   │
                   │   • Hard Guard: Code-level check on policy approval    │
                   │   • Write-once 8-Stage Audit Ledger in PostgreSQL      │
                   │   • Live Telemetry & Case Management Dashboard         │
                   └───────────────────────────┘
```

> **The Structural Safety Guarantee:** The ML/LLM layer *proposes*; the deterministic policy engine *disposes*. The execution engine enforces a code-level invariant (`ExecutionNotApprovedError`) that physically blocks any payment retry, notification, or link generation unless the Policy Engine emits `APPROVED`.

---

## 🔄 End-to-End System Pipeline
```
PAYMENT FAILURE

│ (Razorpay Test Mode)

▼

RAZORPAY WEBHOOK ──► CLOUDFLARE TUNNEL ──► FASTAPI BACKEND (/api/v1/webhooks/razorpay)

│

┌─────────────────────────────────────────────────┴─────────────────────────────────────────────────┐

│ 1. Ingestion: Raw HMAC-SHA256 signature verification & x-razorpay-event-id idempotency deduplication│

│ 2. Entity Mapping: Resolve account_id -> Razorpay Merchant in PostgreSQL                          │

│ 3. Relational Persistence: payment_events -> recovery_cases (simulation_status: false)            │

└─────────────────────────────────────────────────┬─────────────────────────────────────────────────┘

▼

3-TIER CAUSE DIAGNOSIS

┌──────────────────┼──────────────────┐

▼                  ▼                  ▼

Path A             Path B             Path C

Deterministic      XGBoost Multi-      Structured

Decline Codes      Class (Tabular)    LLM Fallback

└──────────────────┬──────────────────┘

▼

RECOVERY PROBABILITY MODEL

(XGBoost Calibrated Probability Engine)

▼

ACTION RECOMMENDATION

(Fixed 7-Action Enum: Retries, Links, etc.)

▼

DETERMINISTIC POLICY ENGINE

(APPROVED / DENIED / ROUTE_TO_HUMAN)

▼

POLICY-GUARDED EXECUTION

(Raises error if policy != APPROVED)

▼

IMMUTABLE AUDIT LEDGER

(8-Stage write-once trace in PostgreSQL)

▼

FULL REACT/VITE DASHBOARD

```
---

## ⚡ Verified Technical Highlights

* **Real Webhook Ingestion via Live Tunnels:** Evaluated and verified against real Razorpay test-mode webhooks delivered over a live Cloudflare Tunnel, confirming exact header HMAC-SHA256 signature parsing against raw payload bytes.
* **Dual-State Data Lineage:** Full isolation between synthetic demo workloads (`simulation_status: true`) and live webhook ingestions (`simulation_status: false`), ensuring audit integrity.
* **Adversarial & Fault-Tolerant Test Suite:** **175 automated tests** covering tampered HMAC signatures, duplicate webhook storms, label-leakage assertions, and foreign-key relational integrity constraints.
* **Leakage-Proof ML Feature Pipeline:** Import-time schema assertions ensuring feature/label independence with merchant-level (70/15/15) split boundaries to prevent cross-merchant contamination.
* **Observability Visualizer:** Complete 8-page React control plane featuring real-time KPI metrics, an 8-stage visual pipeline execution trace, model calibration curves, and policy tables.

---

## 📁 Repository Structure
```
.

├── backend/

│   ├── app/

│   │   ├── agents/          # Tool contracts, deterministic loop, execution guards

│   │   ├── api/v1/          # Ingestion, webhook, case, and policy endpoints

│   │   ├── core/            # Config, security, database sessions, logging

│   │   ├── ml/              # Feature schemas, inference pipelines, model definitions

│   │   ├── policies/        # Pure deterministic policy engine & default rules

│   │   ├── repositories/    # PostgreSQL data access layer

│   │   ├── schemas/         # Pydantic v2 domain & validation schemas

│   │   ├── services/        # Webhook parsing, failure diagnosis, action selection

│   │   └── webhooks/        # Raw-byte HMAC validation & idempotency handlers

│   ├── tests/

│   │   ├── adversarial/     # Signature tampering, bypass attempts, duplicate webhooks

│   │   ├── integration/     # Full-pipeline case ingestion-to-execution tests

│   │   ├── security/        # Auth validation, key leakage, rate limiting

│   │   └── unit/            # Policy rules, ML feature extraction, data leakage

│   ├── alembic/             # Version-controlled relational migrations

│   └── requirements.txt

├── frontend/

│   ├── src/

│   │   ├── components/      # PipelineTrace, CaseTable, MetricsCards, Charts

│   │   ├── pages/           # Overview, Cases, Trace, Policies, Ledger, Models

│   │   └── services/        # Typed API client services

│   └── package.json

├── data/

│   ├── raw/ & processed/    # Merchant-split synthetic datasets (750 records)

│   └── models/              # Serialized XGBoost classification & probability models

├── docs/                    # In-depth architectural, policy, and taxonomy specs

├── docker-compose.yml       # Production-ready orchestration definition

├── SETUP.md                 # Deterministic step-by-step reproduction instructions

└── README.md

```
---

## 🛠️ Tech Stack

| Layer | Technology | Purpose |
| :--- | :--- | :--- |
| **Backend** | Python 3.12, FastAPI, Uvicorn, Pydantic v2 | High-performance, schema-validated asynchronous API |
| **Database** | PostgreSQL 16, SQLAlchemy 2.0, Alembic | ACID relational storage with foreign-key cascade protections |
| **Machine Learning** | XGBoost, Scikit-Learn, Pandas, NumPy | Multi-class cause classification & calibrated recovery scoring |
| **Ingestion** | Razorpay SDK, Cryptography (HMAC-SHA256) | Official webhook signature verification & idempotency control |
| **Frontend** | React 18, TypeScript, Vite, TailwindCSS | Operational ledger, case review, and visual pipeline inspector |
| **Networking** | Cloudflare Tunnel (`cloudflared`) | Secure local tunneling for external Razorpay webhook testing |

---

## 🚀 Quickstart & Setup

### Option 1: Local Development (Fast Track)

```bash
# 1. Setup Backend
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 2. Database Initialization
createdb recovery_orchestrator
cp ../.env.example ../.env   # Configure DATABASE_URL and API_KEY
alembic upgrade head
python -m app.policies.seed_policies

# 3. Start Backend API Server
uvicorn app.main:app --host 127.0.0.1 --port 8000

# 4. Start Frontend Dashboard (New Terminal)
cd ../frontend
npm install
cp .env.example .env         # Ensure VITE_API_KEY matches API_KEY
npm run dev
```

*Frontend runs at `http://localhost:5173` | Swagger API docs at `http://localhost:8000/docs`*

### Option 2: Run Full Automated Test Suite (175 Tests)

```bash
cd backend
pytest tests/ -v
```

## 🔗 Live Razorpay Webhook Configuration
To receive live Razorpay test-mode webhooks into your local instance:

1. **Start Cloudflare Tunnel:**

```bash
cloudflared tunnel --url http://localhost:8000
```

2. **Configure Razorpay Dashboard:**

- Navigate to **Razorpay Dashboard → Settings → Webhooks**.
- Set Webhook URL: `https://<your-tunnel-url>.trycloudflare.com/api/v1/webhooks/razorpay`
- Select Active Events: `payment.failed`
- Set Secret: Enter the secret matching `RAZORPAY_WEBHOOK_SECRET` in your `.env`.

3. **Trigger Test Failures:**

- Simulate a failed checkout in Razorpay Sandbox.
- Observe real-time ingestion in `payment_events`, automated case generation in `recovery_cases`, and live traces on the frontend dashboard.

## 🛡️ Production Safety & Policy Invariants

| Scenario | Evaluated Risk | Enforced Policy Invariant | Resulting Action | Risk Block |
|---|---|---|---|---|
| **Fraud suspicion** | Automated retries are forbidden across all conditions | `ROUTE_TO_HUMAN` | ✓ |
| **Customer Opt-Out** | Compliance violation | User has revoked automated recovery notifications | `DENIED` | ✓ |
| **Low ML Confidence** | Ambiguous failure reason | Cause prediction confidence falls below threshold ($<40\%$) | `ROUTE_TO_HUMAN` | ✓ |
| **Max Retry Exceeded** | Charge fatigue / Spam | Retries $\ge$ configured policy limit for given cause | `DENIED` → `STOP_RECOVERY` | ✓ |
| **Unmapped Cause** | Missing system policy | Fails safe on unknown or unconfigured failure types | `ROUTE_TO_HUMAN` | ✓ |

## 📖 Deep-Dive Documentation Index

- [`docs/architecture.md`](docs/architecture.md) — Multi-layer architecture, ingestion pathways, and state machines.
- [`docs/cause-taxonomy.md`](docs/cause-taxonomy.md) — 11 failure causes, event signatures, and action mapping defaults.
- [`docs/policies.md`](docs/policies.md) — Deterministic evaluation engine, rule precedence, and seeded configs.
- [`docs/agent.md`](docs/agent.md) — Formal tool contracts, agentic loop, and execution guard invariants.
- [`docs/ml.md`](docs/ml.md) — Training pipelines, feature schemas, zero-leakage merchant splits, and metrics.
- [`docs/razorpay.md`](docs/razorpay.md) — Webhook verification contracts, live vs. simulated boundaries, and payload specs.
- [`docs/security.md`](docs/security.md) — API authentication, rate limiting, and secret protection policies.
- [`docs/evaluation.md`](docs/evaluation.md) — Batch evaluation methodology over 600 independent test records.
