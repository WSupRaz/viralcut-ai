/**
 * Regression test: a localStorage upload session whose server-side multipart
 * upload no longer exists must not leave an un-resumable "Upload paused" card
 * on screen. Reproduces the reported state -- GET .../uploads/parts answers
 * 409 Conflict, the card claims "0% uploaded", and resume can only dead-end.
 */
import { chromium } from "playwright";
const BASE = process.env.BASE ?? "http://localhost:3000";
let passed = 0, failed = 0;
const check = (n, c, d = "") => (c ? (console.log(`  PASS  ${n}`), passed++) : (console.log(`  FAIL  ${n}${d ? ` -- ${d}` : ""}`), failed++));

const browser = await chromium.launch({ headless: true });
const page = await (await browser.newContext()).newPage();
page.setDefaultTimeout(30_000);

try {
  const email = `stale-resume-${Date.now()}@example.com`;
  await page.goto(`${BASE}/sign-up`, { waitUntil: "networkidle" });
  await page.fill("#name", "Stale Resume");
  await page.fill("#email", email);
  await page.fill("#password", "testpass123");
  await page.getByRole("button", { name: "Create account" }).click();
  await page.waitForURL(/\/dashboard\/projects/, { timeout: 30_000 });

  await page.goto(`${BASE}/dashboard/projects/new`, { waitUntil: "networkidle" });
  await page.fill("#title", "Stale resume project");
  await page.getByRole("button", { name: /^Create project$/ }).click();
  await page.waitForURL(/\/dashboard\/projects\/[0-9a-f-]{36}$/, { timeout: 30_000 });
  const projectId = page.url().split("/").pop();

  // Plant a stale session, exactly as a failed upload would leave behind.
  await page.evaluate((pid) => {
    localStorage.setItem(`viralcut.upload.session.${pid}`, JSON.stringify({
      projectId: pid,
      sourceVideoId: "8dfe4eac-a781-4336-87c0-e588be7a527f",
      uploadId: "gone", r2Key: "raw/x", partSize: 8388608, partCount: 3,
      fileName: "0708.mp4", fileSize: 421500000, fileType: "video/mp4",
      startedAt: Date.now(),
    }));
  }, projectId);

  // Server has no such session -> 409, mirroring the reported response.
  await page.route("**/uploads/parts*", (route) =>
    route.fulfill({ status: 409, contentType: "application/json", body: JSON.stringify({ detail: "upload session expired" }) }));

  await page.reload({ waitUntil: "networkidle" });
  await page.waitForTimeout(2500);

  const cardVisible = await page.getByText(/Upload paused/).isVisible().catch(() => false);
  check("stale resume card is NOT shown", !cardVisible);

  const uploadBtn = await page.getByRole("button", { name: /Upload video/ }).isVisible().catch(() => false);
  check("normal upload control is available instead", uploadBtn);

  const cleared = await page.evaluate((pid) => localStorage.getItem(`viralcut.upload.session.${pid}`), projectId);
  check("stale localStorage session was cleared", cleared === null);
} catch (err) {
  check("unexpected error", false, err.message.split("\n")[0]);
} finally {
  await browser.close();
}
console.log(`\n${passed} passed, ${failed} failed`);
process.exit(failed === 0 ? 0 : 1);
