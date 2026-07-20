# ADR 0005: Edit-plan JSON contract — timeline/cuts semantics and validation

## Status
Accepted

## Context
The original spec requires Claude to output a JSON object with, among other
fields, both `"timeline": []` and `"cuts": []` as separate top-level arrays,
without defining how they differ. Left as-is, that's two arrays that could
independently claim to be the authoritative "what to keep" answer — if they
ever disagree, the renderer has no principled way to pick a winner, and a
disagreement would only surface as a rendering bug, not a validation error.

Separately, `docs/01-architecture.md` already commits to a specific defense
against a real risk: "Claude will occasionally hallucinate an out-of-range
timestamp — validate, don't assume." Task 8 is where that promise has to
become actual code, not just a line in an architecture doc.

## Decision

### `timeline` is the sole rendering authority
`timeline` is an ordered array of `Clip` objects. Each clip names a
`source_video_id`, an in/out range in that source's own coordinates
(`source_start`/`source_end`), and where it lands in the final output
(`output_start`/`output_end`). This alone is sufficient to drive the ffmpeg
cut/concat step — nothing else needs to be consulted to know what to keep.

`cuts` is **informational, not authoritative**: an array of the ranges that
were *removed* from each source video, tagged with why (`silence`,
`filler_word`, `dead_moment`, `repeated_section`, `other`). It exists so the
product can show "removed 45s of silence, 12 filler words" in the UI and so
removal reasoning is auditable — it is never read by the renderer. If
`timeline` and `cuts` ever disagree, `timeline` wins, full stop, because it's
the only one anything downstream actually consumes.

### All non-timeline timestamps are output-timeline coordinates
`subtitles`, `zooms`, `transitions`, `sound_effects`, `motion_graphics`,
`broll`, and `music` all use `start`/`end` (or `at`, for point events) in the
**final rendered output's** timeline, not the source video's. This is the
only choice that doesn't require every consumer of the plan to re-derive
"where does source-video time T end up after cuts" for itself. `output_start`/
`output_end` on `timeline` clips is exactly the mapping that makes this work.

### Full contract now, partial implementation is fine
The schema defines every field the original spec asked for (`transitions`,
`sound_effects`, `motion_graphics`, `broll`, `music`, `retention_prediction`)
even though Phase 1's renderer (tasks 10-11) only consumes `timeline`,
`subtitles`, `zooms`, and `viral_score` — the rest (B-roll, music,
transitions/motion-graphics beyond captions/zooms) are Phase 2 per
`docs/04-roadmap.md`. Defining the stable contract once and growing the
implementation into it beats redesigning the JSON shape every phase.

### Validation is two separate steps, not one
1. **Structural validation** (Pydantic field types/constraints, Zod on the
   Node side): rejects malformed JSON outright — wrong types, missing
   required fields, scores outside 0-100, etc. A failure here means the
   edit-plan worker should retry the Claude call, not proceed.
2. **`validate_and_clamp()`**: takes a structurally-valid plan plus the real
   `{source_video_id: duration_seconds}` map and:
   - Hard-rejects (raises) anything a clamp can't safely paper over: a
     `source_video_id` that doesn't exist, a clip with `source_start >=
     source_end`.
   - Clamps `source_start`/`source_end` into `[0, duration]` for hallucinated
     out-of-range values.
   - **Re-derives `output_start`/`output_end` from scratch** based on clip
     order and clamped source durations, rather than trusting whatever
     Claude put there — this eliminates an entire class of arithmetic
     mistakes (gaps, overlaps, drift) instead of trying to detect and repair
     them after the fact.
   - Clamps every other array's `start`/`end`/`at` into
     `[0, total_output_duration]` (computed *after* the timeline clamp
     above), and drops any entry that's zero-length or inverted post-clamp.

The Python implementation is authoritative (edit-plan generation runs in the
Python/Celery worker). The Zod schema on the Node/Remotion side is a
structural-validation guard only — it does not reimplement clamping. Node
never receives a plan that hasn't already been through
`validate_and_clamp()`.

## Consequences
- One rendering source of truth (`timeline`); `cuts` can never cause a
  silent contradiction because nothing downstream reads it for cut
  decisions.
- `output_start`/`output_end` being *recomputed* rather than merely
  *checked* means Claude doesn't need to get timeline arithmetic right for
  the render to be correct — it only needs to get clip order and in/out
  points approximately right, which is a much easier bar.
- Two schema implementations (Pydantic, Zod) that must be kept in sync by
  hand — no cross-language schema generation tool was introduced for this,
  since the field set is small and stable enough that the maintenance cost
  of a codegen pipeline isn't worth it yet. Revisit if the schema grows
  significantly or drifts in practice.
