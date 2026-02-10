#!/usr/bin/env python3
"""Clip placement logic for AI video generation."""

from typing import Dict, List


def determine_clip_placements(aligned_words: List[Dict], clip_duration: int = 8) -> List[Dict]:
    """
    Determine 3 clip placements within first 60 seconds based on song structure.

    Args:
        aligned_words: List of aligned word dicts with startS, endS, word
        clip_duration: Duration of each clip in seconds

    Returns:
        List of 3 clip definitions with id, start_time, end_time, segment_type
    """
    clips = []

    # Find verse and chorus markers
    verse_start = None
    chorus_start = None
    first_word_start = 0.5  # Default if no words found

    for word in aligned_words:
        text = word.get("word", "")
        start = word.get("startS", 0)

        # Track first actual word
        if first_word_start == 0.5 and start > 0:
            first_word_start = start

        # Find section markers
        if "[Verse" in text and verse_start is None:
            verse_start = start
        if "[Chorus]" in text and chorus_start is None:
            chorus_start = start

    # Clip 1: Intro (start of song)
    intro_start = max(0, first_word_start - 0.5)
    clips.append({
        "id": 1,
        "start_time": intro_start,
        "end_time": intro_start + clip_duration,
        "segment_type": "intro"
    })

    # Clip 2: Verse (around 15-20 seconds)
    if verse_start and 10 < verse_start < 44:
        verse_placement = verse_start
    else:
        verse_placement = 15

    # Ensure we don't overlap with clip 1
    if verse_placement < clips[0]["end_time"] + 2:
        verse_placement = clips[0]["end_time"] + 2

    # Ensure clip 2 ends within 60 seconds with room for clip 3
    if verse_placement + clip_duration > 42:
        verse_placement = 34  # 34 + 8 = 42, leaves room for clip 3

    clips.append({
        "id": 2,
        "start_time": verse_placement,
        "end_time": verse_placement + clip_duration,
        "segment_type": "verse"
    })

    # Clip 3: Chorus (around 30-45 seconds)
    if chorus_start and 25 < chorus_start < 52:
        chorus_placement = chorus_start
    else:
        chorus_placement = 38

    # Ensure we don't overlap with clip 2
    if chorus_placement < clips[1]["end_time"] + 2:
        chorus_placement = clips[1]["end_time"] + 2

    # Ensure clip ends within 60 seconds
    if chorus_placement + clip_duration > 60:
        chorus_placement = 52  # 52 + 8 = 60

    clips.append({
        "id": 3,
        "start_time": chorus_placement,
        "end_time": chorus_placement + clip_duration,
        "segment_type": "chorus"
    })

    return clips


def extract_lyrics_for_clip(aligned_words: List[Dict], start: float, end: float) -> str:
    """
    Extract lyrics text for a specific time window.

    Args:
        aligned_words: List of aligned word dicts
        start: Start time in seconds
        end: End time in seconds

    Returns:
        Concatenated lyrics for the time window
    """
    lyrics = []

    for word in aligned_words:
        word_start = word.get("startS", 0)
        word_end = word.get("endS", 0)

        # Include words that overlap with our window
        if word_start < end and word_end > start:
            text = word.get("word", "").strip()
            # Remove section markers like [Verse 1]
            if not text.startswith("["):
                # Clean up newlines from section markers
                text = text.replace("\n", " ").strip()
                if text:
                    lyrics.append(text)

    return " ".join(lyrics)
