#!/bin/sh
# Apply pending DB migrations before serving. This is what makes PaaS deploys
# (Render, Railway) self-healing: a deploy ships new code that queries new
# columns, so the schema must be upgraded before uvicorn accepts traffic.
# Migrations are idempotent (IF NOT EXISTS) so concurrent replica boots are
# safe; Alembic's version table means this is a no-op once up to date.
set -e

echo "[entrypoint] Applying database migrations..."
alembic upgrade head
echo "[entrypoint] Migrations up to date."

echo "[entrypoint] Starting API on 0.0.0.0:${PORT:-8000}"
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
