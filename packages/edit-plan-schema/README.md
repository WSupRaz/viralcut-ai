# edit-plan-schema

The JSON contract for the edit plan: Claude's output, the render worker's
input, and the frontend timeline all derive from this shape. See
[docs/adr/0005-edit-plan-schema.md](../../docs/adr/0005-edit-plan-schema.md)
for the design decisions (`timeline` vs `cuts`, output-timeline coordinates,
why validation is two separate steps).

## Two implementations, kept in sync by hand

- **`python/edit_plan_schema/`** — Pydantic models (`schema.py`) plus
  `validate_and_clamp()` (`validation.py`), the authoritative implementation.
  Used by the edit-plan worker (Claude call) and the render worker's ffmpeg
  cut stage.
- **`node/`** — Zod schema mirroring the Pydantic models field for field.
  Structural validation only on this side; a plan reaching Node has already
  been through Python's `validate_and_clamp()`.

There's no cross-language codegen here (see ADR-0005's consequences) — if you
change one side, change the other, and re-run both verification suites.

## Import paths

- Python: `import edit_plan_schema` — the package is copied onto
  `PYTHONPATH=/app/packages` in both `infra/docker/api.Dockerfile` and
  `infra/docker/worker.Dockerfile`, same pattern as `db_models`.
- Node: `@viralcut/edit-plan-schema`, consumed via a local path dependency
  from `apps/render-worker` (added when that app is built).
