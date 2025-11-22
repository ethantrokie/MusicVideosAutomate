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


def load_config() -> Dict:
    """Load configuration."""
    with open('config/config.json') as f:
        return json.load(f)


def load_segments() -> Dict:
    """Load segment analysis results."""
    segments_file = get_output_path('segments.json')
    with open(segments_file) as f:
        return json.load(f)


def build_full_video():
    """Build full horizontal video using existing assembly script."""
    print("🎬 Building full video (16:9)...")

    # Call existing video assembly script with horizontal resolution
    result = subprocess.run(
        ['./venv/bin/python3', 'agents/5_assemble_video.py', '--resolution', '1920x1080'],
        capture_output=True,
        text=True
    )

    if result.returncode != 0:
        raise Exception(f"Full video assembly failed: {result.stderr}")

    print(result.stdout)

    # Rename output to full.mp4
    output_dir = Path(os.environ.get('OUTPUT_DIR', 'outputs/current'))
    final_video = output_dir / 'final_video.mp4'
    full_video = output_dir / 'full.mp4'

    if final_video.exists():
        final_video.rename(full_video)
        print(f"✅ Full video saved: {full_video}")
        return full_video
    else:
        raise Exception("Final video not found after assembly")


def extract_short_from_full(full_video: Path, segment_name: str, segments: Dict, output_name: str):
    """
    Extract a short segment from the full video using FFmpeg.

    Args:
        full_video: Path to full video
        segment_name: 'hook' or 'educational'
        segments: Segment analysis results
        output_name: Output filename (e.g., 'short_hook.mp4')
    """
    print(f"✂️  Extracting {segment_name} short...")

    segment = segments[segment_name]
    start = segment['start']
    duration = segment['duration']

    output_dir = Path(os.environ.get('OUTPUT_DIR', 'outputs/current'))
    output_path = output_dir / output_name

    # Extract segment with FFmpeg (crop to 9:16 and extract time range)
    # For now, just extract the time range - cropping to 9:16 would require
    # knowing the full video's dimensions and calculating center crop
    cmd = [
        'ffmpeg', '-y',
        '-i', str(full_video),
        '-ss', str(start),
        '-t', str(duration),
        '-c:v', 'libx264',
        '-c:a', 'aac',
        '-preset', 'fast',
        str(output_path)
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        raise Exception(f"FFmpeg extraction failed: {result.stderr}")

    print(f"✅ Short saved: {output_path}")
    return output_path


def crop_to_vertical(video_path: Path, output_path: Path):
    """
    Crop horizontal video to vertical 9:16 format.

    Args:
        video_path: Input video path
        output_path: Output video path
    """
    print(f"  Cropping to 9:16...")

    # Get video dimensions first
    probe_cmd = [
        'ffprobe', '-v', 'error',
        '-select_streams', 'v:0',
        '-show_entries', 'stream=width,height',
        '-of', 'json',
        str(video_path)
    ]

    result = subprocess.run(probe_cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise Exception("Could not probe video dimensions")

    info = json.loads(result.stdout)
    width = info['streams'][0]['width']
    height = info['streams'][0]['height']

    # Calculate 9:16 crop (center crop)
    target_width = int(height * 9 / 16)
    x_offset = (width - target_width) // 2

    # Crop with FFmpeg
    temp_path = video_path.with_suffix('.temp.mp4')
    cmd = [
        'ffmpeg', '-y',
        '-i', str(video_path),
        '-filter:v', f'crop={target_width}:{height}:{x_offset}:0',
        '-c:a', 'copy',
        str(temp_path)
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        raise Exception(f"Cropping failed: {result.stderr}")

    # Replace original with cropped
    temp_path.rename(output_path)


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
        print()

        # Build full video using existing assembly
        full_video = build_full_video()
        print()

        # Check if shorts are enabled
        if not video_formats.get('shorts', {}).get('enabled', True):
            print("⚠️  Shorts disabled in config, skipping")
            return

        # Extract and crop shorts
        for segment_name, output_name in [('hook', 'short_hook.mp4'), ('educational', 'short_educational.mp4')]:
            # Extract segment
            short_path = extract_short_from_full(full_video, segment_name, segments, output_name)

            # Crop to vertical
            crop_to_vertical(short_path, short_path)
            print()

        print("✅ All videos built successfully!")
        print()
        print("Output files:")
        output_dir = Path(os.environ.get('OUTPUT_DIR', 'outputs/current'))
        print(f"  {output_dir}/full.mp4")
        print(f"  {output_dir}/short_hook.mp4")
        print(f"  {output_dir}/short_educational.mp4")

    except Exception as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
