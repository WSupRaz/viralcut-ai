from workers.celery_app import celery_app


@celery_app.task(name="workers.tasks.health.ping")
def ping(echo: str = "pong") -> dict[str, str]:
    """No-op task used to prove broker -> worker -> result-backend round trip."""
    return {"status": "ok", "echo": echo}
