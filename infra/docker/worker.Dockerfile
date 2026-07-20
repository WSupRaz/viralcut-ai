FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# ffmpeg + build deps for PySceneDetect/av bindings (ADR-0003: ffmpeg + PySceneDetect only)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    ffmpeg \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY workers/requirements.txt ./requirements.txt
RUN pip install -r requirements.txt

COPY workers ./workers
COPY packages/edit-plan-schema ./packages/edit-plan-schema

CMD ["celery", "-A", "workers.celery_app", "worker", "--loglevel=info"]
