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
        ["celery", "-A", "workers.celery_app:celery_app", "worker", "--loglevel=info"],
        check=True,
    )
