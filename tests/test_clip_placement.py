#!/usr/bin/env python3
"""Tests for clip placement logic."""

import pytest
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'agents'))


class TestClipPlacement:
    """Test clip placement determination."""

    def test_determine_placements_returns_three_clips(self):
        """Test that we always get 3 clip placements."""
        from clip_placement import determine_clip_placements

        # Minimal aligned words
        aligned_words = [
            {"word": "[Verse 1]\nTest ", "startS": 0.5, "endS": 1.0},
            {"word": "lyrics ", "startS": 1.0, "endS": 1.5},
            {"word": "[Chorus]\nMore ", "startS": 30.0, "endS": 30.5},
        ]

        clips = determine_clip_placements(aligned_words)

        assert len(clips) == 3
        assert all("id" in c for c in clips)
        assert all("start_time" in c for c in clips)
        assert all("end_time" in c for c in clips)
        assert all("segment_type" in c for c in clips)

    def test_clips_within_60_seconds(self):
        """Test all clips are placed within first 60 seconds."""
        from clip_placement import determine_clip_placements

        aligned_words = [
            {"word": "Test ", "startS": 0.5, "endS": 1.0},
            {"word": "[Chorus]\nChorus ", "startS": 45.0, "endS": 46.0},
        ]

        clips = determine_clip_placements(aligned_words)

        for clip in clips:
            assert clip["end_time"] <= 60, f"Clip {clip['id']} ends at {clip['end_time']}s"

    def test_clips_are_5_seconds(self):
        """Test each clip is 5 seconds long (default for Kling API)."""
        from clip_placement import determine_clip_placements

        aligned_words = [{"word": "Test ", "startS": 0.5, "endS": 1.0}]

        clips = determine_clip_placements(aligned_words)

        for clip in clips:
            duration = clip["end_time"] - clip["start_time"]
            assert duration == 5, f"Clip {clip['id']} is {duration}s, expected 5s"

    def test_extract_lyrics_for_window(self):
        """Test lyrics extraction for time window."""
        from clip_placement import extract_lyrics_for_clip

        aligned_words = [
            {"word": "[Verse 1]\nHello ", "startS": 0.0, "endS": 0.5},
            {"word": "world ", "startS": 0.5, "endS": 1.0},
            {"word": "test ", "startS": 1.0, "endS": 1.5},
            {"word": "outside ", "startS": 10.0, "endS": 10.5},
        ]

        lyrics = extract_lyrics_for_clip(aligned_words, start=0.0, end=2.0)

        assert "world" in lyrics
        assert "test" in lyrics
        assert "outside" not in lyrics
        assert "[Verse" not in lyrics  # Section markers removed


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
