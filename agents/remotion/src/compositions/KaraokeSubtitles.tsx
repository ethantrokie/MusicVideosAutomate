import React from "react";
import { AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import type { PhraseGroup, WordTiming } from "../types";

interface KaraokeSubtitlesProps {
  phrases: PhraseGroup[];
  isShort: boolean;
}

interface WordStyle {
  color: string;
  transform: string;
  textShadow: string;
}

const getWordStyle = (
  word: WordTiming,
  currentMs: number,
  frame: number,
  fps: number
): WordStyle => {
  const isActive = currentMs >= word.startMs && currentMs <= word.endMs;
  const isPast = currentMs > word.endMs;

  if (isActive) {
    const activationFrame = Math.round((word.startMs / 1000) * fps);
    const framesSinceActive = Math.max(0, frame - activationFrame);

    const liftSpring = spring({
      frame: framesSinceActive,
      fps,
      config: {
        mass: 0.4,
        damping: 10,
        stiffness: 200,
      },
    });
    const translateY = interpolate(liftSpring, [0, 1], [0, -4]);

    return {
      color: "#FFD700",
      transform: `translateY(${translateY}px)`,
      textShadow: "0 0 12px rgba(255, 215, 0, 0.8), 0 0 24px rgba(255, 215, 0, 0.4)",
    };
  }

  if (isPast) {
    return {
      color: "#FFFFFF",
      transform: "scale(1)",
      textShadow: "none",
    };
  }

  // Future word
  return {
    color: "rgba(255, 255, 255, 0.6)",
    transform: "scale(1)",
    textShadow: "none",
  };
};

export const KaraokeSubtitles: React.FC<KaraokeSubtitlesProps> = ({ phrases, isShort }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const currentMs = (frame / fps) * 1000;

  const activePhrase = phrases.find(
    (phrase) => currentMs >= phrase.startMs && currentMs <= phrase.endMs
  );

  if (!activePhrase) {
    return null;
  }

  const bottomPosition = isShort ? "25%" : "10%";
  const fontSize = isShort ? 44 : 48;

  return (
    <AbsoluteFill style={{ backgroundColor: "transparent" }}>
      <div
        style={{
          position: "absolute",
          bottom: bottomPosition,
          left: 0,
          right: 0,
          paddingLeft: 40,
          paddingRight: 40,
          display: "flex",
          flexDirection: "row",
          flexWrap: "wrap",
          justifyContent: "center",
          alignItems: "center",
          gap: 8,
        }}
      >
        {activePhrase.words.map((word, index) => {
          const wordStyle = getWordStyle(word, currentMs, frame, fps);
          return (
            <span
              key={`${word.word}-${index}`}
              style={{
                color: wordStyle.color,
                transform: wordStyle.transform,
                textShadow: wordStyle.textShadow,
                fontSize,
                fontFamily: "SF Pro Display, -apple-system, system-ui, Arial, sans-serif",
                fontWeight: 700,
                display: "inline-block",
                transition: "none",
                WebkitTextStroke: "2px rgba(0, 0, 0, 0.8)",
                paintOrder: "stroke fill",
              }}
            >
              {word.word}
            </span>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};
