#!/usr/bin/env python3
"""
Visual Ranking Agent
Downloads candidate media and uses Claude's vision capabilities to rank them
for educational quality and relevance.
"""

import os
import sys
import json
import requests
from pathlib import Path
from typing import List, Dict, Optional

# Add agents directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))
from output_helper import get_output_path, ensure_output_dir


def download_media_file(url: str, output_path: str) -> bool:
    """Download a media file from URL."""
    try:
        response = requests.get(url, stream=True, timeout=30)
        if response.status_code == 200:
            with open(output_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            return True
    except Exception as e:
        print(f"  ⚠️  Download failed: {e}")
    return False


def main():
    """Main execution."""
    print("👁️  Visual Ranking Agent: Analyzing media quality...")

    # Load research data
    research_path = get_output_path("research.json")
    if not research_path.exists():
        print(f"❌ Error: {research_path} not found")
        sys.exit(1)

    with open(research_path) as f:
        research = json.load(f)

    media_suggestions = research.get("media_suggestions", [])
    print(f"  Found {len(media_suggestions)} media candidates")

    # Create temp download directory
    temp_dir = ensure_output_dir("temp_media")

    # Download all media files
    print("  Downloading media files for analysis...")
    downloaded_media = []

    for i, media in enumerate(media_suggestions, 1):
        media_url = media.get("url", "")
        media_type = media.get("type", "image")

        # Determine file extension
        ext = ".mp4" if media_type == "video" else ".gif" if "giphy" in media_url.lower() else ".jpg"
        temp_path = temp_dir / f"candidate_{i:02d}{ext}"

        print(f"    [{i}/{len(media_suggestions)}] Downloading {media.get('source', 'unknown')} media...")

        # Use stock photo resolver for URL resolution
        from stock_photo_api import StockPhotoResolver
        resolver = StockPhotoResolver()
        resolved_url = resolver.resolve_url(media_url, media_type)

        if resolved_url and download_media_file(resolved_url, str(temp_path)):
            downloaded_media.append({
                "index": i - 1,
                "local_path": str(temp_path),
                "original_data": media,
                "resolved_url": resolved_url
            })
        else:
            print(f"      ⚠️  Failed to download")

    print(f"\n  Successfully downloaded {len(downloaded_media)} files")

    # Save downloaded media list for Claude to analyze
    analysis_input = {
        "topic": research.get("topic", ""),
        "tone": research.get("tone", ""),
        "key_facts": research.get("key_facts", []),
        "downloaded_media": downloaded_media
    }

    analysis_input_path = get_output_path("visual_analysis_input.json")
    with open(analysis_input_path, "w") as f:
        json.dump(analysis_input, f, indent=2)

    print(f"\n✅ Media downloaded and ready for visual analysis")
    print(f"📁 Files saved to: {temp_dir}")
    print(f"\n⏭️  Next: Run visual analysis to rank media quality")
    print(f"   This requires Claude Code's visual analysis capabilities")


if __name__ == "__main__":
    main()
