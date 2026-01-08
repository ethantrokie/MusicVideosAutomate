#!/usr/bin/env python3 -u
"""
Uploads video to Dropbox and triggers Zapier via email for TikTok posting.

Usage:
  python agents/6_upload_dropbox_zapier.py <video_path> [caption]
  python agents/6_upload_dropbox_zapier.py --run=TIMESTAMP --type=full|short_hook|short_educational|short_intro
"""

import os
import sys
import json
import argparse
import re
import smtplib
from email.mime.text import MIMEText
import dropbox
from dropbox.exceptions import ApiError, AuthError
from dropbox.files import WriteMode
from pathlib import Path

# Email configuration for Zapier
SENDER_EMAIL = "ethantrokie@gmail.com"
ZAPIER_EMAIL = "tiktok.rhch0u@zapiermail.com"
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587

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
    elif video_type == 'short_intro':
        return f"""{topic} - First minute preview!

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
        'short_educational': 'short_educational.mp4',
        'short_intro': 'short_intro.mp4'
    }
    filename = type_to_file.get(video_type, 'full.mp4')
    return run_dir / filename


def get_valid_access_token(config: dict) -> str:
    """Get a valid access token, refreshing if necessary."""
    dropbox_config = config.get('dropbox', {})

    # Check if we have a refresh token
    refresh_token = dropbox_config.get('refresh_token')
    app_key = dropbox_config.get('app_key')
    app_secret = dropbox_config.get('app_secret')

    if refresh_token and app_key and app_secret:
        # Use refresh token to get a fresh access token
        try:
            dbx = dropbox.Dropbox(
                oauth2_refresh_token=refresh_token,
                app_key=app_key,
                app_secret=app_secret
            )
            # Test the connection and get current token
            dbx.users_get_current_account()
            return dbx._oauth2_access_token
        except Exception as e:
            print(f"⚠️ Warning: Failed to use refresh token: {e}")
            print("   Falling back to access_token from config")

    # Fallback to direct access token (short-lived)
    access_token = dropbox_config.get('access_token', '')
    if not access_token:
        raise ValueError("No Dropbox access_token or refresh_token found in config")

    return access_token


def upload_to_dropbox(file_path: Path, config: dict, destination_path: str) -> str:
    """Uploads a file to Dropbox and returns a shared public link."""
    print(f"  Uploading {file_path.name} to Dropbox at {destination_path}...")

    try:
        access_token = get_valid_access_token(config)
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


def get_gmail_app_password(config: dict) -> str:
    """Get Gmail app password from environment or config."""
    # Try environment variable first
    password = os.environ.get("GMAIL_APP_PASSWORD")
    if password:
        return password.replace(" ", "")

    # Try config file
    password = config.get("gmail", {}).get("app_password", "")
    if password:
        return password.replace(" ", "")

    return ""


def send_to_zapier_email(video_url: str, caption: str, config: dict) -> bool:
    """Send video URL and caption to Zapier via email."""
    print(f"  Sending to Zapier via email...")

    app_password = get_gmail_app_password(config)
    if not app_password:
        print("❌ Error: Gmail App Password not found.")
        print("   Set GMAIL_APP_PASSWORD env var or add gmail.app_password to config.json")
        return False

    # Subject = first line of caption (title/description)
    # Body = video URL
    subject = caption.split('\n')[0].strip()

    msg = MIMEText(video_url, 'plain')
    msg['Subject'] = subject
    msg['From'] = SENDER_EMAIL
    msg['To'] = ZAPIER_EMAIL

    try:
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(SENDER_EMAIL, app_password)
        server.sendmail(SENDER_EMAIL, ZAPIER_EMAIL, msg.as_string())
        server.quit()

        print(f"✅ Successfully sent to Zapier via email")
        print(f"   Subject: {subject}")
        print(f"   To: {ZAPIER_EMAIL}")
        return True

    except smtplib.SMTPAuthenticationError:
        print("❌ Error: Gmail authentication failed. Check app password.")
        return False
    except Exception as e:
        print(f"❌ Error sending email: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description='Upload video to TikTok via Dropbox + Zapier')
    parser.add_argument('video_path', nargs='?', help='Direct path to video file')
    parser.add_argument('caption', nargs='?', help='Caption for the video')
    parser.add_argument('--run', help='Run timestamp (e.g., 20251207_080423)')
    parser.add_argument('--type', dest='video_type', default='full',
                        choices=['full', 'short_hook', 'short_educational', 'short_intro'],
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

    # Check for Dropbox Config (either refresh_token or access_token)
    dropbox_config = config.get("dropbox", {})
    has_auth = dropbox_config.get("refresh_token") or dropbox_config.get("access_token")

    if not has_auth:
        print("❌ Error: No Dropbox authentication found in config/config.json")
        print("   Run: python automation/dropbox_auth_helper.py")
        print("   Or add 'dropbox.access_token' manually")
        sys.exit(1)

    # Check for Gmail config (needed for email to Zapier)
    if not get_gmail_app_password(config):
        print("❌ Error: Gmail App Password not found in config/config.json")
        print("   Add 'gmail.app_password' to config or set GMAIL_APP_PASSWORD env var")
        sys.exit(1)

    # For app-scoped folders, root "/" is the app folder (Apps/Upload_Youtube_Vids/)
    destination_path = f"/{video_path.name}"

    public_url = upload_to_dropbox(video_path, config, destination_path)
    success = send_to_zapier_email(public_url, caption, config)

    if not success:
        sys.exit(1)


if __name__ == "__main__":
    main()
