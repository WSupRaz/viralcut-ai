from celery import Celery
from celery.signals import task_postrun, task_prerun

from workers import keepalive
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


# Registered here rather than per-task so every task -- proxy, metadata, edit
# plan, render -- is covered automatically. Under the prefork pool these fire
# inside the child process running the task, so the heartbeat thread's
# lifetime is scoped to exactly that task.
@task_prerun.connect
def _keepalive_task_started(**_kwargs) -> None:
    keepalive.task_started()


@task_postrun.connect
def _keepalive_task_finished(**_kwargs) -> None:
    keepalive.task_finished()


celery_app.conf.beat_schedule = {
    # Abandoned (never-completed) upload sessions older than the TTL are
    # aborted/removed hourly -- the API-side sweep only fires when a new
    # upload starts in the same project, which misses abandoned projects.
    "sweep-abandoned-uploads": {
        "task": "workers.tasks.cleanup.sweep_abandoned_uploads",
        "schedule": 3600.0,
    },
}
