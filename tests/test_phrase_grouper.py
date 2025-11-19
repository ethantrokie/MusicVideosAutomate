import pytest
from agents.phrase_grouper import PhraseGrouper


def test_parse_aligned_words_into_phrases():
    """Test parsing aligned words into phrase boundaries."""
    grouper = PhraseGrouper()

    aligned_words = [
        {"word": "Look", "startS": 0.5, "endS": 0.8},
        {"word": "at", "startS": 0.8, "endS": 0.9},
        {"word": "a", "startS": 0.9, "endS": 1.0},
        {"word": "leaf", "startS": 1.0, "endS": 1.3},
        # Gap > 0.3s indicates phrase boundary
        {"word": "It's", "startS": 1.8, "endS": 2.0},
        {"word": "green", "startS": 2.0, "endS": 2.3},
    ]

    phrases = grouper.parse_into_phrases(aligned_words, gap_threshold=0.3)

    assert len(phrases) == 2
    assert phrases[0]["text"] == "Look at a leaf"
    assert phrases[0]["startS"] == 0.5
    assert phrases[0]["endS"] == 1.3
    assert phrases[1]["text"] == "It's green"
