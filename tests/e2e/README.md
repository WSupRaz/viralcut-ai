# ViralCut AI — E2E tests

Three layers of end-to-end tests, all exercised in CI (`.github/workflows/e2e.yml`)
and runnable locally against the compose stack.

| Suite | What it proves | Command |
|---|---|---|
| `api/e2e_validation.py` | Server-side validation: type/oversize rejection, path-traversal sanitization, non-video + size-mismatch rejection at complete, cancel/abort cleanup | `python tests/e2e/api/e2e_validation.py` |
| `api/e2e_upload.py` | Full API upload flow (start → part PUTs → complete → job) plus resume-after-interruption | `python tests/e2e/api/e2e_upload.py <video> --api http://localhost:8000` |
| `client/upload-client.e2e.mts` | The real browser upload client (chunking, retry/backoff, progress, resume, cancel) against the live stack | `cd apps/web && npx tsx ../../tests/e2e/client/upload-client.e2e.mts` |
| `browser/upload-resume.mjs` | The real UI: upload → refresh mid-upload → resume card → re-select → complete | see below |

## Prerequisites (local)

1. `cp .env.example .env`
2. `docker compose -f infra/docker-compose.dev.yml up -d` (full stack incl. web)
3. `tests/e2e/scripts/make-test-video.sh` (generates videos via the worker's ffmpeg)
4. `pip install httpx`

## Browser suite

```bash
cd tests/e2e/browser && npm ci
node upload-resume.mjs ../artifacts/ci-upload-100mb.mp4   # local: uses installed Edge
```

Env knobs:

- `E2E_BASE_URL` — app URL (default `http://localhost:3000`)
- `PW_CHANNEL` — browser channel; `msedge` locally, **unset** in CI (bundled chromium)
- `E2E_UPLOAD_MBPS` — throttled upload bandwidth (default 30)

In CI the web app is built and served with `next start`, so the suite runs
against production-like code.

## CI

`.github/workflows/e2e.yml` runs all four suites on every push/PR:

1. boots postgres, redis, MinIO, API (auto-migrates on boot), worker, render-worker
2. waits for API health, generates test videos
3. validation + API upload suites
4. `next build` + `next start`, then the client and browser suites

Optional: set `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` in GitHub repo secrets to
also exercise the metadata/edit-plan pipeline in CI; without them the proxy
stage (the scope of these suites) still passes.
