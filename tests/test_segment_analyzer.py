#!/usr/bin/env python3
"""
Unit tests for segment analyzer.
"""

import sys
from pathlib import Path

# Add agents directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'agents'))

from analyze_segments import detect_musical_hook


def test_detect_musical_hook_with_repetition():
    """Test hook detection with repeated chorus."""
    # Mock lyrics with repeated chorus
    lyrics = {
        'words': [
            {'word': 'Verse', 'start': 0.0, 'end': 1.0},
            {'word': 'line', 'start': 1.0, 'end': 2.0},
            {'word': 'one.', 'start': 2.0, 'end': 3.0},
            {'word': 'Chorus', 'start': 10.0, 'end': 11.0},
            {'word': 'hook', 'start': 11.0, 'end': 12.0},
            {'word': 'line.', 'start': 12.0, 'end': 13.0},
            {'word': 'More', 'start': 20.0, 'end': 21.0},
            {'word': 'verse.', 'start': 21.0, 'end': 22.0},
            {'word': 'Chorus', 'start': 30.0, 'end': 31.0},  # Repeated
            {'word': 'hook', 'start': 31.0, 'end': 32.0},    # Repeated
            {'word': 'line.', 'start': 32.0, 'end': 33.0},   # Repeated
            {'word': 'Final', 'start': 40.0, 'end': 41.0},
            {'word': 'verse.', 'start': 41.0, 'end': 42.0},
        ],
        'metadata': {'duration': 45.0}
    }

    result = detect_musical_hook(lyrics, min_duration=5, max_duration=60)

    assert 'start' in result
    assert 'end' in result
    assert 'duration' in result
    assert 'rationale' in result
    assert result['start'] >= 0
    assert result['duration'] >= 5
    assert result['duration'] <= 60
    print("✓ Hook detection with repetition works")


def test_detect_musical_hook_fallback():
    """Test hook detection fallback when no repetition."""
    lyrics = {
        'words': [
            {'word': 'Unique', 'start': 0.0, 'end': 1.0},
            {'word': 'word', 'start': 1.0, 'end': 2.0},
            {'word': 'every', 'start': 2.0, 'end': 3.0},
            {'word': 'time.', 'start': 3.0, 'end': 4.0},
            # Add enough words to go past 90s
            *[{'word': f'word{i}', 'start': float(i+5), 'end': float(i+6)} for i in range(90)]
        ],
        'metadata': {'duration': 100.0}
    }

    result = detect_musical_hook(lyrics, min_duration=30, max_duration=60)

    assert result['start'] == 30  # Fallback position
    assert result['rationale'].startswith('Fallback')
    print("✓ Hook detection fallback works")


def run_tests():
    """Run all tests."""
    print("Running segment analyzer tests...")
    test_detect_musical_hook_with_repetition()
    test_detect_musical_hook_fallback()
    print("✅ All segment analyzer tests passed!")


if __name__ == '__main__':
    run_tests()
