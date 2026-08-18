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
    # SigV4 signing region. "auto" is the Cloudflare R2 convention and is
    # what this app has always sent; Backblaze accepts it (every write call
    # against B2 succeeds with it). Configurable so a provider that does
    # validate the region against its endpoint can be given the real one
    # (e.g. us-east-005) without a code change.
    r2_region: str = "auto"
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

    # Browser origins allowed to call the API. The frontend is deployed to
    # Vercel, whose deployment + preview URLs change on every push, so main.py
    # also allows any *.vercel.app origin via regex -- explicit entries here
    # are for local dev and any custom domain. Accepts a JSON array or a
    # comma-separated list in the ALLOWED_ORIGINS env var.
    allowed_origins: list[str] = ["http://localhost:3000"]

    # Hard cap for a single source-video upload. 5 GiB matches the S3
    # single-PUT ceiling; anything the UI allows must be ≤ this. Override
    # via MAX_UPLOAD_BYTES in the environment.
    max_upload_bytes: int = 5 * 1024 * 1024 * 1024

    # Abandoned-upload sweep: a pending (never-completed) upload session
    # older than this is aborted and removed when a new upload starts in the
    # same project. Bounds orphaned multipart uploads without needing a
    # scheduled job.
    abandoned_upload_ttl_hours: int = 24

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
