"""The edit-plan JSON contract (ADR-0005). Claude's output, the render
worker's input, and the frontend timeline all derive from this shape.

`timeline` is the sole rendering authority. Every other timed array uses
output-timeline coordinates (post-cut), not source-video coordinates. See
docs/adr/0005-edit-plan-schema.md for the full reasoning.

This model validates *raw* Claude output, before validate_and_clamp() has
run. Timestamp fields (source_start, output_end, start, end, at, ...)
deliberately carry no ge=0/duration bound here -- that range depends on the
actual source video's duration, which this layer doesn't know, and
hallucinated out-of-range timestamps are exactly what validate_and_clamp()
exists to repair rather than reject. Only clamp-proof invariants (types,
scores, enums, zoom scale) are enforced at this layer.
"""

import uuid
from typing import Literal

from pydantic import BaseModel, Field

CutReason = Literal["silence", "filler_word", "dead_moment", "repeated_section", "other"]
TransitionType = Literal["hard_cut", "crossfade", "whip_pan", "zoom_punch"]
ZoomFocus = Literal["center", "left", "right", "top", "bottom"]
MotionGraphicTemplate = Literal[
    "lower_third", "callout", "counter", "cta_screen", "highlight_box", "arrow", "progress_bar"
]
BrollSource = Literal["pexels", "pixabay"]


class SourceVideoRef(BaseModel):
    source_video_id: uuid.UUID
    duration_seconds: float = Field(ge=0)


class Clip(BaseModel):
    """One entry in `timeline`. Rendering authority (ADR-0005) -- ffmpeg's
    cut/concat step is driven entirely by this array, in order."""

    id: str
    source_video_id: uuid.UUID
    source_start: float
    source_end: float
    output_start: float
    output_end: float


class CutRange(BaseModel):
    """Informational only (ADR-0005) -- a range removed from a source video,
    for UI display ("removed 45s of silence") and audit, never read by the
    renderer."""

    source_video_id: uuid.UUID
    source_start: float
    source_end: float
    reason: CutReason = "other"


class Subtitle(BaseModel):
    start: float
    end: float
    text: str
    emphasis_words: list[str] = Field(default_factory=list)


class Zoom(BaseModel):
    start: float
    end: float
    scale: float = Field(gt=0, le=3.0)
    focus: ZoomFocus = "center"


class Transition(BaseModel):
    at: float
    type: TransitionType
    duration_seconds: float = Field(default=0.0, ge=0)


class SoundEffect(BaseModel):
    at: float
    asset_tag: str
    volume_db: float = 0.0


class MotionGraphic(BaseModel):
    start: float
    end: float
    template: MotionGraphicTemplate
    props: dict = Field(default_factory=dict)


class BrollClip(BaseModel):
    start: float
    end: float
    keyword: str
    source: BrollSource = "pexels"


class MusicCue(BaseModel):
    start: float
    end: float
    asset_tag: str
    volume_db: float = -18.0


class ViralScore(BaseModel):
    hook_score: int = Field(ge=0, le=100)
    retention_score: int = Field(ge=0, le=100)
    engagement_score: int = Field(ge=0, le=100)
    reasoning: str = ""


class RetentionPrediction(BaseModel):
    predicted_drop_off_points: list[float] = Field(default_factory=list)
    notes: str = ""


class EditPlan(BaseModel):
    version: Literal["1.0"] = "1.0"
    style_slug: str
    source_videos: list[SourceVideoRef]

    timeline: list[Clip]
    cuts: list[CutRange] = Field(default_factory=list)
    subtitles: list[Subtitle] = Field(default_factory=list)
    zooms: list[Zoom] = Field(default_factory=list)
    transitions: list[Transition] = Field(default_factory=list)
    sound_effects: list[SoundEffect] = Field(default_factory=list)
    motion_graphics: list[MotionGraphic] = Field(default_factory=list)
    broll: list[BrollClip] = Field(default_factory=list)
    music: list[MusicCue] = Field(default_factory=list)

    viral_score: ViralScore
    retention_prediction: RetentionPrediction = Field(default_factory=RetentionPrediction)
