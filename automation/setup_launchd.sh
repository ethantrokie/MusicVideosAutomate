#!/bin/bash
# Setup launchd scheduling for daily automation and hourly queue processing
# Run this to enable automatic daily video generation and staggered uploads

set -e

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "🤖 Setting up automation scheduling..."
echo ""

# Ensure logs directory exists
mkdir -p "$PROJECT_DIR/automation/logs"

# ============================================================
# 1. Daily Pipeline Job (runs at 9 AM)
# ============================================================
DAILY_PLIST_PATH="$HOME/Library/LaunchAgents/com.learningscience.daily.plist"

cat > "$DAILY_PLIST_PATH" <<EOF
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

echo "✅ Created daily pipeline plist at:"
echo "   $DAILY_PLIST_PATH"

# Load the daily job
echo "Loading daily pipeline job..."
launchctl unload "$DAILY_PLIST_PATH" 2>/dev/null || true
launchctl load "$DAILY_PLIST_PATH"

# ============================================================
# 2. Hourly Queue Processor Job (runs every hour at minute 0)
# ============================================================
QUEUE_PLIST_PATH="$HOME/Library/LaunchAgents/com.learningscience.queue.plist"

cat > "$QUEUE_PLIST_PATH" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.learningscience.queue</string>
    <key>ProgramArguments</key>
    <array>
        <string>$PROJECT_DIR/venv/bin/python3</string>
        <string>$PROJECT_DIR/automation/youtube_queue_processor.py</string>
        <string>--process</string>
    </array>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Minute</key>
        <integer>0</integer>
    </dict>
    <key>WorkingDirectory</key>
    <string>$PROJECT_DIR</string>
    <key>StandardOutPath</key>
    <string>$PROJECT_DIR/automation/logs/launchd_queue.log</string>
    <key>StandardErrorPath</key>
    <string>$PROJECT_DIR/automation/logs/launchd_queue_error.log</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
    </dict>
</dict>
</plist>
EOF

echo "✅ Created queue processor plist at:"
echo "   $QUEUE_PLIST_PATH"

# Load the queue job
echo "Loading queue processor job..."
launchctl unload "$QUEUE_PLIST_PATH" 2>/dev/null || true
launchctl load "$QUEUE_PLIST_PATH"

echo ""
echo "✅ Automation scheduling is now enabled!"
echo ""
echo "Jobs configured:"
echo "  1. Daily Pipeline:    Every day at 9:00 AM"
echo "  2. Queue Processor:   Every hour at :00"
echo ""
echo "Staggered YouTube upload schedule:"
echo "  - Day 0: Full video + Hook short (uploaded immediately)"
echo "  - Day 1: Educational short (8 AM Central)"
echo "  - Day 2: Intro short (8 AM Central)"
echo ""
echo "To verify jobs are loaded:"
echo "  launchctl list | grep learningscience"
echo ""
echo "To check queue status:"
echo "  python3 automation/youtube_queue_processor.py status"
echo ""
echo "To unload (disable automation):"
echo "  launchctl unload ~/Library/LaunchAgents/com.learningscience.daily.plist"
echo "  launchctl unload ~/Library/LaunchAgents/com.learningscience.queue.plist"
echo ""
echo "Logs:"
echo "  - Daily pipeline:  automation/logs/launchd_daily.log"
echo "  - Queue processor: automation/logs/launchd_queue.log"
echo ""
echo "To test manually:"
echo "  ./automation/daily_pipeline.sh"
echo "  python3 automation/youtube_queue_processor.py --process --dry-run"
echo ""
