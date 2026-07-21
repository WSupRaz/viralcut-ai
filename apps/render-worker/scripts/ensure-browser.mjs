// Pre-downloads Remotion's headless Chromium at image build time instead of
// on the first production render -- keeps that first request from being
// slow (or failing outright if the runtime environment's egress is flaky).
import { ensureBrowser } from "@remotion/renderer";

await ensureBrowser();
console.log("Chromium ready.");
