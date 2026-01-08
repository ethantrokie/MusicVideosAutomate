#!/usr/bin/env python3
"""
Cross-link uploaded videos by updating descriptions.
"""

import os
import sys
import pickle
import json
from pathlib import Path
from googleapiclient.discovery import build


def get_youtube_service():
    """Get authenticated YouTube API service."""
    token_path = Path('config/youtube_token.pickle')

    with open(token_path, 'rb') as token:
        creds = pickle.load(token)

    return build('youtube', 'v3', credentials=creds)


def update_video_description(youtube, video_id: str, new_description: str):
    """Update video description."""
    # Get current video details
    response = youtube.videos().list(
        part='snippet',
        id=video_id
    ).execute()

    if not response['items']:
        raise ValueError(f"Video not found: {video_id}")

    snippet = response['items'][0]['snippet']

    # Update description
    snippet['description'] = new_description

    # Update video
    youtube.videos().update(
        part='snippet',
        body={
            'id': video_id,
            'snippet': snippet
        }
    ).execute()


def main(full_id: str, hook_id: str, edu_id: str, intro_id: str = None, tiktok_full_id: str = None, tiktok_hook_id: str = None):
    """Cross-link videos across YouTube and TikTok."""
    print("🔗 Cross-linking videos...")

    youtube = get_youtube_service()

    # Build YouTube URLs
    full_url = f"https://youtube.com/watch?v={full_id}"
    hook_url = f"https://youtube.com/shorts/{hook_id}"
    edu_url = f"https://youtube.com/shorts/{edu_id}"
    intro_url = f"https://youtube.com/shorts/{intro_id}" if intro_id else None

    # Load topic from research.json (preferred) or fallback to idea.txt
    output_dir = Path(os.environ.get('OUTPUT_DIR', 'outputs/current'))
    research_path = output_dir / 'research.json'
    topic = ''  # Initialize
    if research_path.exists():
        with open(research_path) as f:
            research = json.load(f)
            topic = research.get('video_title', '')
    
    # Fallback to old method if video_title not available
    if not topic:
        topic = Path('input/idea.txt').read_text().strip().split('.')[0]

    # Build TikTok URLs if IDs provided
    tiktok_full_url = None
    tiktok_hook_url = None
    if tiktok_full_id or tiktok_hook_id:
        # Load TikTok username from config
        config_path = Path('automation/config/automation_config.json')
        if config_path.exists():
            with open(config_path) as f:
                config = json.load(f)
                tiktok_username = config.get('tiktok', {}).get('username', '@learningsciencemusic')
        else:
            tiktok_username = '@learningsciencemusic'

        if tiktok_full_id:
            tiktok_full_url = f"https://tiktok.com/{tiktok_username}/video/{tiktok_full_id}"
        if tiktok_hook_id:
            tiktok_hook_url = f"https://tiktok.com/{tiktok_username}/video/{tiktok_hook_id}"

    # Build cross-platform links section
    tiktok_section = ""
    if tiktok_full_url or tiktok_hook_url:
        tiktok_section = "\n\nAlso on TikTok:"
        if tiktok_full_url:
            tiktok_section += f"\n- Full version: {tiktok_full_url}"
        if tiktok_hook_url:
            tiktok_section += f"\n- Musical hook: {tiktok_hook_url}"

    # Build intro section if available
    intro_section = f"\n- Intro Preview: {intro_url}" if intro_url else ""

    # Update full video description
    full_desc = f"""Learn about {topic} through music! Full version.

Watch the Shorts versions:
- Musical Hook: {hook_url}
- Educational Highlight: {edu_url}{intro_section}{tiktok_section}

#education #learning #science"""

    print(f"  Updating full video description...")
    update_video_description(youtube, full_id, full_desc)

    # Update hook short description
    hook_desc = f"""{topic} 🎵

Watch the full version: {full_url}
See the educational highlight: {edu_url}{tiktok_section if tiktok_full_url or tiktok_hook_url else ''}

#shorts #education #learning"""

    print(f"  Updating hook short description...")
    update_video_description(youtube, hook_id, hook_desc)

    # Update educational short description
    edu_desc = f"""{topic} - Key concept explained! 📚

Watch the full version: {full_url}
See the musical hook: {hook_url}{tiktok_section if tiktok_full_url or tiktok_hook_url else ''}

#shorts #education #learning"""

    print(f"  Updating educational short description...")
    update_video_description(youtube, edu_id, edu_desc)

    # Update intro short description (if available)
    if intro_id:
        intro_desc = f"""{topic} - First minute preview! 🎬

Watch the full version: {full_url}
See the educational highlight: {edu_url}{tiktok_section if tiktok_full_url or tiktok_hook_url else ''}

#shorts #education #learning"""

        print(f"  Updating intro short description...")
        update_video_description(youtube, intro_id, intro_desc)

    print("✅ Cross-linking complete")

    # Save results
    output_dir = Path(os.environ.get('OUTPUT_DIR', 'outputs/current'))
    results = {
        'youtube': {
            'full_video': {'id': full_id, 'url': full_url},
            'hook_short': {'id': hook_id, 'url': hook_url},
            'educational_short': {'id': edu_id, 'url': edu_url}
        }
    }

    # Add intro short to results if available
    if intro_id:
        results['youtube']['intro_short'] = {'id': intro_id, 'url': intro_url}

    # Add TikTok results if available
    if tiktok_full_id or tiktok_hook_id:
        results['tiktok'] = {}
        if tiktok_full_id:
            results['tiktok']['full_video'] = {'id': tiktok_full_id, 'url': tiktok_full_url}
        if tiktok_hook_id:
            results['tiktok']['hook_short'] = {'id': tiktok_hook_id, 'url': tiktok_hook_url}

    with open(output_dir / 'upload_results.json', 'w') as f:
        json.dump(results, f, indent=2)


if __name__ == '__main__':
    if len(sys.argv) < 4 or len(sys.argv) > 7:
        print("Usage: crosslink_videos.py <full_video_id> <hook_short_id> <edu_short_id> [intro_short_id] [tiktok_full_id] [tiktok_hook_id]")
        sys.exit(1)

    try:
        # Extract arguments (empty strings are treated as None)
        full_id = sys.argv[1]
        hook_id = sys.argv[2]
        edu_id = sys.argv[3]
        intro_id = sys.argv[4] if len(sys.argv) > 4 and sys.argv[4] else None
        tiktok_full_id = sys.argv[5] if len(sys.argv) > 5 and sys.argv[5] else None
        tiktok_hook_id = sys.argv[6] if len(sys.argv) > 6 and sys.argv[6] else None

        main(full_id, hook_id, edu_id, intro_id, tiktok_full_id, tiktok_hook_id)
    except Exception as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
