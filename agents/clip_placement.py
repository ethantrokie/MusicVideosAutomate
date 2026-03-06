#!/usr/bin/env python3
"""Clip placement logic for AI video generation."""

from typing import Dict, List


def find_phrase_boundaries(aligned_words: List[Dict]) -> List[Dict]:
    """
    Find phrase/sentence boundaries based on punctuation and pauses.
    
    Returns list of phrases with start_time, end_time, text.
    """
    phrases = []
    current_phrase = {"words": [], "start": None, "end": None}
    
    for i, word in enumerate(aligned_words):
        text = word.get("word", "")
        start = word.get("startS", 0)
        end = word.get("endS", 0)
        
        # Skip section markers
        if text.startswith("["):
            continue
            
        # Start new phrase if needed
        if current_phrase["start"] is None:
            current_phrase["start"] = start
        
        current_phrase["words"].append(text.strip())
        current_phrase["end"] = end
        
        # Check for phrase end: punctuation or long pause
        is_phrase_end = False
        clean_text = text.strip()
        
        # Punctuation endings
        if any(clean_text.endswith(p) for p in [".", "!", "?", ",", "\n"]):
            is_phrase_end = True
        
        # Check for pause before next word
        if i + 1 < len(aligned_words):
            next_word = aligned_words[i + 1]
            next_start = next_word.get("startS", 0)
            gap = next_start - end
            if gap > 0.3:  # 300ms pause = phrase boundary
                is_phrase_end = True
        
        if is_phrase_end and current_phrase["words"]:
            phrases.append({
                "start_time": current_phrase["start"],
                "end_time": current_phrase["end"],
                "text": " ".join(current_phrase["words"]).strip()
            })
            current_phrase = {"words": [], "start": None, "end": None}
    
    # Don't forget last phrase
    if current_phrase["words"]:
        phrases.append({
            "start_time": current_phrase["start"],
            "end_time": current_phrase["end"],
            "text": " ".join(current_phrase["words"]).strip()
        })
    
    return phrases


def find_nearest_phrase_start(phrases: List[Dict], target_time: float, min_time: float = 0) -> float:
    """
    Find the start of the phrase nearest to target_time that starts after min_time.
    """
    best_phrase = None
    best_distance = float('inf')
    
    for phrase in phrases:
        phrase_start = phrase["start_time"]
        if phrase_start < min_time:
            continue
        
        distance = abs(phrase_start - target_time)
        if distance < best_distance:
            best_distance = distance
            best_phrase = phrase
    
    return best_phrase["start_time"] if best_phrase else target_time


def determine_clip_placements(aligned_words: List[Dict], clip_duration: int = 5) -> List[Dict]:
    """
    Determine 3 clip placements within first 60 seconds based on song structure.
    Clips are aligned to phrase boundaries for proper lip-sync.

    Args:
        aligned_words: List of aligned word dicts with startS, endS, word
        clip_duration: Duration of each clip in seconds

    Returns:
        List of 3 clip definitions with id, start_time, end_time, segment_type
    """
    clips = []
    
    # Find phrase boundaries
    phrases = find_phrase_boundaries(aligned_words)
    print(f"    Found {len(phrases)} phrases in song")

    # Find verse and chorus markers
    verse_start = None
    chorus_start = None
    first_word_start = 0.5

    for word in aligned_words:
        text = word.get("word", "")
        start = word.get("startS", 0)

        if first_word_start == 0.5 and start > 0 and not text.startswith("["):
            first_word_start = start

        if "[Verse" in text and verse_start is None:
            verse_start = start
        if "[Chorus]" in text and chorus_start is None:
            chorus_start = start

    # Clip 1: Intro - always starts at 0s so the AI artist is the first thing viewers see
    intro_start = 0.0
    clips.append({
        "id": 1,
        "start_time": intro_start,
        "end_time": round(intro_start + clip_duration, 3),
        "segment_type": "intro"
    })
    print(f"    Clip 1 (intro): starts at {intro_start:.2f}s (always first)")

    # Clip 2: Verse - find phrase near 15-20s mark
    target_verse = verse_start if verse_start and 10 < verse_start < 44 else 15
    min_verse = clips[0]["end_time"] + 1  # At least 1s gap
    verse_placement = round(find_nearest_phrase_start(phrases, target_verse, min_time=min_verse), 3)

    # Make sure it fits
    if verse_placement + clip_duration > 42:
        verse_placement = round(find_nearest_phrase_start(phrases, 34, min_time=min_verse), 3)

    clips.append({
        "id": 2,
        "start_time": verse_placement,
        "end_time": round(verse_placement + clip_duration, 3),
        "segment_type": "verse"
    })
    print(f"    Clip 2 (verse): starts at phrase boundary {verse_placement:.2f}s")

    # Clip 3: Chorus - find phrase near chorus marker or 32-38s
    target_chorus = chorus_start if chorus_start and 25 < chorus_start < 52 else 32
    min_chorus = clips[1]["end_time"] + 1
    chorus_placement = round(find_nearest_phrase_start(phrases, target_chorus, min_time=min_chorus), 3)

    # Make sure it fits within 60s
    if chorus_placement + clip_duration > 60:
        chorus_placement = round(find_nearest_phrase_start(phrases, 50, min_time=min_chorus), 3)

    clips.append({
        "id": 3,
        "start_time": chorus_placement,
        "end_time": round(chorus_placement + clip_duration, 3),
        "segment_type": "chorus"
    })
    print(f"    Clip 3 (chorus): starts at phrase boundary {chorus_placement:.2f}s")

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
                text = text.replace("\n", " ").strip()
                if text:
                    lyrics.append(text)

    return " ".join(lyrics)
