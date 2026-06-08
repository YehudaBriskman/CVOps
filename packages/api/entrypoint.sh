#!/bin/sh
set -e

echo "[entrypoint] Running database migrations..."
alembic upgrade head

echo "[entrypoint] Starting API server..."
exec uvicorn cvops_api.main:app --host 0.0.0.0 --port 8000
