"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useRef, useState } from "react";
import {
  ArrowLeftIcon,
  CheckCircle2Icon,
  FilmIcon,
  Loader2Icon,
  UploadCloudIcon,
  XIcon,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { ApiError } from "@/lib/api-client";
import {
  useCreateProject,
  useMyPlan,
  useStyles,
  useUploadVideoToProject,
} from "@/lib/query/hooks";
import {
  formatBytes,
  formatUploadProgress,
  type UploadProgress,
} from "@/lib/upload-client";
import { ACCEPTED_VIDEO_ACCEPT, validateVideoFile } from "@/lib/video-file";

/** Matches the API's own default when the plan endpoint hasn't loaded yet;
 *  the server re-checks against the caller's real plan regardless. */
const FALLBACK_MAX_UPLOAD_BYTES = 5 * 1024 * 1024 * 1024;

type Phase = "idle" | "creating" | "uploading" | "done";

export default function NewProjectPage() {
  const router = useRouter();
  const { data: styles } = useStyles();
  const { data: myPlan } = useMyPlan();
  const createProject = useCreateProject();
  const uploadVideo = useUploadVideoToProject();

  const [title, setTitle] = useState("");
  const [styleId, setStyleId] = useState("");
  const [instructions, setInstructions] = useState("");

  const [file, setFile] = useState<File | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [fileError, setFileError] = useState<string | null>(null);

  const [phase, setPhase] = useState<Phase>("idle");
  const [progress, setProgress] = useState<UploadProgress | null>(null);
  const [error, setError] = useState<string | null>(null);

  /** Set once the project exists. Retrying after a failed upload must reuse
   *  it rather than creating a second project for the same submission. */
  const [projectId, setProjectId] = useState<string | null>(null);
  /** True once a part has been accepted for this project, so a retry resumes
   *  the existing multipart session instead of starting a second one. */
  const hasPartialUpload = useRef(false);
  /** Guards against a double-click landing two submissions before React has
   *  re-rendered with the disabled button. */
  const submitting = useRef(false);
  const abortRef = useRef<AbortController | null>(null);

  const maxUploadBytes = myPlan?.limits.max_upload_bytes ?? FALLBACK_MAX_UPLOAD_BYTES;
  const styleItems = styles?.map((style) => ({ value: style.id, label: style.name })) ?? [];
  const busy = phase === "creating" || phase === "uploading";

  const selectFile = useCallback(
    (candidate: File | undefined) => {
      if (!candidate) return;
      const problem = validateVideoFile(candidate, maxUploadBytes);
      if (problem) {
        setFileError(problem);
        setFile(null);
        return;
      }
      setFileError(null);
      setFile(candidate);
    },
    [maxUploadBytes]
  );

  function onDrop(event: React.DragEvent) {
    event.preventDefault();
    setIsDragging(false);
    if (busy) return;
    selectFile(event.dataTransfer.files[0]);
  }

  function removeFile() {
    setFile(null);
    setFileError(null);
    setProgress(null);
  }

  async function onSubmit(event: React.FormEvent) {
    event.preventDefault();
    if (submitting.current || busy) return;

    if (!title.trim()) {
      setError("Give your project a name first.");
      return;
    }
    if (file) {
      const problem = validateVideoFile(file, maxUploadBytes);
      if (problem) {
        setFileError(problem);
        return;
      }
    }

    submitting.current = true;
    setError(null);

    // Declared outside the try so the catch can tell "creation failed" from
    // "created, then upload failed". The `projectId` state can't be used for
    // that: it's the render-time value, still null in this closure even after
    // setProjectId runs below.
    // Reuse the project from a previous attempt whose upload failed --
    // otherwise every retry would leave another empty project behind.
    let id = projectId;

    try {
      if (!id) {
        setPhase("creating");
        const project = await createProject.mutateAsync({
          title: title.trim(),
          target_aspect_ratio: "9:16",
          style_id: styleId || null,
          instructions: instructions.trim() || null,
        });
        id = project.id;
        setProjectId(id);
      }

      // No footage yet is a valid choice: the project detail page can upload
      // later, so send them there rather than blocking project creation.
      if (!file) {
        router.replace(`/dashboard/projects/${id}`);
        return;
      }

      setPhase("uploading");
      abortRef.current = new AbortController();
      await uploadVideo.mutateAsync({
        projectId: id,
        file,
        signal: abortRef.current.signal,
        resumeExisting: hasPartialUpload.current,
        onProgress: (update) => {
          if (update.uploadedBytes > 0) hasPartialUpload.current = true;
          setProgress(update);
        },
      });

      setPhase("done");
      router.replace(`/dashboard/projects/${id}`);
    } catch (err) {
      const cancelled = err instanceof DOMException && err.name === "AbortError";
      setPhase("idle");
      setProgress(null);
      if (cancelled) {
        setError(null);
      } else if (id) {
        // The project exists, so the failure was in the upload -- keep it and
        // let the user retry the upload alone.
        setError(
          err instanceof ApiError
            ? `Video upload failed: ${err.message}`
            : "Video upload failed."
        );
      } else {
        setError(
          err instanceof ApiError ? err.message : "Could not create the project. Try again."
        );
      }
      // Only re-open the gate on failure. Every success path navigates away,
      // and releasing it there lets a queued second click (a double-click that
      // landed while the first submit was still in flight) start a *second*
      // upload against the project that was just created.
      submitting.current = false;
      abortRef.current = null;
    }
  }

  const progressLabels = progress ? formatUploadProgress(progress) : null;
  const uploadFailedAfterCreate = !!projectId && !busy && !!error;

  return (
    <div className="mx-auto flex max-w-2xl flex-col gap-6">
      <div>
        <Link
          href="/dashboard/projects"
          className="inline-flex items-center gap-1.5 text-sm text-muted-foreground transition-colors hover:text-foreground"
        >
          <ArrowLeftIcon className="size-3.5" />
          Projects
        </Link>
        <h1 className="mt-3 text-2xl font-semibold tracking-tight">Create new project</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Name it, pick a style, and add your footage — all in one step. Vertical (9:16) only for
          now.
        </p>
      </div>

      <Card>
        <form onSubmit={onSubmit} className="flex flex-col gap-5 px-4 py-4">
          <div className="flex flex-col gap-2">
            <Label htmlFor="title">Project name</Label>
            <Input
              id="title"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="e.g. Podcast episode 12 — best moments"
              disabled={busy}
              required
            />
          </div>

          <div className="flex flex-col gap-2">
            <Label htmlFor="style">Editing style</Label>
            <Select
              items={styleItems}
              value={styleId}
              onValueChange={(value) => setStyleId(value ?? "")}
              disabled={busy}
            >
              <SelectTrigger id="style" className="w-full">
                <SelectValue placeholder="Choose a style" />
              </SelectTrigger>
              <SelectContent>
                {styles?.map((style) => (
                  <SelectItem key={style.id} value={style.id}>
                    {style.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="flex flex-col gap-2">
            <Label htmlFor="instructions">Prompt / instructions (optional)</Label>
            <Textarea
              id="instructions"
              placeholder='e.g. "Turn this podcast into a punchy hook-driven short."'
              value={instructions}
              onChange={(e) => setInstructions(e.target.value)}
              disabled={busy}
            />
          </div>

          <div className="flex flex-col gap-2">
            <Label>Video</Label>

            {!file ? (
              <>
                <label
                  onDragOver={(e) => {
                    e.preventDefault();
                    if (!busy) setIsDragging(true);
                  }}
                  onDragLeave={() => setIsDragging(false)}
                  onDrop={onDrop}
                  className={`flex cursor-pointer flex-col items-center justify-center gap-2 rounded-xl border border-dashed px-6 py-10 text-center transition-colors ${
                    isDragging
                      ? "border-primary bg-primary/[0.07]"
                      : "border-border hover:border-primary/50 hover:bg-muted/40"
                  } ${busy ? "pointer-events-none opacity-60" : ""}`}
                >
                  <input
                    type="file"
                    accept={ACCEPTED_VIDEO_ACCEPT}
                    className="hidden"
                    disabled={busy}
                    onChange={(e) => {
                      selectFile(e.target.files?.[0]);
                      e.target.value = "";
                    }}
                  />
                  <UploadCloudIcon className="size-7 text-muted-foreground" />
                  <div>
                    <p className="text-sm font-medium">Drop your video here</p>
                    <p className="mt-0.5 text-xs text-muted-foreground">
                      or click to browse — mp4, mov, m4v up to {formatBytes(maxUploadBytes)}
                    </p>
                  </div>
                </label>
                <p className="text-xs text-muted-foreground">
                  You can also skip this and add footage later.
                </p>
              </>
            ) : (
              <div className="flex flex-col gap-3 rounded-xl border px-4 py-3">
                <div className="flex items-start justify-between gap-3">
                  <div className="flex min-w-0 items-center gap-3">
                    <span className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-muted">
                      <FilmIcon className="size-4 text-muted-foreground" />
                    </span>
                    <div className="min-w-0">
                      <p className="truncate text-sm font-medium">{file.name}</p>
                      <p className="text-xs text-muted-foreground">
                        {formatBytes(file.size)} · {file.type || "video"}
                      </p>
                    </div>
                  </div>
                  {!busy && (
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon-sm"
                      aria-label="Remove video"
                      onClick={removeFile}
                    >
                      <XIcon />
                    </Button>
                  )}
                </div>

                {phase === "idle" && !error && (
                  <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
                    <CheckCircle2Icon className="size-3.5" />
                    Ready to upload
                  </p>
                )}

                {phase === "uploading" && progress && progressLabels && (
                  <div className="flex flex-col gap-1.5">
                    <div className="h-1.5 w-full overflow-hidden rounded-full bg-muted">
                      <div
                        className="h-full rounded-full bg-primary transition-all"
                        style={{ width: `${Math.min(100, progress.percent)}%` }}
                      />
                    </div>
                    <div className="flex flex-wrap justify-between gap-x-3 text-xs text-muted-foreground">
                      <span>
                        {progress.phase === "verifying"
                          ? "Verifying upload…"
                          : `Uploading ${progressLabels.percentLabel}`}
                        {progress.retrying ? " · retrying" : ""}
                      </span>
                      <span>
                        {progressLabels.bytesLabel}
                        {progressLabels.etaLabel ? ` · ${progressLabels.etaLabel}` : ""}
                      </span>
                    </div>
                  </div>
                )}

                {phase === "done" && (
                  <p className="flex items-center gap-1.5 text-xs text-primary">
                    <CheckCircle2Icon className="size-3.5" />
                    Uploaded — starting processing…
                  </p>
                )}
              </div>
            )}

            {fileError && <p className="text-sm text-destructive">{fileError}</p>}
          </div>

          {error && (
            <div className="flex flex-col gap-1 rounded-lg border border-destructive/40 bg-destructive/[0.07] px-3 py-2.5">
              <p className="text-sm text-destructive">{error}</p>
              {uploadFailedAfterCreate && (
                <p className="text-xs text-muted-foreground">
                  Your project was created and saved. Retrying resumes this upload — it won&apos;t
                  create a second project. You can also{" "}
                  <Link
                    href={`/dashboard/projects/${projectId}`}
                    className="underline underline-offset-2 hover:text-foreground"
                  >
                    open the project
                  </Link>{" "}
                  and upload there.
                </p>
              )}
            </div>
          )}

          <div className="flex items-center gap-2">
            <Button type="submit" disabled={busy || !title.trim()}>
              {phase === "creating" && <Loader2Icon className="animate-spin" />}
              {phase === "uploading" && <Loader2Icon className="animate-spin" />}
              {phase === "creating"
                ? "Creating project…"
                : phase === "uploading"
                  ? "Uploading video…"
                  : uploadFailedAfterCreate
                    ? "Retry upload"
                    : file
                      ? "Create project & upload video"
                      : "Create project"}
            </Button>

            {phase === "uploading" ? (
              <Button type="button" variant="outline" onClick={() => abortRef.current?.abort()}>
                Cancel upload
              </Button>
            ) : (
              !busy && (
                <Button variant="ghost" render={<Link href="/dashboard/projects" />}>
                  Cancel
                </Button>
              )
            )}
          </div>
        </form>
      </Card>
    </div>
  );
}
