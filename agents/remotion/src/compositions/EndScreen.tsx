import React from "react";
import { AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";

interface EndScreenProps {
  channelName: string;
  isShort: boolean;
  durationMs: number;
}

export const EndScreen: React.FC<EndScreenProps> = ({ channelName, isShort }) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();

  const ctaFontSize = isShort ? 50 : 55;
  const channelFontSize = isShort ? 40 : 45;

  // Background: black fades to 0.6 opacity over 0.5s
  const bgOpacity = interpolate(frame, [0, Math.round(0.5 * fps)], [0, 0.6], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  // CTA: spring entrance delayed 0.3s (scale 0.5 -> 1.0)
  const ctaDelayFrames = Math.round(0.3 * fps);
  const ctaSpring = spring({
    frame: Math.max(0, frame - ctaDelayFrames),
    fps,
    config: {
      mass: 0.6,
      damping: 10,
      stiffness: 120,
    },
  });
  const ctaScale = interpolate(ctaSpring, [0, 1], [0.5, 1.0]);
  const ctaOpacity = interpolate(ctaSpring, [0, 0.1], [0, 1], {
    extrapolateRight: "clamp",
  });

  // Channel name: typewriter effect delayed 0.6s, 2 frames per character
  const channelDelayFrames = Math.round(0.6 * fps);
  const framesPerChar = 2;
  const framesSinceChannelStart = Math.max(0, frame - channelDelayFrames);
  const visibleCharCount = Math.floor(framesSinceChannelStart / framesPerChar);
  const visibleText = channelName.slice(0, visibleCharCount);
  const isTyping = visibleCharCount < channelName.length;

  // Blinking cursor: blinks every 15 frames (2Hz at 30fps)
  const cursorVisible = Math.floor(framesSinceChannelStart / 15) % 2 === 0;
  const showCursor = isTyping || (visibleCharCount >= channelName.length && cursorVisible);

  const channelOpacity = interpolate(
    frame,
    [channelDelayFrames, channelDelayFrames + 5],
    [0, 1],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );

  // Subscribe icon (shorts only): spring bounce delayed 0.9s (scale 0 -> 1.1)
  const iconDelayFrames = Math.round(0.9 * fps);
  const iconSpring = spring({
    frame: Math.max(0, frame - iconDelayFrames),
    fps,
    config: {
      mass: 0.4,
      damping: 8,
      stiffness: 200,
    },
  });
  const iconScale = interpolate(iconSpring, [0, 1], [0, 1.1]);
  const iconOpacity = interpolate(iconSpring, [0, 0.1], [0, 1], {
    extrapolateRight: "clamp",
  });

  // Layout positions
  const ctaTop = isShort ? "35%" : "40%";
  const channelTop = isShort ? "50%" : "55%";
  const iconTop = "68%";

  return (
    <AbsoluteFill style={{ backgroundColor: "transparent" }}>
      {/* Dark background overlay */}
      <AbsoluteFill
        style={{
          backgroundColor: `rgba(0, 0, 0, ${bgOpacity})`,
        }}
      />

      {/* CTA "Like & Subscribe!" */}
      <div
        style={{
          position: "absolute",
          top: ctaTop,
          left: 0,
          right: 0,
          textAlign: "center",
          opacity: ctaOpacity,
          transform: `scale(${ctaScale})`,
        }}
      >
        <span
          style={{
            color: "#FFD700",
            fontSize: ctaFontSize,
            fontFamily: "Impact, Arial Black, sans-serif",
            fontWeight: 900,
            WebkitTextStroke: "3px black",
            paintOrder: "stroke fill",
            display: "inline-block",
          }}
        >
          Like &amp; Subscribe!
        </span>
      </div>

      {/* Channel name with typewriter effect */}
      <div
        style={{
          position: "absolute",
          top: channelTop,
          left: 0,
          right: 0,
          textAlign: "center",
          opacity: channelOpacity,
        }}
      >
        <span
          style={{
            color: "#FFFFFF",
            fontSize: channelFontSize,
            fontFamily: "SF Pro Display, -apple-system, system-ui, sans-serif",
            fontWeight: 600,
            display: "inline-block",
          }}
        >
          {visibleText}
          {showCursor && (
            <span
              style={{
                display: "inline-block",
                width: 3,
                height: channelFontSize,
                backgroundColor: "#FFFFFF",
                marginLeft: 2,
                verticalAlign: "text-bottom",
              }}
            />
          )}
        </span>
      </div>

      {/* Subscribe icon emoji (shorts only) */}
      {isShort && (
        <div
          style={{
            position: "absolute",
            top: iconTop,
            left: 0,
            right: 0,
            textAlign: "center",
            opacity: iconOpacity,
            transform: `scale(${iconScale})`,
          }}
        >
          <span
            style={{
              fontSize: 64,
              display: "inline-block",
            }}
          >
            👆
          </span>
        </div>
      )}
    </AbsoluteFill>
  );
};
