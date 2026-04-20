import React from "react";
import { AbsoluteFill, Sequence } from "remotion";
import { EduImageRegions } from "./EduImageRegions";
import { KaraokeSubtitles } from "./KaraokeSubtitles";
import { HookText } from "./HookText";
import { TitleCard } from "./TitleCard";
import { TransitionOverlay } from "./SceneTransitions";
import { EndScreen } from "./EndScreen";
import type { OverlayProps } from "../types";

export const OverlayComposition: React.FC<OverlayProps> = (props) => {
  const {
    durationMs,
    fps,
    hookText,
    titleText,
    channelName,
    isShort,
    phrases,
    eduImages,
    shotBoundaries,
    animateHook,
    karaokeEnabled,
    eduRevealEnabled,
    transitionsEnabled,
  } = props;

  return (
    <AbsoluteFill style={{ backgroundColor: "transparent" }}>
      {/* Layer 1: Scene transitions (behind everything, at shot boundaries) */}
      {transitionsEnabled &&
        shotBoundaries
          .filter((b) => b.transitionType !== "cut")
          .map((boundary, i) => {
            const transitionDurationMs = 400;
            const startFrame = Math.max(
              0,
              Math.round(((boundary.timeMs - transitionDurationMs / 2) / 1000) * fps)
            );
            const durationFrames = Math.round((transitionDurationMs / 1000) * fps);
            return (
              <Sequence
                key={`transition-${i}`}
                from={startFrame}
                durationInFrames={durationFrames}
              >
                <TransitionOverlay boundary={boundary} />
              </Sequence>
            );
          })}

      {/* Layer 2: Educational image reveals (at their scheduled times) */}
      {eduRevealEnabled &&
        eduImages.map((image, i) => {
          const startFrame = Math.round((image.startMs / 1000) * fps);
          const durationFrames = Math.round(((image.endMs - image.startMs) / 1000) * fps);
          return (
            <Sequence key={`edu-${i}`} from={startFrame} durationInFrames={durationFrames}>
              <EduImageRegions image={image} />
            </Sequence>
          );
        })}

      {/* Layer 3: Hook text (first 2s) */}
      {hookText && (
        <Sequence from={0} durationInFrames={Math.round(fps * 2)}>
          <HookText text={hookText} durationMs={2000} isShort={isShort} animate={animateHook} />
        </Sequence>
      )}

      {/* Layer 4: Title card (first 2s, positioned below hook) */}
      {titleText && (
        <Sequence from={0} durationInFrames={Math.round(fps * 2)}>
          <TitleCard text={titleText} durationMs={2000} isShort={isShort} />
        </Sequence>
      )}

      {/* Layer 5: Karaoke subtitles (full duration, always on top of images) */}
      {karaokeEnabled && phrases.length > 0 && (
        <KaraokeSubtitles phrases={phrases} isShort={isShort} />
      )}

      {/* Layer 6: End screen (last 3s) */}
      <Sequence
        from={Math.round(((durationMs - 3000) / 1000) * fps)}
        durationInFrames={Math.round(fps * 3)}
      >
        <EndScreen channelName={channelName} isShort={isShort} durationMs={3000} />
      </Sequence>
    </AbsoluteFill>
  );
};
