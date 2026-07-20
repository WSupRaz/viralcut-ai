import React from "react";
import { Composition } from "remotion";
import { z } from "zod";
import { EditComposition, editCompositionPropsSchema } from "./compositions/EditComposition";

// calculateMetadata below derives the actual composition duration/fps/
// dimensions from these, rather than hardcoding them -- render.ts fills
// them in from the real input video's probed metadata.
const rootPropsSchema = editCompositionPropsSchema.extend({
  videoDurationInSeconds: z.number(),
  videoWidth: z.number(),
  videoHeight: z.number(),
  fps: z.number(),
});

export const RemotionRoot: React.FC = () => {
  return (
    <Composition
      id="Edit"
      component={EditComposition}
      schema={rootPropsSchema}
      defaultProps={{
        videoSrc: "",
        subtitles: [],
        zooms: [],
        videoDurationInSeconds: 1,
        videoWidth: 1080,
        videoHeight: 1920,
        fps: 30,
      }}
      durationInFrames={30}
      fps={30}
      width={1080}
      height={1920}
      calculateMetadata={async ({ props }) => {
        return {
          durationInFrames: Math.max(1, Math.ceil(props.videoDurationInSeconds * props.fps)),
          fps: props.fps,
          width: props.videoWidth,
          height: props.videoHeight,
        };
      }}
    />
  );
};
