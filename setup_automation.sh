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
