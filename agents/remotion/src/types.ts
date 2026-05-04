export interface WordTiming {
  word: string;
  startMs: number;
  endMs: number;
}

export interface PhraseGroup {
  text: string;
  startMs: number;
  endMs: number;
  words: WordTiming[];
}

export interface ImageRegion {
  label: string;
  bounds: {
    x: number;  // percentage 0-100
    y: number;
    w: number;
    h: number;
  };
  order: number;
  fromDirection: "left" | "right" | "top" | "bottom";
  delayMs: number;
}

export interface EduImage {
  src: string;
  startMs: number;
  endMs: number;
  concept: string;
  regions: ImageRegion[];
  imageWidth: number;
  imageHeight: number;
}

export interface ShotBoundary {
  timeMs: number;
  transitionType: "wipe" | "slide" | "fade" | "iris" | "cut";
}

export interface EduDiagram {
  svgContent: string;
  concept: string;
  startMs: number;
  endMs: number;
}

export interface OverlayProps {
  durationMs: number;
  fps: number;
  width: number;
  height: number;
  hookText: string;
  titleText: string;
  channelName: string;
  isShort: boolean;
  phrases: PhraseGroup[];
  eduImages: EduImage[];
  eduDiagrams: EduDiagram[];
  shotBoundaries: ShotBoundary[];
  karaokeEnabled: boolean;
  eduRevealEnabled: boolean;
  transitionsEnabled: boolean;
  animateHook: boolean;
  musicIndicatorEnabled: boolean;
}
