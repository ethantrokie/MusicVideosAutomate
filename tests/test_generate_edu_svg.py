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
    assert "parse" in result["reason"].lower() or "malformed" in result["reason"].lower()


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
    # Sorted by data-order (stable sort preserves document order for ties)
    assert groups[0]["order"] == 1
    assert groups[1]["order"] == 1
    assert groups[2]["order"] == 2
    assert groups[2]["id"] == "second"
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


from unittest.mock import patch


def test_generate_single_svg_calls_claude():
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
    assert mock_call.call_count == 2


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
