from celery import Celery

from workers.config import settings

celery_app = Celery(
    "viralcut",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=[
        "workers.tasks.health",
        "workers.tasks.cleanup",
        "workers.tasks.proxy",
        "workers.tasks.metadata_extraction",
        "workers.tasks.edit_plan",
        "workers.tasks.render_dispatch",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    result_expires=3600,
    broker_connection_retry_on_startup=True,
)

celery_app.conf.beat_schedule = {
    # Abandoned (never-completed) upload sessions older than the TTL are
    # aborted/removed hourly -- the API-side sweep only fires when a new
    # upload starts in the same project, which misses abandoned projects.
    "sweep-abandoned-uploads": {
        "task": "workers.tasks.cleanup.sweep_abandoned_uploads",
        "schedule": 3600.0,
    },
}
