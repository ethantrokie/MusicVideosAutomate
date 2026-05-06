# SVG Educational Diagrams Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace fal.ai raster educational images with Claude-generated SVG diagrams that have individually animatable elements, rendered with Rough.js hand-drawn styling in Remotion.

**Architecture:** Claude generates structured SVG code with semantic `<g>` groups via `claude -p`. Each group has `data-order` and `data-delay` attributes controlling animation sequence. A new Remotion component parses the SVG, applies Rough.js hand-drawn styling to shapes, and animates each group with spring physics. Complex objects can be embedded via fal.ai `<image>` elements within the SVG.

**Tech Stack:** Python (SVG generation agent), Claude CLI (`claude -p` with vision), Remotion (React/TypeScript), Rough.js, svg-parser, fal.ai (optional embeds)

---

## File Structure

### New files

```
agents/generate_edu_svg.py                              # SVG generation agent (replaces generate_educational_images.py + analyze_edu_image_regions.py)
agents/prompts/svg_diagram_prompt.md                    # System prompt for Claude SVG generation
agents/remotion/src/compositions/EduSvgDiagram.tsx      # Remotion component for animated SVG diagrams
agents/remotion/src/utils/svgToReact.ts                 # SVG parser → React element converter with Rough.js
tests/test_generate_edu_svg.py                          # Tests for SVG generation agent
tests/test_svg_props_builder.py                         # Tests for props builder SVG handling
```

### Modified files

```
agents/remotion/src/types.ts                            # Replace EduImage with EduDiagram
agents/remotion/src/compositions/OverlayComposition.tsx  # Swap EduImageRegions → EduSvgDiagram
agents/remotion/package.json                            # Add roughjs, svg-parser deps
agents/remotion_props_builder.py                        # Rewrite _build_edu_images → _build_edu_diagrams
agents/render_remotion_overlays.py                      # Update embedded image handling
pipeline.sh                                             # Replace Stage 4.6/4.7
config/config.json                                      # Update educational_images config
```

### Deleted files

```
agents/remotion/src/compositions/EduImageRegions.tsx     # Replaced by EduSvgDiagram
agents/generate_educational_images.py                    # Replaced by generate_edu_svg.py
agents/analyze_edu_image_regions.py                      # No longer needed (SVG structure IS the animation plan)
tests/test_analyze_edu_image_regions.py                  # No longer needed
tests/test_educational_images.py                         # No longer needed (replaced by test_generate_edu_svg.py)
```

---

## Task 1: SVG Validation and Parsing Utilities (Python)

**Files:**
- Create: `agents/generate_edu_svg.py` (validation functions only)
- Create: `tests/test_generate_edu_svg.py`

TDD: Write tests for SVG validation and parsing FIRST, then implement.

- [ ] **Step 1: Write failing tests for SVG validation**

Create `tests/test_generate_edu_svg.py`:

```python
import json
import pytest
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "agents"))


def test_validate_svg_accepts_valid_svg():
    from generate_edu_svg import validate_svg

    svg = '''<svg viewBox="0 0 1080 720" xmlns="http://www.w3.org/2000/svg">
      <rect width="1080" height="720" fill="#1a1a2e"/>
      <g id="title" data-order="1" data-delay="0">
        <text x="540" y="80" fill="#ffd700">Hello</text>
      </g>
      <g id="detail" data-order="2" data-delay="800">
        <rect x="200" y="300" width="120" height="180" fill="none" stroke="#e0e0e0"/>
      </g>
    </svg>'''

    result = validate_svg(svg)
    assert result["valid"] is True
    assert result["group_count"] == 2
    assert result["has_background"] is True


def test_validate_svg_rejects_malformed_xml():
    from generate_edu_svg import validate_svg

    result = validate_svg("<svg><g><not closed")
    assert result["valid"] is False
    assert "malformed" in result["reason"].lower() or "parse" in result["reason"].lower()


def test_validate_svg_rejects_no_groups():
    from generate_edu_svg import validate_svg

    svg = '<svg viewBox="0 0 1080 720"><rect width="100" height="100"/></svg>'
    result = validate_svg(svg)
    assert result["valid"] is False
    assert "group" in result["reason"].lower()


def test_validate_svg_rejects_missing_data_order():
    from generate_edu_svg import validate_svg

    svg = '''<svg viewBox="0 0 1080 720">
      <g id="no-order"><rect x="0" y="0" width="100" height="100"/></g>
    </svg>'''
    result = validate_svg(svg)
    assert result["valid"] is False


def test_extract_groups_returns_ordered_groups():
    from generate_edu_svg import extract_groups

    svg = '''<svg viewBox="0 0 1080 720" xmlns="http://www.w3.org/2000/svg">
      <g id="second" data-order="2" data-delay="800">
        <rect x="200" y="300" width="120" height="180"/>
      </g>
      <g id="first" data-order="1" data-delay="0">
        <text x="540" y="80">Title</text>
      </g>
      <g id="also-first" data-order="1" data-delay="0">
        <circle cx="100" cy="100" r="50"/>
      </g>
    </svg>'''

    groups = extract_groups(svg)
    assert len(groups) == 3
    # Should be sorted by data-order
    assert groups[0]["id"] == "first"
    assert groups[1]["id"] == "also-first"
    assert groups[2]["id"] == "second"
    assert groups[0]["order"] == 1
    assert groups[2]["order"] == 2
    assert groups[2]["delay_ms"] == 800


def test_extract_fal_placeholders():
    from generate_edu_svg import extract_fal_placeholders

    svg = '''<svg viewBox="0 0 1080 720">
      <g id="obj" data-order="1" data-delay="0">
        <image data-fal-prompt="a hydraulic piston in chalk style" x="100" y="200" width="300" height="200"/>
      </g>
      <g id="label" data-order="2" data-delay="500">
        <text x="250" y="420">PISTON</text>
      </g>
    </svg>'''

    placeholders = extract_fal_placeholders(svg)
    assert len(placeholders) == 1
    assert placeholders[0]["prompt"] == "a hydraulic piston in chalk style"
    assert placeholders[0]["x"] == 100
    assert placeholders[0]["width"] == 300


def test_replace_fal_placeholder():
    from generate_edu_svg import replace_fal_placeholder

    svg = '''<svg><g id="obj" data-order="1" data-delay="0">
        <image data-fal-prompt="a piston" x="100" y="200" width="300" height="200"/>
      </g></svg>'''

    result = replace_fal_placeholder(svg, "a piston", "piston_001.png")
    assert 'data-fal-prompt' not in result
    assert 'href="piston_001.png"' in result
    assert 'x="100"' in result


def test_parse_claude_response_extracts_svg():
    from generate_edu_svg import parse_claude_response

    response = '''Here is the SVG diagram:

```svg
<svg viewBox="0 0 1080 720" xmlns="http://www.w3.org/2000/svg">
  <g id="title" data-order="1" data-delay="0">
    <text x="540" y="80">Test</text>
  </g>
</svg>
```

This diagram shows the concept.'''

    svg = parse_claude_response(response)
    assert svg is not None
    assert '<svg' in svg
    assert 'data-order' in svg


def test_parse_claude_response_handles_raw_svg():
    from generate_edu_svg import parse_claude_response

    response = '<svg viewBox="0 0 1080 720"><g id="a" data-order="1" data-delay="0"><rect/></g></svg>'
    svg = parse_claude_response(response)
    assert svg is not None


def test_parse_claude_response_returns_none_for_invalid():
    from generate_edu_svg import parse_claude_response

    assert parse_claude_response("no svg here at all") is None
    assert parse_claude_response("") is None
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
./venv/bin/python -m pytest tests/test_generate_edu_svg.py -v
```

Expected: ImportError -- `generate_edu_svg` not found.

- [ ] **Step 3: Implement validation and parsing functions**

Create `agents/generate_edu_svg.py` with these functions:

- `validate_svg(svg_string) -> dict` -- parses XML, checks for `<g>` elements with `data-order`, returns `{"valid": bool, "reason": str, "group_count": int, "has_background": bool}`
- `extract_groups(svg_string) -> list` -- extracts groups with id, order, delay_ms, sorted by order
- `extract_fal_placeholders(svg_string) -> list` -- finds `<image data-fal-prompt="...">` elements
- `replace_fal_placeholder(svg_string, prompt, filename) -> str` -- replaces placeholder with `href`
- `parse_claude_response(response) -> Optional[str]` -- extracts SVG from Claude's response (handles markdown fences, preamble text)

Use `xml.etree.ElementTree` for XML parsing (stdlib, no deps). Reuse the `_extract_json_from_text` pattern from `analyze_edu_image_regions.py` for extracting SVG from Claude responses.

- [ ] **Step 4: Run tests to verify they pass**

```bash
./venv/bin/python -m pytest tests/test_generate_edu_svg.py -v
```

Expected: All 9 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add agents/generate_edu_svg.py tests/test_generate_edu_svg.py
git commit -m "feat: SVG validation and parsing utilities with TDD tests"
```

---

## Task 2: SVG Generation Agent (Claude Integration)

**Files:**
- Modify: `agents/generate_edu_svg.py` (add generation logic)
- Create: `agents/prompts/svg_diagram_prompt.md`
- Modify: `tests/test_generate_edu_svg.py` (add generation tests)

- [ ] **Step 1: Write failing tests for SVG generation**

Add to `tests/test_generate_edu_svg.py`:

```python
from unittest.mock import patch, MagicMock


def test_generate_single_svg_calls_claude(tmp_path):
    from generate_edu_svg import generate_single_svg

    mock_svg = '''<svg viewBox="0 0 1080 720" xmlns="http://www.w3.org/2000/svg">
      <rect width="1080" height="720" fill="#1a1a2e"/>
      <g id="title" data-order="1" data-delay="0">
        <text x="540" y="80" fill="#ffd700">Test</text>
      </g>
      <g id="detail" data-order="2" data-delay="800">
        <rect x="200" y="300" width="120" height="180" stroke="#e0e0e0"/>
      </g>
    </svg>'''

    with patch("generate_edu_svg._call_claude_svg") as mock_call:
        mock_call.return_value = mock_svg
        result = generate_single_svg(
            key_fact="Force equals pressure times area",
            topic="Hydraulic systems",
        )

    assert result is not None
    assert result["svg_content"] is not None
    assert result["group_count"] == 2
    assert result["generation_status"] == "success"
    mock_call.assert_called_once()


def test_generate_single_svg_retries_on_invalid():
    from generate_edu_svg import generate_single_svg

    invalid_svg = "<svg><not valid</svg>"
    valid_svg = '''<svg viewBox="0 0 1080 720">
      <g id="a" data-order="1" data-delay="0"><rect x="0" y="0" width="100" height="100"/></g>
      <g id="b" data-order="2" data-delay="500"><text x="50" y="50">B</text></g>
    </svg>'''

    with patch("generate_edu_svg._call_claude_svg") as mock_call:
        mock_call.side_effect = [invalid_svg, valid_svg]
        result = generate_single_svg(
            key_fact="Test concept",
            topic="Test topic",
        )

    assert result["generation_status"] == "success"
    assert mock_call.call_count == 2  # Retried once


def test_generate_single_svg_falls_back_on_double_failure():
    from generate_edu_svg import generate_single_svg

    with patch("generate_edu_svg._call_claude_svg") as mock_call:
        mock_call.return_value = None
        result = generate_single_svg(
            key_fact="Test concept",
            topic="Test topic",
        )

    assert result["generation_status"] == "fallback"
    assert result.get("svg_content") is None
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
./venv/bin/python -m pytest tests/test_generate_edu_svg.py::test_generate_single_svg_calls_claude -v
```

- [ ] **Step 3: Create the SVG system prompt**

Create `agents/prompts/svg_diagram_prompt.md` with the full system prompt including:
- SVG structure requirements (viewBox, groups, data-order, data-delay)
- Color scheme (#1a1a2e background, #e0e0e0 strokes, #ffd700 accents)
- The concrete example SVG snippet from the spec
- Instructions for `<image data-fal-prompt="...">` placeholders
- Pedagogical ordering guidance
- 50KB size limit

The prompt should reference the 6 images at `agents/svg_reference_images/ref_*.png` for Claude to read.

- [ ] **Step 4: Implement generation functions**

Add to `agents/generate_edu_svg.py`:

- `_call_claude_svg(key_fact, topic) -> Optional[str]` -- calls `claude -p` with the SVG prompt, returns raw SVG or None. Uses 30-min timeout with the background+kill pattern from other agents.
- `generate_single_svg(key_fact, topic) -> dict` -- calls `_call_claude_svg`, validates, retries once on failure, returns `{"svg_content", "group_count", "generation_status", "embedded_images"}`. Falls back to `{"generation_status": "fallback"}` if both attempts fail.
- `_render_fal_embeds(svg_content, output_dir) -> str` -- for each `<image data-fal-prompt>`, calls fal.ai, saves PNG, replaces placeholder. Port the `generate_image()` function from `generate_educational_images.py` into this file (copy, don't import -- the old file is deleted in Task 8).
- `select_concepts_and_timing(topic, key_facts, phrase_groups, count) -> list` -- port the concept selection logic from `generate_educational_images.py`'s `select_concepts_and_prompts()`. This calls Claude to pick which key facts to illustrate, match them to phrase group timings, and enforce placement constraints (verse sections only, 3s minimum gap, even distribution). The output is a list of `{"key_fact", "start_time", "end_time", "duration", "matched_phrase_group"}` dicts -- same as current but without image prompts.
- `generate_all_svgs(run_dir) -> None` -- main orchestrator. Loads research.json for key_facts and topic, loads phrase_groups.json for timing, calls `select_concepts_and_timing` to pick concepts, calls `generate_single_svg` per concept, writes `edu_svg_manifest.json`.
- `main()` -- CLI entry point. Reads config for `svg_model` and passes to generation functions.

- [ ] **Step 5: Run all tests**

```bash
./venv/bin/python -m pytest tests/test_generate_edu_svg.py -v
```

- [ ] **Step 6: Commit**

```bash
git add agents/generate_edu_svg.py agents/prompts/svg_diagram_prompt.md tests/test_generate_edu_svg.py
git commit -m "feat: SVG generation agent with Claude integration and retry logic"
```

---

## Task 3: Remotion Types and Props Builder

**Files:**
- Modify: `agents/remotion/src/types.ts`
- Modify: `agents/remotion_props_builder.py`
- Create: `tests/test_svg_props_builder.py`
- Modify: `agents/render_remotion_overlays.py`

- [ ] **Step 1: Write failing tests for SVG props builder**

Create `tests/test_svg_props_builder.py`:

```python
import json
import pytest
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "agents"))


def _make_config():
    return {
        "video_settings": {"resolution": [1080, 1920], "fps": 30},
        "remotion_overlay": {"enabled": True, "karaoke_enabled": True,
                             "edu_reveal_enabled": True, "transitions_enabled": False},
    }


def test_build_edu_diagrams_from_svg_manifest(tmp_path):
    from remotion_props_builder import build_overlay_props

    (tmp_path / "research.json").write_text(json.dumps({"video_title": "Test"}))
    (tmp_path / "phrase_groups.json").write_text(json.dumps([]))
    (tmp_path / "approved_media.json").write_text(json.dumps({"shot_list": []}))

    edu_dir = tmp_path / "educational_images"
    edu_dir.mkdir()
    manifest = {
        "format": "svg",
        "diagrams": [
            {
                "id": 1,
                "key_fact": "Force equals pressure times area",
                "svg_content": '<svg viewBox="0 0 1080 720"><g id="a" data-order="1" data-delay="0"><text>A</text></g></svg>',
                "start_time": 5.0,
                "end_time": 11.0,
                "generation_status": "success",
            },
        ],
    }
    (edu_dir / "edu_svg_manifest.json").write_text(json.dumps(manifest))

    props = build_overlay_props(tmp_path, _make_config(), "short_intro", 60000)

    assert len(props["eduDiagrams"]) == 1
    assert "<svg" in props["eduDiagrams"][0]["svgContent"]
    assert props["eduDiagrams"][0]["startMs"] == 5000
    assert props["eduDiagrams"][0]["endMs"] == 11000
    assert props["eduDiagrams"][0]["concept"] == "Force equals pressure times area"


def test_build_edu_diagrams_skips_fallback_entries(tmp_path):
    from remotion_props_builder import build_overlay_props

    (tmp_path / "research.json").write_text(json.dumps({"video_title": "Test"}))
    (tmp_path / "phrase_groups.json").write_text(json.dumps([]))
    (tmp_path / "approved_media.json").write_text(json.dumps({"shot_list": []}))

    edu_dir = tmp_path / "educational_images"
    edu_dir.mkdir()
    manifest = {
        "format": "svg",
        "diagrams": [
            {"id": 1, "key_fact": "A", "svg_content": "<svg>...</svg>",
             "start_time": 5.0, "end_time": 11.0, "generation_status": "success"},
            {"id": 2, "key_fact": "B", "svg_content": None,
             "start_time": 15.0, "end_time": 21.0, "generation_status": "fallback"},
        ],
    }
    (edu_dir / "edu_svg_manifest.json").write_text(json.dumps(manifest))

    props = build_overlay_props(tmp_path, _make_config(), "short_intro", 60000)

    # Only the successful SVG should be included
    assert len(props["eduDiagrams"]) == 1
    assert props["eduDiagrams"][0]["concept"] == "A"


def test_segment_offset_shifts_diagram_times(tmp_path):
    from remotion_props_builder import build_overlay_props

    (tmp_path / "research.json").write_text(json.dumps({"video_title": "Test"}))
    (tmp_path / "phrase_groups.json").write_text(json.dumps([]))
    (tmp_path / "approved_media.json").write_text(json.dumps({"shot_list": []}))

    edu_dir = tmp_path / "educational_images"
    edu_dir.mkdir()
    manifest = {
        "format": "svg",
        "diagrams": [
            {"id": 1, "key_fact": "A", "svg_content": "<svg>...</svg>",
             "start_time": 50.0, "end_time": 56.0, "generation_status": "success"},
        ],
    }
    (edu_dir / "edu_svg_manifest.json").write_text(json.dumps(manifest))

    # Hook short starting at 44s
    props = build_overlay_props(tmp_path, _make_config(), "short_hook", 15000, segment_start_s=44.0)

    assert len(props["eduDiagrams"]) == 1
    assert props["eduDiagrams"][0]["startMs"] == 6000   # 50000 - 44000
    assert props["eduDiagrams"][0]["endMs"] == 12000    # 56000 - 44000


def test_old_raster_manifest_ignored_when_svg_exists(tmp_path):
    """When both old raster and new SVG manifests exist, SVG wins."""
    from remotion_props_builder import build_overlay_props

    (tmp_path / "research.json").write_text(json.dumps({"video_title": "Test"}))
    (tmp_path / "phrase_groups.json").write_text(json.dumps([]))
    (tmp_path / "approved_media.json").write_text(json.dumps({"shot_list": []}))

    edu_dir = tmp_path / "educational_images"
    edu_dir.mkdir()

    # Old raster manifest
    old_manifest = {"images": [{"id": 1, "file": "img.png", "start_time": 5, "end_time": 8}]}
    (edu_dir / "edu_image_manifest.json").write_text(json.dumps(old_manifest))

    # New SVG manifest
    svg_manifest = {
        "format": "svg",
        "diagrams": [
            {"id": 1, "key_fact": "SVG concept", "svg_content": "<svg>...</svg>",
             "start_time": 5.0, "end_time": 11.0, "generation_status": "success"},
        ],
    }
    (edu_dir / "edu_svg_manifest.json").write_text(json.dumps(svg_manifest))

    props = build_overlay_props(tmp_path, _make_config(), "full", 180000)

    # Should use SVG, not raster
    assert "eduDiagrams" in props
    assert len(props["eduDiagrams"]) == 1
    assert props["eduDiagrams"][0]["concept"] == "SVG concept"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
./venv/bin/python -m pytest tests/test_svg_props_builder.py -v
```

- [ ] **Step 3: Update types.ts**

In `agents/remotion/src/types.ts`:

Add new `EduDiagram` interface (keep `EduImage` and `ImageRegion` temporarily for backward compat):

```ts
export interface EduDiagram {
  svgContent: string;
  concept: string;
  startMs: number;
  endMs: number;
}
```

Update `OverlayProps` to include `eduDiagrams`:

```ts
export interface OverlayProps {
  // ... existing fields ...
  eduImages: EduImage[];       // Keep for backward compat during transition
  eduDiagrams: EduDiagram[];   // New SVG diagrams
  // ... rest ...
}
```

- [ ] **Step 4: Update props builder**

In `agents/remotion_props_builder.py`:

Add `_build_edu_diagrams(run_dir)` function that:
1. Checks for `edu_svg_manifest.json` first (new format)
2. Falls back to `edu_image_manifest.json` (old format, returns empty list for diagrams)
3. Returns list of `{"svgContent", "concept", "startMs", "endMs"}` dicts

Update `build_overlay_props` to:
1. Call `_build_edu_diagrams` alongside `_build_edu_images`
2. Include both `eduImages` and `eduDiagrams` in the output
3. Apply segment offset shifting to `eduDiagrams` the same way as `eduImages`

- [ ] **Step 5: Update render orchestrator**

In `agents/render_remotion_overlays.py`, update the embedded image copying to also handle SVG-referenced images:

```python
    # Copy embedded images from SVG diagrams to Remotion's public/
    for diagram in props.get("eduDiagrams", []):
        svg = diagram.get("svgContent", "")
        # Find any href="filename.png" in the SVG
        import re
        for match in re.finditer(r'href="([^"]+\.png)"', svg):
            filename = match.group(1)
            src_path = run_dir / "educational_images" / filename
            if src_path.exists():
                dest = public_dir / filename
                shutil.copy2(str(src_path), str(dest))
```

- [ ] **Step 6: Run all tests**

```bash
./venv/bin/python -m pytest tests/test_svg_props_builder.py tests/test_remotion_props_builder.py -v
```

- [ ] **Step 7: Commit**

```bash
git add agents/remotion/src/types.ts agents/remotion_props_builder.py agents/render_remotion_overlays.py tests/test_svg_props_builder.py
git commit -m "feat: EduDiagram type and props builder with SVG manifest support"
```

---

## Task 4: SVG-to-React Converter with Rough.js

**Files:**
- Create: `agents/remotion/src/utils/svgToReact.ts`
- Modify: `agents/remotion/package.json` (add deps)

- [ ] **Step 1: Install dependencies**

```bash
cd agents/remotion
npm install roughjs svg-parser
```

Note: If `@types/svg-parser` doesn't exist on npm, create a `src/utils/svg-parser.d.ts` declaration file:
```ts
declare module 'svg-parser' {
  interface Node { type: string; tagName?: string; properties?: Record<string, string>; children?: Node[]; value?: string; }
  function parse(source: string): { children: Node[] };
}
```

- [ ] **Step 2: Write failing tests for svgToReact utilities**

Create `agents/remotion/src/utils/__tests__/svgToReact.test.ts`:

```ts
import { parseSvgGroups, isSimplePath } from "../svgToReact";

describe("parseSvgGroups", () => {
  it("extracts groups sorted by data-order", () => {
    const svg = `<svg viewBox="0 0 1080 720">
      <g id="b" data-order="2" data-delay="800"><rect x="0" y="0" width="100" height="100"/></g>
      <g id="a" data-order="1" data-delay="0"><text>Hello</text></g>
    </svg>`;
    const groups = parseSvgGroups(svg);
    expect(groups).toHaveLength(2);
    expect(groups[0].id).toBe("a");
    expect(groups[0].order).toBe(1);
    expect(groups[1].id).toBe("b");
    expect(groups[1].delayMs).toBe(800);
  });

  it("groups same data-order elements together", () => {
    const svg = `<svg viewBox="0 0 1080 720">
      <g id="left" data-order="1" data-delay="0"><rect/></g>
      <g id="right" data-order="1" data-delay="0"><rect/></g>
      <g id="later" data-order="2" data-delay="600"><text>X</text></g>
    </svg>`;
    const groups = parseSvgGroups(svg);
    expect(groups).toHaveLength(3);
    expect(groups[0].order).toBe(1);
    expect(groups[1].order).toBe(1);
    expect(groups[2].order).toBe(2);
  });

  it("returns empty array for SVG with no groups", () => {
    const svg = `<svg viewBox="0 0 1080 720"><rect/></svg>`;
    expect(parseSvgGroups(svg)).toHaveLength(0);
  });
});

describe("isSimplePath", () => {
  it("returns true for short paths without cubic beziers", () => {
    expect(isSimplePath("M 10 10 L 100 100")).toBe(true);
    expect(isSimplePath("M 0 0 Q 50 50 100 0")).toBe(true);
  });

  it("returns false for long paths", () => {
    const longPath = "M 0 0 " + "L 10 10 ".repeat(100);
    expect(isSimplePath(longPath)).toBe(false);
  });

  it("returns false for cubic bezier paths", () => {
    expect(isSimplePath("M 0 0 C 10 20 30 40 50 60")).toBe(false);
  });
});
```

Run: `cd agents/remotion && npx jest src/utils/__tests__/svgToReact.test.ts` (or configure test runner).

- [ ] **Step 3: Create svgToReact.ts**

Create `agents/remotion/src/utils/svgToReact.ts`:

This module exports:

- `parseSvgGroups(svgContent: string) -> SvgGroup[]` -- parses SVG, extracts groups sorted by `data-order`, each group with its children elements
- `svgElementToReact(element, roughSvg, seed) -> React.ReactNode` -- converts a single SVG element to a React element, applying Rough.js to shapes
- `isSimplePath(d: string) -> boolean` -- returns true if path is simple enough for Rough.js (<500 chars, no cubic Beziers)

Types:
```ts
interface SvgGroup {
  id: string;
  order: number;
  delayMs: number;
  children: SvgElement[];
}

interface SvgElement {
  tagName: string;
  properties: Record<string, string>;
  children?: SvgElement[];
}
```

Rough.js integration:
- Create `rough.svg(svgElement)` renderer once per component
- For `rect`: `roughSvg.rectangle(x, y, w, h, {seed, roughness: 1.5, stroke, strokeWidth})`
- For `circle`: `roughSvg.circle(cx, cy, diameter, {seed, ...})`
- For `ellipse`: `roughSvg.ellipse(cx, cy, w, h, {seed, ...})`
- For `line`: `roughSvg.line(x1, y1, x2, y2, {seed, ...})`
- For simple `path`: `roughSvg.path(d, {seed, ...})`
- For complex `path`: render as standard SVG `<path>` with `strokeDasharray: "4 2"` for hand-drawn feel
- For `text`: render as `<text>` with `fontFamily: "'Caveat', 'Patrick Hand', cursive, sans-serif"`
- For `image`: render as Remotion `<Img src={staticFile(href)}>`
- For `polygon`/`polyline`: render as standard SVG (Rough.js doesn't handle these natively)

- [ ] **Step 4: Run tests to verify they pass**

- [ ] **Step 5: Commit**

```bash
git add agents/remotion/package.json agents/remotion/package-lock.json agents/remotion/src/utils/svgToReact.ts agents/remotion/src/utils/__tests__/
git commit -m "feat: SVG-to-React converter with Rough.js hand-drawn styling"
```

---

## Task 5: EduSvgDiagram Remotion Component

**Files:**
- Create: `agents/remotion/src/compositions/EduSvgDiagram.tsx`
- Modify: `agents/remotion/src/compositions/OverlayComposition.tsx`
- Delete: `agents/remotion/src/compositions/EduImageRegions.tsx`

- [ ] **Step 1: Create EduSvgDiagram.tsx**

The component:
1. Receives `svgContent`, `concept`, and timing props
2. Calls `parseSvgGroups(svgContent)` to extract animated groups
3. Creates a Rough.js SVG renderer with deterministic seeds
4. Renders inside a positioned container (centered in 1080x1920 at y=600, 1080x720 viewport)
5. Each group animates via `<Sequence>` with spring fade-in (opacity 0→1) and scale (0.95→1.0)
6. Groups with same `data-order` share the same `<Sequence from={...}>`
7. Concept label appears above the diagram after all groups visible
8. Exit fade over last 0.5s

```tsx
import React, { useMemo, useRef } from "react";
import {
  AbsoluteFill, Sequence, Img, staticFile,
  useCurrentFrame, useVideoConfig, interpolate, spring,
} from "remotion";
import rough from "roughjs";
import { parseSvgGroups, svgElementToReact } from "../utils/svgToReact";

interface EduSvgDiagramProps {
  svgContent: string;
  concept: string;
}

// ... component implementation
```

- [ ] **Step 2: Update OverlayComposition.tsx**

- Add import for `EduSvgDiagram`
- Add rendering block for `eduDiagrams` array (alongside existing `eduImages` block)
- Each diagram wrapped in `<Sequence>` at correct frame offset

```tsx
import { EduSvgDiagram } from "./EduSvgDiagram";

// In the render:
{/* SVG Diagrams (new) */}
{eduRevealEnabled && props.eduDiagrams?.map((diagram, i) => {
  const startFrame = Math.round((diagram.startMs / 1000) * fps);
  const durationFrames = Math.round(((diagram.endMs - diagram.startMs) / 1000) * fps);
  return (
    <Sequence key={`svg-${i}`} from={startFrame} durationInFrames={durationFrames}>
      <EduSvgDiagram svgContent={diagram.svgContent} concept={diagram.concept} />
    </Sequence>
  );
})}
```

- [ ] **Step 3: Delete EduImageRegions.tsx**

```bash
rm agents/remotion/src/compositions/EduImageRegions.tsx
```

Remove the `EduImageRegions` import and its rendering block from OverlayComposition.tsx entirely. The `eduImages` prop remains in `OverlayProps` for type compatibility but nothing renders it -- the new `eduDiagrams` block handles all educational content.

- [ ] **Step 4: Test with Remotion Studio**

```bash
cd agents/remotion && npx remotion studio
```

Preview with test SVG props. Verify:
- SVG renders centered in the portrait frame
- Rough.js makes shapes look hand-drawn
- Groups animate in sequence
- Text renders cleanly without Rough.js
- Concept label appears after all groups

- [ ] **Step 5: Commit**

```bash
git add agents/remotion/src/compositions/EduSvgDiagram.tsx agents/remotion/src/compositions/OverlayComposition.tsx
git rm agents/remotion/src/compositions/EduImageRegions.tsx
git commit -m "feat: EduSvgDiagram component with Rough.js and sequential animation"
```

---

## Task 6: Pipeline Integration

**Files:**
- Modify: `pipeline.sh`
- Modify: `config/config.json`

- [ ] **Step 1: Update pipeline.sh**

Replace Stage 4.6 content:

```bash
# Stage 4.6: Educational SVG Diagram Generation
if [ $START_STAGE -le 4 ]; then
    # ... check edu images enabled ...
    echo "🎨 Generating educational SVG diagrams..."
    if ./venv/bin/python3 agents/generate_edu_svg.py; then
        echo "✅ SVG diagram generation complete"
    else
        echo -e "${YELLOW}⚠️  SVG diagram generation failed, will use stock footage only${NC}"
    fi
fi
```

Remove Stage 4.7 (region analysis) entirely.

- [ ] **Step 2: Update config.json**

Add SVG-specific config:

```json
"educational_images": {
    "enabled": true,
    "count": 8,
    "duration_seconds": 6.0,
    "svg_model": "claude-sonnet-4-6",
    "fal_embed_model": "fal-ai/reve/text-to-image",
    "style": "hand-drawn whiteboard sketch, dark charcoal background, white chalk-like lines"
}
```

- [ ] **Step 3: Commit**

```bash
git add pipeline.sh config/config.json
git commit -m "feat: pipeline integration for SVG diagram generation"
```

---

## Task 7: End-to-End Test

**Files:** None (validation only)

- [ ] **Step 1: Run SVG generation on a real topic**

```bash
# Use a recent run's research data
export OUTPUT_DIR=outputs/runs/20260419_090057
./venv/bin/python3 agents/generate_edu_svg.py
```

Verify manifest created with SVG content.

- [ ] **Step 2: Inspect generated SVGs**

```bash
python3 -c "
import json
with open('outputs/runs/20260419_090057/educational_images/edu_svg_manifest.json') as f:
    m = json.load(f)
for d in m['diagrams'][:3]:
    print(f'[{d[\"id\"]}] {d[\"key_fact\"][:50]}')
    print(f'  Status: {d[\"generation_status\"]}')
    print(f'  Groups: {d.get(\"group_count\", \"?\")}')
    print(f'  SVG size: {len(d.get(\"svg_content\", \"\"))} chars')
    print()
"
```

- [ ] **Step 3: Rebuild video with SVG diagrams**

```bash
./venv/bin/python3 agents/build_multiformat_videos.py
./venv/bin/python3 agents/render_remotion_overlays.py \
  --run-dir=outputs/runs/20260419_090057 \
  --format=short_intro \
  --video=outputs/runs/20260419_090057/short_intro.mp4 \
  --duration-ms=60000
```

- [ ] **Step 4: Extract frames and verify**

```bash
VID=outputs/runs/20260419_090057/short_intro.mp4
# Capture at times where edu diagrams should appear
ffmpeg -y -ss 3 -i $VID -frames:v 1 /tmp/svg_test_first_group.png
ffmpeg -y -ss 5 -i $VID -frames:v 1 /tmp/svg_test_all_groups.png
ffmpeg -y -ss 7 -i $VID -frames:v 1 /tmp/svg_test_with_label.png
```

Verify:
- Shapes have hand-drawn Rough.js styling (not clean machine lines)
- Groups animate in sequentially (first group visible, then second appears)
- Text is readable
- Concept label appears above diagram
- Dark background matches the video aesthetic
- Any fal.ai embeds render correctly within the SVG

- [ ] **Step 5: Run full test suite**

```bash
./venv/bin/python -m pytest tests/ -v
```

Expected: All tests pass, no regressions.

- [ ] **Step 6: Open video for manual review**

```bash
open outputs/runs/20260419_090057/short_intro.mp4
```

---

## Task 8: Cleanup

**Files:**
- Delete: `agents/analyze_edu_image_regions.py`
- Delete: `tests/test_analyze_edu_image_regions.py`

- [ ] **Step 1: Remove deprecated files**

```bash
git rm agents/generate_educational_images.py agents/analyze_edu_image_regions.py
git rm tests/test_analyze_edu_image_regions.py tests/test_educational_images.py
```

- [ ] **Step 2: Run full test suite to confirm no breakage**

```bash
./venv/bin/python -m pytest tests/ -v
```

- [ ] **Step 3: Commit**

```bash
git add -A
git commit -m "chore: remove deprecated raster region analysis (replaced by SVG diagrams)"
```
