#!/usr/bin/env python3
"""
TikTok Video Uploader Using Browser Automation

Uploads videos to TikTok using the tiktok-uploader package with browser automation.
This method bypasses the official API's sandbox restrictions by using browser cookies.

Usage:
    ./automation/tiktok_uploader_browser.py --video path/to/video.mp4 --title "My Video" --caption "Caption text"
    ./automation/tiktok_uploader_browser.py --video path/to/video.mp4 --title "My Video" --caption "Caption text" --privacy PUBLIC_TO_EVERYONE
"""

import argparse
import json
import sys
from pathlib import Path

try:
    from tiktok_uploader.upload import upload_video
    from tiktok_uploader.auth import AuthBackend
except ImportError:
    print("❌ Error: tiktok-uploader package not found")
    print("Install with: pip install tiktok-uploader")
    sys.exit(1)

# File paths
SCRIPT_DIR = Path(__file__).parent.parent
COOKIES_PATH = SCRIPT_DIR / "config" / "tiktok_cookies.txt"


def upload_to_tiktok(video_path, title, caption, privacy_level="PUBLIC_TO_EVERYONE", username="@learningsciencemusic"):
    """
    Upload video to TikTok using browser automation

    Args:
        video_path: Path to video file
        title: Video title (not directly used by TikTok API, used for internal tracking)
        caption: Video caption/description
        privacy_level: Privacy setting (PUBLIC_TO_EVERYONE, MUTUAL_FOLLOW_FRIENDS, SELF_ONLY)
        username: TikTok username for constructing video URL

    Returns:
        dict: Upload result with video ID and URL
    """
    video_path = Path(video_path)
    if not video_path.exists():
        raise FileNotFoundError(f"Video file not found: {video_path}")

    if not COOKIES_PATH.exists():
        raise FileNotFoundError(
            f"Cookies file not found: {COOKIES_PATH}\n"
            f"Please follow the setup instructions in docs/TIKTOK_BROWSER_SETUP.md to extract your TikTok cookies."
        )

    print(f"📤 Uploading video: {video_path.name}")
    print(f"   Caption: {caption[:50]}..." if len(caption) > 50 else f"   Caption: {caption}")
    print(f"   Privacy: {privacy_level}")

    # Configure upload parameters
    upload_params = {
        'filename': str(video_path),
        'description': caption,
        'cookies': str(COOKIES_PATH),
        'comment': True,  # Enable comments
        'stitch': True,   # Enable stitch
        'duet': True,     # Enable duet
    }

    # Map privacy levels to tiktok-uploader format
    privacy_map = {
        "PUBLIC_TO_EVERYONE": "PUBLIC_TO_EVERYONE",
        "MUTUAL_FOLLOW_FRIENDS": "MUTUAL_FOLLOW_FRIENDS",
        "SELF_ONLY": "SELF_ONLY",
        "public_to_everyone": "PUBLIC_TO_EVERYONE",
        "mutual_follow_friends": "MUTUAL_FOLLOW_FRIENDS",
        "self_only": "SELF_ONLY"
    }

    if privacy_level.upper() in privacy_map:
        upload_params['privacy'] = privacy_map[privacy_level.upper()]

    try:
        # Upload video using browser automation
        print("Starting browser automation upload...")
        result = upload_video(**upload_params)

        # tiktok-uploader returns different result formats
        # Try to extract video ID if available
        video_id = None
        video_url = None

        if isinstance(result, dict):
            video_id = result.get('id') or result.get('video_id')
            video_url = result.get('url')

        # Construct URL if we have a video ID
        if video_id and not video_url:
            # Remove @ from username if present
            clean_username = username.lstrip('@')
            video_url = f"https://www.tiktok.com/@{clean_username}/video/{video_id}"

        print(f"✅ Video uploaded successfully!")
        if video_id:
            print(f"   Video ID: {video_id}")
        if video_url:
            print(f"   Video URL: {video_url}")

        return {
            "id": video_id or "unknown",
            "url": video_url or f"https://www.tiktok.com/{username}",
            "status": "success",
            "method": "browser_automation"
        }

    except Exception as e:
        error_msg = str(e)

        # Provide helpful error messages
        if "cookies" in error_msg.lower():
            raise Exception(
                f"❌ Cookie authentication failed: {error_msg}\n"
                f"\n"
                f"Your cookies may have expired. To refresh:\n"
                f"1. Log into TikTok in your browser\n"
                f"2. Install 'Get cookies.txt' browser extension\n"
                f"3. Export cookies and save to: {COOKIES_PATH}\n"
                f"\n"
                f"See docs/TIKTOK_BROWSER_SETUP.md for detailed instructions."
            )
        elif "browser" in error_msg.lower() or "chrome" in error_msg.lower():
            raise Exception(
                f"❌ Browser automation failed: {error_msg}\n"
                f"\n"
                f"Make sure Google Chrome is installed.\n"
                f"On macOS: Download from https://www.google.com/chrome/"
            )
        else:
            raise Exception(f"❌ Upload failed: {error_msg}")


def main():
    parser = argparse.ArgumentParser(description="Upload videos to TikTok using browser automation")
    parser.add_argument("--video", required=True, help="Path to video file")
    parser.add_argument("--title", required=True, help="Video title (for internal tracking)")
    parser.add_argument("--caption", help="Video caption (defaults to title)")
    parser.add_argument("--privacy", default="PUBLIC_TO_EVERYONE",
                       choices=["PUBLIC_TO_EVERYONE", "MUTUAL_FOLLOW_FRIENDS", "SELF_ONLY",
                               "public_to_everyone", "mutual_follow_friends", "self_only"],
                       help="Privacy level")
    parser.add_argument("--username", default="@learningsciencemusic",
                       help="TikTok username for URL construction")

    args = parser.parse_args()

    caption = args.caption or args.title

    try:
        result = upload_to_tiktok(
            video_path=args.video,
            title=args.title,
            caption=caption,
            privacy_level=args.privacy,
            username=args.username
        )

        # Print result as JSON for parsing by shell scripts
        print(json.dumps(result))

    except Exception as e:
        print(f"\n{e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
