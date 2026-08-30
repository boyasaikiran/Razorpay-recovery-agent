#!/bin/sh
set -e

echo "Waiting for PostgreSQL to be ready..."
until python -c "
import sys
import psycopg2
from app.core.config import get_settings
settings = get_settings()
url = settings.database_url.replace('postgresql+psycopg2', 'postgresql')
try:
    conn = psycopg2.connect(url)
    conn.close()
except Exception as e:
    print(f'DB not ready: {e}')
    sys.exit(1)
"; do
  sleep 1
done
echo "PostgreSQL is ready."

echo "Running Alembic migrations..."
alembic upgrade head

echo "Seeding default policies (idempotent)..."
python -m app.policies.seed_policies || echo "Policy seeding skipped/failed (non-fatal, may already be seeded)."

echo "Starting application: $@"
exec "$@"
