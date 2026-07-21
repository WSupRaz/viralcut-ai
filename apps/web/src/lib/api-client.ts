import type {
  EditPlan,
  Export,
  Job,
  Project,
  SourceVideo,
  SourceVideoPresignResponse,
  Style,
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

  listStyles: (token: string) => request<Style[]>("/api/v1/styles", { token }),

  listProjects: (token: string) => request<Project[]>("/api/v1/projects", { token }),

  createProject: (
    token: string,
    data: { title: string; target_aspect_ratio: string; style_id?: string | null; instructions?: string | null }
  ) => request<Project>("/api/v1/projects", { method: "POST", body: data, token }),

  getProject: (token: string, projectId: string) =>
    request<Project>(`/api/v1/projects/${projectId}`, { token }),

  presignUpload: (token: string, projectId: string, filename: string, contentType: string) =>
    request<SourceVideoPresignResponse>(`/api/v1/projects/${projectId}/source-videos/presign-upload`, {
      method: "POST",
      body: { filename, content_type: contentType },
      token,
    }),

  uploadToR2: async (uploadUrl: string, file: File) => {
    const res = await fetch(uploadUrl, {
      method: "PUT",
      headers: { "Content-Type": file.type },
      body: file,
    });
    if (!res.ok) throw new ApiError(res.status, "Upload to storage failed");
  },

  confirmUpload: (token: string, projectId: string, sourceVideoId: string) =>
    request<Job>(`/api/v1/projects/${projectId}/source-videos/${sourceVideoId}/confirm-upload`, {
      method: "POST",
      token,
    }),

  listSourceVideos: (token: string, projectId: string) =>
    request<SourceVideo[]>(`/api/v1/projects/${projectId}/source-videos`, { token }),

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
