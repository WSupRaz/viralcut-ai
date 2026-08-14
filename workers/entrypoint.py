import os
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer


class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"ok")

    def log_message(self, format: str, *args) -> None:
        pass


def serve_health() -> None:
    port = int(os.environ.get("PORT", 8000))
    HTTPServer(("0.0.0.0", port), HealthHandler).serve_forever()


if __name__ == "__main__":
    # Free-tier PaaS hosts (Render) only offer a "Background Worker" service
    # type on paid plans; the free "Web Service" type requires binding a
    # port and answering HTTP health checks. This thread exists purely to
    # satisfy that requirement -- the actual work still happens in the
    # Celery worker process below. See app.core.celery_client.send_task for
    # the other half (waking this service back up after it idles out).
    threading.Thread(target=serve_health, daemon=True).start()
    subprocess.run(
        [
            "celery",
            "-A",
            "workers.celery_app:celery_app",
            "worker",
            "--loglevel=info",
            # Celery's prefork pool defaults concurrency to the container's
            # reported CPU count, with no idea how little RAM a free-tier
            # instance actually has (512MB). Each forked process can run
            # ffmpeg/ASR/Claude calls, so 8 of them (this host's CPU count)
            # running concurrently reliably OOMs and gets silently killed
            # mid-task -- the task just vanishes with no error, and the
            # service restarts from scratch. One process at a time is safe;
            # revisit only after moving off the free tier.
            "--concurrency=1",
            # Embed the beat scheduler in the same process: a separate beat
            # container would be another always-on free-tier instance for one
            # hourly housekeeping task. At this scale the embedded scheduler
            # (runs the abandoned-upload sweep every hour) is the right
            # trade; split it out if the schedule ever grows.
            "-B",
        ],
        check=True,
    )
