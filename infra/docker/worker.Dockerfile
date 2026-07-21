FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# db_models and edit_plan_schema are shared packages (used by both this
# worker and the FastAPI service) -- put them on PYTHONPATH so
# `import db_models` / `import edit_plan_schema` resolve regardless of WORKDIR.
ENV PYTHONPATH=/app/packages

# ffmpeg + build deps for PySceneDetect/av bindings (ADR-0003: ffmpeg + PySceneDetect only)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    ffmpeg \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY workers/requirements.txt ./requirements.txt
RUN pip install -r requirements.txt

COPY packages/db_models ./packages/db_models
COPY packages/edit-plan-schema/python/edit_plan_schema ./packages/edit_plan_schema
COPY workers ./workers

EXPOSE 8000

CMD ["python", "-m", "workers.entrypoint"]
