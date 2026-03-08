#!/usr/bin/env python3
"""
Multi-format video builder.
Orchestrates creation of full video + two shorts from one song.
"""

import os
import sys
import json
import subprocess
from pathlib import Path
from typing import Dict

# Add agents directory to path
sys.path.insert(0, str(Path(__file__).parent))
from output_helper import get_output_path


def build_video_with_format_plan(
    format_type: str,
    resolution: str,
    output_name: str,
    media_plan_file: str,
    start_time: float = 0.0,
    duration: float = None
) -> bool:
    """
    Build a video using a format-specific media plan.

    Args:
        format_type: "full", "hook", or "educational"
        resolution: Video resolution (e.g., "1920x1080")
        output_name: Output filename (e.g., "full.mp4")
        media_plan_file: Media plan JSON file (e.g., "media_plan_full.json")
        start_time: Start time in seconds for audio slicing
        duration: Desired audio duration in seconds (if None, uses video duration)

    Returns:
        True if successful, False otherwise
    """
    print(f"🎬 Building {format_type} video from {media_plan_file} (audio start: {start_time}s, duration: {duration}s)...")

    output_dir = Path(os.getenv("OUTPUT_DIR", "outputs"))
    media_plan_path = output_dir / media_plan_file

    if not media_plan_path.exists():
        print(f"  ❌ Media plan not found: {media_plan_path}")
        return False

    # Temporarily swap approved_media.json with format-specific plan
    approved_media_path = output_dir / "approved_media.json"
    backup_path = output_dir / "approved_media.json.backup"

    # Backup original approved_media.json
    if approved_media_path.exists():
        approved_media_path.rename(backup_path)

    try:
        # Copy format-specific plan to approved_media.json
        import shutil
        shutil.copy(media_plan_path, approved_media_path)

        # Delete cached synchronized_plan.json to force regeneration
        # This prevents the bug where all videos use the same cached plan
        sync_plan_path = output_dir / "synchronized_plan.json"
        if sync_plan_path.exists():
            sync_plan_path.unlink()

        # Call video assembly with appropriate resolution, audio start time, and duration
        cmd = [
            sys.executable,
            'agents/5_assemble_video.py',
            '--resolution', resolution,
            '--audio-start', str(start_time)
        ]

        # Add audio duration if specified
        if duration is not None:
            cmd.extend(['--audio-duration', str(duration)])
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=600
        )

        if result.returncode != 0:
            print(f"  ❌ Video assembly failed")
            # Print stderr if available, otherwise stdout (many scripts print errors to stdout)
            error_output = result.stderr.strip() if result.stderr.strip() else result.stdout.strip()
            if error_output:
                print(f"  Error: {error_output[-1000:]}")  # Last 1000 chars
            else:
                print(f"  Error: No error output captured")
            return False

        # Rename final_video.mp4 to format-specific name
        final_video = output_dir / "final_video.mp4"
        if final_video.exists():
            final_video.rename(output_dir / output_name)
            print(f"  ✅ Created {output_name}")
            return True
        else:
            print(f"  ❌ Video assembly didn't create final_video.mp4")
            return False

    finally:
        # Restore original approved_media.json
        if backup_path.exists():
            if approved_media_path.exists():
                approved_media_path.unlink()
            backup_path.rename(approved_media_path)

    return False


def load_config() -> Dict:
    """Load configuration."""
    with open('config/config.json') as f:
        return json.load(f)


def load_segments() -> Dict:
    """Load segment analysis results."""
    segments_file = get_output_path('segments.json')
    with open(segments_file) as f:
        return json.load(f)


def build_full_video(duration: float) -> Path:
    """Build full horizontal video using format-specific media plan."""
    print("🎬 Building full video (16:9) with 180s media plan...")

    success = build_video_with_format_plan(
        format_type="full",
        resolution="1920x1080",
        output_name="full.mp4",
        media_plan_file="media_plan_full.json",
        start_time=0.0,
        duration=duration
    )

    if not success:
        print("❌ Failed to build full video")
        sys.exit(1)

    output_dir = Path(os.getenv("OUTPUT_DIR", "outputs"))
    return output_dir / "full.mp4"


def build_hook_short(start_time: float, duration: float) -> Path:
    """Build hook short using format-specific media plan."""
    print(f"🎬 Building hook short (9:16) with 30s media plan (start: {start_time}s)...")

    success = build_video_with_format_plan(
        format_type="hook",
        resolution="1080x1920",
        output_name="short_hook.mp4",
        media_plan_file="media_plan_hook.json",
        start_time=start_time,
        duration=duration
    )

    if not success:
        print("❌ Failed to build hook short")
        sys.exit(1)

    output_dir = Path(os.getenv("OUTPUT_DIR", "outputs"))
    return output_dir / "short_hook.mp4"


def build_educational_short(start_time: float, duration: float) -> Path:
    """Build educational short using format-specific media plan."""
    print(f"🎬 Building educational short (9:16) with 30s media plan (start: {start_time}s)...")

    success = build_video_with_format_plan(
        format_type="educational",
        resolution="1080x1920",
        output_name="short_educational.mp4",
        media_plan_file="media_plan_educational.json",
        start_time=start_time,
        duration=duration
    )

    if not success:
        print("❌ Failed to build educational short")
        sys.exit(1)

    output_dir = Path(os.getenv("OUTPUT_DIR", "outputs"))
    return output_dir / "short_educational.mp4"


def build_intro_short(start_time: float, duration: float) -> Path:
    """Build intro short using format-specific media plan."""
    print(f"🎬 Building intro short (9:16) with {duration}s media plan (start: {start_time}s)...")

    success = build_video_with_format_plan(
        format_type="intro",
        resolution="1080x1920",
        output_name="short_intro.mp4",
        media_plan_file="media_plan_intro.json",
        start_time=start_time,
        duration=duration
    )

    if not success:
        print("❌ Failed to build intro short")
        sys.exit(1)

    output_dir = Path(os.getenv("OUTPUT_DIR", "outputs"))
    return output_dir / "short_intro.mp4"


def main():
    """Main execution."""
    print("🎥 Multi-Format Video Builder")
    print("=" * 50)

    config = load_config()
    video_formats = config.get('video_formats', {})

    # Check if multi-format is enabled
    if not video_formats.get('full_video', {}).get('enabled', True):
        print("⚠️  Full video disabled in config, skipping")
        return

    try:
        # Load segment analysis
        segments = load_segments()
        print(f"📊 Loaded segments:")
        print(f"  Full: {segments['full']['duration']:.1f}s")
        print(f"  Hook: {segments['hook']['start']:.1f}-{segments['hook']['end']:.1f}s")
        print(f"  Educational: {segments['educational']['start']:.1f}-{segments['educational']['end']:.1f}s")
        print(f"  Intro: {segments['intro']['start']:.1f}-{segments['intro']['end']:.1f}s")
        print()

        # Build format-specific media plans based on segments
        print("\n📋 Creating format-specific media plans...")
        result = subprocess.run(
            [sys.executable, 'agents/build_format_media_plan.py'],
            env=os.environ.copy()
        )

        if result.returncode != 0:
            print("❌ Failed to create format-specific media plans")
            sys.exit(1)
        print()

        # Build full video using format-specific media plan
        full_video = build_full_video(segments['full']['duration'])
        print()

        # Check if shorts are enabled
        if not video_formats.get('shorts', {}).get('enabled', True):
            print("⚠️  Shorts disabled in config, skipping")
            return

        # Check format_mode: "full" = all 4 formats, "reduced" = full + intro only
        format_mode = video_formats.get('format_mode', 'full')
        print(f"  Format mode: {format_mode}")

        output_dir = Path(os.environ.get('OUTPUT_DIR', 'outputs/current'))

        if format_mode == 'reduced':
            # Reduced mode: only build intro short (starts from beginning of song)
            print("  Reduced mode: building full + intro short only")
            build_intro_short(segments['intro']['start'], segments['intro']['duration'])
            print()

            print("✅ Videos built (reduced mode)!")
            print()
            print("Output files:")
            print(f"  {output_dir}/full.mp4")
            print(f"  {output_dir}/short_intro.mp4")
        else:
            # Full mode: build all shorts
            build_hook_short(segments['hook']['start'], segments['hook']['duration'])
            print()
            build_educational_short(segments['educational']['start'], segments['educational']['duration'])
            print()
            build_intro_short(segments['intro']['start'], segments['intro']['duration'])
            print()

            print("✅ All videos built successfully!")
            print()
            print("Output files:")
            print(f"  {output_dir}/full.mp4")
            print(f"  {output_dir}/short_hook.mp4")
            print(f"  {output_dir}/short_educational.mp4")
            print(f"  {output_dir}/short_intro.mp4")

    except Exception as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
