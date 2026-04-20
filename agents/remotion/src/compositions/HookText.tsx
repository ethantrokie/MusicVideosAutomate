import React from "react";
import { AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";

interface HookTextProps {
  text: string;
  durationMs: number;
  isShort: boolean;
  animate: boolean;
}

export const HookText: React.FC<HookTextProps> = ({ text, durationMs, isShort, animate }) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();

  const fontSize = isShort ? 72 : 80;
  const exitStartFrame = durationInFrames - Math.round(0.3 * fps);

  // Exit: scale shrinks to 0.8 + opacity fades over last 0.3s
  const exitProgress = interpolate(frame, [exitStartFrame, durationInFrames], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const exitScale = interpolate(exitProgress, [0, 1], [1.0, 0.8]);
  const exitOpacity = interpolate(exitProgress, [0, 1], [1.0, 0.0]);

  const characters = text.split("");

  if (!animate) {
    // Static instant appearance, smooth crossfade exit
    return (
      <AbsoluteFill style={{ backgroundColor: "transparent" }}>
        <div
          style={{
            position: "absolute",
            top: "12%",
            left: 0,
            right: 0,
            textAlign: "center",
            paddingLeft: 40,
            paddingRight: 40,
            opacity: exitOpacity,
            transform: `scale(${exitScale})`,
          }}
        >
          <span
            style={{
              color: "#FFD700",
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
  }

  // Animated: per-character stagger entrance from -40px above
  return (
    <AbsoluteFill style={{ backgroundColor: "transparent" }}>
      <div
        style={{
          position: "absolute",
          top: "12%",
          left: 0,
          right: 0,
          textAlign: "center",
          paddingLeft: 40,
          paddingRight: 40,
          opacity: exitOpacity,
          transform: `scale(${exitScale})`,
          display: "flex",
          justifyContent: "center",
          flexWrap: "wrap",
        }}
      >
        {characters.map((char, index) => {
          const charDelayFrames = index; // 1-frame stagger
          const charFrame = Math.max(0, frame - charDelayFrames);

          const charSpring = spring({
            frame: charFrame,
            fps,
            config: {
              mass: 0.5,
              damping: 12,
              stiffness: 150,
            },
            durationInFrames: Math.round(0.3 * fps),
          });

          const charTranslateY = interpolate(charSpring, [0, 1], [-40, 0]);
          const charOpacity = interpolate(charSpring, [0, 0.1], [0, 1], {
            extrapolateRight: "clamp",
          });

          return (
            <span
              key={`char-${index}`}
              style={{
                color: "#FFD700",
                fontSize,
                fontFamily: "Impact, Arial Black, sans-serif",
                fontWeight: 900,
                WebkitTextStroke: "4px black",
                paintOrder: "stroke fill",
                display: "inline-block",
                transform: `translateY(${charTranslateY}px)`,
                opacity: charOpacity,
                whiteSpace: char === " " ? "pre" : "normal",
              }}
            >
              {char}
            </span>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};
