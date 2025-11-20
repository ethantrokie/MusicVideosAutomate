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
