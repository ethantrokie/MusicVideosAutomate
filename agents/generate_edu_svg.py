#!/usr/bin/env python3
"""
SVG validation and parsing utilities for educational diagrams.

Claude generates SVG diagrams with semantic <g> groups that have
data-order and data-delay attributes for animation sequencing.
This module validates those SVGs and extracts structured data for
downstream rendering and fal.ai image substitution.
"""

import re
import xml.etree.ElementTree as ET
from typing import Optional

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
