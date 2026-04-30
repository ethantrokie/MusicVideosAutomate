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

  const fontSize = isShort ? 64 : 72;
  const exitStartFrame = durationInFrames - Math.round(0.3 * fps);

  // Entrance: spring fade+scale (0.9 -> 1.0) over 0.4s
  const entranceSpring = spring({
    frame,
    fps,
    config: {
      mass: 0.6,
      damping: 15,
      stiffness: 100,
    },
    durationInFrames: Math.round(0.4 * fps),
  });
  const entranceScale = interpolate(entranceSpring, [0, 1], [0.9, 1.0]);
  const entranceOpacity = interpolate(entranceSpring, [0, 0.15], [0, 1], {
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
          top: "25%",
          left: 0,
          right: 0,
          textAlign: "center",
          paddingLeft: 40,
          paddingRight: 40,
          opacity,
          transform: `scale(${entranceScale})`,
        }}
      >
        <span
          style={{
            color: "#FFFFFF",
            fontSize,
            fontFamily: "Impact, Arial Black, sans-serif",
            fontWeight: 900,
            WebkitTextStroke: "4px black",
            paintOrder: "stroke fill",
            display: "inline-block",
          }}
        >
          {text}
        </span>
      </div>
    </AbsoluteFill>
  );
};
