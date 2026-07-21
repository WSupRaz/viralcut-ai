from celery import Celery

from app.core.config import settings

# Dispatch-only client: the API enqueues tasks by name (send_task) without
# importing the workers package -- that's a separate deployable, and
# importing its task modules here would blur the boundary between the two
# services for no benefit (send_task needs only the task name + args).
celery_client = Celery("viralcut-api-client", broker=settings.celery_broker_url)
