# ViralCut AI — Docs Index

Read in this order:

1. [01-architecture.md](01-architecture.md) — system diagram, pipeline, cost defaults
2. [02-folder-structure.md](02-folder-structure.md) — monorepo layout
3. [03-database-schema.md](03-database-schema.md) — Postgres schema
4. [04-roadmap.md](04-roadmap.md) — phases, sequential task list, costs, risks
5. [05-deployment.md](05-deployment.md) — Railway + Vercel + Cloudflare R2 deployment runbook
6. [adr/](adr/) — decisions that deviate from the original spec, with reasoning

## Deviations from the original spec (see ADRs for full reasoning)

- Prisma → SQLAlchemy 2.0 + Alembic ([ADR 0002](adr/0002-orm-choice.md))
- Self-hosted Whisper Large V3 → hosted ASR, OpenAI primary / Groq fallback ([ADR 0001](adr/0001-asr-provider.md))
- Dropped MoviePy and OpenCV from MVP video stack ([ADR 0003](adr/0003-video-stack-scope.md))
- Dropped face/emotion/object detection from MVP metadata; no speaker diarization in Phase 1 ([ADR 0004](adr/0004-metadata-extraction-scope.md))
- Resolved `timeline` vs `cuts` ambiguity in the edit-plan contract; `timeline` is the sole rendering authority ([ADR 0005](adr/0005-edit-plan-schema.md))
- Claude primary / OpenRouter fallback for edit-plan generation, also covering the spec's "Gemini fallback" need ([ADR 0006](adr/0006-edit-plan-llm-fallback.md))
