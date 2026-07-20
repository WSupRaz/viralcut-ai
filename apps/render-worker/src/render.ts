import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { bundle } from "@remotion/bundler";
import { getVideoMetadata, renderMedia, selectComposition } from "@remotion/renderer";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

interface Args {
  input: string;
  subtitles: string;
  zooms?: string;
  output: string;
}

function parseArgs(): Args {
  const args = process.argv.slice(2);
  const get = (name: string): string => {
    const prefix = `--${name}=`;
    const found = args.find((a) => a.startsWith(prefix));
    if (!found) throw new Error(`Missing required arg --${name}`);
    return found.slice(prefix.length);
  };
  const getOptional = (name: string): string | undefined => {
    const prefix = `--${name}=`;
    return args.find((a) => a.startsWith(prefix))?.slice(prefix.length);
  };
  return {
    input: get("input"),
    subtitles: get("subtitles"),
    zooms: getOptional("zooms"),
    output: get("output"),
  };
}

async function main() {
  const args = parseArgs();
  const input = path.resolve(args.input);
  const output = path.resolve(args.output);
  const subtitles = JSON.parse(fs.readFileSync(path.resolve(args.subtitles), "utf-8"));
  const zooms = args.zooms ? JSON.parse(fs.readFileSync(path.resolve(args.zooms), "utf-8")) : [];

  console.log(`Probing ${input}...`);
  const videoMetadata = await getVideoMetadata(input);
  console.log("video metadata:", videoMetadata);

  console.log("Bundling Remotion composition...");
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

  console.log("Selecting composition...");
  const composition = await selectComposition({
    serveUrl: bundleLocation,
    id: "Edit",
    inputProps,
  });

  console.log(`Rendering to ${output}...`);
  await renderMedia({
    composition,
    serveUrl: bundleLocation,
    codec: "h264",
    outputLocation: output,
    inputProps,
  });

  console.log(`Rendered to ${output}`);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
