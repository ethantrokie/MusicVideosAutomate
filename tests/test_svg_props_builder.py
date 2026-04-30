import json
import pytest
from pathlib import Path
from unittest.mock import patch

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "agents"))

# Disable A/B experiments during tests so they don't interfere with expected values
@pytest.fixture(autouse=True)
def disable_experiments():
    with patch("engagement_experiments.get_engagement_experiment_variant", return_value=None):
        yield


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

    props = build_overlay_props(tmp_path, _make_config(), "short_hook", 15000, segment_start_s=44.0)
    assert len(props["eduDiagrams"]) == 1
    assert props["eduDiagrams"][0]["startMs"] == 6000
    assert props["eduDiagrams"][0]["endMs"] == 12000


def test_old_raster_manifest_ignored_when_svg_exists(tmp_path):
    from remotion_props_builder import build_overlay_props

    (tmp_path / "research.json").write_text(json.dumps({"video_title": "Test"}))
    (tmp_path / "phrase_groups.json").write_text(json.dumps([]))
    (tmp_path / "approved_media.json").write_text(json.dumps({"shot_list": []}))

    edu_dir = tmp_path / "educational_images"
    edu_dir.mkdir()
    (edu_dir / "img1.png").write_bytes(b"fake")

    # Old raster manifest
    old_manifest = {"images": [{"id": 1, "local_path": str(edu_dir / "img1.png"), "start_time": 5, "end_time": 8, "concept": "old"}]}
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
    assert "eduDiagrams" in props
    assert len(props["eduDiagrams"]) == 1
    assert props["eduDiagrams"][0]["concept"] == "SVG concept"
