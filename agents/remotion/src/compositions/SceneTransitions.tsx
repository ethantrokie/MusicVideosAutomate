import React from "react";
import { AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import type { ShotBoundary } from "../types";

interface TransitionOverlayProps {
  boundary: ShotBoundary;
}

// Wipe: black semi-transparent bar sweeps left-to-right with gradient
const WipeTransition: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();

  const progress = interpolate(frame, [0, durationInFrames], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  // Bar center position goes from -4% to 104% of width
  const barCenterPercent = interpolate(progress, [0, 1], [-4, 104]);

  return (
    <AbsoluteFill style={{ backgroundColor: "transparent" }}>
      <div
        style={{
          position: "absolute",
          top: 0,
          bottom: 0,
          left: `${barCenterPercent - 4}%`,
          width: "8%",
          background:
            "linear-gradient(to right, transparent, rgba(0,0,0,0.7) 30%, rgba(0,0,0,0.7) 70%, transparent)",
        }}
      />
    </AbsoluteFill>
  );
};

// Iris: circle expands from center then contracts (30% of max radius)
const IrisTransition: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();

  const halfFrames = Math.floor(durationInFrames / 2);

  // Expand phase (0 -> half), contract phase (half -> end)
  const expandSpring = spring({
    frame,
    fps,
    config: { mass: 0.6, damping: 12, stiffness: 100 },
    durationInFrames: halfFrames,
  });
  const contractSpring = spring({
    frame: Math.max(0, frame - halfFrames),
    fps,
    config: { mass: 0.6, damping: 12, stiffness: 100 },
    durationInFrames: halfFrames,
  });

  // Max radius is 30% of viewport (subtle)
  const maxRadiusVw = 30;
  const expandRadius = interpolate(expandSpring, [0, 1], [0, maxRadiusVw]);
  const contractRadius = interpolate(contractSpring, [0, 1], [maxRadiusVw, 0]);
  const radius = frame <= halfFrames ? expandRadius : contractRadius;

  return (
    <AbsoluteFill style={{ backgroundColor: "transparent" }}>
      <div
        style={{
          position: "absolute",
          top: "50%",
          left: "50%",
          width: `${radius * 2}vw`,
          height: `${radius * 2}vw`,
          transform: "translate(-50%, -50%)",
          borderRadius: "50%",
          border: "3px solid rgba(255, 255, 255, 0.8)",
          boxShadow: "0 0 20px rgba(255, 255, 255, 0.4)",
          pointerEvents: "none",
        }}
      />
    </AbsoluteFill>
  );
};

// Fade: black overlay fades to 0.3 opacity then back to 0
const FadeTransition: React.FC = () => {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();

  const halfFrames = Math.floor(durationInFrames / 2);

  const opacity = interpolate(
    frame,
    [0, halfFrames, durationInFrames],
    [0, 0.3, 0],
    {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
    }
  );

  return (
    <AbsoluteFill
      style={{
        backgroundColor: `rgba(0, 0, 0, ${opacity})`,
      }}
    />
  );
};

export const TransitionOverlay: React.FC<TransitionOverlayProps> = ({ boundary }) => {
  switch (boundary.transitionType) {
    case "wipe":
      return <WipeTransition />;
    case "slide":
      return <WipeTransition />;
    case "iris":
      return <IrisTransition />;
    case "fade":
      return <FadeTransition />;
    case "cut":
      return null;
    default:
      return null;
  }
};
