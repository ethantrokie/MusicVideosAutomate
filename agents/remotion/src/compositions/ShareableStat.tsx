import React from "react";
import { useCurrentFrame, useVideoConfig, interpolate } from "remotion";

interface ShareableStatProps {
  text: string;
  durationMs: number;
}

export const ShareableStat: React.FC<ShareableStatProps> = ({ text, durationMs }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const fadeInFrames = Math.round(fps * 0.3);
  const opacity = interpolate(frame, [0, fadeInFrames], [0, 1], {
    extrapolateRight: "clamp",
  });

  const scale = interpolate(frame, [0, fadeInFrames], [0.95, 1], {
    extrapolateRight: "clamp",
  });

  if (!text) return null;

  return (
    <div
      style={{
        position: "absolute",
        bottom: "15%",
        left: "6%",
        right: "6%",
        display: "flex",
        justifyContent: "center",
        alignItems: "center",
        opacity,
        transform: `scale(${scale})`,
      }}
    >
      <div
        style={{
          backgroundColor: "rgba(0, 0, 0, 0.55)",
          borderRadius: 16,
          padding: "16px 28px",
          maxWidth: "90%",
        }}
      >
        <p
          style={{
            fontFamily: "'Bebas Neue', sans-serif",
            fontSize: "5.5vh",
            fontWeight: 700,
            color: "white",
            textAlign: "center",
            lineHeight: 1.3,
            margin: 0,
            textShadow: "0 2px 8px rgba(0,0,0,0.6)",
            letterSpacing: "0.02em",
            textTransform: "uppercase",
          }}
        >
          {text}
        </p>
      </div>
    </div>
  );
};
