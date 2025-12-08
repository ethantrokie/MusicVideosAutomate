#!/usr/bin/env python3
"""
Video assembly agent using MoviePy.
Combines approved media with generated music into final video.
"""

import os
import sys
import json
import argparse
from pathlib import Path

# Add agents directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))
from output_helper import get_output_path, ensure_output_dir

# Monkey patch for Pillow 10+ compatibility with moviepy 1.0.3
try:
    from PIL import Image
    if not hasattr(Image, 'ANTIALIAS'):
        Image.ANTIALIAS = Image.LANCZOS
except ImportError:
    pass

from moviepy.editor import (
    VideoFileClip,
    ImageClip,
    AudioFileClip,
    CompositeVideoClip,
    concatenate_videoclips,
    CompositeAudioClip
)
import moviepy.video.fx.all as vfx
import logging
from typing import List, Dict
from consolidate_clips import consolidate_phrase_groups


def load_config():
    """Load video settings from config."""
    config_path = Path("config/config.json")
    with open(config_path) as f:
        config = json.load(f)
    return config["video_settings"]


def load_sync_config():
    """Load lyric sync configuration."""
    config_path = Path("config/config.json")
    with open(config_path) as f:
        config = json.load(f)
    return config.get("lyric_sync", {
        "enabled": True,
        "min_phrase_duration": 1.5,
        "phrase_gap_threshold": 0.3,
        "keyword_boost_multiplier": 2.0,
        "transition_duration": 0.3
    })


def load_approved_media():
    """Load approved media shot list."""
    media_path = get_output_path("approved_media.json")
    if not media_path.exists():
        print(f"❌ Error: {media_path} not found")
        print("Run approval script first: ./approve_media.sh")
        sys.exit(1)

    with open(media_path) as f:
        data = json.load(f)
        # Normalize field names for semantic matcher compatibility
        # Matcher expects "url" but approved_media has "media_url"
        if "shot_list" in data:
            for shot in data["shot_list"]:
                if "media_url" in shot and "url" not in shot:
                    shot["url"] = shot["media_url"]
        return data


def create_clip_from_shot(shot: dict, video_settings: dict):
    """
    Create MoviePy clip from shot data.

    Args:
        shot: Shot dict with local_path, duration, etc.
        video_settings: Video resolution and settings

    Returns:
        MoviePy clip object
    """
    local_path = shot["local_path"]
    duration = shot["duration"]
    media_type = shot["media_type"]
    transition = shot.get("transition", "fade")

    target_width, target_height = video_settings["resolution"]

    try:
        if media_type == "image":
            # Create image clip
            clip = ImageClip(local_path, duration=duration)
        else:
            # Load video clip
            clip = VideoFileClip(local_path)

            # Trim if clip is longer than needed
            # If clip is shorter, loop it to fill the required duration
            if clip.duration > duration:
                clip = clip.subclip(0, duration)
            elif clip.duration < duration:
                # Loop the clip to fill the required duration
                # This prevents the "frozen frame" issue where MoviePy freezes the last frame
                loops_needed = int(duration / clip.duration) + 1
                print(f"  🔄 Looping shot {shot['shot_number']}: {clip.duration:.2f}s → {duration:.2f}s ({loops_needed}x)")
                clip = concatenate_videoclips([clip] * loops_needed).subclip(0, duration)


        # Resize to fit target resolution (letterbox/pillarbox instead of crop)
        # This preserves all content without cropping

        # Calculate aspect ratios
        clip_aspect = clip.w / clip.h
        target_aspect = target_width / target_height

        if clip_aspect > target_aspect:
            # Video is wider than target (horizontal video for vertical format)
            # Fit to width, add black bars top/bottom (letterbox)
            clip = clip.resize(width=target_width)
        else:
            # Video is taller than target (or already vertical)
            # Fit to height, add black bars left/right (pillarbox)
            clip = clip.resize(height=target_height)

        # No transitions - hard cuts only
        # (Transitions removed per user preference)

        # Center the clip on a black background of target size using margin
        if clip.w != target_width or clip.h != target_height:
            # Use margin to center clip - simpler than custom make_frame
            clip = clip.on_color(
                size=(target_width, target_height),
                color=(0, 0, 0),
                pos='center'
            )

        return clip

    except Exception as e:
        print(f"  ⚠️  Error loading shot {shot['shot_number']}: {e}")
        import traceback
        traceback.print_exc()
        # Return black placeholder clip
        import numpy as np
        black_frame = np.zeros((target_height, target_width, 3), dtype='uint8')
        return ImageClip(black_frame).set_duration(duration)


def fetch_and_process_lyrics(music_metadata: dict, research_data: dict, sync_config: dict):
    """
    Fetch timestamps and create phrase groups.

    Args:
        music_metadata: Music metadata with task_id and audio_id
        research_data: Research data with key_facts
        sync_config: Sync configuration

    Returns:
        Tuple of (aligned_lyrics, phrase_groups) or (None, None) on failure
    """
    from suno_lyrics_sync import SunoLyricsSync
    from phrase_grouper import PhraseGrouper
    import subprocess

    logger = logging.getLogger(__name__)

    # Fetch timestamps
    try:
        sync = SunoLyricsSync()
        task_id = music_metadata.get("task_id")
        audio_id = music_metadata.get("audio_id")

        if not task_id or not audio_id:
            logger.warning("Missing task_id or audio_id, cannot fetch timestamps")
            return None, None

        logger.info(f"Fetching aligned lyrics for audio {audio_id}...")
        aligned_data = sync.fetch_aligned_lyrics(task_id, audio_id)

        # Detect actual audio duration using ffprobe
        audio_path = get_output_path("song.mp3")
        if audio_path.exists():
            try:
                ffprobe_cmd = [
                    'ffprobe', '-v', 'error',
                    '-show_entries', 'format=duration',
                    '-of', 'default=noprint_wrappers=1:nokey=1',
                    str(audio_path)
                ]
                result = subprocess.run(ffprobe_cmd, capture_output=True, text=True, timeout=10)
                if result.returncode == 0:
                    actual_duration = float(result.stdout.strip())
                    logger.info(f"Detected actual audio duration: {actual_duration:.2f}s")

                    # Filter timestamps to actual audio duration
                    aligned_words = aligned_data.get("alignedWords", [])
                    original_count = len(aligned_words)

                    # Filter words that start beyond audio duration
                    filtered_words = [w for w in aligned_words if w["startS"] < actual_duration]

                    # Clamp end times to audio duration
                    for w in filtered_words:
                        if w["endS"] > actual_duration:
                            w["endS"] = actual_duration

                    filtered_count = original_count - len(filtered_words)
                    if filtered_count > 0:
                        logger.warning(f"⚠️  Filtered {filtered_count} words with timestamps beyond audio duration ({actual_duration:.2f}s)")
                        logger.warning(f"   Original word count: {original_count}, Filtered: {len(filtered_words)}")

                    aligned_data["alignedWords"] = filtered_words
                else:
                    logger.warning("Could not detect audio duration with ffprobe, using all timestamps")
            except Exception as e:
                logger.warning(f"Could not detect audio duration: {e}, using all timestamps")
        else:
            logger.warning(f"Audio file not found at {audio_path}, cannot filter timestamps")

        # Save aligned lyrics (with filtered timestamps if applied)
        aligned_path = get_output_path("lyrics_aligned.json")
        with open(aligned_path, 'w') as f:
            json.dump(aligned_data, f, indent=2)
        logger.info(f"Saved aligned lyrics to {aligned_path}")

    except Exception as e:
        logger.error(f"Failed to fetch aligned lyrics: {e}")
        return None, None

    # Parse and group phrases
    try:
        grouper = PhraseGrouper()

        # Parse into phrases
        aligned_words = aligned_data.get("alignedWords", [])
        phrases = grouper.parse_into_phrases(
            aligned_words,
            gap_threshold=sync_config["phrase_gap_threshold"]
        )

        # Extract key terms
        lyrics_text = " ".join([w["word"] for w in aligned_words])
        key_facts = research_data.get("key_facts", [])
        key_terms = grouper.extract_key_terms(lyrics_text, key_facts)

        # Group by topic
        phrase_groups = grouper.group_phrases_by_topic(phrases, key_terms)

        # Save phrase groups
        groups_path = get_output_path("phrase_groups.json")
        with open(groups_path, 'w') as f:
            json.dump(phrase_groups, f, indent=2)
        logger.info(f"Saved {len(phrase_groups)} phrase groups to {groups_path}")

        return aligned_data, phrase_groups

    except Exception as e:
        logger.error(f"Failed to process phrases: {e}")
        return None, None


def create_synchronized_plan(phrase_groups: List[Dict], approved_media: List[Dict], sync_config: dict, target_audio_duration: float = None) -> Dict:
    """
    Create synchronized media plan using semantic matching with clip consolidation.

    Args:
        phrase_groups: Phrase groups from AI
        approved_media: Available media from curator
        sync_config: Sync configuration including clip consolidation settings
        target_audio_duration: Target audio duration in seconds (optional, extends last shot if needed)

    Returns:
        Synchronized plan dict
    """
    from semantic_matcher import SemanticMatcher

    logger = logging.getLogger(__name__)

    # Check if consolidation is enabled
    consolidation_config = sync_config.get("clip_consolidation", {})
    if consolidation_config.get("enabled", False):
        logger.info(f"Consolidating {len(phrase_groups)} phrase groups into longer clips...")

        # Consolidate phrase groups into longer segments
        consolidated_clips = consolidate_phrase_groups(phrase_groups, consolidation_config)

        logger.info(f"Created {len(consolidated_clips)} consolidated clips (avg {sum(c['duration'] for c in consolidated_clips)/len(consolidated_clips):.1f}s each)")

        # Match videos to consolidated clips (not individual phrase groups)
        matcher = SemanticMatcher(keyword_boost=sync_config["keyword_boost_multiplier"])

        shots = []
        for clip in consolidated_clips:
            # Use combined key terms from all phrase groups in this clip
            clip_description = f"{' / '.join(clip['topics'])}"
            clip_key_terms = clip['key_terms']

            # Create a temporary group for matching
            temp_group = {
                "topic": clip_description,
                "key_terms": clip_key_terms,
                "start_time": clip["start_time"],
                "end_time": clip["end_time"],
                "duration": clip["duration"],
                "phrases": []
            }

            # Flatten all phrases from all phrase groups in this clip
            for pg in clip["phrase_groups"]:
                temp_group["phrases"].extend(pg.get("phrases", []))

            # Match video to this consolidated clip
            matched_groups = matcher.match_videos_to_groups([temp_group], approved_media)

            if not matched_groups:
                logger.warning(f"No match for consolidated clip {clip['clip_id']}")
                continue

            matched = matched_groups[0]

            # Find media object
            media = next((m for m in approved_media if m.get("url") == matched.get("video_url")), None)

            if not media or "local_path" not in media:
                logger.warning(f"No local media found for {matched.get('video_url', 'unknown')}, skipping")
                continue

            shot = {
                "shot_number": len(shots) + 1,
                "local_path": media["local_path"],
                "media_type": media.get("media_type", "video"),
                "description": clip_description,
                "start_time": clip["start_time"],
                "end_time": clip["end_time"],
                "duration": clip["duration"],
                "lyrics_match": " / ".join([p["text"] for pg in clip["phrase_groups"] for p in pg.get("phrases", [])]),
                "topic": clip_description,
                "key_terms": clip_key_terms,
                "match_score": matched["match_score"],
                "transition": "crossfade",
                "phrase_groups": clip["phrase_groups"]  # Preserve for subtitle timing
            }
            shots.append(shot)

    else:
        # Original behavior: match videos to individual phrase groups
        logger.info(f"Using original phrase-level matching for {len(phrase_groups)} groups")

        matcher = SemanticMatcher(keyword_boost=sync_config["keyword_boost_multiplier"])
        matched_groups = matcher.match_videos_to_groups(phrase_groups, approved_media)

        shots = []
        for group in matched_groups:
            media = next((m for m in approved_media if m.get("url") == group.get("video_url")), None)

            if not media or "local_path" not in media:
                logger.warning(f"No local media found for {group.get('video_url', 'unknown')}, skipping")
                continue

            shot = {
                "shot_number": len(shots) + 1,
                "local_path": media["local_path"],
                "media_type": media.get("media_type", "video"),
                "description": group["video_description"],
                "start_time": group["start_time"],
                "end_time": group["end_time"],
                "duration": max(group["duration"], sync_config["min_phrase_duration"]),
                "lyrics_match": " / ".join([p["text"] for p in group["phrases"]]),
                "topic": group["topic"],
                "key_terms": group["key_terms"],
                "match_score": group["match_score"],
                "transition": "crossfade",
                "phrase_groups": [group]  # Single phrase group
            }
            shots.append(shot)

    # Set first and last transitions to fade
    if shots:
        shots[0]["transition"] = "fade"
        shots[-1]["transition"] = "fade"

    total_duration = shots[-1]["end_time"] if shots else 0

    # Extend last shot if it doesn't cover the full audio duration
    if target_audio_duration and shots and total_duration < target_audio_duration:
        gap = target_audio_duration - total_duration
        logger.warning(f"⚠️  Phrase groups end at {total_duration:.1f}s, but audio is {target_audio_duration:.1f}s")
        logger.warning(f"   Extending last shot by {gap:.1f}s to cover full audio duration")

        # Extend the last shot to cover the gap
        last_shot = shots[-1]
        last_shot["end_time"] = target_audio_duration
        last_shot["duration"] = last_shot["end_time"] - last_shot["start_time"]

        total_duration = target_audio_duration

    plan = {
        "shot_list": shots,
        "total_duration": total_duration,
        "total_shots": len(shots),
        "transition_style": "smooth",
        "pacing": "consolidated" if consolidation_config.get("enabled", False) else "synchronized",
        "sync_method": "suno_timestamps"
    }

    # Save synchronized plan
    sync_path = get_output_path("synchronized_plan.json")
    with open(sync_path, 'w') as f:
        json.dump(plan, f, indent=2)
    logger.info(f"Saved synchronized plan to {sync_path}")

    return plan


def assemble_video(approved_data: dict, video_settings: dict, audio_path: str, audio_start: float = 0.0, audio_duration: float = None):
    """
    Assemble final video from approved media and audio.

    Args:
        approved_data: Approved media JSON
        video_settings: Video config
        audio_path: Path to music file
        audio_start: Start time in seconds for audio slicing
        audio_duration: Desired audio duration in seconds (if None, uses video duration)

    Returns:
        Path to final video
    """
    print("🎬 Assembling video...")

    shots = approved_data["shot_list"]

    # Filter out shots without local_path (failed downloads)
    available_shots = [s for s in shots if 'local_path' in s]
    skipped_shots = [s for s in shots if 'local_path' not in s]

    if skipped_shots:
        print(f"  ⚠️  Skipping {len(skipped_shots)} shots with failed downloads:")
        for shot in skipped_shots:
            print(f"    - Shot {shot['shot_number']}: {shot['description'][:50]}...")

    if not available_shots:
        print("  ❌ No shots available - all downloads failed!")
        sys.exit(1)

    clips = []

    # Create clips for each shot
    print(f"  Creating {len(available_shots)} video clips...")
    for i, shot in enumerate(available_shots, 1):
        print(f"    [{i}/{len(available_shots)}] Shot {shot['shot_number']}: {shot['description'][:40]}...")
        clip = create_clip_from_shot(shot, video_settings)
        clips.append(clip)

    # Concatenate all clips
    print("  Concatenating clips...")
    if approved_data.get("transition_style") == "smooth":
        # Use crossfadein for smooth transitions
        final_video = concatenate_videoclips(clips, method="compose")
    else:
        final_video = concatenate_videoclips(clips)

    # Load and attach audio
    print(f"  Adding audio track (starting at {audio_start}s)...")
    audio = AudioFileClip(audio_path)

    # Slice audio if start time is provided
    if audio_start > 0:
        audio = audio.subclip(audio_start)

    # Determine target audio duration
    target_duration = audio_duration if audio_duration is not None else final_video.duration

    # Trim audio to target duration
    if audio.duration > target_duration:
        audio = audio.subclip(0, target_duration)
        print(f"  Trimmed audio to {target_duration}s")

    # Trim video to match audio duration (handles clips that run too long)
    if final_video.duration > target_duration:
        final_video = final_video.subclip(0, target_duration)
        print(f"  Trimmed video to {target_duration}s (matches audio)")

    final_video = final_video.set_audio(audio)

    # Export final video
    ensure_output_dir()
    output_path = str(get_output_path("final_video.mp4"))
    print(f"  Rendering final video to {output_path}...")
    print("  (This may take a few minutes...)")

    final_video.write_videofile(
        output_path,
        fps=video_settings["fps"],
        codec="libx264",
        audio_codec="aac",
        preset="medium",
        threads=4
    )

    # Clean up
    final_video.close()
    audio.close()
    for clip in clips:
        clip.close()

    return output_path


def main():
    """Main execution."""
    logging.basicConfig(level=logging.INFO, format='%(message)s')
    logger = logging.getLogger(__name__)

    # Parse command-line arguments
    parser = argparse.ArgumentParser()
    parser.add_argument('--resolution',
                       type=str,
                       default='1080x1920',
                       help='Output resolution WIDTHxHEIGHT (default: 1080x1920 for vertical)')
    parser.add_argument('--no-sync',
                       action='store_true',
                       help='Disable synchronized assembly, use curator plan directly')
    parser.add_argument('--no-consolidation',
                       action='store_true',
                       help='Disable clip consolidation, use phrase-level clips')
    parser.add_argument('--audio-start',
                       type=float,
                       default=0.0,
                       help='Start time in seconds for audio slicing (default: 0.0)')
    parser.add_argument('--audio-duration',
                       type=float,
                       default=None,
                       help='Desired audio duration in seconds (default: None, uses video duration)')
    args = parser.parse_args()

    # Parse resolution
    width, height = map(int, args.resolution.split('x'))

    print("🎞️  Video Assembly Agent: Creating final video...")

    # Load configuration
    video_settings = load_config()
    sync_config = load_sync_config()

    # Override resolution with command-line argument
    video_settings["resolution"] = (width, height)
    print(f"  Target resolution: {width}x{height}")

    # Override consolidation if flag is set
    if args.no_consolidation:
        if "clip_consolidation" not in sync_config:
            sync_config["clip_consolidation"] = {}
        sync_config["clip_consolidation"]["enabled"] = False
        print("  Clip consolidation: DISABLED (--no-consolidation flag)")

    # Load approved media
    approved_data = load_approved_media()

    # Check for audio
    audio_path = get_output_path("song.mp3")
    if not audio_path.exists():
        print(f"❌ Error: {audio_path} not found")
        print("Run composer agent first: ./agents/3_compose.py")
        sys.exit(1)

    # Attempt synchronized assembly if enabled and not disabled by flag
    if sync_config.get("enabled", True) and not args.no_sync:
        try:
            # Load music metadata
            metadata_path = get_output_path("music_metadata.json")
            if metadata_path.exists():
                with open(metadata_path) as f:
                    music_metadata = json.load(f)

                # Load research data
                research_path = get_output_path("research.json")
                if research_path.exists():
                    with open(research_path) as f:
                        research_data = json.load(f)

                    print("\n🎵 Fetching lyric timestamps from Suno API...")
                    aligned_data, phrase_groups = fetch_and_process_lyrics(
                        music_metadata, research_data, sync_config
                    )

                    if phrase_groups:
                        print(f"✅ Created {len(phrase_groups)} semantic phrase groups")
                        print("\n🎯 Matching videos to phrase groups...")

                        # Get available media from approved list
                        available_media = [
                            {
                                "url": shot.get("media_url", ""),
                                "description": shot.get("description", ""),
                                "local_path": shot.get("local_path"),
                                "media_type": shot.get("media_type", "video")
                            }
                            for shot in approved_data["shot_list"]
                            if "local_path" in shot
                        ]

                        synchronized_plan = create_synchronized_plan(
                            phrase_groups, available_media, sync_config, target_audio_duration=args.audio_duration
                        )

                        print(f"✅ Matched {len(synchronized_plan['shot_list'])} synchronized shots")
                        print("\n🎬 Assembling synchronized video...")

                        # Use synchronized plan instead of approved_data
                        output_path = assemble_video(synchronized_plan, video_settings, str(audio_path), audio_start=args.audio_start, audio_duration=args.audio_duration)

                        print(f"\n✅ Synchronized video assembly complete!")
                        print(f"📹 Final video: {output_path}")
                        print(f"🎯 Synchronization: {len(phrase_groups)} phrase-aligned shots")
                        print(f"\nNext steps:")
                        print(f"  - Preview: open {output_path}")
                        print(f"  - Compare with phrase_groups.json to verify timing")
                        return

        except Exception as e:
            logger.warning(f"Synchronized assembly failed: {e}")
            logger.warning("Falling back to curator's media plan")

    # Fallback to original assembly
    print("\n🎬 Assembling video with curator's timing...")
    # Fallback to original assembly
    print("\n🎬 Assembling video with curator's timing...")
    output_path = assemble_video(approved_data, video_settings, str(audio_path), audio_start=args.audio_start, audio_duration=args.audio_duration)

    print(f"\n✅ Video assembly complete!")
    print(f"📹 Final video: {output_path}")
    print(f"\nNext steps:")
    print(f"  - Preview: open {output_path}")
    print(f"  - Edit in iMovie if needed")
    print(f"  - Share to TikTok/Instagram Reels")


if __name__ == "__main__":
    main()
