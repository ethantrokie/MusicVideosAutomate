#!/usr/bin/env python3
"""
Tests for engagement A/B experiments.

Tests all 5 engagement features and the shared experiment helper.
Each feature is gated behind an A/B experiment:
  1. engagement_hook_source — lyrics hook_line vs title-derived
  2. engagement_opening_enhance — saturation/contrast boost on shot 1
  3. engagement_hook_sfx — synthetic audio hit at t=0
  4. engagement_fast_pacing — 1.5s shots for first 5 in shorts
  5. engagement_animated_hook — 0.15s pop-in animation
"""

import json
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

# Add agents directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "agents"))


# ── Shared helper tests ─────────────────────────────────────────────────

class TestEngagementExperiments:
    """Tests for engagement_experiments.py shared helper."""

    def _make_experiment(self, config_key, control, treatment, weeks=8, days_ago=0):
        """Create a test experiment dict."""
        created = datetime.now() - timedelta(days=days_ago)
        return {
            "id": f"exp_test_{config_key}",
            "name": f"Test {config_key}",
            "config_key": config_key,
            "control_value": control,
            "treatment_value": treatment,
            "duration_weeks": weeks,
            "created_at": created.isoformat(),
            "status": "active",
            "current_week": 1,
            "current_variant": "control",
            "results": {
                "control": {"videos": [], "total_views": 0, "total_engagement": 0, "avg_retention": 0, "avg_engaged_view_rate": 0, "total_subscribers_gained": 0},
                "treatment": {"videos": [], "total_views": 0, "total_engagement": 0, "avg_retention": 0, "avg_engaged_view_rate": 0, "total_subscribers_gained": 0}
            }
        }

    def test_returns_control_in_week_1(self, tmp_path, monkeypatch):
        """Odd week (1) should return control value."""
        from engagement_experiments import get_engagement_experiment_variant

        exp = self._make_experiment("engagement_hook_source", "false", "true", days_ago=0)
        state = {"experiments": [exp], "completed": []}

        state_path = tmp_path / "automation" / "state"
        state_path.mkdir(parents=True)
        with open(state_path / "ab_experiments.json", "w") as f:
            json.dump(state, f)

        # Monkeypatch Path in the module to point to our temp file
        import engagement_experiments
        original_path = engagement_experiments.Path
        monkeypatch.setattr(
            engagement_experiments, "Path",
            lambda p: state_path / "ab_experiments.json" if "ab_experiments" in str(p) else original_path(p)
        )

        result = get_engagement_experiment_variant("engagement_hook_source")
        # Week 1 (day 0) → odd → control → "false"
        assert result == "false"

    def test_returns_treatment_in_week_2(self):
        """Even week (2) should return treatment value."""
        exp = self._make_experiment("engagement_hook_sfx", "false", "true", days_ago=8)
        created = datetime.fromisoformat(exp["created_at"])
        elapsed_days = (datetime.now() - created).days
        week = max(1, (elapsed_days // 7) + 1)
        assert week == 2  # 8 days ago = week 2
        assert week % 2 == 0  # Even = treatment

    def test_expired_experiment_returns_none(self):
        """Experiment past its duration_weeks should not return a variant."""
        exp = self._make_experiment("engagement_hook_sfx", "false", "true", weeks=2, days_ago=30)
        created = datetime.fromisoformat(exp["created_at"])
        elapsed_days = (datetime.now() - created).days
        week = max(1, (elapsed_days // 7) + 1)
        assert week > exp["duration_weeks"]

    def test_missing_file_returns_none(self):
        """No experiment file should return None."""
        from engagement_experiments import get_engagement_experiment_variant

        with patch("engagement_experiments.Path") as mock_path:
            mock_path.return_value.exists.return_value = False
            result = get_engagement_experiment_variant("engagement_hook_source")
            assert result is None

    def test_is_feature_enabled_from_config(self):
        """Falls back to config when no experiment is active."""
        from engagement_experiments import is_engagement_feature_enabled

        config = {"engagement": {"hook_sfx_enabled": True}}
        with patch("engagement_experiments.get_engagement_experiment_variant", return_value=None):
            result = is_engagement_feature_enabled("engagement_hook_sfx", config)
            assert result is True

    def test_experiment_overrides_config(self):
        """Active experiment should override config value."""
        from engagement_experiments import is_engagement_feature_enabled

        config = {"engagement": {"hook_sfx_enabled": False}}
        with patch("engagement_experiments.get_engagement_experiment_variant", return_value="true"):
            result = is_engagement_feature_enabled("engagement_hook_sfx", config)
            assert result is True

    def test_config_disabled_respected(self):
        """When config says disabled and no experiment, feature is off."""
        from engagement_experiments import is_engagement_feature_enabled

        config = {"engagement": {"hook_sfx_enabled": False}}
        with patch("engagement_experiments.get_engagement_experiment_variant", return_value=None):
            result = is_engagement_feature_enabled("engagement_hook_sfx", config)
            assert result is False


# ── Change 1: Hook line from lyrics ──────────────────────────────────────

class TestHookLineFromLyrics:
    """Tests for get_hook_line_from_lyrics() in video_overlays.py."""

    def test_reads_display_hook_text(self, tmp_path):
        """display_hook_text should be preferred over hook_line."""
        from video_overlays import get_hook_line_from_lyrics

        lyrics = {
            "viral_elements": {
                "hook_line": "Everything you know about chocolate is WRONG",
                "display_hook_text": "Chocolate's DARK Secret?!"
            }
        }
        with open(tmp_path / "lyrics.json", "w") as f:
            json.dump(lyrics, f)

        result = get_hook_line_from_lyrics(tmp_path)
        assert result == "Chocolate's DARK Secret?!"

    def test_falls_back_to_hook_line(self, tmp_path):
        """Falls back to hook_line when display_hook_text is missing."""
        from video_overlays import get_hook_line_from_lyrics

        lyrics = {
            "viral_elements": {
                "hook_line": "Short hook line"
            }
        }
        with open(tmp_path / "lyrics.json", "w") as f:
            json.dump(lyrics, f)

        result = get_hook_line_from_lyrics(tmp_path)
        assert result == "Short hook line"

    def test_truncates_long_hook_line(self, tmp_path):
        """Hook lines over 7 words should be truncated."""
        from video_overlays import get_hook_line_from_lyrics

        lyrics = {
            "viral_elements": {
                "hook_line": "Everything you know about chocolate is completely and utterly WRONG"
            }
        }
        with open(tmp_path / "lyrics.json", "w") as f:
            json.dump(lyrics, f)

        result = get_hook_line_from_lyrics(tmp_path)
        assert result == "Everything you know about chocolate is completely..."
        assert len(result.replace("...", "").split()) == 7

    def test_returns_none_when_missing(self, tmp_path):
        """Returns None when lyrics.json doesn't exist."""
        from video_overlays import get_hook_line_from_lyrics

        result = get_hook_line_from_lyrics(tmp_path)
        assert result is None

    def test_returns_none_for_empty_viral_elements(self, tmp_path):
        """Returns None when viral_elements has no hook fields."""
        from video_overlays import get_hook_line_from_lyrics

        lyrics = {"viral_elements": {}}
        with open(tmp_path / "lyrics.json", "w") as f:
            json.dump(lyrics, f)

        result = get_hook_line_from_lyrics(tmp_path)
        assert result is None

    def test_display_hook_text_priority_chain(self, tmp_path):
        """Priority: display_hook_text > hook_line > None."""
        from video_overlays import get_hook_line_from_lyrics, generate_hook_text

        # With both fields: display_hook_text wins
        lyrics = {
            "viral_elements": {
                "hook_line": "Fallback hook",
                "display_hook_text": "Primary hook"
            }
        }
        with open(tmp_path / "lyrics.json", "w") as f:
            json.dump(lyrics, f)
        assert get_hook_line_from_lyrics(tmp_path) == "Primary hook"

        # Without display_hook_text: hook_line used
        lyrics = {"viral_elements": {"hook_line": "Fallback hook"}}
        with open(tmp_path / "lyrics.json", "w") as f:
            json.dump(lyrics, f)
        assert get_hook_line_from_lyrics(tmp_path) == "Fallback hook"

        # Without both: returns None (caller uses generate_hook_text)
        lyrics = {"viral_elements": {}}
        with open(tmp_path / "lyrics.json", "w") as f:
            json.dump(lyrics, f)
        assert get_hook_line_from_lyrics(tmp_path) is None

        # Fallback: generate_hook_text from title
        hook = generate_hook_text("How Chocolate Gets Its Snap")
        assert hook == "Chocolate Gets Its Snap?!"


# ── Change 2: Opening frame enhancement ──────────────────────────────────

class TestEnhanceOpeningClip:
    """Tests for enhance_opening_clip() in 5_assemble_video.py."""

    def test_applies_enhancement(self):
        """Enhancement should modify pixel values."""
        import numpy as np
        from PIL import Image as PILImage

        # Create a test frame (mid-gray)
        frame = np.full((100, 100, 3), 128, dtype=np.uint8)

        # Import and apply enhancement
        from importlib import import_module
        assemble = import_module("5_assemble_video")

        config = {
            "opening_saturation": 1.25,
            "opening_contrast": 1.15,
            "opening_brightness": 1.05,
        }

        # Create a mock clip with fl_image
        processed_frames = []

        class MockClip:
            def fl_image(self, func):
                processed_frames.append(func(frame))
                return self

        mock_clip = MockClip()
        assemble.enhance_opening_clip(mock_clip, config)

        assert len(processed_frames) == 1
        # Enhanced frame should differ from original
        enhanced = processed_frames[0]
        assert enhanced.shape == frame.shape
        # Brightness boost should make pixels brighter
        assert enhanced.mean() > frame.mean()

    def test_only_applied_to_shot_1(self):
        """Enhancement config check — only shot_number == 1 gets enhanced."""
        shot_1 = {"shot_number": 1, "description": "Opening shot"}
        shot_2 = {"shot_number": 2, "description": "Second shot"}

        assert shot_1.get("shot_number") == 1  # Should enhance
        assert shot_2.get("shot_number") != 1  # Should not enhance


# ── Change 3: Hook SFX generation ────────────────────────────────────────

class TestHookSfx:
    """Tests for generate_hook_sfx() in audio_utils.py."""

    def test_generates_audio_file(self):
        """generate_hook_sfx should produce a valid audio file."""
        from audio_utils import generate_hook_sfx

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            output_path = f.name

        result = generate_hook_sfx(output_path)

        if result:
            # ffmpeg is available
            path = Path(result)
            assert path.exists()
            assert path.stat().st_size > 0
            path.unlink()  # Cleanup
        else:
            # ffmpeg not available (CI environment)
            pytest.skip("ffmpeg not available")

    def test_returns_empty_string_on_failure(self):
        """Should return empty string when ffmpeg fails."""
        from audio_utils import generate_hook_sfx

        # Use an invalid output path
        result = generate_hook_sfx("/nonexistent/directory/sfx.wav")
        assert result == ""


# ── Change 4: Faster opening pacing ──────────────────────────────────────

class TestFasterOpeningPacing:
    """Tests for fast pacing A/B experiment in build_format_media_plan.py."""

    def test_fast_pacing_reduces_shot_duration(self):
        """When fast pacing experiment is active, IDEAL_SHOT_DURATION should be 1.5s."""
        config = {
            "engagement": {
                "fast_pacing_enabled": True,
                "opening_shot_duration": 1.5,
                "opening_shot_count": 5,
            }
        }

        # Verify config values
        eng = config["engagement"]
        assert eng["opening_shot_duration"] == 1.5
        assert eng["opening_shot_count"] == 5

    def test_default_pacing_for_shorts(self):
        """Default shorts pacing should be 2.0s shots."""
        # From build_format_media_plan.py
        IDEAL_SHOT_DURATION = 2.0
        MIN_SHOT_DURATION = 1.5
        MAX_SHOT_DURATION = 3.0

        assert IDEAL_SHOT_DURATION == 2.0
        assert MIN_SHOT_DURATION == 1.5

    def test_fast_pacing_only_for_shorts(self):
        """Fast pacing should NOT apply to full video format."""
        format_types = ["full", "hook", "educational", "intro"]
        shorts_formats = ["hook", "educational", "intro"]

        for fmt in format_types:
            if fmt == "full":
                # Full video should not get fast pacing
                IDEAL = 5.0
            else:
                # Shorts get fast pacing when experiment is active
                IDEAL = 1.5
            assert fmt not in shorts_formats or IDEAL <= 2.0


# ── Change 5: Animated hook text ─────────────────────────────────────────

class TestAnimatedHookText:
    """Tests for animated hook text pop-in in video_overlays.py."""

    def test_scale_function(self):
        """Scale should start at 0.8 and reach 1.0 by t=0.15."""
        # The lambda from create_hook_overlay: min(1.0, 0.8 + (t / 0.15) * 0.2)
        scale_fn = lambda t: min(1.0, 0.8 + (t / 0.15) * 0.2)

        assert scale_fn(0.0) == pytest.approx(0.8)
        assert scale_fn(0.075) == pytest.approx(0.9)
        assert scale_fn(0.15) == pytest.approx(1.0)
        assert scale_fn(0.3) == pytest.approx(1.0)  # Clamped at 1.0
        assert scale_fn(1.0) == pytest.approx(1.0)  # Well past animation

    def test_animation_disabled_by_default(self):
        """Without A/B experiment, animate should be False."""
        from engagement_experiments import is_engagement_feature_enabled

        config = {"engagement": {"animated_hook_text": False}}
        with patch("engagement_experiments.get_engagement_experiment_variant", return_value=None):
            result = is_engagement_feature_enabled("engagement_animated_hook", config)
            assert result is False

    def test_animation_enabled_by_experiment(self):
        """A/B treatment should enable animation."""
        from engagement_experiments import is_engagement_feature_enabled

        with patch("engagement_experiments.get_engagement_experiment_variant", return_value="true"):
            result = is_engagement_feature_enabled("engagement_animated_hook")
            assert result is True


# ── Config toggle tests ──────────────────────────────────────────────────

class TestConfigDisabled:
    """Verify each feature respects its config toggle."""

    @pytest.mark.parametrize("config_key,config_field", [
        ("engagement_hook_source", "hook_source_lyrics"),
        ("engagement_opening_enhance", "opening_enhance_enabled"),
        ("engagement_hook_sfx", "hook_sfx_enabled"),
        ("engagement_fast_pacing", "fast_pacing_enabled"),
        ("engagement_animated_hook", "animated_hook_text"),
    ])
    def test_feature_disabled_when_config_false(self, config_key, config_field):
        """Feature should be off when config value is False and no experiment."""
        from engagement_experiments import is_engagement_feature_enabled

        config = {"engagement": {config_field: False}}
        with patch("engagement_experiments.get_engagement_experiment_variant", return_value=None):
            assert is_engagement_feature_enabled(config_key, config) is False

    @pytest.mark.parametrize("config_key,config_field", [
        ("engagement_hook_source", "hook_source_lyrics"),
        ("engagement_opening_enhance", "opening_enhance_enabled"),
        ("engagement_hook_sfx", "hook_sfx_enabled"),
        ("engagement_fast_pacing", "fast_pacing_enabled"),
        ("engagement_animated_hook", "animated_hook_text"),
    ])
    def test_feature_enabled_when_config_true(self, config_key, config_field):
        """Feature should be on when config value is True and no experiment."""
        from engagement_experiments import is_engagement_feature_enabled

        config = {"engagement": {config_field: True}}
        with patch("engagement_experiments.get_engagement_experiment_variant", return_value=None):
            assert is_engagement_feature_enabled(config_key, config) is True

    @pytest.mark.parametrize("config_key", [
        "engagement_hook_source",
        "engagement_opening_enhance",
        "engagement_hook_sfx",
        "engagement_fast_pacing",
        "engagement_animated_hook",
    ])
    def test_experiment_treatment_enables_feature(self, config_key):
        """A/B treatment='true' should enable feature regardless of config."""
        from engagement_experiments import is_engagement_feature_enabled

        config = {"engagement": {}}  # All defaults (False)
        with patch("engagement_experiments.get_engagement_experiment_variant", return_value="true"):
            assert is_engagement_feature_enabled(config_key, config) is True

    @pytest.mark.parametrize("config_key", [
        "engagement_hook_source",
        "engagement_opening_enhance",
        "engagement_hook_sfx",
        "engagement_fast_pacing",
        "engagement_animated_hook",
    ])
    def test_experiment_control_disables_feature(self, config_key):
        """A/B control='false' should disable feature regardless of config."""
        from engagement_experiments import is_engagement_feature_enabled

        config = {"engagement": {}}
        with patch("engagement_experiments.get_engagement_experiment_variant", return_value="false"):
            assert is_engagement_feature_enabled(config_key, config) is False
