"""validate_and_clamp() -- the second of the two validation steps in
ADR-0005. Pydantic's own field constraints (schema.py) catch structurally
malformed JSON; this catches a structurally-valid plan that hallucinates
timestamps outside what the actual media supports.

Hard-rejects (raises EditPlanValidationError) only what can't be safely
repaired: an unknown source_video_id, or a clip whose source_start/end is
inverted even after clamping. Everything else -- out-of-range timestamps,
overlong overlays, degenerate zero-length ranges -- gets clamped or dropped,
with each adjustment logged so silent corruption doesn't happen quietly.
"""

import logging
import uuid

from edit_plan_schema.schema import EditPlan

logger = logging.getLogger("edit_plan_schema.validation")


class EditPlanValidationError(ValueError):
    pass


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(value, hi))


def validate_and_clamp(plan: EditPlan, source_durations: dict[uuid.UUID, float]) -> EditPlan:
    """`source_durations` must come from the database (SourceVideo rows),
    never from `plan.source_videos` -- that's Claude-supplied and is exactly
    the kind of value this function exists to not trust."""
    if not plan.timeline:
        raise EditPlanValidationError("timeline is empty -- nothing to render")

    clamped_clips = []
    for clip in plan.timeline:
        duration = source_durations.get(clip.source_video_id)
        if duration is None:
            raise EditPlanValidationError(
                f"timeline clip {clip.id!r} references unknown source_video_id "
                f"{clip.source_video_id} -- not in the real source video set"
            )

        source_start = _clamp(clip.source_start, 0.0, duration)
        source_end = _clamp(clip.source_end, 0.0, duration)
        if source_start >= source_end:
            raise EditPlanValidationError(
                f"timeline clip {clip.id!r} has an inverted/zero-length source range "
                f"after clamping to [0, {duration}]: start={source_start}, end={source_end} "
                f"(raw: start={clip.source_start}, end={clip.source_end})"
            )
        if (source_start, source_end) != (clip.source_start, clip.source_end):
            logger.warning(
                "clamped clip %r source range from [%s, %s] to [%s, %s] (source duration %s)",
                clip.id, clip.source_start, clip.source_end, source_start, source_end, duration,
            )
        clamped_clips.append(
            clip.model_copy(update={"source_start": source_start, "source_end": source_end})
        )

    # Re-derive output_start/output_end from clip order + clamped source
    # durations rather than trusting Claude's arithmetic (ADR-0005).
    rebuilt_clips = []
    cursor = 0.0
    for clip in clamped_clips:
        clip_duration = clip.source_end - clip.source_start
        output_start = cursor
        output_end = cursor + clip_duration
        cursor = output_end
        rebuilt_clips.append(
            clip.model_copy(update={"output_start": output_start, "output_end": output_end})
        )
    total_output_duration = cursor

    clamped_cuts = []
    for cut in plan.cuts:
        duration = source_durations.get(cut.source_video_id)
        if duration is None:
            logger.warning(
                "dropping cuts entry referencing unknown source_video_id %s", cut.source_video_id
            )
            continue
        source_start = _clamp(cut.source_start, 0.0, duration)
        source_end = _clamp(cut.source_end, 0.0, duration)
        if source_start >= source_end:
            continue
        clamped_cuts.append(
            cut.model_copy(update={"source_start": source_start, "source_end": source_end})
        )

    def _clamp_ranged(items: list, label: str) -> list:
        result = []
        for item in items:
            start = _clamp(item.start, 0.0, total_output_duration)
            end = _clamp(item.end, 0.0, total_output_duration)
            if start >= end:
                logger.warning(
                    "dropping degenerate %s entry after clamping: raw start=%s end=%s "
                    "(output duration %s)", label, item.start, item.end, total_output_duration,
                )
                continue
            if (start, end) != (item.start, item.end):
                logger.warning(
                    "clamped %s entry from [%s, %s] to [%s, %s]",
                    label, item.start, item.end, start, end,
                )
            result.append(item.model_copy(update={"start": start, "end": end}))
        return result

    def _clamp_pointed(items: list, label: str) -> list:
        result = []
        for item in items:
            at = _clamp(item.at, 0.0, total_output_duration)
            if at != item.at:
                logger.warning("clamped %s.at from %s to %s", label, item.at, at)
            result.append(item.model_copy(update={"at": at}))
        return result

    return plan.model_copy(
        update={
            "timeline": rebuilt_clips,
            "cuts": clamped_cuts,
            "subtitles": _clamp_ranged(plan.subtitles, "subtitles"),
            "zooms": _clamp_ranged(plan.zooms, "zooms"),
            "transitions": _clamp_pointed(plan.transitions, "transitions"),
            "sound_effects": _clamp_pointed(plan.sound_effects, "sound_effects"),
            "motion_graphics": _clamp_ranged(plan.motion_graphics, "motion_graphics"),
            "broll": _clamp_ranged(plan.broll, "broll"),
            "music": _clamp_ranged(plan.music, "music"),
        }
    )
