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
