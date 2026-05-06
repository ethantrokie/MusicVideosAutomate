import json
import pytest
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "agents"))


def test_detect_no_repair_needed():
    from repair_suno_alignment import detect_and_repair

    lyrics = "[Intro]\nLine one here\nLine two here\n"
    aligned = [
        {"word": "[Intro]\n", "startS": 0.0, "endS": 0.1},
        {"word": "Line ", "startS": 0.5, "endS": 0.7},
        {"word": "one ", "startS": 0.7, "endS": 0.9},
        {"word": "here\n", "startS": 0.9, "endS": 1.2},
        {"word": "Line ", "startS": 1.5, "endS": 1.7},
        {"word": "two ", "startS": 1.7, "endS": 1.9},
        {"word": "here\n", "startS": 1.9, "endS": 2.2},
    ]

    repaired, stats = detect_and_repair(lyrics, aligned)
    assert not stats["repair_needed"]


def test_detect_dropped_first_line():
    from repair_suno_alignment import detect_and_repair

    lyrics = "[Intro]\nYou click a lighter\nNo batteries no fuel\nBut hidden inside\n"
    aligned = [
        {"word": "[Intro]\nNo ", "startS": 0.08, "endS": 0.32},
        {"word": "batteries ", "startS": 0.32, "endS": 0.74},
        {"word": "no ", "startS": 0.85, "endS": 1.0},
        {"word": "fuel\n", "startS": 1.0, "endS": 1.5},
        {"word": "But ", "startS": 2.0, "endS": 2.2},
        {"word": "hidden ", "startS": 2.2, "endS": 2.5},
        {"word": "inside\n", "startS": 2.5, "endS": 3.0},
    ]

    repaired, stats = detect_and_repair(lyrics, aligned)
    assert stats["repair_needed"]
    assert stats["dropped"] >= 1

    repaired_text = ' '.join(w['word'].strip() for w in repaired)
    assert "click" in repaired_text.lower() or "lighter" in repaired_text.lower()


def test_interpolated_timestamps_between_neighbors():
    from repair_suno_alignment import detect_and_repair

    lyrics = "Line A\nLine B dropped\nLine C\n"
    aligned = [
        {"word": "Line ", "startS": 1.0, "endS": 1.2},
        {"word": "A\n", "startS": 1.2, "endS": 2.0},
        {"word": "Line ", "startS": 5.0, "endS": 5.2},
        {"word": "C\n", "startS": 5.2, "endS": 6.0},
    ]

    repaired, stats = detect_and_repair(lyrics, aligned)
    assert stats["repair_needed"]

    b_words = [w for w in repaired if "B" in w.get("word", "") or "dropped" in w.get("word", "")]
    assert len(b_words) > 0

    for w in b_words:
        assert 2.0 <= w["startS"] <= 5.0
        assert 2.0 <= w["endS"] <= 5.0


def test_normalize_line_strips_tags():
    from repair_suno_alignment import _normalize_line

    assert _normalize_line("[Intro]") == ""
    assert _normalize_line("[Verse 1]") == ""
    assert _normalize_line("Hello world!") == "hello world"
    assert _normalize_line("  No batteries, no fuel  ") == "no batteries no fuel"


def test_extract_aligned_lines():
    from repair_suno_alignment import _extract_aligned_lines

    aligned = [
        {"word": "Hello ", "startS": 0.0, "endS": 0.5},
        {"word": "world\n", "startS": 0.5, "endS": 1.0},
        {"word": "Next ", "startS": 1.5, "endS": 1.8},
        {"word": "line\n", "startS": 1.8, "endS": 2.2},
    ]

    lines = _extract_aligned_lines(aligned)
    assert len(lines) == 2
    assert lines[0]["text"] == "Hello world"
    assert lines[0]["start_s"] == 0.0
    assert lines[1]["text"] == "Next line"
