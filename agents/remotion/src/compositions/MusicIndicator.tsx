import React from "react";
import { useCurrentFrame, useVideoConfig, interpolate } from "remotion";

interface MusicIndicatorProps {
  durationMs: number;
}

export const MusicIndicator: React.FC<MusicIndicatorProps> = ({ durationMs }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const totalFrames = Math.round((durationMs / 1000) * fps);

  const fadeInFrames = Math.round(fps * 0.5);
  const fadeOutStart = totalFrames - Math.round(fps * 0.5);
  const opacity = interpolate(
    frame,
    [0, fadeInFrames, fadeOutStart, totalFrames],
    [0, 0.7, 0.7, 0],
    { extrapolateRight: "clamp" }
  );

  const barConfigs = [
    { speed: 1.8, maxHeight: 60 },
    { speed: 2.5, maxHeight: 80 },
    { speed: 1.3, maxHeight: 50 },
    { speed: 2.1, maxHeight: 70 },
  ];

  return (
    <div
      style={{
        position: "absolute",
        bottom: "8%",
        left: "4%",
        display: "flex",
        alignItems: "flex-end",
        gap: 4,
        opacity,
      }}
    >
      {barConfigs.map((bar, i) => {
        const height = interpolate(
          Math.sin((frame / fps) * bar.speed * Math.PI),
          [-1, 1],
          [15, bar.maxHeight]
        );
        return (
          <div
            key={i}
            style={{
              width: 6,
              height: `${height}%`,
              backgroundColor: "white",
              borderRadius: 3,
              minHeight: 8,
              maxHeight: 40,
            }}
          />
        );
      })}
    </div>
  );
};
