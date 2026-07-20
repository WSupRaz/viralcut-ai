# Roadmap

## Phase 1 — MVP

Goal: a user can upload raw footage, pick a style preset, add an instruction,
and get back an exported vertical video with captions, silence removal, and
zooms — with no human editing step. This is the smallest thing that proves
"looks like a human editor did it," not the smallest thing that technically
runs the pipeline.

### Build order (why this order)

1. **Foundation**: auth, project CRUD, presigned R2 upload, Postgres schema
   (docs/03-database-schema.md), job table + Celery skeleton with a no-op task
   to prove the queue works end to end. Nothing here is interesting, but
   everything else depends on it, and it's where integration bugs
   (CORS, presigned URL expiry, worker can't reach Postgres) are cheapest to
   find.
2. **Metadata pipeline**: proxy generation, ASR (Deepgram), PySceneDetect,
   silencedetect, assembled into the `metadata` row. This is testable in
   isolation with no Claude/render involvement — validate quality here first,
   because a bad transcript poisons everything downstream.
3. **Edit-plan generation**: Claude call against `packages/edit-plan-schema`,
   with the **Alex Hormozi preset only** (simplest rule set — fixed pacing,
   no cinematic judgment calls) to prove the metadata-in/plan-out contract
   before building the other three presets.
4. **Render pipeline**: ffmpeg cuts/silence-removal, then Remotion captions +
   zooms. Ship end-to-end for Hormozi preset before adding Documentary/
   MrBeast/Ali Abdaal — a working renderer for one preset de-risks the
   pipeline far more than four half-working presets.
5. **Remaining presets** (Documentary, MrBeast, Ali Abdaal) — now that the
   plan→render contract is proven, these are mostly `rules_json` + a handful
   of new Remotion compositions (dark overlay, meme graphics, minimal
   captions), not new architecture.
6. **Export + delivery**: aspect ratio / quality selection, final R2 delivery,
   signed download URL.

### Explicit MVP feature list (per your spec, unchanged)
- Upload videos (mp4, mov, m4v)
- Prompt input (free text + style preset selection)
- Auto captions (Remotion)
- Silence removal (ffmpeg)
- Zooms (Remotion, timed off transcript emphasis + scene cuts, not face
  tracking — see ADR-0003)
- Viral presets: Hormozi first, then the other three
- Export (9:16 only for MVP — 16:9/1:1 in Phase 2, see below)

### Explicitly NOT in Phase 1 (cut for scope, not forgotten)
- Face/emotion/object detection (ADR-0004)
- B-roll auto-insertion (Pexels/Pixabay) — Phase 2
- Music library auto-selection — Phase 2
- Timeline drag-and-drop re-editing UI — Phase 2 (Phase 1 timeline is
  view-only, showing what Claude produced)
- 16:9 and 1:1 export, 4K quality — Phase 2
- Billing/credits enforcement — build the schema now, wire up Stripe in
  Phase 2 (MVP can run on a manual/free allowlist while you validate output
  quality with real users)

## Phase 2 — Paid Product

- Stripe billing + credit ledger enforcement (schema already exists from
  Phase 1)
- B-roll engine (Pexels/Pixabay, keyword selection + insertion via Claude)
- Music + sound-effect library with auto-selection
- Full export matrix (9:16, 16:9, 1:1 × 720p/1080p/4k)
- Timeline editor becomes editable (drag clips, adjust captions/zooms
  manually) — this is also where you start collecting the human-correction
  signal that's valuable for prompt/preset tuning later
- OpenCV face-tracked auto-reframe (closes the ADR-0003 gap)
- Retry/failure UX in the job system (user-facing, not just backend logic)

## Phase 3 — Scale

- Self-hosted ASR evaluation if volume justifies it (ADR-0001 breakeven)
- Face/emotion/object detection, gated behind specific features that need
  them (ADR-0004) — e.g., emotion-timed B-roll, subject-aware punch zooms
- Multi-region render workers if latency/geo becomes a complaint
- Custom user-defined style presets (currently system-only per schema)
- Terraform/IaC for infra (fine to hand-manage in Phase 1/2)

---

## Task list — Phase 1 (sequential; confirm before I move to the next one)

Per your instruction, I'll implement these one at a time and stop for your
review after each rather than batching the whole phase:

1. Monorepo scaffold (`infra/docker-compose.dev.yml`, base Dockerfiles, repo
   README, `.gitignore`, `.env.example`)
2. Postgres schema — SQLAlchemy models + Alembic initial migration
3. FastAPI service skeleton — auth, project CRUD, presigned R2 upload
4. Celery skeleton — Redis broker config, no-op task proving queue works
5. Proxy worker (ffmpeg transcode task)
6. Metadata worker — ASR integration (Deepgram client + fallback)
7. Metadata worker — PySceneDetect + silencedetect integration
8. `packages/edit-plan-schema` — the JSON contract (pydantic + zod)
9. Edit-plan worker — Claude client, Hormozi-only prompt, schema validation +
   duration clamping
10. Render worker — ffmpeg cuts/silence-removal stage
11. Render worker — Remotion captions composition
12. Render worker — Remotion punch-zoom composition
13. Export flow — R2 delivery, signed URL, job status wiring end-to-end
14. Frontend — upload flow + project dashboard
15. Frontend — style/instruction input + job progress UI
16. Frontend — read-only timeline/result viewer + export download
17. Remaining three presets (Documentary, MrBeast, Ali Abdaal) — rules +
    compositions
18. End-to-end smoke test with real footage, cost/latency measurement against
    the $0.30/video target

---

## Cost estimate per video (Phase 1, ~10-minute source → one 60s vertical short)

| Item | Cost | Notes |
|---|---|---|
| ASR (Deepgram, 10 min) | ~$0.05 | ADR-0001 |
| Claude edit-plan call | ~$0.03–0.06 | metadata JSON in, structured JSON out; prompt caching on style-rules block |
| Proxy transcode (CPU) | ~$0.01 | small CPU instance, seconds of compute |
| Render (ffmpeg + Remotion, CPU) | ~$0.05–0.12 | biggest variable cost; Remotion render time scales with output duration and composition complexity |
| R2 storage + egress | ~$0.005 | R2 has no egress fee, storage is cheap; proxies/renders should have a lifecycle policy (see risk below) |
| **Total** | **~$0.15–0.25** | inside the $0.30 target, with headroom |

At 5 shorts generated from one long source (your "turn this podcast into 5
viral shorts" example), metadata extraction cost is paid once and amortized
across all 5 — only the render step repeats 5x, so the marginal cost per
additional short is closer to $0.05–0.12, not the full $0.15–0.25.

## Biggest technical risks

1. **Claude hallucinating timestamps/references outside actual media
   bounds.** Mitigation: hard validation + clamping layer between Claude
   output and the renderer (ADR referenced in architecture.md step 5) — never
   trust the JSON blindly, ever, even though the schema is "guaranteed."
2. **Render cost/time variance.** Remotion server-side rendering is CPU-heavy
   and scales with composition complexity, not just duration. Needs real
   benchmarking in task 18 before you price plans — don't set subscription
   tiers off the estimate table above, set them off measured numbers.
3. **ASR/diarization quality on noisy or multi-speaker podcast audio** — the
   whole pipeline's captions and cut timing are downstream of transcript
   accuracy. Budget time for a fallback/re-try path (Groq Whisper) when
   Deepgram confidence is low, not just when it errors.
4. **Auto-reframe quality without face tracking in MVP** (ADR-0003) — center-
   crop will look wrong whenever a speaker isn't centered in frame. This is
   the single most likely "doesn't look like a human editor did it" complaint
   from early users. Flagged now so it's a known trade-off, not a surprise at
   launch.
5. **B-roll/music licensing for a commercial SaaS output.** Pexels/Pixabay's
   free tiers have usage terms that need checking against "user pays you,
   video ends up on their monetized social account" — verify licensing before
   Phase 2 ships B-roll, not after.
6. **Storage cost creep.** Proxies + intermediate renders + final exports all
   accumulate in R2 per project. Needs a lifecycle/cleanup policy (e.g., purge
   proxies and intermediate renders N days after a project is finalized) —
   not urgent for Phase 1 but put it in the schema/design now so it's not a
   Phase 3 migration.
7. **Celery at-least-once delivery** can double-run a render task on worker
   crash/restart. Render tasks must be idempotent (safe to re-run, keyed by
   job id, overwrite not append) — build this in from task 10, not retrofit
   later.
