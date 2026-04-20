# Educational Image Animation Improvements Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix three remaining issues with the educational image region animation: (1) 34% fallback rate from unreliable Claude CLI subprocess, (2) single-object images get awkward splits with no pedagogical value, and (3) stock footage bleeding through region gaps during build-up.

**Architecture:** All three fixes are contained to two files -- the analyzer (`analyze_edu_image_regions.py`) and the Remotion component (`EduImageRegions.tsx`). The analyzer gets a retry on failure, a classification step to detect single-object images, and the Remotion component gets a dimmed full-image background layer behind the regions.

**Tech Stack:** Python subprocess (Claude CLI), Remotion (React/TypeScript)

---

## Problem 1: 34% Fallback Rate (Retry on Failure)

**Root cause:** The `claude -p` subprocess call sometimes returns invalid JSON, times out, or fails to start. This is transient -- the same image often succeeds on a second attempt.

**Fix:** Add a single retry loop around the subprocess call in `analyze_single_image`. If the first attempt fails to produce valid regions, wait 2 seconds and try once more. Only fall back to the simple L/R split if both attempts fail.

### Files
- Modify: `agents/analyze_edu_image_regions.py` (`analyze_single_image` function)
- Modify: `tests/test_analyze_edu_image_regions.py` (add retry test)

### Changes to `analyze_single_image`

Replace the single subprocess call with a loop of 2 attempts:

```python
def analyze_single_image(image_path: str) -> List[Dict]:
    """Analyze a single educational image using Claude Haiku vision."""
    width, height = _get_image_dimensions(image_path)

    max_attempts = 2
    for attempt in range(max_attempts):
        try:
            result = _call_claude_vision(image_path)
            if result:
                return result
        except Exception as e:
            print(f"  Attempt {attempt + 1} failed for {Path(image_path).name}: {e}")

        if attempt < max_attempts - 1:
            import time
            time.sleep(2)

    print(f"  Using fallback regions for {Path(image_path).name}")
    return _generate_fallback_regions(width, height)
```

Extract the actual Claude call into `_call_claude_vision` for clarity:

```python
def _call_claude_vision(image_path: str) -> Optional[List[Dict]]:
    """Call Claude Haiku vision and return validated regions, or None on failure."""
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
        return None
    return None
```

### Test

```python
def test_analyze_retries_on_first_failure(monkeypatch):
    """analyze_single_image retries once on failure before falling back."""
    from analyze_edu_image_regions import analyze_single_image
    call_count = 0

    def mock_call(image_path):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return None  # First attempt fails
        return [{"label": "A", "bounds": {"x": 0, "y": 0, "w": 100, "h": 100},
                 "order": 1, "from_direction": "left", "delay_ms": 800}]

    monkeypatch.setattr("analyze_edu_image_regions._call_claude_vision", mock_call)
    monkeypatch.setattr("analyze_edu_image_regions._get_image_dimensions", lambda p: (1248, 832))
    import analyze_edu_image_regions
    analyze_edu_image_regions.time = type('', (), {'sleep': lambda s: None})()

    regions = analyze_single_image("/fake/path.png")
    assert call_count == 2
    assert regions[0]["label"] == "A"
```

---

## Problem 2: Single-Object Images Get Awkward Splits (Classification Step)

**Root cause:** Images with one centered object (DNA helix, stamping press) don't have natural sub-regions. Claude either returns unhelpful splits or falls back to left/right halves, which cuts the object awkwardly.

**Fix:** Change the Claude prompt to FIRST classify the image, THEN decide how to handle it. The prompt asks Claude to output a `type` field:
- `"comparison"` -- side-by-side elements (split into regions)
- `"multi_element"` -- multiple distinct labeled parts (split into regions)
- `"single_object"` -- one centered element (skip regions, just fade in)
- `"process"` -- sequential steps (split top-to-bottom)

For `single_object` type, return an empty regions list. The Remotion component already handles empty regions with a simple fade-in.

### Files
- Modify: `agents/analyze_edu_image_regions.py` (update `ANALYSIS_PROMPT`, update parsing)
- Modify: `tests/test_analyze_edu_image_regions.py` (add classification test)

### New Prompt

```python
ANALYSIS_PROMPT = """Analyze this educational diagram image for animation in a music video.

STEP 1 - Classify the image type:
- "comparison": side-by-side elements comparing two things (e.g., sliding vs rolling, before vs after)
- "multi_element": multiple distinct labeled parts of a system (e.g., labeled diagram with 3+ components)
- "single_object": one centered object or illustration with minimal sub-parts (e.g., a DNA helix, a single machine)
- "process": sequential steps shown in order (e.g., step 1 -> step 2 -> step 3)

STEP 2 - Based on the type:
- For "comparison" or "multi_element": identify 2-4 key regions to animate separately
- For "single_object": return an empty regions array (the image will just fade in)
- For "process": identify 2-4 regions ordered by the process flow

For each region output:
- label: short name (2-4 words)
- bounds: bounding box as percentages {{x, y, w, h}} where 0,0 is top-left, values 0-100
- order: entrance order (1 = appears first)
- from_direction: "left", "right", "top", or "bottom"
- delay_ms: milliseconds to wait after previous region (0 for first, 800-1500 for others)

RULES:
- 2-4 regions max. Group labels with their diagram element.
- Bounds should generously cover each element including its label.
- First region = foundational context. Last region = key insight.

Output ONLY valid JSON, no markdown:
{{"type": "<classification>", "regions": [...]}}

{image_path}"""
```

### Parsing Changes

Update `_parse_region_response` to handle the new `{"type": ..., "regions": [...]}` format:

```python
def _parse_region_response(response: str) -> tuple:
    """Parse Claude's response into (image_type, regions_list)."""
    text = response.strip()
    # Strip markdown fences
    if text.startswith("```"):
        lines = text.split("\n")
        start = 1
        end = len(lines)
        for i in range(len(lines) - 1, 0, -1):
            if lines[i].strip() == "```":
                end = i
                break
        text = "\n".join(lines[start:end])

    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return data.get("type", "multi_element"), data.get("regions", [])
        if isinstance(data, list):
            # Backwards compat: old format was just a list
            return "multi_element", data
    except (json.JSONDecodeError, ValueError):
        pass
    return None, []
```

### Update `_call_claude_vision`

```python
def _call_claude_vision(image_path: str) -> Optional[tuple]:
    """Returns (image_type, validated_regions) or None on failure."""
    prompt = ANALYSIS_PROMPT.format(image_path=image_path)
    try:
        result = subprocess.run(
            [CLAUDE_CLI, "-p", prompt,
             "--model", "claude-haiku-4-5",
             "--dangerously-skip-permissions"],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode == 0 and result.stdout.strip():
            img_type, regions = _parse_region_response(result.stdout)
            if img_type == "single_object":
                return ("single_object", [])
            if regions:
                validated = _validate_regions(regions)
                if validated:
                    return (img_type or "multi_element", validated)
    except subprocess.TimeoutExpired:
        return None
    return None
```

### Update `analyze_single_image`

```python
def analyze_single_image(image_path: str) -> tuple:
    """Returns (image_type, regions_list)."""
    width, height = _get_image_dimensions(image_path)

    max_attempts = 2
    for attempt in range(max_attempts):
        result = _call_claude_vision(image_path)
        if result is not None:
            img_type, regions = result
            return (img_type, regions)

        if attempt < max_attempts - 1:
            import time
            time.sleep(2)

    return ("fallback", _generate_fallback_regions(width, height))
```

### Update `analyze_all_images`

Store the image type in the manifest:

```python
        img_type, regions = analyze_single_image(image_path)
        img["image_type"] = img_type
        img["regions"] = regions
```

### Test

```python
def test_single_object_returns_empty_regions():
    """Single-object classification returns empty regions."""
    from analyze_edu_image_regions import _parse_region_response

    response = '{"type": "single_object", "regions": []}'
    img_type, regions = _parse_region_response(response)
    assert img_type == "single_object"
    assert regions == []


def test_comparison_returns_regions():
    """Comparison classification returns regions normally."""
    from analyze_edu_image_regions import _parse_region_response

    response = '{"type": "comparison", "regions": [{"label": "A", "bounds": {"x": 0, "y": 0, "w": 50, "h": 100}, "order": 1, "from_direction": "left", "delay_ms": 0}]}'
    img_type, regions = _parse_region_response(response)
    assert img_type == "comparison"
    assert len(regions) == 1


def test_backwards_compat_plain_array():
    """Old format (plain JSON array) still works."""
    from analyze_edu_image_regions import _parse_region_response

    response = '[{"label": "A", "bounds": {"x": 0, "y": 0, "w": 100, "h": 100}, "order": 1, "from_direction": "left", "delay_ms": 0}]'
    img_type, regions = _parse_region_response(response)
    assert img_type == "multi_element"
    assert len(regions) == 1
```

---

## Problem 3: Stock Footage Bleeds Through Region Gaps (Dimmed Background Layer)

**Root cause:** During the region build-up phase, the areas between and around regions are transparent, so the base video's stock footage shows through. This is jarring -- you see half a ball bearing diagram next to sparks flying.

**Fix:** Add a dimmed (15% opacity) full image layer behind the regions in the Remotion component. This shows a faint silhouette of the complete diagram from the start, so gaps between regions show dim content instead of stock footage. When the full image fades in at the end, it goes from 15% to 100%.

This is the same idea as v2, but now it works because:
- The base video no longer has the edu image (MoviePy excluded it)
- The regions are overflow:hidden crops (positioned correctly)
- The dim base is just visual polish, not the primary animation mechanism

### Files
- Modify: `agents/remotion/src/compositions/EduImageRegions.tsx`

### Change

In the `return` statement of `EduImageRegions`, add a dimmed full image as the FIRST layer (behind regions):

```tsx
  return (
    <AbsoluteFill style={{ opacity: exitOpacity }}>
      {/* Layer 0: Dimmed full image silhouette (fills gaps between regions) */}
      <AbsoluteFill style={{ opacity: 0.15 }}>
        <Img
          src={imgSrc}
          style={{ width: "100%", height: "100%", objectFit: "contain" }}
        />
      </AbsoluteFill>

      {/* Layer 1: Bright regions appear one by one */}
      {regions.map((region, i) => (
        <Sequence key={i} from={regionTimings[i]}>
          <RegionPiece ... />
        </Sequence>
      ))}

      {/* Layer 2: Full image fades in after all regions */}
      <AbsoluteFill style={{ opacity: fullImageOpacity }}>
        <Img ... />
      </AbsoluteFill>

      {/* Layer 3: Concept label */}
      ...
    </AbsoluteFill>
  );
```

The dimmed layer sits at a constant 0.15 opacity. The bright regions (at 1.0 opacity) visually "pop" against it. When the full image fades in (0→1.0), it smoothly replaces both the dim background and the region crops.

No test needed -- this is a visual-only change verified by frame extraction.

---

## Execution Order

1. **Problem 1 (retry)** -- modify analyzer, add test, run tests
2. **Problem 2 (classification)** -- modify analyzer prompt + parsing, add tests, run tests
3. **Problem 3 (dim background)** -- modify Remotion component
4. **E2E test** -- re-analyze all images on March 24 run, rebuild, render, extract frames, verify

Problems 1 and 2 are both in the analyzer so they should be done together. Problem 3 is independent.
