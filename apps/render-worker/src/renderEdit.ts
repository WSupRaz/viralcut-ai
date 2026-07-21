import path from "node:path";
import { fileURLToPath } from "node:url";
import { bundle } from "@remotion/bundler";
import { getVideoMetadata, renderMedia, selectComposition } from "@remotion/renderer";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

export interface RenderEditArgs {
  inputPath: string;
  outputPath: string;
  subtitles: unknown[];
  zooms: unknown[];
}

// Shared by both the CLI entrypoint (render.ts) and the HTTP service
// (server.ts) so there's exactly one implementation of "run the Edit
// composition", not two that could drift.
export async function renderEditVideo({
  inputPath,
  outputPath,
  subtitles,
  zooms,
}: RenderEditArgs): Promise<void> {
  const input = path.resolve(inputPath);
  const output = path.resolve(outputPath);

  const videoMetadata = await getVideoMetadata(input);

  // Remotion's asset pipeline only serves http(s) URLs, not raw local file
  // paths -- serve the input video's own directory as the bundle's public
  // dir and reference it by filename via staticFile() in the composition.
  const bundleLocation = await bundle({
    entryPoint: path.join(__dirname, "index.ts"),
    publicDir: path.dirname(input),
  });

  const inputProps = {
    videoSrc: path.basename(input),
    subtitles,
    zooms,
    videoDurationInSeconds: videoMetadata.durationInSeconds,
    videoWidth: videoMetadata.width,
    videoHeight: videoMetadata.height,
    fps: videoMetadata.fps ?? 30,
  };

  const composition = await selectComposition({
    serveUrl: bundleLocation,
    id: "Edit",
    inputProps,
  });

  await renderMedia({
    composition,
    serveUrl: bundleLocation,
    codec: "h264",
    outputLocation: output,
    inputProps,
  });
}
