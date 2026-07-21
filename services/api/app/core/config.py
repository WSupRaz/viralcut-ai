from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    redis_url: str = "redis://redis:6379/0"
    celery_broker_url: str = "redis://redis:6379/0"

    jwt_secret: str
    jwt_expires_in_minutes: int = 10080

    r2_account_id: str = ""
    r2_access_key_id: str = ""
    r2_secret_access_key: str = ""
    r2_bucket_name: str = "viralcut-assets"
    r2_public_base_url: str = ""
    # Overrides the computed R2 endpoint; used in dev to point at MinIO instead.
    r2_endpoint_url: str | None = None
    # Overrides r2_endpoint_url specifically for presigned URLs handed to the
    # browser. In dev, R2_ENDPOINT_URL is the Docker-internal MinIO hostname
    # (http://minio:9000), unreachable from a browser on the host -- the
    # presigned URL's host must be one the browser can actually resolve.
    # Doesn't apply to real R2 in prod (one public endpoint for everyone),
    # so this only needs to be set for local dev.
    r2_public_endpoint_url: str | None = None

    allowed_origins: list[str] = ["http://localhost:3000"]

    # Best-effort "wake up" ping fired at the worker's public URL whenever a
    # task is enqueued -- needed only on free-tier PaaS hosts (e.g. Render)
    # that spin a service down after idle HTTP traffic; the Celery worker's
    # actual work (consuming Redis) isn't something those platforms see as
    # "activity". Leave unset where the worker doesn't sleep (local dev, or
    # any always-on host).
    worker_wake_url: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
