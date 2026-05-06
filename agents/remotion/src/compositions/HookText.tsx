import React from "react";
import { AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";

interface HookTextProps {
  text: string;
  durationMs: number;
  isShort: boolean;
}

export const HookText: React.FC<HookTextProps> = ({ text, durationMs, isShort }) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames, height } = useVideoConfig();

  // Dynamic font size: ~7.5% of screen height
  const fontSize = Math.round(height * 0.075);
  const exitStartFrame = durationInFrames - Math.round(0.3 * fps);

  // Exit animation
  const exitProgress = interpolate(frame, [exitStartFrame, durationInFrames], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const exitScale = interpolate(exitProgress, [0, 1], [1.0, 0.85]);
  const exitOpacity = interpolate(exitProgress, [0, 1], [1.0, 0.0]);

  // ALL CAPS for hook text
  const displayText = text.toUpperCase();
  const words = displayText.split(" ");

  return (
    <AbsoluteFill style={{ backgroundColor: "transparent" }}>
      <div
        style={{
          position: "absolute",
          top: "30%",
          left: "6%",
          right: "6%",
          display: "flex",
          justifyContent: "center",
          opacity: exitOpacity,
          transform: `scale(${exitScale})`,
        }}
      >
        {/* Subtle dark backdrop pill */}
        <div
          style={{
            backgroundColor: "rgba(0, 0, 0, 0.35)",
            borderRadius: 16,
            padding: "20px 32px",
            maxWidth: "95%",
            textAlign: "center",
            lineHeight: 1.15,
          }}
        >
          {/* Word-by-word stagger animation */}
          {words.map((word, wordIdx) => {
            // 3-frame delay per word
            const wordDelay = wordIdx * 3;
            const wordFrame = Math.max(0, frame - wordDelay);

            const wordSpring = spring({
              frame: wordFrame,
              fps,
              config: { mass: 0.6, damping: 14, stiffness: 220 },
              durationInFrames: Math.round(0.2 * fps),
            });

            const wordTranslateY = interpolate(wordSpring, [0, 1], [15, 0]);
            const wordOpacity = interpolate(wordSpring, [0, 0.3], [0, 1], {
              extrapolateRight: "clamp",
            });
            const wordScale = interpolate(wordSpring, [0, 1], [0.9, 1.0]);

            return (
              <React.Fragment key={`word-${wordIdx}`}>
                <span
                  style={{
                    display: "inline-block",
                    color: "#FFFFFF",
                    fontSize,
                    fontFamily: "'Bebas Neue', 'Montserrat', 'Oswald', Impact, sans-serif",
                    fontWeight: 800,
                    letterSpacing: "0.04em",
                    WebkitTextStroke: `${Math.round(fontSize * 0.04)}px rgba(0, 0, 0, 0.9)`,
                    paintOrder: "stroke fill",
                    textShadow: "0 4px 12px rgba(0, 0, 0, 0.5), 0 0 30px rgba(255, 215, 0, 0.15)",
                    transform: `translateY(${wordTranslateY}px) scale(${wordScale})`,
                    opacity: wordOpacity,
                    whiteSpace: "nowrap",
                  }}
                >
                  {word}
                </span>
                {wordIdx < words.length - 1 && (
                  <span style={{ display: "inline-block", width: "0.3em", fontSize }}>{"\u00A0"}</span>
                )}
              </React.Fragment>
            );
          })}
        </div>
      </div>
    </AbsoluteFill>
  );
};
