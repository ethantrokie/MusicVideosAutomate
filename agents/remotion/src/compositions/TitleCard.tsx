import React from "react";
import { AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";

interface TitleCardProps {
  text: string;
  durationMs: number;
  isShort: boolean;
}

export const TitleCard: React.FC<TitleCardProps> = ({ text, isShort }) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames, height } = useVideoConfig();

  // Smaller than hook: ~3.5% of screen height
  const fontSize = Math.round(height * 0.035);
  const exitStartFrame = durationInFrames - Math.round(0.3 * fps);

  // Delayed entrance: appears 0.4s after hook starts
  const entranceDelay = Math.round(0.4 * fps);
  const entranceSpring = spring({
    frame: Math.max(0, frame - entranceDelay),
    fps,
    config: { mass: 0.5, damping: 15, stiffness: 140 },
    durationInFrames: Math.round(0.3 * fps),
  });
  const entranceOpacity = interpolate(entranceSpring, [0, 0.3], [0, 1], {
    extrapolateRight: "clamp",
  });
  const entranceTranslateY = interpolate(entranceSpring, [0, 1], [10, 0]);

  // Exit
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
          top: "62%",
          left: "10%",
          right: "10%",
          display: "flex",
          justifyContent: "center",
          opacity,
          transform: `translateY(${entranceTranslateY}px)`,
        }}
      >
        <span
          style={{
            color: "rgba(255, 255, 255, 0.9)",
            fontSize,
            fontFamily: "'Inter', 'SF Pro Display', 'Montserrat', system-ui, sans-serif",
            fontWeight: 600,
            textAlign: "center",
            display: "block",
            lineHeight: 1.3,
            textShadow: "0 2px 8px rgba(0, 0, 0, 0.7), 0 0 4px rgba(0, 0, 0, 0.9)",
            letterSpacing: "0.02em",
          }}
        >
          {text}
        </span>
      </div>
    </AbsoluteFill>
  );
};
