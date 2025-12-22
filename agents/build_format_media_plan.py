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

FormatType = Literal["full", "hook", "educational"]


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


def build_format_plan(format_type: FormatType, target_duration: float,
                      available_clips: List[Dict], output_file: str) -> bool:
    """
    Build a media plan for a specific format by assigning clips from the pool.
    Preserves all semantic metadata for 5_assemble_video.py's matcher.

    Strategy:
    - Maximize visual variety by using many short clips instead of few long clips
    - For 'full': Target 15-30 shots at 3-8s each
    - For 'hook'/'educational': Target 12-20 shots at 1.5-3s each (~2s ideal for engagement)
    - Distribute duration evenly for better pacing
    """
    print(f"  Building {format_type} media plan ({target_duration}s + {CLIP_COVERAGE_BUFFER_SECONDS}s buffer)...")

    if not available_clips:
        print(f"    ❌ No available clips to assign")
        return False

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

    # Build shot list for this format
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
    
    # Create the media plan
    media_plan = {
        "format": format_type,
        "target_duration": target_duration,
        "total_duration": current_duration,
        "total_shots": len(shot_list),
        "pacing": "varied",
        "transition_style": "smooth",
        "shot_list": shot_list
    }
    
    # Save the plan
    output_path = get_output_path(output_file)
    with open(output_path, 'w') as f:
        json.dump(media_plan, f, indent=2)
    
    print(f"    ✅ Created {output_file} with {len(shot_list)} shots ({current_duration:.1f}s)")
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
    
    # Load all available media clips with semantic metadata
    print("\n📦 Loading available media clips...")
    available_clips = load_available_media()
    
    if not available_clips:
        print("❌ Error: No downloaded media clips found")
        print("Media must be downloaded before building format-specific plans")
        sys.exit(1)
    
    total_duration = sum(c["actual_duration"] for c in available_clips)
    print(f"  Found {len(available_clips)} clips totaling {total_duration:.1f}s")
    
    # Show clips with their descriptions for verification
    for clip in available_clips[:5]:  # Show first 5
        desc = clip.get('description', 'No description')[:40]
        print(f"    - shot_{clip['shot_number']:02d}: {clip['actual_duration']:.1f}s | {desc}...")
    if len(available_clips) > 5:
        print(f"    ... and {len(available_clips) - 5} more")
    print()
    
    # Build media plan for each format
    formats: list[FormatType] = ["full", "hook", "educational"]
    success_count = 0
    
    for format_type in formats:
        config = get_format_config(format_type, segments)
        success = build_format_plan(
            format_type,
            config["duration"],
            available_clips,
            config["output_file"]
        )
        if success:
            success_count += 1
    
    # Summary
    print(f"\n✅ Built {success_count}/{len(formats)} format-specific media plans")
    print(f"   All plans preserve description, media_url for semantic matching")
    
    if success_count < len(formats):
        print("⚠️  Some media plans failed - videos may have incorrect durations")
        sys.exit(1)


if __name__ == "__main__":
    main()
