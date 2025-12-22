#!/usr/bin/env python3 -u
"""
Uploads video to Dropbox and triggers Zapier webhook for TikTok posting.

Usage:
  python agents/6_upload_dropbox_zapier.py <video_path> [caption]
  python agents/6_upload_dropbox_zapier.py --run=TIMESTAMP --type=full|short_hook|short_educational
"""

import os
import sys
import json
import argparse
import re
import requests
import dropbox
from dropbox.exceptions import ApiError, AuthError
from dropbox.files import WriteMode
from pathlib import Path

# Add shared helpers
sys.path.insert(0, str(Path(__file__).parent))
from output_helper import get_output_path

# Force unbuffered output
sys.stdout = os.fdopen(sys.stdout.fileno(), 'w', buffering=1)
sys.stderr = os.fdopen(sys.stderr.fileno(), 'w', buffering=1)

CONFIG_PATH = Path("config/config.json")


def load_config():
    if not CONFIG_PATH.exists():
        print("❌ Error: config/config.json not found")
        sys.exit(1)
    
    with open(CONFIG_PATH) as f:
        return json.load(f)


def generate_hashtags(topic: str, video_type: str) -> str:
    """Generate topic-based hashtags."""
    # Extract keywords from topic (words 4+ letters, lowercase, no special chars)
    words = re.findall(r'\b[a-zA-Z]{4,}\b', topic.lower())
    
    # Skip common words
    skip_words = {'through', 'about', 'with', 'from', 'into', 'that', 'this', 
                  'have', 'will', 'your', 'their', 'what', 'when', 'where', 'which'}
    keywords = [w for w in words[:5] if w not in skip_words]
    
    topic_tags = ' '.join(f'#{w}' for w in keywords)
    
    # Base hashtags depending on video type
    if video_type == 'full':
        return f"{topic_tags} #education #learning #science #stem #edutok #musicvideo"
    else:
        return f"{topic_tags} #shorts #education #learning #science #stem #edutok"


def generate_caption(topic: str, video_type: str, youtube_channel: str = "@learningsciencemusic") -> str:
    """Generate caption based on video type."""
    hashtags = generate_hashtags(topic, video_type)
    
    if video_type == 'full':
        return f"""Learn about {topic} through music!

View full version on YouTube {youtube_channel}

{hashtags}"""
    elif video_type == 'short_hook':
        return f"""{topic}

View full video on YouTube {youtube_channel}

{hashtags}"""
    elif video_type == 'short_educational':
        return f"""{topic} - Key concept explained!

Watch the full version on YouTube {youtube_channel}

{hashtags}"""
    else:
        return f"""Learn about {topic}!

{hashtags}"""


def get_topic_from_run(run_dir: Path) -> str:
    """Extract topic from research.json or fallback to idea.txt."""
    research_file = run_dir / "research.json"
    if research_file.exists():
        try:
            with open(research_file) as f:
                data = json.load(f)
                topic = data.get('video_title', '')
                if topic:
                    return topic
        except Exception:
            pass
    
    # Fallback to idea.txt
    idea_file = Path("input/idea.txt")
    if idea_file.exists():
        idea = idea_file.read_text().strip()
        # Extract topic (before "Tone:" if present)
        if "Tone:" in idea:
            return idea.split("Tone:")[0].strip().rstrip('.')
        return idea.split('.')[0].strip()
    
    return "Educational Video"


def get_video_path_from_type(run_dir: Path, video_type: str) -> Path:
    """Get video file path based on type."""
    type_to_file = {
        'full': 'full.mp4',
        'short_hook': 'short_hook.mp4',
        'short_educational': 'short_educational.mp4'
    }
    filename = type_to_file.get(video_type, 'full.mp4')
    return run_dir / filename


def upload_to_dropbox(file_path: Path, access_token: str, destination_path: str) -> str:
    """Uploads a file to Dropbox and returns a shared public link."""
    print(f"  Uploading {file_path.name} to Dropbox at {destination_path}...")
    
    try:
        dbx = dropbox.Dropbox(access_token)
        
        with open(file_path, 'rb') as f:
            dbx.files_upload(
                f.read(), 
                destination_path, 
                mode=WriteMode('overwrite')
            )
            
        print("  ✓ Upload successful")
        
        # Create shared link
        try:
            link_metadata = dbx.sharing_create_shared_link_with_settings(destination_path)
            url = link_metadata.url
        except ApiError as e:
            if e.error.is_shared_link_already_exists():
                links = dbx.sharing_list_shared_links(path=destination_path).links
                url = links[0].url
            else:
                raise e
        
        # Modify URL to be a direct download link
        # Dropbox links end with ?dl=0 (preview), change to ?dl=1 for direct download
        direct_url = url.replace("?dl=0", "?dl=1").replace("&dl=0", "&dl=1")
        print(f"  ✓ Direct download link: {direct_url}")
        return direct_url
        
    except AuthError:
        print("❌ Error: Invalid Dropbox access token")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error uploading to Dropbox: {e}")
        sys.exit(1)


def trigger_zapier(webhook_url: str, video_url: str, caption: str):
    """Triggers Zapier webhook with video URL and caption."""
    print(f"  Triggering Zapier webhook...")
    
    payload = {
        "text": caption,
        "video_url": video_url
    }
    
    try:
        response = requests.post(webhook_url, json=payload)
        response.raise_for_status()
        print(f"✅ Successfully triggered Zapier: {response.text}")
        return True
    except Exception as e:
        print(f"❌ Error triggering Zapier: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description='Upload video to TikTok via Dropbox + Zapier')
    parser.add_argument('video_path', nargs='?', help='Direct path to video file')
    parser.add_argument('caption', nargs='?', help='Caption for the video')
    parser.add_argument('--run', help='Run timestamp (e.g., 20251207_080423)')
    parser.add_argument('--type', dest='video_type', default='full',
                        choices=['full', 'short_hook', 'short_educational'],
                        help='Video type to upload')
    
    args = parser.parse_args()
    
    # Determine video path and caption
    if args.run:
        # Pipeline mode: use --run and --type
        run_dir = Path(f"outputs/runs/{args.run}")
        if not run_dir.exists():
            # Try current symlink
            run_dir = Path("outputs/current")
            if not run_dir.exists():
                print(f"❌ Error: Run directory not found: outputs/runs/{args.run}")
                sys.exit(1)
        
        video_path = get_video_path_from_type(run_dir, args.video_type)
        topic = get_topic_from_run(run_dir)
        
        # Load YouTube channel from automation config
        automation_config = Path("automation/config/automation_config.json")
        youtube_channel = "@learningsciencemusic"
        if automation_config.exists():
            try:
                with open(automation_config) as f:
                    auto_cfg = json.load(f)
                    youtube_channel = auto_cfg.get('youtube', {}).get('channel_handle', youtube_channel)
            except Exception:
                pass
        
        caption = generate_caption(topic, args.video_type, youtube_channel)
        print(f"📤 Uploading {args.video_type} to TikTok via Zapier...")
        print(f"  Topic: {topic}")
    elif args.video_path:
        # Direct mode: use positional arguments
        video_path = Path(args.video_path)
        caption = args.caption or "Check out this amazing video! 🎥"
    else:
        parser.print_help()
        sys.exit(1)
    
    if not video_path.exists():
        print(f"❌ Error: Video file not found: {video_path}")
        sys.exit(1)

    config = load_config()
    
    # Check for Dropbox Config (nested under "dropbox" key)
    dropbox_config = config.get("dropbox", {})
    dropbox_token = dropbox_config.get("access_token")
            
    if not dropbox_token or dropbox_token == "YOUR_ACCESS_TOKEN_HERE":
        print("❌ Error: 'dropbox.access_token' missing in config/config.json")
        print("   Generate a token at: https://www.dropbox.com/developers/apps")
        sys.exit(1)
        
    # Check for Zapier Config (nested under "zapier" key)
    zapier_config = config.get("zapier", {})
    zapier_webhook = zapier_config.get("webhook_url")
        
    if not zapier_webhook:
        print("❌ Error: 'zapier.webhook_url' missing in config/config.json")
        sys.exit(1)

    # For app-scoped folders, root "/" is the app folder (Apps/Upload_Youtube_Vids/)
    destination_path = f"/{video_path.name}"
    
    public_url = upload_to_dropbox(video_path, dropbox_token, destination_path)
    success = trigger_zapier(zapier_webhook, public_url, caption)
    
    if not success:
        sys.exit(1)


if __name__ == "__main__":
    main()
