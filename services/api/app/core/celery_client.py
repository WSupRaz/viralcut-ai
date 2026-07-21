import httpx
from celery import Celery

from app.core.config import settings

# Dispatch-only client: the API enqueues tasks by name (send_task) without
# importing the workers package -- that's a separate deployable, and
# importing its task modules here would blur the boundary between the two
# services for no benefit (send_task needs only the task name + args).
celery_client = Celery("viralcut-api-client", broker=settings.celery_broker_url)


def send_task(*args, **kwargs):
    """Enqueue a task, then best-effort ping the worker's public URL.

    Free-tier PaaS (Render) spins a web service down after 15 minutes with
    no HTTP traffic. The Celery worker only consumes from Redis, which the
    platform can't see as "activity" -- without this ping, a sleeping
    worker would never wake up to pick up the task it was just given.
    No-op if WORKER_WAKE_URL isn't set (local dev, or any host where the
    worker process never sleeps).
    """
    result = celery_client.send_task(*args, **kwargs)
    if settings.worker_wake_url:
        try:
            httpx.get(settings.worker_wake_url, timeout=2.0)
        except httpx.HTTPError:
            pass
    return result
