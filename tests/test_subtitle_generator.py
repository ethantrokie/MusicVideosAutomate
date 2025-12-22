#!/usr/bin/env python3
"""
Unit tests for subtitle generator.
"""

import sys
from pathlib import Path
import tempfile

# Add agents directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'agents'))

from generate_subtitles import (
    format_srt_timestamp,
    format_ass_timestamp,
    generate_traditional_srt,
    generate_karaoke_srt,
    generate_phrase_highlight_ass
)


def test_format_srt_timestamp():
    """Test SRT timestamp formatting."""
    assert format_srt_timestamp(0.0) == "00:00:00,000"
    assert format_srt_timestamp(1.5) == "00:00:01,500"
    assert format_srt_timestamp(61.234) == "00:01:01,234"
    assert format_srt_timestamp(3661.567) == "01:01:01,567"
    print("✓ SRT timestamp formatting works")


def test_format_ass_timestamp():
    """Test ASS timestamp formatting."""
    assert format_ass_timestamp(0.0) == "0:00:00.00"
    assert format_ass_timestamp(1.5) == "0:00:01.50"
    assert format_ass_timestamp(61.234) == "0:01:01.23"
    assert format_ass_timestamp(3661.567) == "1:01:01.56"
    print("✓ ASS timestamp formatting works")


def test_generate_traditional_srt():
    """Test traditional subtitle generation."""
    words = [
        {'word': 'Hello', 'start': 0.0, 'end': 0.5},
        {'word': 'world', 'start': 0.5, 'end': 1.0},
        {'word': 'this', 'start': 1.0, 'end': 1.5},
        {'word': 'is', 'start': 1.5, 'end': 2.0},
        {'word': 'a', 'start': 2.0, 'end': 2.2},
        {'word': 'test.', 'start': 2.2, 'end': 2.5},
        {'word': 'Another', 'start': 3.0, 'end': 3.5},
        {'word': 'sentence.', 'start': 3.5, 'end': 4.0},
    ]

    with tempfile.NamedTemporaryFile(mode='w', suffix='.srt', delete=False) as f:
        output_path = Path(f.name)

    try:
        generate_traditional_srt(words, output_path, min_duration=2.0, max_duration=3.5)

        content = output_path.read_text()
        assert content.strip()  # File not empty
        assert '00:00:00,000 --> ' in content  # Has timestamp
        assert 'Hello world' in content  # Has grouped words
        print("✓ Traditional SRT generation works")

    finally:
        output_path.unlink()


def test_generate_karaoke_srt():
    """Test karaoke subtitle generation."""
    words = [
        {'word': 'Hello', 'start': 0.0, 'end': 0.5},
        {'word': 'world', 'start': 0.5, 'end': 1.0},
        {'word': 'test', 'start': 1.0, 'end': 1.5},
    ]

    with tempfile.NamedTemporaryFile(mode='w', suffix='.srt', delete=False) as f:
        output_path = Path(f.name)

    try:
        generate_karaoke_srt(words, output_path)

        content = output_path.read_text()
        lines = content.strip().split('\n')

        # Should have 3 word entries (each with 4 lines: number, timestamp, word, blank)
        assert len([l for l in lines if l == 'Hello']) == 1
        assert len([l for l in lines if l == 'world']) == 1
        assert len([l for l in lines if l == 'test']) == 1
        print("✓ Karaoke SRT generation works")

    finally:
        output_path.unlink()


def test_generate_phrase_highlight_ass():
    """Test phrase-highlight ASS subtitle generation."""
    words = [
        {'word': 'Hello', 'start': 0.0, 'end': 0.5},
        {'word': 'world', 'start': 0.5, 'end': 1.0},
        {'word': 'this', 'start': 1.0, 'end': 1.5},
        {'word': 'is', 'start': 1.5, 'end': 2.0},
        {'word': 'a', 'start': 2.0, 'end': 2.5},
        {'word': 'test.', 'start': 2.5, 'end': 3.0},
        {'word': 'Another', 'start': 3.5, 'end': 4.0},
        {'word': 'phrase', 'start': 4.0, 'end': 4.5},
        {'word': 'here.', 'start': 4.5, 'end': 5.0},
    ]

    with tempfile.NamedTemporaryFile(mode='w', suffix='.ass', delete=False) as f:
        output_path = Path(f.name)

    try:
        generate_phrase_highlight_ass(words, output_path, min_words=3, max_words=5)

        content = output_path.read_text()
        
        # Check for ASS header elements
        assert '[Script Info]' in content
        assert 'PlayResX:' in content
        assert '[V4+ Styles]' in content
        assert 'Style: Karaoke' in content
        assert '[Events]' in content
        
        # Check for karaoke tags
        assert '\\kf' in content  # Has karaoke tags
        assert 'Dialogue:' in content  # Has dialogue lines
        
        # Check words are present
        assert 'Hello' in content
        assert 'world' in content
        
        print("✓ Phrase-highlight ASS generation works")

    finally:
        output_path.unlink()


def run_tests():
    """Run all tests."""
    print("Running subtitle generator tests...")
    test_format_srt_timestamp()
    test_format_ass_timestamp()
    test_generate_traditional_srt()
    test_generate_karaoke_srt()
    test_generate_phrase_highlight_ass()
    print("✅ All subtitle generator tests passed!")


if __name__ == '__main__':
    run_tests()

