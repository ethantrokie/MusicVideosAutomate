import { Composition } from "remotion";
import { OverlayComposition } from "./compositions/OverlayComposition";
import type { OverlayProps } from "./types";

const defaultProps: OverlayProps = {
  durationMs: 60000,
  fps: 30,
  width: 1080,
  height: 1920,
  hookText: "Science is Amazing?!",
  titleText: "How Photosynthesis Works",
  channelName: "@learningsciencemusic",
  isShort: true,
  phrases: [],
  eduImages: [],
  shotBoundaries: [],
  animateHook: false,
  karaokeEnabled: true,
  eduRevealEnabled: true,
  transitionsEnabled: false,
};

const calculateMetadata = ({ props }: { props: OverlayProps }) => ({
  durationInFrames: Math.ceil((props.durationMs / 1000) * props.fps),
  fps: props.fps,
  width: props.width,
  height: props.height,
});

export const RemotionRoot: React.FC = () => {
  return (
    <>
      <Composition
        id="OverlayComposition"
        component={OverlayComposition}
        calculateMetadata={calculateMetadata}
        durationInFrames={Math.ceil((defaultProps.durationMs / 1000) * defaultProps.fps)}
        fps={defaultProps.fps}
        width={defaultProps.width}
        height={defaultProps.height}
        defaultProps={defaultProps}
      />
    </>
  );
};
