import React from "react";
import { AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";

interface HookTextProps {
  text: string;
  durationMs: number;
  isShort: boolean;
}

export const HookText: React.FC<HookTextProps> = ({ text, durationMs, isShort }) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();

  const fontSize = isShort ? 96 : 108;
  const exitStartFrame = durationInFrames - Math.round(0.3 * fps);

  // Exit: scale shrinks to 0.8 + opacity fades over last 0.3s
  const exitProgress = interpolate(frame, [exitStartFrame, durationInFrames], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const exitScale = interpolate(exitProgress, [0, 1], [1.0, 0.8]);
  const exitOpacity = interpolate(exitProgress, [0, 1], [1.0, 0.0]);

  // Background pill fade-in (appears slightly before text for visual foundation)
  const bgOpacity = interpolate(frame, [0, Math.round(fps * 0.15)], [0, 0.85], {
    extrapolateRight: "clamp",
  });

  // Split into words so we can wrap between words (not mid-word)
  const words = text.split(" ");
  let charIndex = 0;

  return (
    <AbsoluteFill style={{ backgroundColor: "transparent" }}>
      {/* Dark background pill -- centered on screen */}
      <div
        style={{
          position: "absolute",
          top: "33%",
          left: "5%",
          right: "5%",
          display: "flex",
          justifyContent: "center",
          opacity: bgOpacity * exitOpacity,
          transform: `scale(${exitScale})`,
        }}
      >
        <div
          style={{
            backgroundColor: "rgba(0, 0, 0, 0.75)",
            borderRadius: 20,
            padding: "24px 36px",
            maxWidth: "95%",
            textAlign: "center",
          }}
        >
          {/* Hook text: word-wrapped, per-character stagger within each word */}
          {words.map((word, wordIdx) => {
            const wordChars = word.split("");
            const wordStartIndex = charIndex;
            charIndex += word.length + 1; // +1 for the space

            return (
              <span key={`word-${wordIdx}`} style={{ display: "inline-block", whiteSpace: "nowrap" }}>
                {wordChars.map((char, ci) => {
                  const globalIndex = wordStartIndex + ci;
                  const charFrame = Math.max(0, frame - globalIndex);

                  const charSpring = spring({
                    frame: charFrame,
                    fps,
                    config: { mass: 0.5, damping: 12, stiffness: 150 },
                    durationInFrames: Math.round(0.3 * fps),
                  });

                  const charTranslateY = interpolate(charSpring, [0, 1], [-30, 0]);
                  const charOpacity = interpolate(charSpring, [0, 0.1], [0, 1], {
                    extrapolateRight: "clamp",
                  });
                  const charScale = interpolate(charSpring, [0, 1], [0.8, 1.0]);

                  return (
                    <span
                      key={`c-${globalIndex}`}
                      style={{
                        color: "#FFD700",
                        fontSize,
                        fontFamily: "Impact, 'Arial Black', sans-serif",
                        fontWeight: 900,
                        WebkitTextStroke: "4px black",
                        paintOrder: "stroke fill",
                        display: "inline-block",
                        transform: `translateY(${charTranslateY}px) scale(${charScale})`,
                        opacity: charOpacity,
                        textShadow: "0 4px 12px rgba(0, 0, 0, 0.6)",
                      }}
                    >
                      {char}
                    </span>
                  );
                })}
                {/* Space between words */}
                {wordIdx < words.length - 1 && (
                  <span style={{ display: "inline-block", width: "0.3em" }}>{" "}</span>
                )}
              </span>
            );
          })}
        </div>
      </div>
    </AbsoluteFill>
  );
};
