"""Keep a free-tier PaaS web service awake for the duration of a task.

Render spins down a free web service after 15 minutes with no *inbound
traffic* -- CPU activity does not count, so a long ffmpeg transcode looks
exactly like an idle service. When that happens mid-task the container is
killed, its local filesystem (the temp dir holding the downloaded source and
partial output) is discarded, and because Celery acks a task on receipt the
task is simply gone: the job row stays frozen at whatever progress it last
wrote, forever, with no error recorded anywhere.

`app.core.celery_client.send_task` already pings the worker when a task is
*enqueued*, which wakes a sleeping worker up -- but that is a single request
at the one moment the service is guaranteed to be busy anyway. This module
covers the rest of the task's life.

The heartbeat runs only while at least one task is in flight, not on a timer
forever: keeping a service awake around the clock would burn the free tier's
pooled instance-hours (750/month across all services, and a month is ~730
hours) on an otherwise-idle worker.
"""

import os
import threading

import httpx

# Comfortably inside Render's 15-minute idle window, with room for a couple of
# consecutive failed pings before the service would actually be spun down.
HEARTBEAT_INTERVAL_SECONDS = 240
HEARTBEAT_TIMEOUT_SECONDS = 10.0

_lock = threading.Lock()
_active_tasks = 0
_stop_event: threading.Event | None = None


def external_url() -> str:
    """The service's own public URL -- the ping has to arrive through the
    platform's edge to count as inbound traffic, so localhost won't do.

    RENDER_EXTERNAL_URL is injected automatically for Render web services;
    WORKER_WAKE_URL is the manually-configured equivalent from the deploy
    runbook (docs/05-deployment.md). Empty on hosts that never sleep (local
    dev, any always-on deployment), which disables the heartbeat entirely.
    """
    return os.environ.get("RENDER_EXTERNAL_URL") or os.environ.get("WORKER_WAKE_URL", "")


def _beat(url: str, stop: threading.Event) -> None:
    # stop.wait() doubles as the sleep: it returns early the moment the last
    # in-flight task finishes, so an idle worker stops pinging immediately
    # rather than after one more full interval.
    while not stop.wait(HEARTBEAT_INTERVAL_SECONDS):
        try:
            httpx.get(url, timeout=HEARTBEAT_TIMEOUT_SECONDS)
        except Exception:
            # Best-effort: a failed ping is not worth failing the task over,
            # and the next one is only a few minutes out.
            pass


def task_started() -> None:
    global _active_tasks, _stop_event

    url = external_url()
    if not url:
        return

    with _lock:
        _active_tasks += 1
        if _stop_event is None:
            _stop_event = threading.Event()
            threading.Thread(
                target=_beat, args=(url, _stop_event), daemon=True, name="keepalive"
            ).start()


def task_finished() -> None:
    global _active_tasks, _stop_event

    with _lock:
        _active_tasks = max(0, _active_tasks - 1)
        if _active_tasks == 0 and _stop_event is not None:
            _stop_event.set()
            _stop_event = None
