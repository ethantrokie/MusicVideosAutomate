#!/bin/bash
# Setup launchd scheduling for daily automation
# Run this to enable automatic daily video generation

set -e

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "🤖 Setting up daily automation scheduling..."
echo ""

# Create daily launchd plist
PLIST_PATH="$HOME/Library/LaunchAgents/com.learningscience.daily.plist"

cat > "$PLIST_PATH" <<EOF
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

echo "✅ Created launchd plist at:"
echo "   $PLIST_PATH"
echo ""

# Load the job
echo "Loading launchd job..."
launchctl unload "$PLIST_PATH" 2>/dev/null || true
launchctl load "$PLIST_PATH"

echo ""
echo "✅ Daily automation is now enabled!"
echo ""
echo "Schedule: Every day at 9:00 AM (America/Chicago timezone)"
echo "Logs: automation/logs/daily_YYYY-MM-DD.log"
echo ""
echo "To verify the job is loaded:"
echo "  launchctl list | grep learningscience"
echo ""
echo "To unload (disable automation):"
echo "  launchctl unload ~/Library/LaunchAgents/com.learningscience.daily.plist"
echo ""
echo "To test manually right now:"
echo "  ./automation/daily_pipeline.sh"
echo ""
