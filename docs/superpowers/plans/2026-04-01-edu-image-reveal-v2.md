# Educational Image Reveal v2 - Dimmed-to-Bright Region Animation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix three problems with the current educational image region animation: (1) regions slide in on top of an already-visible image making the animation pointless, (2) images display for only ~2.5s which is too fast to absorb, and (3) the concept label floats at the top of the screen disconnected from the image.

**Architecture:** Replace the current approach (clip-path slide-in over visible image) with a "dimmed base to bright region" pattern inspired by Kurzgesagt and 3Blue1Brown. The full image starts at ~15% brightness. Each region reveals by brightening to 100% in place (no spatial movement). After all regions reveal, the full image is bright. The concept label is anchored above the image content area. Display duration increases from ~2.5s to 5-8s.

**Tech Stack:** Remotion (React/TypeScript), CSS opacity masking, Python config

---

## The Three Problems and Fixes

### Problem 1: Regions animate over already-visible image
**Current:** The full image is visible at `objectFit: "contain"` from frame 0. Regions slide in on top, but the image is already there so the animation adds nothing.

**Fix:** Start with the full image dimmed to ~15% opacity (barely visible silhouette on dark background). Each region "reveals" by placing a bright (100% opacity) clip of that region on top of the dimmed base. No spatial movement -- the bright region simply fades/scales into existence in its correct position. After all regions have revealed, the dimmed base fades up to full brightness so the viewer sees the complete diagram at 100%.

### Problem 2: Images display for only ~2.5s
**Current:** Educational images configured for 2.5s display in config.json. Research shows educational diagrams need 3-5 seconds per region, with 8-15s total.

**Fix:** Increase `educational_images.duration_seconds` from 2.5 to 6.0 in config. For images with 3+ regions, the analyzer should suggest longer durations in the manifest. The Remotion component should budget ~1.5s per region plus 1.5s for the full reveal.

### Problem 3: Concept label disconnected from image
**Current:** Label sits at `top: 8%` of the 1920px frame regardless of where the image content actually is. With `objectFit: "contain"`, a landscape image is centered vertically, leaving large black bars above and below. The label floats in the black bar area, disconnected.

**Fix:** Position the label directly above the image's visible area. For a landscape image (e.g. 1248x832) displayed in a 1080x1920 portrait frame with `contain`, the image occupies roughly the middle ~44% of the height. The label should sit just above that -- approximately at 25% from top for landscape images, adjusting based on aspect ratio.

---

## File Structure

### Modified files

```
agents/remotion/src/compositions/EduImageRegions.tsx    # Rewrite animation logic
config/config.json                                       # Increase edu image duration
agents/analyze_edu_image_regions.py                      # Add suggested_duration to output
agents/remotion/src/types.ts                             # No changes needed (types already correct)
agents/remotion_props_builder.py                         # Pass duration override if present
```

---

## Task 1: Rewrite EduImageRegions Component

**Files:**
- Modify: `agents/remotion/src/compositions/EduImageRegions.tsx`

This is the main visual change. Replace the clip-path slide-in approach with dimmed-base + bright-region reveals.

- [ ] **Step 1: Rewrite EduImageRegions.tsx**

The new component logic:

```tsx
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

/**
 * CSS inset() clip to isolate a region of the image.
 * inset(top right bottom left) as percentages from each edge.
 */
const getInsetClip = (bounds: ImageRegion["bounds"]): string => {
  const top = bounds.y;
  const right = 100 - (bounds.x + bounds.w);
  const bottom = 100 - (bounds.y + bounds.h);
  const left = bounds.x;
  return `inset(${top}% ${right}% ${bottom}% ${left}%)`;
};

const REGION_REVEAL_MS = 500; // Each region fades in over 0.5s

/**
 * A single bright region that fades+scales into existence
 * on top of the dimmed base image.
 */
const BrightRegion: React.FC<{
  image: EduImage;
  region: ImageRegion;
  imageStyle: React.CSSProperties;
}> = ({ image, region, imageStyle }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  // Fade in with slight scale (0.95 -> 1.0) over 0.5s
  const progress = spring({
    frame,
    fps,
    config: { mass: 0.5, damping: 15, stiffness: 120 },
    durationInFrames: Math.round((REGION_REVEAL_MS / 1000) * fps),
  });

  const opacity = interpolate(progress, [0, 1], [0, 1]);
  const scale = interpolate(progress, [0, 1], [0.95, 1.0]);

  const imgSrc = image.src.startsWith("http")
    ? image.src
    : staticFile(image.src);

  return (
    <AbsoluteFill
      style={{
        clipPath: getInsetClip(region.bounds),
        opacity,
        transform: `scale(${scale})`,
        transformOrigin: `${region.bounds.x + region.bounds.w / 2}% ${region.bounds.y + region.bounds.h / 2}%`,
      }}
    >
      <Img src={imgSrc} style={imageStyle} />
    </AbsoluteFill>
  );
};

interface EduImageRegionsProps {
  image: EduImage;
}

export const EduImageRegions: React.FC<EduImageRegionsProps> = ({ image }) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames, width, height } = useVideoConfig();

  const regions = image.regions ?? [];
  const hasRegions = regions.length > 0;

  const imgSrc = image.src.startsWith("http")
    ? image.src
    : staticFile(image.src);

  // Common image style: contain = no cropping, centered
  const imageStyle: React.CSSProperties = {
    width: "100%",
    height: "100%",
    objectFit: "contain",
  };

  // --- Timing ---
  // Budget: region reveals take first ~60% of duration, full image visible for last ~40%
  const regionTimings = regions.map((region, i) => {
    const cumulativeDelay = regions
      .slice(0, i)
      .reduce((sum, r) => sum + r.delayMs, 0);
    return { startMs: cumulativeDelay };
  });

  const lastRegionStartMs =
    regionTimings.length > 0
      ? regionTimings[regionTimings.length - 1].startMs
      : 0;
  const allRegionsRevealedMs = lastRegionStartMs + REGION_REVEAL_MS;

  // Full image brightens 300ms after last region finishes
  const fullBrightenMs = allRegionsRevealedMs + 300;
  const fullBrightenFrame = Math.round((fullBrightenMs / 1000) * fps);

  // Dimmed base fades from 0.15 to 1.0 when full image brightens
  const baseBrightness = interpolate(
    frame,
    [fullBrightenFrame, fullBrightenFrame + Math.round(fps * 0.4)],
    [0.15, 1],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );

  // Exit fade: last 0.4s
  const exitStartFrame = durationInFrames - Math.round(fps * 0.4);
  const exitOpacity = interpolate(
    frame,
    [exitStartFrame, durationInFrames],
    [1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );

  // Concept label: appears when full image brightens
  const labelOpacity = interpolate(
    frame,
    [fullBrightenFrame, fullBrightenFrame + Math.round(fps * 0.3)],
    [0, 1],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );

  // --- Label positioning ---
  // For a landscape image in a portrait frame, calculate where the image
  // content actually sits vertically so the label anchors just above it.
  // With objectFit:contain, a 1248x832 image in 1080x1920 occupies:
  //   displayed width = 1080, displayed height = 1080 * (832/1248) = 720
  //   vertical offset from top = (1920 - 720) / 2 = 600px = 31.25%
  // Label should sit just above that.
  // We approximate: label at max(5%, imageTopPercent - 5%)
  // Since we don't know exact image dimensions in the component,
  // position at 22% which works for typical landscape edu images.
  const labelTop = "22%";

  if (!hasRegions) {
    // No regions: simple fade-in of the full image
    const fadeIn = interpolate(frame, [0, Math.round(fps * 0.5)], [0, 1], {
      extrapolateRight: "clamp",
    });
    return (
      <AbsoluteFill style={{ opacity: Math.min(fadeIn, exitOpacity) }}>
        <Img src={imgSrc} style={imageStyle} />
        {image.concept && (
          <div style={{
            position: "absolute", top: labelTop, left: 0, right: 0,
            display: "flex", justifyContent: "center", opacity: fadeIn,
          }}>
            <ConceptLabel text={image.concept} />
          </div>
        )}
      </AbsoluteFill>
    );
  }

  return (
    <AbsoluteFill style={{ opacity: exitOpacity }}>
      {/* Layer 1: Dimmed base image (always visible, starts at 15% brightness) */}
      <AbsoluteFill style={{ opacity: baseBrightness }}>
        <Img src={imgSrc} style={imageStyle} />
      </AbsoluteFill>

      {/* Layer 2: Bright regions revealed one by one */}
      {/* These clip the full-brightness image to each region's bounds */}
      {/* They sit on top of the dimmed base, creating the "spotlight" effect */}
      {regions.map((region, i) => {
        const startFrame = Math.round(
          (regionTimings[i].startMs / 1000) * fps
        );
        return (
          <Sequence key={`region-${i}`} from={startFrame}>
            <BrightRegion
              image={image}
              region={region}
              imageStyle={imageStyle}
            />
          </Sequence>
        );
      })}

      {/* Layer 3: Concept label anchored above image content */}
      {image.concept && (
        <div style={{
          position: "absolute", top: labelTop, left: 0, right: 0,
          display: "flex", justifyContent: "center", opacity: labelOpacity,
        }}>
          <ConceptLabel text={image.concept} />
        </div>
      )}
    </AbsoluteFill>
  );
};

/** Reusable concept label pill */
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
```

Key changes from v1:
- **No spatial movement** -- regions don't slide in. They appear in place via opacity+scale.
- **Dimmed base at 15%** -- viewer sees a faint silhouette of the full image from the start.
- **Bright clip-path regions** -- each region is a full-brightness clip of the image, fading in on top of the dim base.
- **transformOrigin per region** -- the slight scale (0.95->1.0) expands from each region's center, not the frame center.
- **Full image brightens** after all regions revealed -- dimmed base fades from 15% to 100%.
- **Label at 22%** -- just above where a landscape image sits in a portrait frame.

- [ ] **Step 2: Preview in Remotion Studio**

Verify:
- Image starts dimmed (barely visible silhouette)
- Each region brightens into existence in order (no sliding)
- After all regions: full image at 100% brightness
- Concept label appears above the image, not floating in black space
- Exit fade works

- [ ] **Step 3: Commit**

```bash
git add agents/remotion/src/compositions/EduImageRegions.tsx
git commit -m "fix: rewrite edu image reveal - dimmed base with bright region spotlights"
```

---

## Task 2: Increase Educational Image Display Duration

**Files:**
- Modify: `config/config.json`
- Modify: `agents/analyze_edu_image_regions.py`
- Modify: `agents/remotion_props_builder.py`

- [ ] **Step 1: Increase default duration in config.json**

Change `educational_images.duration_seconds` from `2.5` to `6.0`:

```json
"educational_images": {
    ...
    "duration_seconds": 6.0,
    ...
}
```

- [ ] **Step 2: Add suggested_duration to region analyzer output**

In `agents/analyze_edu_image_regions.py`, after analyzing regions for an image, calculate a suggested duration based on region count:

```python
        # Suggest duration: 1.5s per region + 1.5s for full reveal + 1s buffer
        suggested_duration = len(regions) * 1.5 + 1.5 + 1.0
        img["suggested_duration"] = round(min(suggested_duration, 10.0), 1)
```

Add this after the `img["regions"] = regions` line in `analyze_all_images`.

- [ ] **Step 3: Update props builder to use suggested duration**

In `agents/remotion_props_builder.py`, in `_build_edu_images`, when building each image dict, use `suggested_duration` if available to override the default:

After computing startMs/endMs, add:

```python
        # Use suggested duration from region analysis if available
        suggested = img.get("suggested_duration")
        if suggested:
            start_s = img.get("start_time", 0)
            end_ms = _seconds_to_ms(start_s + suggested)
            # Don't exceed original end time by more than 3s
            original_end_ms = _seconds_to_ms(img.get("end_time", 0))
            end_ms = min(end_ms, original_end_ms + 3000)
```

Then use `end_ms` instead of the original `endMs` in the dict.

- [ ] **Step 4: Run tests**

```bash
./venv/bin/python -m pytest tests/test_remotion_props_builder.py tests/test_analyze_edu_image_regions.py -v
```

- [ ] **Step 5: Commit**

```bash
git add config/config.json agents/analyze_edu_image_regions.py agents/remotion_props_builder.py
git commit -m "feat: increase edu image display time to 6s with region-count-based suggestions"
```

---

## Task 3: End-to-End Test

**Files:** None (validation only)

- [ ] **Step 1: Re-run region analysis** (to get suggested_duration)

```bash
# Clear existing regions first so they're re-analyzed
python3 -c "
import json
with open('outputs/runs/20260324_090047/educational_images/edu_image_manifest.json') as f:
    m = json.load(f)
for img in m['images']:
    img.pop('regions', None)
    img.pop('suggested_duration', None)
with open('outputs/runs/20260324_090047/educational_images/edu_image_manifest.json', 'w') as f:
    json.dump(m, f, indent=2)
"

export OUTPUT_DIR=outputs/runs/20260324_090047
./venv/bin/python3 agents/analyze_edu_image_regions.py
```

- [ ] **Step 2: Re-assemble and apply Remotion**

```bash
./venv/bin/python3 agents/build_multiformat_videos.py
./venv/bin/python3 agents/render_remotion_overlays.py \
  --run-dir=outputs/runs/20260324_090047 \
  --format=short_intro \
  --video=outputs/runs/20260324_090047/short_intro.mp4 \
  --duration-ms=60000
```

- [ ] **Step 3: Extract frames and verify**

```bash
VID=outputs/runs/20260324_090047/short_intro.mp4
# Edu image 1 starts at ~16s: capture at start (dimmed), mid (one region bright), end (full)
ffmpeg -y -ss 16.2 -i $VID -frames:v 1 /tmp/v2_edu1_dimmed.png
ffmpeg -y -ss 16.8 -i $VID -frames:v 1 /tmp/v2_edu1_one_region.png
ffmpeg -y -ss 18.0 -i $VID -frames:v 1 /tmp/v2_edu1_full.png
```

Verify:
- At 16.2s: image is visible but dimmed (~15% brightness silhouette)
- At 16.8s: one region is bright while rest stays dimmed
- At 18.0s: full image at 100% brightness with concept label above it
- Image displays for ~6s total (not the old 2.5s)
- Concept label sits just above the image content, not floating in black space

- [ ] **Step 4: Full test suite**

```bash
./venv/bin/python -m pytest tests/ -v
```
