FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# db_models and edit_plan_schema are shared packages (used by both this API
# and the Celery workers) -- put them on PYTHONPATH so `import db_models` /
# `import edit_plan_schema` resolve regardless of WORKDIR.
ENV PYTHONPATH=/app/packages

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY services/api/requirements.txt ./requirements.txt
RUN pip install -r requirements.txt

COPY packages/db_models ./packages/db_models
COPY packages/edit-plan-schema/python/edit_plan_schema ./packages/edit_plan_schema
COPY services/api ./services/api
COPY services/api/entrypoint.sh ./entrypoint.sh
RUN chmod +x ./entrypoint.sh

WORKDIR /app/services/api

EXPOSE 8000

# Migrate-on-boot then serve. Shell form (not exec form) so $PORT expands --
# Railway (and most PaaS) assign a dynamic port via this env var; falls back
# to 8000 for plain `docker compose up` where nothing sets it.
CMD ["./entrypoint.sh"]
