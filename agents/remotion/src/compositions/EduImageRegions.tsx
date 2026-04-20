import React from "react";
import {
  AbsoluteFill,
  Img,
  Sequence,
  interpolate,
  spring,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import type { EduImage, ImageRegion } from "../types";

/** Calculate where objectFit:contain places the image in the composition */
const calculateContainLayout = (
  compWidth: number,
  compHeight: number,
  imgWidth: number,
  imgHeight: number,
) => {
  const imgAspect = imgWidth / imgHeight;
  const compAspect = compWidth / compHeight;

  let renderedWidth: number;
  let renderedHeight: number;

  if (imgAspect > compAspect) {
    renderedWidth = compWidth;
    renderedHeight = compWidth / imgAspect;
  } else {
    renderedHeight = compHeight;
    renderedWidth = compHeight * imgAspect;
  }

  return {
    renderedWidth,
    renderedHeight,
    offsetX: (compWidth - renderedWidth) / 2,
    offsetY: (compHeight - renderedHeight) / 2,
    scale: renderedWidth / imgWidth,
  };
};

const ENTRANCE_DURATION_FRAMES = 15;

const RegionPiece: React.FC<{
  imgSrc: string;
  region: ImageRegion;
  layout: ReturnType<typeof calculateContainLayout>;
  imgWidth: number;
  imgHeight: number;
}> = ({ imgSrc, region, layout, imgWidth, imgHeight }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const progress = spring({
    frame,
    fps,
    config: { mass: 0.5, damping: 14, stiffness: 100 },
    durationInFrames: ENTRANCE_DURATION_FRAMES,
  });

  const opacity = interpolate(progress, [0, 1], [0, 1]);
  const scale = interpolate(progress, [0, 1], [0.92, 1.0]);

  // Convert region bounds (percentages) to source image pixels
  const srcX = (region.bounds.x / 100) * imgWidth;
  const srcY = (region.bounds.y / 100) * imgHeight;
  const srcW = (region.bounds.w / 100) * imgWidth;
  const srcH = (region.bounds.h / 100) * imgHeight;

  // Map to composition coordinates
  const destX = layout.offsetX + srcX * layout.scale;
  const destY = layout.offsetY + srcY * layout.scale;
  const destW = srcW * layout.scale;
  const destH = srcH * layout.scale;

  return (
    <div
      style={{
        position: "absolute",
        left: destX,
        top: destY,
        width: destW,
        height: destH,
        overflow: "hidden",
        opacity,
        transform: `scale(${scale})`,
        transformOrigin: "center center",
      }}
    >
      <Img
        src={imgSrc}
        style={{
          position: "absolute",
          width: layout.renderedWidth,
          height: layout.renderedHeight,
          left: -(srcX * layout.scale),
          top: -(srcY * layout.scale),
        }}
      />
    </div>
  );
};

const ConceptLabel: React.FC<{ text: string }> = ({ text }) => (
  <div
    style={{
      backgroundColor: "rgba(0, 0, 0, 0.75)",
      borderRadius: 14,
      padding: "8px 20px",
      maxWidth: "88%",
    }}
  >
    <span
      style={{
        color: "#FFFFFF",
        fontSize: 26,
        fontFamily: "SF Pro Display, -apple-system, system-ui, sans-serif",
        fontWeight: 600,
        textAlign: "center",
        lineHeight: 1.3,
      }}
    >
      {text}
    </span>
  </div>
);

export const EduImageRegions: React.FC<{ image: EduImage }> = ({ image }) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames, width: compW, height: compH } = useVideoConfig();

  const regions = image.regions ?? [];
  const imgSrc = image.src.startsWith("http") ? image.src : staticFile(image.src);
  const imgW = image.imageWidth || 1248;
  const imgH = image.imageHeight || 832;

  const layout = calculateContainLayout(compW, compH, imgW, imgH);

  // Staggered entrance timing -- enforce minimum 800ms between regions
  const regionTimings = regions.map((region, i) => {
    const cumulativeDelay = regions.slice(0, i).reduce(
      (sum, r) => sum + Math.max(r.delayMs, 800), 0
    );
    return Math.round((cumulativeDelay / 1000) * fps);
  });

  // Full image appears after all regions have entered (fills any gaps)
  const lastRegionFrame = regionTimings.length > 0
    ? regionTimings[regionTimings.length - 1] + ENTRANCE_DURATION_FRAMES
    : 0;
  const fullImageStartFrame = lastRegionFrame + Math.round(fps * 0.3);

  const fullImageOpacity = interpolate(
    frame,
    [fullImageStartFrame, fullImageStartFrame + Math.round(fps * 0.4)],
    [0, 1],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
  );

  // Label appears with the full image
  const labelOpacity = fullImageOpacity;

  // Exit fade: last 0.5s
  const exitStart = durationInFrames - Math.round(fps * 0.5);
  const exitOpacity = interpolate(
    frame, [exitStart, durationInFrames], [1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
  );

  // Label position: just above the image content area
  const labelTopPx = Math.max(20, layout.offsetY - 80);

  if (!regions.length) {
    const fadeIn = interpolate(frame, [0, Math.round(fps * 0.5)], [0, 1], {
      extrapolateRight: "clamp",
    });
    return (
      <AbsoluteFill style={{ opacity: Math.min(fadeIn, exitOpacity) }}>
        <Img src={imgSrc} style={{ width: "100%", height: "100%", objectFit: "contain" }} />
      </AbsoluteFill>
    );
  }

  return (
    <AbsoluteFill style={{ opacity: exitOpacity }}>
      {/* Layer 0: Dimmed full image silhouette (fills gaps between regions during build-up) */}
      <AbsoluteFill style={{ opacity: 0.15 }}>
        <Img
          src={imgSrc}
          style={{ width: "100%", height: "100%", objectFit: "contain" }}
        />
      </AbsoluteFill>

      {/* Layer 1: Bright regions appear one by one at their correct positions */}
      {regions.map((region, i) => (
        <Sequence key={i} from={regionTimings[i]}>
          <RegionPiece
            imgSrc={imgSrc}
            region={region}
            layout={layout}
            imgWidth={imgW}
            imgHeight={imgH}
          />
        </Sequence>
      ))}

      {/* Full image fades in after all regions -- fills any gaps from partial coverage */}
      <AbsoluteFill style={{ opacity: fullImageOpacity }}>
        <Img
          src={imgSrc}
          style={{ width: "100%", height: "100%", objectFit: "contain" }}
        />
      </AbsoluteFill>

      {/* Concept label above image content */}
      {image.concept && (
        <div
          style={{
            position: "absolute",
            top: labelTopPx,
            left: 0,
            right: 0,
            display: "flex",
            justifyContent: "center",
            opacity: labelOpacity,
          }}
        >
          <ConceptLabel text={image.concept} />
        </div>
      )}
    </AbsoluteFill>
  );
};
