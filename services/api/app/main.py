import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from alembic import command
from alembic.config import Config as AlembicConfig
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import settings


def _run_migrations() -> None:
    """Apply pending Alembic migrations. Belt-and-braces on top of
    entrypoint.sh: some PaaS setups (Render custom start command, Railway)
    override the Docker CMD, so migrate here too -- the API must never serve
    against a schema its code doesn't understand. Migrations are idempotent
    and Alembic's version table makes this a no-op once up to date."""
    api_dir = Path(__file__).resolve().parents[1]
    cfg = AlembicConfig(str(api_dir / "alembic.ini"))
    cfg.set_main_option("script_location", str(api_dir / "app/db/migrations"))
    command.upgrade(cfg, "head")


@asynccontextmanager
async def lifespan(_: FastAPI):
    # env.py drives an async engine with asyncio.run(), so run it in a worker
    # thread -- we're already inside uvicorn's event loop here.
    try:
        await asyncio.to_thread(_run_migrations)
    except Exception as exc:  # noqa: BLE001 -- never block startup on a
        # migration problem; log it so a deploy still swaps in and the exact
        # failure is visible in the host's logs (the API's DB queries will
        # fail loudly on their own if the schema is genuinely out of date).
        print(f"[startup] alembic upgrade head FAILED (continuing): {exc}", flush=True)
    yield


app = FastAPI(title="ViralCut AI API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)


@app.get("/healthz", tags=["health"])
async def healthz() -> dict[str, str]:
    return {"status": "ok"}
