# Remotion Overlay Layer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Remotion-based overlay rendering layer to the pipeline that produces animated educational image reveals, TikTok-style karaoke subtitles, animated title/hook text, scene transitions, and branded end screens -- composited onto the existing MoviePy-assembled base video.

**Architecture:** Hybrid approach. MoviePy continues to assemble base video clips (stages 6-6.5). A new Remotion project renders a transparent overlay video (ProRes 4444 with alpha). FFmpeg composites the overlay onto the base video. Python orchestrates by writing a JSON props file and invoking `npx remotion render` via subprocess. Existing MoviePy overlays and subtitle systems are preserved as fallbacks.

**Tech Stack:** Remotion 4.x (React/TypeScript), Node.js 18+, `@remotion/transitions`, `@remotion/captions`, FFmpeg (alpha compositing), Python subprocess (orchestration)

---

## File Structure

### New files (Remotion project)

```
agents/remotion/                          # Remotion project root
  package.json                            # Remotion + dependencies
  tsconfig.json                           # TypeScript config
  remotion.config.ts                      # Remotion bundler config
  src/
    Root.tsx                              # Composition registry (all compositions)
    types.ts                              # Shared TypeScript types for props
    index.ts                              # Entry point (registerRoot)
    compositions/
      OverlayComposition.tsx              # Main composition -- sequences all overlay layers
      EduImageReveal.tsx                  # Animated educational image component
      KaraokeSubtitles.tsx                # TikTok-style word-by-word highlighting
      HookText.tsx                        # Animated hook text entrance
      TitleCard.tsx                       # Animated title card
      EndScreen.tsx                       # Branded CTA end screen
      SceneTransitions.tsx                # Transition effects between shot boundaries
```

### New files (Python integration)

```
agents/render_remotion_overlays.py        # Python orchestrator: builds props, calls Remotion, composites
agents/remotion_props_builder.py          # Builds the JSON props file from pipeline data
tests/test_remotion_props_builder.py      # Unit tests for props builder
tests/test_render_remotion_overlays.py    # Integration tests for the render orchestrator
```

### Modified files

```
pipeline.sh                               # Add Stage 7.4 (Remotion overlay render + composite)
config/config.json                        # Add remotion overlay config section
agents/video_overlays.py                  # Add fallback detection (skip if Remotion succeeded)
agents/generate_subtitles.py              # Add fallback detection (skip if Remotion succeeded)
```

---

## Task 1: Remotion Project Scaffolding

**Files:**
- Create: `agents/remotion/package.json`
- Create: `agents/remotion/tsconfig.json`
- Create: `agents/remotion/remotion.config.ts`
- Create: `agents/remotion/src/Root.tsx`
- Create: `agents/remotion/src/types.ts`

This task sets up the Remotion project with dependencies and a minimal composition that renders a transparent frame. No visual content yet -- just proving the toolchain works.

- [ ] **Step 1: Verify Node.js is available**

```bash
node --version  # Expect v18+
npm --version
```

If not installed: `brew install node`

- [ ] **Step 2: Create package.json**

Create `agents/remotion/package.json`:

```json
{
  "name": "music-video-overlays",
  "version": "1.0.0",
  "private": true,
  "scripts": {
    "start": "npx remotion studio",
    "build": "npx remotion render src/index.ts OverlayComposition out/overlay.mov",
    "render": "npx remotion render"
  },
  "dependencies": {
    "remotion": "^4.0.0",
    "@remotion/cli": "^4.0.0",
    "@remotion/bundler": "^4.0.0",
    "@remotion/renderer": "^4.0.0",
    "@remotion/transitions": "^4.0.0",
    "@remotion/captions": "^4.0.0",
    "react": "^18.0.0",
    "react-dom": "^18.0.0"
  },
  "devDependencies": {
    "typescript": "^5.0.0",
    "@types/react": "^18.0.0"
  }
}
```

- [ ] **Step 3: Create tsconfig.json**

Create `agents/remotion/tsconfig.json`:

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "commonjs",
    "jsx": "react-jsx",
    "strict": true,
    "esModuleInterop": true,
    "skipLibCheck": true,
    "forceConsistentCasingInFileNames": true,
    "outDir": "./dist",
    "rootDir": "./src",
    "resolveJsonModule": true
  },
  "include": ["src/**/*"]
}
```

- [ ] **Step 4: Create remotion.config.ts**

Create `agents/remotion/remotion.config.ts`:

```ts
import { Config } from "@remotion/cli/config";

Config.setVideoImageFormat("png"); // PNG for alpha channel support
```

- [ ] **Step 5: Create shared types**

Create `agents/remotion/src/types.ts`:

```ts
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

export interface EduImage {
  src: string;           // Absolute path to image file
  startMs: number;
  endMs: number;
  concept: string;       // Label text for the concept
}

export interface ShotBoundary {
  timeMs: number;        // Cut point between shots
  transitionType: "wipe" | "slide" | "fade" | "iris" | "cut";
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
  shotBoundaries: ShotBoundary[];
  // Feature flags (match existing A/B system)
  animateHook: boolean;
  karaokeEnabled: boolean;
  eduRevealEnabled: boolean;
  transitionsEnabled: boolean;
}
```

- [ ] **Step 6: Create Root.tsx with minimal composition**

Create `agents/remotion/src/Root.tsx`:

```tsx
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

// calculateMetadata ensures CLI --props override default dimensions/duration
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
        // Fallback values used by Remotion Studio when no props provided
        durationInFrames={Math.ceil(
          (defaultProps.durationMs / 1000) * defaultProps.fps
        )}
        fps={defaultProps.fps}
        width={defaultProps.width}
        height={defaultProps.height}
        defaultProps={defaultProps}
      />
    </>
  );
};
```

Create `agents/remotion/src/index.ts`:

```ts
import { registerRoot } from "remotion";
import { RemotionRoot } from "./Root";

registerRoot(RemotionRoot);
```

- [ ] **Step 7: Create placeholder OverlayComposition**

Create `agents/remotion/src/compositions/OverlayComposition.tsx`:

```tsx
import { AbsoluteFill } from "remotion";
import type { OverlayProps } from "../types";

export const OverlayComposition: React.FC<OverlayProps> = () => {
  // Transparent background -- this renders as an alpha overlay
  return <AbsoluteFill style={{ backgroundColor: "transparent" }} />;
};
```

- [ ] **Step 8: Install dependencies and verify render**

```bash
cd agents/remotion
npm install
npx remotion render src/index.ts OverlayComposition --frames=0-1 out/test.png
```

Expected: A transparent PNG is rendered. No errors.

- [ ] **Step 9: Add agents/remotion/node_modules to .gitignore**

Append to project root `.gitignore`:

```
agents/remotion/node_modules/
agents/remotion/out/
agents/remotion/dist/
```

- [ ] **Step 10: Commit**

```bash
git add agents/remotion/ .gitignore
git commit -m "feat: scaffold Remotion overlay project with toolchain verification"
```

---

## Task 2: Animated Educational Image Reveals

**Files:**
- Create: `agents/remotion/src/compositions/EduImageReveal.tsx`
- Modify: `agents/remotion/src/compositions/OverlayComposition.tsx`

This is the highest-impact visual upgrade. Educational images currently display as static 2.5s clips with a barely-perceptible 3% Ken Burns zoom. This task adds animated entrance effects: the image fades in with a scale-up spring, an optional concept label slides in from below, and the whole thing has a subtle parallax drift.

- [ ] **Step 1: Write EduImageReveal component**

Create `agents/remotion/src/compositions/EduImageReveal.tsx`:

```tsx
import {
  AbsoluteFill,
  Img,
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import type { EduImage } from "../types";

interface EduImageRevealProps {
  image: EduImage;
}

export const EduImageReveal: React.FC<EduImageRevealProps> = ({ image }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  // Spring-based scale entrance (0.85 -> 1.0 with slight overshoot)
  const scaleProgress = spring({
    frame,
    fps,
    config: { mass: 0.8, damping: 12, stiffness: 100 },
    durationInFrames: Math.round(fps * 0.6),
  });
  const scale = interpolate(scaleProgress, [0, 1], [0.85, 1.02]);

  // Opacity fade-in over first 0.3s
  const opacity = interpolate(frame, [0, Math.round(fps * 0.3)], [0, 1], {
    extrapolateRight: "clamp",
  });

  // Subtle vertical drift (parallax feel) -- 15px over full duration
  const durationFrames = useVideoConfig().durationInFrames;
  const translateY = interpolate(frame, [0, durationFrames], [8, -8], {
    extrapolateRight: "clamp",
  });

  // Concept label entrance -- delayed 0.4s, slides up from below
  const labelDelay = Math.round(fps * 0.4);
  const labelProgress = spring({
    frame: Math.max(0, frame - labelDelay),
    fps,
    config: { mass: 0.6, damping: 14, stiffness: 120 },
    durationInFrames: Math.round(fps * 0.5),
  });
  const labelY = interpolate(labelProgress, [0, 1], [30, 0]);
  const labelOpacity = interpolate(labelProgress, [0, 1], [0, 1]);

  // Exit fade (last 0.3s)
  const exitStart = durationFrames - Math.round(fps * 0.3);
  const exitOpacity = interpolate(
    frame,
    [exitStart, durationFrames],
    [1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );

  const combinedOpacity = Math.min(opacity, exitOpacity);

  return (
    <AbsoluteFill style={{ opacity: combinedOpacity }}>
      {/* Image layer */}
      <AbsoluteFill
        style={{
          justifyContent: "center",
          alignItems: "center",
          transform: `scale(${scale}) translateY(${translateY}px)`,
        }}
      >
        <Img
          src={image.src}
          style={{
            width: "100%",
            height: "100%",
            objectFit: "contain",
          }}
        />
      </AbsoluteFill>

      {/* Concept label overlay -- upper 40% of frame */}
      {image.concept && (
        <div
          style={{
            position: "absolute",
            bottom: "62%",
            left: 0,
            right: 0,
            display: "flex",
            justifyContent: "center",
            opacity: labelOpacity,
            transform: `translateY(${labelY}px)`,
          }}
        >
          <div
            style={{
              backgroundColor: "rgba(0, 0, 0, 0.7)",
              color: "white",
              padding: "12px 28px",
              borderRadius: 12,
              fontSize: 36,
              fontWeight: 700,
              fontFamily: "system-ui, -apple-system, sans-serif",
              textAlign: "center",
              maxWidth: "80%",
            }}
          >
            {image.concept}
          </div>
        </div>
      )}
    </AbsoluteFill>
  );
};
```

- [ ] **Step 2: Wire EduImageReveal into OverlayComposition**

Update `agents/remotion/src/compositions/OverlayComposition.tsx`:

```tsx
import { AbsoluteFill, Sequence } from "remotion";
import { EduImageReveal } from "./EduImageReveal";
import type { OverlayProps } from "../types";

export const OverlayComposition: React.FC<OverlayProps> = (props) => {
  const { fps, eduImages, eduRevealEnabled } = props;

  return (
    <AbsoluteFill style={{ backgroundColor: "transparent" }}>
      {/* Educational image reveals */}
      {eduRevealEnabled &&
        eduImages.map((image, i) => {
          const startFrame = Math.round((image.startMs / 1000) * fps);
          const durationFrames = Math.round(
            ((image.endMs - image.startMs) / 1000) * fps
          );
          return (
            <Sequence
              key={`edu-${i}`}
              from={startFrame}
              durationInFrames={durationFrames}
            >
              <EduImageReveal image={image} />
            </Sequence>
          );
        })}
    </AbsoluteFill>
  );
};
```

- [ ] **Step 3: Test with Remotion Studio**

```bash
cd agents/remotion
npx remotion studio
```

Open browser, select OverlayComposition, update props with a test image path. Verify:
- Image scales in with spring bounce
- Label slides up after 0.4s delay
- Subtle vertical drift over duration
- Opacity fades in and out cleanly
- Background remains transparent

- [ ] **Step 4: Test render to ProRes 4444 (alpha)**

```bash
npx remotion render src/index.ts OverlayComposition out/edu_test.mov \
  --codec=prores \
  --prores-profile=4444 \
  --props='{"durationMs":3000,"fps":30,"width":1080,"height":1920,"hookText":"","titleText":"","channelName":"","isShort":true,"phrases":[],"eduImages":[{"src":"/tmp/test_image.png","startMs":0,"endMs":3000,"concept":"Photosynthesis"}],"shotBoundaries":[],"animateHook":false,"karaokeEnabled":false,"eduRevealEnabled":true,"transitionsEnabled":false}'
```

Verify output has alpha channel: `ffprobe -v error -select_streams v:0 -show_entries stream=codec_name,pix_fmt out/edu_test.mov`

Expected: `pix_fmt=yuva444p10le` (or similar alpha format)

- [ ] **Step 5: Commit**

```bash
git add agents/remotion/src/compositions/EduImageReveal.tsx agents/remotion/src/compositions/OverlayComposition.tsx
git commit -m "feat: add animated educational image reveal component with spring entrance"
```

---

## Task 3: TikTok-Style Karaoke Subtitles

**Files:**
- Create: `agents/remotion/src/compositions/KaraokeSubtitles.tsx`
- Modify: `agents/remotion/src/compositions/OverlayComposition.tsx`

Replace the ASS/pycaps subtitle systems with Remotion's `@remotion/captions` for word-by-word karaoke highlighting. Active words get a spring-scale pop and color change. Phrase groups display together with the active word emphasized.

- [ ] **Step 1: Create KaraokeSubtitles component**

Create `agents/remotion/src/compositions/KaraokeSubtitles.tsx`:

```tsx
import {
  AbsoluteFill,
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import type { PhraseGroup, WordTiming } from "../types";

interface KaraokeSubtitlesProps {
  phrases: PhraseGroup[];
  isShort: boolean;
}

const ActiveWord: React.FC<{
  word: WordTiming;
  isActive: boolean;
  isPast: boolean;
}> = ({ word, isActive, isPast }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  // Compute frame offset since this word became active
  const wordStartFrame = Math.round((word.startMs / 1000) * fps);
  const framesSinceActive = Math.max(0, frame - wordStartFrame);

  // Spring pop fires once when word activates (single entrance, not cycling)
  const popScale =
    isActive || isPast
      ? spring({
          frame: framesSinceActive,
          fps,
          config: { mass: 0.4, damping: 10, stiffness: 200 },
          durationInFrames: Math.round(fps * 0.25),
        })
      : 0;

  const scale = isActive ? interpolate(popScale, [0, 1], [1, 1.15]) : 1;

  const color = isActive ? "#FFD700" : isPast ? "#FFFFFF" : "rgba(255, 255, 255, 0.6)";
  const textShadow = isActive
    ? "0 0 20px rgba(255, 215, 0, 0.6), 0 2px 4px rgba(0, 0, 0, 0.8)"
    : "0 2px 4px rgba(0, 0, 0, 0.8)";

  return (
    <span
      style={{
        display: "inline-block",
        color,
        transform: `scale(${scale})`,
        textShadow,
        transition: "none", // All animation from frame, not CSS transitions
        marginRight: 8,
        fontWeight: isActive ? 800 : 700,
      }}
    >
      {word.word}
    </span>
  );
};

export const KaraokeSubtitles: React.FC<KaraokeSubtitlesProps> = ({
  phrases,
  isShort,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const currentMs = (frame / fps) * 1000;

  // Find the currently active phrase
  const activePhrase = phrases.find(
    (p) => currentMs >= p.startMs && currentMs <= p.endMs
  );

  if (!activePhrase) return null;

  const bottomMargin = isShort ? "25%" : "10%";
  const fontSize = isShort ? 44 : 48;

  return (
    <AbsoluteFill>
      <div
        style={{
          position: "absolute",
          bottom: bottomMargin,
          left: 0,
          right: 0,
          display: "flex",
          justifyContent: "center",
          flexWrap: "wrap",
          padding: "0 40px",
        }}
      >
        <div
          style={{
            display: "flex",
            flexWrap: "wrap",
            justifyContent: "center",
            gap: 0,
            fontSize,
            fontFamily:
              "'SF Pro Display', 'Inter', system-ui, -apple-system, sans-serif",
            lineHeight: 1.4,
          }}
        >
          {activePhrase.words.map((word, i) => {
            const isActive =
              currentMs >= word.startMs && currentMs <= word.endMs;
            const isPast = currentMs > word.endMs;
            return (
              <ActiveWord
                key={`${activePhrase.startMs}-${i}`}
                word={word}
                isActive={isActive}
                isPast={isPast}
              />
            );
          })}
        </div>
      </div>
    </AbsoluteFill>
  );
};
```

- [ ] **Step 2: Wire into OverlayComposition**

Add to `agents/remotion/src/compositions/OverlayComposition.tsx`, inside the `<AbsoluteFill>` after edu images:

```tsx
import { KaraokeSubtitles } from "./KaraokeSubtitles";

// ... inside the component, after edu images:

      {/* Karaoke subtitles -- always on top of edu images */}
      {karaokeEnabled && phrases.length > 0 && (
        <KaraokeSubtitles phrases={phrases} isShort={isShort} />
      )}
```

- [ ] **Step 3: Preview in Remotion Studio with test word timings**

Create a test props JSON with sample phrases and verify:
- Phrase appears when its time range is active
- Active word highlights yellow with scale pop
- Past words are solid white
- Future words are dimmed
- Words wrap cleanly within the container

- [ ] **Step 4: Commit**

```bash
git add agents/remotion/src/compositions/KaraokeSubtitles.tsx agents/remotion/src/compositions/OverlayComposition.tsx
git commit -m "feat: add TikTok-style karaoke subtitles with spring-pop word highlighting"
```

---

## Task 4: Animated Hook Text and Title Card

**Files:**
- Create: `agents/remotion/src/compositions/HookText.tsx`
- Create: `agents/remotion/src/compositions/TitleCard.tsx`
- Modify: `agents/remotion/src/compositions/OverlayComposition.tsx`

Replace the static MoviePy TextClip overlays. Hook text enters with a per-character stagger spring from above. Title card fades in below with a subtle scale. Both exit with smooth shrink-fade.

- [ ] **Step 1: Create HookText component**

Create `agents/remotion/src/compositions/HookText.tsx`:

```tsx
import {
  AbsoluteFill,
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";

interface HookTextProps {
  text: string;
  durationMs: number;
  isShort: boolean;
  animate: boolean;
}

export const HookText: React.FC<HookTextProps> = ({
  text,
  durationMs,
  isShort,
  animate,
}) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();

  const fontSize = isShort ? 72 : 80;

  if (!animate) {
    // Static mode (control group) -- instant appearance, smooth exit
    const exitStart = durationInFrames - Math.round(fps * 0.3);
    const opacity = interpolate(frame, [exitStart, durationInFrames], [1, 0], {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
    });

    return (
      <AbsoluteFill>
        <div
          style={{
            position: "absolute",
            top: "12%",
            left: 0,
            right: 0,
            textAlign: "center",
            padding: "0 30px",
            opacity,
          }}
        >
          <span
            style={{
              fontSize,
              fontWeight: 900,
              color: "#FFD700",
              fontFamily: "Impact, 'Arial Black', system-ui, sans-serif",
              WebkitTextStroke: "4px black",
              paintOrder: "stroke fill",
            }}
          >
            {text}
          </span>
        </div>
      </AbsoluteFill>
    );
  }

  // Animated mode: per-character stagger entrance
  const characters = text.split("");

  // Exit animation
  const exitStart = durationInFrames - Math.round(fps * 0.3);
  const exitScale = interpolate(
    frame,
    [exitStart, durationInFrames],
    [1, 0.8],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );
  const exitOpacity = interpolate(
    frame,
    [exitStart, durationInFrames],
    [1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );

  return (
    <AbsoluteFill>
      <div
        style={{
          position: "absolute",
          top: "12%",
          left: 0,
          right: 0,
          textAlign: "center",
          padding: "0 30px",
          opacity: exitOpacity,
          transform: `scale(${exitScale})`,
        }}
      >
        {characters.map((char, i) => {
          const staggerDelay = i * 1; // 1 frame per character
          const charProgress = spring({
            frame: Math.max(0, frame - staggerDelay),
            fps,
            config: { mass: 0.5, damping: 12, stiffness: 150 },
            durationInFrames: Math.round(fps * 0.3),
          });
          const charY = interpolate(charProgress, [0, 1], [-40, 0]);
          const charOpacity = interpolate(charProgress, [0, 1], [0, 1]);

          return (
            <span
              key={i}
              style={{
                display: "inline-block",
                fontSize,
                fontWeight: 900,
                color: "#FFD700",
                fontFamily: "Impact, 'Arial Black', system-ui, sans-serif",
                WebkitTextStroke: "4px black",
                paintOrder: "stroke fill",
                transform: `translateY(${charY}px)`,
                opacity: charOpacity,
                whiteSpace: char === " " ? "pre" : "normal",
              }}
            >
              {char}
            </span>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};
```

- [ ] **Step 2: Create TitleCard component**

Create `agents/remotion/src/compositions/TitleCard.tsx`:

```tsx
import {
  AbsoluteFill,
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";

interface TitleCardProps {
  text: string;
  durationMs: number;
  isShort: boolean;
}

export const TitleCard: React.FC<TitleCardProps> = ({
  text,
  durationMs,
  isShort,
}) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();

  const fontSize = isShort ? 48 : 56;

  // Entrance: fade + slight scale-up over 0.4s
  const entranceProgress = spring({
    frame,
    fps,
    config: { mass: 0.6, damping: 15, stiffness: 100 },
    durationInFrames: Math.round(fps * 0.4),
  });
  const entranceScale = interpolate(entranceProgress, [0, 1], [0.9, 1]);
  const entranceOpacity = interpolate(entranceProgress, [0, 1], [0, 1]);

  // Exit: fade out over last 0.3s
  const exitStart = durationInFrames - Math.round(fps * 0.3);
  const exitOpacity = interpolate(
    frame,
    [exitStart, durationInFrames],
    [1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );

  return (
    <AbsoluteFill>
      <div
        style={{
          position: "absolute",
          top: "25%",
          left: 0,
          right: 0,
          textAlign: "center",
          padding: "0 40px",
          opacity: Math.min(entranceOpacity, exitOpacity),
          transform: `scale(${entranceScale})`,
        }}
      >
        <span
          style={{
            fontSize,
            fontWeight: 700,
            color: "white",
            fontFamily: "Impact, 'Arial Black', system-ui, sans-serif",
            WebkitTextStroke: "3px black",
            paintOrder: "stroke fill",
            lineHeight: 1.3,
          }}
        >
          {text}
        </span>
      </div>
    </AbsoluteFill>
  );
};
```

- [ ] **Step 3: Wire HookText and TitleCard into OverlayComposition**

Add to `OverlayComposition.tsx`:

```tsx
import { HookText } from "./HookText";
import { TitleCard } from "./TitleCard";

// ... inside <AbsoluteFill>, before edu images:

      {/* Hook text -- first 2 seconds */}
      {hookText && (
        <Sequence from={0} durationInFrames={Math.round(fps * 2)}>
          <HookText
            text={hookText}
            durationMs={2000}
            isShort={isShort}
            animate={animateHook}
          />
        </Sequence>
      )}

      {/* Title card -- first 2 seconds, positioned below hook */}
      {titleText && (
        <Sequence from={0} durationInFrames={Math.round(fps * 2)}>
          <TitleCard text={titleText} durationMs={2000} isShort={isShort} />
        </Sequence>
      )}
```

- [ ] **Step 4: Preview both in Remotion Studio**

Verify:
- Hook text characters stagger in from above (when `animateHook=true`)
- Hook text appears instantly (when `animateHook=false`)
- Title card fades in with slight scale below the hook
- Both exit smoothly
- Yellow hook and white title don't overlap

- [ ] **Step 5: Commit**

```bash
git add agents/remotion/src/compositions/HookText.tsx agents/remotion/src/compositions/TitleCard.tsx agents/remotion/src/compositions/OverlayComposition.tsx
git commit -m "feat: add animated hook text and title card overlay components"
```

---

## Task 5: Scene Transitions

**Files:**
- Create: `agents/remotion/src/compositions/SceneTransitions.tsx`
- Modify: `agents/remotion/src/compositions/OverlayComposition.tsx`

Add visual transition effects at shot boundaries. These render as brief animated overlays at cut points (not replacing the cut itself, just adding a visual flourish). Different transition types for different content: wipe for stock footage cuts, iris for educational images, fade for AI clips.

- [ ] **Step 1: Create SceneTransitions component**

Create `agents/remotion/src/compositions/SceneTransitions.tsx`:

```tsx
import {
  AbsoluteFill,
  interpolate,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import type { ShotBoundary } from "../types";

interface TransitionOverlayProps {
  boundary: ShotBoundary;
}

const WipeTransition: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames, width } = useVideoConfig();

  // Black bar sweeps across screen
  const progress = interpolate(frame, [0, durationInFrames], [0, 1], {
    extrapolateRight: "clamp",
  });

  const barWidth = width * 0.08;
  const barX = interpolate(progress, [0, 1], [-barWidth, width + barWidth]);

  return (
    <AbsoluteFill>
      <div
        style={{
          position: "absolute",
          top: 0,
          left: barX,
          width: barWidth,
          height: "100%",
          background:
            "linear-gradient(90deg, transparent, rgba(0,0,0,0.4), transparent)",
        }}
      />
    </AbsoluteFill>
  );
};

const IrisTransition: React.FC = () => {
  const frame = useCurrentFrame();
  const { durationInFrames, width, height } = useVideoConfig();

  // Circle expands from center then contracts
  const halfDuration = durationInFrames / 2;
  const progress =
    frame < halfDuration
      ? interpolate(frame, [0, halfDuration], [0, 1])
      : interpolate(frame, [halfDuration, durationInFrames], [1, 0]);

  const maxRadius = Math.sqrt(width * width + height * height) / 2;
  const radius = progress * maxRadius * 0.3; // Only partial coverage for subtlety

  return (
    <AbsoluteFill>
      <div
        style={{
          position: "absolute",
          top: "50%",
          left: "50%",
          width: radius * 2,
          height: radius * 2,
          marginTop: -radius,
          marginLeft: -radius,
          borderRadius: "50%",
          border: "3px solid rgba(255, 255, 255, 0.15)",
          boxShadow: "0 0 30px rgba(255, 255, 255, 0.1)",
        }}
      />
    </AbsoluteFill>
  );
};

const FadeTransition: React.FC = () => {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();

  const halfDuration = durationInFrames / 2;
  const opacity =
    frame < halfDuration
      ? interpolate(frame, [0, halfDuration], [0, 0.3])
      : interpolate(frame, [halfDuration, durationInFrames], [0.3, 0]);

  return (
    <AbsoluteFill
      style={{ backgroundColor: `rgba(0, 0, 0, ${opacity})` }}
    />
  );
};

const TransitionOverlay: React.FC<TransitionOverlayProps> = ({ boundary }) => {
  switch (boundary.transitionType) {
    case "wipe":
      return <WipeTransition />;
    case "iris":
      return <IrisTransition />;
    case "fade":
      return <FadeTransition />;
    case "slide":
      return <WipeTransition />; // Reuse wipe for now
    default:
      return null; // "cut" = no transition overlay
  }
};

interface SceneTransitionsProps {
  shotBoundaries: ShotBoundary[];
}

export const SceneTransitions: React.FC<SceneTransitionsProps> = ({
  shotBoundaries,
}) => {
  return <></>;
};

// Export individual transition for use in OverlayComposition sequences
export { TransitionOverlay };
```

- [ ] **Step 2: Wire transitions into OverlayComposition**

Add to `OverlayComposition.tsx`:

```tsx
import { TransitionOverlay } from "./SceneTransitions";

// ... inside <AbsoluteFill>, as the FIRST layer (behind everything else):

      {/* Scene transitions -- brief visual flourish at shot boundaries */}
      {transitionsEnabled &&
        shotBoundaries
          .filter((b) => b.transitionType !== "cut")
          .map((boundary, i) => {
            const transitionDurationMs = 400; // 0.4s per transition
            const startFrame = Math.round(
              ((boundary.timeMs - transitionDurationMs / 2) / 1000) * fps
            );
            const durationFrames = Math.round(
              (transitionDurationMs / 1000) * fps
            );
            return (
              <Sequence
                key={`transition-${i}`}
                from={Math.max(0, startFrame)}
                durationInFrames={durationFrames}
              >
                <TransitionOverlay boundary={boundary} />
              </Sequence>
            );
          })}
```

- [ ] **Step 3: Preview transitions in Remotion Studio**

Verify each transition type renders correctly with transparent background.

- [ ] **Step 4: Commit**

```bash
git add agents/remotion/src/compositions/SceneTransitions.tsx agents/remotion/src/compositions/OverlayComposition.tsx
git commit -m "feat: add scene transition overlays (wipe, iris, fade) at shot boundaries"
```

---

## Task 6: Branded End Screen

**Files:**
- Create: `agents/remotion/src/compositions/EndScreen.tsx`
- Modify: `agents/remotion/src/compositions/OverlayComposition.tsx`

Replace the static ColorClip + TextClip end screen with an animated version. Subscribe text springs in, channel name types in, and a subtle particle/shimmer effect adds polish.

- [ ] **Step 1: Create EndScreen component**

Create `agents/remotion/src/compositions/EndScreen.tsx`:

```tsx
import {
  AbsoluteFill,
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";

interface EndScreenProps {
  channelName: string;
  isShort: boolean;
  durationMs: number;
}

export const EndScreen: React.FC<EndScreenProps> = ({
  channelName,
  isShort,
  durationMs,
}) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();

  // Background fade in
  const bgOpacity = interpolate(
    frame,
    [0, Math.round(fps * 0.5)],
    [0, 0.6],
    { extrapolateRight: "clamp" }
  );

  // CTA text spring entrance (delayed 0.3s)
  const ctaDelay = Math.round(fps * 0.3);
  const ctaProgress = spring({
    frame: Math.max(0, frame - ctaDelay),
    fps,
    config: { mass: 0.6, damping: 10, stiffness: 120 },
    durationInFrames: Math.round(fps * 0.5),
  });
  const ctaScale = interpolate(ctaProgress, [0, 1], [0.5, 1]);
  const ctaOpacity = interpolate(ctaProgress, [0, 1], [0, 1]);

  // Channel name typewriter effect (delayed 0.6s)
  const typeDelay = Math.round(fps * 0.6);
  const typedFrames = Math.max(0, frame - typeDelay);
  const charsToShow = Math.min(
    channelName.length,
    Math.floor(typedFrames / 2) // 2 frames per character
  );
  const displayedChannel = channelName.slice(0, charsToShow);

  // Subscribe icon bounce (delayed 0.9s)
  const iconDelay = Math.round(fps * 0.9);
  const iconProgress = spring({
    frame: Math.max(0, frame - iconDelay),
    fps,
    config: { mass: 0.4, damping: 8, stiffness: 200 },
    durationInFrames: Math.round(fps * 0.4),
  });
  const iconScale = interpolate(iconProgress, [0, 1], [0, 1.1]);

  const ctaFontSize = isShort ? 50 : 55;
  const channelFontSize = isShort ? 40 : 45;

  return (
    <AbsoluteFill>
      {/* Semi-transparent background */}
      <AbsoluteFill
        style={{ backgroundColor: `rgba(0, 0, 0, ${bgOpacity})` }}
      />

      {/* CTA text */}
      <div
        style={{
          position: "absolute",
          top: isShort ? "35%" : "40%",
          left: 0,
          right: 0,
          textAlign: "center",
          opacity: ctaOpacity,
          transform: `scale(${ctaScale})`,
        }}
      >
        <span
          style={{
            fontSize: ctaFontSize,
            fontWeight: 800,
            color: "#FFD700",
            fontFamily: "'SF Pro Display', system-ui, sans-serif",
            WebkitTextStroke: "2px rgba(0, 0, 0, 0.5)",
            paintOrder: "stroke fill",
          }}
        >
          Like & Subscribe!
        </span>
      </div>

      {/* Channel name with typewriter */}
      <div
        style={{
          position: "absolute",
          top: isShort ? "50%" : "55%",
          left: 0,
          right: 0,
          textAlign: "center",
        }}
      >
        <span
          style={{
            fontSize: channelFontSize,
            fontWeight: 600,
            color: "white",
            fontFamily: "'SF Pro Display', system-ui, sans-serif",
            WebkitTextStroke: "2px rgba(0, 0, 0, 0.5)",
            paintOrder: "stroke fill",
          }}
        >
          {isShort ? `Full song on\n` : ""}
          {displayedChannel}
          {charsToShow < channelName.length && (
            <span style={{ opacity: frame % 10 < 5 ? 1 : 0 }}>|</span>
          )}
        </span>
      </div>

      {/* Subscribe icon */}
      {isShort && (
        <div
          style={{
            position: "absolute",
            top: "68%",
            left: 0,
            right: 0,
            textAlign: "center",
            transform: `scale(${iconScale})`,
          }}
        >
          <span style={{ fontSize: 80 }}>👆</span>
        </div>
      )}
    </AbsoluteFill>
  );
};
```

- [ ] **Step 2: Wire EndScreen into OverlayComposition**

Add to `OverlayComposition.tsx`:

```tsx
import { EndScreen } from "./EndScreen";

// ... inside <AbsoluteFill>, after karaoke subtitles:

      {/* End screen -- last 3 seconds */}
      <Sequence
        from={Math.round(((durationMs - 3000) / 1000) * fps)}
        durationInFrames={Math.round(fps * 3)}
      >
        <EndScreen
          channelName={channelName}
          isShort={isShort}
          durationMs={3000}
        />
      </Sequence>
```

- [ ] **Step 3: Preview in Remotion Studio**

Verify: background fades in, CTA springs in, channel name types in, subscribe icon bounces.

- [ ] **Step 4: Commit**

```bash
git add agents/remotion/src/compositions/EndScreen.tsx agents/remotion/src/compositions/OverlayComposition.tsx
git commit -m "feat: add animated end screen with spring CTA and typewriter channel name"
```

---

## Task 7: Python Props Builder

**Files:**
- Create: `agents/remotion_props_builder.py`
- Create: `tests/test_remotion_props_builder.py`

Build the bridge between the Python pipeline data (approved_media.json, lyrics_aligned.json, edu_image_manifest.json, research.json) and Remotion's JSON props format. This module reads pipeline artifacts and produces the `OverlayProps` JSON.

- [ ] **Step 1: Write the failing test**

Create `tests/test_remotion_props_builder.py`:

```python
import json
import pytest
from pathlib import Path
from unittest.mock import patch

# Will be imported from agents/
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "agents"))


def test_build_props_from_minimal_data(tmp_path: Path):
    """Props builder produces valid OverlayProps from minimal pipeline data."""
    from remotion_props_builder import build_overlay_props

    # Create minimal pipeline artifacts
    research = {"video_title": "How Photosynthesis Works"}
    (tmp_path / "research.json").write_text(json.dumps(research))

    lyrics = {"alignedWords": [
        {"word": "plants", "startS": 0.5, "endS": 1.0},
        {"word": "need", "startS": 1.0, "endS": 1.3},
        {"word": "light", "startS": 1.3, "endS": 1.8},
    ]}
    (tmp_path / "lyrics_aligned.json").write_text(json.dumps(lyrics))

    phrase_groups = [
        {"text": "plants need light", "startS": 0.5, "endS": 1.8,
         "words": [
             {"word": "plants", "startS": 0.5, "endS": 1.0},
             {"word": "need", "startS": 1.0, "endS": 1.3},
             {"word": "light", "startS": 1.3, "endS": 1.8},
         ]}
    ]
    (tmp_path / "phrase_groups.json").write_text(json.dumps(phrase_groups))

    approved = {
        "shot_list": [
            {"shot_number": 1, "start_time": 0, "end_time": 3, "media_type": "video"},
            {"shot_number": 2, "start_time": 3, "end_time": 6, "media_type": "image", "source": "educational_image"},
        ]
    }
    (tmp_path / "approved_media.json").write_text(json.dumps(approved))

    config = {
        "video_settings": {"resolution": [1080, 1920], "fps": 30},
        "remotion_overlay": {"enabled": True},
    }

    props = build_overlay_props(
        run_dir=tmp_path,
        config=config,
        format_type="short_hook",
        duration_ms=6000,
    )

    assert props["width"] == 1080
    assert props["height"] == 1920
    assert props["fps"] == 30
    assert props["durationMs"] == 6000
    assert props["isShort"] is True
    assert props["titleText"] == "How Photosynthesis Works"
    assert len(props["phrases"]) == 1
    assert props["phrases"][0]["words"][0]["word"] == "plants"


def test_edu_images_included_when_manifest_exists(tmp_path: Path):
    """Educational images from manifest are included in props."""
    from remotion_props_builder import build_overlay_props

    (tmp_path / "research.json").write_text(json.dumps({"video_title": "Test"}))
    (tmp_path / "lyrics_aligned.json").write_text(json.dumps({"alignedWords": []}))
    (tmp_path / "phrase_groups.json").write_text(json.dumps([]))
    (tmp_path / "approved_media.json").write_text(json.dumps({"shot_list": []}))

    edu_dir = tmp_path / "educational_images"
    edu_dir.mkdir()
    manifest = {
        "images": [
            {"local_path": "/tmp/img1.png", "start_time": 5.0, "end_time": 7.5, "concept": "Chloroplast"},
            {"local_path": "/tmp/img2.png", "start_time": 15.0, "end_time": 17.0, "concept": "Light reaction"},
        ]
    }
    (edu_dir / "edu_image_manifest.json").write_text(json.dumps(manifest))

    config = {
        "video_settings": {"resolution": [1080, 1920], "fps": 30},
        "remotion_overlay": {"enabled": True},
    }

    props = build_overlay_props(run_dir=tmp_path, config=config, format_type="full", duration_ms=180000)

    assert len(props["eduImages"]) == 2
    assert props["eduImages"][0]["concept"] == "Chloroplast"
    assert props["eduImages"][0]["startMs"] == 5000
    assert props["eduImages"][1]["startMs"] == 15000


def test_shot_boundaries_extracted(tmp_path: Path):
    """Shot boundaries are extracted from approved_media shot list."""
    from remotion_props_builder import build_overlay_props

    (tmp_path / "research.json").write_text(json.dumps({"video_title": "Test"}))
    (tmp_path / "lyrics_aligned.json").write_text(json.dumps({"alignedWords": []}))
    (tmp_path / "phrase_groups.json").write_text(json.dumps([]))

    approved = {
        "shot_list": [
            {"shot_number": 1, "start_time": 0, "end_time": 3, "media_type": "video", "source": "stock"},
            {"shot_number": 2, "start_time": 3, "end_time": 6, "media_type": "image", "source": "educational_image"},
            {"shot_number": 3, "start_time": 6, "end_time": 11, "media_type": "video", "source": "ai_generated"},
        ]
    }
    (tmp_path / "approved_media.json").write_text(json.dumps(approved))

    config = {
        "video_settings": {"resolution": [1080, 1920], "fps": 30},
        "remotion_overlay": {"enabled": True},
    }

    props = build_overlay_props(run_dir=tmp_path, config=config, format_type="full", duration_ms=11000)

    # Should have 2 boundaries (between shot 1-2 and 2-3)
    assert len(props["shotBoundaries"]) == 2
    assert props["shotBoundaries"][0]["timeMs"] == 3000
    assert props["shotBoundaries"][1]["timeMs"] == 6000
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /Users/ethantrokie/SoftwareDevProjects/MusicVideosAutomate
./venv/bin/python -m pytest tests/test_remotion_props_builder.py -v
```

Expected: ImportError -- `remotion_props_builder` not found.

- [ ] **Step 3: Implement remotion_props_builder.py**

Create `agents/remotion_props_builder.py`:

```python
#!/usr/bin/env python3
"""
Builds Remotion overlay props JSON from pipeline artifacts.

Reads: research.json, lyrics_aligned.json, phrase_groups.json,
       approved_media.json, educational_images/edu_image_manifest.json
Produces: OverlayProps dict matching agents/remotion/src/types.ts
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Literal

FormatType = Literal["full", "short_hook", "short_educational", "short_intro"]


def _read_json(path: Path) -> Any:
    """Read and parse a JSON file. Returns empty dict/list on failure."""
    if not path.exists():
        return {}
    with open(path) as f:
        return json.load(f)


def _seconds_to_ms(seconds: float) -> int:
    """Convert seconds to integer milliseconds."""
    return int(round(seconds * 1000))


def _build_phrases(phrase_groups: List[Dict]) -> List[Dict]:
    """Convert pipeline phrase groups to Remotion PhraseGroup format."""
    phrases = []
    for group in phrase_groups:
        start_s = group.get("startS", group.get("start_time", 0))
        end_s = group.get("endS", group.get("end_time", 0))

        words = []
        for w in group.get("words", []):
            w_start = w.get("startS", w.get("start", 0))
            w_end = w.get("endS", w.get("end", 0))
            words.append({
                "word": w.get("word", ""),
                "startMs": _seconds_to_ms(w_start),
                "endMs": _seconds_to_ms(w_end),
            })

        phrases.append({
            "text": group.get("text", ""),
            "startMs": _seconds_to_ms(start_s),
            "endMs": _seconds_to_ms(end_s),
            "words": words,
        })

    return phrases


def _build_edu_images(run_dir: Path) -> List[Dict]:
    """Read educational image manifest and convert to Remotion format."""
    manifest_path = run_dir / "educational_images" / "edu_image_manifest.json"
    manifest = _read_json(manifest_path)

    images = []
    for img in manifest.get("images", []):
        images.append({
            "src": img.get("local_path", ""),
            "startMs": _seconds_to_ms(img.get("start_time", 0)),
            "endMs": _seconds_to_ms(img.get("end_time", 0)),
            "concept": img.get("concept", img.get("key_fact", "")),
        })

    return images


def _determine_transition_type(prev_shot: Dict, next_shot: Dict) -> str:
    """Pick transition type based on media types at the boundary."""
    next_source = next_shot.get("source", "")
    prev_source = prev_shot.get("source", "")

    if next_source == "educational_image" or prev_source == "educational_image":
        return "iris"
    if next_source == "ai_generated" or prev_source == "ai_generated":
        return "fade"
    return "wipe"


def _build_shot_boundaries(approved_data: Dict) -> List[Dict]:
    """Extract shot boundary times and assign transition types."""
    shots = approved_data.get("shot_list", [])
    boundaries = []

    for i in range(len(shots) - 1):
        boundary_time = shots[i].get("end_time", 0)
        transition_type = _determine_transition_type(shots[i], shots[i + 1])
        boundaries.append({
            "timeMs": _seconds_to_ms(boundary_time),
            "transitionType": transition_type,
        })

    return boundaries


def _is_short_format(format_type: FormatType) -> bool:
    """Return True if the format is a short-form vertical video."""
    return format_type in ("short_hook", "short_educational", "short_intro")


def _get_hook_text(run_dir: Path, title: str) -> str:
    """Generate hook text from lyrics or title (mirrors video_overlays.py logic)."""
    lyrics_path = run_dir / "lyrics.json"
    if lyrics_path.exists():
        try:
            lyrics_data = json.loads(lyrics_path.read_text())
            viral = lyrics_data.get("viral_elements", {})
            display_hook = viral.get("display_hook_text", "").strip()
            if display_hook:
                words = display_hook.split()
                return " ".join(words[:7]) + ("..." if len(words) > 7 else "")
            hook_line = viral.get("hook_line", "").strip()
            if hook_line:
                words = hook_line.split()
                return " ".join(words[:7]) + ("..." if len(words) > 7 else "")
        except (json.JSONDecodeError, OSError):
            pass

    # Fallback: derive from title (same logic as video_overlays.generate_hook_text)
    clean = title.replace(" Explained", "").replace(" (Music Video)", "").strip()
    lower = clean.lower()
    if lower.startswith("how "):
        return f"{clean[4:]}?!"
    elif lower.startswith(("why ", "what ")):
        return f"{clean}?"
    elif lower.startswith("the "):
        return f"{clean[4:]}?!"
    return f"{clean}?!"


def build_overlay_props(
    run_dir: Path,
    config: Dict,
    format_type: FormatType,
    duration_ms: int,
) -> Dict:
    """
    Build complete OverlayProps dict for Remotion render.

    Args:
        run_dir: Pipeline run directory containing all artifacts
        config: Loaded config/config.json
        format_type: Video format being rendered
        duration_ms: Total video duration in milliseconds

    Returns:
        Dict matching OverlayProps TypeScript interface
    """
    video_settings = config.get("video_settings", {})
    resolution = video_settings.get("resolution", [1080, 1920])
    fps = video_settings.get("fps", 30)

    research = _read_json(run_dir / "research.json")
    title = research.get("video_title", "Educational Video")

    phrase_groups = _read_json(run_dir / "phrase_groups.json")
    if isinstance(phrase_groups, dict):
        phrase_groups = phrase_groups.get("phrase_groups", [])

    approved = _read_json(run_dir / "approved_media.json")

    is_short = _is_short_format(format_type)

    return {
        "durationMs": duration_ms,
        "fps": fps,
        "width": resolution[0],
        "height": resolution[1],
        "hookText": _get_hook_text(run_dir, title),
        "titleText": title,
        "channelName": config.get("remotion_overlay", {}).get("channel_name", "@learningsciencemusic"),
        "isShort": is_short,
        "phrases": _build_phrases(phrase_groups if isinstance(phrase_groups, list) else []),
        "eduImages": _build_edu_images(run_dir),
        "shotBoundaries": _build_shot_boundaries(approved),
        "animateHook": False,  # Set by A/B experiment in render_remotion_overlays.py
        "karaokeEnabled": True,
        "eduRevealEnabled": True,
        "transitionsEnabled": False,  # Start disabled, enable after validation
    }
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
./venv/bin/python -m pytest tests/test_remotion_props_builder.py -v
```

Expected: All 3 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add agents/remotion_props_builder.py tests/test_remotion_props_builder.py
git commit -m "feat: add Remotion props builder with tests for pipeline data conversion"
```

---

## Task 8: Python Render Orchestrator

**Files:**
- Create: `agents/render_remotion_overlays.py`
- Create: `tests/test_render_remotion_overlays.py`
- Modify: `config/config.json`

This is the main integration point. The orchestrator: (1) calls `build_overlay_props()`, (2) writes props to a temp JSON, (3) invokes `npx remotion render` to produce a ProRes 4444 overlay with alpha, (4) composites the overlay onto the base video with FFmpeg.

- [ ] **Step 1: Write failing integration test**

Create `tests/test_render_remotion_overlays.py`:

```python
import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "agents"))


def test_build_ffmpeg_composite_command():
    """FFmpeg composite command is correctly formed."""
    from render_remotion_overlays import _build_composite_command

    cmd = _build_composite_command(
        base_video=Path("/tmp/run/full.mp4"),
        overlay_video=Path("/tmp/run/overlay_full.mov"),
        output_path=Path("/tmp/run/full_with_overlay.mp4"),
    )

    assert "ffmpeg" in cmd[0] or cmd[0].endswith("ffmpeg")
    assert "-filter_complex" in cmd
    # Should use overlay filter with alpha
    filter_idx = cmd.index("-filter_complex") + 1
    assert "overlay" in cmd[filter_idx]


def test_remotion_render_command_formed_correctly():
    """Remotion CLI render command includes props path and codec."""
    from render_remotion_overlays import _build_remotion_render_command

    cmd = _build_remotion_render_command(
        props_path=Path("/tmp/props.json"),
        output_path=Path("/tmp/overlay.mov"),
        remotion_dir=Path("/Users/ethantrokie/SoftwareDevProjects/MusicVideosAutomate/agents/remotion"),
    )

    assert "npx" in cmd[0] or "remotion" in " ".join(cmd)
    assert "--props" in " ".join(cmd) or "/tmp/props.json" in " ".join(cmd)
    assert "prores" in " ".join(cmd).lower() or "4444" in " ".join(cmd)


def test_config_section_respected(tmp_path: Path):
    """When remotion_overlay.enabled is False, render is skipped."""
    from render_remotion_overlays import should_render_remotion_overlay

    config_disabled = {"remotion_overlay": {"enabled": False}}
    assert should_render_remotion_overlay(config_disabled) is False

    config_enabled = {"remotion_overlay": {"enabled": True}}
    assert should_render_remotion_overlay(config_enabled) is True

    config_missing = {}
    assert should_render_remotion_overlay(config_missing) is False
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
./venv/bin/python -m pytest tests/test_render_remotion_overlays.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implement render_remotion_overlays.py**

Create `agents/render_remotion_overlays.py`:

```python
#!/usr/bin/env python3
"""
Remotion overlay render orchestrator.

Pipeline integration point that:
1. Builds props JSON from pipeline artifacts
2. Invokes Remotion CLI to render transparent overlay video
3. Composites overlay onto base video with FFmpeg
4. Falls back to existing MoviePy overlays on failure
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Dict, List, Optional

sys.path.insert(0, str(Path(__file__).parent))
from remotion_props_builder import build_overlay_props, FormatType
from engagement_experiments import is_engagement_feature_enabled

REMOTION_DIR = Path(__file__).parent / "remotion"
COMPOSITION_ID = "OverlayComposition"


def should_render_remotion_overlay(config: Dict) -> bool:
    """Check if Remotion overlay rendering is enabled."""
    return config.get("remotion_overlay", {}).get("enabled", False)


def _find_executable(name: str) -> str:
    """Find an executable, checking common paths for launchd compatibility."""
    found = shutil.which(name)
    if found:
        return found

    fallback_paths = [
        f"/opt/homebrew/bin/{name}",
        f"/usr/local/bin/{name}",
        f"/usr/bin/{name}",
    ]
    for path in fallback_paths:
        if os.path.exists(path) and os.access(path, os.X_OK):
            return path

    return name


def _build_remotion_render_command(
    props_path: Path,
    output_path: Path,
    remotion_dir: Path,
) -> List[str]:
    """Build the npx remotion render CLI command."""
    npx = _find_executable("npx")
    return [
        npx, "remotion", "render",
        "src/index.ts",
        COMPOSITION_ID,
        str(output_path),
        "--codec=prores",
        "--prores-profile=4444",
        f"--props={props_path}",
        "--log=error",
    ]


def _build_composite_command(
    base_video: Path,
    overlay_video: Path,
    output_path: Path,
) -> List[str]:
    """Build FFmpeg command to composite overlay onto base video."""
    ffmpeg = _find_executable("ffmpeg")
    return [
        ffmpeg, "-y",
        "-i", str(base_video),
        "-i", str(overlay_video),
        "-filter_complex", "[0:v][1:v]overlay=0:0:format=auto[outv]",
        "-map", "[outv]",
        "-map", "0:a?",
        "-c:v", "libx264",
        "-preset", "medium",
        "-c:a", "copy",
        str(output_path),
    ]


def render_overlay(
    run_dir: Path,
    config: Dict,
    format_type: FormatType,
    base_video_path: Path,
    duration_ms: int,
) -> Optional[Path]:
    """
    Render Remotion overlay and composite onto base video.

    Args:
        run_dir: Pipeline run directory
        config: Loaded config.json
        format_type: Video format (full, short_hook, etc.)
        base_video_path: Path to the assembled base video
        duration_ms: Video duration in milliseconds

    Returns:
        Path to composited video, or None on failure (caller should fall back)
    """
    if not should_render_remotion_overlay(config):
        return None

    # Check Remotion project exists
    if not (REMOTION_DIR / "node_modules").exists():
        print("  ⚠️  Remotion node_modules not found. Run: cd agents/remotion && npm install")
        return None

    # Build props
    props = build_overlay_props(run_dir, config, format_type, duration_ms)

    # Apply A/B experiment flags
    props["animateHook"] = is_engagement_feature_enabled("engagement_animated_hook")
    props["transitionsEnabled"] = config.get("remotion_overlay", {}).get("transitions_enabled", False)

    # Write props to temp file
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(props, f)
        props_path = Path(f.name)

    overlay_path = run_dir / f"overlay_{format_type}.mov"
    output_path = run_dir / f"{format_type}_with_overlay.mp4"

    try:
        # Step 1: Render overlay with Remotion
        print(f"  🎨 Rendering Remotion overlay for {format_type}...")
        render_cmd = _build_remotion_render_command(props_path, overlay_path, REMOTION_DIR)
        result = subprocess.run(
            render_cmd,
            capture_output=True,
            text=True,
            cwd=str(REMOTION_DIR),
            timeout=600,  # 10 min timeout
        )

        if result.returncode != 0:
            print(f"  ❌ Remotion render failed: {result.stderr[:500]}")
            return None

        print(f"  ✅ Overlay rendered: {overlay_path}")

        # Step 2: Composite overlay onto base video
        print(f"  🔧 Compositing overlay onto base video...")
        composite_cmd = _build_composite_command(base_video_path, overlay_path, output_path)
        result = subprocess.run(
            composite_cmd,
            capture_output=True,
            text=True,
            timeout=300,
        )

        if result.returncode != 0:
            print(f"  ❌ FFmpeg composite failed: {result.stderr[:500]}")
            return None

        # Replace base video with composited version
        shutil.move(str(output_path), str(base_video_path))
        print(f"  ✅ Overlay composited successfully for {format_type}")

        return base_video_path

    except subprocess.TimeoutExpired:
        print(f"  ❌ Remotion render timed out for {format_type}")
        return None
    except Exception as e:
        print(f"  ❌ Remotion overlay failed: {e}")
        return None
    finally:
        # Cleanup temp files
        props_path.unlink(missing_ok=True)
        if overlay_path.exists():
            overlay_path.unlink(missing_ok=True)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
./venv/bin/python -m pytest tests/test_render_remotion_overlays.py -v
```

Expected: All 3 tests PASS.

- [ ] **Step 5: Add remotion_overlay config section to config.json**

Add to `config/config.json` at the top level:

```json
"remotion_overlay": {
    "enabled": false,
    "transitions_enabled": false
}
```

Start with `enabled: false` so the pipeline runs unchanged until explicitly turned on.

- [ ] **Step 6: Commit**

```bash
git add agents/render_remotion_overlays.py tests/test_render_remotion_overlays.py config/config.json
git commit -m "feat: add Remotion render orchestrator with FFmpeg alpha compositing"
```

---

## Task 9: Pipeline Integration

**Files:**
- Modify: `pipeline.sh` (add Stage 7.4)
- Modify: `agents/video_overlays.py` (add fallback detection)
- Modify: `agents/generate_subtitles.py` (add fallback detection)

Wire the Remotion overlay render into the pipeline just before subtitle generation (Stage 7). If Remotion succeeds, it sets a flag file and the existing subtitle/overlay stages (7 and 7.5) skip their work. If Remotion fails, those stages run as fallback.

- [ ] **Step 1: Add Stage 7.4 to pipeline.sh**

Insert as a new block just before the existing Stage 7 block (subtitle generation) in `pipeline.sh`. The new stage checks if Remotion is enabled, renders overlays for each video format, and sets a `.remotion_overlay_applied` flag on success:

```bash
# Stage 7.4: Remotion Overlay Rendering (optional)
if [ $START_STAGE -le 7 ]; then
    REMOTION_OVERLAY_ENABLED=$(python3 -c "
import json
with open('config/config.json') as f:
    config = json.load(f)
print(config.get('remotion_overlay', {}).get('enabled', False))
" 2>/dev/null || echo "False")

    if [ "$REMOTION_OVERLAY_ENABLED" = "True" ]; then
        echo ""
        echo -e "${BLUE}Stage 7.4: Remotion Overlay Rendering${NC}"
        echo "---"

        REMOTION_SUCCESS=false

        for video_file in "${RUN_DIR}"/*.mp4; do
            [ -f "$video_file" ] || continue
            basename=$(basename "$video_file" .mp4)

            # Determine format type from filename
            case "$basename" in
                full) FORMAT_TYPE="full" ;;
                short_hook) FORMAT_TYPE="short_hook" ;;
                short_educational) FORMAT_TYPE="short_educational" ;;
                short_intro) FORMAT_TYPE="short_intro" ;;
                *) continue ;;
            esac

            # Get video duration in ms
            DURATION_MS=$(python3 -c "
import subprocess, json
result = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'json', '$video_file'], capture_output=True, text=True)
d = json.loads(result.stdout)
print(int(float(d['format']['duration']) * 1000))
" 2>/dev/null || echo "0")

            echo "  🎨 Rendering Remotion overlay for $basename (${DURATION_MS}ms)..."
            if ./venv/bin/python3 agents/render_remotion_overlays.py \
                --run-dir="${RUN_DIR}" \
                --format="${FORMAT_TYPE}" \
                --video="${video_file}" \
                --duration-ms="${DURATION_MS}"; then
                echo "  ✅ Remotion overlay applied to $basename"
                REMOTION_SUCCESS=true
            else
                echo -e "${YELLOW}  ⚠️  Remotion overlay failed for $basename, will use fallback${NC}"
            fi
        done

        if [ "$REMOTION_SUCCESS" = "true" ]; then
            touch "${RUN_DIR}/.remotion_overlay_applied"
            echo "✅ Remotion overlays applied (fallback stages will be skipped)"
        fi
    fi
fi
```

- [ ] **Step 2: Add CLI interface to render_remotion_overlays.py**

Append to `agents/render_remotion_overlays.py`:

```python
def main():
    """CLI entry point for pipeline integration."""
    import argparse

    parser = argparse.ArgumentParser(description="Render Remotion overlay onto video")
    parser.add_argument("--run-dir", type=str, required=True, help="Pipeline run directory")
    parser.add_argument("--format", type=str, required=True,
                        choices=["full", "short_hook", "short_educational", "short_intro"])
    parser.add_argument("--video", type=str, required=True, help="Base video path")
    parser.add_argument("--duration-ms", type=int, required=True, help="Video duration in ms")

    args = parser.parse_args()

    config_path = Path("config/config.json")
    with open(config_path) as f:
        config = json.load(f)

    result = render_overlay(
        run_dir=Path(args.run_dir),
        config=config,
        format_type=args.format,
        base_video_path=Path(args.video),
        duration_ms=args.duration_ms,
    )

    sys.exit(0 if result else 1)


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Add fallback detection to video_overlays.py**

At the top of the `main()` function in `agents/video_overlays.py`, add early exit:

```python
    # Skip if Remotion overlay already applied
    remotion_flag = Path(args.video).parent / ".remotion_overlay_applied"
    if remotion_flag.exists():
        print("  ⏭️  Skipping MoviePy overlays (Remotion overlay already applied)")
        return
```

- [ ] **Step 4: Add fallback detection to generate_subtitles.py**

In the main execution section of `agents/generate_subtitles.py`, add early exit when Remotion handled subtitles. Find the main function and add at the top:

```python
    # Skip if Remotion overlay already applied (includes karaoke subtitles)
    remotion_flag = Path(os.environ.get("OUTPUT_DIR", ".")) / ".remotion_overlay_applied"
    if remotion_flag.exists():
        print("  ⏭️  Skipping subtitle generation (Remotion overlay already applied)")
        return
```

- [ ] **Step 5: Test pipeline with Remotion disabled (regression check)**

```bash
# Ensure Remotion is disabled (default)
python3 -c "
import json
with open('config/config.json') as f:
    c = json.load(f)
print('remotion enabled:', c.get('remotion_overlay', {}).get('enabled', False))
"
```

Expected: `remotion enabled: False`. Pipeline runs unchanged.

- [ ] **Step 6: Test pipeline with Remotion enabled (integration test)**

```bash
# Enable Remotion overlay
python3 -c "
import json
with open('config/config.json') as f:
    c = json.load(f)
c['remotion_overlay'] = {'enabled': True, 'transitions_enabled': False}
with open('config/config.json', 'w') as f:
    json.dump(c, f, indent=2)
"

# Run pipeline from a recent run directory
# (Or run stages 7-7.5 manually on an existing video)
```

Verify:
- Remotion overlay renders without error
- FFmpeg composites overlay onto base video
- Stage 7 and 7.5 are skipped (flag file detected)
- Final video has animated overlays

- [ ] **Step 7: Commit**

```bash
git add pipeline.sh agents/render_remotion_overlays.py agents/video_overlays.py agents/generate_subtitles.py
git commit -m "feat: integrate Remotion overlay into pipeline with fallback to MoviePy"
```

---

## Task 10: Config, A/B Testing, and Feature Flags

**Files:**
- Modify: `config/config.json`
- Modify: `agents/engagement_experiments.py` (if needed)

Add granular feature flags so each Remotion overlay component can be independently enabled/disabled and A/B tested. This aligns with the existing A/B testing framework.

- [ ] **Step 1: Expand remotion_overlay config section**

Update `config/config.json` `remotion_overlay` section:

```json
"remotion_overlay": {
    "enabled": false,
    "karaoke_enabled": true,
    "edu_reveal_enabled": true,
    "transitions_enabled": false,
    "animated_end_screen": true
}
```

- [ ] **Step 2: Wire config flags into props builder**

Update `agents/remotion_props_builder.py` `build_overlay_props()` to read these:

```python
    remotion_config = config.get("remotion_overlay", {})

    return {
        # ... existing fields ...
        "karaokeEnabled": remotion_config.get("karaoke_enabled", True),
        "eduRevealEnabled": remotion_config.get("edu_reveal_enabled", True),
        "transitionsEnabled": remotion_config.get("transitions_enabled", False),
    }
```

- [ ] **Step 3: Add test for config flag propagation**

Add to `tests/test_remotion_props_builder.py`:

```python
def test_config_flags_propagated(tmp_path: Path):
    """Remotion overlay config flags are propagated to props."""
    from remotion_props_builder import build_overlay_props

    (tmp_path / "research.json").write_text(json.dumps({"video_title": "Test"}))
    (tmp_path / "lyrics_aligned.json").write_text(json.dumps({"alignedWords": []}))
    (tmp_path / "phrase_groups.json").write_text(json.dumps([]))
    (tmp_path / "approved_media.json").write_text(json.dumps({"shot_list": []}))

    config = {
        "video_settings": {"resolution": [1080, 1920], "fps": 30},
        "remotion_overlay": {
            "enabled": True,
            "karaoke_enabled": False,
            "transitions_enabled": True,
        },
    }

    props = build_overlay_props(run_dir=tmp_path, config=config, format_type="full", duration_ms=60000)

    assert props["karaokeEnabled"] is False
    assert props["transitionsEnabled"] is True
```

- [ ] **Step 4: Run all tests**

```bash
./venv/bin/python -m pytest tests/test_remotion_props_builder.py tests/test_render_remotion_overlays.py -v
```

Expected: All tests PASS.

- [ ] **Step 5: Commit**

```bash
git add config/config.json agents/remotion_props_builder.py tests/test_remotion_props_builder.py
git commit -m "feat: add granular feature flags for Remotion overlay components"
```

---

## Rollout Strategy

After all tasks are complete:

1. **Enable on one format first**: Set `enabled: true` in config and test with `short_hook` only (shortest video = fastest render = quickest feedback).

2. **Validate quality**: Run pipeline once, inspect the output video for:
   - Educational image animations look natural (not jarring)
   - Karaoke timing is accurate against the music
   - Hook text is readable at YouTube Shorts resolution
   - End screen is visible and not cut off
   - No alpha channel artifacts (black fringing, missing transparency)

3. **Enable remaining formats**: Once `short_hook` looks good, enable for all formats.

4. **Enable transitions last**: These are the most subtle and least impactful. Enable `transitions_enabled` after the core overlay components are validated.

5. **A/B test**: After 1-2 weeks of Remotion-enabled videos, compare retention/engagement metrics against pre-Remotion videos in the weekly optimizer.

6. **Remove fallback**: Once confident, remove the MoviePy overlay and pycaps subtitle code paths. Keep the `.remotion_overlay_applied` flag mechanism for debugging.
