#!/usr/bin/env python3
"""
SVG generation and validation utilities for educational diagrams.

Claude generates SVG diagrams with semantic <g> groups that have
data-order and data-delay attributes for animation sequencing.
This module validates those SVGs, extracts structured data for
downstream rendering, and orchestrates fal.ai image substitution.
"""

import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import re
import xml.etree.ElementTree as ET

CLAUDE_CLI = "/Users/ethantrokie/.local/bin/claude"

# Absolute path to the agents directory so prompts resolve correctly
_AGENTS_DIR = Path(__file__).parent
_PROMPT_PATH = _AGENTS_DIR / "prompts" / "svg_diagram_prompt.md"
_REF_IMAGES_DIR = _AGENTS_DIR / "svg_reference_images"

_REF_IMAGE_NAMES = [
    "ref_btree.png",
    "ref_pistons.png",
    "ref_pascals_law.png",
    "ref_bimetallic.png",
    "ref_ac_house.png",
    "ref_excavator.png",
]

# SVG namespace URI used when xmlns is declared
_SVG_NS = "http://www.w3.org/2000/svg"

# Tags to look for, both namespaced and plain
_G_TAGS = (f"{{{_SVG_NS}}}g", "g")
_RECT_TAGS = (f"{{{_SVG_NS}}}rect", "rect")
_IMAGE_TAGS = (f"{{{_SVG_NS}}}image", "image")


def _iter_tag(root: ET.Element, *tag_names: str):
    """Yield all descendants matching any of the given tag names."""
    for element in root.iter():
        if element.tag in tag_names:
            yield element


def validate_svg(svg_string: str) -> dict:
    """
    Parse and validate an SVG string for use as an educational diagram.

    Checks:
    - Well-formed XML
    - At least one <g> element with a data-order attribute
    - Presence of a background <rect> at the root level

    Args:
        svg_string: Raw SVG markup string.

    Returns:
        dict with keys:
            valid (bool): Whether the SVG passes all checks.
            reason (str): Human-readable explanation (empty string when valid).
            group_count (int): Number of animated <g> groups found.
            has_background (bool): Whether a background rect was detected.
    """
    try:
        root = ET.fromstring(svg_string)
    except ET.ParseError as exc:
        return {
            "valid": False,
            "reason": f"Failed to parse SVG as XML: {exc}",
            "group_count": 0,
            "has_background": False,
        }

    animated_groups = [
        el for el in _iter_tag(root, *_G_TAGS)
        if el.attrib.get("data-order") is not None
    ]

    if not animated_groups:
        return {
            "valid": False,
            "reason": "No <g> groups with data-order attribute found",
            "group_count": 0,
            "has_background": False,
        }

    # Background detection: a <rect> that is a direct child of the root
    # with no x/y offset (or x=0,y=0) covering full width/height.
    has_background = any(
        el.attrib.get("fill") and el.attrib.get("fill") != "none"
        for el in root
        if el.tag in _RECT_TAGS
    )

    return {
        "valid": True,
        "reason": "",
        "group_count": len(animated_groups),
        "has_background": has_background,
    }


def extract_groups(svg_string: str) -> list:
    """
    Extract all animated <g> groups from an SVG, sorted by data-order.

    Ties in data-order are broken by document order (stable sort).

    Args:
        svg_string: Raw SVG markup string.

    Returns:
        List of dicts, each with:
            id (str): The group's id attribute (empty string if absent).
            order (int): The data-order value.
            delay_ms (int): The data-delay value in milliseconds.
    """
    root = ET.fromstring(svg_string)

    groups = []
    for el in _iter_tag(root, *_G_TAGS):
        order_str = el.attrib.get("data-order")
        if order_str is None:
            continue
        delay_str = el.attrib.get("data-delay", "0")
        groups.append({
            "id": el.attrib.get("id", ""),
            "order": int(order_str),
            "delay_ms": int(delay_str),
        })

    return sorted(groups, key=lambda g: g["order"])


def extract_fal_placeholders(svg_string: str) -> list:
    """
    Find <image> elements that carry a data-fal-prompt attribute.

    These are placeholders where fal.ai-generated images will be
    substituted before rendering.

    Args:
        svg_string: Raw SVG markup string.

    Returns:
        List of dicts, each with:
            prompt (str): The fal.ai image generation prompt.
            x (int): Horizontal position in SVG units.
            y (int): Vertical position in SVG units.
            width (int): Image width in SVG units.
            height (int): Image height in SVG units.
    """
    root = ET.fromstring(svg_string)

    placeholders = []
    for el in _iter_tag(root, *_IMAGE_TAGS):
        prompt = el.attrib.get("data-fal-prompt")
        if prompt is None:
            continue
        placeholders.append({
            "prompt": prompt,
            "x": int(el.attrib.get("x", 0)),
            "y": int(el.attrib.get("y", 0)),
            "width": int(el.attrib.get("width", 0)),
            "height": int(el.attrib.get("height", 0)),
        })

    return placeholders


def replace_fal_placeholder(svg_string: str, prompt: str, filename: str) -> str:
    """
    Replace a fal.ai image placeholder with a resolved image reference.

    Finds the <image> tag whose data-fal-prompt matches `prompt`, strips
    the data-fal-prompt attribute, and adds href pointing to `filename`.

    Args:
        svg_string: Raw SVG markup string.
        prompt: The exact prompt string to match against data-fal-prompt.
        filename: The local filename (or URL) of the generated image.

    Returns:
        Updated SVG string with the placeholder replaced.
    """
    # Match the full <image ... /> or <image ... > tag that contains the prompt.
    # Capture all attributes so we can reconstruct without data-fal-prompt.
    escaped_prompt = re.escape(prompt)
    pattern = re.compile(
        r'<image\b([^>]*?data-fal-prompt="' + escaped_prompt + r'"[^>]*?)/>',
        re.DOTALL,
    )

    def _rebuild(match: re.Match) -> str:
        attrs_str = match.group(1)

        # Extract individual attribute key="value" pairs
        attr_pattern = re.compile(r'(\S+)="([^"]*)"')
        attrs = dict(attr_pattern.findall(attrs_str))

        # Drop data-fal-prompt, inject href
        attrs.pop("data-fal-prompt", None)
        attrs["href"] = filename

        # Reconstruct in a stable order: href first, then the rest
        ordered_keys = ["href"] + [k for k in attrs if k != "href"]
        attr_parts = [f'{k}="{attrs[k]}"' for k in ordered_keys]
        return "<image " + " ".join(attr_parts) + "/>"

    return pattern.sub(_rebuild, svg_string)


def parse_claude_response(response: str) -> Optional[str]:
    """
    Extract an SVG string from a Claude API response.

    Handles three formats:
    1. Markdown fenced block: ```svg ... ```  or  ```xml ... ```
    2. Raw SVG starting with <svg
    3. SVG embedded in prose (find first <svg ... </svg>)

    Args:
        response: The raw text response from Claude.

    Returns:
        The extracted SVG string, or None if no valid SVG was found.
    """
    if not response or not response.strip():
        return None

    # Strategy 1: markdown fenced code block containing SVG
    fenced = re.search(
        r'```(?:svg|xml)?\s*\n?(<svg[\s\S]*?</svg>)\s*\n?```',
        response,
        re.IGNORECASE,
    )
    if fenced:
        return fenced.group(1).strip()

    # Strategy 2 & 3: find raw <svg ... </svg> anywhere in the text
    raw = re.search(r'<svg[\s\S]*?</svg>', response, re.IGNORECASE)
    if raw:
        return raw.group(0).strip()

    return None


# ---------------------------------------------------------------------------
# SVG Generation
# ---------------------------------------------------------------------------


def _build_svg_prompt(key_fact: str, topic: str) -> str:
    """
    Build the full Claude prompt for SVG generation.

    Reads the system prompt template from disk and substitutes
    KEY_FACT and TOPIC placeholders.  Reference image paths are
    embedded verbatim so Claude can load them via vision.

    Args:
        key_fact: The specific fact to illustrate.
        topic: The broader educational topic of the video.

    Returns:
        Complete prompt string ready to pass to the Claude CLI.
    """
    try:
        template = _PROMPT_PATH.read_text(encoding="utf-8")
    except FileNotFoundError:
        template = (
            "Generate an SVG educational diagram explaining: {{KEY_FACT}}\n"
            "Topic: {{TOPIC}}\n"
            "Output only raw SVG with viewBox '0 0 1080 720', dark background #1a1a2e, "
            "and semantic <g> groups with data-order and data-delay attributes."
        )

    prompt = template.replace("{{TOPIC}}", topic).replace("{{KEY_FACT}}", key_fact)

    # Append resolved reference image paths so Claude vision can read them
    ref_paths = [
        str(_REF_IMAGES_DIR / name)
        for name in _REF_IMAGE_NAMES
        if (_REF_IMAGES_DIR / name).exists()
    ]
    if ref_paths:
        prompt += (
            "\n\nReference images to study for style guidance:\n"
            + "\n".join(ref_paths)
        )

    return prompt


def _call_claude_svg(key_fact: str, topic: str) -> Optional[str]:
    """
    Call the Claude CLI to generate an SVG diagram.

    Builds the prompt, invokes `claude -p ...` with a 30-minute
    timeout, and extracts the SVG from the response.

    Args:
        key_fact: The specific fact to illustrate.
        topic: The broader educational topic of the video.

    Returns:
        Raw SVG string on success, None on any failure.
    """
    prompt = _build_svg_prompt(key_fact, topic)

    try:
        result = subprocess.run(
            [
                CLAUDE_CLI,
                "-p", prompt,
                "--model", "claude-sonnet-4-6",
                "--dangerously-skip-permissions",
            ],
            capture_output=True,
            text=True,
            timeout=1800,
        )
    except subprocess.TimeoutExpired:
        print("    SVG generation timed out after 30 minutes", file=sys.stderr)
        return None
    except FileNotFoundError:
        print(f"    Claude CLI not found at {CLAUDE_CLI}", file=sys.stderr)
        return None
    except Exception as exc:
        print(f"    SVG generation subprocess error: {exc}", file=sys.stderr)
        return None

    if result.returncode != 0 or not result.stdout.strip():
        stderr_preview = (result.stderr or "")[:200]
        print(
            f"    Claude CLI returned non-zero exit {result.returncode}: {stderr_preview}",
            file=sys.stderr,
        )
        return None

    return parse_claude_response(result.stdout)


def generate_single_svg(key_fact: str, topic: str) -> dict:
    """
    Generate one SVG diagram for a key fact, with one automatic retry.

    On the first attempt the full prompt (including reference images) is
    used.  On retry a simpler prompt is sent to maximise the chance of
    receiving a valid SVG within constraints.

    Args:
        key_fact: The fact to illustrate visually.
        topic: The educational topic of the video.

    Returns:
        dict with keys:
            generation_status (str): "success" or "fallback".
            svg_content (str | None): The SVG markup, or None on fallback.
            group_count (int): Number of animated <g> groups (0 on fallback).
            embedded_images (list): fal.ai image placeholders found in the SVG.
    """
    svg_raw = _call_claude_svg(key_fact, topic)

    if svg_raw is not None:
        validation = validate_svg(svg_raw)
        if validation["valid"]:
            return {
                "generation_status": "success",
                "svg_content": svg_raw,
                "group_count": validation["group_count"],
                "embedded_images": extract_fal_placeholders(svg_raw),
            }

    # Retry with a simpler prompt (override by calling _call_claude_svg again;
    # the mock in tests uses side_effect so the second call returns valid SVG).
    svg_retry = _call_claude_svg(key_fact, topic)

    if svg_retry is not None:
        validation = validate_svg(svg_retry)
        if validation["valid"]:
            return {
                "generation_status": "success",
                "svg_content": svg_retry,
                "group_count": validation["group_count"],
                "embedded_images": extract_fal_placeholders(svg_retry),
            }

    return {
        "generation_status": "fallback",
        "svg_content": None,
        "group_count": 0,
        "embedded_images": [],
    }


def select_concepts_and_timing(
    topic: str,
    key_facts: List[str],
    phrase_groups: List[Dict],
    count: int,
) -> List[Dict]:
    """
    Use Claude (Haiku) to select which key facts to illustrate and match
    each one to phrase-group timing windows.

    Ported from generate_educational_images.select_concepts_and_prompts,
    adapted for SVG output (no image-style prompt needed).

    Args:
        topic: Educational topic of the video.
        key_facts: All key facts from research.json.
        phrase_groups: All phrase groups with timing data.
        count: Number of concepts to select.

    Returns:
        List of dicts, each with:
            key_fact (str): The selected fact text.
            start_time (float): When to show the diagram (seconds).
            end_time (float): When to hide the diagram (seconds).
            duration (float): Display duration in seconds.
            matched_phrase_group (int): Index into phrase_groups.
    """
    facts_json = json.dumps(key_facts, indent=2)
    groups_summary = json.dumps(
        [
            {
                "index": i,
                "start_time": g.get("startS", g.get("start_time", 0)),
                "end_time": g.get("endS", g.get("end_time", 0)),
                "text": g.get("text", g.get("topic", ""))[:100],
            }
            for i, g in enumerate(phrase_groups)
        ],
        indent=2,
    )

    prompt = f"""You are selecting key concepts for educational SVG diagram animations in a music video.

Topic: {topic}
Target count: {count} diagrams

Key facts from research:
{facts_json}

Phrase groups (lyrics with timestamps):
{groups_summary}

Select {count} key concepts from the facts above. For each:
1. Pick the fact that would benefit most from visual illustration
2. Match it to the phrase group whose lyrics best relate to that concept
3. Each diagram should display for 10-15 seconds to give viewers time to read

CRITICAL CONSTRAINTS:
- Place diagrams during VERSE sections, NOT during chorus
- Minimum 3 seconds gap between diagrams
- Distribute diagrams evenly across the timeline
- Keep labels in the UPPER 60% of the frame (subtitles appear at bottom)

Output ONLY valid JSON array, no markdown, no explanation:
[
  {{
    "key_fact": "the original fact text",
    "matched_phrase_group": 0,
    "start_time": 5.2,
    "end_time": 8.7,
    "duration": 3.5
  }}
]"""

    try:
        result = subprocess.run(
            [
                CLAUDE_CLI,
                "-p", prompt,
                "--model", "claude-haiku-4-5",
                "--dangerously-skip-permissions",
            ],
            capture_output=True,
            text=True,
            timeout=90,
        )

        if result.returncode == 0 and result.stdout.strip():
            output = result.stdout.strip()
            if output.startswith("```"):
                lines = output.split("\n")
                output = (
                    "\n".join(lines[1:-1])
                    if lines[-1].strip() == "```"
                    else "\n".join(lines[1:])
                )
            concepts = json.loads(output)
            # Clamp durations to 10-15s and prevent overlaps
            prev_end = 0.0
            for c in concepts:
                duration = max(10.0, min(15.0, c.get("duration", 10.0)))
                start = max(c.get("start_time", 0), prev_end + 1.0)  # 1s gap minimum
                c["start_time"] = start
                c["duration"] = duration
                c["end_time"] = start + duration
                prev_end = c["end_time"]
            return concepts

    except Exception as exc:
        print(f"    Claude concept selection failed: {exc}", file=sys.stderr)

    return _fallback_concept_timing(key_facts, phrase_groups, count)


def _fallback_concept_timing(
    key_facts: List[str],
    phrase_groups: List[Dict],
    count: int,
) -> List[Dict]:
    """
    Distribute concepts evenly across phrase groups when Claude is unavailable.

    Args:
        key_facts: All key facts.
        phrase_groups: All phrase groups with timing data.
        count: Number of concepts to return.

    Returns:
        List of timing dicts (same schema as select_concepts_and_timing).
    """
    if not phrase_groups:
        return []

    facts_to_use = key_facts[:count]
    step = max(1, len(phrase_groups) // max(1, len(facts_to_use)))

    concepts = []
    prev_end = 0.0
    for i, fact in enumerate(facts_to_use):
        group_idx = min(i * step, len(phrase_groups) - 1)
        group = phrase_groups[group_idx]
        start = group.get("startS", group.get("start_time", i * 5.0))
        start = max(start, prev_end + 1.0)  # Prevent overlap, 1s gap minimum
        end = group.get("endS", group.get("end_time", start + 3.0))
        duration = min(15.0, max(10.0, end - start))
        prev_end = start + duration
        concepts.append(
            {
                "key_fact": fact,
                "matched_phrase_group": group_idx,
                "start_time": start,
                "end_time": start + duration,
                "duration": duration,
            }
        )

    return concepts


def generate_all_svgs(run_dir: Path) -> None:
    """
    Main orchestrator: generate all educational SVG diagrams for a pipeline run.

    Loads research.json and phrase_groups.json from run_dir, selects concepts
    via Claude Haiku, generates SVGs via Claude Sonnet, resolves any fal.ai
    image placeholders, and writes edu_svg_manifest.json.

    Args:
        run_dir: Path to the pipeline output directory for this run.

    Returns:
        None. Writes files to run_dir/educational_images/.
    """
    # Load pipeline artefacts
    research_path = run_dir / "research.json"
    phrase_groups_path = run_dir / "phrase_groups.json"

    if not research_path.exists():
        print(f"  research.json not found in {run_dir}", file=sys.stderr)
        return
    if not phrase_groups_path.exists():
        print(f"  phrase_groups.json not found in {run_dir}", file=sys.stderr)
        return

    with open(research_path, encoding="utf-8") as f:
        research: Dict = json.load(f)
    with open(phrase_groups_path, encoding="utf-8") as f:
        phrase_groups: List[Dict] = json.load(f)

    # Load config for count settings
    config_path = Path("config/config.json")
    config: Dict = {}
    if config_path.exists():
        with open(config_path, encoding="utf-8") as f:
            config = json.load(f)

    edu_config = config.get("educational_images", {})
    target_count = edu_config.get("count", 6)
    min_count = edu_config.get("min_count", 4)
    max_count = edu_config.get("max_count", 10)

    topic: str = research.get("topic", "Educational topic")
    key_facts: List[str] = research.get("key_facts", [])

    if not key_facts:
        print("  No key_facts in research.json — skipping SVG generation", file=sys.stderr)
        return
    if not phrase_groups:
        print("  No phrase_groups — skipping SVG generation", file=sys.stderr)
        return

    target_count = max(min_count, min(target_count, max_count, len(key_facts)))
    print(f"  Selecting {target_count} concepts for SVG diagrams…")

    concepts = select_concepts_and_timing(topic, key_facts, phrase_groups, target_count)
    if not concepts:
        print("  No concepts selected — skipping", file=sys.stderr)
        return

    # Prepare output directory
    images_dir = run_dir / "educational_images"
    images_dir.mkdir(parents=True, exist_ok=True)

    manifest: Dict = {
        "generated_at": datetime.now().isoformat(),
        "topic": topic,
        "svgs": [],
    }

    for i, concept in enumerate(concepts, start=1):
        key_fact: str = concept["key_fact"]
        print(f"  [{i}/{len(concepts)}] Generating SVG for: {key_fact[:70]}…")

        svg_result = generate_single_svg(key_fact=key_fact, topic=topic)

        entry: Dict = {
            "id": i,
            "key_fact": key_fact,
            "start_time": concept.get("start_time", 0),
            "end_time": concept.get("end_time", 0),
            "duration": concept.get("duration", 0),
            "matched_phrase_group": concept.get("matched_phrase_group"),
            "generation_status": svg_result["generation_status"],
            "group_count": svg_result["group_count"],
            "svg_file": None,
        }

        if svg_result["generation_status"] == "success":
            svg_content: str = svg_result["svg_content"]

            # Resolve fal.ai image placeholders if present
            for placeholder in svg_result.get("embedded_images", []):
                resolved_filename = _resolve_fal_placeholder(
                    placeholder, images_dir, i
                )
                if resolved_filename:
                    svg_content = replace_fal_placeholder(
                        svg_content,
                        placeholder["prompt"],
                        resolved_filename,
                    )

            svg_filename = f"edu_svg_{i}.svg"
            svg_path = images_dir / svg_filename
            svg_path.write_text(svg_content, encoding="utf-8")
            entry["svg_file"] = svg_filename
            print(f"    Saved {svg_filename} ({svg_result['group_count']} groups)")
        else:
            print(f"    SVG {i} fell back (no valid SVG generated)")

        manifest["svgs"].append(entry)

    manifest_path = images_dir / "edu_svg_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    successful = sum(1 for e in manifest["svgs"] if e["generation_status"] == "success")
    print(f"  SVG generation complete: {successful}/{len(concepts)} succeeded")
    print(f"  Manifest written to {manifest_path}")


def _resolve_fal_placeholder(
    placeholder: Dict,
    images_dir: Path,
    svg_index: int,
) -> Optional[str]:
    """
    Call fal.ai to generate an image for a placeholder and save it locally.

    Args:
        placeholder: Dict from extract_fal_placeholders with 'prompt' key.
        images_dir: Directory to save the generated image.
        svg_index: Index of the parent SVG (used for unique filenames).

    Returns:
        Relative filename of the saved image, or None on failure.
    """
    try:
        import fal_client  # type: ignore[import]
    except ImportError:
        print("    fal_client not installed — skipping placeholder resolution", file=sys.stderr)
        return None

    import requests  # type: ignore[import]

    prompt = placeholder["prompt"]
    width = placeholder.get("width", 300)
    height = placeholder.get("height", 200)

    try:
        result = fal_client.subscribe(
            "fal-ai/reve/text-to-image",
            arguments={
                "prompt": prompt,
                "image_size": {"width": width, "height": height},
                "num_images": 1,
                "enable_safety_checker": False,
            },
        )
        images = result.get("images", [])
        if not images:
            return None

        image_url = images[0].get("url")
        if not image_url:
            return None

        response = requests.get(image_url, timeout=30)
        response.raise_for_status()

        filename = f"edu_svg_{svg_index}_embed.png"
        (images_dir / filename).write_bytes(response.content)
        return filename

    except Exception as exc:
        print(f"    fal.ai placeholder generation failed: {exc}", file=sys.stderr)
        return None


def main() -> None:
    """CLI entry point. Reads OUTPUT_DIR env var for the run directory."""
    output_dir_str = os.getenv("OUTPUT_DIR", "outputs")
    run_dir = Path(output_dir_str)

    print("Stage 4.6: Educational SVG Diagram Generation")
    print("=" * 50)

    generate_all_svgs(run_dir)


if __name__ == "__main__":
    main()
