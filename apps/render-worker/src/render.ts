import fs from "node:fs";
import path from "node:path";
import { renderEditVideo } from "./renderEdit";

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
  const subtitles = JSON.parse(fs.readFileSync(path.resolve(args.subtitles), "utf-8"));
  const zooms = args.zooms ? JSON.parse(fs.readFileSync(path.resolve(args.zooms), "utf-8")) : [];

  console.log(`Rendering ${args.input} -> ${args.output}...`);
  await renderEditVideo({
    inputPath: args.input,
    outputPath: args.output,
    subtitles,
    zooms,
  });
  console.log(`Rendered to ${args.output}`);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
