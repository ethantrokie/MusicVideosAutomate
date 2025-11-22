#!/usr/bin/env python3
"""Tests for clip consolidation logic."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / 'agents'))

from consolidate_clips import consolidate_phrase_groups


def test_consolidate_merges_short_consecutive_groups():
    """Should merge consecutive phrase groups under target duration."""
    phrase_groups = [
        {
            "group_id": 1,
            "topic": "chlorophyll",
            "start_time": 0.0,
            "end_time": 2.0,
            "duration": 2.0,
            "key_terms": ["chlorophyll", "green"]
        },
        {
            "group_id": 2,
            "topic": "chlorophyll structure",
            "start_time": 2.1,
            "end_time": 4.0,
            "duration": 1.9,
            "key_terms": ["chlorophyll", "molecule"]
        },
        {
            "group_id": 3,
            "topic": "photosynthesis",
            "start_time": 4.2,
            "end_time": 7.0,
            "duration": 2.8,
            "key_terms": ["photosynthesis", "light"]
        }
    ]

    config = {
        "target_clip_duration": 8.0,
        "min_clip_duration": 4.0,
        "max_clip_duration": 15.0,
        "semantic_coherence_threshold": 0.7
    }

    result = consolidate_phrase_groups(phrase_groups, config)

    # Should consolidate groups 1+2 (similar topics) into one clip
    assert len(result) == 2
    assert result[0]["duration"] >= 3.9  # Groups 1+2 combined
    assert len(result[0]["phrase_groups"]) == 2
    assert result[1]["duration"] == 2.8  # Group 3 alone


def test_consolidate_respects_max_duration():
    """Should not exceed max_clip_duration."""
    phrase_groups = [
        {"group_id": i, "topic": "test", "start_time": i*5.0,
         "end_time": (i+1)*5.0, "duration": 5.0, "key_terms": ["test"]}
        for i in range(5)
    ]

    config = {
        "target_clip_duration": 8.0,
        "min_clip_duration": 4.0,
        "max_clip_duration": 12.0,
        "semantic_coherence_threshold": 0.9
    }

    result = consolidate_phrase_groups(phrase_groups, config)

    # No clip should exceed 12s
    for clip in result:
        assert clip["duration"] <= 12.0


def test_consolidate_preserves_phrase_group_metadata():
    """Should keep original phrase groups for subtitle timing."""
    phrase_groups = [
        {
            "group_id": 1,
            "topic": "test",
            "phrases": [{"text": "hello", "startS": 0.0, "endS": 1.0}],
            "start_time": 0.0,
            "end_time": 2.0,
            "duration": 2.0,
            "key_terms": ["test"]
        },
        {
            "group_id": 2,
            "topic": "test2",
            "phrases": [{"text": "world", "startS": 2.0, "endS": 3.0}],
            "start_time": 2.0,
            "end_time": 4.0,
            "duration": 2.0,
            "key_terms": ["test"]
        }
    ]

    config = {
        "target_clip_duration": 8.0,
        "min_clip_duration": 4.0,
        "max_clip_duration": 15.0,
        "semantic_coherence_threshold": 0.8
    }

    result = consolidate_phrase_groups(phrase_groups, config)

    # Should preserve phrase data for subtitles
    assert len(result[0]["phrase_groups"]) == 2
    assert result[0]["phrase_groups"][0]["phrases"][0]["text"] == "hello"
    assert result[0]["phrase_groups"][1]["phrases"][0]["text"] == "world"
