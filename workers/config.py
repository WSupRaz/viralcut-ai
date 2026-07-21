from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    celery_broker_url: str = "redis://redis:6379/0"
    celery_result_backend: str = "redis://redis:6379/1"

    database_url: str

    r2_account_id: str = ""
    r2_access_key_id: str = ""
    r2_secret_access_key: str = ""
    r2_bucket_name: str = "viralcut-assets"
    # Overrides the computed R2 endpoint; used in dev to point at MinIO instead.
    r2_endpoint_url: str | None = None

    openai_api_key: str = ""
    # Optional fallback ASR provider, used only if the OpenAI call fails.
    groq_api_key: str = ""

    anthropic_api_key: str = ""
    # Optional fallback edit-plan provider, used only if the Claude call fails.
    openrouter_api_key: str = ""

    render_worker_url: str = "http://render-worker:3001"

    @property
    def sync_database_url(self) -> str:
        """DATABASE_URL is asyncpg-flavored for the FastAPI service; workers
        run Celery tasks synchronously, so use the sync psycopg driver
        instead (asyncpg connections aren't safe to share across Celery's
        prefork worker processes)."""
        return self.database_url.replace("postgresql+asyncpg://", "postgresql+psycopg://")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
