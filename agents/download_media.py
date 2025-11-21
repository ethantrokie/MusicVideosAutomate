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


if __name__ == "__main__":
    main()
