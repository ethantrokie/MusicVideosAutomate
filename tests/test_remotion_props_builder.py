#!/usr/bin/env python3
"""
Tests for remotion_props_builder module.
"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "agents"))
from remotion_props_builder import build_overlay_props


def _make_minimal_config() -> dict:
    return {
        "video_settings": {
            "resolution": [1080, 1920],
            "fps": 30,
        },
        "remotion_overlay": {
            "channel_name": "@learningsciencemusic",
            "karaoke_enabled": True,
            "edu_reveal_enabled": True,
            "transitions_enabled": False,
        },
    }


def test_build_props_from_minimal_data(tmp_path: Path):
    """Build props from minimal pipeline artifacts and assert basic fields."""
    # Create research.json
    (tmp_path / "research.json").write_text(
        json.dumps({"video_title": "Photosynthesis Explained"})
    )

    # Create lyrics_aligned.json
    (tmp_path / "lyrics_aligned.json").write_text(
        json.dumps({"alignedWords": [{"word": "hello", "startS": 0.0, "endS": 0.5}]})
    )

    # Create phrase_groups.json as a list
    phrase_groups = [
        {
            "text": "Hello world",
            "startS": 0.0,
            "endS": 2.0,
            "words": [
                {"word": "Hello", "startS": 0.0, "endS": 0.5},
                {"word": "world", "startS": 0.6, "endS": 1.0},
            ],
        }
    ]
    (tmp_path / "phrase_groups.json").write_text(json.dumps(phrase_groups))

    # Create approved_media.json
    (tmp_path / "approved_media.json").write_text(
        json.dumps({"shot_list": []})
    )

    config = _make_minimal_config()
    props = build_overlay_props(tmp_path, config, "short_hook", 60000)

    assert props["width"] == 1080
    assert props["height"] == 1920
    assert props["fps"] == 30
    assert props["durationMs"] == 60000
    assert props["isShort"] is True
    assert props["titleText"] == "Photosynthesis Explained"

    # Phrases are converted with ms times
    assert len(props["phrases"]) == 1
    phrase = props["phrases"][0]
    assert phrase["text"] == "Hello world"
    assert phrase["startMs"] == 0
    assert phrase["endMs"] == 2000
    assert len(phrase["words"]) == 2
    assert phrase["words"][0]["word"] == "Hello"
    assert phrase["words"][0]["startMs"] == 0
    assert phrase["words"][0]["endMs"] == 500
    assert phrase["words"][1]["word"] == "world"
    assert phrase["words"][1]["startMs"] == 600
    assert phrase["words"][1]["endMs"] == 1000


def test_edu_images_included_when_manifest_exists(tmp_path: Path):
    """Educational images are read from manifest and converted to ms."""
    edu_dir = tmp_path / "educational_images"
    edu_dir.mkdir()

    # Create actual image files so the existence check passes
    (edu_dir / "img1.png").write_bytes(b"fake png")
    (edu_dir / "img2.png").write_bytes(b"fake png")

    manifest = {
        "images": [
            {
                "local_path": str(edu_dir / "img1.png"),
                "start_time": 5.0,
                "end_time": 10.0,
                "concept": "Chlorophyll",
                "regions": [
                    {"label": "Leaf", "bounds": {"x": 0, "y": 0, "w": 50, "h": 100}, "order": 1, "from_direction": "left", "delay_ms": 0},
                    {"label": "Cell", "bounds": {"x": 50, "y": 0, "w": 50, "h": 100}, "order": 2, "from_direction": "right", "delay_ms": 300},
                ],
            },
            {
                "local_path": str(edu_dir / "img2.png"),
                "start_time": 15.5,
                "end_time": 20.0,
                "concept": "ATP synthesis",
            },
        ]
    }
    (edu_dir / "edu_image_manifest.json").write_text(json.dumps(manifest))

    # Minimal other artifacts
    (tmp_path / "research.json").write_text(json.dumps({"video_title": "Test"}))
    (tmp_path / "phrase_groups.json").write_text(json.dumps([]))
    (tmp_path / "approved_media.json").write_text(json.dumps({"shot_list": []}))

    config = _make_minimal_config()
    props = build_overlay_props(tmp_path, config, "full", 30000)

    assert len(props["eduImages"]) == 2

    img0 = props["eduImages"][0]
    assert img0["src"] == str((edu_dir / "img1.png").resolve())
    assert img0["startMs"] == 5000
    assert img0["endMs"] == 10000
    assert img0["concept"] == "Chlorophyll"

    img1 = props["eduImages"][1]
    assert img1["concept"] == "ATP synthesis"
    assert img1["startMs"] == 15500

    assert len(props["eduImages"][0]["regions"]) == 2
    assert props["eduImages"][0]["regions"][0]["fromDirection"] == "left"
    assert props["eduImages"][0]["regions"][1]["delayMs"] == 300
    # Second image has no regions
    assert props["eduImages"][1]["regions"] == []


def test_shot_boundaries_extracted(tmp_path: Path):
    """Shot boundaries use correct transition types based on media source."""
    approved = {
        "shot_list": [
            {"shot_number": 1, "start_time": 0.0, "end_time": 5.0, "source": "stock_video"},
            {"shot_number": 2, "start_time": 5.0, "end_time": 10.0, "source": "stock_video"},
            {"shot_number": 3, "start_time": 10.0, "end_time": 15.0, "source": "educational_image"},
        ]
    }
    (tmp_path / "approved_media.json").write_text(json.dumps(approved))
    (tmp_path / "research.json").write_text(json.dumps({"video_title": "Test"}))
    (tmp_path / "phrase_groups.json").write_text(json.dumps([]))

    config = _make_minimal_config()
    props = build_overlay_props(tmp_path, config, "full", 15000)

    boundaries = props["shotBoundaries"]
    assert len(boundaries) == 2

    # First boundary: stock_video -> stock_video => wipe
    assert boundaries[0]["timeMs"] == 5000
    assert boundaries[0]["transitionType"] == "wipe"

    # Second boundary: stock_video -> educational_image => iris
    assert boundaries[1]["timeMs"] == 10000
    assert boundaries[1]["transitionType"] == "iris"


def test_config_flags_propagated(tmp_path: Path):
    """Config flags karaoke_enabled and transitions_enabled flow into props."""
    (tmp_path / "research.json").write_text(json.dumps({"video_title": "Test"}))
    (tmp_path / "phrase_groups.json").write_text(json.dumps([]))
    (tmp_path / "approved_media.json").write_text(json.dumps({"shot_list": []}))

    config = {
        "video_settings": {"resolution": [1080, 1920], "fps": 30},
        "remotion_overlay": {
            "karaoke_enabled": False,
            "edu_reveal_enabled": True,
            "transitions_enabled": True,
        },
    }

    props = build_overlay_props(tmp_path, config, "short_educational", 45000)

    assert props["karaokeEnabled"] is False
    assert props["transitionsEnabled"] is True
    assert props["eduRevealEnabled"] is True


def test_segment_offset_shifts_timestamps(tmp_path: Path):
    """Phrases are filtered and shifted by segment start time."""
    (tmp_path / "research.json").write_text(json.dumps({"video_title": "Test"}))
    (tmp_path / "approved_media.json").write_text(json.dumps({"shot_list": []}))

    # Phrases at absolute times: 5s, 15s, 45s, 50s
    groups = [
        {"text": "early phrase", "startS": 5.0, "endS": 10.0},
        {"text": "mid phrase", "startS": 15.0, "endS": 20.0},
        {"text": "hook phrase", "startS": 45.0, "endS": 48.0},
        {"text": "hook phrase 2", "startS": 50.0, "endS": 53.0},
    ]
    (tmp_path / "phrase_groups.json").write_text(json.dumps(groups))

    config = _make_minimal_config()

    # Build props for hook short starting at 44s, 15s duration
    props = build_overlay_props(tmp_path, config, "short_hook", 15000, segment_start_s=44.0)

    # Should only have the two hook phrases, shifted to 0-relative
    assert len(props["phrases"]) == 2
    assert props["phrases"][0]["text"] == "hook phrase"
    assert props["phrases"][0]["startMs"] == 1000   # 45000 - 44000
    assert props["phrases"][0]["endMs"] == 4000     # 48000 - 44000
    assert props["phrases"][1]["startMs"] == 6000   # 50000 - 44000


def test_segment_offset_zero_returns_all(tmp_path: Path):
    """With segment_start_s=0, all phrases within duration are returned."""
    (tmp_path / "research.json").write_text(json.dumps({"video_title": "Test"}))
    (tmp_path / "approved_media.json").write_text(json.dumps({"shot_list": []}))

    groups = [
        {"text": "phrase 1", "startS": 1.0, "endS": 5.0},
        {"text": "phrase 2", "startS": 10.0, "endS": 15.0},
    ]
    (tmp_path / "phrase_groups.json").write_text(json.dumps(groups))

    config = _make_minimal_config()
    props = build_overlay_props(tmp_path, config, "full", 60000, segment_start_s=0.0)

    assert len(props["phrases"]) == 2
    assert props["phrases"][0]["startMs"] == 1000
    assert props["phrases"][1]["startMs"] == 10000


def test_word_times_clamped_to_phrase_bounds(tmp_path: Path):
    """Words that extend outside their phrase are clamped."""
    (tmp_path / "research.json").write_text(json.dumps({"video_title": "Test"}))
    (tmp_path / "approved_media.json").write_text(json.dumps({"shot_list": []}))

    groups = [
        {"text": "test phrase", "startS": 5.0, "endS": 8.0, "words": [
            {"word": "test", "startS": 4.8, "endS": 5.5},
            {"word": "phrase", "startS": 5.5, "endS": 8.2},
        ]},
    ]
    (tmp_path / "phrase_groups.json").write_text(json.dumps(groups))

    config = _make_minimal_config()
    props = build_overlay_props(tmp_path, config, "full", 30000)

    words = props["phrases"][0]["words"]
    assert words[0]["startMs"] == 5000   # clamped from 4800 to 5000
    assert words[1]["endMs"] == 8000     # clamped from 8200 to 8000


def test_curiosity_hook_used_when_experiment_active(tmp_path):
    """When hook_overhaul experiment is in treatment, use curiosity hook."""
    from remotion_props_builder import build_overlay_props
    from unittest.mock import patch

    (tmp_path / "research.json").write_text(json.dumps({
        "video_title": "How Chocolate Gets Its Snap",
        "key_facts": ["Chocolate has 6 crystal forms", "Only form V snaps"],
    }))
    (tmp_path / "phrase_groups.json").write_text(json.dumps([]))
    (tmp_path / "approved_media.json").write_text(json.dumps({"shot_list": []}))

    config = _make_minimal_config()

    with patch("engagement_experiments.get_engagement_experiment_variant") as mock_exp:
        mock_exp.return_value = "true"
        with patch("remotion_props_builder._generate_curiosity_hook") as mock_hook:
            mock_hook.return_value = "6 crystal forms hide in your chocolate"
            props = build_overlay_props(tmp_path, config, "short_intro", 60000)

    assert props["hookText"] == "6 crystal forms hide in your chocolate"
