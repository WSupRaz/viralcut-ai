# Deployment

Live-hosting the same stack that already runs via `docker-compose.dev.yml`,
across four providers: **Vercel** (frontend), **Render** (API, Celery
worker, render-worker -- three separate services), **Neon** (Postgres), and
**Upstash** (Redis), plus **Backblaze B2** for object storage.

## Why four providers, not Railway

The original plan was Railway (API + worker + render-worker + Postgres +
Redis under one account) -- the minimal version of "managed multi-service"
hosting. Railway turned out to require a paid Hobby plan ($5/mo, needs a
card on file) to run databases or keep services alive past a short trial
credit. The founder has no card available, so Railway is out entirely, not
just for its database (same problem that ruled out Cloudflare R2 -- see
Step 2).

Neon (Postgres), Upstash (Redis), and Render (compute) each have a
permanently free tier that needs no card. Splitting across three providers
instead of one is the cost of avoiding a card, not a preference.

### The tradeoffs of going card-free

- **Render's free "Web Service" sleeps after 15 minutes of no HTTP
  traffic**, with a 30-60s cold start on the next request. Fine for
  personal, occasional use; a visitor hitting a cold API will just wait a
  bit on the first request.
- **Render has no free "Background Worker" service type** (that's
  paid-only) -- only free "Web Service". The Celery worker doesn't
  naturally serve HTTP, so `workers/entrypoint.py` now runs a trivial
  health-check HTTP server alongside the Celery process purely so Render
  will accept it as a free Web Service. See that file's comment for why.
- **A sleeping worker won't wake itself** -- consuming from Redis isn't
  something Render sees as "activity". `app/core/celery_client.py`'s
  `send_task()` fires a best-effort HTTP ping at `WORKER_WAKE_URL` (the
  worker's own public Render URL) every time a task is enqueued, which
  wakes it if asleep and is a harmless no-op if already awake.
- **512MB RAM on Render's free tier is tight for headless Chromium.**
  render-worker (Remotion) is the one service most likely to hit this
  ceiling on longer/larger renders. If renders start failing with OOM,
  that's the first thing to suspect -- the fix at that point is upgrading
  just that one service to a paid Render plan, not the whole stack.
- **Neon's free Postgres scales to zero after 5 minutes idle**, with a
  brief cold-start reconnect. Not an issue for a single-user app used
  occasionally.

## Prerequisites

- GitHub account (Render and Vercel both deploy from a connected repo)
- Backblaze account (object storage)
- Neon account (Postgres)
- Upstash account (Redis)
- Render account (API, worker, render-worker)
- Vercel account (frontend)

None of these require a payment card for this app's scale.

## Step 1 -- Push to GitHub

```bash
git remote add origin <your-repo-url>
git push -u origin master
```

## Step 2 -- Backblaze B2 (object storage)

1. backblaze.com -> sign up (no card required for a private bucket).
2. **Buckets -> Create a Bucket**. Name it something globally-unique like
   `viralcut-assets-<yourname>` (update `R2_BUCKET_NAME` everywhere below to
   match). Files in Bucket: **Private** (required -- and the only setting
   B2's free tier needs to stay card-free). Default Encryption: Disable.
   Object Lock: Disable (this app overwrites/deletes objects on retry --
   Object Lock would block that).
3. **Application Keys -> Add a New Application Key**. Name it, scope
   **Allow access to Bucket(s)** to just that bucket, Read and Write access.
   Save the **keyID** and **applicationKey** -- the key is shown once.
4. On the bucket's detail page, note the **Endpoint** field, e.g.
   `s3.us-east-005.backblazeb2.com` (region varies by account). Prefix it
   with `https://` for the env var below.

B2's S3-compatible endpoint is the same for every bucket in your account
(not per-bucket) -- unlike local dev's MinIO split, you do **not** need an
`R2_PUBLIC_ENDPOINT_URL` override in production. The app's storage client
(`R2_ENDPOINT_URL` etc.) is provider-agnostic -- B2 is a drop-in
S3-compatible swap for R2, same variable names throughout.

**CORS is mandatory.** The browser PUTs uploaded parts *directly* to B2 via
presigned URLs (cross-origin, from your Vercel domain to B2). Without a CORS
policy on the bucket, the browser aborts every part PUT before it starts
(the upload sits at 0% and eventually reports "Upload paused due to network
issues"; B2 answers the preflight with `403 AccessDenied: This CORS request
is not allowed`). There's a one-command script -- same S3 PutBucketCors API
the provider console uses, so it works for B2, R2, MinIO, and AWS S3:

```bash
# B2: endpoint is your account's S3-compatible endpoint, e.g.
# https://s3.us-east-005.backblazeb2.com (NOT the console URL). Keys are the
# application-keyID/applicationKey from Step 2. --origin repeatable.
R2_ENDPOINT_URL=https://<s3-endpoint> \
R2_ACCESS_KEY_ID=<keyID> R2_SECRET_ACCESS_KEY=<applicationKey> \
R2_BUCKET_NAME=<bucket> \
  python infra/scripts/configure_bucket_cors.py \
  --origin https://<your-vercel-domain>

# Or the provider console: Bucket -> CORS Rules -> New rule:
#   AllowedOrigins = your Vercel domain (* works for dev but is wider)
#   AllowedMethods = GET, PUT, POST, DELETE, HEAD
#   AllowedHeaders = * | ExposeHeaders = ETag | MaxAgeSeconds = 3600
```

(Local dev's MinIO gets the equivalent via `infra/docker-compose.dev.yml`'s
`minio-init` step -- MinIO's own S3 API rejects `PutBucketCors` on some
builds, a known dev quirk; prod B2/R2 implement it.)

**Lifecycle rule (abandoned uploads).** A browser that dies mid-upload leaves
an open multipart session (and its uploaded parts) on the bucket. The app
sweeps these itself (a Celery beat task every hour, plus on-start), but the
provider should back that up so orphaned sessions can't accrue even if the
worker is down:

```bash
# R2 (or B2 via its S3-compatible endpoint) -- abort incomplete multipart
# uploads 1 day after initiation (matches ABANDONED_UPLOAD_TTL_HOURS=24):
R2_ACCOUNT_ID=... R2_ACCESS_KEY_ID=... R2_SECRET_ACCESS_KEY=... \
R2_BUCKET_NAME=<your bucket> R2_ENDPOINT_URL=https://<s3-endpoint> \
  python infra/scripts/configure_bucket_lifecycle.py
```

R2 also expires incomplete multipart uploads by default after 7 days, so this
just tightens the window; B2 needs the rule. Alternatively use the provider
console: Cloudflare R2 **Bucket -> Settings -> Lifecycle rules**, or B2
**Bucket -> Lifecycle Rules** (action: abort incomplete multipart uploads,
1 day). Local dev's MinIO may reject the S3 lifecycle API on some builds -- a
known MinIO quirk; dev cleanup is covered by the in-app sweeps, so ignore the
error there.

## Step 3 -- Neon (Postgres)

1. neon.tech -> sign up (no card required).
2. **Create a project**. Any name/region.
3. On the project dashboard, copy the **Connection string** -- it comes in
   the plain `postgresql://` form.

The API needs the async-driver variant: `postgresql+asyncpg://...` -- same
credentials/host, just the scheme prefix changed. Workers need the sync
`postgresql+psycopg://...` variant (see `workers/config.py`'s
`sync_database_url` property, which derives it automatically from an
asyncpg-style URL -- so set `DATABASE_URL` everywhere as
`postgresql+asyncpg://...` and workers convert it themselves). Neon's connection string usually includes `?sslmode=require&channel_binding=require`
-- drop both. `asyncpg` doesn't understand either one; use `?ssl=require`
instead (SQLAlchemy's asyncpg dialect translates that into the `sslmode`
kwarg asyncpg actually validates against -- `sslmode=require` passed
straight through, or `channel_binding`, both fail outright).

## Step 4 -- Upstash (Redis)

1. upstash.com -> sign up (no card required).
2. **Create Database**. Any name/region (pick one close to Render's region
   for lower latency).
3. On the database dashboard, copy the **Redis connection string**
   (`rediss://...` -- note the double `s`, Upstash requires TLS).

Use it for both `CELERY_BROKER_URL` and `CELERY_RESULT_BACKEND`, with
different trailing DB numbers (`/0` and `/1`) same as local dev -- Upstash
supports the standard Redis DB-index namespacing.

## Step 5 -- Render: the three app services

render.com -> sign up (no card required). Then, for each of the three
services below: **New -> Web Service -> Build and deploy from a Git
repository**, connect your GitHub repo, and set:

| Service | Dockerfile path | Notes |
|---|---|---|
| `api` | `infra/docker/api.Dockerfile` | Root Directory = repo root (build context needs `packages/`, `services/api/`) |
| `worker` | `infra/docker/worker.Dockerfile` | Deploy as a **Web Service** (not Background Worker -- that's paid-only). `workers/entrypoint.py` binds a port so this works. |
| `render-worker` | `infra/docker/render-worker.Dockerfile` | Also a Web Service. Bump the instance type if renders OOM (512MB free RAM is tight for headless Chromium). |

Render auto-detects each Dockerfile and injects `$PORT` -- all three
services already read it (`api.Dockerfile`'s CMD, `render-worker`'s
`config.ts`, and the new `workers/entrypoint.py`). Instance type: Free, for
all three, to start.

Render's default health check is a TCP socket probe (it accepts the
connection), so services pass without any configuration -- but if you enable
an HTTP health check path, point it at a route the service actually answers.
`/healthz` for `api` (and the API also answers 200 on `/`), `/` for
`render-worker` and `worker` (`workers/entrypoint.py`'s health server
answers 200 on any path). A wrong HTTP health check path is the classic
cause of "Deploy failed" emails with no obvious crash: Render probes the
path for up to 15 minutes, then cancels the deploy and keeps the old
instance running.

### Environment variables (all three services)

Copy from `.env.example`, with these production-specific changes:

```
DATABASE_URL=postgresql+asyncpg://<user>:<password>@<neon-host>/<db>?ssl=require
CELERY_BROKER_URL=<upstash-rediss-url>/0
CELERY_RESULT_BACKEND=<upstash-rediss-url>/1

R2_ENDPOINT_URL=https://<your-b2-endpoint>
R2_ACCESS_KEY_ID=<keyID from Step 2>
R2_SECRET_ACCESS_KEY=<applicationKey from Step 2>
R2_BUCKET_NAME=<your bucket name from Step 2>
# R2_ACCOUNT_ID: unused by B2, but keep any placeholder value set --
# storage.py's fallback chain only reaches it if R2_ENDPOINT_URL is unset.
# R2_PUBLIC_ENDPOINT_URL: leave unset in production.

RENDER_WORKER_URL=<render-worker's own https://*.onrender.com URL>
WORKER_WAKE_URL=<worker's own https://*.onrender.com URL>  (api and worker only -- render-worker doesn't need this, it's woken by real HTTP calls already)

JWT_SECRET=<generate a real random secret, e.g. `openssl rand -hex 32`>

ANTHROPIC_API_KEY=...
OPENROUTER_API_KEY=...
OPENAI_API_KEY=...
GROQ_API_KEY=...

ALLOWED_ORIGINS=["https://<your-vercel-domain>"]
```

Render services in the same account don't share a private network the way
Railway's do -- use each service's public `*.onrender.com` URL for
`RENDER_WORKER_URL` and `WORKER_WAKE_URL`. That's also exactly what lets
those HTTP calls wake a sleeping service back up.

`api` additionally needs `JWT_EXPIRES_IN_MINUTES`, `R2_BUCKET_NAME`, and
optionally `MAX_UPLOAD_BYTES` (default 5 GiB) / `ABANDONED_UPLOAD_TTL_HOURS`
(default 24) -- same var names as `.env.example`, just real values instead of
the MinIO dev defaults.

**Worker disk, not RAM, is the second constraint.** A 1.2 GB upload needs
>1.2 GB of free space in the worker's temp dir (raw source + 480p proxy
coexist while transcoding). Render's free tier gives instances a small
ephemeral disk; if proxy generation fails with a disk-full style error, set
`TMPDIR` on the worker service to a path on a larger/persistent volume
(`workers/ffmpeg.py` and the pipeline stream everything -- memory is bounded
by the `-threads 1` decode caps already in place, disk is the real floor).

## Step 5b/6 -- Migrations now run automatically on boot

No manual migration step is needed anymore: the `api` container runs
`alembic upgrade head` before uvicorn starts (`infra/docker/api.Dockerfile`
CMD -> `services/api/entrypoint.sh`) *and* again at app startup
(`app/main.py` lifespan) as a fallback for PaaS configs that override the
Docker CMD. Migrations are idempotent (`IF NOT EXISTS`) and Alembic's
version table makes the second run a no-op, so concurrent replica boots are
safe. Every deploy self-heals the schema.

If a migration genuinely fails (e.g. the DB's `alembic_version` doesn't
chain to this code's revisions), the container logs the exact error and
boots anyway -- do **not** treat that as success; the log line starting
`[entrypoint]` is the diagnosis to paste back. Expected healthy boot logs:

```
[entrypoint] Current DB revision: c7d8e9f0a1b2
[entrypoint] Migrations up to date.
[entrypoint] Starting API on 0.0.0.0:8000
```

(Manual alternative, if you ever need it from your own machine:)

```bash
docker compose -f infra/docker-compose.dev.yml build api
docker compose -f infra/docker-compose.dev.yml run --rm \
  -e DATABASE_URL="postgresql+asyncpg://<user>:<password>@<neon-host>/<db>?ssl=require" \
  api alembic upgrade head
```

## Step 7 -- Vercel: frontend

1. vercel.com -> **Add New -> Project** -> import your GitHub repo.
2. **Root Directory**: `apps/web`.
3. Framework preset: Next.js (auto-detected).
4. Environment variable: `NEXT_PUBLIC_API_URL=https://<your-render-api-public-url>`.
5. Deploy.

Vercel gives you a `*.vercel.app` domain automatically -- no custom domain
needed yet (per the "use IP/subdomain for now" decision), and its free tier
needs no card either.

## Step 8 -- Close the loop: CORS

The API allows any `https://*.vercel.app` origin automatically (regex in
`app/main.py`), so a Vercel deploy works with zero CORS config -- Vercel
changes its deployment URL on every push and the API accepts them all.
`ALLOWED_ORIGINS` still works for anything else (a custom domain, local
dev); it accepts a JSON array or comma-separated list:

```
ALLOWED_ORIGINS=["https://your-actual-project.vercel.app","https://app.yourdomain.com"]
```

## Step 8b -- Production-readiness features (built-in, no config)

- **Rate limiting.** In-process sliding-window limits per client IP:
  `register`/`login` at 10/min, upload-starts at 20/min, general requests
  at 600/min. Dependency-free and right-sized for Render's single API
  instance; if the API ever scales horizontally, swap `app/core/abuse.py`
  for a Redis-backed limiter (Redis is already in the stack).
- **Security headers.** OWASP baseline (`X-Content-Type-Options: nosniff`,
  `X-Frame-Options: DENY`, `Referrer-Policy`, `Permissions-Policy`) set by
  `SecurityHeadersMiddleware` in `app/main.py`.
- **Plan limits.** Every tier (free/creator/pro/business) caps projects,
  clips per project, upload size, export quality, and exports per project
  (`app/core/plan_limits.py`). Enforcement is server-side in the service
  layer; the frontend shows live usage and gates uploads client-side using
  `GET /api/v1/plans/me`. The public `GET /api/v1/plans` endpoint drives the
  marketing pricing page. New accounts start on `free`; assigning paid tiers
  is a billing integration (Stripe, Phase 2) -- until then, promote a user
  by updating `users.plan` in the DB directly.
- **Keep-alive.** `.github/workflows/keep-alive.yml` pings every prod
  endpoint every 10 minutes (GitHub Actions cron), which keeps Render's
  free-tier services from sleeping after 15 idle minutes -- no cold-start
  delay for real visitors, at zero cost. Add any new public URLs to the
  `PING_URLS` repo variable (Settings -> Secrets and variables -> Actions
  -> Variables).
- **Abandoned-upload cleanup.** A Celery beat task (`-B` embedded in the
  worker) sweeps pending multipart sessions hourly, plus the bucket
  lifecycle rule from Step 2 as the provider-side backstop.

## Step 9 -- Verify

1. Open the Vercel URL, sign up, create a project, upload a short clip.
2. Watch it progress through proxy -> metadata (auto-chained) in the UI.
   The first request may take 30-60s if `api` or `worker` had gone idle.
3. Trigger edit-plan generation, then export, via the API directly (job
   progress UI for these two steps is task 15/16 -- not yet in the frontend
   as of this doc).
4. Confirm the final export downloads and plays. If the render fails with
   an OOM-looking error, that's the 512MB free-tier RAM ceiling on
   `render-worker` -- bump just that service to a paid instance type.

If the API returns `500` on `GET /projects/{id}/source-videos` after a
deploy, the schema migration didn't apply -- check the `api` service's
Render logs for the `[entrypoint]` line (see Step 5b/6). With the current
code this is self-healing: a fresh deploy runs the migration on boot.

## Costs

Same per-video cost model as `docs/04-roadmap.md` (~$0.15-0.25/video in AI
provider calls). Hosting itself is $0/month on this stack as long as it
stays within each provider's free tier (Neon: 0.5GB storage / 100 CU-hours;
Upstash: 256MB / 500k commands; Render: 750 pooled instance-hours across the
three free services; Vercel: generous free tier for a single-user
frontend). The most likely thing to force a paid upgrade is render-worker's
RAM if renders start OOMing -- that's a single $7/mo Render instance-type
bump, not a stack-wide change.
