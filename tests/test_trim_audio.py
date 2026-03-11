#!/usr/bin/env python3
"""Tests for audio intro trimming agent."""

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

# Set OUTPUT_DIR before import
_tmp = tempfile.mkdtemp()
os.environ.setdefault("OUTPUT_DIR", _tmp)

from agents.trim_audio import (
    compute_crop_offset,
    shift_timestamps,
    build_crop_metadata,
    load_config,
    run_trim,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def output_dir(tmp_path):
    """Create a temporary output directory with suno_output.json and song.mp3."""
    suno_data = {
        "song": {"duration": 120.0, "title": "Test Song"},
        "metadata": {"duration": 120.0},
        "alignedWords": [
            {"word": "Hello", "success": True, "startS": 23.5, "endS": 24.0, "palign": 0},
            {"word": "world", "success": True, "startS": 24.5, "endS": 25.0, "palign": 0},
            {"word": "today", "success": True, "startS": 26.0, "endS": 26.5, "palign": 0},
        ],
    }
    (tmp_path / "suno_output.json").write_text(json.dumps(suno_data))
    (tmp_path / "song.mp3").write_bytes(b"fake-audio-data")
    return tmp_path


@pytest.fixture
def short_intro_dir(tmp_path):
    """Output dir where intro is already short (first lyric at 0.16s)."""
    suno_data = {
        "song": {"duration": 120.0},
        "metadata": {"duration": 120.0},
        "alignedWords": [
            {"word": "Quick", "success": True, "startS": 0.16, "endS": 0.5, "palign": 0},
            {"word": "start", "success": True, "startS": 0.6, "endS": 1.0, "palign": 0},
        ],
    }
    (tmp_path / "suno_output.json").write_text(json.dumps(suno_data))
    (tmp_path / "song.mp3").write_bytes(b"fake-audio-data")
    return tmp_path


@pytest.fixture
def config_dir(tmp_path):
    """Create config directory with audio_trim settings."""
    config_path = tmp_path / "config"
    config_path.mkdir()
    config = {
        "audio_trim": {"enabled": True, "max_intro_seconds": 2.0}
    }
    (config_path / "config.json").write_text(json.dumps(config))
    return tmp_path


@pytest.fixture
def disabled_config_dir(tmp_path):
    """Create config directory with audio_trim disabled."""
    config_path = tmp_path / "config"
    config_path.mkdir()
    config = {
        "audio_trim": {"enabled": False, "max_intro_seconds": 2.0}
    }
    (config_path / "config.json").write_text(json.dumps(config))
    return tmp_path


# ── compute_crop_offset ──────────────────────────────────────────────────────


class TestComputeCropOffset:
    def test_long_intro_computes_offset(self):
        words = [
            {"startS": 23.5, "endS": 24.0},
            {"startS": 24.5, "endS": 25.0},
        ]
        offset = compute_crop_offset(words, max_intro_seconds=2.0)
        assert offset == pytest.approx(21.5)  # 23.5 - 2.0

    def test_short_intro_returns_zero(self):
        words = [
            {"startS": 0.16, "endS": 0.5},
            {"startS": 0.6, "endS": 1.0},
        ]
        offset = compute_crop_offset(words, max_intro_seconds=2.0)
        assert offset == 0.0

    def test_exactly_at_threshold_returns_zero(self):
        words = [{"startS": 2.0, "endS": 2.5}]
        offset = compute_crop_offset(words, max_intro_seconds=2.0)
        assert offset == 0.0

    def test_just_over_threshold(self):
        words = [{"startS": 2.2, "endS": 2.5}]
        offset = compute_crop_offset(words, max_intro_seconds=2.0)
        # 2.2 - 2.0 = 0.2, but <= 0.1 threshold means no crop
        # Actually 0.2 > 0.1 so it should crop
        assert offset == pytest.approx(0.2)

    def test_within_tolerance_no_crop(self):
        """Offset <= 0.1 should be treated as no-op."""
        words = [{"startS": 2.05, "endS": 2.5}]
        offset = compute_crop_offset(words, max_intro_seconds=2.0)
        # 2.05 - 2.0 = 0.05, which is <= 0.1 tolerance
        assert offset == 0.0

    def test_empty_words_returns_zero(self):
        offset = compute_crop_offset([], max_intro_seconds=2.0)
        assert offset == 0.0

    def test_custom_max_intro(self):
        words = [{"startS": 10.0, "endS": 10.5}]
        offset = compute_crop_offset(words, max_intro_seconds=5.0)
        assert offset == pytest.approx(5.0)  # 10.0 - 5.0


# ── shift_timestamps ─────────────────────────────────────────────────────────


class TestShiftTimestamps:
    def test_shifts_all_timestamps(self):
        words = [
            {"word": "Hello", "startS": 23.5, "endS": 24.0},
            {"word": "world", "startS": 24.5, "endS": 25.0},
        ]
        shifted = shift_timestamps(words, crop_offset=21.5)
        assert shifted[0]["startS"] == pytest.approx(2.0)
        assert shifted[0]["endS"] == pytest.approx(2.5)
        assert shifted[1]["startS"] == pytest.approx(3.0)
        assert shifted[1]["endS"] == pytest.approx(3.5)

    def test_clamps_to_zero(self):
        """Timestamps should never go below 0."""
        words = [
            {"word": "First", "startS": 1.0, "endS": 1.5},
        ]
        shifted = shift_timestamps(words, crop_offset=2.0)
        assert shifted[0]["startS"] == 0.0
        assert shifted[0]["endS"] == 0.0

    def test_preserves_other_fields(self):
        words = [
            {"word": "Test", "startS": 10.0, "endS": 10.5, "success": True, "palign": 0},
        ]
        shifted = shift_timestamps(words, crop_offset=5.0)
        assert shifted[0]["word"] == "Test"
        assert shifted[0]["success"] is True
        assert shifted[0]["palign"] == 0

    def test_does_not_mutate_original(self):
        words = [{"word": "X", "startS": 10.0, "endS": 10.5}]
        shift_timestamps(words, crop_offset=5.0)
        assert words[0]["startS"] == 10.0  # Original unchanged

    def test_zero_offset_returns_copy(self):
        words = [{"word": "Y", "startS": 5.0, "endS": 5.5}]
        shifted = shift_timestamps(words, crop_offset=0.0)
        assert shifted[0]["startS"] == 5.0
        assert shifted is not words


# ── build_crop_metadata ──────────────────────────────────────────────────────


class TestBuildCropMetadata:
    def test_metadata_values(self):
        meta = build_crop_metadata(
            crop_offset=21.5,
            original_first_lyric=23.5,
            new_first_lyric=2.0,
        )
        assert meta["crop_offset"] == 21.5
        assert meta["original_first_lyric"] == 23.5
        assert meta["new_first_lyric"] == 2.0


# ── load_config ──────────────────────────────────────────────────────────────


class TestLoadConfig:
    def test_loads_enabled_config(self, config_dir):
        cfg = load_config(config_dir)
        assert cfg["enabled"] is True
        assert cfg["max_intro_seconds"] == 2.0

    def test_loads_disabled_config(self, disabled_config_dir):
        cfg = load_config(disabled_config_dir)
        assert cfg["enabled"] is False

    def test_missing_config_returns_defaults(self, tmp_path):
        cfg = load_config(tmp_path)
        assert cfg["enabled"] is True
        assert cfg["max_intro_seconds"] == 2.0


# ── run_trim (integration) ──────────────────────────────────────────────────


class TestRunTrim:
    @patch("agents.trim_audio.crop_audio_file")
    def test_long_intro_trims_and_shifts(self, mock_crop, output_dir):
        mock_crop.return_value = True

        result = run_trim(output_dir, max_intro_seconds=2.0)

        assert result["cropped"] is True
        assert result["crop_offset"] == pytest.approx(21.5)

        # Verify suno_output.json was updated
        updated = json.loads((output_dir / "suno_output.json").read_text())
        assert updated["alignedWords"][0]["startS"] == pytest.approx(2.0)
        assert updated["alignedWords"][1]["startS"] == pytest.approx(3.0)

        # Verify audio_crop.json was written
        crop_meta = json.loads((output_dir / "audio_crop.json").read_text())
        assert crop_meta["crop_offset"] == pytest.approx(21.5)
        assert crop_meta["original_first_lyric"] == pytest.approx(23.5)
        assert crop_meta["new_first_lyric"] == pytest.approx(2.0)

        # Verify duration metadata updated
        assert updated["song"]["duration"] == pytest.approx(120.0 - 21.5)
        assert updated["metadata"]["duration"] == pytest.approx(120.0 - 21.5)

        mock_crop.assert_called_once()

    @patch("agents.trim_audio.crop_audio_file")
    def test_short_intro_no_op(self, mock_crop, short_intro_dir):
        result = run_trim(short_intro_dir, max_intro_seconds=2.0)

        assert result["cropped"] is False
        assert result["crop_offset"] == 0.0
        mock_crop.assert_not_called()

        # suno_output.json should be unchanged
        data = json.loads((short_intro_dir / "suno_output.json").read_text())
        assert data["alignedWords"][0]["startS"] == pytest.approx(0.16)

    @patch("agents.trim_audio.crop_audio_file")
    def test_disabled_config_skips(self, mock_crop, output_dir, disabled_config_dir):
        cfg = load_config(disabled_config_dir)
        result = run_trim(output_dir, enabled=False)

        assert result["cropped"] is False
        assert result["skipped_reason"] == "disabled"
        mock_crop.assert_not_called()

    @patch("agents.trim_audio.crop_audio_file")
    def test_ffmpeg_failure_raises(self, mock_crop, output_dir):
        mock_crop.return_value = False

        with pytest.raises(RuntimeError, match="ffmpeg"):
            run_trim(output_dir, max_intro_seconds=2.0)
