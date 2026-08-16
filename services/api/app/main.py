import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import settings
from app.db.auto_migrate import run_migrations


@asynccontextmanager
async def lifespan(_: FastAPI):
    # run_migrations drives an async engine with asyncio.run(), so run it in
    # a worker thread -- we're already inside uvicorn's event loop here. It
    # is belt-and-braces on top of entrypoint.sh: some PaaS setups (Render
    # custom start command, Railway) override the Docker CMD, so migrate here
    # too -- the API must never serve against a schema its code doesn't
    # understand. The runner heals DBs created outside Alembic (see
    # app/db/auto_migrate.py).
    try:
        await asyncio.to_thread(run_migrations)
    except Exception as exc:  # noqa: BLE001 -- never block startup on a
        # migration problem; log it so a deploy still swaps in and the exact
        # failure is visible in the host's logs (the API's DB queries will
        # fail loudly on their own if the schema is genuinely out of date).
        print(f"[startup] migration FAILED (continuing): {exc}", flush=True)
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


@app.get("/", tags=["health"], include_in_schema=False)
async def root() -> dict[str, str]:
    # Some PaaS setups (Render HTTP health checks, uptime monitors) probe the
    # root path. Return 200 so a deploy can never fail purely on the health
    # check path; the real health signal is /healthz.
    return {"service": "viralcut-api", "status": "ok"}
