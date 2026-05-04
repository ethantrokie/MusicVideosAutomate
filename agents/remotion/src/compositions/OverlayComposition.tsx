import React from "react";
import { AbsoluteFill, Sequence } from "remotion";
import { EduSvgDiagram } from "./EduSvgDiagram";
import { KaraokeSubtitles } from "./KaraokeSubtitles";
import { HookText } from "./HookText";
import { MusicIndicator } from "./MusicIndicator";
import { TitleCard } from "./TitleCard";
import { TransitionOverlay } from "./SceneTransitions";
import { EndScreen } from "./EndScreen";
import { ShareableStat } from "./ShareableStat";
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
    shotBoundaries,
    karaokeEnabled,
    eduRevealEnabled,
    transitionsEnabled,
    musicIndicatorEnabled,
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

      {/* Layer 2: SVG Diagrams */}
      {eduRevealEnabled &&
        props.eduDiagrams?.map((diagram, i) => {
          const startFrame = Math.round((diagram.startMs / 1000) * fps);
          const durationFrames = Math.round(
            ((diagram.endMs - diagram.startMs) / 1000) * fps,
          );
          return (
            <Sequence
              key={`svg-diagram-${i}`}
              from={startFrame}
              durationInFrames={durationFrames}
            >
              <EduSvgDiagram
                svgContent={diagram.svgContent}
                concept={diagram.concept}
              />
            </Sequence>
          );
        })}

      {/* Layer 3: Hook text (first 3s) -- the main scroll-stopper */}
      {hookText && (
        <Sequence from={0} durationInFrames={Math.round(fps * 3)}>
          <HookText text={hookText} durationMs={3000} isShort={isShort} />
        </Sequence>
      )}

      {/* Layer 3b: Music indicator (first 5s) -- signals this is a music video */}
      {musicIndicatorEnabled && (
        <Sequence from={0} durationInFrames={Math.round(fps * 5)}>
          <MusicIndicator durationMs={5000} />
        </Sequence>
      )}

      {/* Layer 4: Title card (appears at 1s, fades at 3s -- below hook, smaller) */}
      {titleText && (
        <Sequence from={Math.round(fps * 0.8)} durationInFrames={Math.round(fps * 2.2)}>
          <TitleCard text={titleText} durationMs={2200} isShort={isShort} />
        </Sequence>
      )}

      {/* Layer 5: Karaoke subtitles (full duration, always on top of images) */}
      {karaokeEnabled && phrases.length > 0 && (
        <KaraokeSubtitles phrases={phrases} isShort={isShort} />
      )}

      {/* Layer 5b: Shareable stat (last 2.5s, above karaoke, below end screen) */}
      {props.shareableStat && (
        <Sequence
          from={Math.round(((durationMs - 2500) / 1000) * fps)}
          durationInFrames={Math.round(fps * 2.5)}
        >
          <ShareableStat text={props.shareableStat} durationMs={2500} />
        </Sequence>
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
