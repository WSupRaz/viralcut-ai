/**
 * Browser E2E for the resumable upload flow, driven through the REAL UI.
 *
 *  - signs up a fresh user, creates a project
 *  - starts a large upload with throttled upload bandwidth
 *  - reloads the page mid-upload
 *  - asserts the "Upload paused" resume card appears with progress retained
 *  - re-selects the same file and asserts the upload resumes to completion
 *  - asserts the localStorage session is cleared and the clip row appears
 *
 * Run:  node upload-resume.mjs <path-to-video>
 *
 * Browser selection:
 *  - locally, uses the installed Microsoft Edge:  PW_CHANNEL=msedge (default)
 *  - in CI, install the bundled chromium (`npx playwright install chromium`)
 *    and leave PW_CHANNEL unset
 * Override the app URL with E2E_BASE_URL (default http://localhost:3000).
 */
import { chromium } from "playwright";
import path from "node:path";

const videoPath = process.argv[2];
if (!videoPath) {
  console.error("usage: node upload-resume.mjs <video-file>");
  process.exit(1);
}
const fileName = path.basename(videoPath);

const BASE = process.env.E2E_BASE_URL ?? "http://localhost:3000";
// "msedge" locally (no download); set PW_CHANNEL=chromium in CI to use the
// bundled chromium (any other value is passed through to playwright).
const rawChannel = process.env.PW_CHANNEL ?? "msedge";
const channel = rawChannel && rawChannel !== "chromium" ? rawChannel : undefined;
const UPLOAD_THROUGHPUT = Number(process.env.E2E_UPLOAD_MBPS ?? 30) * 1024 * 1024;

let passed = 0;
let failed = 0;
function ok(name, cond, detail = "") {
  if (cond) {
    passed += 1;
    console.log(`  PASS ${name}`);
  } else {
    failed += 1;
    console.log(`  FAIL ${name}${detail ? `: ${detail}` : ""}`);
  }
}

async function waitFor(fn, { timeout = 120_000, interval = 500 } = {}) {
  const deadline = Date.now() + timeout;
  let last;
  while (Date.now() < deadline) {
    last = await fn();
    if (last) return last;
    await new Promise((r) => setTimeout(r, interval));
  }
  throw new Error(`waitFor timed out; last=${JSON.stringify(last)}`);
}

const browser = await chromium.launch({ channel, headless: true });
try {
  const context = await browser.newContext();
  const page = await context.newPage();

  // ---------- sign up ----------
  await page.goto(`${BASE}/sign-up`, { waitUntil: "networkidle" });
  await page.waitForTimeout(500); // let React hydration settle before filling
  await page.fill("#name", "Browser E2E");
  const email = `browser-${Date.now()}@example.com`;
  await page.fill("#email", email);
  await page.fill("#password", "testpass123");
  await page.getByRole("button", { name: "Create account" }).click();
  await waitFor(() => page.url().includes("/dashboard/projects"));
  ok("signed up and redirected to projects", true);

  // ---------- create project ----------
  await page.waitForLoadState("networkidle");
  // The form lives on a dedicated /dashboard/projects/new page, reached via a
  // "New project" control. Matched role-agnostically: it renders as an anchor
  // (it navigates), but older builds rendered it as a button that revealed an
  // inline form.
  // NOTE: wait for it rather than probing isVisible() — on a cold server the
  // page can still be hydrating when we first look, and the click would be
  // skipped entirely (then #title never appears).
  const newProjectBtn = page
    .locator('a:has-text("New project"), button:has-text("New project")')
    .first();
  try {
    await newProjectBtn.waitFor({ state: "visible", timeout: 10_000 });
    await newProjectBtn.click();
    await page.locator("#title").waitFor({ state: "visible", timeout: 10_000 });
  } catch {
    // Older builds render the form inline — #title should already be present.
  }
  await page.fill("#title", "Browser resumable upload E2E");
  await page.getByRole("button", { name: "Create project" }).click();
  await waitFor(() => /\/dashboard\/projects\/[0-9a-f-]+$/.test(page.url()));
  await page.waitForLoadState("networkidle");
  ok("created project and entered it", true);

  // ---------- throttle upload bandwidth ----------
  const cdp = await context.newCDPSession(page);
  await cdp.send("Network.enable");
  await cdp.send("Network.emulateNetworkConditions", {
    offline: false,
    latency: 40,
    downloadThroughput: 200 * 1024 * 1024,
    uploadThroughput: UPLOAD_THROUGHPUT,
  });

  // ---------- start upload ----------
  await page.setInputFiles("input[type=file]", videoPath);

  // Wait until we've made real progress (>= 20%).
  const progressRe = /(\d+)%/;
  const progressBefore = await waitFor(async () => {
    const text = await page.locator("body").innerText();
    const m = text.match(progressRe);
    return m && Number(m[1]) >= 20 ? Number(m[1]) : null;
  }, { timeout: 90_000 });
  ok(`upload made real progress before reload (${progressBefore}%)`, progressBefore >= 20);

  // ---------- reload mid-upload ----------
  await page.reload({ waitUntil: "domcontentloaded" });
  await page.waitForTimeout(3000);

  await waitFor(() => page.getByText(/Upload paused/).first().isVisible().catch(() => false));
  const pausedText = await page.getByText(/Upload paused/).first().innerText();
  ok("resume card appears after refresh", pausedText.includes("Upload paused"), pausedText);
  ok("resume card names the file", pausedText.includes(fileName), pausedText);
  const pausedPct = await page
    .getByText(/Upload paused/)
    .first()
    .locator("xpath=following-sibling::p[1]")
    .innerText()
    .catch(() => "");
  ok("resume card shows retained progress", /\d+% uploaded/.test(pausedPct), pausedPct);

  // ---------- resume by re-selecting the same file ----------
  await page.setInputFiles("input[type=file]", videoPath);
  await waitFor(async () => {
    const pausedVisible = await page.getByText(/Upload paused/).isVisible().catch(() => false);
    return pausedVisible ? null : true;
  }, { timeout: 30_000 });
  ok("resume restarted the upload (paused card gone)", true);

  // Wait for the clip row to appear (upload completed -> list refetch).
  await waitFor(() => page.getByText(fileName).first().isVisible().catch(() => false), {
    timeout: 180_000,
  });
  ok("upload completed and clip row appears", true);

  // Session must be cleared after completion.
  const session = await page.evaluate(() => localStorage.getItem(`viralcut.upload.session.${window.location.pathname.split("/").pop()}`));
  ok("localStorage session cleared after completion", session === null, session ?? "");

  console.log(`\n${passed} passed, ${failed} failed`);
  if (failed > 0) process.exit(1);
  console.log("BROWSER E2E OK");
} finally {
  await browser.close();
}
