"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api-client";
import { uploadVideoChunked } from "@/lib/upload-client";
import { useAuthStore } from "@/stores/auth-store";
import type { Job } from "@/types/api";

function useToken(): string {
  const token = useAuthStore((s) => s.token);
  if (!token) throw new Error("Not authenticated");
  return token;
}

const TERMINAL_JOB_STATUSES: Job["status"][] = ["succeeded", "failed"];

export function useStyles() {
  const token = useToken();
  return useQuery({ queryKey: ["styles"], queryFn: () => api.listStyles(token) });
}

export function useProjects() {
  const token = useToken();
  return useQuery({ queryKey: ["projects"], queryFn: () => api.listProjects(token) });
}

export function useProject(projectId: string) {
  const token = useToken();
  return useQuery({
    queryKey: ["projects", projectId],
    queryFn: () => api.getProject(token, projectId),
  });
}

export function useCreateProject() {
  const token = useToken();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: {
      title: string;
      target_aspect_ratio: string;
      style_id?: string | null;
      instructions?: string | null;
    }) => api.createProject(token, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["projects"] });
    },
  });
}

export function useSourceVideos(projectId: string) {
  const token = useToken();
  return useQuery({
    queryKey: ["projects", projectId, "source-videos"],
    queryFn: () => api.listSourceVideos(token, projectId),
    refetchInterval: (query) => {
      const videos = query.state.data;
      if (!videos) return false;
      const allReady = videos.every((v) => v.status === "metadata_ready" || v.status === "failed");
      return allReady ? false : 2000;
    },
  });
}

export function useDeleteSourceVideo(projectId: string) {
  const token = useToken();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (sourceVideoId: string) => api.deleteSourceVideo(token, projectId, sourceVideoId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["projects", projectId, "source-videos"] });
    },
  });
}

export function useRetrySourceVideo(projectId: string) {
  const token = useToken();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (sourceVideoId: string) => api.retrySourceVideo(token, projectId, sourceVideoId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["projects", projectId, "source-videos"] });
      queryClient.invalidateQueries({ queryKey: ["projects", projectId, "jobs"] });
    },
  });
}

export function useUploadSourceVideo(projectId: string) {
  const token = useToken();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      file,
      onProgress,
      signal,
      resumeExisting = false,
    }: {
      file: File;
      onProgress?: Parameters<typeof uploadVideoChunked>[0]["onProgress"];
      signal?: AbortSignal;
      resumeExisting?: boolean;
    }) =>
      uploadVideoChunked({
        token,
        projectId,
        file,
        onProgress,
        signal,
        resumeExisting,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["projects", projectId, "source-videos"] });
      queryClient.invalidateQueries({ queryKey: ["projects", projectId, "jobs"] });
    },
  });
}

export function useJobs(projectId: string) {
  const token = useToken();
  return useQuery({
    queryKey: ["projects", projectId, "jobs"],
    queryFn: () => api.listJobs(token, projectId),
    refetchInterval: (query) => {
      const jobs = query.state.data;
      if (!jobs) return false;
      const allTerminal = jobs.every((j) => TERMINAL_JOB_STATUSES.includes(j.status));
      return allTerminal ? false : 2000;
    },
  });
}

export function useEditPlans(projectId: string) {
  const token = useToken();
  return useQuery({
    queryKey: ["projects", projectId, "edit-plans"],
    queryFn: () => api.listEditPlans(token, projectId),
  });
}

export function useTriggerEditPlan(projectId: string) {
  const token = useToken();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => api.triggerEditPlan(token, projectId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["projects", projectId, "jobs"] });
    },
  });
}

export function useExports(projectId: string) {
  const token = useToken();
  return useQuery({
    queryKey: ["projects", projectId, "exports"],
    queryFn: () => api.listExports(token, projectId),
    refetchInterval: (query) => {
      const exports = query.state.data;
      if (!exports) return false;
      const allTerminal = exports.every((e) => TERMINAL_JOB_STATUSES.includes(e.job_status));
      return allTerminal ? false : 3000;
    },
  });
}

export function useCreateExport(projectId: string) {
  const token = useToken();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: { edit_plan_id: string; aspect_ratio: string; quality: string }) =>
      api.createExport(token, projectId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["projects", projectId, "exports"] });
    },
  });
}
