"use client";

import { useParams } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { DownloadIcon, RotateCwIcon, SparklesIcon, Trash2Icon } from "lucide-react";
import { api as apiClient } from "@/lib/api-client";
import { useAuthStore } from "@/stores/auth-store";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Separator } from "@/components/ui/separator";
import { ApiError } from "@/lib/api-client";
import {
  clearUploadSession,
  formatBytes,
  formatUploadProgress,
  loadUploadSession,
  PausedUploadError,
  type UploadProgress,
  type UploadSession,
} from "@/lib/upload-client";
import {
  useCreateExport,
  useDeleteSourceVideo,
  useEditPlans,
  useExports,
  useJobs,
  useMyPlan,
  useProject,
  useRetrySourceVideo,
  useSourceVideos,
  useTriggerEditPlan,
  useUploadSourceVideo,
} from "@/lib/query/hooks";
import { ACCEPTED_VIDEO_ACCEPT, isAcceptedVideo } from "@/lib/video-file";
import type { ExportQuality, Job, JobStatus, SourceVideoStatus } from "@/types/api";

const STATUS_VARIANT: Record<SourceVideoStatus, "secondary" | "default" | "destructive" | "outline"> = {
  uploaded: "secondary",
  proxy_ready: "default",
  metadata_ready: "default",
  failed: "destructive",
};

const STATUS_LABEL: Record<SourceVideoStatus, string> = {
  uploaded: "Uploaded -- queued for processing",
  proxy_ready: "Generating proxy...",
  metadata_ready: "Ready",
  failed: "Failed",
};

const JOB_STATUS_VARIANT: Record<JobStatus, "secondary" | "default" | "destructive" | "outline"> = {
  queued: "secondary",
  running: "default",
  retrying: "default",
  succeeded: "default",
  failed: "destructive",
};

const JOB_STATUS_LABEL: Record<JobStatus, string> = {
  queued: "Queued",
  running: "Processing...",
  retrying: "Retrying...",
  succeeded: "Ready",
  failed: "Failed",
};  const JOB_TYPE_LABEL: Record<string, string> = {
    proxy: "Proxy",
    metadata_extraction: "Metadata",
    edit_plan: "Edit plan",
    render: "Render",
  };

  const QUALITY_ITEMS: { value: ExportQuality; label: string }[] = [
    { value: "720p", label: "720p" },
    { value: "1080p", label: "1080p (recommended)" },
    { value: "4k", label: "4K" },
  ];


export default function ProjectDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { data: project } = useProject(id);
  const { data: sourceVideos } = useSourceVideos(id);
  const { data: jobs } = useJobs(id);
  const { data: editPlans } = useEditPlans(id);
  const { data: exports } = useExports(id);
  const { data: myPlan } = useMyPlan();
  const maxUploadBytes = myPlan?.limits.max_upload_bytes ?? 5 * 1024 * 1024 * 1024;
  const maxClips = myPlan?.limits.max_clips_per_project;
  const allowedQualities = myPlan?.limits.export_qualities ?? ["720p", "1080p"];
  const uploadVideo = useUploadSourceVideo(id);
  const deleteVideo = useDeleteSourceVideo(id);
  const retryVideo = useRetrySourceVideo(id);
  const triggerEditPlan = useTriggerEditPlan(id);
  const createExport = useCreateExport(id);

  const fileInputRef = useRef<HTMLInputElement>(null);
  const uploadControllerRef = useRef<AbortController | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [uploadingCount, setUploadingCount] = useState(0);
  const [uploadProgress, setUploadProgress] = useState<UploadProgress | null>(null);
  // A stored-but-not-running upload session (page refreshed mid-upload, or a
  // network failure paused it) -- the user re-selects the same file to resume.
  const [pausedSession, setPausedSession] = useState<UploadSession | null>(null);
  const [pausedPercent, setPausedPercent] = useState(0);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [retryingId, setRetryingId] = useState<string | null>(null);
  const [planError, setPlanError] = useState<string | null>(null);
  const [exportError, setExportError] = useState<string | null>(null);
  const [quality, setQuality] = useState<ExportQuality>("1080p");

  const queryClient = useQueryClient();
  const token = useAuthStore((s) => s.token) ?? "";

  // Restore an interrupted upload session after a refresh: fetch how far the
  // server got, and offer to resume from there instead of starting over.
  useEffect(() => {
    const session = loadUploadSession(id);
    if (!session || !token) return;
    // Intentional: surface a stored upload session exactly once on mount.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setPausedSession(session);
    let cancelled = false;
    apiClient
      .getUploadParts(token, id, session.sourceVideoId)
      .then((parts) => {
        if (cancelled) return;
        const uploaded = parts.reduce((sum, p) => sum + p.size, 0);
        setPausedPercent(
          session.fileSize > 0 ? Math.min(100, (uploaded / session.fileSize) * 100) : 0
        );
      })
      .catch(() => {
        // Server session may have expired -- Discard will clean it up.
        if (!cancelled) setPausedPercent(0);
      });
    return () => {
      cancelled = true;
    };
  }, [id, token]);

  async function onDiscardPaused() {
    const session = pausedSession;
    setPausedSession(null);
    clearUploadSession(id);
    if (!session) return;
    try {
      await apiClient.deleteSourceVideo(token, id, session.sourceVideoId);
    } catch {
      // Best-effort; the abandoned-upload sweep cleans up server-side.
    }
  }

  async function onDelete(sourceVideoId: string) {
    if (!window.confirm("Remove this clip? This can't be undone.")) return;
    setDeletingId(sourceVideoId);
    try {
      await deleteVideo.mutateAsync(sourceVideoId);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not remove clip");
    } finally {
      setDeletingId(null);
    }
  }

  async function onRetry(sourceVideoId: string) {
    setRetryingId(sourceVideoId);
    try {
      await retryVideo.mutateAsync(sourceVideoId);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not restart processing");
    } finally {
      setRetryingId(null);
    }
  }

  async function onGeneratePlan() {
    setPlanError(null);
    try {
      await triggerEditPlan.mutateAsync();
    } catch (err) {
      setPlanError(err instanceof ApiError ? err.message : "Could not start edit-plan generation");
    }
  }

  async function onCreateExport() {
    if (!latestPlan) return;
    setExportError(null);
    try {
      await createExport.mutateAsync({ edit_plan_id: latestPlan.id, aspect_ratio: "9:16", quality });
    } catch (err) {
      setExportError(err instanceof ApiError ? err.message : "Could not start export");
    }
  }

  const runUpload = useCallback(
    async (file: File, resumeExisting: boolean) => {
      const controller = new AbortController();
      uploadControllerRef.current = controller;
      setUploadProgress({
        phase: "starting",
        uploadedBytes: 0,
        totalBytes: file.size,
        percent: 0,
        partNumber: 0,
        partCount: 0,
        etaSeconds: null,
      });
      try {
        await uploadVideo.mutateAsync({
          file,
          signal: controller.signal,
          resumeExisting,
          onProgress: setUploadProgress,
        });
        setUploadProgress(null);
      } catch (err) {
        if (err instanceof PausedUploadError) {
          // Network gave up on a part; keep the session and offer resume.
          setPausedSession(loadUploadSession(id));
          setUploadProgress(null);
          setError("Upload paused due to network issues. Select the file again to resume.");
          return;
        }
        if (err instanceof DOMException && err.name === "AbortError") {
          setError("Upload cancelled. The incomplete upload was cleaned up.");
          setUploadProgress(null);
          return;
        }
        setError(err instanceof ApiError ? err.message : "Upload failed");
        setUploadProgress(null);
      } finally {
        uploadControllerRef.current = null;
        setUploadingCount(0);
      }
    },
    [id, uploadVideo]
  );

  async function onFilesSelected(e: React.ChangeEvent<HTMLInputElement>) {
    const files = Array.from(e.target.files ?? []);
    e.target.value = "";
    if (files.length === 0) return;

    const unsupported = files.filter((f) => !isAcceptedVideo(f));
    if (unsupported.length > 0) {
      setError(`Unsupported file type: ${unsupported.map((f) => f.name).join(", ")}. Allowed: mp4, mov, m4v.`);
      return;
    }

    const tooLarge = files.filter((file) => file.size > maxUploadBytes);
    if (tooLarge.length > 0) {
      setError(
        `${tooLarge.map((file) => file.name).join(", ")} is larger than your plan's upload limit (${formatBytes(maxUploadBytes)}). Split the file or upgrade for a higher limit.`
      );
      return;
    }

    if (maxClips !== undefined && sourceVideos && sourceVideos.length >= maxClips) {
      setError(
        `Your plan allows ${maxClips} clip(s) per project. Remove one or upgrade to upload more.`
      );
      return;
    }

    setError(null);
    setUploadingCount(files.length);

    const first = files[0];
    // Same file as a paused session? Resume in place (the session stays in
    // localStorage so uploadVideoChunked can skip already-uploaded parts).
    // Different file? Discard the old paused session first (its partial
    // object is deleted server-side), then start a fresh upload.
    if (pausedSession) {
      const sameFile =
        pausedSession.fileName === first.name && pausedSession.fileSize === first.size;
      if (!sameFile) {
        await onDiscardPaused();
        clearUploadSession(id);
      }
      setPausedSession(null);
      await runUpload(first, sameFile);
    } else {
      await runUpload(first, false);
    }
  }

  function onCancelUpload() {
    uploadControllerRef.current?.abort();
  }

  const latestJobForVideo = useCallback(
    (videoId: string) =>
      (jobs ?? []).reduce<Job | null>(
        (latest, j) =>
          j.source_video_id === videoId && (!latest || j.created_at >= latest.created_at) ? j : latest,
        null
      ),
    [jobs]
  );

  const latestPlan = editPlans?.[0];
  const allMetadataReady =
    !!sourceVideos && sourceVideos.length > 0 && sourceVideos.every((v) => v.status === "metadata_ready");
  const editPlanJob = jobs?.find((j) => j.type === "edit_plan" && j.status !== "succeeded" && j.status !== "failed");
  const planDuration = latestPlan
    ? Math.max(0, ...latestPlan.plan_json.timeline.map((c) => c.output_end))
    : 0;

  const wasGeneratingRef = useRef(false);
  useEffect(() => {
    const isGenerating = !!editPlanJob;
    if (wasGeneratingRef.current && !isGenerating) {
      queryClient.invalidateQueries({ queryKey: ["projects", id, "edit-plans"] });
    }
    wasGeneratingRef.current = isGenerating;
  }, [editPlanJob, queryClient, id]);

  if (!project) return null;

  const activeJobs = (jobs ?? []).filter(
    (j) => j.status === "queued" || j.status === "running" || j.status === "retrying"
  );
  const progress = uploadProgress;
  const progressLabels = progress ? formatUploadProgress(progress) : null;

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold">{project.title}</h1>
        {project.instructions && (
          <p className="mt-1 text-sm text-muted-foreground">{project.instructions}</p>
        )}
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Source videos</CardTitle>
          <CardDescription>
            Upload mp4, mov, or m4v files up to 5 GB each. Uploads are chunked and resumable -- a
            dropped connection or a refresh won&apos;t force you to start a 1.2 GB file over from zero.
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          <div className="flex flex-wrap items-center gap-3">
            <input
              ref={fileInputRef}
              type="file"
              accept={ACCEPTED_VIDEO_ACCEPT}
              multiple
              className="hidden"
              onChange={onFilesSelected}
            />
            <Button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              disabled={uploadingCount > 0 || !!progress}
            >
              {progress ? "Uploading..." : uploadingCount > 0 ? "Uploading..." : "Upload video(s)"}
            </Button>
            {(uploadingCount > 0 || progress) && (
              <Button
                type="button"
                variant="outline"
                onClick={onCancelUpload}
                disabled={!progress}
              >
                Cancel upload
              </Button>
            )}
            {error && <p className="w-full text-sm text-destructive">{error}</p>}
          </div>

          {progress && progressLabels && (
            <div className="flex flex-col gap-2 rounded-lg border bg-muted/40 px-4 py-3">
              <div className="flex items-center justify-between gap-3 text-sm">
                <span className="truncate font-medium">
                  {progress.phase === "verifying"
                    ? "Verifying upload..."
                    : progress.phase === "starting"
                      ? "Starting upload..."
                      : progress.retrying
                        ? `Uploading (retrying part ${progress.partNumber}/${progress.partCount})...`
                        : `Uploading part ${progress.partNumber}/${progress.partCount}...`}
                </span>
                <span className="tabular-nums text-muted-foreground">{progressLabels.percentLabel}</span>
              </div>
              <div className="h-2 w-full overflow-hidden rounded-full bg-muted">
                <div
                  className="h-full bg-primary transition-all"
                  style={{ width: `${Math.min(100, progress.percent)}%` }}
                />
              </div>
              <div className="flex items-center justify-between text-xs text-muted-foreground">
                <span className="tabular-nums">{progressLabels.bytesLabel}</span>
                <span>{progressLabels.etaLabel ?? (progress.phase === "verifying" ? "Almost done" : " ")}</span>
              </div>
            </div>
          )}

          {pausedSession && (
            <div className="flex flex-col gap-2 rounded-lg border border-dashed px-4 py-3">
              <p className="text-sm font-medium">Upload paused -- {pausedSession.fileName}</p>
              <p className="text-xs text-muted-foreground">
                {Math.floor(pausedPercent)}% uploaded. Select the same file to resume from where it
                stopped (no need to re-upload what already made it).
              </p>
              <div className="h-2 w-full overflow-hidden rounded-full bg-muted">
                <div className="h-full bg-primary" style={{ width: `${pausedPercent}%` }} />
              </div>
              <div className="mt-1 flex gap-2">
                <Button type="button" size="sm" onClick={() => fileInputRef.current?.click()}>
                  Select file to resume
                </Button>
                <Button type="button" size="sm" variant="outline" onClick={onDiscardPaused}>
                  Discard
                </Button>
              </div>
            </div>
          )}

          {activeJobs.length > 0 && (
            <div className="flex flex-wrap items-center gap-2 text-sm">
              <span className="text-muted-foreground">Processing:</span>
              {activeJobs.map((job) => (
                <Badge key={job.id} variant={JOB_STATUS_VARIANT[job.status]}>
                  {job.stage ?? JOB_STATUS_LABEL[job.status]}
                  {job.progress_pct > 0 && ` (${job.progress_pct}%)`}
                </Badge>
              ))}
            </div>
          )}

          {sourceVideos && sourceVideos.length > 0 && (
            <>
              <Separator />
              <ul className="flex flex-col gap-2">
                {sourceVideos
                  .filter((video) => !video.upload_pending)
                  .map((video) => {
                    const job = latestJobForVideo(video.id);
                    const isActiveJob =
                      job && (job.status === "queued" || job.status === "running" || job.status === "retrying");
                    const badgeLabel = isActiveJob
                      ? `${JOB_TYPE_LABEL[job.type] ?? "Processing"}: ${job.stage ?? JOB_STATUS_LABEL[job.status]}`
                      : STATUS_LABEL[video.status];
                    return (
                      <li key={video.id} className="flex flex-col gap-1 rounded-md border px-3 py-2 text-sm">
                        <div className="flex items-center justify-between gap-2">
                          <span className="truncate text-muted-foreground">
                            {video.original_filename ?? `Clip ${video.order_index + 1}`}
                            {video.duration_seconds && ` -- ${Math.round(Number(video.duration_seconds))}s`}
                            {video.size_bytes && ` -- ${formatBytes(video.size_bytes)}`}
                          </span>
                          <div className="flex shrink-0 items-center gap-2">
                            <Badge
                              variant={isActiveJob ? JOB_STATUS_VARIANT[job!.status] : STATUS_VARIANT[video.status]}
                              title={job?.error ?? undefined}
                            >
                              {badgeLabel}
                              {isActiveJob && job!.progress_pct > 0 && ` (${job!.progress_pct}%)`}
                            </Badge>
                            {/* Only offer a retry when nothing is already in
                                flight for this clip: each click enqueues a
                                fresh proxy job, and with an active job still
                                running they stack up (one clip, a dozen
                                queued transcodes) and starve the worker. */}
                            {(video.status === "uploaded" || video.status === "failed") &&
                              !isActiveJob && (
                              <Button
                                type="button"
                                variant="ghost"
                                size="icon-sm"
                                aria-label="Retry processing"
                                title="Stuck? Restart processing for this clip."
                                disabled={retryingId === video.id}
                                onClick={() => onRetry(video.id)}
                              >
                                <RotateCwIcon className="text-muted-foreground" />
                              </Button>
                            )}
                            <Button
                              type="button"
                              variant="ghost"
                              size="icon-sm"
                              aria-label="Remove clip"
                              disabled={deletingId === video.id}
                              onClick={() => onDelete(video.id)}
                            >
                              <Trash2Icon className="text-muted-foreground" />
                            </Button>
                          </div>
                        </div>
                        {video.status === "failed" && job?.error && (
                          <p className="text-xs text-destructive" title={job.error}>
                            {job.error.length > 220 ? `${job.error.slice(0, 220)}…` : job.error}
                          </p>
                        )}
                      </li>
                    );
                  })}
              </ul>
            </>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Edit plan</CardTitle>
          <CardDescription>
            Claude picks the strongest moments from your footage and assembles a cut list around your
            chosen style.
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          {!sourceVideos || sourceVideos.length === 0 ? (
            <p className="text-sm text-muted-foreground">Upload a video first.</p>
          ) : (
            <div className="flex flex-wrap items-center gap-3">
              <Button
                type="button"
                onClick={onGeneratePlan}
                disabled={!allMetadataReady || !!editPlanJob || triggerEditPlan.isPending}
              >
                <SparklesIcon />
                {editPlanJob
                  ? editPlanJob.stage ?? "Generating..."
                  : latestPlan
                    ? "Regenerate edit plan"
                    : "Generate edit plan"}
              </Button>
              {!allMetadataReady && !editPlanJob && (
                <p className="text-sm text-muted-foreground">
                  Waiting for all clips to finish processing first.
                </p>
              )}
              {planError && <p className="w-full text-sm text-destructive">{planError}</p>}
            </div>
          )}

          {latestPlan && (
            <>
              <Separator />
              <div className="flex flex-col gap-3">
                <div className="grid grid-cols-3 gap-3 text-center">
                  <div className="rounded-lg border px-3 py-2">
                    <p className="text-xs text-muted-foreground">Hook</p>
                    <p className="text-lg font-semibold">{latestPlan.viral_score.hook_score}</p>
                  </div>
                  <div className="rounded-lg border px-3 py-2">
                    <p className="text-xs text-muted-foreground">Retention</p>
                    <p className="text-lg font-semibold">{latestPlan.viral_score.retention_score}</p>
                  </div>
                  <div className="rounded-lg border px-3 py-2">
                    <p className="text-xs text-muted-foreground">Engagement</p>
                    <p className="text-lg font-semibold">{latestPlan.viral_score.engagement_score}</p>
                  </div>
                </div>
                <p className="text-sm text-muted-foreground">{latestPlan.viral_score.reasoning}</p>
                <p className="text-xs text-muted-foreground">
                  {latestPlan.plan_json.timeline.length} clip
                  {latestPlan.plan_json.timeline.length === 1 ? "" : "s"} -- ~
                  {Math.round(planDuration)}s output
                </p>
              </div>
            </>
          )}
        </CardContent>
      </Card>

      {latestPlan && (
        <Card>
          <CardHeader>
            <CardTitle>Export</CardTitle>
            <CardDescription>Vertical (9:16) only for now.</CardDescription>
          </CardHeader>
          <CardContent className="flex flex-col gap-4">
            <div className="flex flex-wrap items-center gap-3">
              <Select
                items={QUALITY_ITEMS.filter((item) => allowedQualities.includes(item.value))}
                value={quality}
                onValueChange={(value) => value && setQuality(value as ExportQuality)}
              >
                <SelectTrigger className="w-40">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {QUALITY_ITEMS.filter((item) => allowedQualities.includes(item.value)).map((item) => (
                    <SelectItem key={item.value} value={item.value}>
                      {item.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <Button type="button" onClick={onCreateExport} disabled={createExport.isPending}>
                {createExport.isPending ? "Starting..." : "Start export"}
              </Button>
              {exportError && <p className="w-full text-sm text-destructive">{exportError}</p>}
            </div>

            {exports && exports.length > 0 && (
              <>
                <Separator />
                <ul className="flex flex-col gap-2">
                  {exports.map((exp) => (
                    <li
                      key={exp.id}
                      className="flex items-center justify-between rounded-md border px-3 py-2 text-sm"
                    >
                      <span className="text-muted-foreground">{exp.quality}</span>
                      <div className="flex items-center gap-2">
                        <Badge variant={JOB_STATUS_VARIANT[exp.job_status]}>
                          {JOB_STATUS_LABEL[exp.job_status]}
                        </Badge>
                        {exp.job_status === "succeeded" && exp.download_url && (
                          <a href={exp.download_url} target="_blank" rel="noreferrer">
                            <Button type="button" variant="ghost" size="icon-sm" aria-label="Download export">
                              <DownloadIcon className="text-muted-foreground" />
                            </Button>
                          </a>
                        )}
                      </div>
                    </li>
                  ))}
                </ul>
              </>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  );
}
