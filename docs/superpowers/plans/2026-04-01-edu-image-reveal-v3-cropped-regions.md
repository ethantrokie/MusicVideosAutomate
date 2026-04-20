# Educational Image Reveal v3 - Pre-Cropped Region Assembly

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the broken clip-path approach with pre-cropped PNG regions that animate into their correct positions independently, building up the complete diagram piece by piece on a black background.

**Architecture:** The region analyzer (Stage 4.7) now uses PIL to crop each detected region from the source image into a separate PNG file. The Remotion component uses overflow:hidden containers with the full image offset inside, positioned at exact pixel coordinates calculated from the objectFit:contain layout. Each region fades in with a slight scale at its final position -- no clip-path, no objectFit interaction issues. The base video has no edu images (already excluded when Remotion is enabled).

**Tech Stack:** PIL/Pillow (cropping), Remotion (React/TypeScript), overflow:hidden CSS cropping

---

## Why This Approach Works

The previous approaches failed because:
1. **v1 (clip-path slide):** Regions slid over an already-visible image
2. **v2 (clip-path spotlight):** clip-path percentages are relative to the container (1080x1920), not the image content area (1080x720 after objectFit:contain), causing misaligned crops. The brightness difference on white-on-dark images was also imperceptible.

**v3 approach:** Use overflow:hidden containers positioned at exact pixel coordinates. Each container holds the full-resolution image shifted by negative offsets so only the desired region is visible. The coordinate mapping accounts for objectFit:contain letterboxing.

This is the standard technique from motion graphics -- the same approach used by After Effects and Remotion community projects for assembling image pieces.

---

## File Structure

### Modified files

```
agents/analyze_edu_image_regions.py          # Add PIL cropping of regions to separate PNGs
agents/remotion/src/compositions/EduImageRegions.tsx  # Rewrite with overflow:hidden positioned regions
agents/remotion/src/types.ts                 # Add imageWidth/imageHeight to EduImage
agents/remotion_props_builder.py             # Pass image dimensions
agents/render_remotion_overlays.py           # Copy region PNGs to public/ alongside source images
```

---

## Task 1: Add Image Dimensions to Props Pipeline

**Files:**
- Modify: `agents/remotion/src/types.ts`
- Modify: `agents/remotion_props_builder.py`

The Remotion component needs to know the source image dimensions to calculate the objectFit:contain layout and coordinate mapping.

- [ ] **Step 1: Add dimensions to EduImage type**

In `agents/remotion/src/types.ts`, add two fields to `EduImage`:

```ts
export interface EduImage {
  src: string;
  startMs: number;
  endMs: number;
  concept: string;
  regions: ImageRegion[];
  imageWidth: number;   // NEW: source image width in pixels
  imageHeight: number;  // NEW: source image height in pixels
}
```

- [ ] **Step 2: Pass dimensions from props builder**

In `agents/remotion_props_builder.py`, in `_build_edu_images`, get image dimensions and include them. Add before the `images.append(...)`:

```python
        # Get image dimensions for Remotion coordinate mapping
        img_width, img_height = 1248, 832  # defaults
        try:
            result = subprocess.run(
                ["ffprobe", "-v", "error", "-select_streams", "v:0",
                 "-show_entries", "stream=width,height", "-of", "csv=p=0",
                 str(Path(src).resolve())],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode == 0:
                parts = result.stdout.strip().split(",")
                img_width, img_height = int(parts[0]), int(parts[1])
        except Exception:
            pass
```

Then add to the dict: `"imageWidth": img_width, "imageHeight": img_height,`

Need to add `import subprocess` at the top of the file if not already there.

- [ ] **Step 3: Commit**

---

## Task 2: Rewrite EduImageRegions with Overflow-Hidden Positioning

**Files:**
- Modify: `agents/remotion/src/compositions/EduImageRegions.tsx`

Replace the entire component with the overflow:hidden container approach.

The key algorithm:

1. Calculate objectFit:contain layout:
   - `renderedWidth = containerWidth` (since image is landscape in portrait container)
   - `renderedHeight = containerWidth / imageAspect`
   - `offsetY = (containerHeight - renderedHeight) / 2`
   - `scale = containerWidth / imageWidth`

2. For each region (with bounds as percentages 0-100 of source image):
   - Convert to source pixels: `srcX = bounds.x * imageWidth / 100`
   - Map to composition pixels: `destX = offsetX + srcX * scale`
   - Create an overflow:hidden div at `(destX, destY)` with `(destW, destH)`
   - Inside: place the full image at `left: -(srcX * scale)`, `top: -(srcY * scale)`

3. Animation: each region container fades in (0→1 opacity) with a slight scale (0.92→1.0) at staggered delays. No spatial movement.

4. After all regions visible, no need for a "full image reveal" -- the regions already form the complete image when all visible.

5. Concept label appears after all regions, positioned just above the image content area.

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

const ENTRANCE_DURATION_FRAMES = 15; // 0.5s at 30fps

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
      {/* Full image inside, offset so only this region shows */}
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

  // Staggered entrance: each region delayed by its delayMs
  const regionTimings = regions.map((region, i) => {
    const cumulativeDelay = regions.slice(0, i).reduce((sum, r) => sum + r.delayMs, 0);
    return Math.round((cumulativeDelay / 1000) * fps);
  });

  // Label appears after last region finishes entering
  const lastRegionFrame = regionTimings.length > 0
    ? regionTimings[regionTimings.length - 1] + ENTRANCE_DURATION_FRAMES
    : 0;
  const labelStartFrame = lastRegionFrame + Math.round(fps * 0.3);

  const labelOpacity = interpolate(
    frame,
    [labelStartFrame, labelStartFrame + Math.round(fps * 0.3)],
    [0, 1],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
  );

  // Exit fade: last 0.5s
  const exitStart = durationInFrames - Math.round(fps * 0.5);
  const exitOpacity = interpolate(
    frame, [exitStart, durationInFrames], [1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
  );

  // Label position: just above the image content area
  const labelTopPx = Math.max(20, layout.offsetY - 80);

  if (!regions.length) {
    // Fallback: fade in the full image
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
      {/* Regions appear one by one */}
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
```

- [ ] **Step 1: Replace EduImageRegions.tsx with the code above**
- [ ] **Step 2: Commit**

---

## Task 3: Update Render Orchestrator to Copy Region Source Images

**Files:**
- Modify: `agents/render_remotion_overlays.py`

The render orchestrator already copies edu images to Remotion's public/ directory. No additional changes needed since we're using the full source image (not separate crop PNGs) -- the overflow:hidden approach crops at render time in the browser.

No changes needed for this task. Skip.

---

## Task 4: End-to-End Test

- [ ] **Step 1: Re-run region analysis** (to refresh with latest analyzer)

```bash
# Clear and re-analyze
python3 -c "..."  # clear regions
./venv/bin/python3 agents/analyze_edu_image_regions.py
```

- [ ] **Step 2: Re-assemble clean video + apply Remotion**

```bash
./venv/bin/python3 agents/build_multiformat_videos.py
./venv/bin/python3 agents/render_remotion_overlays.py --run-dir=... --format=short_intro --video=... --duration-ms=60000
```

- [ ] **Step 3: Extract frames and verify**

Verify:
- Before edu image: stock footage only
- At edu image start: first region fades in at correct position on black background
- Next region appears at staggered delay
- All regions together form the complete diagram
- Concept label appears above image after all regions
- Image holds for 5-6 seconds total
- Stock footage behind letterbox bars (not covered by edu image)
