import React from "react";
import { AbsoluteFill, OffthreadVideo, interpolate, staticFile, useCurrentFrame, useVideoConfig } from "remotion";
import { z } from "zod";
import { ZoomSchema } from "@viralcut/edit-plan-schema";

export const zoomableVideoPropsSchema = z.object({
  // Filename only, relative to the bundle's publicDir -- resolved via
  // staticFile() below, same convention as CaptionOverlay's video source.
  videoSrc: z.string(),
  zooms: z.array(ZoomSchema),
});

export type ZoomableVideoProps = z.infer<typeof zoomableVideoPropsSchema>;

// Quick ease in/out around each zoom window so the scale change reads as a
// "punch" (Hormozi style: "Punch zoom... hold the zoom through the phrase,
// then release") rather than an instant snap-cut in scale.
const ZOOM_EASE_SECONDS = 0.15;

export function useZoomScale(zooms: z.infer<typeof ZoomSchema>[]): number {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = frame / fps;

  for (const zoom of zooms) {
    if (t < zoom.start - ZOOM_EASE_SECONDS || t > zoom.end + ZOOM_EASE_SECONDS) {
      continue;
    }
    if (t < zoom.start) {
      return interpolate(t, [zoom.start - ZOOM_EASE_SECONDS, zoom.start], [1, zoom.scale], {
        extrapolateLeft: "clamp",
        extrapolateRight: "clamp",
      });
    }
    if (t > zoom.end) {
      return interpolate(t, [zoom.end, zoom.end + ZOOM_EASE_SECONDS], [zoom.scale, 1], {
        extrapolateLeft: "clamp",
        extrapolateRight: "clamp",
      });
    }
    return zoom.scale;
  }
  return 1;
}

// Owns the video layer and its scale transform only -- captions render as a
// separate, unscaled overlay on top (see compositions/EditComposition.tsx),
// so the punch zoom affects the footage without blowing up caption text.
export const ZoomableVideo: React.FC<ZoomableVideoProps> = ({ videoSrc, zooms }) => {
  const scale = useZoomScale(zooms);

  return (
    <AbsoluteFill style={{ transform: `scale(${scale})`, transformOrigin: "50% 50%" }}>
      <OffthreadVideo src={staticFile(videoSrc)} />
    </AbsoluteFill>
  );
};
