#!/usr/bin/env python3
"""
Video assembly agent using MoviePy.
Combines approved media with generated music into final video.
"""

import os
import sys
import json
from pathlib import Path
from moviepy.editor import (
    VideoFileClip,
    ImageClip,
    AudioFileClip,
    CompositeVideoClip,
    concatenate_videoclips,
    CompositeAudioClip
)
from moviepy.video.fx import resize, fadein, fadeout


def load_config():
    """Load video settings from config."""
    config_path = Path("config/config.json")
    with open(config_path) as f:
        config = json.load(f)
    return config["video_settings"]


def load_approved_media():
    """Load approved media shot list."""
    media_path = Path("outputs/approved_media.json")
    if not media_path.exists():
        print("❌ Error: outputs/approved_media.json not found")
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

        # Resize to target resolution (maintain aspect ratio, crop to fit)
        clip = clip.resize(height=target_height)

        if clip.w < target_width:
            clip = clip.resize(width=target_width)

        # Center crop
        if clip.w > target_width:
            x_center = clip.w / 2
            x1 = x_center - target_width / 2
            clip = clip.crop(x1=x1, width=target_width)

        if clip.h > target_height:
            y_center = clip.h / 2
            y1 = y_center - target_height / 2
            clip = clip.crop(y1=y1, height=target_height)

        # Apply transitions
        if transition == "fade" or transition == "crossfade":
            fade_duration = 0.5
            clip = fadein(clip, fade_duration)
            clip = fadeout(clip, fade_duration)

        return clip

    except Exception as e:
        print(f"  ⚠️  Error loading shot {shot['shot_number']}: {e}")
        # Return black placeholder clip
        return ImageClip(
            size=(target_width, target_height),
            color=(0, 0, 0),
            duration=duration
        )


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
    clips = []

    # Create clips for each shot
    print(f"  Creating {len(shots)} video clips...")
    for i, shot in enumerate(shots, 1):
        print(f"    [{i}/{len(shots)}] Shot {shot['shot_number']}: {shot['description'][:40]}...")
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
    output_path = "outputs/final_video.mp4"
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
    audio_path = "outputs/song.mp3"
    if not Path(audio_path).exists():
        print("❌ Error: outputs/song.mp3 not found")
        print("Run composer agent first: ./agents/3_compose.py")
        sys.exit(1)

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
