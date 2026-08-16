import type {
  EditPlan,
  Export,
  Job,
  PlanLimits,
  Project,
  SourceVideo,
  Style,
  UploadPart,
  UploadPartUrl,
  UploadStartResponse,
  User,
} from "@/types/api";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  status: number;

  constructor(status: number, detail: string) {
    super(detail);
    this.status = status;
  }
}

export type UploadProgressCallback = (progress: number) => void;

const UPLOAD_TIMEOUT_MS = 60 * 60 * 1000;

async function request<T>(
  path: string,
  options: { method?: string; body?: unknown; token?: string | null } = {}
): Promise<T> {
  const { method = "GET", body, token } = options;

  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (token) headers.Authorization = `Bearer ${token}`;

  const res = await fetch(`${API_BASE}${path}`, {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });

  if (!res.ok) {
    let detail = res.statusText;
    try {
      const data = await res.json();
      detail = data.detail ?? detail;
    } catch {
      // response body wasn't JSON -- fall back to statusText
    }
    throw new ApiError(res.status, detail);
  }

  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export const api = {
  register: (email: string, password: string, name: string) =>
    request<User>("/api/v1/auth/register", { method: "POST", body: { email, password, name } }),

  login: (email: string, password: string) =>
    request<{ access_token: string; token_type: string }>("/api/v1/auth/login", {
      method: "POST",
      body: { email, password },
    }),

  me: (token: string) => request<User>("/api/v1/auth/me", { token }),

  /** The caller's current plan tier + limits (drives UI gating). */
  myPlan: (token: string) => request<{ tier: string; limits: PlanLimits }>("/api/v1/plans/me", { token }),

  /** Every plan tier and its limits (public pricing data). */
  listPlans: () => request<{ plans: { tier: string; limits: PlanLimits }[] }>("/api/v1/plans"),

  listStyles: (token: string) => request<Style[]>("/api/v1/styles", { token }),

  listProjects: (token: string) => request<Project[]>("/api/v1/projects", { token }),

  createProject: (
    token: string,
    data: { title: string; target_aspect_ratio: string; style_id?: string | null; instructions?: string | null }
  ) => request<Project>("/api/v1/projects", { method: "POST", body: data, token }),

  getProject: (token: string, projectId: string) =>
    request<Project>(`/api/v1/projects/${projectId}`, { token }),

  /** Begin a resumable multipart upload session; returns chunk geometry. */
  startUpload: (
    token: string,
    projectId: string,
    data: { filename: string; content_type: string; size_bytes: number }
  ) =>
    request<UploadStartResponse>(`/api/v1/projects/${projectId}/source-videos/uploads/start`, {
      method: "POST",
      body: data,
      token,
    }),

  /** Parts already on the server for a pending upload (for resume). */
  getUploadParts: (token: string, projectId: string, sourceVideoId: string) =>
    request<UploadPart[]>(`/api/v1/projects/${projectId}/source-videos/${sourceVideoId}/uploads/parts`, {
      token,
    }),

  /** Freshly-signed PUT URL for one part. */
  getPartUrl: (token: string, projectId: string, sourceVideoId: string, partNumber: number) =>
    request<UploadPartUrl>(`/api/v1/projects/${projectId}/source-videos/${sourceVideoId}/uploads/part-url?part_number=${partNumber}`, {
      token,
    }),

  /** Verify + assemble all parts server-side, enqueue processing. */
  completeUpload: (token: string, projectId: string, sourceVideoId: string) =>
    request<Job>(`/api/v1/projects/${projectId}/source-videos/${sourceVideoId}/uploads/complete`, {
      method: "POST",
      token,
    }),

  /** Re-run processing for a source video (checks storage first). */
  retrySourceVideo: (token: string, projectId: string, sourceVideoId: string) =>
    request<Job>(`/api/v1/projects/${projectId}/source-videos/${sourceVideoId}/retry`, {
      method: "POST",
      token,
    }),

  /** PUT a single chunk to a presigned part URL (streams, never loads the
   *  whole file into memory -- File.slice() blobs are read off disk). */
  uploadPart: (
    uploadUrl: string,
    blob: Blob,
    onProgress?: UploadProgressCallback,
    signal?: AbortSignal
  ) =>
    new Promise<void>((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      let settled = false;

      const finish = (callback: () => void) => {
        if (settled) return;
        settled = true;
        signal?.removeEventListener("abort", abortUpload);
        callback();
      };

      const abortUpload = () => xhr.abort();
      if (signal?.aborted) {
        reject(new DOMException("Upload cancelled", "AbortError"));
        return;
      }

      signal?.addEventListener("abort", abortUpload, { once: true });
      xhr.open("PUT", uploadUrl);
      xhr.timeout = UPLOAD_TIMEOUT_MS;

      xhr.upload.onprogress = (event) => {
        if (event.lengthComputable) {
          onProgress?.(Math.min(100, Math.round((event.loaded / event.total) * 100)));
        }
      };
      xhr.onload = () => {
        if (xhr.status >= 200 && xhr.status < 300) {
          onProgress?.(100);
          finish(resolve);
          return;
        }
        finish(() => reject(new ApiError(xhr.status, "Upload to storage failed")));
      };
      xhr.onerror = () => finish(() => reject(new ApiError(0, "Network error while uploading video")));
      xhr.ontimeout = () =>
        finish(() => reject(new ApiError(0, "Upload timed out. Check your connection and try again.")));
      xhr.onabort = () => finish(() => reject(new DOMException("Upload cancelled", "AbortError")));
      xhr.send(blob);
    }),

  listSourceVideos: (token: string, projectId: string) =>
    request<SourceVideo[]>(`/api/v1/projects/${projectId}/source-videos`, { token }),

  deleteSourceVideo: (token: string, projectId: string, sourceVideoId: string) =>
    request<void>(`/api/v1/projects/${projectId}/source-videos/${sourceVideoId}`, {
      method: "DELETE",
      token,
    }),

  listJobs: (token: string, projectId: string) =>
    request<Job[]>(`/api/v1/projects/${projectId}/jobs`, { token }),

  getJob: (token: string, projectId: string, jobId: string) =>
    request<Job>(`/api/v1/projects/${projectId}/jobs/${jobId}`, { token }),

  triggerEditPlan: (token: string, projectId: string) =>
    request<Job>(`/api/v1/projects/${projectId}/edit-plans`, { method: "POST", token }),

  listEditPlans: (token: string, projectId: string) =>
    request<EditPlan[]>(`/api/v1/projects/${projectId}/edit-plans`, { token }),

  createExport: (
    token: string,
    projectId: string,
    data: { edit_plan_id: string; aspect_ratio: string; quality: string }
  ) => request<Export>(`/api/v1/projects/${projectId}/exports`, { method: "POST", body: data, token }),

  listExports: (token: string, projectId: string) =>
    request<Export[]>(`/api/v1/projects/${projectId}/exports`, { token }),

  getExport: (token: string, projectId: string, exportId: string) =>
    request<Export>(`/api/v1/projects/${projectId}/exports/${exportId}`, { token }),
};
