import pytest
import numpy as np
from agents.semantic_matcher import SemanticMatcher


def test_match_videos_to_groups():
    """Test CLIP + keyword boosting matching."""
    matcher = SemanticMatcher()

    phrase_groups = [
        {
            "group_id": 1,
            "topic": "ATP synthase molecular motor",
            "key_terms": ["atp synthase", "molecular motor"],
            "duration": 5.0,
            "phrases": [{"text": "ATP synthase spins like a motor"}]
        }
    ]

    available_media = [
        {
            "url": "video1.mp4",
            "description": "ATP synthase rotating and producing energy"
        },
        {
            "url": "video2.mp4",
            "description": "plant cell structure"
        }
    ]

    matched = matcher.match_videos_to_groups(phrase_groups, available_media)

    assert len(matched) == 1
    assert matched[0]["video_url"] == "video1.mp4"
    assert matched[0]["match_score"] > 0.5
