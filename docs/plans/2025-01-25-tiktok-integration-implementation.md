# TikTok Integration Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add TikTok upload functionality to the automated video system, enabling daily posts to both YouTube and TikTok platforms with cross-platform linking and independent error handling.

**Architecture:** Create Python uploader using TikTok Content Posting API with OAuth 2.0, wrap with bash script for metadata generation, integrate into existing pipeline with independent error handling, and update cross-linking to include both platforms.

**Tech Stack:** Python 3.9+, TikTok Content Posting API, OAuth 2.0, bash scripting, jq for JSON parsing, requests library for HTTP

---

## Task 1: Add Python Dependencies

**Files:**
- Modify: `requirements.txt`

**Step 1: Add requests library to requirements.txt**

```bash
echo "requests>=2.31.0" >> requirements.txt
```

**Step 2: Install dependencies**

```bash
./venv/bin/pip install -r requirements.txt
```

Expected output:
```
Successfully installed requests-2.31.0
```

**Step 3: Verify installation**

```bash
./venv/bin/python3 -c "import requests; print(f'requests {requests.__version__}')"
```

Expected output:
```
requests 2.31.0
```

**Step 4: Commit**

```bash
git add requirements.txt
git commit -m "deps: add requests library for TikTok API integration"
```

---

## Task 2: Create TikTok Credentials Template

**Files:**
- Create: `config/tiktok_credentials.json.template`

**Step 1: Create credentials template file**

```bash
cat > config/tiktok_credentials.json.template << 'EOF'
{
  "client_key": "YOUR_CLIENT_KEY_HERE",
  "client_secret": "YOUR_CLIENT_SECRET_HERE",
  "redirect_uri": "http://localhost:8080/callback"
}
EOF
```

**Step 2: Add .gitignore entry for actual credentials**

```bash
echo "config/tiktok_credentials.json" >> .gitignore
echo "config/tiktok_token.pickle" >> .gitignore
```

**Step 3: Verify gitignore**

```bash
git check-ignore config/tiktok_credentials.json config/tiktok_token.pickle
```

Expected output:
```
config/tiktok_credentials.json
config/tiktok_token.pickle
```

**Step 4: Commit**

```bash
git add config/tiktok_credentials.json.template .gitignore
git commit -m "config: add TikTok credentials template and gitignore entries"
```

---

## Task 3: Create TikTok Uploader - OAuth Module

**Files:**
- Create: `automation/tiktok_uploader.py`

**Step 1: Create file with OAuth authentication logic**

```python
#!/usr/bin/env python3
"""
TikTok video uploader using Content Posting API.
Handles OAuth 2.0 authentication and video uploads with chunked transfer.
"""

import json
import pickle
import os
import sys
import time
import webbrowser
from urllib.parse import urlencode, parse_qs, urlparse
from http.server import HTTPServer, BaseHTTPRequestHandler
import requests

# Configuration paths
CREDENTIALS_PATH = "config/tiktok_credentials.json"
TOKEN_PATH = "config/tiktok_token.pickle"

# TikTok API endpoints
BASE_URL = "https://open.tiktokapis.com"
AUTH_URL = "https://www.tiktok.com/v2/auth/authorize/"
TOKEN_URL = f"{BASE_URL}/v2/oauth/token/"


class OAuthCallbackHandler(BaseHTTPRequestHandler):
    """Handle OAuth callback from TikTok."""

    def do_GET(self):
        """Capture authorization code from callback."""
        query = parse_qs(urlparse(self.path).query)

        if 'code' in query:
            self.server.auth_code = query['code'][0]
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(b'<html><body><h1>Authorization successful!</h1><p>You can close this window.</p></body></html>')
        else:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b'<html><body><h1>Authorization failed</h1></body></html>')

    def log_message(self, format, *args):
        """Suppress log messages."""
        pass


class TikTokAuth:
    """Handle TikTok OAuth 2.0 authentication."""

    def __init__(self, credentials_path=CREDENTIALS_PATH, token_path=TOKEN_PATH):
        """Initialize with credentials and token paths."""
        self.credentials_path = credentials_path
        self.token_path = token_path
        self.credentials = self._load_credentials()
        self.token = self._load_token()

    def _load_credentials(self):
        """Load OAuth credentials from JSON file."""
        if not os.path.exists(self.credentials_path):
            print(f"❌ Error: Credentials file not found: {self.credentials_path}")
            print(f"Please create it from the template: config/tiktok_credentials.json.template")
            sys.exit(1)

        with open(self.credentials_path, 'r') as f:
            return json.load(f)

    def _load_token(self):
        """Load cached OAuth token if available."""
        if os.path.exists(self.token_path):
            try:
                with open(self.token_path, 'rb') as f:
                    return pickle.load(f)
            except Exception as e:
                print(f"⚠️  Warning: Failed to load token cache: {e}")
                return None
        return None

    def _save_token(self, token):
        """Save OAuth token to cache."""
        with open(self.token_path, 'wb') as f:
            pickle.dump(token, f)
        self.token = token

    def get_authorization_url(self):
        """Generate authorization URL for user consent."""
        params = {
            'client_key': self.credentials['client_key'],
            'scope': 'video.publish',
            'response_type': 'code',
            'redirect_uri': self.credentials['redirect_uri']
        }
        return f"{AUTH_URL}?{urlencode(params)}"

    def run_oauth_flow(self):
        """Run complete OAuth flow with local callback server."""
        print("🔐 Starting TikTok OAuth authentication...")

        # Open browser for user consent
        auth_url = self.get_authorization_url()
        print(f"Opening browser for authorization: {auth_url}")
        webbrowser.open(auth_url)

        # Start local server to capture callback
        server = HTTPServer(('localhost', 8080), OAuthCallbackHandler)
        server.auth_code = None

        print("Waiting for authorization callback...")
        server.handle_request()

        if not server.auth_code:
            print("❌ Authorization failed: No code received")
            sys.exit(1)

        print("✅ Authorization code received")

        # Exchange code for access token
        token_data = {
            'client_key': self.credentials['client_key'],
            'client_secret': self.credentials['client_secret'],
            'code': server.auth_code,
            'grant_type': 'authorization_code',
            'redirect_uri': self.credentials['redirect_uri']
        }

        response = requests.post(TOKEN_URL, json=token_data)

        if response.status_code != 200:
            print(f"❌ Token exchange failed: {response.status_code}")
            print(response.text)
            sys.exit(1)

        token = response.json()
        self._save_token(token)

        print("✅ OAuth authentication complete!")
        return token

    def refresh_token(self):
        """Refresh expired access token."""
        if not self.token or 'refresh_token' not in self.token:
            return self.run_oauth_flow()

        print("🔄 Refreshing access token...")

        token_data = {
            'client_key': self.credentials['client_key'],
            'client_secret': self.credentials['client_secret'],
            'grant_type': 'refresh_token',
            'refresh_token': self.token['refresh_token']
        }

        response = requests.post(TOKEN_URL, json=token_data)

        if response.status_code != 200:
            print(f"⚠️  Token refresh failed, re-authenticating...")
            return self.run_oauth_flow()

        token = response.json()
        self._save_token(token)

        print("✅ Token refreshed")
        return token

    def get_access_token(self):
        """Get valid access token, refreshing if needed."""
        if not self.token:
            return self.run_oauth_flow()['access_token']

        # Check if token is expired (assuming 24h lifetime)
        if 'expires_in' in self.token:
            # In production, should track actual expiry time
            # For now, refresh proactively
            pass

        return self.token['access_token']


if __name__ == "__main__":
    # Test OAuth flow
    if len(sys.argv) > 1 and sys.argv[1] == '--auth':
        auth = TikTokAuth()
        token = auth.run_oauth_flow()
        print(f"\n✅ Authentication successful!")
        print(f"Access token: {token['access_token'][:20]}...")
    else:
        print("Usage: ./automation/tiktok_uploader.py --auth")
        print("This will authenticate with TikTok and save credentials.")
```

**Step 2: Make executable**

```bash
chmod +x automation/tiktok_uploader.py
```

**Step 3: Verify syntax**

```bash
./venv/bin/python3 -m py_compile automation/tiktok_uploader.py
```

Expected: No output (successful compilation)

**Step 4: Commit**

```bash
git add automation/tiktok_uploader.py
git commit -m "feat: add TikTok OAuth 2.0 authentication module"
```

---

## Task 4: Add TikTok Uploader - Video Upload Module

**Files:**
- Modify: `automation/tiktok_uploader.py` (add video upload functionality)

**Step 1: Add video upload class and methods**

Add after the `TikTokAuth` class (before `if __name__ == "__main__":`):

```python

class TikTokUploader:
    """Handle TikTok video uploads."""

    def __init__(self):
        """Initialize with authentication."""
        self.auth = TikTokAuth()
        self.access_token = self.auth.get_access_token()

    def _get_headers(self):
        """Get headers for API requests."""
        return {
            'Authorization': f'Bearer {self.access_token}',
            'Content-Type': 'application/json; charset=UTF-8'
        }

    def init_upload(self, video_path, title, caption, privacy_level='public_to_everyone'):
        """
        Initialize video upload and get upload URL.

        Args:
            video_path: Path to video file
            title: Video title
            caption: Video caption with hashtags
            privacy_level: public_to_everyone, mutual_follow_friends, or self_only

        Returns:
            dict with publish_id and upload_url
        """
        # Get video file size
        video_size = os.path.getsize(video_path)

        # Initialize direct post
        init_data = {
            'post_info': {
                'title': title,
                'privacy_level': privacy_level,
                'disable_duet': False,
                'disable_comment': False,
                'disable_stitch': False,
                'video_cover_timestamp_ms': 1000
            },
            'source_info': {
                'source': 'FILE_UPLOAD',
                'video_size': video_size,
                'chunk_size': min(video_size, 10 * 1024 * 1024),  # 10 MB chunks
                'total_chunk_count': (video_size + 10 * 1024 * 1024 - 1) // (10 * 1024 * 1024)
            },
            'post_mode': 'DIRECT_POST',
            'media_type': 'VIDEO'
        }

        # Add caption if provided
        if caption:
            init_data['post_info']['description'] = caption

        response = requests.post(
            f"{BASE_URL}/v2/post/publish/video/init/",
            headers=self._get_headers(),
            json=init_data
        )

        if response.status_code != 200:
            print(f"❌ Upload initialization failed: {response.status_code}")
            print(response.text)
            # Try refreshing token once
            self.access_token = self.auth.refresh_token()['access_token']
            response = requests.post(
                f"{BASE_URL}/v2/post/publish/video/init/",
                headers=self._get_headers(),
                json=init_data
            )
            if response.status_code != 200:
                raise Exception(f"Upload init failed: {response.text}")

        result = response.json()
        return result['data']

    def upload_video_chunks(self, video_path, upload_url):
        """
        Upload video in chunks to TikTok.

        Args:
            video_path: Path to video file
            upload_url: Upload URL from init_upload
        """
        chunk_size = 10 * 1024 * 1024  # 10 MB
        video_size = os.path.getsize(video_path)

        print(f"📤 Uploading video: {os.path.basename(video_path)} ({video_size / (1024*1024):.1f} MB)")

        with open(video_path, 'rb') as f:
            uploaded = 0
            chunk_index = 0

            while uploaded < video_size:
                chunk = f.read(chunk_size)
                if not chunk:
                    break

                chunk_index += 1
                chunk_start = uploaded
                chunk_end = uploaded + len(chunk) - 1

                headers = {
                    'Content-Range': f'bytes {chunk_start}-{chunk_end}/{video_size}',
                    'Content-Length': str(len(chunk)),
                    'Content-Type': 'video/mp4'
                }

                response = requests.put(upload_url, headers=headers, data=chunk)

                if response.status_code not in (200, 201, 202):
                    raise Exception(f"Chunk upload failed: {response.status_code} - {response.text}")

                uploaded += len(chunk)
                progress = (uploaded / video_size) * 100
                print(f"  Chunk {chunk_index}: {progress:.1f}% complete")

        print("✅ Video upload complete")

    def check_status(self, publish_id, max_attempts=30, delay=10):
        """
        Poll upload status until processing complete.

        Args:
            publish_id: ID from init_upload
            max_attempts: Maximum polling attempts
            delay: Seconds between attempts

        Returns:
            Video ID once published
        """
        print(f"⏳ Checking upload status (publish_id: {publish_id})...")

        for attempt in range(max_attempts):
            response = requests.post(
                f"{BASE_URL}/v2/post/publish/status/fetch/",
                headers=self._get_headers(),
                json={'publish_id': publish_id}
            )

            if response.status_code != 200:
                print(f"⚠️  Status check failed: {response.status_code}")
                time.sleep(delay)
                continue

            result = response.json()
            status = result['data']['status']

            if status == 'PUBLISH_COMPLETE':
                video_id = result['data'].get('video_id') or result['data'].get('id')
                print(f"✅ Video published successfully!")
                print(f"   Video ID: {video_id}")
                return video_id

            elif status == 'FAILED':
                fail_reason = result['data'].get('fail_reason', 'Unknown error')
                raise Exception(f"Video processing failed: {fail_reason}")

            else:
                print(f"   Status: {status} (attempt {attempt + 1}/{max_attempts})")
                time.sleep(delay)

        raise Exception("Upload status check timed out")

    def upload(self, video_path, title, caption, privacy_level='public_to_everyone'):
        """
        Complete video upload workflow.

        Args:
            video_path: Path to video file
            title: Video title
            caption: Video caption with hashtags
            privacy_level: Privacy setting

        Returns:
            Video ID
        """
        if not os.path.exists(video_path):
            raise FileNotFoundError(f"Video not found: {video_path}")

        # Step 1: Initialize upload
        init_result = self.init_upload(video_path, title, caption, privacy_level)
        publish_id = init_result['publish_id']
        upload_url = init_result['upload_url']

        print(f"📋 Upload initialized (ID: {publish_id})")

        # Step 2: Upload video chunks
        self.upload_video_chunks(video_path, upload_url)

        # Step 3: Poll status until complete
        video_id = self.check_status(publish_id)

        return video_id
```

**Step 2: Update main section for upload command**

Replace the existing `if __name__ == "__main__":` section with:

```python

def main():
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(description='Upload videos to TikTok')
    parser.add_argument('--auth', action='store_true', help='Authenticate with TikTok')
    parser.add_argument('--video', help='Path to video file')
    parser.add_argument('--title', help='Video title')
    parser.add_argument('--caption', help='Video caption with hashtags')
    parser.add_argument('--privacy', default='public_to_everyone',
                       choices=['public_to_everyone', 'mutual_follow_friends', 'self_only'],
                       help='Privacy level')

    args = parser.parse_args()

    if args.auth:
        # Run OAuth flow
        auth = TikTokAuth()
        token = auth.run_oauth_flow()
        print(f"\n✅ Authentication successful!")
        print(f"Access token saved to: {TOKEN_PATH}")

    elif args.video:
        # Upload video
        if not args.title or not args.caption:
            print("❌ Error: --title and --caption are required for upload")
            sys.exit(1)

        uploader = TikTokUploader()
        video_id = uploader.upload(args.video, args.title, args.caption, args.privacy)

        # Output video URL
        # Note: Need to get username from config
        print(f"\n✅ Upload complete!")
        print(f"Video ID: {video_id}")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
```

**Step 3: Verify syntax**

```bash
./venv/bin/python3 -m py_compile automation/tiktok_uploader.py
```

**Step 4: Commit**

```bash
git add automation/tiktok_uploader.py
git commit -m "feat: add TikTok video upload with chunked transfer"
```

---

## Task 5: Create upload_to_tiktok.sh Script

**Files:**
- Create: `upload_to_tiktok.sh`

**Step 1: Create bash wrapper script**

```bash
cat > upload_to_tiktok.sh << 'EOF'
#!/bin/bash
# Upload video to TikTok with metadata generation

set -e

# Default values
PRIVACY="public_to_everyone"
RUN_DIR=""
VIDEO_TYPE="full"  # full, short_hook

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --privacy=*)
            PRIVACY="${1#*=}"
            shift
            ;;
        --run=*)
            RUN_DIR="outputs/runs/${1#*=}"
            shift
            ;;
        --type=*)
            VIDEO_TYPE="${1#*=}"
            shift
            ;;
        --help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --run=TIMESTAMP        Upload specific run"
            echo "  --privacy=STATUS       Privacy: public_to_everyone, mutual_follow_friends, self_only"
            echo "  --type=TYPE           Video type: full, short_hook"
            echo "  --help                Show this help"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Function to generate topic-based hashtags (reuse YouTube logic)
generate_hashtags() {
    local topic=$1
    local video_type=$2

    # Extract keywords from topic (words 4+ letters, lowercase, no special chars)
    local keywords=$(echo "$topic" | tr '[:upper:]' '[:lower:]' | grep -oE '\b[a-z]{4,}\b' | head -5)

    # Build topic-specific hashtags
    local topic_tags=""
    for word in $keywords; do
        # Skip common words
        if [[ ! "$word" =~ ^(through|about|with|from|into|that|this|have|will|your|their)$ ]]; then
            topic_tags="${topic_tags}#${word} "
        fi
    done

    # Base hashtags depending on video type
    if [ "$video_type" = "full" ]; then
        echo "${topic_tags}#education #learning #science #stem #edutok #musicvideo"
    else
        echo "${topic_tags}#shorts #education #learning #science #stem #edutok"
    fi
}

# Function to generate metadata based on video type
generate_metadata() {
    local video_type=$1
    local topic=$2

    # Generate hashtags
    local hashtags=$(generate_hashtags "$topic" "$video_type")

    case $video_type in
        full)
            TITLE="${topic} - Full Educational Song"
            CAPTION="Learn about ${topic} through music!

View full video on YouTube @learningsciencemusic

${hashtags}"
            VIDEO_FILE="full.mp4"
            ;;
        short_hook)
            TITLE="${topic} 🎵"
            CAPTION="${topic}

View full video on YouTube @learningsciencemusic

${hashtags}"
            VIDEO_FILE="short_hook.mp4"
            ;;
        *)
            echo "❌ Error: Unknown video type: $video_type"
            exit 1
            ;;
    esac
}

# Use latest run if not specified
if [ -z "$RUN_DIR" ]; then
    RUN_DIR="outputs/current"
fi

# Get topic from idea.txt
TOPIC=$(head -1 input/idea.txt | cut -d'.' -f1)

# Generate metadata based on video type
generate_metadata "$VIDEO_TYPE" "$TOPIC"

VIDEO_PATH="$RUN_DIR/$VIDEO_FILE"

if [ ! -f "$VIDEO_PATH" ]; then
    echo "❌ Error: Video not found at $VIDEO_PATH"
    exit 1
fi

echo "📤 Uploading to TikTok..."
echo "  Type: $VIDEO_TYPE"
echo "  Video: $VIDEO_PATH"
echo "  Title: $TITLE"
echo "  Privacy: $PRIVACY"

# Upload using Python helper
UPLOAD_OUTPUT=$(./venv/bin/python3 automation/tiktok_uploader.py \
    --video "$VIDEO_PATH" \
    --title "$TITLE" \
    --caption "$CAPTION" \
    --privacy "$PRIVACY" 2>&1)

echo "$UPLOAD_OUTPUT"

# Extract video ID from output
VIDEO_ID=$(echo "$UPLOAD_OUTPUT" | grep "Video ID:" | cut -d: -f2 | tr -d ' ')

if [ -n "$VIDEO_ID" ]; then
    # Save video ID to file for cross-linking
    echo "$VIDEO_ID" > "${RUN_DIR}/tiktok_id_${VIDEO_TYPE}.txt"

    # Load TikTok username from config
    CONFIG_FILE="automation/config/automation_config.json"
    if [ -f "$CONFIG_FILE" ]; then
        TIKTOK_USER=$(jq -r '.tiktok.username' "$CONFIG_FILE" 2>/dev/null || echo "@learningsciencemusic")
    else
        TIKTOK_USER="@learningsciencemusic"
    fi

    # Construct TikTok URL
    TIKTOK_URL="https://tiktok.com/${TIKTOK_USER}/video/${VIDEO_ID}"

    echo "  Video ID: $VIDEO_ID"
    echo "  URL: $TIKTOK_URL"
    echo "  Saved to: ${RUN_DIR}/tiktok_id_${VIDEO_TYPE}.txt"
fi

echo "✅ Upload complete!"
EOF
```

**Step 2: Make executable**

```bash
chmod +x upload_to_tiktok.sh
```

**Step 3: Verify script syntax**

```bash
bash -n upload_to_tiktok.sh
```

Expected: No output (successful syntax check)

**Step 4: Commit**

```bash
git add upload_to_tiktok.sh
git commit -m "feat: add TikTok upload bash wrapper with metadata generation"
```

---

## Task 6: Update automation_config.json

**Files:**
- Modify: `automation/config/automation_config.json`

**Step 1: Add TikTok configuration section**

Add the `tiktok` section after the `youtube` section (before `notifications`):

```json
  "tiktok": {
    "enabled": true,
    "username": "@learningsciencemusic",
    "privacy_status": "public_to_everyone",
    "credentials_path": "config/tiktok_credentials.json"
  },
```

Full context - the config should now look like:

```json
{
  "scheduling": {
    "daily_run_time": "09:00",
    "timezone": "America/Chicago",
    "weekly_analysis_day": "Sunday",
    "weekly_analysis_time": "10:00"
  },
  "youtube": {
    "channel_handle": "@learningsciencemusic",
    "privacy_status": "public",
    "default_category": "Education",
    "credentials_path": "config/youtube_credentials.json"
  },
  "tiktok": {
    "enabled": true,
    "username": "@learningsciencemusic",
    "privacy_status": "public_to_everyone",
    "credentials_path": "config/tiktok_credentials.json"
  },
  "notifications": {
    "phone": "914-844-4402",
    "notify_on_success": true,
    "notify_on_failure": true,
    "notify_on_weekly_report": true,
    "notify_on_pending_changes": true
  },
  "optimization": {
    "enabled": false,
    "auto_apply_high_confidence": true,
    "confidence_threshold": 0.8,
    "max_changes_per_week": 2
  },
  "topic_generation": {
    "avoid_repeat_days": 30,
    "categories": ["engineering", "biology", "computer science", "chemistry", "physics", "earth_science", "civil engineering"],
    "prefer_trending": false
  }
}
```

**Step 2: Validate JSON syntax**

```bash
jq . automation/config/automation_config.json > /dev/null
```

Expected: No output (valid JSON)

**Step 3: Verify TikTok config can be read**

```bash
jq -r '.tiktok.username' automation/config/automation_config.json
```

Expected output:
```
@learningsciencemusic
```

**Step 4: Commit**

```bash
git add automation/config/automation_config.json
git commit -m "config: add TikTok integration settings"
```

---

## Task 7: Modify pipeline.sh - Load TikTok Config

**Files:**
- Modify: `pipeline.sh` (lines 12-20, add TikTok config loading)

**Step 1: Update config loading section**

In `pipeline.sh`, find the config loading section (around line 12-20) and update it to also load TikTok settings:

```bash
# Load configuration
CONFIG_FILE="automation/config/automation_config.json"
if [ -f "$CONFIG_FILE" ]; then
    YOUTUBE_PRIVACY=$(jq -r '.youtube.privacy_status' "$CONFIG_FILE" 2>/dev/null || echo "unlisted")
    YOUTUBE_CHANNEL=$(jq -r '.youtube.channel_handle' "$CONFIG_FILE" 2>/dev/null || echo "")
    TIKTOK_ENABLED=$(jq -r '.tiktok.enabled' "$CONFIG_FILE" 2>/dev/null || echo "false")
    TIKTOK_PRIVACY=$(jq -r '.tiktok.privacy_status' "$CONFIG_FILE" 2>/dev/null || echo "public_to_everyone")
else
    YOUTUBE_PRIVACY="unlisted"
    YOUTUBE_CHANNEL=""
    TIKTOK_ENABLED="false"
    TIKTOK_PRIVACY="public_to_everyone"
fi
```

**Step 2: Verify config loading works**

```bash
bash -c 'CONFIG_FILE="automation/config/automation_config.json"; TIKTOK_ENABLED=$(jq -r ".tiktok.enabled" "$CONFIG_FILE"); echo "TikTok enabled: $TIKTOK_ENABLED"'
```

Expected output:
```
TikTok enabled: true
```

**Step 3: Commit**

```bash
git add pipeline.sh
git commit -m "feat: load TikTok configuration in pipeline"
```

---

## Task 8: Modify pipeline.sh Stage 8 - Add TikTok Uploads

**Files:**
- Modify: `pipeline.sh` (Stage 8, after YouTube uploads around line 560)

**Step 1: Add TikTok upload calls after YouTube uploads**

Find the YouTube upload section in Stage 8 (after the three `./upload_to_youtube.sh` calls), and add TikTok uploads:

```bash
    # TikTok uploads (independent error handling)
    if [ "$TIKTOK_ENABLED" = "true" ]; then
        echo ""
        echo "📤 Uploading to TikTok..."

        # Upload full video
        if [ -f "${RUN_DIR}/full.mp4" ]; then
            echo "  Uploading full video..."
            if ./upload_to_tiktok.sh --run="${RUN_TIMESTAMP}" --type=full --privacy="${TIKTOK_PRIVACY}"; then
                TIKTOK_FULL_ID=$(cat "${RUN_DIR}/tiktok_id_full.txt" 2>/dev/null || echo "")
                echo "  ✅ Full video uploaded (ID: $TIKTOK_FULL_ID)"
            else
                echo "  ⚠️  TikTok full video upload failed (continuing)"
            fi
        fi

        # Upload hook short
        if [ -f "${RUN_DIR}/short_hook.mp4" ]; then
            echo "  Uploading hook short..."
            if ./upload_to_tiktok.sh --run="${RUN_TIMESTAMP}" --type=short_hook --privacy="${TIKTOK_PRIVACY}"; then
                TIKTOK_HOOK_ID=$(cat "${RUN_DIR}/tiktok_id_short_hook.txt" 2>/dev/null || echo "")
                echo "  ✅ Hook short uploaded (ID: $TIKTOK_HOOK_ID)"
            else
                echo "  ⚠️  TikTok hook short upload failed (continuing)"
            fi
        fi

        echo "✅ TikTok uploads complete"
    else
        echo "ℹ️  TikTok uploads disabled in config"
    fi
```

**Step 2: Verify bash syntax**

```bash
bash -n pipeline.sh
```

Expected: No output (successful syntax check)

**Step 3: Commit**

```bash
git add pipeline.sh
git commit -m "feat: add TikTok uploads to pipeline Stage 8 with independent error handling"
```

---

## Task 9: Modify pipeline.sh Stage 9 - Update Cross-Linking

**Files:**
- Modify: `pipeline.sh` (Stage 9, around line 585)

**Step 1: Update cross-linking to include TikTok**

Find Stage 9 in pipeline.sh and update the cross-linking section to collect TikTok video IDs:

Replace the existing Stage 9 section with:

```bash
echo ""
echo "========================================="
echo "Stage 9/9: Cross-linking videos"
echo "========================================="
echo ""

# Collect all video IDs
declare -A YOUTUBE_IDS
declare -A TIKTOK_IDS

# YouTube IDs
if [ -f "${RUN_DIR}/video_id_full.txt" ]; then
    YOUTUBE_IDS[full]=$(cat "${RUN_DIR}/video_id_full.txt")
fi
if [ -f "${RUN_DIR}/video_id_short_hook.txt" ]; then
    YOUTUBE_IDS[short_hook]=$(cat "${RUN_DIR}/video_id_short_hook.txt")
fi
if [ -f "${RUN_DIR}/video_id_short_educational.txt" ]; then
    YOUTUBE_IDS[short_educational]=$(cat "${RUN_DIR}/video_id_short_educational.txt")
fi

# TikTok IDs
if [ -f "${RUN_DIR}/tiktok_id_full.txt" ]; then
    TIKTOK_IDS[full]=$(cat "${RUN_DIR}/tiktok_id_full.txt")
fi
if [ -f "${RUN_DIR}/tiktok_id_short_hook.txt" ]; then
    TIKTOK_IDS[short_hook]=$(cat "${RUN_DIR}/tiktok_id_short_hook.txt")
fi

# Create upload_results.json
cat > "${RUN_DIR}/upload_results.json" << EOF
{
  "youtube": {
    "full_video": {
      "id": "${YOUTUBE_IDS[full]:-}",
      "url": "https://youtube.com/watch?v=${YOUTUBE_IDS[full]:-}"
    },
    "hook_short": {
      "id": "${YOUTUBE_IDS[short_hook]:-}",
      "url": "https://youtube.com/shorts/${YOUTUBE_IDS[short_hook]:-}"
    },
    "educational_short": {
      "id": "${YOUTUBE_IDS[short_educational]:-}",
      "url": "https://youtube.com/shorts/${YOUTUBE_IDS[short_educational]:-}"
    }
  },
  "tiktok": {
    "full_video": {
      "id": "${TIKTOK_IDS[full]:-}",
      "url": "https://tiktok.com/@learningsciencemusic/video/${TIKTOK_IDS[full]:-}"
    },
    "hook_short": {
      "id": "${TIKTOK_IDS[short_hook]:-}",
      "url": "https://tiktok.com/@learningsciencemusic/video/${TIKTOK_IDS[short_hook]:-}"
    }
  }
}
EOF

echo "📝 Created upload_results.json with all video IDs"

# Call Python cross-linking agent if all YouTube videos uploaded
if [ -n "${YOUTUBE_IDS[full]}" ] && [ -n "${YOUTUBE_IDS[short_hook]}" ] && [ -n "${YOUTUBE_IDS[short_educational]}" ]; then
    echo "🔗 Cross-linking YouTube video descriptions..."
    if ./venv/bin/python3 agents/crosslink_videos.py --run="${RUN_TIMESTAMP}"; then
        echo "✅ YouTube cross-linking complete"
    else
        echo "⚠️  YouTube cross-linking failed (continuing)"
    fi
else
    echo "ℹ️  Skipping YouTube cross-linking (not all videos uploaded)"
fi

echo ""
echo "✅ Stage 9 complete!"
```

**Step 2: Verify bash syntax**

```bash
bash -n pipeline.sh
```

**Step 3: Test JSON generation with sample data**

```bash
# Test the JSON structure
cat << 'EOF' | bash
YOUTUBE_IDS=([full]="abc123" [short_hook]="def456" [short_educational]="ghi789")
TIKTOK_IDS=([full]="7123456789" [short_hook]="7987654321")

cat << INNER_EOF
{
  "youtube": {
    "full_video": {
      "id": "${YOUTUBE_IDS[full]:-}",
      "url": "https://youtube.com/watch?v=${YOUTUBE_IDS[full]:-}"
    }
  },
  "tiktok": {
    "full_video": {
      "id": "${TIKTOK_IDS[full]:-}",
      "url": "https://tiktok.com/@learningsciencemusic/video/${TIKTOK_IDS[full]:-}"
    }
  }
}
INNER_EOF
EOF
```

Verify the JSON output is valid

**Step 4: Commit**

```bash
git add pipeline.sh
git commit -m "feat: update Stage 9 cross-linking to include TikTok videos"
```

---

## Task 10: Update daily_pipeline.sh Notifications

**Files:**
- Modify: `automation/daily_pipeline.sh` (lines 67-88)

**Step 1: Update notification to include TikTok status**

Find the success notification section (around line 80-84) and update it:

```bash
            if [ -f "$UPLOAD_RESULTS" ]; then
                FULL_VIDEO_ID=$(jq -r '.youtube.full_video.id' "$UPLOAD_RESULTS" 2>/dev/null || echo "unknown")
                TIKTOK_FULL_ID=$(jq -r '.tiktok.full_video.id' "$UPLOAD_RESULTS" 2>/dev/null || echo "")
                TIKTOK_HOOK_ID=$(jq -r '.tiktok.hook_short.id' "$UPLOAD_RESULTS" 2>/dev/null || echo "")
            else
                # Fallback to log parsing
                FULL_VIDEO_ID=$(grep "Video uploaded:.*full" "$LOG_FILE" | head -1 | grep -oE 'watch\?v=([A-Za-z0-9_-]+)' | cut -d'=' -f2 || echo "unknown")
                TIKTOK_FULL_ID=""
                TIKTOK_HOOK_ID=""
            fi

            log "✅ Daily videos published successfully with cross-linking"

            if [ "$NOTIFY_SUCCESS" = "true" ]; then
                # Build notification message
                NOTIFICATION="✅ Daily videos published!
Topic: $TOPIC

YouTube:
- Full: https://youtube.com/watch?v=$FULL_VIDEO_ID
- 3 formats with cross-linking"

                # Add TikTok info if videos were uploaded
                if [ -n "$TIKTOK_FULL_ID" ] || [ -n "$TIKTOK_HOOK_ID" ]; then
                    NOTIFICATION="$NOTIFICATION

TikTok:"
                    if [ -n "$TIKTOK_FULL_ID" ]; then
                        NOTIFICATION="$NOTIFICATION
- Full: https://tiktok.com/@learningsciencemusic/video/$TIKTOK_FULL_ID"
                    fi
                    if [ -n "$TIKTOK_HOOK_ID" ]; then
                        NOTIFICATION="$NOTIFICATION
- Hook: https://tiktok.com/@learningsciencemusic/video/$TIKTOK_HOOK_ID"
                    fi
                fi

                NOTIFICATION="$NOTIFICATION

Status: $PRIVACY (multi-platform)"

                send_notification "$NOTIFICATION"
            fi
```

**Step 2: Verify bash syntax**

```bash
bash -n automation/daily_pipeline.sh
```

**Step 3: Test jq extraction**

```bash
# Create test upload_results.json
cat > /tmp/test_results.json << 'EOF'
{
  "youtube": {
    "full_video": {"id": "abc123", "url": "https://youtube.com/watch?v=abc123"}
  },
  "tiktok": {
    "full_video": {"id": "7123456789", "url": "https://tiktok.com/@user/video/7123456789"},
    "hook_short": {"id": "7987654321", "url": "https://tiktok.com/@user/video/7987654321"}
  }
}
EOF

# Test extraction
echo "YouTube ID: $(jq -r '.youtube.full_video.id' /tmp/test_results.json)"
echo "TikTok Full ID: $(jq -r '.tiktok.full_video.id' /tmp/test_results.json)"
echo "TikTok Hook ID: $(jq -r '.tiktok.hook_short.id' /tmp/test_results.json)"
```

Expected output:
```
YouTube ID: abc123
TikTok Full ID: 7123456789
TikTok Hook ID: 7987654321
```

**Step 4: Commit**

```bash
git add automation/daily_pipeline.sh
git commit -m "feat: update notifications to include TikTok upload status"
```

---

## Task 11: Create Setup Instructions

**Files:**
- Create: `docs/TIKTOK_SETUP.md`

**Step 1: Create setup documentation**

```bash
cat > docs/TIKTOK_SETUP.md << 'EOF'
# TikTok Integration Setup

## Prerequisites

1. **Create TikTok Developer Account**
   - Go to https://developers.tiktok.com/
   - Sign in with your TikTok account
   - Complete developer verification

2. **Register Application**
   - Navigate to "My Apps" → "Create App"
   - Fill in app details:
     - App name: "Learning Science Music Automation"
     - Category: "Education"
   - Save to get Client Key and Client Secret

3. **Request Content Posting API Access**
   - In app settings, go to "Add products"
   - Enable "Content Posting API"
   - Request scope: `video.publish`
   - Wait for approval (usually instant for unaudited apps)

4. **Configure OAuth Redirect**
   - In app settings, add redirect URI: `http://localhost:8080/callback`
   - Save changes

## Configuration

1. **Create credentials file:**

```bash
cp config/tiktok_credentials.json.template config/tiktok_credentials.json
```

2. **Edit config/tiktok_credentials.json:**

```json
{
  "client_key": "YOUR_CLIENT_KEY_HERE",
  "client_secret": "YOUR_CLIENT_SECRET_HERE",
  "redirect_uri": "http://localhost:8080/callback"
}
```

Replace `YOUR_CLIENT_KEY_HERE` and `YOUR_CLIENT_SECRET_HERE` with values from TikTok developer portal.

3. **Run OAuth authentication:**

```bash
./venv/bin/python3 automation/tiktok_uploader.py --auth
```

This will:
- Open browser for TikTok authorization
- Start local server on port 8080
- Exchange authorization code for access token
- Save token to `config/tiktok_token.pickle`

## Verify Setup

1. **Test authentication:**

```bash
./venv/bin/python3 automation/tiktok_uploader.py --auth
```

Should output: `✅ Authentication successful!`

2. **Test manual upload (optional):**

```bash
./upload_to_tiktok.sh --run=TIMESTAMP --type=full --privacy=public_to_everyone
```

Replace TIMESTAMP with an actual run directory.

## Important Notes

### Unaudited Apps Post as Private

**By default, videos from unaudited apps are posted as PRIVATE.**

To post public videos:
1. Submit app for TikTok audit review
2. In developer portal: "My Apps" → Your App → "Submit for Audit"
3. Provide app description and use case
4. Wait for approval (typically 1-2 weeks)

Until approved, all videos will be private regardless of privacy setting.

### Token Refresh

- TikTok access tokens typically expire after 24 hours
- The uploader automatically refreshes tokens when needed
- If refresh fails, will trigger new OAuth flow
- Check logs if authentication errors occur

### Testing Strategy

**Phase 1: Manual Testing**
1. Upload test video with privacy=self_only
2. Verify video appears in TikTok profile (private)
3. Check metadata, captions, hashtags

**Phase 2: Pipeline Integration**
1. Run full pipeline: `./pipeline.sh --express`
2. Verify both YouTube and TikTok uploads
3. Check upload_results.json contains both platforms

**Phase 3: Daily Automation**
1. Run daily pipeline: `./automation/daily_pipeline.sh`
2. Verify notifications include both platforms
3. Monitor for token refresh issues

## Troubleshooting

**"Authorization failed: No code received"**
- Check redirect URI matches exactly: `http://localhost:8080/callback`
- Verify port 8080 is not in use
- Try different browser

**"Upload initialization failed: 401"**
- Token expired, run: `./venv/bin/python3 automation/tiktok_uploader.py --auth`
- Verify credentials are correct

**"Videos are private even with privacy=public_to_everyone"**
- App is unaudited, submit for audit in developer portal
- Use privacy=self_only for testing until approval

**"Chunk upload failed"**
- Check video file size < 2GB
- Verify stable internet connection
- Retry upload

## Configuration Reference

**Privacy Levels:**
- `public_to_everyone` - Visible to all (requires audited app)
- `mutual_follow_friends` - Followers only
- `self_only` - Private

**Video Requirements:**
- Format: MP4 recommended
- Max size: 2GB
- Duration: 3 seconds - 10 minutes
- Aspect ratios: 16:9 (full), 9:16 (shorts)

## Support

For TikTok API issues, see:
- Documentation: https://developers.tiktok.com/doc/content-posting-api-get-started
- Developer forum: https://developers.tiktok.com/community
EOF
```

**Step 2: Commit**

```bash
git add docs/TIKTOK_SETUP.md
git commit -m "docs: add TikTok integration setup guide"
```

---

## Task 12: Update Main README

**Files:**
- Modify: `README.md` (add TikTok integration section)

**Step 1: Add TikTok section to README**

Add after the YouTube upload section:

```markdown
### TikTok Integration

The system automatically uploads videos to TikTok in addition to YouTube.

**Setup:**
1. Follow setup instructions in [docs/TIKTOK_SETUP.md](docs/TIKTOK_SETUP.md)
2. Create `config/tiktok_credentials.json` from template
3. Run OAuth authentication: `./venv/bin/python3 automation/tiktok_uploader.py --auth`

**Videos Uploaded:**
- Full song video (16:9)
- Hook short video (9:16)

**Features:**
- Independent error handling (YouTube succeeds even if TikTok fails)
- Automatic token refresh
- Cross-platform linking in captions
- Topic-aware hashtags

**Configuration:**

Edit `automation/config/automation_config.json`:

```json
{
  "tiktok": {
    "enabled": true,
    "username": "@learningsciencemusic",
    "privacy_status": "public_to_everyone"
  }
}
```

**Manual Upload:**

```bash
./upload_to_tiktok.sh --run=TIMESTAMP --type=full
./upload_to_tiktok.sh --run=TIMESTAMP --type=short_hook
```
```

**Step 2: Commit**

```bash
git add README.md
git commit -m "docs: add TikTok integration documentation to README"
```

---

## Testing Phase

After completing all implementation tasks, follow this testing sequence:

### Test 1: Verify Dependencies

```bash
./venv/bin/python3 -c "import requests; print('✅ requests imported')"
```

### Test 2: Syntax Checks

```bash
./venv/bin/python3 -m py_compile automation/tiktok_uploader.py
bash -n upload_to_tiktok.sh
bash -n pipeline.sh
bash -n automation/daily_pipeline.sh
```

### Test 3: OAuth Authentication (Manual)

**Important:** Requires TikTok developer account setup first (see docs/TIKTOK_SETUP.md)

```bash
# Create credentials file
cp config/tiktok_credentials.json.template config/tiktok_credentials.json
# Edit with actual credentials
# Then run:
./venv/bin/python3 automation/tiktok_uploader.py --auth
```

Expected: Browser opens, auth succeeds, token saved to config/tiktok_token.pickle

### Test 4: Manual Upload (Optional)

```bash
# Use existing video from a previous run
LATEST_RUN=$(ls -td outputs/runs/* | head -1)
./upload_to_tiktok.sh --run=$(basename $LATEST_RUN) --type=full --privacy=self_only
```

Expected: Video uploads successfully, ID saved to file

### Test 5: Pipeline Integration

```bash
./pipeline.sh --express
```

Expected:
- Stage 8 uploads to both YouTube (3 videos) and TikTok (2 videos)
- Stage 9 creates upload_results.json with both platforms
- TikTok upload failures don't block YouTube

### Test 6: Daily Pipeline

```bash
./automation/daily_pipeline.sh
```

Expected:
- Full pipeline runs
- Notification includes both YouTube and TikTok links
- upload_results.json contains IDs from both platforms

### Test 7: Verify Cross-Linking

```bash
# Check upload_results.json structure
LATEST_RUN=$(ls -td outputs/runs/* | head -1)
jq . "$LATEST_RUN/upload_results.json"
```

Expected JSON:
```json
{
  "youtube": {
    "full_video": {"id": "...", "url": "..."},
    "hook_short": {"id": "...", "url": "..."},
    "educational_short": {"id": "...", "url": "..."}
  },
  "tiktok": {
    "full_video": {"id": "...", "url": "..."},
    "hook_short": {"id": "...", "url": "..."}
  }
}
```

---

## Implementation Complete

All tasks complete! The TikTok integration is now fully implemented.

**Summary of changes:**
- ✅ Created `automation/tiktok_uploader.py` with OAuth and video upload
- ✅ Created `upload_to_tiktok.sh` bash wrapper
- ✅ Updated `automation_config.json` with TikTok settings
- ✅ Modified `pipeline.sh` to upload to TikTok (Stage 8) and cross-link (Stage 9)
- ✅ Updated `automation/daily_pipeline.sh` notifications
- ✅ Added setup documentation

**Next steps:**
1. Complete TikTok developer account setup (docs/TIKTOK_SETUP.md)
2. Run OAuth authentication
3. Test manual upload with privacy=self_only
4. Run full pipeline integration test
5. Submit app for TikTok audit to enable public posting
6. Monitor daily automation for 1 week

**Key features:**
- Independent error handling (YouTube succeeds even if TikTok fails)
- Automatic OAuth token refresh
- Topic-aware hashtag generation
- Cross-platform linking in captions
- Unified upload_results.json tracking
