# Recovery Orchestrator -- Backend Dockerfile
#
# NOT BUILT OR RUN in the sandbox that authored this repository (no
# Docker daemon was available there). Written carefully against the
# actual requirements.txt and app structure, but `docker build` /
# `docker compose up` need to be run by you to confirm it works end
# to end.

FROM python:3.12-slim AS base

# Verified via `ldd` against the actual installed wheels (not assumed):
# psycopg2-binary bundles its own libpq, libssl, libcrypto, etc.
# (psycopg2_binary.libs/), and xgboost bundles its own libgomp
# (xgboost.libs/) -- neither needs libpq-dev, gcc, or libgomp1 installed
# at the OS level. Only curl is genuinely needed, for HEALTHCHECK.
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

COPY . .

RUN chmod +x docker-entrypoint.sh

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --start-period=30s --retries=5 \
    CMD curl -f http://localhost:8000/api/v1/health || exit 1

ENTRYPOINT ["./docker-entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
