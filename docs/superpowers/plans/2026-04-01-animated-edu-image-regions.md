# Animated Educational Image Regions Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the generic zoom animation on educational images with a region-based reveal where Claude Vision identifies 2-4 key visual components in each image, and Remotion crops and animates each region into frame individually -- like a teacher building a diagram piece by piece.

**Architecture:** A new pipeline stage (4.7) runs after edu image generation. For each image, Claude Haiku analyzes it via `claude -p` with vision to identify regions with bounding boxes, entrance order, and slide direction. This region data is saved to the edu_image_manifest. Remotion's `EduImageReveal` component is replaced with `EduImageRegions`, which crops the source image into regions and animates each one in sequentially using `<Sequence>` offsets. The full image is shown with `objectFit: "contain"` (not "cover") to avoid cropping, and regions are CSS-clipped cutouts that slide in from their designated directions.

**Tech Stack:** Claude CLI (Haiku, vision), Python subprocess, Remotion (React/TypeScript), CSS `clip-path` for region cropping

---

## File Structure

### New files

```
agents/analyze_edu_image_regions.py       # Vision analysis: claude -p per image -> region JSON
tests/test_analyze_edu_image_regions.py   # Tests for region analysis and manifest update
agents/remotion/src/compositions/EduImageRegions.tsx  # New Remotion component: region-based reveal
```

### Modified files

```
pipeline.sh                                # Add Stage 4.7 after edu image generation
agents/remotion/src/types.ts               # Add ImageRegion type
agents/remotion/src/compositions/OverlayComposition.tsx  # Swap EduImageReveal -> EduImageRegions
agents/remotion_props_builder.py           # Include region data in props
agents/render_remotion_overlays.py         # No changes needed (already copies images to public/)
```

### Deleted files

```
agents/remotion/src/compositions/EduImageReveal.tsx  # Replaced by EduImageRegions
```

---

## Task 1: Image Region Analyzer Agent

**Files:**
- Create: `agents/analyze_edu_image_regions.py`
- Create: `tests/test_analyze_edu_image_regions.py`

This agent runs after edu image generation. For each image in the manifest, it calls Claude Haiku with vision to identify 2-4 key visual regions, then writes the region data back into the manifest.

- [ ] **Step 1: Write failing test**

Create `tests/test_analyze_edu_image_regions.py`:

```python
import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "agents"))


def test_parse_region_response_valid_json():
    """Parser extracts region list from Claude response."""
    from analyze_edu_image_regions import _parse_region_response

    response = """```json
[
  {"label": "Sliding Diagram", "bounds": {"x": 0, "y": 0, "w": 50, "h": 100}, "order": 1, "from_direction": "left", "delay_ms": 0},
  {"label": "Rolling Diagram", "bounds": {"x": 50, "y": 0, "w": 50, "h": 100}, "order": 2, "from_direction": "right", "delay_ms": 300}
]
```"""
    regions = _parse_region_response(response)
    assert len(regions) == 2
    assert regions[0]["label"] == "Sliding Diagram"
    assert regions[0]["bounds"]["w"] == 50
    assert regions[1]["from_direction"] == "right"


def test_parse_region_response_plain_json():
    """Parser handles response without markdown fences."""
    from analyze_edu_image_regions import _parse_region_response

    response = '[{"label": "A", "bounds": {"x": 0, "y": 0, "w": 100, "h": 100}, "order": 1, "from_direction": "top", "delay_ms": 0}]'
    regions = _parse_region_response(response)
    assert len(regions) == 1


def test_parse_region_response_invalid():
    """Parser returns empty list on invalid response."""
    from analyze_edu_image_regions import _parse_region_response

    assert _parse_region_response("not json at all") == []
    assert _parse_region_response("") == []


def test_validate_regions_clamps_bounds():
    """Validator clamps bounds to 0-100 range."""
    from analyze_edu_image_regions import _validate_regions

    regions = [
        {"label": "A", "bounds": {"x": -5, "y": 0, "w": 120, "h": 50}, "order": 1, "from_direction": "left", "delay_ms": 0}
    ]
    validated = _validate_regions(regions)
    assert validated[0]["bounds"]["x"] == 0
    assert validated[0]["bounds"]["w"] == 100


def test_validate_regions_rejects_too_many():
    """Validator caps at 4 regions max."""
    from analyze_edu_image_regions import _validate_regions

    regions = [
        {"label": f"R{i}", "bounds": {"x": 0, "y": 0, "w": 25, "h": 100}, "order": i, "from_direction": "left", "delay_ms": 0}
        for i in range(6)
    ]
    validated = _validate_regions(regions)
    assert len(validated) == 4


def test_fallback_regions_for_landscape():
    """Fallback produces left/right split for landscape images."""
    from analyze_edu_image_regions import _generate_fallback_regions

    regions = _generate_fallback_regions(1248, 832)
    assert len(regions) == 2
    assert regions[0]["from_direction"] == "left"
    assert regions[1]["from_direction"] == "right"


def test_fallback_regions_for_portrait():
    """Fallback produces top/bottom split for portrait images."""
    from analyze_edu_image_regions import _generate_fallback_regions

    regions = _generate_fallback_regions(768, 1344)
    assert len(regions) == 2
    assert regions[0]["from_direction"] == "top"
    assert regions[1]["from_direction"] == "bottom"
```

- [ ] **Step 2: Run tests -- expect ImportError**

```bash
./venv/bin/python -m pytest tests/test_analyze_edu_image_regions.py -v
```

- [ ] **Step 3: Implement analyze_edu_image_regions.py**

Create `agents/analyze_edu_image_regions.py`:

```python
#!/usr/bin/env python3
"""
Educational image region analyzer.

Uses Claude Haiku vision to identify 2-4 key visual regions in each
educational image, producing bounding boxes and animation metadata.
This enables Remotion to animate each region into frame individually.

Pipeline Stage: 4.7 (after edu image generation, before media curation)
Cost: ~$0 (Haiku vision, ~7s per image)
"""

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional

sys.path.insert(0, str(Path(__file__).parent))
from output_helper import get_output_path

CLAUDE_CLI = "/Users/ethantrokie/.local/bin/claude"

ANALYSIS_PROMPT = """Identify 2-4 key visual regions in this educational diagram for animation. Each region will be cropped from the image and animated into frame separately, like a teacher building a diagram step by step.

Think pedagogically: what should the viewer see FIRST to build understanding? Then what comes next?

For each region output:
- label: short name (2-4 words)
- bounds: bounding box as percentages {{x, y, w, h}} where 0,0 is top-left, values 0-100
- order: entrance order (1 = appears first)
- from_direction: where it slides in from: "left", "right", "top", or "bottom"
- delay_ms: milliseconds to wait after previous region starts entering (0 for first, 200-500 for others)

RULES:
- 2-4 regions ONLY. Group text labels with their associated diagram element.
- Bounds should cover the full visual element including its label.
- Regions can overlap slightly (up to 10%).
- First region should be the foundational/context element.
- Last region should be the most important insight or comparison.

Output ONLY a valid JSON array, no markdown fences, no explanation:

{image_path}"""


def _parse_region_response(response: str) -> List[Dict]:
    """Parse Claude's JSON response into region list."""
    text = response.strip()

    # Strip markdown code fences if present
    if text.startswith("```"):
        lines = text.split("\n")
        # Remove first line (```json) and last line (```)
        start = 1
        end = len(lines)
        for i in range(len(lines) - 1, 0, -1):
            if lines[i].strip() == "```":
                end = i
                break
        text = "\n".join(lines[start:end])

    try:
        regions = json.loads(text)
        if isinstance(regions, list):
            return regions
    except (json.JSONDecodeError, ValueError):
        pass

    return []


def _validate_regions(regions: List[Dict]) -> List[Dict]:
    """Validate and sanitize region data."""
    valid_directions = {"left", "right", "top", "bottom"}
    validated = []

    for region in regions[:4]:  # Cap at 4 regions
        bounds = region.get("bounds", {})
        validated.append({
            "label": str(region.get("label", "Region"))[:50],
            "bounds": {
                "x": max(0, min(100, bounds.get("x", 0))),
                "y": max(0, min(100, bounds.get("y", 0))),
                "w": max(5, min(100, bounds.get("w", 50))),
                "h": max(5, min(100, bounds.get("h", 50))),
            },
            "order": int(region.get("order", len(validated) + 1)),
            "from_direction": region.get("from_direction", "left") if region.get("from_direction") in valid_directions else "left",
            "delay_ms": max(0, min(1000, int(region.get("delay_ms", 300)))),
        })

    # Sort by order
    validated.sort(key=lambda r: r["order"])

    return validated


def _generate_fallback_regions(width: int, height: int) -> List[Dict]:
    """Generate simple split regions when vision analysis fails."""
    is_landscape = width > height

    if is_landscape:
        return [
            {"label": "Left half", "bounds": {"x": 0, "y": 0, "w": 50, "h": 100}, "order": 1, "from_direction": "left", "delay_ms": 0},
            {"label": "Right half", "bounds": {"x": 50, "y": 0, "w": 50, "h": 100}, "order": 2, "from_direction": "right", "delay_ms": 400},
        ]
    else:
        return [
            {"label": "Top half", "bounds": {"x": 0, "y": 0, "w": 100, "h": 50}, "order": 1, "from_direction": "top", "delay_ms": 0},
            {"label": "Bottom half", "bounds": {"x": 0, "y": 50, "w": 100, "h": 50}, "order": 2, "from_direction": "bottom", "delay_ms": 400},
        ]


def _get_image_dimensions(image_path: str) -> tuple:
    """Get image width and height using ffprobe."""
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v:0",
             "-show_entries", "stream=width,height", "-of", "csv=p=0",
             image_path],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0:
            parts = result.stdout.strip().split(",")
            return int(parts[0]), int(parts[1])
    except Exception:
        pass
    return 1248, 832  # Default assumption


def analyze_single_image(image_path: str) -> List[Dict]:
    """
    Analyze a single educational image using Claude Haiku vision.

    Args:
        image_path: Absolute path to the PNG image

    Returns:
        List of validated region dicts, or fallback regions on failure
    """
    width, height = _get_image_dimensions(image_path)

    prompt = ANALYSIS_PROMPT.format(image_path=image_path)

    try:
        result = subprocess.run(
            [CLAUDE_CLI, "-p", prompt,
             "--model", "claude-haiku-4-5",
             "--dangerously-skip-permissions"],
            capture_output=True, text=True, timeout=30,
        )

        if result.returncode == 0 and result.stdout.strip():
            regions = _parse_region_response(result.stdout)
            if regions:
                validated = _validate_regions(regions)
                if validated:
                    return validated

    except subprocess.TimeoutExpired:
        print(f"  ⚠️  Vision analysis timed out for {Path(image_path).name}")
    except Exception as e:
        print(f"  ⚠️  Vision analysis failed for {Path(image_path).name}: {e}")

    # Fallback: simple split based on aspect ratio
    print(f"  Using fallback regions for {Path(image_path).name}")
    return _generate_fallback_regions(width, height)


def analyze_all_images(run_dir: Path) -> None:
    """
    Analyze all educational images in a run and update the manifest.

    Reads edu_image_manifest.json, analyzes each successful image,
    writes regions back into the manifest under each image's 'regions' key.
    """
    edu_dir = run_dir / "educational_images"
    manifest_path = edu_dir / "edu_image_manifest.json"

    if not manifest_path.exists():
        print("  No educational images manifest found, skipping region analysis")
        return

    with open(manifest_path) as f:
        manifest = json.load(f)

    images = manifest.get("images", [])
    analyzed_count = 0

    for img in images:
        if img.get("generation_status") != "success":
            continue

        # Skip if already analyzed
        if img.get("regions"):
            continue

        # Resolve image path
        image_path = img.get("local_path", "")
        if not image_path or not Path(image_path).exists():
            filename = img.get("file", "")
            if filename:
                image_path = str(edu_dir / filename)

        if not image_path or not Path(image_path).exists():
            print(f"  ⚠️  Image file not found for image {img.get('id', '?')}")
            continue

        print(f"  🔍 Analyzing regions for {Path(image_path).name}...")
        regions = analyze_single_image(image_path)
        img["regions"] = regions
        analyzed_count += 1

        print(f"    Found {len(regions)} regions: {', '.join(r['label'] for r in regions)}")

    # Write updated manifest
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)

    print(f"  ✅ Analyzed {analyzed_count} images, manifest updated")


def main():
    """CLI entry point."""
    run_dir = Path(os.environ.get("OUTPUT_DIR", ""))
    if not run_dir.exists():
        print("❌ OUTPUT_DIR not set or doesn't exist")
        sys.exit(1)

    print("🔍 Analyzing educational image regions...")
    analyze_all_images(run_dir)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests -- expect pass**

```bash
./venv/bin/python -m pytest tests/test_analyze_edu_image_regions.py -v
```

- [ ] **Step 5: Commit**

```bash
git add agents/analyze_edu_image_regions.py tests/test_analyze_edu_image_regions.py
git commit -m "feat: add vision-based educational image region analyzer using Claude Haiku"
```

---

## Task 2: Update Types and Props Builder

**Files:**
- Modify: `agents/remotion/src/types.ts`
- Modify: `agents/remotion_props_builder.py`
- Modify: `tests/test_remotion_props_builder.py`

Add the `ImageRegion` type to Remotion and pass region data through the props builder.

- [ ] **Step 1: Add ImageRegion type to types.ts**

Add to `agents/remotion/src/types.ts`:

```ts
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
```

Update `EduImage` interface:

```ts
export interface EduImage {
  src: string;
  startMs: number;
  endMs: number;
  concept: string;
  regions: ImageRegion[];
}
```

- [ ] **Step 2: Update props builder to include regions**

In `agents/remotion_props_builder.py`, update `_build_edu_images` to include region data:

Replace the `images.append(...)` block with:

```python
        # Convert region data, using camelCase for TypeScript
        regions = []
        for region in img.get("regions", []):
            bounds = region.get("bounds", {})
            regions.append({
                "label": region.get("label", ""),
                "bounds": {
                    "x": bounds.get("x", 0),
                    "y": bounds.get("y", 0),
                    "w": bounds.get("w", 100),
                    "h": bounds.get("h", 100),
                },
                "order": region.get("order", 1),
                "fromDirection": region.get("from_direction", "left"),
                "delayMs": region.get("delay_ms", 300),
            })

        images.append({
            "src": str(Path(src).resolve()),
            "startMs": _seconds_to_ms(img.get("start_time", 0)),
            "endMs": _seconds_to_ms(img.get("end_time", 0)),
            "concept": img.get("concept", img.get("key_fact", "")),
            "regions": regions,
        })
```

- [ ] **Step 3: Update test to include regions**

Update `tests/test_remotion_props_builder.py` `test_edu_images_included_when_manifest_exists`:

Add regions to the manifest fixture:

```python
    manifest = {
        "images": [
            {
                "local_path": str(edu_dir / "img1.png"),
                "start_time": 5.0,
                "end_time": 10.0,
                "concept": "Chlorophyll",
                "regions": [
                    {"label": "Leaf", "bounds": {"x": 0, "y": 0, "w": 50, "h": 100}, "order": 1, "from_direction": "left", "delay_ms": 0},
                    {"label": "Cell", "bounds": {"x": 50, "y": 0, "w": 50, "h": 100}, "order": 2, "from_direction": "right", "delay_ms": 300},
                ],
            },
            ...
        ]
    }
```

Add assertion:

```python
    assert len(props["eduImages"][0]["regions"]) == 2
    assert props["eduImages"][0]["regions"][0]["fromDirection"] == "left"
```

- [ ] **Step 4: Run tests**

```bash
./venv/bin/python -m pytest tests/test_remotion_props_builder.py -v
```

- [ ] **Step 5: Commit**

```bash
git add agents/remotion/src/types.ts agents/remotion_props_builder.py tests/test_remotion_props_builder.py
git commit -m "feat: add ImageRegion type and pass region data through props builder"
```

---

## Task 3: EduImageRegions Remotion Component

**Files:**
- Create: `agents/remotion/src/compositions/EduImageRegions.tsx`
- Delete: `agents/remotion/src/compositions/EduImageReveal.tsx`
- Modify: `agents/remotion/src/compositions/OverlayComposition.tsx`

The core visual component. For each educational image, it:
1. Shows the full image with `objectFit: "contain"` (letterboxed, all content visible)
2. Starts with the image hidden (opacity 0)
3. For each region in order: crops that region from the image using CSS `clip-path: inset()` and slides it in from its designated direction
4. After all regions have entered, shows the full image briefly so the viewer sees it as a whole
5. Fades out

- [ ] **Step 1: Create EduImageRegions component**

Create `agents/remotion/src/compositions/EduImageRegions.tsx`:

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
 * Computes the CSS inset() values to clip the image to a given region.
 * inset(top right bottom left) — values are distances from each edge.
 */
const getInsetClip = (bounds: ImageRegion["bounds"]): string => {
  const top = bounds.y;
  const left = bounds.x;
  const bottom = 100 - (bounds.y + bounds.h);
  const right = 100 - (bounds.x + bounds.w);
  return `inset(${top}% ${right}% ${bottom}% ${left}%)`;
};

/**
 * Get the starting transform offset based on slide direction.
 */
const getSlideOffset = (
  direction: ImageRegion["fromDirection"],
  progress: number
): string => {
  const distance = interpolate(progress, [0, 1], [80, 0]);
  switch (direction) {
    case "left":
      return `translateX(-${distance}%)`;
    case "right":
      return `translateX(${distance}%)`;
    case "top":
      return `translateY(-${distance}%)`;
    case "bottom":
      return `translateY(${distance}%)`;
  }
};

interface RegionLayerProps {
  image: EduImage;
  region: ImageRegion;
  imageStyle: React.CSSProperties;
}

/**
 * A single animated region: clips the full image to the region bounds
 * and slides it in from the designated direction.
 */
const RegionLayer: React.FC<RegionLayerProps> = ({
  image,
  region,
  imageStyle,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  // Spring entrance over 0.5s
  const entranceProgress = spring({
    frame,
    fps,
    config: { mass: 0.6, damping: 14, stiffness: 100 },
    durationInFrames: Math.round(fps * 0.5),
  });

  const slideTransform = getSlideOffset(region.fromDirection, entranceProgress);
  const opacity = interpolate(entranceProgress, [0, 1], [0, 1]);

  return (
    <AbsoluteFill
      style={{
        clipPath: getInsetClip(region.bounds),
        transform: slideTransform,
        opacity,
      }}
    >
      <Img
        src={image.src.startsWith("http") ? image.src : staticFile(image.src)}
        style={imageStyle}
      />
    </AbsoluteFill>
  );
};

interface EduImageRegionsProps {
  image: EduImage;
}

export const EduImageRegions: React.FC<EduImageRegionsProps> = ({ image }) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();

  const regions = image.regions ?? [];
  const hasRegions = regions.length > 0;

  // Common image style: contain (never crop), centered
  const imageStyle: React.CSSProperties = {
    width: "100%",
    height: "100%",
    objectFit: "contain",
  };

  // Calculate timing for region entrances
  // Each region enters after its delay_ms from the previous one starting
  const regionTimings = regions.map((region, i) => {
    const cumulativeDelay = regions
      .slice(0, i)
      .reduce((sum, r) => sum + r.delayMs, 0);
    const entranceDurationMs = 500; // 0.5s spring entrance
    return {
      startMs: cumulativeDelay,
      endMs: cumulativeDelay + entranceDurationMs,
    };
  });

  // After last region finishes entering, show full image
  const lastRegionEnd =
    regionTimings.length > 0
      ? regionTimings[regionTimings.length - 1].endMs
      : 0;
  const fullRevealStartMs = lastRegionEnd + 200; // 200ms after last region

  // Exit fade: last 0.4s
  const exitStartFrame = durationInFrames - Math.round(fps * 0.4);
  const exitOpacity = interpolate(
    frame,
    [exitStartFrame, durationInFrames],
    [1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );

  // Full image fade-in after all regions have entered
  const fullRevealFrame = Math.round((fullRevealStartMs / 1000) * fps);
  const fullImageOpacity = interpolate(
    frame,
    [fullRevealFrame, fullRevealFrame + Math.round(fps * 0.3)],
    [0, 1],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );

  // Concept label: appears with the full image reveal
  const labelOpacity = interpolate(
    frame,
    [fullRevealFrame, fullRevealFrame + Math.round(fps * 0.3)],
    [0, 1],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );

  if (!hasRegions) {
    // Fallback: simple fade-in if no regions (shouldn't happen with fallback generator)
    const fadeIn = interpolate(frame, [0, Math.round(fps * 0.3)], [0, 1], {
      extrapolateRight: "clamp",
    });
    return (
      <AbsoluteFill style={{ opacity: Math.min(fadeIn, exitOpacity) }}>
        <Img
          src={
            image.src.startsWith("http") ? image.src : staticFile(image.src)
          }
          style={imageStyle}
        />
      </AbsoluteFill>
    );
  }

  return (
    <AbsoluteFill style={{ opacity: exitOpacity }}>
      {/* Layer 1: Region-by-region reveal */}
      {regions.map((region, i) => {
        const startFrame = Math.round(
          (regionTimings[i].startMs / 1000) * fps
        );
        return (
          <Sequence key={`region-${i}`} from={startFrame}>
            <RegionLayer
              image={image}
              region={region}
              imageStyle={imageStyle}
            />
          </Sequence>
        );
      })}

      {/* Layer 2: Full image fades in after all regions entered */}
      <AbsoluteFill style={{ opacity: fullImageOpacity }}>
        <Img
          src={
            image.src.startsWith("http") ? image.src : staticFile(image.src)
          }
          style={imageStyle}
        />
      </AbsoluteFill>

      {/* Layer 3: Concept label appears with full image */}
      {image.concept && (
        <div
          style={{
            position: "absolute",
            top: "8%",
            left: 0,
            right: 0,
            display: "flex",
            justifyContent: "center",
            opacity: labelOpacity,
          }}
        >
          <div
            style={{
              backgroundColor: "rgba(0, 0, 0, 0.7)",
              borderRadius: 16,
              padding: "10px 24px",
              maxWidth: "85%",
            }}
          >
            <span
              style={{
                color: "#FFFFFF",
                fontSize: 28,
                fontFamily:
                  "SF Pro Display, -apple-system, system-ui, sans-serif",
                fontWeight: 600,
                textAlign: "center",
              }}
            >
              {image.concept}
            </span>
          </div>
        </div>
      )}
    </AbsoluteFill>
  );
};
```

- [ ] **Step 2: Update OverlayComposition to use EduImageRegions**

In `agents/remotion/src/compositions/OverlayComposition.tsx`:

Change the import from:
```tsx
import { EduImageReveal } from "./EduImageReveal";
```
To:
```tsx
import { EduImageRegions } from "./EduImageRegions";
```

Change the usage from:
```tsx
<EduImageReveal image={image} />
```
To:
```tsx
<EduImageRegions image={image} />
```

- [ ] **Step 3: Delete old EduImageReveal.tsx**

```bash
rm agents/remotion/src/compositions/EduImageReveal.tsx
```

- [ ] **Step 4: Test with Remotion Studio**

```bash
cd agents/remotion && npx remotion studio
```

Preview with test props that include regions. Verify:
- Each region slides in from its direction sequentially
- After all regions enter, the full image fades in cleanly
- Image uses `contain` (no cropping, letterboxed)
- Concept label appears at top
- Exit fade works

- [ ] **Step 5: Commit**

```bash
git add agents/remotion/src/compositions/EduImageRegions.tsx agents/remotion/src/compositions/OverlayComposition.tsx
git rm agents/remotion/src/compositions/EduImageReveal.tsx
git commit -m "feat: replace generic zoom with region-based reveal animation"
```

---

## Task 4: Pipeline Integration

**Files:**
- Modify: `pipeline.sh`

Add Stage 4.7 after educational image generation (Stage 4.6) and before media curation (Stage 5).

- [ ] **Step 1: Add Stage 4.7 to pipeline.sh**

Find the block after Stage 4.6 (educational image generation) and before Stage 5 (media curation). Add:

```bash
# Stage 4.7: Educational Image Region Analysis
if [ $START_STAGE -le 4 ]; then
    EDU_MANIFEST="${RUN_DIR}/educational_images/edu_image_manifest.json"
    if [ -f "$EDU_MANIFEST" ]; then
        echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
        echo -e "${BLUE}Stage 4.7: Educational Image Region Analysis${NC}"
        echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

        echo "🔍 Analyzing image regions for animation..."
        if ./venv/bin/python3 agents/analyze_edu_image_regions.py; then
            echo "✅ Image region analysis complete"
        else
            echo -e "${YELLOW}⚠️  Region analysis failed, will use fallback animations${NC}"
        fi
        echo ""
    fi
fi
```

- [ ] **Step 2: Commit**

```bash
git add pipeline.sh
git commit -m "feat: add Stage 4.7 for educational image region analysis"
```

---

## Task 5: End-to-End Test

**Files:** None (validation only)

Run the full flow on an existing run that has educational images.

- [ ] **Step 1: Run region analysis on March 24 run**

```bash
export OUTPUT_DIR=outputs/runs/20260324_090047
./venv/bin/python3 agents/analyze_edu_image_regions.py
```

Verify: manifest updated with regions for all 8 images.

- [ ] **Step 2: Re-assemble clean video**

```bash
export OUTPUT_DIR=outputs/runs/20260324_090047
./venv/bin/python3 agents/build_multiformat_videos.py
```

- [ ] **Step 3: Apply Remotion overlay**

```bash
./venv/bin/python3 agents/render_remotion_overlays.py \
  --run-dir=outputs/runs/20260324_090047 \
  --format=short_intro \
  --video=outputs/runs/20260324_090047/short_intro.mp4 \
  --duration-ms=60000
```

- [ ] **Step 4: Extract frames and verify**

```bash
# Frame at 17s -- should show sliding friction diagram building region by region
ffmpeg -y -ss 17 -i outputs/runs/20260324_090047/short_intro.mp4 -frames:v 1 /tmp/regions_test_17s.png

# Frame at 18s -- should show full image revealed
ffmpeg -y -ss 18 -i outputs/runs/20260324_090047/short_intro.mp4 -frames:v 1 /tmp/regions_test_18s.png
```

Verify: regions animate in separately, full image shows all content (no cropping), concept label visible at top.

- [ ] **Step 5: Run all tests**

```bash
./venv/bin/python -m pytest tests/ -v
```

Expected: all pass, no regressions.
