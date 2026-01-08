#!/usr/bin/env python3
"""
Build format-specific media plans for multi-format video generation.
Assigns already-downloaded media clips to each format based on duration requirements,
while preserving semantic metadata for lyrics matching.

Architecture (Option B): 
- Download all media ONCE in Stage 5
- This script assigns clips from that pool to each format's plan
- Preserves description, media_url, lyrics_match for 5_assemble_video.py's semantic matcher
- No re-running curator, no duplicate downloads, consistent media across formats
"""

import os
import sys
import json
import subprocess
from pathlib import Path
from typing import Dict, List, Literal

# Minimum buffer to ensure clips cover full audio duration even if some downloads fail
CLIP_COVERAGE_BUFFER_SECONDS = 15

FormatType = Literal["full", "hook", "educational", "intro"]


def get_output_path(filename: str) -> Path:
    """Get path in OUTPUT_DIR."""
    output_dir = os.getenv("OUTPUT_DIR", "outputs")
    return Path(output_dir) / filename


def get_media_duration(file_path: str) -> float:
    """Get duration of media file in seconds using ffprobe."""
    try:
        result = subprocess.run([
            'ffprobe', '-v', 'error',
            '-show_entries', 'format=duration',
            '-of', 'default=noprint_wrappers=1:nokey=1',
            file_path
        ], capture_output=True, text=True, timeout=10)

        if result.returncode == 0:
            return float(result.stdout.strip())
    except Exception:
        pass
    return 0.0


def load_phrase_groups() -> List[Dict]:
    """
    Load phrase groups with lyric timestamps.
    Returns empty list if file doesn't exist (graceful degradation).
    """
    phrase_groups_path = get_output_path("phrase_groups.json")

    if not phrase_groups_path.exists():
        print("  ⚠️  phrase_groups.json not found, will use sequential timing")
        return []

    try:
        with open(phrase_groups_path) as f:
            phrase_groups = json.load(f)

        print(f"  ✓ Loaded {len(phrase_groups)} phrase groups with lyric timestamps")
        return phrase_groups
    except Exception as e:
        print(f"  ⚠️  Error loading phrase_groups.json: {e}, using sequential timing")
        return []


def get_phrase_time(phrase_group: Dict, key: str) -> float:
    """
    Get time value from phrase group, handling both old and new key formats.

    Args:
        phrase_group: Phrase group dictionary
        key: Either 'start' or 'end'

    Returns:
        Time value in seconds
    """
    if key == 'start':
        # Try new format first (startS), then old format (start_time)
        return phrase_group.get('startS', phrase_group.get('start_time', 0))
    elif key == 'end':
        # Try new format first (endS), then old format (end_time)
        return phrase_group.get('endS', phrase_group.get('end_time', 0))
    return 0


def match_clips_to_phrase_groups(
    phrase_groups: List[Dict],
    available_clips: List[Dict]
) -> List[Dict]:
    """
    Match each phrase group to the best available clip using semantic similarity.

    Args:
        phrase_groups: List of phrase groups with start_time, end_time, key_terms
        available_clips: List of clips with description, lyrics_match metadata

    Returns:
        List of phrase groups with matched clip data added
    """
    from difflib import SequenceMatcher

    matched_groups = []
    used_clip_indices = set()

    for idx, group in enumerate(phrase_groups):
        # Build search text from phrase group text field
        # phrase_text can be from 'text' (new format) or 'topic' (old format)
        phrase_text = group.get("text", group.get("topic", ""))

        # Extract key terms from text if available, otherwise use key_terms field
        key_terms = " ".join(group.get("key_terms", []))
        search_text = f"{phrase_text} {key_terms}".lower()

        # Find best matching clip
        best_score = 0
        best_clip_idx = None

        for clip_idx, clip in enumerate(available_clips):
            # Prefer unused clips, but allow reuse if needed
            reuse_penalty = 0.3 if clip_idx in used_clip_indices else 0

            # Score based on description and lyrics_match
            clip_text = f"{clip.get('description', '')} {clip.get('lyrics_match', '')}".lower()

            # Simple word overlap score
            search_words = set(search_text.split())
            clip_words = set(clip_text.split())
            overlap = len(search_words & clip_words)
            total = len(search_words | clip_words)
            score = (overlap / total if total > 0 else 0) - reuse_penalty

            if score > best_score:
                best_score = score
                best_clip_idx = clip_idx

        # Add matched clip data to group
        if best_clip_idx is not None:
            matched_group = group.copy()
            matched_group["matched_clip"] = available_clips[best_clip_idx]
            matched_group["match_score"] = best_score
            matched_group["group_id"] = idx  # Add group_id for tracking
            matched_groups.append(matched_group)
            used_clip_indices.add(best_clip_idx)
        else:
            # Still add the group even if no clip matched, for tracking
            matched_group = group.copy()
            matched_group["group_id"] = idx
            print(f"  ⚠️  No clip match for phrase group {idx} ({phrase_text[:40]}...)")

    return matched_groups


def build_synchronized_shot_list(
    matched_groups: List[Dict],
    segment_start: float,
    segment_end: float
) -> List[Dict]:
    """
    Build shot list with lyric-synchronized timing.
    Filters phrase groups to segment time range and creates shots with actual timestamps.

    Args:
        matched_groups: Phrase groups with matched clips
        segment_start: Segment start time in seconds (e.g., 30 for hook)
        segment_end: Segment end time in seconds (e.g., 45 for hook)

    Returns:
        List of shots with synchronized start_time, end_time from lyrics
    """
    shots = []
    shot_number = 1

    # Filter groups to this segment's time range
    segment_groups = [
        g for g in matched_groups
        if get_phrase_time(g, 'start') < segment_end and get_phrase_time(g, 'end') > segment_start
    ]

    print(f"    📍 Found {len(segment_groups)} phrase groups in segment range {segment_start}-{segment_end}s")

    for group in segment_groups:
        clip = group.get("matched_clip")
        if not clip:
            continue

        # Use ACTUAL lyric timestamps from phrase group
        lyric_start = max(get_phrase_time(group, 'start'), segment_start)
        lyric_end = min(get_phrase_time(group, 'end'), segment_end)
        duration = lyric_end - lyric_start

        # Adjust timing to segment-relative (0-based for this segment)
        relative_start = lyric_start - segment_start
        relative_end = lyric_end - segment_start

        shot = {
            "shot_number": shot_number,
            "local_path": clip["local_path"],
            "media_type": clip.get("media_type", "video"),
            "media_url": clip.get("media_url", ""),
            "description": clip.get("description", ""),
            "lyrics_match": group.get("text", group.get("topic", "")),  # Support both new (text) and old (topic) formats
            "source": clip.get("source", ""),
            "transition": clip.get("transition", "crossfade"),
            "priority": clip.get("priority", "normal"),
            # SYNCHRONIZED TIMING - from actual lyrics
            "start_time": relative_start,
            "end_time": relative_end,
            "duration": duration,
            # Preserve phrase group for debugging
            "phrase_group_id": group.get("group_id"),
            "absolute_start": lyric_start,  # For debugging
            "absolute_end": lyric_end,
            "match_score": group.get("match_score", 0)
        }

        shots.append(shot)
        shot_number += 1

    # GAP FILLING: Detect and fill gaps in lyric coverage
    # If there are shots but the first one doesn't start at 0 (relative to segment),
    # there's an instrumental intro that needs visual content
    if shots and shots[0]["start_time"] > 0.5:  # 0.5s threshold to avoid tiny gaps
        gap_duration = shots[0]["start_time"]
        print(f"    🔧 Detected {gap_duration:.1f}s gap before first lyrics (instrumental intro)")

        # Find the first shot's clip to reuse (visual continuity)
        first_clip = None
        for group in segment_groups:
            clip = group.get("matched_clip")
            if clip:
                first_clip = clip
                break

        if first_clip:
            # Create filler shot for the instrumental intro
            filler_shot = {
                "shot_number": 0,  # Will renumber all shots after
                "local_path": first_clip["local_path"],
                "media_type": first_clip.get("media_type", "video"),
                "media_url": first_clip.get("media_url", ""),
                "description": first_clip.get("description", "") + " (instrumental intro)",
                "lyrics_match": "[Instrumental]",
                "source": first_clip.get("source", ""),
                "transition": "fade",
                "priority": "normal",
                "start_time": 0.0,
                "end_time": gap_duration,
                "duration": gap_duration,
                "phrase_group_id": None,
                "absolute_start": segment_start,
                "absolute_end": segment_start + gap_duration,
                "match_score": 0.0
            }

            # Insert at beginning and renumber all shots
            shots.insert(0, filler_shot)
            for i, shot in enumerate(shots):
                shot["shot_number"] = i + 1

            print(f"    ✅ Added filler shot for instrumental intro (0-{gap_duration:.1f}s)")

    return shots


def get_format_config(format_type: FormatType, segments: Dict) -> Dict:
    """Get duration and configuration for each format."""
    configs = {
        "full": {
            "duration": segments["full"]["duration"],
            "output_file": "media_plan_full.json",
            "description": "Full horizontal video"
        },
        "hook": {
            "duration": segments["hook"]["duration"],
            "output_file": "media_plan_hook.json",
            "description": "Hook short vertical video"
        },
        "educational": {
            "duration": segments["educational"]["duration"],
            "output_file": "media_plan_educational.json",
            "description": "Educational short vertical video"
        },
        "intro": {
            "duration": segments["intro"]["duration"],
            "output_file": "media_plan_intro.json",
            "description": "Intro short vertical video"
        }
    }
    return configs[format_type]


def load_available_media() -> List[Dict]:
    """
    Load all available downloaded media from approved_media.json and media_manifest.json.
    Preserves all semantic metadata (description, media_url, lyrics_match) for matching.
    Returns a list of clips with local_path, duration, and all metadata.
    """
    output_dir = os.getenv("OUTPUT_DIR", "outputs")
    
    approved_path = get_output_path("approved_media.json")
    manifest_path = get_output_path("media_manifest.json")
    
    available_clips = []
    
    # Build lookup from manifest (has local_path for downloaded files)
    downloaded_files = {}
    if manifest_path.exists():
        with open(manifest_path) as f:
            manifest = json.load(f)
            for item in manifest.get("downloaded", []):
                downloaded_files[item["shot_number"]] = item["local_path"]
    
    # Load approved media and preserve all semantic metadata
    if approved_path.exists():
        with open(approved_path) as f:
            approved = json.load(f)
            
        for shot in approved.get("shot_list", []):
            shot_num = shot.get("shot_number")
            
            # Try to get local_path from shot itself first, then from manifest
            local_path = shot.get("local_path")
            if not local_path and shot_num in downloaded_files:
                local_path = downloaded_files[shot_num]
            
            if local_path and Path(local_path).exists():
                # Get actual duration - try ffprobe first, fall back to metadata duration
                actual_duration = get_media_duration(local_path)
                if actual_duration == 0:
                    # ffprobe failed (not installed or error) - use duration from metadata
                    actual_duration = shot.get("duration", 0)

                if actual_duration > 0:
                    # Preserve ALL metadata for semantic matching
                    clip = {
                        "shot_number": shot_num,
                        "local_path": local_path,
                        "actual_duration": actual_duration,
                        # Semantic matching fields
                        "media_url": shot.get("media_url", ""),
                        "media_type": shot.get("media_type", "video"),
                        "description": shot.get("description", ""),
                        "lyrics_match": shot.get("lyrics_match", ""),
                        # Additional metadata
                        "source": shot.get("source", ""),
                        "transition": shot.get("transition", "crossfade"),
                        "priority": shot.get("priority", "normal"),
                    }
                    available_clips.append(clip)
    
    # Also check media directory directly for any files not in approved_media
    # (fallback for discovered files)
    media_dir = Path(output_dir) / "media"
    if media_dir.exists():
        existing_paths = {c["local_path"] for c in available_clips}
        # Check for all supported media formats (mp4, gif, jpg, jpeg, png)
        for media_file in media_dir.glob("shot_*.*"):
            if media_file.suffix.lower() not in ['.mp4', '.gif', '.jpg', '.jpeg', '.png']:
                continue
            if str(media_file) not in existing_paths:
                duration = get_media_duration(str(media_file))
                # If ffprobe fails, assume a default duration of 5 seconds for discovered files
                if duration == 0:
                    duration = 5.0

                # Extract shot number from filename
                try:
                    shot_num = int(media_file.stem.replace("shot_", ""))
                except ValueError:
                    shot_num = len(available_clips) + 100  # Fallback

                available_clips.append({
                    "shot_number": shot_num,
                    "local_path": str(media_file),
                    "actual_duration": duration,
                    "media_url": "",
                    "media_type": "video",
                    "description": f"Discovered media file: {media_file.name}",
                    "lyrics_match": "",
                    "source": "discovered",
                    "transition": "crossfade",
                    "priority": "low",
                })
    
    # Sort by shot number for consistency
    available_clips.sort(key=lambda x: x["shot_number"])
    
    return available_clips


def get_lyrics_in_time_range(suno_data: Dict, start_time: float, end_time: float) -> str:
    """
    Extract which lyrics appear in a given time range.
    Returns concatenated lyric text for that segment.
    """
    aligned_words = suno_data.get('alignedWords', [])
    segment_words = []

    for word_data in aligned_words:
        word_start = word_data.get('startS', 0)
        word_end = word_data.get('endS', 0)

        # Include word if it overlaps with the segment
        if word_start < end_time and word_end > start_time:
            segment_words.append(word_data.get('word', ''))

    return ''.join(segment_words).strip()


def score_clip_for_segment(clip: Dict, segment_lyrics: str) -> float:
    """
    Score how well a clip matches the segment's lyrics.
    Returns score 0.0-1.0, higher is better match.
    """
    lyrics_match = clip.get('lyrics_match', '').lower()
    segment_lyrics_lower = segment_lyrics.lower()

    if not lyrics_match or not segment_lyrics:
        return 0.0

    # Calculate word overlap
    match_words = set(lyrics_match.split())
    segment_words = set(segment_lyrics_lower.split())

    # Remove common words for better matching
    stopwords = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'you', 'that', 'this'}
    match_words -= stopwords
    segment_words -= stopwords

    if not segment_words:
        return 0.0

    # Jaccard similarity: intersection / union
    intersection = len(match_words & segment_words)
    union = len(match_words | segment_words)

    if union == 0:
        return 0.0

    return intersection / union


def filter_clips_for_segment(available_clips: List[Dict], segment_lyrics: str,
                             min_score: float = 0.1) -> List[Dict]:
    """
    Filter and sort clips by relevance to segment lyrics.
    Returns clips sorted by match score (best first).
    Falls back to all clips if no matches meet threshold.
    """
    if not segment_lyrics:
        # No segment lyrics - return all clips
        return available_clips

    # Score all clips
    scored_clips = []
    for clip in available_clips:
        score = score_clip_for_segment(clip, segment_lyrics)
        scored_clips.append((score, clip))

    # Sort by score (descending)
    scored_clips.sort(key=lambda x: x[0], reverse=True)

    # Filter by minimum score
    matching_clips = [clip for score, clip in scored_clips if score >= min_score]

    # If we have good matches, use them. Otherwise fall back to all clips
    if matching_clips:
        match_count = len(matching_clips)
        avg_score = sum(score_clip_for_segment(c, segment_lyrics) for c in matching_clips) / match_count
        print(f"    📍 Using {match_count}/{len(available_clips)} clips matching segment lyrics (avg score: {avg_score:.2f})")
        return matching_clips
    else:
        print(f"    ⚠️  No clips matched segment lyrics (threshold={min_score}), using all clips")
        return available_clips


def build_format_plan(format_type: FormatType, target_duration: float,
                      available_clips: List[Dict], output_file: str,
                      segment_lyrics: str = "", segments: Dict = None,
                      phrase_groups: List[Dict] = None) -> bool:
    """
    Build a media plan for a specific format by assigning clips from the pool.
    Preserves all semantic metadata for 5_assemble_video.py's matcher.

    Strategy:
    - Filter clips to match segment's lyrics (for hook/educational shorts)
    - Maximize visual variety by using many short clips instead of few long clips
    - For 'full': Target 15-30 shots at 3-8s each
    - For 'hook'/'educational': Target 12-20 shots at 1.5-3s each (~2s ideal for engagement)
    - Distribute duration evenly for better pacing
    """
    print(f"  Building {format_type} media plan ({target_duration}s + {CLIP_COVERAGE_BUFFER_SECONDS}s buffer)...")

    if not available_clips:
        print(f"    ❌ No available clips to assign")
        return False

    # Load phrase groups for lyric synchronization
    use_lyric_sync = phrase_groups is not None and len(phrase_groups) > 0

    if use_lyric_sync:
        print(f"  ✓ Lyric synchronization ENABLED - using phrase group timestamps")
        # Match clips to phrase groups semantically
        matched_groups = match_clips_to_phrase_groups(phrase_groups, available_clips)
        print(f"    Matched {len(matched_groups)} phrase groups to clips")
    else:
        print(f"  ⚠️  Lyric synchronization DISABLED - using sequential timing fallback")
        matched_groups = []

    # Filter clips to match segment lyrics (for shorts)
    if segment_lyrics:
        print(f"    🎯 Filtering clips for segment lyrics ({len(segment_lyrics.split())} words)...")
        available_clips = filter_clips_for_segment(available_clips, segment_lyrics)

    # Calculate total available duration
    total_available = sum(c["actual_duration"] for c in available_clips)
    required_duration = target_duration + CLIP_COVERAGE_BUFFER_SECONDS

    print(f"    Available: {total_available:.1f}s from {len(available_clips)} clips")
    print(f"    Required: {required_duration:.1f}s")

    # Check if we have sufficient clips (curator should download 1.2x target)
    recommended_duration = target_duration * 1.2
    if total_available < target_duration:
        print(f"    ❌ CRITICAL: Insufficient clips! Have {total_available:.1f}s, need {target_duration:.1f}s")
        print(f"       Video will be too short. Check curator or download failures.")
        # Continue anyway - video assembly will loop clips to fill
    elif total_available < required_duration:
        shortage = required_duration - total_available
        print(f"    ⚠️  Warning: Short by {shortage:.1f}s (have {total_available:.1f}s, need {required_duration:.1f}s)")
        print(f"       Clips will be reused extensively. Consider downloading more media.")
    elif total_available < recommended_duration:
        print(f"    ⚠️  Note: Curator should download 1.2x target ({recommended_duration:.1f}s), have {total_available:.1f}s")
        print(f"       Should work but clips will be reused more than ideal.")

    # Define ideal shot duration ranges for visual variety
    if format_type == "full":
        # Full video: longer shots for comprehensive coverage
        IDEAL_SHOT_DURATION = 5.0
        MIN_SHOT_DURATION = 3.0
        MAX_SHOT_DURATION = 8.0
        TARGET_MIN_SHOTS = 15
    else:
        # Shorts: rapid pacing with very quick cuts (~2s each for maximum engagement)
        IDEAL_SHOT_DURATION = 2.0
        MIN_SHOT_DURATION = 1.5
        MAX_SHOT_DURATION = 3.0
        TARGET_MIN_SHOTS = 12

    # Calculate how many shots to use (maximize variety while respecting constraints)
    ideal_num_shots = int(required_duration / IDEAL_SHOT_DURATION)
    num_clips = len(available_clips)

    # Strategy: prefer ideal shot duration, allow reuse if needed for better pacing
    if total_available >= required_duration:
        # We have enough total duration
        if num_clips >= ideal_num_shots:
            # Enough clips to achieve ideal pacing without reuse
            num_shots = ideal_num_shots
            max_clip_reuse = 1
            print(f"    📊 Optimal pacing: using {num_shots} clips at ~{IDEAL_SHOT_DURATION:.1f}s each (no reuse)")
        else:
            # Need to reuse some clips to achieve ideal pacing
            num_shots = ideal_num_shots
            max_clip_reuse = min(3, int(ideal_num_shots / num_clips) + 1)
            print(f"    📊 Fast pacing: using {num_clips} clips with up to {max_clip_reuse}x reuse for ~{IDEAL_SHOT_DURATION:.1f}s shots")
    else:
        # Insufficient total duration - need to reuse clips to fill required time
        if total_available < target_duration:
            # Critical shortage: allow aggressive reuse
            max_clip_reuse = 5
            print(f"    📊 Insufficient clips: allowing up to {max_clip_reuse}x reuse per clip")
        else:
            # Moderate shortage: allow moderate reuse
            max_clip_reuse = 3
            print(f"    📊 Below buffer target: allowing up to {max_clip_reuse}x reuse per clip")

        # Calculate shots needed with reuse
        num_shots = max(TARGET_MIN_SHOTS, min(ideal_num_shots, num_clips * max_clip_reuse))

    # Calculate base duration per shot (will be varied slightly for natural pacing)
    base_duration_per_shot = required_duration / num_shots

    # Ensure base duration is within acceptable range
    base_duration_per_shot = max(MIN_SHOT_DURATION, min(base_duration_per_shot, MAX_SHOT_DURATION))

    print(f"    Strategy: {num_shots} shots at ~{base_duration_per_shot:.1f}s each for visual variety")

    # Build shot list with synchronized or sequential timing
    if use_lyric_sync and segments is not None:
        # Get segment boundaries from segments.json
        segment_info = segments.get(format_type, {})
        segment_start = segment_info.get("start", 0)
        segment_end = segment_info.get("end", target_duration)

        # Build synchronized shots
        shot_list = build_synchronized_shot_list(
            matched_groups,
            segment_start,
            segment_end
        )

        # Calculate total duration from shots
        total_duration = max((s["end_time"] for s in shot_list), default=0) if shot_list else 0

        print(f"    ✓ Created {len(shot_list)} synchronized shots (duration: {total_duration:.1f}s)")

    else:
        # FALLBACK: Sequential timing (original logic)
        shot_list = []
        current_duration = 0.0
        clip_index = 0
        shot_number = 1

        while current_duration < required_duration and shot_number <= num_shots:
            # Cycle through clips if we run out
            clip = available_clips[clip_index % num_clips]

            # Calculate duration for this shot
            remaining_needed = required_duration - current_duration

            if shot_number == num_shots:
                # Last shot: use exactly what's needed (plus small buffer)
                clip_duration = min(clip["actual_duration"], remaining_needed + 1.0)
            else:
                # Regular shot: use base duration with slight variation for natural pacing
                # Vary by ±20% for natural feel
                import random
                variation_factor = random.uniform(0.8, 1.2)
                desired_duration = base_duration_per_shot * variation_factor

                # Clamp to acceptable range and clip's actual duration
                clip_duration = min(
                    clip["actual_duration"],
                    max(MIN_SHOT_DURATION, min(desired_duration, MAX_SHOT_DURATION))
                )

            # Create shot with ALL semantic metadata preserved
            shot = {
                "shot_number": shot_number,
                "local_path": clip["local_path"],
                "media_url": clip.get("media_url", ""),
                "media_type": clip.get("media_type", "video"),
                "description": clip.get("description", ""),
                "lyrics_match": clip.get("lyrics_match", ""),
                "source": clip.get("source", ""),
                "duration": clip_duration,
                "start_time": current_duration,
                "end_time": current_duration + clip_duration,
                "transition": clip.get("transition", "crossfade"),
                "priority": clip.get("priority", "normal"),
                "original_shot": clip["shot_number"],
            }
            shot_list.append(shot)

            current_duration += clip_duration
            shot_number += 1
            clip_index += 1

            # Safety limit to prevent infinite loops
            if shot_number > 100:
                print(f"    ⚠️  Hit safety limit of 100 shots")
                break

        total_duration = current_duration
        print(f"    ✓ Created {len(shot_list)} sequential shots (duration: {total_duration:.1f}s)")
    
    # Create the media plan
    media_plan = {
        "format": format_type,
        "target_duration": target_duration,
        "total_duration": total_duration,
        "total_shots": len(shot_list),
        "pacing": "varied",
        "transition_style": "smooth",
        "shot_list": shot_list
    }

    # Save the plan
    output_path = get_output_path(output_file)
    with open(output_path, 'w') as f:
        json.dump(media_plan, f, indent=2)

    print(f"    ✅ Created {output_file} with {len(shot_list)} shots ({total_duration:.1f}s)")
    return True


def main():
    """Build format-specific media plans by assigning from available clips."""
    print("🎨 Building format-specific media plans...")

    # Load segments to get durations
    segments_path = get_output_path("segments.json")
    if not segments_path.exists():
        print(f"❌ Error: {segments_path} not found")
        print("Segment analysis must run before media planning")
        sys.exit(1)

    with open(segments_path) as f:
        segments = json.load(f)

    # Load suno lyrics data for segment-based filtering
    suno_path = get_output_path("suno_output.json")
    suno_data = {}
    if suno_path.exists():
        with open(suno_path) as f:
            suno_data = json.load(f)
        print(f"  ✅ Loaded lyric timestamps from {suno_path.name}")
    else:
        print(f"  ⚠️  No suno_output.json found - will use all clips for each format")

    # Load all available media clips with semantic metadata
    print("\n📦 Loading available media clips...")
    available_clips = load_available_media()

    if not available_clips:
        print("❌ Error: No downloaded media clips found")
        print("Media must be downloaded before building format-specific plans")
        sys.exit(1)

    total_duration = sum(c["actual_duration"] for c in available_clips)
    print(f"  Found {len(available_clips)} clips totaling {total_duration:.1f}s")

    # Load phrase groups for lyric synchronization
    phrase_groups = load_phrase_groups()
    use_lyric_sync = len(phrase_groups) > 0

    if use_lyric_sync:
        print(f"  ✓ Lyric synchronization ENABLED - using phrase group timestamps")
    else:
        print(f"  ⚠️  Lyric synchronization DISABLED - using sequential timing fallback")

    # Show clips with their descriptions for verification
    for clip in available_clips[:5]:  # Show first 5
        desc = clip.get('description', 'No description')[:40]
        lyrics = clip.get('lyrics_match', 'No lyrics')[:40]
        print(f"    - shot_{clip['shot_number']:02d}: {clip['actual_duration']:.1f}s | {desc}... | {lyrics}...")
    if len(available_clips) > 5:
        print(f"    ... and {len(available_clips) - 5} more")
    print()

    # Build media plan for each format
    formats: list[FormatType] = ["full", "hook", "educational", "intro"]
    success_count = 0

    for format_type in formats:
        config = get_format_config(format_type, segments)

        # Extract segment lyrics for filtering (except full video uses all clips)
        segment_lyrics = ""
        if format_type != "full" and suno_data:
            segment_info = segments.get(format_type, {})
            start_time = segment_info.get("start", 0)
            end_time = segment_info.get("end", 0)
            segment_lyrics = get_lyrics_in_time_range(suno_data, start_time, end_time)
            print(f"\n  🎵 {format_type.upper()} segment ({start_time}s-{end_time}s):")
            print(f"     First 100 chars: {segment_lyrics[:100]}...")

        success = build_format_plan(
            format_type,
            config["duration"],
            available_clips.copy(),  # Pass a copy so filtering doesn't affect other formats
            config["output_file"],
            segment_lyrics,
            segments,
            phrase_groups if use_lyric_sync else None
        )
        if success:
            success_count += 1

    # Summary
    print(f"\n✅ Built {success_count}/{len(formats)} format-specific media plans")
    print(f"   Full video: uses all clips sequentially")
    print(f"   Hook/Educational/Intro shorts: filtered by segment lyrics")

    if success_count < len(formats):
        print("⚠️  Some media plans failed - videos may have incorrect durations")
        sys.exit(1)


if __name__ == "__main__":
    main()
