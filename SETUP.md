# SETUP

Exact, copy-pasteable commands to get Recovery Orchestrator running
locally in VS Code. For narrative documentation (architecture, ML
metrics, policy config, etc.) see `README.md` and `docs/`.

Two paths: **Local (no Docker)** and **Docker Compose**. Pick one.

---

## 0. Prerequisites

- Python 3.12+
- Node.js 20+ and npm
- PostgreSQL 14+ (local install) **or** Docker + Docker Compose
- Git

Verify:

```bash
python3 --version
node --version
npm --version
psql --version        # only needed for the non-Docker path
docker --version       # only needed for the Docker path
docker compose version # only needed for the Docker path
```

---

## Path A: Local setup (no Docker)

### 1. Clone / open in VS Code

```bash
cd razorpay-recovery-agent-final
code .
```

### 2. PostgreSQL setup

Create the database (adjust user/password to your local Postgres):

```bash
# Option 1: using createdb
createdb recovery_orchestrator

# Option 2: using psql directly
psql -U postgres -c "CREATE DATABASE recovery_orchestrator;"
```

If you don't have a local PostgreSQL server, install one:

```bash
# macOS
brew install postgresql@16
brew services start postgresql@16

# Ubuntu/Debian
sudo apt-get install postgresql postgresql-contrib
sudo service postgresql start
```

### 3. Environment setup

```bash
cp .env.example .env
```

Edit `.env` and set at minimum:
- `DATABASE_URL` / `DATABASE_URL_ASYNC` — match your local Postgres
  credentials (default assumes `postgres`/`postgres`@`localhost:5432`)
- `API_KEY` — generate one:
  ```bash
  python3 -c "import secrets; print(secrets.token_urlsafe(32))"
  ```
  Paste the output as `API_KEY=...` in `.env`. **Required** — the app
  fails closed (503) on protected endpoints without it, by design.

Optional (leave blank to run in simulated-only mode, which is the
default and fully functional):
- `RAZORPAY_KEY_ID`, `RAZORPAY_KEY_SECRET`, `RAZORPAY_WEBHOOK_SECRET`
- `LLM_API_KEY`, `LLM_MODEL`

### 4. Backend setup

```bash
cd backend
python3 -m venv .venv

# macOS/Linux
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt

# Windows (PowerShell)
# .venv\Scripts\pip install --upgrade pip
# .venv\Scripts\pip install -r requirements.txt
```

### 5. Database migrations

```bash
# still inside backend/
.venv/bin/alembic upgrade head
```

### 6. Policy seeding

```bash
.venv/bin/python -m app.policies.seed_policies
```

### 7. Train the ML models

Required once — the app reads trained model artifacts from
`data/models/`. Pretrained artifacts are already included in this
archive, so this step is **optional** unless you want to retrain:

```bash
.venv/bin/python -m app.ml.train_cause_classifier
.venv/bin/python -m app.ml.train_recovery_probability
```

### 8. Run tests

```bash
# still inside backend/
.venv/bin/python -m pytest -v
```

Expect `175 passed`. Requires the PostgreSQL database from step 2 to
be running and reachable via the `DATABASE_URL` in `.env`.

### 9. Run the backend

```bash
# still inside backend/
.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Backend is now live at http://localhost:8000 (interactive API docs at
http://localhost:8000/docs).

### 10. Frontend setup

Open a **second terminal**:

```bash
cd frontend
npm install
cp .env.example .env
```

Edit `frontend/.env` and set `VITE_API_KEY` to the **same** value as
the backend's `API_KEY` (step 3).

### 11. Run the frontend

```bash
# still inside frontend/
npm run dev
```

Dashboard is now live at http://localhost:5173 (Vite's dev server
proxies `/api/*` to the backend on port 8000 automatically — see
`frontend/vite.config.ts`).

### 12. Generate synthetic data (if `data/processed/*.csv` are missing)

Pretrained data is already included in this archive. To regenerate:

```bash
cd data/synthetic_generator
python3 generate.py --n-records 750 --n-merchants 18 --seed 42
python3 generate.py --n-records 600 --n-merchants 18 --seed 999 --output-dir ..
```

(The second command's output needs to be saved as
`data/processed/evaluation.csv` — see `docs/evaluation.md` for the
exact independent-evaluation-set generation process.)

---

## Path B: Docker Compose

```bash
cp .env.example .env
```

Edit `.env` and set a real `API_KEY` (same as step 3 above) — the
compose file uses `${API_KEY:?...}` and refuses to start without one.

```bash
docker compose up --build
```

- Backend: http://localhost:8000
- Frontend: http://localhost:3000
- Postgres: localhost:5432

The backend container's entrypoint (`backend/docker-entrypoint.sh`)
automatically waits for Postgres, runs migrations, and seeds policies
on startup — steps 5 and 6 above happen automatically in this path.

**Note**: this has not been run end-to-end in the environment that
built this project (see `docker-compose.yml`'s header comment and
`README.md`'s Limitations section for exactly what was and wasn't
verified). If anything fails on your machine, it's most likely a
first-real-run issue worth reporting, not a known gap.

---

## Quick reference: all commands in one block (local path)

```bash
# One-time setup
createdb recovery_orchestrator
cp .env.example .env   # then edit: set API_KEY, check DATABASE_URL

cd backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/alembic upgrade head
.venv/bin/python -m app.policies.seed_policies
.venv/bin/python -m pytest -v          # optional: verify everything passes

# Terminal 1 -- backend
.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload

# Terminal 2 -- frontend
cd frontend
npm install
cp .env.example .env   # then edit: set VITE_API_KEY to match backend's API_KEY
npm run dev
```

Then open http://localhost:5173.
