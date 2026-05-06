import json
import tempfile
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent / "agents"))

from remotion_props_builder import build_overlay_props


def test_shareable_stat_passed_from_lyrics_json():
    """shareable_stat from lyrics.json should appear in overlay props."""
    with tempfile.TemporaryDirectory() as tmp:
        run_dir = Path(tmp)
        (run_dir / "research.json").write_text(json.dumps({
            "video_title": "Test Video",
            "key_facts": ["fact1"],
        }))
        (run_dir / "lyrics.json").write_text(json.dumps({
            "lyrics": "[Intro]\nTest lyrics",
            "viral_elements": {
                "display_hook_text": "Test Hook",
                "shareable_stat": "Your brakes pump 18 times per second",
            }
        }))
        (run_dir / "approved_media.json").write_text(json.dumps({"shot_list": []}))

        config = {
            "video_settings": {"resolution": [1080, 1920], "fps": 30},
            "remotion_overlay": {
                "channel_name": "@test",
                "music_indicator_enabled": True,
                "karaoke_enabled": True,
                "edu_reveal_enabled": True,
                "transitions_enabled": False,
            },
        }

        props = build_overlay_props(run_dir, config, "full", 75000)
        assert props["shareableStat"] == "Your brakes pump 18 times per second"


def test_shareable_stat_empty_when_missing():
    """Props should have empty shareableStat when lyrics.json lacks it."""
    with tempfile.TemporaryDirectory() as tmp:
        run_dir = Path(tmp)
        (run_dir / "research.json").write_text(json.dumps({
            "video_title": "Test Video",
        }))
        (run_dir / "lyrics.json").write_text(json.dumps({
            "lyrics": "[Intro]\nTest",
            "viral_elements": {"display_hook_text": "Hook"},
        }))
        (run_dir / "approved_media.json").write_text(json.dumps({"shot_list": []}))

        config = {
            "video_settings": {"resolution": [1080, 1920], "fps": 30},
            "remotion_overlay": {
                "channel_name": "@test",
                "music_indicator_enabled": True,
                "karaoke_enabled": True,
                "edu_reveal_enabled": True,
                "transitions_enabled": False,
            },
        }

        props = build_overlay_props(run_dir, config, "full", 75000)
        assert props["shareableStat"] == ""
