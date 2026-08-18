import asyncio
import traceback
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.api.v1.router import api_router
from app.core.abuse import SecurityHeadersMiddleware
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


class UnhandledErrorMiddleware(BaseHTTPMiddleware):
    """Turn an unhandled exception into a normal 500 *response*.

    Starlette's ServerErrorMiddleware sits outside every user middleware,
    including CORS, so a 500 it produces carries no Access-Control-Allow-Origin
    header. A browser then cannot read the response at all: fetch rejects with
    an opaque network error and the console reports a CORS failure, hiding the
    fact that the server answered and what it said. Debugging any 500 from the
    client is impossible in that state.

    Catching here -- inside CORSMiddleware -- means the response travels back
    out through it and gets the header, so the client sees a real 500 with a
    readable body. The traceback still goes to the host's logs.
    """

    async def dispatch(self, request: Request, call_next):
        try:
            return await call_next(request)
        except Exception:
            print(
                f"[unhandled] {request.method} {request.url.path}\n{traceback.format_exc()}",
                flush=True,
            )
            return JSONResponse(
                status_code=500,
                content={"detail": "Internal server error. The failure was logged."},
            )


app = FastAPI(title="ViralCut AI API", version="0.1.0", lifespan=lifespan)

# Registration order matters and is inverted: add_middleware inserts at the
# front, so the LAST one added is the outermost. CORS must be outermost so it
# can stamp headers on responses produced by everything inside it, including
# UnhandledErrorMiddleware's 500s.
app.add_middleware(UnhandledErrorMiddleware)
app.add_middleware(SecurityHeadersMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    # The frontend is a Vercel deployment whose URL changes on every push;
    # regex covers all current + future *.vercel.app origins (any user who
    # could reach the API through one already has a token; this only controls
    # what a browser may send/read). Explicit origins in settings.allowed_origins
    # cover local dev and any custom domain.
    allow_origin_regex=r"https://.*\.vercel\.app",
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
