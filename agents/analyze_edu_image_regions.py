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
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).parent))
from output_helper import get_output_path

CLAUDE_CLI = "/Users/ethantrokie/.local/bin/claude"

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

Output ONLY valid JSON, no markdown, no explanation:
{{"type": "<classification>", "regions": [...]}}

{image_path}"""


def _extract_json_from_text(text: str) -> Optional[str]:
    """
    Extract JSON from a response that may contain preamble text,
    markdown fences, or trailing explanation.
    """
    text = text.strip()

    # Try 1: Direct parse (response is pure JSON)
    try:
        json.loads(text)
        return text
    except (json.JSONDecodeError, ValueError):
        pass

    # Try 2: Strip markdown fences
    if "```" in text:
        # Find content between first ``` and last ```
        parts = text.split("```")
        for part in parts[1:]:
            # Remove optional language tag (e.g., "json\n")
            cleaned = re.sub(r"^[a-zA-Z]*\n", "", part.strip())
            try:
                json.loads(cleaned)
                return cleaned
            except (json.JSONDecodeError, ValueError):
                continue

    # Try 3: Find first { or [ and extract to matching closer
    for start_char, end_char in [("{", "}"), ("[", "]")]:
        start_idx = text.find(start_char)
        if start_idx == -1:
            continue
        # Find the matching closing bracket by counting depth
        depth = 0
        for i in range(start_idx, len(text)):
            if text[i] == start_char:
                depth += 1
            elif text[i] == end_char:
                depth -= 1
                if depth == 0:
                    candidate = text[start_idx:i + 1]
                    try:
                        json.loads(candidate)
                        return candidate
                    except (json.JSONDecodeError, ValueError):
                        break

    return None


def _parse_region_response(response: str) -> Tuple[Optional[str], List[Dict]]:
    """
    Parse Claude's response into (image_type, regions_list).

    Handles multiple response formats:
    - {"type": "...", "regions": [...]}  (new structured format)
    - [...]  (old plain array format, backwards compat)
    - Preamble text + JSON  (Claude adds explanation before JSON)
    - Markdown-fenced JSON
    """
    extracted = _extract_json_from_text(response)
    if not extracted:
        return None, []

    try:
        data = json.loads(extracted)
        if isinstance(data, dict):
            return data.get("type", "multi_element"), data.get("regions", [])
        if isinstance(data, list):
            return "multi_element", data
    except (json.JSONDecodeError, ValueError):
        pass

    return None, []


def _validate_regions(regions: List[Dict]) -> List[Dict]:
    """Validate and sanitize region data."""
    valid_directions = {"left", "right", "top", "bottom"}
    validated = []

    for region in regions[:4]:
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
            "delay_ms": max(800, min(2000, int(region.get("delay_ms", 800)))),
        })

    validated.sort(key=lambda r: r["order"])
    return validated


def _generate_fallback_regions(width: int, height: int) -> List[Dict]:
    """Generate simple split regions when vision analysis fails."""
    is_landscape = width > height

    if is_landscape:
        return [
            {"label": "Left half", "bounds": {"x": 0, "y": 0, "w": 50, "h": 100}, "order": 1, "from_direction": "left", "delay_ms": 0},
            {"label": "Right half", "bounds": {"x": 50, "y": 0, "w": 50, "h": 100}, "order": 2, "from_direction": "right", "delay_ms": 1000},
        ]
    else:
        return [
            {"label": "Top half", "bounds": {"x": 0, "y": 0, "w": 100, "h": 50}, "order": 1, "from_direction": "top", "delay_ms": 0},
            {"label": "Bottom half", "bounds": {"x": 0, "y": 50, "w": 100, "h": 50}, "order": 2, "from_direction": "bottom", "delay_ms": 1000},
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
    return 1248, 832


def _call_claude_vision(image_path: str) -> Optional[Tuple[str, List[Dict]]]:
    """
    Call Claude Haiku vision and return (image_type, validated_regions).
    Returns None on failure.
    """
    prompt = ANALYSIS_PROMPT.format(image_path=image_path)
    try:
        result = subprocess.run(
            [CLAUDE_CLI, "-p", prompt,
             "--model", "claude-haiku-4-5",
             "--dangerously-skip-permissions"],
            capture_output=True, text=True, timeout=45,
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


def analyze_single_image(image_path: str) -> Tuple[str, List[Dict]]:
    """
    Analyze a single educational image using Claude Haiku vision.
    Retries once on failure before falling back.

    Returns:
        Tuple of (image_type, regions_list).
        image_type is one of: "comparison", "multi_element", "single_object", "process", "fallback"
    """
    width, height = _get_image_dimensions(image_path)

    max_attempts = 2
    for attempt in range(max_attempts):
        result = _call_claude_vision(image_path)
        if result is not None:
            return result

        if attempt < max_attempts - 1:
            print(f"    Retrying analysis for {Path(image_path).name}...")
            time.sleep(2)

    print(f"  Using fallback regions for {Path(image_path).name}")
    return ("fallback", _generate_fallback_regions(width, height))


def analyze_all_images(run_dir: Path) -> None:
    """Analyze all educational images in a run and update the manifest."""
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
        if img.get("regions") is not None:
            continue

        image_path = img.get("local_path", "")
        if not image_path or not Path(image_path).exists():
            filename = img.get("file", "")
            if filename:
                image_path = str(edu_dir / filename)

        if not image_path or not Path(image_path).exists():
            print(f"  Warning: Image file not found for image {img.get('id', '?')}")
            continue

        print(f"  Analyzing regions for {Path(image_path).name}...")
        img_type, regions = analyze_single_image(image_path)
        img["image_type"] = img_type
        img["regions"] = regions
        # Suggest duration: 1.5s per region + 1.5s for full reveal + 1s buffer
        # Single objects get shorter duration (just a fade-in)
        if img_type == "single_object":
            img["suggested_duration"] = 4.0
        else:
            suggested_duration = len(regions) * 1.5 + 1.5 + 1.0
            img["suggested_duration"] = round(min(suggested_duration, 10.0), 1)
        analyzed_count += 1

        if img_type == "single_object":
            print(f"    Classified as single_object -- will fade in (no region split)")
        else:
            print(f"    Type: {img_type}, {len(regions)} regions: {', '.join(r['label'] for r in regions)}")

    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)

    print(f"  Analyzed {analyzed_count} images, manifest updated")


def main():
    """CLI entry point."""
    run_dir = Path(os.environ.get("OUTPUT_DIR", ""))
    if not run_dir.exists():
        print("ERROR: OUTPUT_DIR not set or doesn't exist")
        sys.exit(1)

    print("Analyzing educational image regions...")
    analyze_all_images(run_dir)


if __name__ == "__main__":
    main()
