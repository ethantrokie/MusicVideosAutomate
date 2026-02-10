#!/usr/bin/env python3
"""Tests for audio utilities."""

import pytest
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'agents'))


class TestAudioSlicing:
    """Test audio slicing functionality."""

    def test_slice_audio_creates_file(self):
        """Test that slice_audio creates output file."""
        from audio_utils import slice_audio

        # Use an existing song file from outputs if available
        test_songs = list(Path("outputs/runs").glob("*/song.mp3"))
        if not test_songs:
            pytest.skip("No song.mp3 files available for testing")

        song_path = str(test_songs[0])

        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
            output_path = tmp.name

        try:
            result = slice_audio(song_path, start=5.0, duration=8.0, output_path=output_path)

            assert result is True
            assert os.path.exists(output_path)
            assert os.path.getsize(output_path) > 0
        finally:
            if os.path.exists(output_path):
                os.unlink(output_path)

    def test_slice_audio_invalid_path_returns_false(self):
        """Test that invalid input path returns False."""
        from audio_utils import slice_audio

        result = slice_audio(
            "/nonexistent/path.mp3",
            start=0,
            duration=8,
            output_path="/tmp/test_output.mp3"
        )

        assert result is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
