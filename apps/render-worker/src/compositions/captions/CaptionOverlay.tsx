import React from "react";
import { AbsoluteFill, Sequence, useVideoConfig } from "remotion";
import { z } from "zod";
import { SubtitleSchema } from "@viralcut/edit-plan-schema";

export const captionOverlayPropsSchema = z.object({
  subtitles: z.array(SubtitleSchema),
});

export type CaptionOverlayProps = z.infer<typeof captionOverlayPropsSchema>;

// Hormozi style (packages/style-presets/hormozi.json): bold, animated
// captions on every spoken word, 1-3 key words per sentence highlighted in
// a contrasting color.
const EMPHASIS_COLOR = "#FFE600";
const BASE_COLOR = "#FFFFFF";

// Fixed-size overlay only -- deliberately has no video layer of its own so
// it can sit on top of ZoomableVideo (compositions/zooms/ZoomableVideo.tsx)
// without the zoom's scale transform blowing up the caption text too.
export const CaptionOverlay: React.FC<CaptionOverlayProps> = ({ subtitles }) => {
  const { fps } = useVideoConfig();

  return (
    <>
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
    </>
  );
};
