#!/bin/sh
# Apply pending DB migrations before serving. This is what makes PaaS deploys
# (Render, Railway) self-healing: a deploy ships new code that queries new
# columns, so the schema must be upgraded before uvicorn accepts traffic.
#
# If the migration fails (e.g. the DB's alembic_version is not an ancestor of
# this code's migration chain), the failure is logged and the API still boots:
# a crash-looping container would keep the host pinned to the previous deploy
# forever, hiding the error. The log line below is the diagnosis -- paste it
# back if it ever appears.
set -e

echo "[entrypoint] Current DB revision: $(alembic current 2>&1 | tail -1)"

if alembic upgrade head; then
  echo "[entrypoint] Migrations up to date."
else
  echo "[entrypoint] WARNING: 'alembic upgrade head' FAILED -- starting anyway; the error above is the diagnosis." >&2
fi

echo "[entrypoint] Starting API on 0.0.0.0:${PORT:-8000}"
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
