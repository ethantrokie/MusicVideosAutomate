import React from "react";
import { AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";

interface TitleCardProps {
  text: string;
  durationMs: number;
  isShort: boolean;
}

export const TitleCard: React.FC<TitleCardProps> = ({ text, isShort }) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();

  const fontSize = isShort ? 52 : 60;
  const exitStartFrame = durationInFrames - Math.round(0.3 * fps);

  // Entrance: spring fade+scale over 0.4s, delayed 0.3s to appear after hook
  const entranceDelay = Math.round(0.3 * fps);
  const entranceSpring = spring({
    frame: Math.max(0, frame - entranceDelay),
    fps,
    config: {
      mass: 0.5,
      damping: 14,
      stiffness: 120,
    },
    durationInFrames: Math.round(0.35 * fps),
  });
  const entranceScale = interpolate(entranceSpring, [0, 1], [0.85, 1.0]);
  const entranceOpacity = interpolate(entranceSpring, [0, 0.2], [0, 1], {
    extrapolateRight: "clamp",
  });

  // Exit: opacity fade over last 0.3s
  const exitOpacity = interpolate(frame, [exitStartFrame, durationInFrames], [1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  const opacity = Math.min(entranceOpacity, exitOpacity);

  return (
    <AbsoluteFill style={{ backgroundColor: "transparent" }}>
      <div
        style={{
          position: "absolute",
          top: "52%",
          left: "8%",
          right: "8%",
          display: "flex",
          justifyContent: "center",
          opacity,
          transform: `scale(${entranceScale})`,
        }}
      >
        <div
          style={{
            backgroundColor: "rgba(0, 0, 0, 0.6)",
            borderRadius: 14,
            padding: "14px 28px",
            maxWidth: "95%",
          }}
        >
          <span
            style={{
              color: "#FFFFFF",
              fontSize,
              fontFamily: "'SF Pro Display', 'Inter', system-ui, -apple-system, sans-serif",
              fontWeight: 700,
              textAlign: "center",
              display: "block",
              lineHeight: 1.2,
              textShadow: "0 2px 8px rgba(0, 0, 0, 0.5)",
            }}
          >
            {text}
          </span>
        </div>
      </div>
    </AbsoluteFill>
  );
};
