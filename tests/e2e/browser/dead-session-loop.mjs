/**
 * A dead multipart session must not send the client into a restart loop.
 *
 * The client clears its local session on 409 and starts over; if start hands
 * back the same dead session, that repeats as fast as the network allows and
 * trips the upload-start rate limiter, reporting "Too many requests" instead
 * of the real problem.
 */
import { chromium } from "playwright";
const BASE = process.env.BASE ?? "http://localhost:3000";
let passed = 0, failed = 0;
const check = (n, c, d = "") => (c ? (console.log(`  PASS  ${n}`), passed++) : (console.log(`  FAIL  ${n}${d ? ` -- ${d}` : ""}`), failed++));

const browser = await chromium.launch({ headless: true });
const page = await (await browser.newContext()).newPage();
page.setDefaultTimeout(30_000);

try {
  const email = `deadloop-${Date.now()}@example.com`;
  await page.goto(`${BASE}/sign-up`, { waitUntil: "networkidle" });
  await page.fill("#name", "Dead Loop");
  await page.fill("#email", email);
  await page.fill("#password", "testpass123");
  await page.getByRole("button", { name: "Create account" }).click();
  await page.waitForURL(/\/dashboard\/projects/, { timeout: 30_000 });

  // Every parts lookup reports the session as gone -- the non-self-correcting case.
  await page.route("**/uploads/parts*", (route) =>
    route.fulfill({ status: 409, contentType: "application/json",
                    body: JSON.stringify({ detail: "upload session expired" }) }));

  let startCalls = 0;
  await page.route("**/uploads/start", (route) => { startCalls += 1; route.continue(); });

  await page.goto(`${BASE}/dashboard/projects/new`, { waitUntil: "networkidle" });
  await page.fill("#title", "Dead session loop");
  await page.setInputFiles("input[type=file]", {
    name: "loop.mp4", mimeType: "video/mp4",
    buffer: Buffer.concat([Buffer.from([0, 0, 0, 0x18]), Buffer.from("ftypmp42"), Buffer.alloc(3000)]),
  });
  await page.getByRole("button", { name: /Create project & upload video/ }).click();

  // Let it run well past the point where a loop would be obvious.
  await page.waitForTimeout(20_000);

  check("upload-start was not called in a loop", startCalls <= 3, `called ${startCalls}x`);
  check("well under the 20/min rate-limit budget", startCalls < 20, `called ${startCalls}x`);

  const body = await page.evaluate(() => document.body.innerText);
  check("a real error is shown, not 'Too many requests'",
    !/too many requests/i.test(body), body.slice(0, 200).replace(/\n/g, " "));
} catch (err) {
  check("unexpected error", false, err.message.split("\n")[0]);
} finally {
  await browser.close();
}
console.log(`\n${passed} passed, ${failed} failed`);
process.exit(failed === 0 ? 0 : 1);
