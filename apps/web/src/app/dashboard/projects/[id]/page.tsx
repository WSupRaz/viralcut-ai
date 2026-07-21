"use client";

import { useParams } from "next/navigation";
import { useRef, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { ApiError } from "@/lib/api-client";
import { useProject, useSourceVideos, useUploadSourceVideo } from "@/lib/query/hooks";
import type { SourceVideoStatus } from "@/types/api";

const ACCEPTED_TYPES = ["video/mp4", "video/quicktime", "video/x-m4v"];

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

  const fileInputRef = useRef<HTMLInputElement>(null);
  const [error, setError] = useState<string | null>(null);
  const [uploadingCount, setUploadingCount] = useState(0);

  async function onFilesSelected(e: React.ChangeEvent<HTMLInputElement>) {
    const files = Array.from(e.target.files ?? []);
    e.target.value = "";
    if (files.length === 0) return;

    const unsupported = files.filter((f) => !ACCEPTED_TYPES.includes(f.type));
    if (unsupported.length > 0) {
      setError(`Unsupported file type: ${unsupported.map((f) => f.name).join(", ")}. Allowed: mp4, mov, m4v.`);
      return;
    }

    setError(null);
    setUploadingCount(files.length);
    try {
      for (const file of files) {
        await uploadVideo.mutateAsync(file);
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Upload failed");
    } finally {
      setUploadingCount(0);
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
            Upload mp4, mov, or m4v files. Each one is transcribed and analyzed automatically.
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          <div>
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
            {error && <p className="mt-2 text-sm text-destructive">{error}</p>}
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
                    <Badge variant={STATUS_VARIANT[video.status]}>{STATUS_LABEL[video.status]}</Badge>
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
