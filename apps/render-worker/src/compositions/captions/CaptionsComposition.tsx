import React from "react";
import { AbsoluteFill, OffthreadVideo, Sequence, staticFile, useVideoConfig } from "remotion";
import { z } from "zod";
import { SubtitleSchema } from "@viralcut/edit-plan-schema";

export const captionsPropsSchema = z.object({
  // Filename only, relative to the bundle's publicDir -- resolved via
  // staticFile() below. Remotion's asset pipeline only serves http(s) URLs,
  // not raw local file paths, so render.ts sets publicDir to the input
  // video's directory and passes just the basename here.
  videoSrc: z.string(),
  subtitles: z.array(SubtitleSchema),
  videoDurationInSeconds: z.number(),
  videoWidth: z.number(),
  videoHeight: z.number(),
  fps: z.number(),
});

export type CaptionsProps = z.infer<typeof captionsPropsSchema>;

// Hormozi style (packages/style-presets/hormozi.json): bold, animated
// captions on every spoken word, 1-3 key words per sentence highlighted in
// a contrasting color.
const EMPHASIS_COLOR = "#FFE600";
const BASE_COLOR = "#FFFFFF";

export const CaptionsComposition: React.FC<CaptionsProps> = ({ videoSrc, subtitles }) => {
  const { fps } = useVideoConfig();

  return (
    <AbsoluteFill style={{ backgroundColor: "black" }}>
      <OffthreadVideo src={staticFile(videoSrc)} />
      {subtitles.map((sub, i) => {
        const fromFrame = Math.round(sub.start * fps);
        const toFrame = Math.round(sub.end * fps);
        const durationInFrames = Math.max(1, toFrame - fromFrame);
        const isEmphasis = sub.emphasis_words.length > 0;

        return (
          <Sequence key={i} from={fromFrame} durationInFrames={durationInFrames}>
            <AbsoluteFill
              style={{ justifyContent: "flex-end", alignItems: "center", paddingBottom: "15%" }}
            >
              <div
                style={{
                  fontFamily: "Arial, Helvetica, sans-serif",
                  fontWeight: 900,
                  fontSize: 90,
                  color: isEmphasis ? EMPHASIS_COLOR : BASE_COLOR,
                  WebkitTextStroke: "4px black",
                  textTransform: "uppercase",
                  textAlign: "center",
                  padding: "0 40px",
                }}
              >
                {sub.text}
              </div>
            </AbsoluteFill>
          </Sequence>
        );
      })}
    </AbsoluteFill>
  );
};
