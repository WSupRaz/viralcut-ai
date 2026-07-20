# ViralCut AI

AI-powered automatic video editing SaaS. Users upload raw footage, pick a
style preset (or describe one), and get back an edited, captioned, viral-
ready short — no manual editing.

Claude is the planning brain only; it never touches video frames. Actual
editing is done by FFmpeg, PySceneDetect, and Remotion. See
[docs/01-architecture.md](docs/01-architecture.md) for the full pipeline.

## Start here

- [docs/README.md](docs/README.md) — architecture, schema, roadmap, ADRs
- [docs/04-roadmap.md](docs/04-roadmap.md) — current phase and task list

## Local development

```bash
cp .env.example .env   # fill in API keys
docker compose -f infra/docker-compose.dev.yml up
```

- API: http://localhost:8000
- Web: http://localhost:3000
- Postgres: localhost:5432
- Redis: localhost:6379

## Repo layout

See [docs/02-folder-structure.md](docs/02-folder-structure.md) for the full
breakdown. Short version: `apps/` (Next.js frontend, Remotion render worker),
`services/api` (FastAPI), `workers/` (Celery pipeline tasks), `packages/`
(shared schemas/types), `infra/` (Docker, compose).
