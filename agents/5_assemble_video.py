#!/usr/bin/env python3
"""
Video assembly agent using MoviePy.
Combines approved media with generated music into final video.
"""

import os
import sys
import json
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


def load_config():
    """Load video settings from config."""
    config_path = Path("config/config.json")
    with open(config_path) as f:
        config = json.load(f)
    return config["video_settings"]


def load_approved_media():
    """Load approved media shot list."""
    media_path = get_output_path("approved_media.json")
    if not media_path.exists():
        print(f"❌ Error: {media_path} not found")
        print("Run approval script first: ./approve_media.sh")
        sys.exit(1)

    with open(media_path) as f:
        return json.load(f)


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

            # Trim if needed
            if clip.duration > duration:
                clip = clip.subclip(0, duration)
            elif clip.duration < duration:
                # Loop if too short
                clip = clip.loop(duration=duration)

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

        # Apply transitions BEFORE centering to avoid recursion issues
        if transition == "fade" or transition == "crossfade":
            fade_duration = 0.5
            clip = vfx.fadein(clip, fade_duration)
            clip = vfx.fadeout(clip, fade_duration)

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


def assemble_video(approved_data: dict, video_settings: dict, audio_path: str):
    """
    Assemble final video from approved media and audio.

    Args:
        approved_data: Approved media JSON
        video_settings: Video config
        audio_path: Path to music file

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
    print("  Adding audio track...")
    audio = AudioFileClip(audio_path)

    # Trim audio if longer than video
    if audio.duration > final_video.duration:
        audio = audio.subclip(0, final_video.duration)

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
    print("🎞️  Video Assembly Agent: Creating final video...")

    # Load configuration
    video_settings = load_config()

    # Load approved media
    approved_data = load_approved_media()

    # Check for audio
    audio_path = get_output_path("song.mp3")
    if not audio_path.exists():
        print(f"❌ Error: {audio_path} not found")
        print("Run composer agent first: ./agents/3_compose.py")
        sys.exit(1)

    audio_path = str(audio_path)  # Convert to string for MoviePy

    # Assemble video
    output_path = assemble_video(approved_data, video_settings, audio_path)

    print(f"\n✅ Video assembly complete!")
    print(f"📹 Final video: {output_path}")
    print(f"\nNext steps:")
    print(f"  - Preview: open {output_path}")
    print(f"  - Edit in iMovie if needed")
    print(f"  - Share to TikTok/Instagram Reels")


if __name__ == "__main__":
    main()
