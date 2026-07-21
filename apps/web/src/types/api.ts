// Mirrors services/api/app/schemas/*.py. Keep both in sync by hand -- see
// packages/edit-plan-schema/README.md for the reasoning on why this repo
// doesn't use cross-language schema codegen.

export type PlanTier = "free" | "creator" | "pro" | "business";

export interface User {
  id: string;
  email: string;
  name: string;
  avatar_url: string | null;
  plan: PlanTier;
  created_at: string;
}

export interface Style {
  id: string;
  name: string;
  slug: string;
  is_system: boolean;
}

export type ProjectStatus = "draft" | "processing" | "ready" | "failed" | "archived";
export type AspectRatio = "9:16" | "16:9" | "1:1";

export interface Project {
  id: string;
  user_id: string;
  title: string;
  status: ProjectStatus;
  target_aspect_ratio: AspectRatio;
  style_id: string | null;
  instructions: string | null;
  created_at: string;
  updated_at: string;
}

export type SourceVideoStatus = "uploaded" | "proxy_ready" | "metadata_ready" | "failed";

export interface SourceVideo {
  id: string;
  project_id: string;
  order_index: number;
  status: SourceVideoStatus;
  duration_seconds: string | null;
  created_at: string;
}

export interface SourceVideoPresignResponse {
  source_video_id: string;
  upload_url: string;
  r2_key: string;
}

export type JobType = "proxy" | "metadata_extraction" | "edit_plan" | "render";
export type JobStatus = "queued" | "running" | "succeeded" | "failed" | "retrying";

export interface Job {
  id: string;
  project_id: string;
  type: JobType;
  status: JobStatus;
  progress_pct: number;
  error: string | null;
  retry_count: number;
  created_at: string;
  updated_at: string;
}

export type EditPlanStatus = "generated" | "approved" | "superseded";

export interface ViralScore {
  hook_score: number;
  retention_score: number;
  engagement_score: number;
  reasoning: string;
}

export interface EditPlanClip {
  id: string;
  source_video_id: string;
  source_start: number;
  source_end: number;
  output_start: number;
  output_end: number;
}

export interface Subtitle {
  start: number;
  end: number;
  text: string;
  emphasis_words: string[];
}

export interface EditPlanJson {
  version: string;
  style_slug: string;
  timeline: EditPlanClip[];
  subtitles: Subtitle[];
  [key: string]: unknown;
}

export interface EditPlan {
  id: string;
  project_id: string;
  style_id: string | null;
  plan_json: EditPlanJson;
  viral_score: ViralScore;
  model: string;
  status: EditPlanStatus;
  created_at: string;
}

export type ExportQuality = "720p" | "1080p" | "4k";

export interface Export {
  id: string;
  project_id: string;
  timeline_id: string;
  aspect_ratio: AspectRatio;
  quality: ExportQuality;
  job_id: string;
  job_status: JobStatus;
  r2_key_output: string | null;
  download_url: string | null;
  created_at: string;
}
