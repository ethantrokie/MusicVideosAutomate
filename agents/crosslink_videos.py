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


def main(full_id: str, hook_id: str, edu_id: str):
    """Cross-link three videos."""
    print("🔗 Cross-linking videos...")

    youtube = get_youtube_service()

    # Build URLs
    full_url = f"https://youtube.com/watch?v={full_id}"
    hook_url = f"https://youtube.com/shorts/{hook_id}"
    edu_url = f"https://youtube.com/shorts/{edu_id}"

    # Load topic
    topic = Path('input/idea.txt').read_text().strip().split('.')[0]

    # Update full video description
    full_desc = f"""Learn about {topic} through music! Full version.

Watch the Shorts versions:
- Musical Hook: {hook_url}
- Educational Highlight: {edu_url}

#education #learning #science"""

    print(f"  Updating full video description...")
    update_video_description(youtube, full_id, full_desc)

    # Update hook short description
    hook_desc = f"""{topic} 🎵

Watch the full version: {full_url}
See the educational highlight: {edu_url}

#shorts #education #learning"""

    print(f"  Updating hook short description...")
    update_video_description(youtube, hook_id, hook_desc)

    # Update educational short description
    edu_desc = f"""{topic} - Key concept explained! 📚

Watch the full version: {full_url}
See the musical hook: {hook_url}

#shorts #education #learning"""

    print(f"  Updating educational short description...")
    update_video_description(youtube, edu_id, edu_desc)

    print("✅ Cross-linking complete")

    # Save results
    output_dir = Path(os.environ.get('OUTPUT_DIR', 'outputs/current'))
    results = {
        'full_video': {'id': full_id, 'url': full_url},
        'hook_short': {'id': hook_id, 'url': hook_url},
        'educational_short': {'id': edu_id, 'url': edu_url}
    }

    with open(output_dir / 'upload_results.json', 'w') as f:
        json.dump(results, f, indent=2)


if __name__ == '__main__':
    if len(sys.argv) != 4:
        print("Usage: crosslink_videos.py <full_video_id> <hook_short_id> <edu_short_id>")
        sys.exit(1)

    try:
        main(sys.argv[1], sys.argv[2], sys.argv[3])
    except Exception as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
