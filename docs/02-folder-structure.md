# Folder Structure

Monorepo, split by deployable unit. Rationale: frontend (Next.js), API
(FastAPI), and workers (Python + Node for Remotion) deploy and scale
independently — separate directories keep that boundary honest instead of a
single `src/` where it's unclear what ships where.

```
viralcut-ai/
├── apps/
│   ├── web/                        # Next.js App Router frontend
│   │   ├── app/
│   │   │   ├── (marketing)/        # public landing pages
│   │   │   ├── (auth)/             # sign in / sign up
│   │   │   ├── dashboard/
│   │   │   │   ├── projects/
│   │   │   │   ├── projects/[id]/  # timeline editor
│   │   │   │   └── billing/
│   │   │   └── api/                # Next.js route handlers (webhooks only —
│   │   │                           # real API is FastAPI, not this)
│   │   ├── components/
│   │   │   ├── ui/                 # shadcn primitives
│   │   │   ├── timeline/           # Clip/Track/Transition/Caption editor
│   │   │   └── upload/
│   │   ├── stores/                 # zustand stores
│   │   ├── lib/
│   │   │   ├── api-client.ts       # typed fetch wrapper for FastAPI
│   │   │   └── query/              # react-query hooks
│   │   └── types/                  # shared TS types (mirrors backend schemas)
│   │
│   └── render-worker/              # Remotion render service (Node)
│       ├── src/
│       │   ├── compositions/       # Remotion <Composition> per template
│       │   │   ├── captions/
│       │   │   ├── zooms/
│       │   │   ├── motion-graphics/
│       │   │   │   ├── lower-third/
│       │   │   │   ├── callout/
│       │   │   │   ├── counter/
│       │   │   │   └── cta-screen/
│       │   │   └── transitions/
│       │   ├── render.ts           # entrypoint invoked by Celery task
│       │   └── schema/             # zod schemas for edit-plan JSON (Node side)
│       └── package.json
│
├── services/
│   └── api/                        # FastAPI service
│       ├── app/
│       │   ├── main.py
│       │   ├── api/
│       │   │   ├── v1/
│       │   │   │   ├── auth.py
│       │   │   │   ├── projects.py
│       │   │   │   ├── uploads.py
│       │   │   │   ├── jobs.py
│       │   │   │   ├── styles.py
│       │   │   │   ├── billing.py
│       │   │   │   └── exports.py
│       │   ├── models/             # SQLAlchemy models (ADR-0002)
│       │   ├── schemas/            # Pydantic request/response models
│       │   ├── services/           # business logic, no framework imports
│       │   ├── core/                # config, security, deps
│       │   └── db/
│       │       ├── session.py
│       │       └── migrations/     # Alembic
│       └── tests/
│
├── workers/                        # Celery workers (Python)
│   ├── celery_app.py
│   ├── tasks/
│   │   ├── proxy.py                # step 2
│   │   ├── metadata_extraction.py  # step 3-4 (asr, scenes, silence)
│   │   ├── edit_plan.py            # step 5 (Claude call + validation)
│   │   └── render_dispatch.py      # step 6 (ffmpeg cuts, then calls render-worker)
│   └── providers/
│       ├── asr/                    # Deepgram / Groq (ADR-0001)
│       ├── scene_detect/
│       ├── broll/                  # Pexels / Pixabay clients
│       └── llm/                    # Claude client + Gemini fallback
│
├── packages/
│   ├── edit-plan-schema/           # single source of truth for the edit-plan
│   │                               # JSON schema, published for both Python
│   │                               # (pydantic) and Node (zod) to consume
│   ├── style-presets/              # Hormozi / Documentary / MrBeast / Ali
│   │                               # Abdaal rule definitions, data not code
│   └── shared-types/
│
├── infra/
│   ├── docker/
│   │   ├── api.Dockerfile
│   │   ├── worker.Dockerfile
│   │   └── render-worker.Dockerfile
│   ├── docker-compose.dev.yml
│   └── terraform/                  # Phase 2+, not MVP
│
├── docs/
│   ├── adr/
│   ├── 01-architecture.md
│   ├── 02-folder-structure.md
│   ├── 03-database-schema.md
│   └── 04-roadmap.md
│
└── README.md
```

## Notes

- `packages/edit-plan-schema` is the load-bearing contract in this whole
  system: Claude's output, the render worker's input, and the frontend
  timeline's data model all derive from it. Define it once, generate/validate
  from it everywhere, never hand-duplicate the shape in three languages.
- `services/api` never touches ffmpeg/Remotion directly — it only enqueues
  jobs and reads status/results from Postgres. Keeps the request/response
  cycle fast and keeps rendering fully async, per your own requirement that
  "rendering must never block requests."
