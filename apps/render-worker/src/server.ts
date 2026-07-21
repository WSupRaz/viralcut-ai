import fs from "node:fs";
import http from "node:http";
import os from "node:os";
import path from "node:path";
import { config } from "./config";
import { renderEditVideo } from "./renderEdit";
import { downloadToPath, uploadFromPath } from "./storage";

interface RenderRequestBody {
  inputKey: string;
  outputKey: string;
  subtitles: unknown[];
  zooms: unknown[];
}

function readJsonBody(req: http.IncomingMessage): Promise<unknown> {
  return new Promise((resolve, reject) => {
    let raw = "";
    req.on("data", (chunk) => (raw += chunk));
    req.on("end", () => {
      try {
        resolve(raw ? JSON.parse(raw) : {});
      } catch (err) {
        reject(err);
      }
    });
    req.on("error", reject);
  });
}

function isRenderRequestBody(body: unknown): body is RenderRequestBody {
  if (typeof body !== "object" || body === null) return false;
  const b = body as Record<string, unknown>;
  return (
    typeof b.inputKey === "string" &&
    typeof b.outputKey === "string" &&
    Array.isArray(b.subtitles) &&
    Array.isArray(b.zooms)
  );
}

async function handleRender(req: http.IncomingMessage, res: http.ServerResponse): Promise<void> {
  const body = await readJsonBody(req);
  if (!isRenderRequestBody(body)) {
    res.writeHead(400, { "Content-Type": "application/json" });
    res.end(JSON.stringify({ error: "Expected { inputKey, outputKey, subtitles, zooms }" }));
    return;
  }

  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), "render-"));
  try {
    const inputPath = path.join(tmpDir, "input.mp4");
    const outputPath = path.join(tmpDir, "output.mp4");

    console.log(`[render] downloading ${body.inputKey}`);
    await downloadToPath(body.inputKey, inputPath);

    console.log(`[render] rendering -> ${body.outputKey}`);
    await renderEditVideo({
      inputPath,
      outputPath,
      subtitles: body.subtitles,
      zooms: body.zooms,
    });

    console.log(`[render] uploading ${body.outputKey}`);
    await uploadFromPath(outputPath, body.outputKey);

    res.writeHead(200, { "Content-Type": "application/json" });
    res.end(JSON.stringify({ outputKey: body.outputKey }));
  } catch (err) {
    console.error("[render] failed:", err);
    res.writeHead(500, { "Content-Type": "application/json" });
    res.end(JSON.stringify({ error: err instanceof Error ? err.message : String(err) }));
  } finally {
    fs.rmSync(tmpDir, { recursive: true, force: true });
  }
}

const server = http.createServer((req, res) => {
  if (req.method === "GET" && req.url === "/healthz") {
    res.writeHead(200, { "Content-Type": "application/json" });
    res.end(JSON.stringify({ status: "ok" }));
    return;
  }

  if (req.method === "POST" && req.url === "/render") {
    handleRender(req, res).catch((err) => {
      console.error("[render] unhandled error:", err);
      res.writeHead(500, { "Content-Type": "application/json" });
      res.end(JSON.stringify({ error: "internal error" }));
    });
    return;
  }

  res.writeHead(404, { "Content-Type": "application/json" });
  res.end(JSON.stringify({ error: "not found" }));
});

server.listen(config.port, () => {
  console.log(`render-worker listening on :${config.port}`);
});
