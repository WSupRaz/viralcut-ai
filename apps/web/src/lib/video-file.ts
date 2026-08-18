/** Client-side video file rules, shared by the create-project flow and the
 *  project detail page so the two can't drift apart.
 *
 *  These checks are a fast-feedback convenience only -- the API re-validates
 *  content type, part sizes, total size and the container's ftyp header when
 *  an upload is completed, and that remains authoritative. */

import { formatBytes } from "@/lib/upload-client";

export const ACCEPTED_VIDEO_TYPES = ["video/mp4", "video/quicktime", "video/x-m4v"];

/** For the file input's `accept`. Extensions are included alongside the MIME
 *  types because some browsers report an empty `type` for .mov/.m4v. */
export const ACCEPTED_VIDEO_ACCEPT = [...ACCEPTED_VIDEO_TYPES, ".mp4", ".mov", ".m4v"].join(",");

const ACCEPTED_EXTENSIONS = [".mp4", ".mov", ".m4v"];

export function isAcceptedVideo(file: File): boolean {
  if (ACCEPTED_VIDEO_TYPES.includes(file.type)) return true;
  // Drag-and-drop and some OS/browser combinations hand over a file with no
  // MIME type at all; fall back to the extension rather than rejecting a file
  // the server would have accepted.
  if (file.type === "") {
    const name = file.name.toLowerCase();
    return ACCEPTED_EXTENSIONS.some((ext) => name.endsWith(ext));
  }
  return false;
}

/** Returns an error message, or null when the file is acceptable. */
export function validateVideoFile(file: File, maxUploadBytes: number): string | null {
  if (!isAcceptedVideo(file)) {
    return `${file.name} isn't a supported format. Upload an mp4, mov, or m4v file.`;
  }
  if (file.size === 0) {
    return `${file.name} is empty.`;
  }
  if (file.size > maxUploadBytes) {
    return `${file.name} is ${formatBytes(file.size)}, over your plan's ${formatBytes(
      maxUploadBytes
    )} upload limit. Upgrade for a higher limit, or split the file.`;
  }
  return null;
}
