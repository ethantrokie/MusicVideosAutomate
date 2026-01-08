#!/usr/bin/env python3
"""
Test script: Send TikTok upload payload via email instead of Zapier webhook.

Sends the same JSON payload that would go to Zapier, but via email.
From: etthantrokie@gmail.com
To: tiktok.rhch0u@zapiermail.com

Usage:
  python test_email_to_zapier.py --run=TIMESTAMP --type=short_intro
  python test_email_to_zapier.py --video=/path/to/video.mp4 --caption="Test caption"

Note: Requires Gmail App Password. Set GMAIL_APP_PASSWORD environment variable
      or add to config/config.json under "gmail.app_password"
"""

import os
import sys
import json
import argparse
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pathlib import Path

# Add agents directory for imports
sys.path.insert(0, str(Path(__file__).parent / "agents"))

CONFIG_PATH = Path("config/config.json")

# Email configuration
SENDER_EMAIL = "ethantrokie@gmail.com"
RECIPIENT_EMAIL = "tiktok.rhch0u@zapiermail.com"
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587


def load_config():
    """Load config file."""
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH) as f:
            return json.load(f)
    return {}


def get_gmail_app_password():
    """Get Gmail app password from environment or config."""
    # Try environment variable first
    password = os.environ.get("GMAIL_APP_PASSWORD")
    if password:
        # Remove spaces (app passwords are sometimes formatted with spaces)
        return password.replace(" ", "")

    # Try config file
    config = load_config()
    password = config.get("gmail", {}).get("app_password")
    if password:
        # Remove spaces (app passwords are sometimes formatted with spaces)
        return password.replace(" ", "")

    return None


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
        if "Tone:" in idea:
            return idea.split("Tone:")[0].strip().rstrip('.')
        return idea.split('.')[0].strip()

    return "Educational Video"


def generate_caption(topic: str, video_type: str, youtube_channel: str = "@learningsciencemusic") -> str:
    """Generate caption based on video type (same as 6_upload_dropbox_zapier.py)."""
    import re

    # Generate hashtags
    words = re.findall(r'\b[a-zA-Z]{4,}\b', topic.lower())
    skip_words = {'through', 'about', 'with', 'from', 'into', 'that', 'this',
                  'have', 'will', 'your', 'their', 'what', 'when', 'where', 'which'}
    keywords = [w for w in words[:5] if w not in skip_words]
    topic_tags = ' '.join(f'#{w}' for w in keywords)

    if video_type == 'full':
        hashtags = f"{topic_tags} #education #learning #science #stem #edutok #musicvideo"
        return f"""Learn about {topic} through music!

View full version on YouTube {youtube_channel}

{hashtags}"""
    else:
        hashtags = f"{topic_tags} #shorts #education #learning #science #stem #edutok"

        if video_type == 'short_hook':
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


def send_email(payload: dict, app_password: str) -> bool:
    """Send payload as email."""
    print(f"  Sending email...")
    print(f"    From: {SENDER_EMAIL}")
    print(f"    To: {RECIPIENT_EMAIL}")

    # Create email
    # Subject = first line of caption (title/description)
    # Body = video URL
    caption = payload.get('text', 'TikTok Upload')
    video_url = payload.get('video_url', '')

    # Use first line as subject (email subjects can't have newlines)
    subject = caption.split('\n')[0].strip()

    msg = MIMEText(video_url, 'plain')
    msg['Subject'] = subject
    msg['From'] = SENDER_EMAIL
    msg['To'] = RECIPIENT_EMAIL

    try:
        # Connect to Gmail SMTP
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(SENDER_EMAIL, app_password)

        # Send email
        server.sendmail(SENDER_EMAIL, RECIPIENT_EMAIL, msg.as_string())
        server.quit()

        print(f"  ✅ Email sent successfully!")
        return True

    except smtplib.SMTPAuthenticationError:
        print(f"  ❌ Authentication failed. Check your Gmail App Password.")
        print(f"     Generate one at: https://myaccount.google.com/apppasswords")
        return False
    except Exception as e:
        print(f"  ❌ Failed to send email: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description='Test: Send TikTok payload via email instead of Zapier')
    parser.add_argument('--video', help='Direct path to video file')
    parser.add_argument('--caption', help='Caption for the video')
    parser.add_argument('--run', help='Run timestamp (e.g., 20251207_080423)')
    parser.add_argument('--type', dest='video_type', default='short_intro',
                        choices=['full', 'short_hook', 'short_educational', 'short_intro'],
                        help='Video type')
    parser.add_argument('--dry-run', action='store_true',
                        help='Show payload without sending email')

    args = parser.parse_args()

    # Get Gmail app password
    app_password = get_gmail_app_password()
    if not app_password and not args.dry_run:
        print("❌ Error: Gmail App Password not found.")
        print("")
        print("Set it via one of these methods:")
        print("  1. Environment variable: export GMAIL_APP_PASSWORD='your-app-password'")
        print("  2. Config file: Add to config/config.json:")
        print('     "gmail": { "app_password": "your-app-password" }')
        print("")
        print("Generate an App Password at: https://myaccount.google.com/apppasswords")
        print("  (Requires 2-Step Verification enabled on your Google account)")
        sys.exit(1)

    # Build the payload (same as 6_upload_dropbox_zapier.py)
    if args.run:
        # Pipeline mode
        run_dir = Path(f"outputs/runs/{args.run}")
        if not run_dir.exists():
            run_dir = Path("outputs/current")
            if not run_dir.exists():
                print(f"❌ Error: Run directory not found")
                sys.exit(1)

        # Get video path
        type_to_file = {
            'full': 'full.mp4',
            'short_hook': 'short_hook.mp4',
            'short_educational': 'short_educational.mp4',
            'short_intro': 'short_intro.mp4'
        }
        video_path = run_dir / type_to_file.get(args.video_type, 'short_intro.mp4')

        if not video_path.exists():
            print(f"❌ Error: Video not found: {video_path}")
            sys.exit(1)

        topic = get_topic_from_run(run_dir)
        caption = generate_caption(topic, args.video_type)

        # For this test, we'll use a placeholder URL since we're not uploading to Dropbox
        video_url = f"[TEST] Local file: {video_path}"

        print(f"📧 Test Email to Zapier")
        print(f"  Run: {args.run}")
        print(f"  Type: {args.video_type}")
        print(f"  Topic: {topic}")

    elif args.video:
        video_path = Path(args.video)
        if not video_path.exists():
            print(f"❌ Error: Video not found: {video_path}")
            sys.exit(1)

        caption = args.caption or "Test video upload"
        video_url = f"[TEST] Local file: {video_path}"

        print(f"📧 Test Email to Zapier")
        print(f"  Video: {video_path}")

    else:
        # Demo mode with sample data
        caption = "This is a test caption for TikTok #test #demo"
        video_url = "[TEST] https://example.com/sample-video.mp4"

        print(f"📧 Test Email to Zapier (Demo Mode)")

    # Build payload (same structure as Zapier webhook)
    payload = {
        "text": caption,
        "video_url": video_url
    }

    print("")
    print("📦 Payload:")
    print(json.dumps(payload, indent=2))
    print("")

    if args.dry_run:
        print("🔍 Dry run - email not sent")
        return

    # Send email
    success = send_email(payload, app_password)

    if success:
        print("")
        print(f"✅ Test complete! Check {RECIPIENT_EMAIL} for the email.")
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
