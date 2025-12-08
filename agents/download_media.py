#!/usr/bin/env python3
"""
Download media files from URLs with retry logic.
"""

import os
import sys
import json
import requests
from pathlib import Path
from urllib.parse import urlparse

# Add agents directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))
from stock_photo_api import StockPhotoResolver
from output_helper import get_output_path, ensure_output_dir


def is_slideshow_gif(file_path: str, fps_threshold: float = 10.0) -> bool:
    """
    Detect if a GIF is a slideshow (low frame rate).

    Args:
        file_path: Path to the file
        fps_threshold: Minimum FPS to be considered video (default: 10)

    Returns:
        bool: True if it's a slideshow GIF, False otherwise
    """
    import subprocess
    import json

    # Only check GIF files
    if not file_path.lower().endswith('.gif'):
        return False

    try:
        # Get frame rate using ffprobe
        result = subprocess.run([
            'ffprobe', '-v', 'error',
            '-select_streams', 'v:0',
            '-show_entries', 'stream=avg_frame_rate',
            '-of', 'json',
            file_path
        ], capture_output=True, text=True, timeout=10)

        if result.returncode != 0:
            return False

        data = json.loads(result.stdout)
        streams = data.get('streams', [])
        if not streams:
            return False

        # Parse frame rate (format: "num/den")
        fps_str = streams[0].get('avg_frame_rate', '0/1')
        num, den = map(int, fps_str.split('/'))
        fps = num / den if den != 0 else 0

        # Consider it a slideshow if FPS is below threshold
        return fps < fps_threshold

    except Exception:
        # If we can't determine, assume it's okay
        return False


def get_media_duration(file_path: str) -> float:
    """
    Get duration of media file in seconds using ffprobe.

    Returns:
        float: Duration in seconds, or 0.0 if unable to determine
    """
    import subprocess

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


def validate_clip_durations(shots: list, downloaded: list, target_duration: float) -> None:
    """
    Validate that downloaded clips have sufficient total duration.

    Args:
        shots: Original shot list from media_plan.json
        downloaded: List of successfully downloaded files
        target_duration: Target video duration in seconds
    """
    print(f"\n🔍 Validating clip durations...")

    # Build mapping from shot_number to required duration
    shot_durations = {}
    for shot in shots:
        shot_durations[shot["shot_number"]] = shot.get("duration", 0)

    # Check actual durations of downloaded files
    actual_durations = {}
    total_actual = 0.0
    total_required = 0.0
    insufficient_clips = []

    for item in downloaded:
        shot_num = item["shot_number"]
        file_path = item["local_path"]
        required_duration = shot_durations.get(shot_num, 0)

        # Get actual duration
        actual_duration = get_media_duration(file_path)
        actual_durations[shot_num] = actual_duration

        total_actual += actual_duration
        total_required += required_duration

        # Track clips that are shorter than required
        if actual_duration < required_duration:
            shortage = required_duration - actual_duration
            insufficient_clips.append({
                "shot_number": shot_num,
                "required": required_duration,
                "actual": actual_duration,
                "shortage": shortage
            })

    # Summary
    print(f"  Total required duration: {total_required:.2f}s")
    print(f"  Total actual duration: {total_actual:.2f}s")
    print(f"  Target video duration: {target_duration:.2f}s")

    if insufficient_clips:
        print(f"\n  ⚠️  Warning: {len(insufficient_clips)} clips are shorter than required:")
        for clip in insufficient_clips:
            print(f"    - Shot {clip['shot_number']}: needs {clip['required']:.2f}s, got {clip['actual']:.2f}s (short by {clip['shortage']:.2f}s)")
        print(f"\n  Note: Video assembly will handle shortages by trimming final video to audio length")

    # Check if we have enough total duration
    if total_actual < target_duration:
        shortage = target_duration - total_actual
        print(f"\n  ⚠️  WARNING: Total clip duration ({total_actual:.2f}s) is less than target ({target_duration:.2f}s)")
        print(f"    Shortage: {shortage:.2f}s")
        print(f"    The final video may end prematurely or show black frames")
        print(f"    Consider downloading more media or using longer clips")
    else:
        surplus = total_actual - target_duration
        print(f"  ✅ Sufficient clip duration (surplus: {surplus:.2f}s)")


def download_file(url: str, output_path: str, max_retries: int = 3) -> bool:
    """
    Download file with retry logic.

    Returns:
        bool: True if successful, False otherwise
    """
    for attempt in range(max_retries):
        try:
            response = requests.get(url, stream=True, timeout=30)

            if response.status_code == 200:
                with open(output_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
                return True
            else:
                print(f"  ⚠️  Attempt {attempt + 1}: HTTP {response.status_code}")

        except Exception as e:
            print(f"  ⚠️  Attempt {attempt + 1}: {str(e)}")

    return False


def main():
    """Download all media from shot list."""
    import argparse

    parser = argparse.ArgumentParser(description='Download media files from shot list')
    parser.add_argument('--aspect-ratio', choices=['landscape', 'portrait', 'any'],
                       default='any', help='Preferred media orientation')
    parser.add_argument('--segment', choices=['full', 'hook', 'educational'],
                       default='full', help='Which segment to fetch media for')
    args = parser.parse_args()

    # Load shot list
    shot_list_path = get_output_path("media_plan.json")
    if not shot_list_path.exists():
        print(f"❌ Error: {shot_list_path} not found")
        sys.exit(1)

    with open(shot_list_path) as f:
        data = json.load(f)

    shots = data["shot_list"]

    # Create segment-specific subdirectory if not full
    if args.segment != 'full':
        media_dir = ensure_output_dir(f"media/{args.segment}")
    else:
        media_dir = ensure_output_dir("media")

    print(f"📥 Downloading {len(shots)} media files for {args.segment} segment...")

    # Initialize URL resolver
    resolver = StockPhotoResolver()

    # Note: aspect_ratio parameter will be used by upstream media planning
    # to filter API results for landscape (16:9) or portrait (9:16) orientation

    downloaded = []
    failed = []

    for shot in shots:
        shot_num = shot["shot_number"]
        page_url = shot["media_url"]
        media_type = shot["media_type"]

        # Resolve page URL to download URL
        url = resolver.resolve_url(page_url, media_type)
        if not url:
            print(f"  [{shot_num}/{len(shots)}] shot_{shot_num:02d}... ❌ (URL resolution failed)")
            failed.append({
                "shot_number": shot_num,
                "url": page_url,
                "reason": "url_resolution_failed"
            })
            continue

        # Determine extension
        parsed = urlparse(url)
        ext = Path(parsed.path).suffix
        if not ext:
            ext = ".jpg" if media_type == "image" else ".mp4"

        # Output filename
        filename = f"shot_{shot_num:02d}{ext}"
        output_path = media_dir / filename

        print(f"  [{shot_num}/{len(shots)}] {filename}... ", end="", flush=True)

        if download_file(url, str(output_path)):
            # Check if it's a slideshow GIF (low FPS)
            if is_slideshow_gif(str(output_path)):
                print("⏭️  (slideshow GIF rejected)")
                output_path.unlink()  # Delete the file
                failed.append({
                    "shot_number": shot_num,
                    "url": url,
                    "reason": "slideshow_gif_rejected"
                })
            else:
                print("✅")
                downloaded.append({
                    "shot_number": shot_num,
                    "local_path": str(output_path),
                    "url": url
                })
        else:
            print("❌")
            failed.append({
                "shot_number": shot_num,
                "url": url,
                "reason": "download_failed"
            })

    # Save download manifest
    manifest = {
        "downloaded": downloaded,
        "failed": failed,
        "success_count": len(downloaded),
        "failure_count": len(failed)
    }

    manifest_path = get_output_path("media_manifest.json")
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)

    print(f"\n✅ Downloaded: {len(downloaded)}/{len(shots)}")
    if failed:
        print(f"❌ Failed: {len(failed)}")
        for f in failed:
            print(f"  - Shot {f['shot_number']}: {f['url']}")

    # Validate clip durations against requirements
    target_duration = data.get("total_duration", 60)  # Default to 60s if not specified
    validate_clip_durations(shots, downloaded, target_duration)


if __name__ == "__main__":
    main()
