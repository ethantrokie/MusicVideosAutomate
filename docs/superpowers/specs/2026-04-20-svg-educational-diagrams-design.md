# SVG Educational Diagrams Design Spec

## Goal

Replace AI-generated raster educational images with Claude-generated SVG diagrams where every element (shapes, labels, arrows, equations) is individually addressable and animatable. Complex real-world objects that SVG can't convey well (organic anatomy, photorealistic textures) can be rendered by fal.ai and embedded as `<image>` elements within the SVG.

## Why

The current raster approach (fal.ai → Claude vision region analysis → bounding box animation) has fundamental problems:
- Bounding boxes are approximate and miss content
- Regions animate over already-visible images or show stock footage in gaps
- No semantic understanding of what's in the image
- Cannot control individual lines, shapes, or labels

SVG solves all of these: every element is a DOM node that can be independently animated, styled, and sequenced.

## Architecture

### Current Flow (being replaced)
```
Stage 4.6: Claude selects concepts → writes fal.ai prompts → fal.ai renders PNGs
Stage 4.7: Claude vision analyzes regions → writes bounding boxes to manifest
Remotion: Animates bounding box crops of raster images
```

### New Flow
```
Stage 4.6: Claude selects concepts → generates structured SVG code directly
           (with optional fal.ai <image> embeds for complex objects)
Remotion: Parses SVG groups → applies Rough.js hand-drawn styling →
          animates each group sequentially with spring physics
```

This eliminates Stage 4.7 entirely. The region analysis agent is no longer needed because the SVG structure IS the animation plan.

## Components

### 1. SVG Generation Agent (`agents/generate_edu_svg.py`)

Replaces both `generate_educational_images.py` and `analyze_edu_image_regions.py`.

**Input:** Topic, key facts, phrase groups with timing (same as current)

**Process per concept:**
1. Call `claude -p` with the SVG system prompt, key fact, and reference images
2. Claude returns SVG code with semantic `<g>` groups
3. If SVG contains `<image data-fal-prompt="...">` placeholders, call fal.ai for each
4. Replace placeholders with local file paths
5. Validate the SVG (well-formed XML, has at least 2 groups with data-order)
6. Save SVG string + metadata to manifest

**Output per concept:**
```json
{
  "id": 1,
  "key_fact": "Pascal's Law: pressure transmits equally...",
  "svg_content": "<svg viewBox='0 0 1080 720'>...</svg>",
  "embedded_images": ["jar_object.png"],
  "start_time": 16.1,
  "end_time": 22.1,
  "duration": 6.0,
  "group_count": 4,
  "generation_status": "success"
}
```

### 2. Claude SVG System Prompt

The prompt instructs Claude to:
- Generate SVG with viewBox `0 0 1080 720` (landscape). The Remotion component centers this vertically in the 1080x1920 portrait frame with 600px letterbox bars top and bottom -- same as the current raster image layout.
- Use a dark background (`#1a1a2e` or similar) with light strokes (`#e0e0e0`) and accent colors (`#ffd700` for emphasis)
- Group every independent element in `<g id="..." data-order="N" data-delay="MS">`
- Elements with the same `data-order` animate simultaneously
- Use standard SVG primitives: `<rect>`, `<circle>`, `<ellipse>`, `<line>`, `<path>`, `<text>`, `<polyline>`, `<polygon>`
- Draw complex shapes with `<path d="...">` -- prefer quadratic (Q) and arc (A) commands over complex cubic Beziers (C) since Rough.js handles simple paths better
- For objects too complex to draw well in SVG, use `<image data-fal-prompt="description of what to render" x="X" y="Y" width="W" height="H" />`
- Think pedagogically about animation order: foundation first, details last, key insight as the finale
- Keep SVG under 50KB (Claude should prefer simpler path descriptions over hyper-detailed ones)

The prompt includes a concrete example SVG snippet showing the expected `<g>` structure:

```svg
<svg viewBox="0 0 1080 720" xmlns="http://www.w3.org/2000/svg">
  <rect width="1080" height="720" fill="#1a1a2e"/>
  <g id="title" data-order="1" data-delay="0">
    <text x="540" y="80" text-anchor="middle" fill="#ffd700" font-size="48">F = P × A</text>
  </g>
  <g id="small-piston" data-order="2" data-delay="800">
    <rect x="200" y="300" width="120" height="180" fill="none" stroke="#e0e0e0" stroke-width="2"/>
    <text x="260" y="520" text-anchor="middle" fill="#e0e0e0" font-size="24">SMALL PISTON</text>
  </g>
  <g id="big-piston" data-order="2" data-delay="800">
    <rect x="600" y="250" width="200" height="230" fill="none" stroke="#e0e0e0" stroke-width="2"/>
    <text x="700" y="520" text-anchor="middle" fill="#e0e0e0" font-size="24">BIG PISTON</text>
  </g>
  <g id="comparison-arrow" data-order="3" data-delay="600">
    <line x1="380" y1="400" x2="560" y2="400" stroke="#ffd700" stroke-width="3"/>
    <polygon points="560,390 580,400 560,410" fill="#ffd700"/>
  </g>
</svg>
```

The prompt also includes the 6 reference images so Claude can see the visual style and complexity level to match. Claude uses `claude -p` with vision to read these images.

### 3. Rough.js Integration

SVG shapes from Claude will be clean/precise. To achieve the hand-drawn chalkboard aesthetic, the Remotion component applies Rough.js at render time.

**How it works:**
- `roughjs` npm package is added to `agents/remotion/`
- The Remotion component walks each SVG group's children
- For simple shape elements (`rect`, `circle`, `ellipse`, `line`): render through Rough.js's SVG renderer with `roughness: 1.5`, `stroke: '#e0e0e0'`, `strokeWidth: 2`
- For `<path>` elements: attempt Rough.js rendering via `rough.path(d)`. If the path is complex (>500 chars in the `d` attribute or contains cubic Beziers), render the path directly with a slight stroke-dasharray jitter to approximate hand-drawn feel without Rough.js
- For `<text>` elements: render directly (no Rough.js) with a handwriting-style font
- For `<image>` elements: render directly (these are fal.ai embeds)

**Important:** Rough.js re-renders the same shape slightly differently each call (it uses random jitter). For video, we need deterministic output. Rough.js accepts a `seed` parameter that fixes the randomness. Each group gets a seed derived from its `id` so the hand-drawn style is consistent across frames.

### 4. Remotion Component (`EduSvgDiagram.tsx`)

Replaces `EduImageRegions.tsx`.

**Props:**
```typescript
interface EduSvgDiagram {
  svgContent: string;    // The full SVG string
  concept: string;       // Concept label text
  startMs: number;
  endMs: number;
}
```

**SVG parsing:** Use `svg-parser` npm package (lightweight, works in Node.js without a browser DOM) to parse the SVG string into an AST. Walk the AST to extract `<g>` elements with `data-order` attributes. Convert each group's children into React elements, applying Rough.js to shape elements during conversion.

**Embedded image handling:** The Python props builder replaces `<image href="path/to/file.png">` in the SVG string with `<image href="filename.png">` (just the filename). The render orchestrator copies the actual PNG files to Remotion's `public/` directory. At render time, `svg-parser` extracts `<image>` elements and the component renders them as Remotion `<Img src={staticFile(href)}>` components positioned at the SVG coordinates.

**Rendering logic:**
1. Parse `svgContent` using `svg-parser` into an AST
2. Extract all `<g>` elements with `data-order` attributes
3. Sort by `data-order`, group elements with same order number
4. For each group, calculate entrance frame from cumulative `data-delay`
5. Convert each group to React elements: shapes → Rough.js, text → direct, images → Remotion `<Img>`
6. Render each group inside a `<Sequence>` with spring fade-in + slight scale (0.95→1.0)
7. The SVG is rendered inside a centered container at `(0, 600)` in the 1080x1920 composition (600px from top = vertically centered for a 720px tall viewBox)
8. After all groups visible, show concept label above the diagram
9. Exit fade over last 0.5s

**Key difference from EduImageRegions:** No coordinate mapping, no objectFit:contain math, no overflow:hidden tricks. The SVG viewBox handles all scaling natively within its positioned container.

### 5. Props Builder Changes (`remotion_props_builder.py`)

**EduImage type simplifies to:**
```typescript
interface EduDiagram {
  svgContent: string;
  concept: string;
  startMs: number;
  endMs: number;
}
```

No more `src`, `regions`, `imageWidth`, `imageHeight`. The SVG string contains everything.

**This is a hard cutover, not a gradual migration.** The `EduImage` type in `types.ts` is replaced entirely by `EduDiagram`. Old manifests with raster image data are not forward-compatible -- re-running the pipeline on an old run would regenerate SVG diagrams from scratch (which is fine since the concepts and timing data are preserved in the manifest).

The props builder reads SVG content from the manifest and passes it through as a string. Embedded fal.ai image filenames are resolved by the render orchestrator which copies PNGs to Remotion's `public/` directory.

**Model for SVG generation:** Use `claude-sonnet-4-6` via `claude -p` (same model as research and lyrics agents). Haiku is too weak for complex SVG path generation.

### 6. Reference Images

Six curated fal.ai examples stored at `agents/svg_reference_images/`:
- `ref_btree.png` -- B-tree hierarchy (easy SVG)
- `ref_pistons.png` -- F=P×A equation with pistons (medium)
- `ref_pascals_law.png` -- Jar with pressure arrows (medium)
- `ref_bimetallic.png` -- Strip bending with heat (medium)
- `ref_ac_house.png` -- House cross-section with AC flow (hard)
- `ref_excavator.png` -- Hydraulic excavator with labels (hardest)

These are passed to Claude via the `claude -p` call so it can see the style and complexity level to match. Claude reads them with its vision capability.

### 7. Pipeline Changes

**Stage 4.6** changes from calling `generate_educational_images.py` to calling `generate_edu_svg.py`. Same trigger, same timing selection, different output format.

**Stage 4.7** (region analysis) is removed. The SVG structure replaces region analysis.

**Manifest format** changes from PNG-centric to SVG-centric. The `edu_image_manifest.json` schema changes to include `svg_content` instead of `file`, `regions`, `image_type`.

## Fallback Strategy

If Claude fails to generate valid SVG (malformed XML, no groups, timeout):
1. **Retry once** with a simpler prompt ("generate a basic labeled diagram")
2. If retry fails, **fall back to fal.ai raster** with simple fade-in (no region animation)

This ensures the pipeline never blocks on SVG generation failures.

## Cost

- **Claude SVG generation:** ~$0.02-0.05 per diagram (Haiku or Sonnet via `claude -p`)
- **fal.ai embeds (rare):** ~$0.01 per embedded object (5-10% of diagrams)
- **Total per video:** ~$0.15-0.40 for 5-8 diagrams (comparable to current cost)
- **Rough.js:** Free, open-source, renders at Remotion build time

## Success Criteria

1. Every SVG element (shape, label, arrow) can be independently animated
2. Hand-drawn aesthetic via Rough.js matches the current chalk-on-blackboard style
3. Claude generates valid SVG for 90%+ of educational concepts
4. Animation sequence is pedagogically ordered (foundation → detail → insight)
5. Complex objects (rare) fall back to fal.ai embeds seamlessly
6. No region analysis step needed -- SVG structure IS the animation plan

## What's NOT Changing

- Topic selection, concept picking, timing alignment -- all stay the same
- Remotion overlay system (karaoke subtitles, hook text, end screen) -- untouched
- Video assembly pipeline (MoviePy, FFmpeg compositing) -- untouched
- The SVG diagrams appear in the same overlay layer as the current edu images
