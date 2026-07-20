import React from "react";
import { Composition } from "remotion";
import { CaptionsComposition, captionsPropsSchema } from "./compositions/captions/CaptionsComposition";

export const RemotionRoot: React.FC = () => {
  return (
    <Composition
      id="Captions"
      component={CaptionsComposition}
      schema={captionsPropsSchema}
      defaultProps={{
        videoSrc: "",
        subtitles: [],
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
