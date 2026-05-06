# Remotion vs FFmpeg: Video Rendering Research

**Date:** 2026-03-30
**Context:** Investigating whether Remotion (remotion.dev) should replace FFmpeg/MoviePy for automated video assembly. Applicable to both MusicVideosAutomate and RedditNewsAutomate pipelines.

---

## TL;DR

Remotion is a React-based programmatic video framework that renders via Chrome Headless Shell. It's free for individuals, excels at complex animations and data-driven templates, but is 2-5x slower than FFmpeg and adds Node.js as a dependency. Best suited for projects that need rich, frequently-iterated visual designs. Less suited for pipelines where video assembly is a straightforward composition of known elements.

---

## What Is Remotion?

- **React/TypeScript framework** for creating videos programmatically
- Videos are React components rendered frame-by-frame via Chrome Headless Shell
- FFmpeg is used internally for final encoding (bundled with Remotion)
- Supports local CLI rendering, programmatic API, and AWS Lambda cloud rendering

## Pricing & Licensing

| Tier | Cost | Who |
|------|------|-----|
| **Free** | $0 | Individuals, small companies (even commercial use) |
| **Company License** | Contact sales | Mid-to-large organizations |
| **Lambda rendering** | ~$0.001/video | AWS Lambda compute costs only |

**For our use case:** $0 licensing. Local rendering = no cloud costs.

## Technical Requirements

| Requirement | Detail |
|-------------|--------|
| **Runtime** | Node.js 18+ (currently not in our stack) |
| **Rendering** | Chrome Headless Shell (bundled) |
| **RAM** | 2-4GB per concurrent render |
| **CPU** | Parallelizable via `--concurrency` flag |
| **macOS/launchd** | Supported (can run headless) |

## Capabilities Comparison

### Where Remotion Wins

| Capability | Remotion | FFmpeg | Gap Size |
|-----------|----------|--------|----------|
| Text animations | 23+ built-in (typewriter, bounce, elastic, 3D flip, etc.) | Manual filter expressions | **Large** |
| Transitions | `<TransitionSeries>` with presets | `xfade` filter (limited) | **Medium** |
| Design iteration | CSS-in-JS, hot reload preview | Re-run FFmpeg each time | **Large** |
| Data-driven templates | Native JSON input props | Requires scripting | **Large** |
| Component reuse | React components, npm ecosystem | Copy-paste filter chains | **Large** |
| Version control | Code diffs show visual intent | Filter string diffs are opaque | **Medium** |
| Rich text | Full HTML/CSS (per-word styling, gradients) | `drawtext` (whole-block only) | **Large** |
| Lottie/SVG animation | Native support | Requires pre-conversion | **Medium** |

### Where FFmpeg Wins

| Capability | FFmpeg | Remotion | Gap Size |
|-----------|--------|----------|----------|
| Rendering speed | Direct encoding, 2-5x faster | Frame-by-frame Chrome screenshots | **Large** |
| Resource usage | Modest CPU, low RAM | 2-4GB RAM for Chrome | **Medium** |
| Audio processing | Native, full control | Delegates to FFmpeg internally | **Medium** |
| Stack simplicity | Works with any language | Requires Node.js + React | **Large** |
| Maturity for AV tasks | Decades of optimization | ~4 years old | **Medium** |
| Subtitle formats | Native ASS/SRT support | Must implement in HTML/CSS | **Medium** |

### Equivalent (No Real Difference)

- Ken Burns zoom/pan effects
- Basic slide/fade animations
- Video scaling/cropping
- Audio mixing and volume adjustment
- Output encoding (H.264, AAC)

## Integration with Python Pipeline

```
Python (data gathering) --> JSON file --> Node.js (Remotion) --> MP4 video
```

### Method 1: CLI (Simplest)
```python
import json, subprocess

props = {"headline": "...", "summary": "...", "clips": [...]}
with open('/tmp/props.json', 'w') as f:
    json.dump(props, f)

subprocess.run([
    'npx', 'remotion', 'render',
    'src/compositions/VideoTemplate.tsx',
    'output.mp4',
    '--props=/tmp/props.json'
])
```

### Method 2: Python SDK (Lambda only)
```bash
pip install remotion-python
```
Handles large props via S3, but requires AWS Lambda setup.

## Performance Comparison

| Metric | FFmpeg | Remotion (Local) |
|--------|--------|-----------------|
| 60s video @ 1080x1920 30fps | ~1-3 min | ~5-15 min |
| RAM usage | <500MB | 2-4GB |
| CPU usage | Moderate | High (Chrome rendering) |
| Concurrent renders | Easy | RAM-limited |

## When to Choose Remotion

**Use Remotion when:**
- Visual design is complex and frequently iterated
- You need rich text animations, spring physics, or choreographed multi-element sequences
- You want data-driven template variants (different visuals per content category)
- Design iteration speed matters more than render speed
- You're already in a Node.js/React ecosystem
- You need a preview/studio UI for non-technical designers

**Use FFmpeg when:**
- Video assembly is a known, stable composition (background + overlays + audio)
- Rendering speed matters (batch processing, tight schedules)
- Stack simplicity matters (pure Python, no Node.js)
- Animations are basic (slide, fade, zoom)
- Audio processing is a major component
- Resource constraints exist (low RAM, shared server)

## Remotion Features Worth Knowing

Even if not migrating, these are capabilities to revisit if needs change:

1. **`@remotion/animated-emoji`** - Animated emoji overlays
2. **`@remotion/motion-blur`** - Motion blur on any element
3. **`@remotion/transitions`** - 15+ transition presets (slide, fade, wipe, clock wipe, etc.)
4. **`@remotion/noise`** - Procedural noise for organic effects
5. **`@remotion/lottie`** - Lottie animation embedding
6. **Spring physics** - `spring({fps, frame, config: {damping, mass, stiffness}})` for organic motion
7. **Remotion Studio** - Browser-based preview with timeline, props editor, render queue
8. **`calculateMetadata()`** - Dynamic video duration/dimensions based on input data

## Sources

- [Remotion Docs](https://www.remotion.dev/docs/)
- [Remotion License](https://www.remotion.dev/docs/license)
- [Remotion vs FFmpeg](https://www.remotion.dev/docs/ffmpeg)
- [Lambda Cost Examples](https://www.remotion.dev/docs/lambda/cost-example)
- [Performance Tips](https://www.remotion.dev/docs/performance)
- [Python Integration](https://www.remotion.dev/docs/lambda/python)
- [Animated Text](https://www.remotion.dev/docs/animated-text)
