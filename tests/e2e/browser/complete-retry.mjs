/**
 * Regression test: a transient network failure on uploads/complete must not
 * throw away a fully-uploaded file. Reproduces the reported symptom --
 * progress reaches 100%, then the finalize call fails at the network layer
 * (net::ERR_FAILED, which the browser surfaces as a CORS error because no
 * response arrives at all).
 */
import { chromium } from "playwright";
import { execFileSync } from "node:child_process";
import { mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const BASE = process.env.BASE ?? "http://localhost:3000";
const API = process.env.API ?? "http://localhost:8000";
let passed = 0, failed = 0;
const check = (n, c, d = "") => (c ? (console.log(`  PASS  ${n}`), passed++) : (console.log(`  FAIL  ${n}${d ? ` -- ${d}` : ""}`), failed++));

const dir = mkdtempSync(join(tmpdir(), "vc-cr-"));
const videoPath = join(dir, "clip.mp4");
execFileSync("docker", ["compose","-f","infra/docker-compose.dev.yml","exec","-T","worker",
  "ffmpeg","-v","error","-y","-f","lavfi","-i","testsrc=duration=2:size=320x240:rate=15",
  "-f","lavfi","-i","sine=duration=2","-c:v","libx264","-preset","ultrafast","-pix_fmt","yuv420p",
  "-c:a","aac","/tmp/cr.mp4"], { cwd: "../../..", stdio: "pipe" });
execFileSync("docker", ["compose","-f","infra/docker-compose.dev.yml","cp","worker:/tmp/cr.mp4", videoPath],
  { cwd: "../../..", stdio: "pipe" });

const browser = await chromium.launch({ headless: true });
const page = await (await browser.newContext()).newPage();
page.setDefaultTimeout(30_000);

try {
  const email = `complete-retry-${Date.now()}@example.com`;
  await page.goto(`${BASE}/sign-up`, { waitUntil: "networkidle" });
  await page.fill("#name", "Complete Retry");
  await page.fill("#email", email);
  await page.fill("#password", "testpass123");
  await page.getByRole("button", { name: "Create account" }).click();
  await page.waitForURL(/\/dashboard\/projects/, { timeout: 30_000 });

  // Fail the FIRST complete call at the network layer, then let it through.
  let completeCalls = 0;
  await page.route("**/uploads/complete", (route) => {
    completeCalls += 1;
    if (completeCalls === 1) return route.abort("failed");
    return route.continue();
  });

  await page.goto(`${BASE}/dashboard/projects/new`, { waitUntil: "networkidle" });
  await page.fill("#title", "Complete retry project");
  await page.setInputFiles("input[type=file]", videoPath);
  await page.getByRole("button", { name: /Create project & upload video/ }).click();

  await page.waitForURL(/\/dashboard\/projects\/[0-9a-f-]{36}$/, { timeout: 90_000 });
  check("upload survives a transient failure on complete", true);
  check("complete was actually retried", completeCalls >= 2, `calls=${completeCalls}`);

  const token = await page.evaluate(() => JSON.parse(localStorage.getItem("viralcut-auth")).state.token);
  const projects = await fetch(`${API}/api/v1/projects`, { headers: { Authorization: `Bearer ${token}` } }).then(r => r.json());
  const clips = await fetch(`${API}/api/v1/projects/${projects[0].id}/source-videos`, { headers: { Authorization: `Bearer ${token}` } }).then(r => r.json());
  check("the clip is attached and not left pending", clips.length === 1 && !clips[0].upload_pending,
    JSON.stringify(clips.map(c => ({ p: c.upload_pending }))));
} catch (err) {
  check("unexpected error", false, err.message.split("\n")[0]);
} finally {
  await browser.close();
}
console.log(`\n${passed} passed, ${failed} failed`);
process.exit(failed === 0 ? 0 : 1);
