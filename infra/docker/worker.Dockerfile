FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# db_models is a shared package (SQLAlchemy models used by both this worker
# and the FastAPI service) -- put it on PYTHONPATH so `import db_models`
# resolves regardless of WORKDIR.
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
COPY workers ./workers

CMD ["celery", "-A", "workers.celery_app:celery_app", "worker", "--loglevel=info"]
