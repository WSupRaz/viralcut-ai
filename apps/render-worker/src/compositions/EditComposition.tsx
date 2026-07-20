import React from "react";
import { AbsoluteFill } from "remotion";
import { z } from "zod";
import { CaptionOverlay, captionOverlayPropsSchema } from "./captions/CaptionOverlay";
import { ZoomableVideo, zoomableVideoPropsSchema } from "./zooms/ZoomableVideo";

export const editCompositionPropsSchema = zoomableVideoPropsSchema.merge(captionOverlayPropsSchema);

export type EditCompositionProps = z.infer<typeof editCompositionPropsSchema>;

// The zoom-transformed video and the caption overlay must render in a single
// pass: captions have to stay fixed-size on top of a video that's being
// scaled, which isn't possible if they were two independently-rendered
// outputs layered afterward (see Task 12 notes in the roadmap/commit).
export const EditComposition: React.FC<EditCompositionProps> = ({ videoSrc, zooms, subtitles }) => {
  return (
    <AbsoluteFill style={{ backgroundColor: "black" }}>
      <ZoomableVideo videoSrc={videoSrc} zooms={zooms} />
      <CaptionOverlay subtitles={subtitles} />
    </AbsoluteFill>
  );
};
