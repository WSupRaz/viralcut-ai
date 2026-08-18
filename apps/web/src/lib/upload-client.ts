import { api, ApiError } from "@/lib/api-client";

/**
 * Chunked, resumable upload of a large video to S3-compatible storage.
 *
 * The file is NEVER loaded into memory: `File.slice()` produces a Blob that
 * the browser reads off disk, and each 8 MiB part is PUT individually. If a
 * part fails (network blip, timeout) it is retried with backoff; if the page
 * is refreshed mid-upload the session metadata survives in localStorage, and
 * asking the server which parts already landed lets us resume from there
 * instead of restarting the whole 1.2 GB.
 *
 * Browser limitation (unavoidable): a Blob handle can't survive a page
 * reload, so resuming after a refresh asks the user to re-select the *same*
 * file (name + size are validated). Network drops within a live page resume
 * fully automatically.
 */

export interface UploadSession {
  projectId: string;
  sourceVideoId: string;
  uploadId: string;
  r2Key: string;
  partSize: number;
  partCount: number;
  fileName: string;
  fileSize: number;
  fileType: string;
  startedAt: number;
}

export type UploadPhase =
  | "starting"
  | "uploading"
  | "verifying"
  | "complete"
  | "paused"
  | "error";

export interface UploadProgress {
  phase: UploadPhase;
  /** Bytes actually on the server (completed parts + in-flight part). */
  uploadedBytes: number;
  totalBytes: number;
  percent: number;
  partNumber: number;
  partCount: number;
  /** Seconds remaining, computed from the rolling average rate. */
  etaSeconds: number | null;
  /** Set when a part is being retried. */
  retrying?: boolean;
  error?: string;
}

const SESSION_PREFIX = "viralcut.upload.session.";
const PART_RETRY_ATTEMPTS = 4;
// The finalize call is cheap and idempotent-ish, and by the time it runs the
// whole file is already uploaded -- worth trying harder than a part.
const COMPLETE_RETRY_ATTEMPTS = 5;
const PART_RETRY_BACKOFF_MS = [1000, 2000, 4000, 8000];

const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

export function loadUploadSession(projectId: string): UploadSession | null {
  try {
    const raw = localStorage.getItem(SESSION_PREFIX + projectId);
    return raw ? (JSON.parse(raw) as UploadSession) : null;
  } catch {
    return null;
  }
}

export function saveUploadSession(session: UploadSession): void {
  try {
    localStorage.setItem(SESSION_PREFIX + session.projectId, JSON.stringify(session));
  } catch {
    // localStorage full/blocked -- resume across refresh is a nice-to-have,
    // not a hard requirement for a single-page failure-free upload.
  }
}

export function clearUploadSession(projectId: string): void {
  try {
    localStorage.removeItem(SESSION_PREFIX + projectId);
  } catch {
    // ignore
  }
}

function formatBytes(bytes: number): string {
  if (bytes >= 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024 * 1024)).toFixed(2)} GB`;
  if (bytes >= 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  return `${Math.round(bytes / 1024)} KB`;
}

export function formatUploadProgress(p: UploadProgress): {
  percentLabel: string;
  bytesLabel: string;
  etaLabel: string | null;
} {
  const percentLabel = `${Math.min(100, Math.floor(p.percent))}%`;
  const bytesLabel = `${formatBytes(p.uploadedBytes)} / ${formatBytes(p.totalBytes)}`;
  let etaLabel: string | null = null;
  if (p.etaSeconds !== null && p.etaSeconds > 0 && p.phase === "uploading") {
    const s = Math.round(p.etaSeconds);
    etaLabel =
      s >= 3600
        ? `${Math.floor(s / 3600)}h ${Math.floor((s % 3600) / 60)}m remaining`
        : s >= 60
          ? `${Math.floor(s / 60)}m ${s % 60}s remaining`
          : `${s}s remaining`;
  }
  return { percentLabel, bytesLabel, etaLabel };
}

interface UploadOptions {
  token: string;
  projectId: string;
  file: File;
  signal?: AbortSignal;
  onProgress?: (progress: UploadProgress) => void;
  /** When true, resume the stored session for this file instead of starting
   *  a fresh upload (used after refresh / network failure). */
  resumeExisting?: boolean;
  /** Internal. Counts self-restarts after a dead session so the retry can
   *  never become an unbounded loop -- see the 409 branch below. */
  restartCount?: number;
}

interface RunningState {
  partNumber: number;
  partCount: number;
  uploadedBytes: number;
  totalBytes: number;
  /** Fixed at upload start -- the rate window spans the whole upload. */
  startedAtMs: number;
  partSizes: number[];
  attempt: number;
  lastError?: string;
}

export interface UploadResult {
  sourceVideoId: string;
  job: Awaited<ReturnType<typeof api.completeUpload>>;
}

function emit(
  onProgress: UploadOptions["onProgress"],
  state: RunningState,
  phase: UploadPhase,
  extra?: Partial<UploadProgress>
): void {
  const percent = state.totalBytes > 0 ? (state.uploadedBytes / state.totalBytes) * 100 : 0;
  const elapsedSec = (Date.now() - state.startedAtMs) / 1000;
  const rate =
    state.uploadedBytes > 0 && elapsedSec > 0 ? state.uploadedBytes / elapsedSec : null;
  const etaSeconds =
    rate && rate > 0 ? (state.totalBytes - state.uploadedBytes) / rate : null;
  onProgress?.({
    phase,
    uploadedBytes: state.uploadedBytes,
    totalBytes: state.totalBytes,
    percent,
    partNumber: state.partNumber,
    partCount: state.partCount,
    etaSeconds,
    retrying: state.attempt > 0,
    error: state.lastError,
    ...extra,
  });
}

function isAbort(error: unknown): boolean {
  return error instanceof DOMException && error.name === "AbortError";
}

/**
 * Upload one file via S3 multipart. Returns the completed upload's job, or
 * throws -- on cancellation the server-side session is aborted and the local
 * session cleared. On a recoverable network failure it returns with the
 * session left in place so the caller can prompt the user to resume.
 */
export async function uploadVideoChunked(options: UploadOptions): Promise<UploadResult> {
  const { token, projectId, file, signal, onProgress } = options;

  let session = options.resumeExisting
    ? loadUploadSession(projectId)
    : null;
  if (session && (session.fileName !== file.name || session.fileSize !== file.size)) {
    // Stored session belongs to a different file -- discard it and start over.
    clearUploadSession(projectId);
    session = null;
  }

  if (!session) {
    onProgress?.({ phase: "starting", uploadedBytes: 0, totalBytes: file.size, percent: 0, partNumber: 0, partCount: 0, etaSeconds: null });
    let started;
    try {
      started = await api.startUpload(token, projectId, {
        filename: file.name,
        content_type: file.type || "video/mp4",
        size_bytes: file.size,
      });
    } catch (error) {
      if (isAbort(error)) throw error;
      throw new ApiError(
        error instanceof ApiError ? error.status : 0,
        `Could not start upload: ${error instanceof ApiError ? error.message : "server unreachable"}`
      );
    }
    session = {
      projectId,
      sourceVideoId: started.source_video_id,
      uploadId: started.upload_id,
      r2Key: started.r2_key,
      partSize: started.part_size,
      partCount: started.part_count,
      fileName: file.name,
      fileSize: file.size,
      fileType: file.type,
      startedAt: Date.now(),
    };
    saveUploadSession(session);
  }

  // Which parts already landed? Resume skips them.
  let uploadedParts = new Set<number>();
  try {
    const parts = await api.getUploadParts(token, projectId, session.sourceVideoId);
    uploadedParts = new Set(parts.map((p) => p.part_number));
  } catch (error) {
    if (isAbort(error)) throw error;
    // 409 == the server-side multipart session vanished (aborted/expired).
    // Restart the session cleanly.
    if (error instanceof ApiError && error.status === 409) {
      clearUploadSession(projectId);
      // Restart once, never repeatedly. If the fresh session is *also* dead the
      // condition is not self-correcting, and looping here re-hits
      // /uploads/start as fast as the network allows -- which trips the
      // upload-start rate limiter and reports "Too many requests" instead of
      // the real problem.
      const restartCount = options.restartCount ?? 0;
      if (restartCount >= 1) {
        throw new ApiError(
          409,
          "Could not start a fresh upload session for this file. Remove the clip and try uploading again."
        );
      }
      return uploadVideoChunked({
        ...options,
        resumeExisting: false,
        restartCount: restartCount + 1,
      });
    }
    // Transient -- we'll find out for real when the first part PUT fails.
  }

  const state: RunningState = {
    partNumber: 1,
    partCount: session.partCount,
    uploadedBytes: 0,
    totalBytes: file.size,
    startedAtMs: Date.now(),
    partSizes: [],
    attempt: 0,
  };

  const partStartBytes = (n: number) => (n - 1) * session.partSize;
  state.uploadedBytes = Array.from(uploadedParts)
    .filter((n) => n <= session.partCount)
    .reduce((sum, n) => {
      state.partSizes[n - 1] =
        n === session.partCount ? file.size - partStartBytes(n) : session.partSize;
      return sum + state.partSizes[n - 1];
    }, 0);

  try {
    for (let n = 1; n <= session.partCount; n += 1) {
      if (signal?.aborted) throw new DOMException("Upload cancelled", "AbortError");
      if (uploadedParts.has(n)) {
        state.partNumber = n;
        continue;
      }

      const start = partStartBytes(n);
      const end = Math.min(file.size, start + session.partSize);
      const blob = file.slice(start, end);
      state.partNumber = n;
      state.attempt = 0;

      let partUploaded = false;
      while (!partUploaded) {
        if (signal?.aborted) throw new DOMException("Upload cancelled", "AbortError");

        let url: string;
        try {
          const res = await api.getPartUrl(token, projectId, session.sourceVideoId, n);
          url = res.upload_url;
        } catch (error) {
          if (isAbort(error)) throw error;
          if (error instanceof ApiError && error.status === 409) {
            clearUploadSession(projectId);
            throw new ApiError(409, "Upload session expired. Select the file again to resume from where it stopped.");
          }
          if (!(await retryable(state, n, onProgress, error))) throw error;
          continue;
        }

        try {
          await api.uploadPart(url, blob, (partPercent) => {
            state.uploadedBytes =
              state.partSizes.slice(0, n - 1).reduce((a, b) => a + b, 0) +
              (blob.size * partPercent) / 100;
            emit(onProgress, state, "uploading");
          }, signal);
          partUploaded = true;
        } catch (error) {
          if (isAbort(error)) throw error;
          if (!(await retryable(state, n, onProgress, error))) {
            // Give up on this part for now -- keep the session so the user
            // can resume (same page: file handle still live; after refresh:
            // re-select the file). Distinguish "hard error" from "paused".
            if (error instanceof ApiError && (error.status === 403 || error.status === 404)) {
              throw error;
            }
            state.lastError =
              error instanceof ApiError ? error.message : "Network error while uploading";
            emit(onProgress, state, "paused");
            throw new PausedUploadError();
          }
        }
      }

      const actualSize = Math.min(session.partSize, file.size - start);
      state.partSizes[n - 1] = actualSize;
      state.uploadedBytes += actualSize;
      state.partNumber = n;
      emit(onProgress, state, "uploading");
    }

    emit(onProgress, state, "verifying");
    // Every byte is already in storage by this point; this call only asks the
    // server to verify and assemble the parts. Failing the whole upload
    // because this one request hit a blip -- after a multi-gigabyte transfer
    // succeeded -- is the worst possible moment to give up, so it gets the
    // same retry treatment the parts do. Only transient failures qualify:
    // a 4xx is a real verdict about the upload and must surface immediately.
    let job;
    let networkAttempts = 0;
    for (let attempt = 1; ; attempt++) {
      try {
        job = await api.completeUpload(token, projectId, session.sourceVideoId);
        break;
      } catch (error) {
        if (isAbort(error)) throw error;

        const status = error instanceof ApiError ? error.status : 0;
        // status 0 covers a fetch that never got a response at all (dropped
        // connection, DNS failure) -- indistinguishable from a CORS error in
        // the browser, and the most common shape of this failure.
        const transient = status === 0 || status >= 500 || status === 408 || status === 429;

        if (error instanceof ApiError && status === 409) {
          if (networkAttempts > 0) {
            // A previous attempt lost its response, so that attempt probably
            // did complete the upload server-side and this 409 is us asking
            // twice -- don't tell the user their finished upload expired.
            clearUploadSession(projectId);
            throw new ApiError(
              409,
              "The upload finished but the confirmation was lost. Refresh the page to check before re-uploading."
            );
          }
          clearUploadSession(projectId);
          throw new ApiError(409, "Upload session expired. Select the file again to resume.");
        }

        if (!transient || attempt >= COMPLETE_RETRY_ATTEMPTS) throw error;

        networkAttempts += 1;
        emit(onProgress, state, "verifying", {
          retrying: true,
          error: error instanceof ApiError ? error.message : "Network error",
        });
        const backoff =
          PART_RETRY_BACKOFF_MS[Math.min(attempt - 1, PART_RETRY_BACKOFF_MS.length - 1)];
        await sleep(backoff + Math.random() * 500);
      }
    }
    clearUploadSession(projectId);
    emit(onProgress, { ...state, uploadedBytes: file.size }, "complete");
    return { sourceVideoId: session.sourceVideoId, job };
  } catch (error) {
    // Cancelled: abort the server-side session so no partial object lingers.
    if (isAbort(error)) {
      try {
        await api.deleteSourceVideo(token, projectId, session.sourceVideoId);
      } catch {
        // best effort -- the abandoned-upload sweep cleans up server-side too
      }
      clearUploadSession(projectId);
    }
    throw error;
  }
}

async function retryable(
  state: RunningState,
  partNumber: number,
  onProgress: UploadOptions["onProgress"],
  error: unknown
): Promise<boolean> {
  state.attempt += 1;
  state.lastError = error instanceof ApiError ? error.message : "Network error";
  if (state.attempt >= PART_RETRY_ATTEMPTS) return false;
  emit(onProgress, state, "uploading");
  const delay = PART_RETRY_BACKOFF_MS[Math.min(state.attempt - 1, PART_RETRY_BACKOFF_MS.length - 1)];
  await sleep(delay + Math.random() * 500);
  return true;
}

/** Thrown when a part failed after all retries; session is left in place. */
export class PausedUploadError extends Error {
  constructor() {
    super("Upload paused; resume to continue");
    this.name = "PausedUploadError";
  }
}

export { formatBytes };
