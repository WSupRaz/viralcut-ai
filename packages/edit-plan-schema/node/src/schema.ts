/**
 * The edit-plan JSON contract (ADR-0005). Mirrors
 * packages/edit-plan-schema/python/edit_plan_schema/schema.py field for
 * field -- keep both in sync by hand when either changes.
 *
 * `timeline` is the sole rendering authority. Every other timed array uses
 * output-timeline coordinates (post-cut), not source-video coordinates.
 *
 * This is a structural-validation guard only. Clamping (out-of-range
 * timestamps, re-deriving output_start/output_end) happens on the Python
 * side before a plan ever reaches this schema -- see
 * docs/adr/0005-edit-plan-schema.md.
 */

import { z } from "zod";

const nonNegative = z.number().min(0);

export const CutReasonSchema = z.enum([
  "silence",
  "filler_word",
  "dead_moment",
  "repeated_section",
  "other",
]);

export const TransitionTypeSchema = z.enum([
  "hard_cut",
  "crossfade",
  "whip_pan",
  "zoom_punch",
]);

export const ZoomFocusSchema = z.enum(["center", "left", "right", "top", "bottom"]);

export const MotionGraphicTemplateSchema = z.enum([
  "lower_third",
  "callout",
  "counter",
  "cta_screen",
  "highlight_box",
  "arrow",
  "progress_bar",
]);

export const BrollSourceSchema = z.enum(["pexels", "pixabay"]);

export const SourceVideoRefSchema = z.object({
  source_video_id: z.string().uuid(),
  duration_seconds: nonNegative,
});

export const ClipSchema = z.object({
  id: z.string(),
  source_video_id: z.string().uuid(),
  source_start: nonNegative,
  source_end: nonNegative,
  output_start: nonNegative,
  output_end: nonNegative,
});

export const CutRangeSchema = z.object({
  source_video_id: z.string().uuid(),
  source_start: nonNegative,
  source_end: nonNegative,
  reason: CutReasonSchema.default("other"),
});

export const SubtitleSchema = z.object({
  start: nonNegative,
  end: nonNegative,
  text: z.string(),
  emphasis_words: z.array(z.string()).default([]),
});

export const ZoomSchema = z.object({
  start: nonNegative,
  end: nonNegative,
  scale: z.number().gt(0).lte(3.0),
  focus: ZoomFocusSchema.default("center"),
});

export const TransitionSchema = z.object({
  at: nonNegative,
  type: TransitionTypeSchema,
  duration_seconds: nonNegative.default(0),
});

export const SoundEffectSchema = z.object({
  at: nonNegative,
  asset_tag: z.string(),
  volume_db: z.number().default(0),
});

export const MotionGraphicSchema = z.object({
  start: nonNegative,
  end: nonNegative,
  template: MotionGraphicTemplateSchema,
  props: z.record(z.string(), z.unknown()).default({}),
});

export const BrollClipSchema = z.object({
  start: nonNegative,
  end: nonNegative,
  keyword: z.string(),
  source: BrollSourceSchema.default("pexels"),
});

export const MusicCueSchema = z.object({
  start: nonNegative,
  end: nonNegative,
  asset_tag: z.string(),
  volume_db: z.number().default(-18.0),
});

export const ViralScoreSchema = z.object({
  hook_score: z.number().int().min(0).max(100),
  retention_score: z.number().int().min(0).max(100),
  engagement_score: z.number().int().min(0).max(100),
  reasoning: z.string().default(""),
});

export const RetentionPredictionSchema = z.object({
  predicted_drop_off_points: z.array(z.number()).default([]),
  notes: z.string().default(""),
});

export const EditPlanSchema = z.object({
  version: z.literal("1.0").default("1.0"),
  style_slug: z.string(),
  source_videos: z.array(SourceVideoRefSchema),

  timeline: z.array(ClipSchema).min(1),
  cuts: z.array(CutRangeSchema).default([]),
  subtitles: z.array(SubtitleSchema).default([]),
  zooms: z.array(ZoomSchema).default([]),
  transitions: z.array(TransitionSchema).default([]),
  sound_effects: z.array(SoundEffectSchema).default([]),
  motion_graphics: z.array(MotionGraphicSchema).default([]),
  broll: z.array(BrollClipSchema).default([]),
  music: z.array(MusicCueSchema).default([]),

  viral_score: ViralScoreSchema,
  retention_prediction: RetentionPredictionSchema.default({
    predicted_drop_off_points: [],
    notes: "",
  }),
});

export type EditPlan = z.infer<typeof EditPlanSchema>;
export type Clip = z.infer<typeof ClipSchema>;
export type Subtitle = z.infer<typeof SubtitleSchema>;
export type Zoom = z.infer<typeof ZoomSchema>;
export type Transition = z.infer<typeof TransitionSchema>;
export type SoundEffect = z.infer<typeof SoundEffectSchema>;
export type MotionGraphic = z.infer<typeof MotionGraphicSchema>;
export type BrollClip = z.infer<typeof BrollClipSchema>;
export type MusicCue = z.infer<typeof MusicCueSchema>;
export type ViralScore = z.infer<typeof ViralScoreSchema>;
export type RetentionPrediction = z.infer<typeof RetentionPredictionSchema>;
