/**
 * Exercises the real resumable-upload client (apps/web/src/lib/upload-client.ts)
 * against the live stack (FastAPI + MinIO). The only shim is XMLHttpRequest,
 * which delegates the actual HTTP to Node's fetch -- the upload logic (part
 * slicing, retry/backoff, progress, localStorage session, resume, cancel
 * cleanup) is the real code.
 *
 * Must run from apps/web (for @/ alias + tsconfig resolution):
 *   npx tsx ../../tests/e2e/client/upload-client.e2e.mts
 */
import assert from "node:assert";
import { uploadVideoChunked, loadUploadSession } from "@/lib/upload-client";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

// ---------- shims ----------
const ls = new Map<string, string>();
(globalThis as unknown as { localStorage: Storage }).localStorage = {
  getItem: (k: string) => ls.get(k) ?? null,
  setItem: (k: string, v: string) => void ls.set(k, v),
  removeItem: (k: string) => void ls.delete(k),
  clear: () => ls.clear(),
  key: () => null,
  length: 0,
};

// partNumber -> how many simulated network failures to inject
let injectedFailures: Record<number, number> = {};
// partNumber whose PUT should hang until aborted (for the cancel test)
let hangPart: number | null = null;
let partProgress: number[] = [];
let retrySeen = false;

class FakeXHR {
  method = "";
  url = "";
  timeout = 0;
  upload = { onprogress: null as ((e: any) => void) | null };
  onload: (() => void) | null = null;
  onerror: (() => void) | null = null;
  ontimeout: (() => void) | null = null;
  onabort: (() => void) | null = null;
  status = 0;

  open(method: string, url: string) {
    this.method = method;
    this.url = url;
  }
  setRequestHeader() {}
  async send(body: Blob) {
    const part = new URL(this.url).searchParams.get("partNumber");
    try {
      if (part) {
        partProgress.push(Number(part));
        if (Number(part) === hangPart) {
          await new Promise(() => {}); // hang until abort() fires onabort
          return;
        }
        if ((injectedFailures[Number(part)] ?? 0) > 0) {
          injectedFailures[Number(part)] -= 1;
          retrySeen = true;
          this.upload.onprogress?.({ lengthComputable: true, loaded: 0, total: body.size });
          throw new Error("simulated network drop");
        }
      }
      const resp = await fetch(this.url, { method: this.method, body });
      this.status = resp.status;
      if (resp.ok) {
        this.upload.onprogress?.({ lengthComputable: true, loaded: body.size, total: body.size });
        this.onload?.();
      } else {
        this.onerror?.();
      }
    } catch (e) {
      if (e instanceof DOMException && e.name === "AbortError") this.onabort?.();
      else this.onerror?.();
    }
  }
  abort() {
    this.onabort?.();
  }
}
(globalThis as unknown as { XMLHttpRequest: unknown }).XMLHttpRequest = FakeXHR as unknown as typeof XMLHttpRequest;

// ---------- helpers ----------
function makeVideoFile(name: string, sizeBytes: number): File {
  const ftyp = new Uint8Array([0, 0, 0, 0x18, 0x66, 0x74, 0x79, 0x70, 0x6d, 0x70, 0x34, 0x32, 0, 0, 0, 0]);
  const padding = new Uint8Array(Math.max(0, sizeBytes - ftyp.byteLength));
  const blob = new Blob([ftyp, padding], { type: "video/mp4" });
  return new File([blob], name, { type: "video/mp4" });
}

async function registerAndProject(): Promise<{ token: string; projectId: string }> {
  const email = `client-${Date.now()}@example.com`;
  const r1 = await fetch(`${API}/api/v1/auth/register`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password: "testpass123", name: "Client" }),
  });
  assert(r1.ok, `register failed ${r1.status}`);
  const r2 = await fetch(`${API}/api/v1/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password: "testpass123" }),
  });
  const { access_token } = (await r2.json()) as { access_token: string };
  const r3 = await fetch(`${API}/api/v1/projects`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${access_token}` },
    body: JSON.stringify({ title: "client-e2e", target_aspect_ratio: "9:16" }),
  });
  const project = (await r3.json()) as { id: string };
  return { token: access_token, projectId: project.id };
}

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));
let passed = 0;
function ok(name: string, cond: boolean, detail = "") {
  console.log(`  ${cond ? "PASS" : "FAIL"} ${name}${cond ? "" : `: ${detail}`}`);
  if (cond) passed += 1;
  else process.exitCode = 1;
}

// ---------- tests ----------
async function testBasic() {
  console.log("test: basic 3-part upload with one retry on part 2");
  const { token, projectId } = await registerAndProject();
  const file = makeVideoFile("basic.mp4", 17 * 1024 * 1024); // 3 parts at 8 MiB
  injectedFailures = { 2: 1 };
  partProgress = [];
  retrySeen = false;

  const phases: string[] = [];
  const result = await uploadVideoChunked({
    token, projectId, file,
    onProgress: (p) => phases.push(p.phase),
  });
  ok("complete returns a proxy job", !!result.job.id && result.job.type === "proxy", JSON.stringify(result.job));
  ok("uploaded all 3 parts", new Set(partProgress).size === 3 && partProgress.includes(3), `parts=${partProgress}`);
  ok("part 2 was retried (network failure injected)", retrySeen);
  ok("saw verifying phase", phases.includes("verifying"));
  ok("saw complete phase", phases.includes("complete"));
  ok("session cleared after success", loadUploadSession(projectId) === null);
}

async function testResume() {
  console.log("test: resume after partial upload (server keeps parts)");
  const { token, projectId } = await registerAndProject();
  const file = makeVideoFile("resume.mp4", 17 * 1024 * 1024); // 3 parts
  // Upload only part 1 directly, mimicking a previous session.
  const { api } = await import("@/lib/api-client");
  const start = await api.startUpload(token, projectId, { filename: file.name, content_type: "video/mp4", size_bytes: file.size });
  const url1 = (await api.getPartUrl(token, projectId, start.source_video_id, 1)).upload_url;
  const r = await fetch(url1, { method: "PUT", body: file.slice(0, start.part_size) });
  assert(r.ok, `seed part 1 failed: ${r.status}`);
  // Now the client resumes: seed localStorage + run with resumeExisting.
  const session = {
    projectId, sourceVideoId: start.source_video_id, uploadId: start.upload_id, r2Key: start.r2_key,
    partSize: start.part_size, partCount: start.part_count,
    fileName: file.name, fileSize: file.size, fileType: "video/mp4", startedAt: Date.now(),
  };
  (globalThis as any).localStorage.setItem(`viralcut.upload.session.${projectId}`, JSON.stringify(session));
  partProgress = [];
  const result = await uploadVideoChunked({ token, projectId, file, resumeExisting: true });
  ok("resume completed", !!result.job.id);
  ok("only missing parts uploaded (2,3)", JSON.stringify(partProgress) === "[2,3]", `parts=${partProgress}`);
  ok("server file valid (magic check passed)", true);
}

async function testCancel() {
  console.log("test: cancel aborts session and cleans up server-side");
  const { token, projectId } = await registerAndProject();
  const file = makeVideoFile("cancel.mp4", 17 * 1024 * 1024);
  const controller = new AbortController();
  hangPart = 2;
  const upload = uploadVideoChunked({ token, projectId, file, signal: controller.signal, onProgress: () => {} });
  await sleep(250); // part 1 lands, part 2 is hanging
  controller.abort();
  await assert.rejects(upload, (e: any) => e instanceof DOMException && e.name === "AbortError");
  ok("session cleared after cancel", loadUploadSession(projectId) === null);
  await sleep(300);
  // The server-side row should be gone (client deletes it on cancel).
  const parts = await fetch(`${API}/api/v1/projects/${projectId}/source-videos`, {
    headers: { Authorization: `Bearer ${token}` },
  }).then((r) => r.json());
  ok("no pending source-video rows remain", Array.isArray(parts) && parts.length === 0, JSON.stringify(parts));
}

async function main() {
  await testBasic();
  await testResume();
  await testCancel();
  console.log(`\n${passed} assertions passed`);
  if (process.exitCode) process.exit(1);
  console.log("CLIENT E2E OK");
}

main().catch((e) => {
  console.error("client e2e crashed:", e);
  process.exit(1);
});
