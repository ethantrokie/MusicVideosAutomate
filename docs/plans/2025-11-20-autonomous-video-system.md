# Autonomous Video System Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a fully autonomous daily video creation system with weekly performance optimization that uploads to @LearningScienceMusic YouTube channel.

**Architecture:** Daily cron job generates topics via Claude Code CLI, runs existing pipeline in express mode, uploads to specific YouTube channel with iMessage notifications. Weekly cron job fetches YouTube Analytics, analyzes with Claude Code, applies safe config changes within guardrails, and reports via iMessage.

**Tech Stack:** Python 3.9+, Bash, Claude Code CLI, YouTube Data API v3, YouTube Analytics API, macOS AppleScript (iMessage), launchd (scheduling)

---

## Task 1: Setup Automation Directory Structure

**Files:**
- Create: `automation/config/automation_config.json`
- Create: `automation/config/guardrails.json`
- Create: `automation/state/topic_history.json`
- Create: `automation/state/optimization_state.json`
- Create: `setup_automation.sh`

**Step 1: Create directory structure**

Run:
```bash
mkdir -p automation/{config,state,logs,reports}
mkdir -p automation/logs
mkdir -p automation/reports
```

Expected: Directories created successfully

**Step 2: Create automation_config.json**

Create `automation/config/automation_config.json`:
```json
{
  "scheduling": {
    "daily_run_time": "09:00",
    "timezone": "America/Chicago",
    "weekly_analysis_day": "Sunday",
    "weekly_analysis_time": "10:00"
  },
  "youtube": {
    "channel_handle": "@LearningScienceMusic",
    "privacy_status": "private",
    "default_category": "Education",
    "credentials_path": "config/youtube_credentials.json"
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
    "categories": ["biology", "chemistry", "physics", "earth_science"],
    "prefer_trending": false
  }
}
```

**Step 3: Create guardrails.json**

Create `automation/config/guardrails.json`:
```json
{
  "safe_ranges": {
    "video_duration": [15, 120],
    "max_media_items": [5, 30],
    "min_media_items": [3, 15],
    "fps": [24, 60],
    "tone_description_max_length": 200
  },
  "allowed_changes": [
    "tone adjustments",
    "duration tweaks",
    "media variety",
    "posting time"
  ],
  "forbidden_changes": [
    "API keys",
    "channel selection",
    "privacy status",
    "resolution",
    "file paths",
    "system commands"
  ],
  "confidence_thresholds": {
    "auto_apply": 0.8,
    "flag_for_review": 0.5,
    "document_only": 0.0
  }
}
```

**Step 4: Create initial state files**

Run:
```bash
echo '{"topics": []}' > automation/state/topic_history.json
echo '{"optimizations": [], "last_analysis": null}' > automation/state/optimization_state.json
```

Expected: Empty state files created

**Step 5: Commit directory structure**

Run:
```bash
git add automation/
git commit -m "feat: create automation directory structure and config files"
```

Expected: Initial structure committed

---

## Task 2: Implement Notification Helper

**Files:**
- Create: `automation/notification_helper.sh`

**Step 1: Create notification script**

Create `automation/notification_helper.sh`:
```bash
#!/bin/bash
# Send iMessage notifications via AppleScript

PHONE="914-844-4402"
LOG_FILE="automation/logs/notifications.log"

send_text() {
    local message="$1"

    # Send via Messages app
    osascript <<EOF
tell application "Messages"
    set targetService to 1st service whose service type = iMessage
    set targetBuddy to buddy "$PHONE" of targetService
    send "$message" to targetBuddy
end tell
EOF

    # Log notification
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Sent: $message" >> "$LOG_FILE"
}

# Main execution
if [ -z "$1" ]; then
    echo "Usage: $0 \"message text\""
    exit 1
fi

send_text "$1"
```

**Step 2: Make executable**

Run:
```bash
chmod +x automation/notification_helper.sh
```

Expected: Script is executable

**Step 3: Test notification manually**

Run:
```bash
./automation/notification_helper.sh "Test: Automation system initialized"
```

Expected: iMessage received at 914-844-4402, entry in automation/logs/notifications.log

**Step 4: Commit notification helper**

Run:
```bash
git add automation/notification_helper.sh
git commit -m "feat: add iMessage notification helper via AppleScript"
```

Expected: Notification helper committed

---

## Task 3: Implement Topic Generator

**Files:**
- Create: `automation/topic_generator.py`

**Step 1: Create topic generator script**

Create `automation/topic_generator.py`:
```python
#!/usr/bin/env python3
"""
Autonomous topic generator using Claude Code CLI.
Generates educational science topics and writes to input/idea.txt.
"""

import json
import subprocess
import sys
from pathlib import Path
from datetime import datetime, timedelta


def load_config():
    """Load automation configuration."""
    config_path = Path("automation/config/automation_config.json")
    with open(config_path) as f:
        return json.load(f)


def load_topic_history():
    """Load topic history to avoid repeats."""
    history_path = Path("automation/state/topic_history.json")
    with open(history_path) as f:
        return json.load(f)


def save_topic_history(history):
    """Save updated topic history."""
    history_path = Path("automation/state/topic_history.json")
    with open(history_path, 'w') as f:
        json.dump(history, f, indent=2)


def get_recent_topics(history, days=30):
    """Get topics from last N days."""
    cutoff = datetime.now() - timedelta(days=days)
    recent = [
        entry["topic"]
        for entry in history["topics"]
        if datetime.fromisoformat(entry["date"]) > cutoff
    ]
    return recent


def generate_topic_via_claude(config, recent_topics):
    """Generate topic using Claude Code CLI."""
    categories = ", ".join(config["topic_generation"]["categories"])

    prompt = f"""Generate ONE educational science topic for a short-form video (60 seconds).

REQUIREMENTS:
- Must be from these categories: {categories}
- K-12 appropriate (ages 10-18)
- Visually interesting (can find stock footage/animations)
- NOT these recent topics: {', '.join(recent_topics[-10:])}

OUTPUT FORMAT (exactly this structure):
Topic: [specific concept]
Tone: [descriptive tone for music/pacing]

EXAMPLE:
Topic: Explain how DNA replication works in cells
Tone: energetic and fast-paced with moments of wonder

Generate now:"""

    result = subprocess.run(
        ["claude", "-p", prompt, "--dangerously-skip-permissions"],
        capture_output=True,
        text=True,
        timeout=30
    )

    if result.returncode != 0:
        raise Exception(f"Claude CLI failed: {result.stderr}")

    return result.stdout.strip()


def parse_topic_output(output):
    """Parse Claude's output into topic and tone."""
    lines = [line.strip() for line in output.split('\n') if line.strip()]

    topic = None
    tone = None

    for line in lines:
        if line.startswith("Topic:"):
            topic = line.replace("Topic:", "").strip()
        elif line.startswith("Tone:"):
            tone = line.replace("Tone:", "").strip()

    if not topic or not tone:
        raise ValueError(f"Could not parse topic/tone from output: {output}")

    return topic, tone


def write_idea_file(topic, tone):
    """Write topic to input/idea.txt."""
    idea_path = Path("input/idea.txt")
    with open(idea_path, 'w') as f:
        f.write(f"{topic}. Tone: {tone}\n")


def main():
    """Main execution."""
    print("🎯 Generating educational science topic...")

    # Load config and history
    config = load_config()
    history = load_topic_history()

    # Get recent topics to avoid repeats
    avoid_days = config["topic_generation"]["avoid_repeat_days"]
    recent_topics = get_recent_topics(history, days=avoid_days)

    # Generate topic via Claude
    output = generate_topic_via_claude(config, recent_topics)
    topic, tone = parse_topic_output(output)

    print(f"  Topic: {topic}")
    print(f"  Tone: {tone}")

    # Write to idea.txt
    write_idea_file(topic, tone)

    # Update history
    history["topics"].append({
        "date": datetime.now().isoformat(),
        "topic": topic,
        "tone": tone
    })
    save_topic_history(history)

    print(f"✅ Topic written to input/idea.txt")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        sys.exit(1)
```

**Step 2: Make executable**

Run:
```bash
chmod +x automation/topic_generator.py
```

Expected: Script is executable

**Step 3: Test topic generator manually**

Run:
```bash
./automation/topic_generator.py
```

Expected:
- Prints topic and tone
- Creates/updates input/idea.txt
- Updates automation/state/topic_history.json

**Step 4: Verify output**

Run:
```bash
cat input/idea.txt
cat automation/state/topic_history.json
```

Expected: Valid topic in idea.txt, entry in history

**Step 5: Commit topic generator**

Run:
```bash
git add automation/topic_generator.py
git commit -m "feat: add autonomous topic generator using Claude Code CLI"
```

Expected: Topic generator committed

---

## Task 4: Modify YouTube Uploader for Channel Selection

**Files:**
- Modify: `upload_to_youtube.sh`

**Step 1: Read current upload script**

Run:
```bash
head -50 upload_to_youtube.sh
```

Expected: See current implementation

**Step 2: Create Python helper for channel selection**

Create `automation/youtube_channel_helper.py`:
```python
#!/usr/bin/env python3
"""
YouTube channel selection helper.
Lists channels and uploads to specific channel by handle.
"""

import os
import sys
import json
import pickle
from pathlib import Path
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request


SCOPES = [
    'https://www.googleapis.com/auth/youtube.upload',
    'https://www.googleapis.com/auth/youtube.readonly'
]


def get_authenticated_service():
    """Authenticate and return YouTube API service."""
    creds = None
    token_path = Path('config/youtube_token.pickle')
    creds_path = Path('config/youtube_credentials.json')

    if token_path.exists():
        with open(token_path, 'rb') as token:
            creds = pickle.load(token)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                str(creds_path), SCOPES)
            creds = flow.run_local_server(port=0)

        with open(token_path, 'wb') as token:
            pickle.dump(creds, token)

    return build('youtube', 'v3', credentials=creds)


def list_channels(youtube):
    """List all channels for authenticated user."""
    request = youtube.channels().list(
        part='snippet,contentDetails',
        mine=True
    )
    response = request.execute()

    channels = []
    for item in response.get('items', []):
        channels.append({
            'id': item['id'],
            'title': item['snippet']['title'],
            'handle': item['snippet'].get('customUrl', 'N/A')
        })

    return channels


def get_channel_id_by_handle(youtube, handle):
    """Get channel ID by handle (e.g., @LearningScienceMusic)."""
    channels = list_channels(youtube)

    for channel in channels:
        if channel['handle'] == handle or f"@{channel['handle']}" == handle:
            return channel['id']

    raise ValueError(f"Channel with handle '{handle}' not found. Available: {channels}")


def upload_video(youtube, video_path, title, description, category, privacy, channel_id=None):
    """Upload video to YouTube."""
    body = {
        'snippet': {
            'title': title,
            'description': description,
            'categoryId': category
        },
        'status': {
            'privacyStatus': privacy
        }
    }

    # If channel_id provided, set it (though mine=True should handle this)
    if channel_id:
        body['snippet']['channelId'] = channel_id

    media = MediaFileUpload(video_path, chunksize=-1, resumable=True)

    request = youtube.videos().insert(
        part=','.join(body.keys()),
        body=body,
        media_body=media
    )

    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            print(f"  Uploaded {int(status.progress() * 100)}%")

    return response['id']


def main():
    """Main CLI interface."""
    import argparse

    parser = argparse.ArgumentParser(description='YouTube channel helper')
    parser.add_argument('--list-channels', action='store_true',
                       help='List available channels')
    parser.add_argument('--channel', type=str,
                       help='Channel handle (e.g., @LearningScienceMusic)')
    parser.add_argument('--video', type=str,
                       help='Path to video file')
    parser.add_argument('--title', type=str,
                       help='Video title')
    parser.add_argument('--description', type=str, default='',
                       help='Video description')
    parser.add_argument('--category', type=str, default='27',
                       help='Category ID (27=Education)')
    parser.add_argument('--privacy', type=str, default='private',
                       choices=['public', 'private', 'unlisted'],
                       help='Privacy status')

    args = parser.parse_args()

    # Authenticate
    youtube = get_authenticated_service()

    # List channels
    if args.list_channels:
        channels = list_channels(youtube)
        print("Available channels:")
        for ch in channels:
            print(f"  - {ch['title']} ({ch['handle']}) [ID: {ch['id']}]")
        return

    # Upload video
    if args.video and args.title:
        # Get channel ID if handle provided
        channel_id = None
        if args.channel:
            channel_id = get_channel_id_by_handle(youtube, args.channel)
            print(f"Uploading to channel: {args.channel} (ID: {channel_id})")

        video_id = upload_video(
            youtube,
            args.video,
            args.title,
            args.description,
            args.category,
            args.privacy,
            channel_id
        )
        print(f"✅ Video uploaded: https://youtube.com/watch?v={video_id}")

        # Return video ID for scripting
        return video_id

    parser.print_help()


if __name__ == '__main__':
    main()
```

**Step 3: Make helper executable**

Run:
```bash
chmod +x automation/youtube_channel_helper.py
```

Expected: Script is executable

**Step 4: Test channel listing**

Run:
```bash
./automation/youtube_channel_helper.py --list-channels
```

Expected: Lists your YouTube channels including @LearningScienceMusic

**Step 5: Update upload_to_youtube.sh to use helper**

Modify `upload_to_youtube.sh` to add channel support:
```bash
#!/bin/bash
# Upload video to YouTube with channel selection support

set -e

# Default values
PRIVACY="unlisted"
RUN_DIR=""
CHANNEL=""

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
        --channel=*)
            CHANNEL="${1#*=}"
            shift
            ;;
        --help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --run=TIMESTAMP        Upload specific run"
            echo "  --privacy=STATUS       Privacy: public, unlisted, private (default: unlisted)"
            echo "  --channel=HANDLE       Channel handle (e.g., @LearningScienceMusic)"
            echo "  --help                 Show this help"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Use latest run if not specified
if [ -z "$RUN_DIR" ]; then
    RUN_DIR="outputs/current"
fi

VIDEO_PATH="$RUN_DIR/final_video.mp4"

if [ ! -f "$VIDEO_PATH" ]; then
    echo "❌ Error: Video not found at $VIDEO_PATH"
    exit 1
fi

# Get topic from idea.txt
TOPIC=$(head -1 input/idea.txt | cut -d'.' -f1)
TITLE="$TOPIC | Educational Short"
DESCRIPTION="Learn about $TOPIC in 60 seconds! 🧬🔬

#science #education #learning #shorts"

echo "📤 Uploading to YouTube..."
echo "  Video: $VIDEO_PATH"
echo "  Title: $TITLE"
echo "  Privacy: $PRIVACY"
if [ -n "$CHANNEL" ]; then
    echo "  Channel: $CHANNEL"
fi

# Upload using Python helper
UPLOAD_CMD="./automation/youtube_channel_helper.py --video \"$VIDEO_PATH\" --title \"$TITLE\" --description \"$DESCRIPTION\" --privacy \"$PRIVACY\""

if [ -n "$CHANNEL" ]; then
    UPLOAD_CMD="$UPLOAD_CMD --channel \"$CHANNEL\""
fi

eval $UPLOAD_CMD

echo "✅ Upload complete!"
```

**Step 6: Test upload to specific channel (private)**

Run:
```bash
# First ensure we have a video
./pipeline.sh --express

# Then test upload to @LearningScienceMusic
./upload_to_youtube.sh --channel="@LearningScienceMusic" --privacy=private
```

Expected: Video uploads to @LearningScienceMusic channel as private

**Step 7: Commit YouTube channel selection**

Run:
```bash
git add automation/youtube_channel_helper.py upload_to_youtube.sh
git commit -m "feat: add YouTube channel selection support for @LearningScienceMusic"
```

Expected: Channel selection committed

---

## Task 5: Implement Daily Pipeline Script

**Files:**
- Create: `automation/daily_pipeline.sh`

**Step 1: Create daily pipeline orchestrator**

Create `automation/daily_pipeline.sh`:
```bash
#!/bin/bash
# Daily video pipeline orchestrator
# Generates topic, creates video, uploads to YouTube, sends notifications

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_DIR"

LOG_DATE=$(date '+%Y-%m-%d')
LOG_FILE="automation/logs/daily_$LOG_DATE.log"
CONFIG_FILE="automation/config/automation_config.json"

# Load config
CHANNEL=$(jq -r '.youtube.channel_handle' "$CONFIG_FILE")
PRIVACY=$(jq -r '.youtube.privacy_status' "$CONFIG_FILE")
NOTIFY_SUCCESS=$(jq -r '.notifications.notify_on_success' "$CONFIG_FILE")
NOTIFY_FAILURE=$(jq -r '.notifications.notify_on_failure' "$CONFIG_FILE")

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

send_notification() {
    local message="$1"
    ./automation/notification_helper.sh "$message"
}

run_pipeline() {
    local attempt=$1

    log "Attempt $attempt: Generating topic..."
    if ! ./automation/topic_generator.py >> "$LOG_FILE" 2>&1; then
        log "❌ Topic generation failed"
        return 1
    fi

    TOPIC=$(head -1 input/idea.txt | cut -d'.' -f1)
    log "Topic: $TOPIC"

    log "Running pipeline in express mode..."
    if ! ./pipeline.sh --express >> "$LOG_FILE" 2>&1; then
        log "❌ Pipeline failed"
        return 1
    fi

    log "Uploading to YouTube ($CHANNEL, $PRIVACY)..."
    if ! ./upload_to_youtube.sh --channel="$CHANNEL" --privacy="$PRIVACY" >> "$LOG_FILE" 2>&1; then
        log "❌ Upload failed"
        return 1
    fi

    log "✅ Pipeline complete"
    return 0
}

main() {
    log "========================================="
    log "Daily Video Pipeline Starting"
    log "========================================="

    # Try up to 2 times
    attempt=1
    max_attempts=2

    while [ $attempt -le $max_attempts ]; do
        if run_pipeline $attempt; then
            # Success!
            TOPIC=$(head -1 input/idea.txt | cut -d'.' -f1)
            VIDEO_ID=$(tail -1 "$LOG_FILE" | grep -o 'watch?v=.*' | cut -d'=' -f2 || echo "unknown")

            log "✅ Daily video published successfully"

            if [ "$NOTIFY_SUCCESS" = "true" ]; then
                send_notification "✅ Daily video published!
Topic: $TOPIC
Video: https://youtube.com/watch?v=$VIDEO_ID
Status: $PRIVACY"
            fi

            exit 0
        fi

        if [ $attempt -eq $max_attempts ]; then
            # Final failure
            log "❌ Pipeline failed after $max_attempts attempts"

            if [ "$NOTIFY_FAILURE" = "true" ]; then
                send_notification "❌ Daily video failed after $max_attempts attempts
Check logs: automation/logs/daily_$LOG_DATE.log"
            fi

            exit 1
        fi

        # Wait before retry
        log "Retrying in 5 minutes..."
        sleep 300
        attempt=$((attempt + 1))
    done
}

# Run main
main
```

**Step 2: Make executable**

Run:
```bash
chmod +x automation/daily_pipeline.sh
```

Expected: Script is executable

**Step 3: Test daily pipeline manually**

Run:
```bash
./automation/daily_pipeline.sh
```

Expected:
- Topic generated
- Video created via pipeline
- Uploaded to @LearningScienceMusic
- Success notification received
- Log file created in automation/logs/

**Step 4: Verify outputs**

Run:
```bash
cat automation/logs/daily_$(date '+%Y-%m-%d').log
```

Expected: Complete log of pipeline execution

**Step 5: Commit daily pipeline**

Run:
```bash
git add automation/daily_pipeline.sh
git commit -m "feat: add daily pipeline orchestrator with retry and notifications"
```

Expected: Daily pipeline committed

---

## Task 6: Install Python Dependencies for YouTube Analytics

**Files:**
- Modify: `requirements.txt` (or create if doesn't exist)

**Step 1: Check for existing requirements**

Run:
```bash
ls requirements.txt 2>/dev/null || echo "No requirements.txt found"
```

**Step 2: Add YouTube API dependencies**

If `requirements.txt` exists, append. Otherwise create:
```
google-api-python-client
google-auth-httplib2
google-auth-oauthlib
```

**Step 3: Install dependencies**

Run:
```bash
./venv/bin/pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib
```

Expected: Packages installed successfully

**Step 4: Verify installation**

Run:
```bash
./venv/bin/python -c "from googleapiclient.discovery import build; print('✓ YouTube API client available')"
```

Expected: ✓ YouTube API client available

**Step 5: Commit requirements**

Run:
```bash
git add requirements.txt
git commit -m "deps: add YouTube API dependencies for analytics"
```

Expected: Dependencies committed

---

## Task 7: Implement Change Guardian

**Files:**
- Create: `automation/change_guardian.py`

**Step 1: Create change validation module**

Create `automation/change_guardian.py`:
```python
#!/usr/bin/env python3
"""
Change guardian - validates proposed config changes against guardrails.
Prevents unsafe or out-of-bounds modifications.
"""

import json
import re
from pathlib import Path
from typing import Dict, Tuple


class ChangeGuardian:
    """Validates proposed configuration changes."""

    def __init__(self, guardrails_path: str = "automation/config/guardrails.json"):
        with open(guardrails_path) as f:
            self.guardrails = json.load(f)

    def validate_change(self, recommendation: Dict) -> Tuple[str, str]:
        """
        Validate a proposed change.

        Returns: (status, reason)
            status: "AUTO_APPLY", "NEEDS_REVIEW", "REJECTED", "DOCUMENT_ONLY"
            reason: explanation
        """
        change_type = recommendation.get("change", "")
        confidence = recommendation.get("confidence", 0.0)
        proposed_value = recommendation.get("proposed_value")

        # Check if forbidden
        for forbidden in self.guardrails["forbidden_changes"]:
            if forbidden.lower() in change_type.lower():
                return "REJECTED", f"Forbidden change type: {forbidden}"

        # Check if allowed
        allowed = False
        for allowed_pattern in self.guardrails["allowed_changes"]:
            if allowed_pattern.split("(")[0].strip().lower() in change_type.lower():
                allowed = True
                break

        if not allowed:
            return "NEEDS_REVIEW", "Change type not in allowed list"

        # Validate specific ranges
        if "duration" in change_type.lower():
            min_dur, max_dur = self.guardrails["safe_ranges"]["video_duration"]
            if not isinstance(proposed_value, (int, float)):
                return "NEEDS_REVIEW", "Duration must be numeric"
            if not (min_dur <= proposed_value <= max_dur):
                return "NEEDS_REVIEW", f"Duration {proposed_value} outside safe range [{min_dur}, {max_dur}]"

        if "media" in change_type.lower():
            if "max" in change_type.lower():
                min_val, max_val = self.guardrails["safe_ranges"]["max_media_items"][0], self.guardrails["safe_ranges"]["max_media_items"][1]
            else:
                min_val, max_val = self.guardrails["safe_ranges"]["min_media_items"][0], self.guardrails["safe_ranges"]["min_media_items"][1]

            if not isinstance(proposed_value, int):
                return "NEEDS_REVIEW", "Media count must be integer"
            if not (min_val <= proposed_value <= max_val):
                return "NEEDS_REVIEW", f"Media count {proposed_value} outside safe range [{min_val}, {max_val}]"

        if "tone" in change_type.lower():
            if not isinstance(proposed_value, str):
                return "NEEDS_REVIEW", "Tone must be string"
            if len(proposed_value) > self.guardrails["safe_ranges"]["tone_description_max_length"]:
                return "NEEDS_REVIEW", f"Tone too long (max {self.guardrails['safe_ranges']['tone_description_max_length']} chars)"

            # Check for injection patterns
            dangerous_patterns = [
                r"exec\(",
                r"eval\(",
                r"__import__",
                r"subprocess",
                r"os\.",
                r"rm\s+-rf",
                r"<script>",
            ]
            for pattern in dangerous_patterns:
                if re.search(pattern, proposed_value, re.IGNORECASE):
                    return "REJECTED", f"Tone contains dangerous pattern: {pattern}"

        # Check confidence threshold
        thresholds = self.guardrails["confidence_thresholds"]
        if confidence >= thresholds["auto_apply"]:
            return "AUTO_APPLY", "High confidence and within guardrails"
        elif confidence >= thresholds["flag_for_review"]:
            return "NEEDS_REVIEW", "Medium confidence"
        else:
            return "DOCUMENT_ONLY", "Low confidence"

    def validate_all(self, recommendations: list) -> Dict:
        """Validate all recommendations."""
        results = {
            "auto_apply": [],
            "needs_review": [],
            "rejected": [],
            "document_only": []
        }

        for rec in recommendations:
            status, reason = self.validate_change(rec)
            rec["validation_status"] = status
            rec["validation_reason"] = reason

            if status == "AUTO_APPLY":
                results["auto_apply"].append(rec)
            elif status == "NEEDS_REVIEW":
                results["needs_review"].append(rec)
            elif status == "REJECTED":
                results["rejected"].append(rec)
            else:
                results["document_only"].append(rec)

        return results


def main():
    """Test change guardian."""
    guardian = ChangeGuardian()

    test_cases = [
        {
            "change": "video_duration",
            "current_value": 60,
            "proposed_value": 55,
            "confidence": 0.85,
            "rationale": "Shorter videos have better retention"
        },
        {
            "change": "tone adjustments",
            "current_value": "energetic",
            "proposed_value": "calm and contemplative",
            "confidence": 0.75,
            "rationale": "Calmer tone might work better"
        },
        {
            "change": "API key update",
            "current_value": "xxx",
            "proposed_value": "yyy",
            "confidence": 0.9,
            "rationale": "Should be rejected"
        },
        {
            "change": "video_duration",
            "current_value": 60,
            "proposed_value": 200,
            "confidence": 0.9,
            "rationale": "Out of range"
        }
    ]

    results = guardian.validate_all(test_cases)

    print("Validation Results:")
    print(f"  Auto-apply: {len(results['auto_apply'])}")
    print(f"  Needs review: {len(results['needs_review'])}")
    print(f"  Rejected: {len(results['rejected'])}")
    print(f"  Document only: {len(results['document_only'])}")

    for rec in results["auto_apply"]:
        print(f"  ✓ {rec['change']}: {rec['validation_reason']}")

    for rec in results["rejected"]:
        print(f"  ✗ {rec['change']}: {rec['validation_reason']}")


if __name__ == "__main__":
    main()
```

**Step 2: Make executable**

Run:
```bash
chmod +x automation/change_guardian.py
```

Expected: Script is executable

**Step 3: Test change guardian**

Run:
```bash
./automation/change_guardian.py
```

Expected:
- Test cases validated
- Duration change (55s): AUTO_APPLY
- API key change: REJECTED
- Out of range duration: NEEDS_REVIEW

**Step 4: Commit change guardian**

Run:
```bash
git add automation/change_guardian.py
git commit -m "feat: add change guardian for validating config modifications"
```

Expected: Change guardian committed

---

## Task 8: Implement Weekly Optimizer

**Files:**
- Create: `automation/weekly_optimizer.py`

**Step 1: Create weekly optimizer script**

Create `automation/weekly_optimizer.py`:
```python
#!/usr/bin/env python3
"""
Weekly performance optimizer.
Fetches YouTube Analytics, analyzes with Claude Code, applies safe changes.
"""

import json
import subprocess
import sys
import re
from pathlib import Path
from datetime import datetime, timedelta
import pickle
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

# Import change guardian
sys.path.insert(0, str(Path(__file__).parent))
from change_guardian import ChangeGuardian


SCOPES = [
    'https://www.googleapis.com/auth/youtube.readonly',
    'https://www.googleapis.com/auth/yt-analytics.readonly'
]


def get_authenticated_service(api_name, api_version):
    """Authenticate and return API service."""
    creds = None
    token_path = Path('config/youtube_token.pickle')
    creds_path = Path('config/youtube_credentials.json')

    if token_path.exists():
        with open(token_path, 'rb') as token:
            creds = pickle.load(token)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                str(creds_path), SCOPES)
            creds = flow.run_local_server(port=0)

        with open(token_path, 'wb') as token:
            pickle.dump(creds, token)

    return build(api_name, api_version, credentials=creds)


def sanitize_text(text, max_length=500):
    """Remove prompt injection patterns."""
    dangerous_patterns = [
        r"ignore\s+(previous|above|all)\s+instructions",
        r"system\s*:",
        r"you\s+are\s+now",
        r"forget\s+(everything|all|previous)",
        r"new\s+instructions",
        r"<script>",
        r"```",
        r"exec\(",
        r"eval\(",
    ]

    cleaned = text
    for pattern in dangerous_patterns:
        cleaned = re.sub(pattern, "[FILTERED]", cleaned, flags=re.IGNORECASE)

    return cleaned[:max_length]


def get_channel_videos(youtube, channel_id, days=7):
    """Get recent videos from channel."""
    since = (datetime.now() - timedelta(days=days)).isoformat() + 'Z'

    request = youtube.search().list(
        part='id,snippet',
        channelId=channel_id,
        maxResults=50,
        order='date',
        publishedAfter=since,
        type='video'
    )

    response = request.execute()

    videos = []
    for item in response.get('items', []):
        videos.append({
            'video_id': item['id']['videoId'],
            'title': sanitize_text(item['snippet']['title'], 100),
            'published_at': item['snippet']['publishedAt']
        })

    return videos


def get_video_analytics(analytics, video_ids):
    """Get analytics data for videos."""
    if not video_ids:
        return []

    video_ids_str = ','.join(video_ids)
    end_date = datetime.now().date()
    start_date = end_date - timedelta(days=7)

    request = analytics.reports().query(
        ids='channel==MINE',
        startDate=start_date.isoformat(),
        endDate=end_date.isoformat(),
        metrics='views,estimatedMinutesWatched,likes,comments,shares,averageViewPercentage',
        dimensions='video',
        filters=f'video=={video_ids_str}'
    )

    response = request.execute()

    metrics = {}
    for row in response.get('rows', []):
        video_id = row[0]
        metrics[video_id] = {
            'views': int(row[1]),
            'watch_time_minutes': int(row[2]),
            'likes': int(row[3]),
            'comments': int(row[4]),
            'shares': int(row[5]),
            'avg_retention': float(row[6])
        }

    return metrics


def load_config():
    """Load configs."""
    with open('automation/config/automation_config.json') as f:
        automation_config = json.load(f)

    with open('config/config.json') as f:
        video_config = json.load(f)

    return automation_config, video_config


def analyze_with_claude(metrics_data, current_config):
    """Analyze metrics with Claude Code CLI."""
    prompt = f"""Analyze this week's educational video performance and suggest 1-2 optimizations.

METRICS:
{json.dumps(metrics_data, indent=2)}

CURRENT CONFIG:
- Video duration: {current_config['video_settings']['duration']}s
- Media items: {current_config['pipeline_settings']['min_media_items']}-{current_config['pipeline_settings']['max_media_items']}
- Current tone examples from recent videos

RULES:
1. Focus on engagement metrics (watch time, likes, shares, retention)
2. Suggest ONLY changes within safe ranges:
   - Duration: 15-120 seconds
   - Media items: 5-30
   - Tone: Any educational style (no profanity)
3. Output JSON ONLY with this exact schema:
{{
  "insights": ["insight 1", "insight 2"],
  "recommendations": [
    {{
      "change": "description of what to change",
      "current_value": current_value,
      "proposed_value": proposed_value,
      "rationale": "why this change",
      "confidence": 0.85,
      "expected_impact": "what we expect to improve"
    }}
  ]
}}

Respond with ONLY valid JSON, no markdown or explanation:"""

    result = subprocess.run(
        ["claude", "-p", prompt, "--dangerously-skip-permissions"],
        capture_output=True,
        text=True,
        timeout=60
    )

    if result.returncode != 0:
        raise Exception(f"Claude CLI failed: {result.stderr}")

    # Parse JSON from output
    output = result.stdout.strip()

    # Try to extract JSON from markdown code blocks if present
    if "```json" in output:
        output = output.split("```json")[1].split("```")[0].strip()
    elif "```" in output:
        output = output.split("```")[1].split("```")[0].strip()

    return json.loads(output)


def apply_changes(auto_apply_changes, video_config):
    """Apply validated changes to config."""
    changes_made = []

    for change in auto_apply_changes:
        change_type = change["change"].lower()
        proposed_value = change["proposed_value"]

        if "duration" in change_type:
            video_config["video_settings"]["duration"] = proposed_value
            changes_made.append(f"video_duration: {change['current_value']} → {proposed_value}")

        elif "max_media" in change_type or "media" in change_type and "max" in str(proposed_value):
            video_config["pipeline_settings"]["max_media_items"] = proposed_value
            changes_made.append(f"max_media_items: {change['current_value']} → {proposed_value}")

        elif "min_media" in change_type:
            video_config["pipeline_settings"]["min_media_items"] = proposed_value
            changes_made.append(f"min_media_items: {change['current_value']} → {proposed_value}")

    # Save updated config
    with open('config/config.json', 'w') as f:
        json.dump(video_config, f, indent=2)

    return changes_made


def save_optimization_state(changes, analysis):
    """Save optimization state for tracking."""
    state_file = Path("automation/state/optimization_state.json")

    with open(state_file) as f:
        state = json.load(f)

    for change_desc in changes:
        parts = change_desc.split(": ")
        if len(parts) == 2:
            change_type, values = parts
            from_val, to_val = values.split(" → ")

            state["optimizations"].append({
                "date": datetime.now().isoformat(),
                "change": change_type,
                "from": from_val,
                "to": to_val,
                "rationale": analysis.get("insights", [""])[0],
                "impact_observed": None
            })

    state["last_analysis"] = datetime.now().isoformat()

    with open(state_file, 'w') as f:
        json.dump(state, f, indent=2)


def generate_report(metrics_data, analysis, validation_results, changes_applied):
    """Generate markdown report."""
    report_date = datetime.now().strftime('%Y-%m-%d')
    report_path = Path(f"automation/reports/{report_date}-analysis.md")

    # Calculate totals
    total_views = sum(m.get('views', 0) for m in metrics_data.values())
    total_engagement = sum(m.get('likes', 0) + m.get('comments', 0) + m.get('shares', 0)
                          for m in metrics_data.values())

    report = f"""# Weekly Performance Analysis - {report_date}

## Summary
- Videos analyzed: {len(metrics_data)}
- Total views: {total_views:,}
- Total engagement: {total_engagement} (likes + comments + shares)

## Insights
{chr(10).join(f'- {insight}' for insight in analysis.get('insights', []))}

## Recommendations

### Auto-Applied (High Confidence)
{chr(10).join(f'- {change}' for change in changes_applied) if changes_applied else '- None this week'}

### Pending Review (Medium Confidence)
{chr(10).join(f'- {rec["change"]}: {rec["rationale"]} (confidence: {rec["confidence"]})'
              for rec in validation_results['needs_review']) if validation_results['needs_review'] else '- None this week'}

### Rejected
{chr(10).join(f'- {rec["change"]}: {rec["validation_reason"]}'
              for rec in validation_results['rejected']) if validation_results['rejected'] else '- None'}

## Changes Applied
{chr(10).join(f'- {change}' for change in changes_applied) if changes_applied else '- No changes applied this week'}

## Next Week Focus
- Monitor impact of applied changes
- Continue tracking retention metrics
"""

    with open(report_path, 'w') as f:
        f.write(report)

    return report_path


def send_notification(report_path, changes_applied, pending_count):
    """Send iMessage notification."""
    message = f"""📊 Weekly analysis complete!
Report: {report_path}
Changes: {len(changes_applied)} auto-applied, {pending_count} pending review"""

    subprocess.run(
        ["./automation/notification_helper.sh", message],
        check=True
    )


def main():
    """Main execution."""
    print("📊 Weekly Performance Optimizer")
    print("=" * 50)

    # Load configs
    automation_config, video_config = load_config()

    # Authenticate APIs
    print("Authenticating with YouTube...")
    youtube = get_authenticated_service('youtube', 'v3')
    analytics = get_authenticated_service('youtubeAnalytics', 'v2')

    # Get channel info
    print("Fetching channel info...")
    channels = youtube.channels().list(part='id', mine=True).execute()
    channel_id = channels['items'][0]['id']

    # Get recent videos
    print("Fetching recent videos...")
    videos = get_channel_videos(youtube, channel_id, days=7)
    print(f"  Found {len(videos)} videos")

    if not videos:
        print("No videos to analyze this week")
        return

    # Get analytics
    print("Fetching analytics data...")
    video_ids = [v['video_id'] for v in videos]
    metrics = get_video_analytics(analytics, video_ids)

    # Combine video info with metrics
    metrics_data = {}
    for video in videos:
        vid = video['video_id']
        if vid in metrics:
            metrics_data[vid] = {
                'title': video['title'],
                **metrics[vid]
            }

    # Analyze with Claude
    print("Analyzing performance with Claude Code...")
    analysis = analyze_with_claude(metrics_data, video_config)

    print(f"  Insights: {len(analysis.get('insights', []))}")
    print(f"  Recommendations: {len(analysis.get('recommendations', []))}")

    # Validate changes
    print("Validating recommendations...")
    guardian = ChangeGuardian()
    validation_results = guardian.validate_all(analysis.get('recommendations', []))

    print(f"  Auto-apply: {len(validation_results['auto_apply'])}")
    print(f"  Needs review: {len(validation_results['needs_review'])}")
    print(f"  Rejected: {len(validation_results['rejected'])}")

    # Apply safe changes if enabled
    changes_applied = []
    if automation_config['optimization']['enabled']:
        if automation_config['optimization']['auto_apply_high_confidence']:
            print("Applying high-confidence changes...")
            changes_applied = apply_changes(validation_results['auto_apply'], video_config)

            for change in changes_applied:
                print(f"  ✓ Applied: {change}")

    # Save pending changes if any
    if validation_results['needs_review']:
        pending_path = Path("automation/pending_changes.json")
        with open(pending_path, 'w') as f:
            json.dump(validation_results['needs_review'], f, indent=2)
        print(f"  ⚠️  Pending changes saved to {pending_path}")

    # Update optimization state
    save_optimization_state(changes_applied, analysis)

    # Generate report
    print("Generating report...")
    report_path = generate_report(metrics_data, analysis, validation_results, changes_applied)
    print(f"  Report saved to {report_path}")

    # Send notification
    if automation_config['notifications']['notify_on_weekly_report']:
        print("Sending notification...")
        send_notification(report_path, changes_applied, len(validation_results['needs_review']))

    print("\n✅ Weekly optimization complete!")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
```

**Step 2: Make executable**

Run:
```bash
chmod +x automation/weekly_optimizer.py
```

Expected: Script is executable

**Step 3: Test weekly optimizer (dry run)**

Run:
```bash
# First ensure optimization is disabled for testing
jq '.optimization.enabled = false' automation/config/automation_config.json > tmp.json && mv tmp.json automation/config/automation_config.json

# Run optimizer
./automation/weekly_optimizer.py
```

Expected:
- Fetches YouTube analytics
- Analyzes with Claude
- Validates recommendations
- Generates report (no changes applied since disabled)
- Notification sent

**Step 4: Verify report**

Run:
```bash
cat automation/reports/$(date +%Y-%m-%d)-analysis.md
```

Expected: Detailed performance report

**Step 5: Commit weekly optimizer**

Run:
```bash
git add automation/weekly_optimizer.py
git commit -m "feat: add weekly performance optimizer with Claude Code analysis"
```

Expected: Weekly optimizer committed

---

## Task 9: Create launchd Plists for Scheduling

**Files:**
- Create: `~/Library/LaunchAgents/com.learningscience.daily.plist`
- Create: `~/Library/LaunchAgents/com.learningscience.weekly.plist`

**Step 1: Create daily launchd plist**

Create `~/Library/LaunchAgents/com.learningscience.daily.plist`:
```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.learningscience.daily</string>
    <key>ProgramArguments</key>
    <array>
        <string>/Users/ethantrokie/SoftwareDevProjects/MusicVideosAutomate/automation/daily_pipeline.sh</string>
    </array>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>9</integer>
        <key>Minute</key>
        <integer>0</integer>
    </dict>
    <key>WorkingDirectory</key>
    <string>/Users/ethantrokie/SoftwareDevProjects/MusicVideosAutomate</string>
    <key>StandardOutPath</key>
    <string>/Users/ethantrokie/SoftwareDevProjects/MusicVideosAutomate/automation/logs/launchd_daily.log</string>
    <key>StandardErrorPath</key>
    <string>/Users/ethantrokie/SoftwareDevProjects/MusicVideosAutomate/automation/logs/launchd_daily_error.log</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
    </dict>
</dict>
</plist>
```

**Step 2: Create weekly launchd plist**

Create `~/Library/LaunchAgents/com.learningscience.weekly.plist`:
```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.learningscience.weekly</string>
    <key>ProgramArguments</key>
    <array>
        <string>/Users/ethantrokie/SoftwareDevProjects/MusicVideosAutomate/venv/bin/python3</string>
        <string>/Users/ethantrokie/SoftwareDevProjects/MusicVideosAutomate/automation/weekly_optimizer.py</string>
    </array>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Weekday</key>
        <integer>0</integer>
        <key>Hour</key>
        <integer>10</integer>
        <key>Minute</key>
        <integer>0</integer>
    </dict>
    <key>WorkingDirectory</key>
    <string>/Users/ethantrokie/SoftwareDevProjects/MusicVideosAutomate</string>
    <key>StandardOutPath</key>
    <string>/Users/ethantrokie/SoftwareDevProjects/MusicVideosAutomate/automation/logs/launchd_weekly.log</string>
    <key>StandardErrorPath</key>
    <string>/Users/ethantrokie/SoftwareDevProjects/MusicVideosAutomate/automation/logs/launchd_weekly_error.log</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
    </dict>
</dict>
</plist>
```

**Step 3: Load daily job**

Run:
```bash
launchctl load ~/Library/LaunchAgents/com.learningscience.daily.plist
```

Expected: Job loaded successfully

**Step 4: Load weekly job**

Run:
```bash
launchctl load ~/Library/LaunchAgents/com.learningscience.weekly.plist
```

Expected: Job loaded successfully

**Step 5: Verify jobs are loaded**

Run:
```bash
launchctl list | grep learningscience
```

Expected: Both jobs listed

**Step 6: Document launchd setup**

Create `automation/README.md`:
```markdown
# Automation System

## Scheduled Jobs

### Daily Video Pipeline
- **Schedule:** Every day at 9:00 AM CST
- **Script:** `automation/daily_pipeline.sh`
- **Logs:** `automation/logs/daily_YYYY-MM-DD.log`

### Weekly Optimizer
- **Schedule:** Every Sunday at 10:00 AM CST
- **Script:** `automation/weekly_optimizer.py`
- **Reports:** `automation/reports/YYYY-MM-DD-analysis.md`

## Managing Jobs

Load jobs:
```bash
launchctl load ~/Library/LaunchAgents/com.learningscience.daily.plist
launchctl load ~/Library/LaunchAgents/com.learningscience.weekly.plist
```

Unload jobs:
```bash
launchctl unload ~/Library/LaunchAgents/com.learningscience.daily.plist
launchctl unload ~/Library/LaunchAgents/com.learningscience.weekly.plist
```

Check status:
```bash
launchctl list | grep learningscience
```

## Configuration

Edit `automation/config/automation_config.json` to:
- Change posting times
- Enable/disable optimization
- Change privacy status (private → public)
- Configure notifications
```

**Step 7: Commit launchd setup**

Run:
```bash
git add automation/README.md
git commit -m "docs: add automation README with launchd management"
```

Expected: Documentation committed

---

## Task 10: Final Integration Testing

**Files:**
- Test all components together

**Step 1: Manual test - Full daily pipeline**

Run:
```bash
./automation/daily_pipeline.sh
```

Expected:
- Topic generated
- Video created
- Uploaded to @LearningScienceMusic (private)
- Success notification received
- Logs written

**Step 2: Verify video on YouTube**

1. Go to YouTube Studio
2. Check @LearningScienceMusic channel
3. Verify latest video is there (private)

Expected: Video uploaded successfully

**Step 3: Manual test - Weekly optimizer**

Run:
```bash
# Enable optimization for testing
jq '.optimization.enabled = true' automation/config/automation_config.json > tmp.json && mv tmp.json automation/config/automation_config.json

# Run optimizer
./automation/weekly_optimizer.py
```

Expected:
- Analytics fetched
- Claude analysis complete
- Changes validated
- Safe changes applied to config/config.json
- Report generated
- Notification received

**Step 4: Verify config changes**

Run:
```bash
git diff config/config.json
```

Expected: See any auto-applied changes (if confidence was high enough)

**Step 5: Review weekly report**

Run:
```bash
cat automation/reports/$(date +%Y-%m-%d)-analysis.md
```

Expected: Comprehensive performance analysis

**Step 6: Test notification system**

Run:
```bash
./automation/notification_helper.sh "✅ Integration testing complete!"
```

Expected: iMessage received

**Step 7: Verify launchd will trigger**

Run:
```bash
# Check next run time for daily job
launchctl list com.learningscience.daily
```

Expected: Job info displayed

**Step 8: Final commit**

Run:
```bash
git add -A
git commit -m "feat: complete autonomous video system integration

- Daily pipeline with topic generation
- Weekly performance optimization
- YouTube channel-specific uploads
- iMessage notifications
- launchd scheduling
- Prompt injection protection
- Full integration tested"
```

Expected: Final integration committed

---

## Task 11: Create Setup Script

**Files:**
- Create: `setup_automation.sh`

**Step 1: Create comprehensive setup script**

Create `setup_automation.sh`:
```bash
#!/bin/bash
# Setup autonomous video system

set -e

echo "🤖 Setting up autonomous video system..."
echo ""

# Get project directory
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

# Create directory structure
echo "📁 Creating directory structure..."
mkdir -p automation/{config,state,logs,reports}

# Check for existing configs
if [ ! -f "automation/config/automation_config.json" ]; then
    echo "  Creating automation_config.json..."
    cat > automation/config/automation_config.json <<'EOF'
{
  "scheduling": {
    "daily_run_time": "09:00",
    "timezone": "America/Chicago",
    "weekly_analysis_day": "Sunday",
    "weekly_analysis_time": "10:00"
  },
  "youtube": {
    "channel_handle": "@LearningScienceMusic",
    "privacy_status": "private",
    "default_category": "Education",
    "credentials_path": "config/youtube_credentials.json"
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
    "categories": ["biology", "chemistry", "physics", "earth_science"],
    "prefer_trending": false
  }
}
EOF
fi

if [ ! -f "automation/config/guardrails.json" ]; then
    echo "  Creating guardrails.json..."
    cat > automation/config/guardrails.json <<'EOF'
{
  "safe_ranges": {
    "video_duration": [15, 120],
    "max_media_items": [5, 30],
    "min_media_items": [3, 15],
    "fps": [24, 60],
    "tone_description_max_length": 200
  },
  "allowed_changes": [
    "tone adjustments",
    "duration tweaks",
    "media variety",
    "posting time"
  ],
  "forbidden_changes": [
    "API keys",
    "channel selection",
    "privacy status",
    "resolution",
    "file paths",
    "system commands"
  ],
  "confidence_thresholds": {
    "auto_apply": 0.8,
    "flag_for_review": 0.5,
    "document_only": 0.0
  }
}
EOF
fi

# Create state files
if [ ! -f "automation/state/topic_history.json" ]; then
    echo '{"topics": []}' > automation/state/topic_history.json
fi

if [ ! -f "automation/state/optimization_state.json" ]; then
    echo '{"optimizations": [], "last_analysis": null}' > automation/state/optimization_state.json
fi

# Install Python dependencies
echo ""
echo "📦 Installing Python dependencies..."
./venv/bin/pip install -q google-api-python-client google-auth-httplib2 google-auth-oauthlib

# Create launchd plists
echo ""
echo "⏰ Creating launchd plists..."

cat > ~/Library/LaunchAgents/com.learningscience.daily.plist <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.learningscience.daily</string>
    <key>ProgramArguments</key>
    <array>
        <string>$PROJECT_DIR/automation/daily_pipeline.sh</string>
    </array>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>9</integer>
        <key>Minute</key>
        <integer>0</integer>
    </dict>
    <key>WorkingDirectory</key>
    <string>$PROJECT_DIR</string>
    <key>StandardOutPath</key>
    <string>$PROJECT_DIR/automation/logs/launchd_daily.log</string>
    <key>StandardErrorPath</key>
    <string>$PROJECT_DIR/automation/logs/launchd_daily_error.log</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
    </dict>
</dict>
</plist>
EOF

cat > ~/Library/LaunchAgents/com.learningscience.weekly.plist <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.learningscience.weekly</string>
    <key>ProgramArguments</key>
    <array>
        <string>$PROJECT_DIR/venv/bin/python3</string>
        <string>$PROJECT_DIR/automation/weekly_optimizer.py</string>
    </array>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Weekday</key>
        <integer>0</integer>
        <key>Hour</key>
        <integer>10</integer>
        <key>Minute</key>
        <integer>0</integer>
    </dict>
    <key>WorkingDirectory</key>
    <string>$PROJECT_DIR</string>
    <key>StandardOutPath</key>
    <string>$PROJECT_DIR/automation/logs/launchd_weekly.log</string>
    <key>StandardErrorPath</key>
    <string>$PROJECT_DIR/automation/logs/launchd_weekly_error.log</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
    </dict>
</dict>
</plist>
EOF

echo ""
echo "✅ Setup complete!"
echo ""
echo "Next steps:"
echo ""
echo "1. Test components manually:"
echo "   ./automation/topic_generator.py"
echo "   ./automation/daily_pipeline.sh"
echo "   ./automation/weekly_optimizer.py"
echo ""
echo "2. Load launchd jobs (when ready for automation):"
echo "   launchctl load ~/Library/LaunchAgents/com.learningscience.daily.plist"
echo "   launchctl load ~/Library/LaunchAgents/com.learningscience.weekly.plist"
echo ""
echo "3. Configuration files:"
echo "   - automation/config/automation_config.json (change privacy status here when ready to go public)"
echo "   - automation/config/guardrails.json (safety boundaries)"
echo ""
echo "4. To go public later:"
echo "   jq '.youtube.privacy_status = \"public\"' automation/config/automation_config.json > tmp && mv tmp automation/config/automation_config.json"
echo ""
```

**Step 2: Make executable**

Run:
```bash
chmod +x setup_automation.sh
```

Expected: Script is executable

**Step 3: Test setup script**

Run:
```bash
./setup_automation.sh
```

Expected: All components set up successfully

**Step 4: Commit setup script**

Run:
```bash
git add setup_automation.sh
git commit -m "feat: add comprehensive automation setup script"
```

Expected: Setup script committed

---

## Final Verification

**Step 1: Verify all files created**

Run:
```bash
ls -la automation/
ls -la automation/config/
ls -la automation/state/
ls -la ~/Library/LaunchAgents/com.learningscience.*
```

Expected: All automation files and launchd plists exist

**Step 2: Verify all scripts are executable**

Run:
```bash
ls -l automation/*.{sh,py} | grep -E '^-rwx'
```

Expected: All scripts have execute permissions

**Step 3: Verify launchd jobs**

Run:
```bash
launchctl list | grep learningscience
```

Expected: Both jobs loaded and ready

**Step 4: Test notification end-to-end**

Run:
```bash
./automation/notification_helper.sh "🎉 Autonomous video system is ready!"
```

Expected: iMessage received at 914-844-4402

**Step 5: Review implementation plan**

Confirm all tasks completed:
- ✅ Directory structure
- ✅ Notification helper
- ✅ Topic generator
- ✅ YouTube channel selection
- ✅ Daily pipeline
- ✅ Python dependencies
- ✅ Change guardian
- ✅ Weekly optimizer
- ✅ launchd plists
- ✅ Integration testing
- ✅ Setup script

**Step 6: Final commit and tag**

Run:
```bash
git tag -a v1.0-autonomous-system -m "Release: Autonomous video system v1.0"
git push origin main --tags
```

Expected: Code pushed with release tag

---

## Usage Instructions

### Daily Operations

**Manual trigger:**
```bash
./automation/daily_pipeline.sh
```

**Check logs:**
```bash
tail -f automation/logs/daily_$(date +%Y-%m-%d).log
```

### Weekly Operations

**Manual trigger:**
```bash
./automation/weekly_optimizer.py
```

**View report:**
```bash
cat automation/reports/$(date +%Y-%m-%d)-analysis.md
```

### Configuration Changes

**Go public:**
```bash
jq '.youtube.privacy_status = "public"' automation/config/automation_config.json > tmp && mv tmp automation/config/automation_config.json
```

**Enable optimization:**
```bash
jq '.optimization.enabled = true' automation/config/automation_config.json > tmp && mv tmp automation/config/automation_config.json
```

**Change posting time:**
```bash
jq '.scheduling.daily_run_time = "11:00"' automation/config/automation_config.json > tmp && mv tmp automation/config/automation_config.json
# Then reload launchd job
launchctl unload ~/Library/LaunchAgents/com.learningscience.daily.plist
launchctl load ~/Library/LaunchAgents/com.learningscience.daily.plist
```

### Troubleshooting

**Daily pipeline failed:**
1. Check `automation/logs/daily_YYYY-MM-DD.log`
2. Check `automation/logs/launchd_daily_error.log`
3. Run manually to debug: `./automation/daily_pipeline.sh`

**No notifications:**
1. Test: `./automation/notification_helper.sh "test"`
2. Check Messages.app is signed in to iMessage
3. Check phone number in config

**YouTube upload failed:**
1. Check credentials: `ls config/youtube_credentials.json`
2. Re-authenticate: `rm config/youtube_token.pickle`
3. Test: `./automation/youtube_channel_helper.py --list-channels`

---

## Success Criteria

- ✅ Daily pipeline runs automatically at 9 AM CST
- ✅ Videos upload to @LearningScienceMusic (private initially)
- ✅ iMessage notifications received for success/failure
- ✅ Weekly analysis runs Sunday 10 AM CST
- ✅ Weekly reports generated in automation/reports/
- ✅ Safe config changes applied automatically
- ✅ All logs captured in automation/logs/
- ✅ Topic history tracked to avoid repeats
- ✅ Prompt injection protection active
- ✅ Manual override capability maintained
