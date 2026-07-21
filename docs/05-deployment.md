# Deployment

Live-hosting the same stack that already runs via `docker-compose.dev.yml`,
across three providers chosen for account-count minimalism (see the "why"
below): **Vercel** (frontend), **Railway** (API, Celery worker, render-worker,
Postgres, Redis -- all under one account/bill), and **Cloudflare R2** (object
storage, replacing the local MinIO stand-in).

## Why this split, not a single VPS

A single cheap VPS running `docker-compose` as-is would be simpler and
slightly cheaper -- that was the recommendation going in. The founder chose
managed multi-service hosting instead (more scalable, though more accounts).
Given that choice, Railway consolidating API + worker + render-worker +
Postgres + Redis under one account is the minimal version of "managed
multi-service" -- avoids also needing separate Neon and Upstash accounts for
no real benefit at this scale.

One constraint holds either way: render-worker needs real RAM for headless
Chromium, so this doesn't fit a true $0 tier. Budget a small paid tier.

## Prerequisites

- GitHub account (Railway and Vercel both deploy from a connected repo)
- Cloudflare account (for R2)
- Railway account
- Vercel account

## Step 1 -- Push to GitHub

```bash
git remote add origin <your-repo-url>
git push -u origin master
```

## Step 2 -- Cloudflare R2

1. dash.cloudflare.com -> **R2 Object Storage** -> **Create bucket**.
   Name it `viralcut-assets` (or update `R2_BUCKET_NAME` everywhere below to
   match whatever you pick).
2. **R2 -> Manage API tokens -> Create API token**. Permissions: Object
   Read & Write, scoped to that bucket. Save the **Access Key ID** and
   **Secret Access Key** -- the secret is shown once.
3. Note your **Account ID** (R2 landing page, right sidebar).
4. Your R2 endpoint is `https://<account-id>.r2.cloudflarestorage.com`.
   Real R2 has one public endpoint for everyone -- unlike local dev, you do
   **not** need an `R2_PUBLIC_ENDPOINT_URL` override in production.

## Step 3 -- Railway: Postgres + Redis

1. railway.app -> **New Project** -> **Empty Project**.
2. **New -> Database -> Add PostgreSQL**. Railway provisions it and exposes
   a `DATABASE_URL` you'll reference from the other services.
3. **New -> Database -> Add Redis**. Same idea, exposes a connection URL.

Railway's Postgres `DATABASE_URL` comes in the plain `postgresql://` form
(sync-style). The API needs the async-driver variant:
`postgresql+asyncpg://...` -- same credentials/host, just the scheme prefix
changed. Workers need the sync `postgresql+psycopg://...` variant (see
`workers/config.py`'s `sync_database_url` property, which derives it
automatically from an asyncpg-style URL -- so set `DATABASE_URL` everywhere
as `postgresql+asyncpg://...` and workers will do the conversion themselves).

## Step 4 -- Railway: the three app services

In the same Railway project, add three services, each **Deploy from GitHub
repo** pointed at your repo, with these settings:

| Service | Dockerfile path | Notes |
|---|---|---|
| `api` | `infra/docker/api.Dockerfile` | Set **Root Directory** to repo root (build context needs `packages/`, `services/api/`) |
| `worker` | `infra/docker/worker.Dockerfile` | No public port needed -- background worker |
| `render-worker` | `infra/docker/render-worker.Dockerfile` | Needs more RAM than the default plan -- bump it in service settings if renders fail/OOM |

Railway auto-detects the Dockerfile's `EXPOSE` and assigns `$PORT` for `api`
and `render-worker` (both already read `$PORT`, see
`docs/adr/` and the Dockerfiles). `worker` doesn't need a public domain --
leave networking off for it.

### Environment variables (all three services)

Copy from `.env.example`, with these production-specific changes:

```
DATABASE_URL=postgresql+asyncpg://<railway-postgres-credentials>
CELERY_BROKER_URL=<railway-redis-url>/0
CELERY_RESULT_BACKEND=<railway-redis-url>/1

R2_ENDPOINT_URL=https://<account-id>.r2.cloudflarestorage.com
R2_ACCOUNT_ID=<account-id>
R2_ACCESS_KEY_ID=<from Step 2>
R2_SECRET_ACCESS_KEY=<from Step 2>
R2_BUCKET_NAME=viralcut-assets
# R2_PUBLIC_ENDPOINT_URL: leave unset in production -- see Step 2 note.

RENDER_WORKER_URL=<railway-internal-url-for-render-worker-service>

JWT_SECRET=<generate a real random secret, e.g. `openssl rand -hex 32`>

ANTHROPIC_API_KEY=...
OPENROUTER_API_KEY=...
OPENAI_API_KEY=...
GROQ_API_KEY=...

ALLOWED_ORIGINS=["https://<your-vercel-domain>"]
```

Railway services in the same project can reach each other over its internal
network by service name -- use that for `RENDER_WORKER_URL` rather than the
public URL (faster, and doesn't require render-worker to have a public
domain at all).

`api` additionally needs `JWT_EXPIRES_IN_MINUTES`, `R2_BUCKET_NAME`, etc. --
same var names as `.env.example`, just real values instead of the MinIO dev
defaults.

## Step 5 -- Run migrations

One-off, after the `api` service's first successful deploy. Railway's
dashboard has a "Run a command" / shell feature per service -- run:

```bash
cd services/api && alembic upgrade head
```

Re-run this any time a new migration is added (same manual, deliberate step
used throughout local development -- no auto-migrate-on-boot, to avoid
concurrent migration races if a service restarts mid-deploy).

## Step 6 -- Vercel: frontend

1. vercel.com -> **Add New -> Project** -> import your GitHub repo.
2. **Root Directory**: `apps/web`.
3. Framework preset: Next.js (auto-detected).
4. Environment variable: `NEXT_PUBLIC_API_URL=https://<your-railway-api-public-url>`.
5. Deploy.

Vercel gives you a `*.vercel.app` domain automatically -- no custom domain
needed yet (per the "use IP/subdomain for now" decision).

## Step 7 -- Close the loop: CORS

Once Vercel gives you its real domain, go back to the `api` service's env
vars on Railway and set:

```
ALLOWED_ORIGINS=["https://your-actual-project.vercel.app"]
```

Redeploy `api` for the change to take effect.

## Step 8 -- Verify

1. Open the Vercel URL, sign up, create a project, upload a short clip.
2. Watch it progress through proxy -> metadata (auto-chained) in the UI.
3. Trigger edit-plan generation, then export, via the API directly (job
   progress UI for these two steps is task 15/16 -- not yet in the frontend
   as of this doc).
4. Confirm the final export downloads and plays.

## Costs

Same per-video cost model as `docs/04-roadmap.md` (~$0.15-0.25/video in AI
provider calls) plus fixed monthly hosting: Railway's usage-based pricing
for four services (api, worker, render-worker, Postgres, Redis) plus
Vercel's free tier for the frontend. Render-worker's RAM requirement is the
main lever on the Railway bill -- watch it after the first few real renders
and size the plan to actual usage rather than guessing upfront.
