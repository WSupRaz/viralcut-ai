"use client";

import { useParams } from "next/navigation";
import { useRef, useState } from "react";
import { Trash2Icon } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { ApiError } from "@/lib/api-client";
import { useDeleteSourceVideo, useProject, useSourceVideos, useUploadSourceVideo } from "@/lib/query/hooks";
import type { SourceVideoStatus } from "@/types/api";

const ACCEPTED_TYPES = ["video/mp4", "video/quicktime", "video/x-m4v"];
const MAX_UPLOAD_BYTES = 5 * 1024 * 1024 * 1024;

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

export default function ProjectDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { data: project } = useProject(id);
  const { data: sourceVideos } = useSourceVideos(id);
  const uploadVideo = useUploadSourceVideo(id);
  const deleteVideo = useDeleteSourceVideo(id);

  const fileInputRef = useRef<HTMLInputElement>(null);
  const uploadControllerRef = useRef<AbortController | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [uploadingCount, setUploadingCount] = useState(0);
  const [currentUpload, setCurrentUpload] = useState<{ name: string; progress: number } | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);

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

  async function onFilesSelected(e: React.ChangeEvent<HTMLInputElement>) {
    const files = Array.from(e.target.files ?? []);
    e.target.value = "";
    if (files.length === 0) return;

    const unsupported = files.filter((f) => !ACCEPTED_TYPES.includes(f.type));
    if (unsupported.length > 0) {
      setError(`Unsupported file type: ${unsupported.map((f) => f.name).join(", ")}. Allowed: mp4, mov, m4v.`);
      return;
    }

    const tooLarge = files.filter((file) => file.size > MAX_UPLOAD_BYTES);
    if (tooLarge.length > 0) {
      setError(
        `${tooLarge.map((file) => file.name).join(", ")} is larger than the 5 GB upload limit. Split the file or choose a smaller export.`
      );
      return;
    }

    setError(null);
    setUploadingCount(files.length);
    try {
      for (const file of files) {
        const controller = new AbortController();
        uploadControllerRef.current = controller;
        setCurrentUpload({ name: file.name, progress: 0 });
        await uploadVideo.mutateAsync({
          file,
          signal: controller.signal,
          onProgress: (progress) => setCurrentUpload({ name: file.name, progress }),
        });
      }
    } catch (err) {
      setError(
        err instanceof DOMException && err.name === "AbortError"
          ? "Upload cancelled. The incomplete clip was removed."
          : err instanceof ApiError
            ? err.message
            : "Upload failed"
      );
    } finally {
      setUploadingCount(0);
      setCurrentUpload(null);
      uploadControllerRef.current = null;
    }
  }

  if (!project) return null;

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
            Upload mp4, mov, or m4v files up to 5 GB each. Each one is transcribed and analyzed automatically.
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          <div className="flex flex-wrap items-center gap-3">
            <input
              ref={fileInputRef}
              type="file"
              accept={ACCEPTED_TYPES.join(",")}
              multiple
              className="hidden"
              onChange={onFilesSelected}
            />
            <Button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              disabled={uploadingCount > 0}
            >
              {uploadingCount > 0 ? `Uploading ${uploadingCount}...` : "Upload video(s)"}
            </Button>
            {uploadingCount > 0 && (
              <Button
                type="button"
                variant="outline"
                onClick={() => uploadControllerRef.current?.abort()}
              >
                Cancel upload
              </Button>
            )}
            {currentUpload && (
              <div className="flex min-w-0 items-center gap-3 rounded-lg border bg-muted/40 px-3 py-2">
                <div
                  className="grid size-11 shrink-0 place-items-center rounded-full"
                  style={{
                    background: `conic-gradient(var(--primary) ${currentUpload.progress * 3.6}deg, var(--muted) 0deg)`,
                  }}
                  aria-label={`${currentUpload.progress}% uploaded`}
                >
                  <div className="grid size-8 place-items-center rounded-full bg-card text-[10px] font-semibold">
                    {currentUpload.progress}%
                  </div>
                </div>
                <div className="min-w-0">
                  <p className="truncate text-sm font-medium">{currentUpload.name}</p>
                  <p className="text-xs text-muted-foreground">
                    {currentUpload.progress === 0 ? "Connecting to secure storage..." : "Uploading securely"}
                  </p>
                </div>
              </div>
            )}
            {error && <p className="w-full text-sm text-destructive">{error}</p>}
          </div>

          {sourceVideos && sourceVideos.length > 0 && (
            <>
              <Separator />
              <ul className="flex flex-col gap-2">
                {sourceVideos.map((video) => (
                  <li
                    key={video.id}
                    className="flex items-center justify-between rounded-md border px-3 py-2 text-sm"
                  >
                    <span className="text-muted-foreground">
                      Clip {video.order_index + 1}
                      {video.duration_seconds && ` -- ${Math.round(Number(video.duration_seconds))}s`}
                    </span>
                    <div className="flex items-center gap-2">
                      <Badge variant={STATUS_VARIANT[video.status]}>{STATUS_LABEL[video.status]}</Badge>
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
                  </li>
                ))}
              </ul>
            </>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
