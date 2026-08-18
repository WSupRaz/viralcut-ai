/**
 * Browser E2E for the merged "create project + upload video" page.
 *
 * Covers the create-flow cases: page loads, validation, file selection via
 * picker and via drag-and-drop, removing a file, submitting with and without
 * a video, duplicate-submit protection, and that a failed upload reuses the
 * already-created project instead of creating a second one.
 *
 * Usage: node create-with-upload.mjs
 *   BASE=http://localhost:3000  API=http://localhost:8000
 */
import { chromium } from "playwright";
import { execFileSync } from "node:child_process";
import { mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const BASE = process.env.BASE ?? "http://localhost:3000";
const API = process.env.API ?? "http://localhost:8000";

let passed = 0;
let failed = 0;

function check(name, condition, detail = "") {
  if (condition) {
    console.log(`  PASS  ${name}`);
    passed++;
  } else {
    console.log(`  FAIL  ${name}${detail ? ` -- ${detail}` : ""}`);
    failed++;
  }
}

/** Small real mp4 so the upload path exercises actual bytes, not a stub. */
function makeVideo() {
  const dir = mkdtempSync(join(tmpdir(), "vc-e2e-"));
  const out = join(dir, "clip.mp4");
  execFileSync("docker", [
    "compose", "-f", "infra/docker-compose.dev.yml", "exec", "-T", "worker",
    "ffmpeg", "-v", "error", "-y",
    "-f", "lavfi", "-i", "testsrc=duration=2:size=320x240:rate=15",
    "-f", "lavfi", "-i", "sine=frequency=440:duration=2",
    "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
    "-c:a", "aac", "/tmp/e2e-clip.mp4",
  ], { cwd: "../../..", stdio: "pipe" });
  execFileSync("docker", ["compose", "-f", "infra/docker-compose.dev.yml", "cp",
    "worker:/tmp/e2e-clip.mp4", out], { cwd: "../../..", stdio: "pipe" });
  return out;
}

const videoPath = makeVideo();
const browser = await chromium.launch({ headless: true });
const context = await browser.newContext();
const page = await context.newPage();
page.setDefaultTimeout(20_000);

const email = `create-e2e-${Date.now()}@example.com`;

try {
  // --- sign up -------------------------------------------------------------
  await page.goto(`${BASE}/sign-up`, { waitUntil: "networkidle" });
  await page.fill("#name", "Create Flow E2E");
  await page.fill("#email", email);
  await page.fill("#password", "testpass123");
  await page.getByRole("button", { name: "Create account" }).click();
  await page.waitForURL(/\/dashboard\/projects/, { timeout: 30_000 });
  check("Test 15: sign-up + auth still works", true);

  // --- Test 1: reach the New Project page ----------------------------------
  await page.locator('a:has-text("New project"), button:has-text("New project")').first().click();
  await page.waitForURL(/\/dashboard\/projects\/new/);
  await page.locator("#title").waitFor({ state: "visible" });
  check("Test 1: New Project page opens", true);

  const dropZoneVisible = await page.getByText("Drop your video here").isVisible();
  check("Create + upload live on one screen", dropZoneVisible);

  // --- Test 2: fill fields, no file ----------------------------------------
  await page.fill("#title", "E2E merged flow");
  await page.fill("#instructions", "make it punchy");
  check("Test 2: fields accept input without a file", true);

  // --- Test 6: submit with no name is blocked ------------------------------
  await page.fill("#title", "");
  const submit = page.getByRole("button", { name: /Create project/ });
  check("Test 6: submit disabled without a project name", await submit.isDisabled());
  await page.fill("#title", "E2E merged flow");

  // --- Test 3: select a video via the file input ---------------------------
  await page.setInputFiles("input[type=file]", videoPath);
  await page.getByText("Ready to upload").waitFor({ state: "visible" });
  const shownName = await page.getByText("clip.mp4").isVisible();
  check("Test 3: file picker selects a video and shows its name", shownName);

  const label = await page.getByRole("button", { name: /Create project & upload video/ }).isVisible();
  check("Submit label reflects that a video is attached", label);

  // --- Test 5: remove the selected video -----------------------------------
  await page.getByRole("button", { name: "Remove video" }).click();
  await page.getByText("Drop your video here").waitFor({ state: "visible" });
  check("Test 5: removing the file restores the drop zone", true);

  // --- Test 4: drag and drop ------------------------------------------------
  // Synthesise a drop with a real File built in-page from the clip's bytes.
  const bytes = Array.from(
    new Uint8Array(execFileSync("node", ["-e", "process.stdout.write(require('fs').readFileSync(process.argv[1]))", videoPath], { maxBuffer: 1 << 28 }))
  );
  await page.evaluate(async (data) => {
    const file = new File([new Uint8Array(data)], "dropped.mp4", { type: "video/mp4" });
    const dt = new DataTransfer();
    dt.items.add(file);
    const zone = [...document.querySelectorAll("label")].find((l) =>
      l.textContent?.includes("Drop your video here")
    );
    zone.dispatchEvent(new DragEvent("dragover", { bubbles: true, dataTransfer: dt }));
    zone.dispatchEvent(new DragEvent("drop", { bubbles: true, dataTransfer: dt }));
  }, bytes);
  await page.getByText("dropped.mp4").waitFor({ state: "visible" });
  check("Test 4: drag-and-drop selects a video", true);

  // --- Test 8 + 12: submit once, no duplicate on double-click --------------
  const submitBtn = page.getByRole("button", { name: /Create project & upload video/ });
  await submitBtn.click();
  await submitBtn.click({ force: true }).catch(() => {}); // second click must be a no-op

  await page.waitForURL(/\/dashboard\/projects\/[0-9a-f-]{36}$/, { timeout: 60_000 });
  check("Test 8: project created and video uploaded, lands on project page", true);

  // --- Test 12 (verify): exactly one project exists -------------------------
  const token = await page.evaluate(() =>
    JSON.parse(localStorage.getItem("viralcut-auth")).state.token
  );
  const projects = await fetch(`${API}/api/v1/projects`, {
    headers: { Authorization: `Bearer ${token}` },
  }).then((r) => r.json());
  check(
    "Test 12: double-click created exactly one project",
    projects.length === 1,
    `got ${projects.length}`
  );

  // --- Test 13: the project belongs to the authenticated user --------------
  const me = await fetch(`${API}/api/v1/auth/me`, {
    headers: { Authorization: `Bearer ${token}` },
  }).then((r) => r.json());
  check("Test 13: project is owned by the signed-in user", projects[0].user_id === me.id);

  // --- the uploaded clip actually landed -----------------------------------
  const clips = await fetch(`${API}/api/v1/projects/${projects[0].id}/source-videos`, {
    headers: { Authorization: `Bearer ${token}` },
  }).then((r) => r.json());
  check("Uploaded video is attached to the project", clips.length === 1, `got ${clips.length}`);

  // --- Test 14: existing projects still open normally ----------------------
  await page.goto(`${BASE}/dashboard/projects`, { waitUntil: "networkidle" });
  await page.getByText("E2E merged flow").first().click();
  await page.waitForURL(/\/dashboard\/projects\/[0-9a-f-]{36}$/);
  check("Test 14: existing project opens from the list", true);

  // --- Test 7: submit with no video creates the project anyway -------------
  await page.goto(`${BASE}/dashboard/projects/new`, { waitUntil: "networkidle" });
  await page.fill("#title", "No video project");
  await page.getByRole("button", { name: /^Create project$/ }).click();
  await page.waitForURL(/\/dashboard\/projects\/[0-9a-f-]{36}$/, { timeout: 30_000 });
  check("Test 7: submitting without a video still creates the project", true);

  // --- Test 9 + 10: upload fails, retry reuses the same project ------------
  // Fresh account: the free plan caps projects (2), and the cases above have
  // already used the quota -- creation would fail for the wrong reason.
  const ctx2 = await browser.newContext();
  const page2 = await ctx2.newPage();
  page2.setDefaultTimeout(20_000);
  const email2 = `create-e2e-retry-${Date.now()}@example.com`;
  await page2.goto(`${BASE}/sign-up`, { waitUntil: "networkidle" });
  await page2.fill("#name", "Retry E2E");
  await page2.fill("#email", email2);
  await page2.fill("#password", "testpass123");
  await page2.getByRole("button", { name: "Create account" }).click();
  await page2.waitForURL(/\/dashboard\/projects/, { timeout: 30_000 });
  const token2 = await page2.evaluate(() =>
    JSON.parse(localStorage.getItem("viralcut-auth")).state.token
  );
  const listProjects2 = () =>
    fetch(`${API}/api/v1/projects`, {
      headers: { Authorization: `Bearer ${token2}` },
    }).then((r) => r.json());

  await page2.goto(`${BASE}/dashboard/projects/new`, { waitUntil: "networkidle" });
  // Break only the multipart start call so creation succeeds and upload fails.
  await page2.route("**/source-videos/uploads/start", (route) => route.abort("failed"));
  await page2.fill("#title", "Retry flow project");
  await page2.setInputFiles("input[type=file]", videoPath);
  await page2.getByRole("button", { name: /Create project & upload video/ }).click();

  await page2.getByText(/Video upload failed/).waitFor({ state: "visible", timeout: 90_000 });
  check("Test 9: upload failure is surfaced, not silent", true);

  const kept = await page2.getByText(/Your project was created and saved/).isVisible();
  check("Test 9: message distinguishes created-project from failed upload", kept);

  const before = await listProjects2();

  // Retry with the network restored -- must reuse the existing project.
  await page2.unroute("**/source-videos/uploads/start");
  await page2.getByRole("button", { name: /Retry upload/ }).click();
  await page2.waitForURL(/\/dashboard\/projects\/[0-9a-f-]{36}$/, { timeout: 60_000 });

  const after = await listProjects2();
  check(
    "Test 10: retry after failed upload did NOT create a second project",
    after.length === before.length,
    `before=${before.length} after=${after.length}`
  );

  // --- Test 11: refresh mid-flow creates no duplicate ----------------------
  const countBeforeRefresh = after.length;
  await page2.goto(`${BASE}/dashboard/projects/new`, { waitUntil: "networkidle" });
  await page2.fill("#title", "Refresh test");
  await page2.setInputFiles("input[type=file]", videoPath);
  await page2.reload({ waitUntil: "networkidle" });
  const countAfterRefresh = (await listProjects2()).length;
  check(
    "Test 11: refreshing before submit creates no project",
    countAfterRefresh === countBeforeRefresh,
    `before=${countBeforeRefresh} after=${countAfterRefresh}`
  );
} catch (err) {
  console.log(`  FAIL  unexpected error -- ${err.message}`);
  failed++;
} finally {
  await browser.close();
}

console.log(`\n${passed} passed, ${failed} failed`);
process.exit(failed === 0 ? 0 : 1);
