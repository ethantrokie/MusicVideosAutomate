import json
import pytest
from pathlib import Path
from unittest.mock import patch

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "agents"))


# --- JSON extraction tests ---

def test_extract_json_pure():
    from analyze_edu_image_regions import _extract_json_from_text

    assert _extract_json_from_text('{"type": "comparison", "regions": []}') == '{"type": "comparison", "regions": []}'


def test_extract_json_with_markdown_fences():
    from analyze_edu_image_regions import _extract_json_from_text

    text = '```json\n{"type": "comparison", "regions": []}\n```'
    result = _extract_json_from_text(text)
    assert json.loads(result)["type"] == "comparison"


def test_extract_json_with_preamble():
    """Claude often adds explanation text before the JSON."""
    from analyze_edu_image_regions import _extract_json_from_text

    text = 'I can see this is a comparison diagram. Here is the analysis:\n\n```json\n{"type": "comparison", "regions": [{"label": "A", "bounds": {"x": 0, "y": 0, "w": 50, "h": 100}, "order": 1, "from_direction": "left", "delay_ms": 0}]}\n```'
    result = _extract_json_from_text(text)
    assert result is not None
    data = json.loads(result)
    assert data["type"] == "comparison"
    assert len(data["regions"]) == 1


def test_extract_json_with_preamble_no_fences():
    """Claude sometimes outputs explanation then raw JSON without fences."""
    from analyze_edu_image_regions import _extract_json_from_text

    text = 'This diagram shows two concepts.\n{"type": "comparison", "regions": []}'
    result = _extract_json_from_text(text)
    assert result is not None
    assert json.loads(result)["type"] == "comparison"


def test_extract_json_returns_none_for_invalid():
    from analyze_edu_image_regions import _extract_json_from_text

    assert _extract_json_from_text("not json at all") is None
    assert _extract_json_from_text("") is None


# --- Parse response tests ---

def test_parse_structured_response():
    from analyze_edu_image_regions import _parse_region_response

    response = '{"type": "comparison", "regions": [{"label": "A", "bounds": {"x": 0, "y": 0, "w": 50, "h": 100}, "order": 1, "from_direction": "left", "delay_ms": 0}]}'
    img_type, regions = _parse_region_response(response)
    assert img_type == "comparison"
    assert len(regions) == 1


def test_parse_single_object_response():
    from analyze_edu_image_regions import _parse_region_response

    response = '{"type": "single_object", "regions": []}'
    img_type, regions = _parse_region_response(response)
    assert img_type == "single_object"
    assert regions == []


def test_parse_backwards_compat_plain_array():
    from analyze_edu_image_regions import _parse_region_response

    response = '[{"label": "A", "bounds": {"x": 0, "y": 0, "w": 100, "h": 100}, "order": 1, "from_direction": "top", "delay_ms": 0}]'
    img_type, regions = _parse_region_response(response)
    assert img_type == "multi_element"
    assert len(regions) == 1


def test_parse_with_preamble_and_fences():
    """The most common failure case -- Claude adds explanation before fenced JSON."""
    from analyze_edu_image_regions import _parse_region_response

    response = 'Perfect. I can see this is a comparison.\n\n```json\n{"type": "comparison", "regions": [{"label": "Left", "bounds": {"x": 0, "y": 0, "w": 50, "h": 100}, "order": 1, "from_direction": "left", "delay_ms": 0}]}\n```\n\nThis should work well for animation.'
    img_type, regions = _parse_region_response(response)
    assert img_type == "comparison"
    assert len(regions) == 1


def test_parse_invalid_returns_none():
    from analyze_edu_image_regions import _parse_region_response

    img_type, regions = _parse_region_response("not json at all")
    assert img_type is None
    assert regions == []


# --- Validation tests ---

def test_validate_regions_clamps_bounds():
    from analyze_edu_image_regions import _validate_regions

    regions = [
        {"label": "A", "bounds": {"x": -5, "y": 0, "w": 120, "h": 50}, "order": 1, "from_direction": "left", "delay_ms": 0}
    ]
    validated = _validate_regions(regions)
    assert validated[0]["bounds"]["x"] == 0
    assert validated[0]["bounds"]["w"] == 100


def test_validate_regions_rejects_too_many():
    from analyze_edu_image_regions import _validate_regions

    regions = [
        {"label": f"R{i}", "bounds": {"x": 0, "y": 0, "w": 25, "h": 100}, "order": i, "from_direction": "left", "delay_ms": 0}
        for i in range(6)
    ]
    validated = _validate_regions(regions)
    assert len(validated) == 4


def test_validate_regions_sorts_by_order():
    from analyze_edu_image_regions import _validate_regions

    regions = [
        {"label": "B", "bounds": {"x": 50, "y": 0, "w": 50, "h": 100}, "order": 2, "from_direction": "right", "delay_ms": 300},
        {"label": "A", "bounds": {"x": 0, "y": 0, "w": 50, "h": 100}, "order": 1, "from_direction": "left", "delay_ms": 0},
    ]
    validated = _validate_regions(regions)
    assert validated[0]["label"] == "A"
    assert validated[1]["label"] == "B"


def test_validate_enforces_min_delay():
    from analyze_edu_image_regions import _validate_regions

    regions = [
        {"label": "A", "bounds": {"x": 0, "y": 0, "w": 100, "h": 100}, "order": 1, "from_direction": "left", "delay_ms": 100}
    ]
    validated = _validate_regions(regions)
    assert validated[0]["delay_ms"] == 800  # clamped up from 100


# --- Fallback tests ---

def test_fallback_regions_for_landscape():
    from analyze_edu_image_regions import _generate_fallback_regions

    regions = _generate_fallback_regions(1248, 832)
    assert len(regions) == 2
    assert regions[0]["from_direction"] == "left"
    assert regions[1]["from_direction"] == "right"


def test_fallback_regions_for_portrait():
    from analyze_edu_image_regions import _generate_fallback_regions

    regions = _generate_fallback_regions(768, 1344)
    assert len(regions) == 2
    assert regions[0]["from_direction"] == "top"
    assert regions[1]["from_direction"] == "bottom"


# --- Retry tests ---

def test_analyze_retries_on_first_failure():
    """analyze_single_image retries once before falling back."""
    from analyze_edu_image_regions import analyze_single_image, _call_claude_vision
    call_count = 0

    def mock_call(image_path):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return None  # First attempt fails
        return ("comparison", [
            {"label": "A", "bounds": {"x": 0, "y": 0, "w": 50, "h": 100},
             "order": 1, "from_direction": "left", "delay_ms": 800}
        ])

    with patch("analyze_edu_image_regions._call_claude_vision", side_effect=mock_call), \
         patch("analyze_edu_image_regions._get_image_dimensions", return_value=(1248, 832)), \
         patch("analyze_edu_image_regions.time") as mock_time:
        img_type, regions = analyze_single_image("/fake/path.png")

    assert call_count == 2
    assert img_type == "comparison"
    assert regions[0]["label"] == "A"
    mock_time.sleep.assert_called_once_with(2)


def test_analyze_falls_back_after_two_failures():
    """Falls back to L/R split after both attempts fail."""
    from analyze_edu_image_regions import analyze_single_image

    with patch("analyze_edu_image_regions._call_claude_vision", return_value=None), \
         patch("analyze_edu_image_regions._get_image_dimensions", return_value=(1248, 832)), \
         patch("analyze_edu_image_regions.time"):
        img_type, regions = analyze_single_image("/fake/path.png")

    assert img_type == "fallback"
    assert len(regions) == 2
    assert regions[0]["from_direction"] == "left"
