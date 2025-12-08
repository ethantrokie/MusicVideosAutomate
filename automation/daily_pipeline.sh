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

# Detect which stage to resume from based on output files
detect_resume_stage() {
    local run_dir="$1"

    # Stage markers (in reverse order - check from latest to earliest)
    # Stage 9: Cross-linking complete (upload_results.json with both youtube and tiktok data)
    if [ -f "$run_dir/upload_results.json" ]; then
        # Check if cross-linking was actually completed by looking for both youtube and tiktok keys
        if jq -e '.youtube and .tiktok' "$run_dir/upload_results.json" >/dev/null 2>&1; then
            echo "10"  # All stages complete, start from 10 (will skip all)
            return
        fi
    fi

    # Stage 8: Upload complete (video_id files exist)
    if [ -f "$run_dir/video_id_full.txt" ]; then
        echo "9"  # Resume from cross-linking
        return
    fi

    # Stage 7: Subtitles complete (subtitles directory exists with SRT files)
    if [ -d "$run_dir/subtitles" ] && [ -n "$(ls -A "$run_dir/subtitles"/*.srt 2>/dev/null)" ]; then
        echo "8"  # Resume from upload
        return
    fi

    # Stage 6: Videos built (full.mp4, short_hook.mp4, short_educational.mp4)
    if [ -f "$run_dir/full.mp4" ] && [ -f "$run_dir/short_hook.mp4" ] && [ -f "$run_dir/short_educational.mp4" ]; then
        echo "7"  # Resume from subtitle generation
        return
    fi

    # Stage 5: Media curation complete (approved_media.json exists)
    if [ -f "$run_dir/approved_media.json" ]; then
        echo "6"  # Resume from video assembly
        return
    fi

    # Stage 4.5: Segment analysis complete (segments.json exists)
    if [ -f "$run_dir/segments.json" ]; then
        echo "5"  # Resume from media curation
        return
    fi

    # Stage 4: Music complete (song.mp3 exists)
    if [ -f "$run_dir/song.mp3" ]; then
        echo "5"  # Resume from segment analysis (Stage 4.5 in pipeline.sh is stage 5 for --start)
        return
    fi

    # Stage 3: Lyrics complete (lyrics.json exists)
    if [ -f "$run_dir/lyrics.json" ]; then
        echo "4"  # Resume from music generation
        return
    fi

    # Stage 2: Visual ranking complete (visual_rankings.json exists)
    if [ -f "$run_dir/visual_rankings.json" ]; then
        echo "3"  # Resume from lyrics
        return
    fi

    # Stage 1: Research complete (research.json exists)
    if [ -f "$run_dir/research.json" ]; then
        echo "2"  # Resume from visual ranking
        return
    fi

    # No stages complete, start from beginning
    echo "1"
}

run_pipeline() {
    local attempt=$1
    local failed_run_dir=$2

    # Only generate new topic on first attempt
    if [ $attempt -eq 1 ]; then
        log "Attempt $attempt: Generating new topic..."
        if ! ./automation/topic_generator.py >> "$LOG_FILE" 2>&1; then
            log "❌ Topic generation failed"
            return 1
        fi

        TOPIC=$(head -1 input/idea.txt | cut -d'.' -f1)
        log "Topic: $TOPIC"

        log "Running pipeline in express mode..."
        if ! ./pipeline.sh --express >> "$LOG_FILE" 2>&1; then
            log "❌ Pipeline failed"
            # Detect the failed run directory
            LATEST_RUN=$(ls -td outputs/runs/* 2>/dev/null | head -1)
            echo "$LATEST_RUN" > /tmp/failed_run_dir.txt
            return 1
        fi
    else
        # Resume from failed run directory
        if [ -z "$failed_run_dir" ] || [ ! -d "$failed_run_dir" ]; then
            log "❌ Cannot resume: failed run directory not found"
            return 1
        fi

        # Extract just the directory name (e.g., "20251129_081159" from "outputs/runs/20251129_081159")
        run_dir_name=$(basename "$failed_run_dir")

        # Detect which stage to resume from
        resume_stage=$(detect_resume_stage "$failed_run_dir")
        log "Detected resume stage: $resume_stage (based on completed artifacts)"

        log "Attempt $attempt: Resuming pipeline from $failed_run_dir at stage $resume_stage..."
        if ! ./pipeline.sh --resume="$run_dir_name" --express --start="$resume_stage" >> "$LOG_FILE" 2>&1; then
            log "❌ Pipeline resume failed"
            return 1
        fi
    fi

    # Pipeline already uploads videos in Stage 8 and cross-links in Stage 9
    log "✅ Pipeline complete (uploads and cross-linking done in pipeline)"
    return 0
}

main() {
    log "========================================="
    log "Daily Video Pipeline Starting"
    log "========================================="

    # Try up to 3 times: 1 initial attempt + 2 resume attempts
    attempt=1
    max_attempts=3
    failed_run_dir=""

    while [ $attempt -le $max_attempts ]; do
        if run_pipeline $attempt "$failed_run_dir"; then
            # Success!
            TOPIC=$(head -1 input/idea.txt | cut -d'.' -f1)

            # Extract video IDs from upload_results.json created by cross-linking
            LATEST_RUN=$(ls -td outputs/runs/* | head -1)
            UPLOAD_RESULTS="$LATEST_RUN/upload_results.json"

            if [ -f "$UPLOAD_RESULTS" ]; then
                FULL_VIDEO_ID=$(jq -r '.youtube.full_video.id' "$UPLOAD_RESULTS" 2>/dev/null || echo "unknown")
                TIKTOK_FULL_URL=$(jq -r '.tiktok.full_video.url // empty' "$UPLOAD_RESULTS" 2>/dev/null)
                TIKTOK_HOOK_URL=$(jq -r '.tiktok.hook_short.url // empty' "$UPLOAD_RESULTS" 2>/dev/null)
            else
                # Fallback to log parsing
                FULL_VIDEO_ID=$(grep "Video uploaded:.*full" "$LOG_FILE" | head -1 | grep -oE 'watch\?v=([A-Za-z0-9_-]+)' | cut -d'=' -f2 || echo "unknown")
                TIKTOK_FULL_URL=""
                TIKTOK_HOOK_URL=""
            fi

            log "✅ Daily videos published successfully with cross-linking"

            # Cleanup temp file on success
            rm -f /tmp/failed_run_dir.txt

            if [ "$NOTIFY_SUCCESS" = "true" ]; then
                NOTIFICATION="✅ Daily videos published!
Topic: $TOPIC
YouTube: https://youtube.com/watch?v=$FULL_VIDEO_ID"

                # Add TikTok URLs if available
                if [ -n "$TIKTOK_FULL_URL" ] || [ -n "$TIKTOK_HOOK_URL" ]; then
                    NOTIFICATION="$NOTIFICATION
"
                    [ -n "$TIKTOK_FULL_URL" ] && NOTIFICATION="$NOTIFICATION
TikTok (full): $TIKTOK_FULL_URL"
                    [ -n "$TIKTOK_HOOK_URL" ] && NOTIFICATION="$NOTIFICATION
TikTok (hook): $TIKTOK_HOOK_URL"
                fi

                NOTIFICATION="$NOTIFICATION
Status: $PRIVACY (multi-platform with cross-linking)"

                send_notification "$NOTIFICATION"
            fi

            exit 0
        fi

        # Pipeline failed - read the failed run directory
        if [ -f /tmp/failed_run_dir.txt ]; then
            failed_run_dir=$(cat /tmp/failed_run_dir.txt)
            log "Detected failed run directory: $failed_run_dir"
        fi

        if [ $attempt -eq $max_attempts ]; then
            # Final failure after all retries - try auto-debug
            log "❌ Pipeline failed after $max_attempts attempts (1 initial + 2 resume attempts)"
            log "🔧 Attempting auto-debug with Claude Code..."
            
            # Run auto-debugger
            if ./automation/auto_debugger.py "$failed_run_dir" "$LOG_FILE" >> "$LOG_FILE" 2>&1; then
                log "✅ Auto-debug fixed the issue!"
                # Cleanup temp file
                rm -f /tmp/failed_run_dir.txt
                exit 0
            fi
            
            log "❌ Auto-debug could not fix the issue"

            if [ "$NOTIFY_FAILURE" = "true" ]; then
                send_notification "❌ Daily video failed after $max_attempts attempts + auto-debug
Check logs: automation/logs/daily_$LOG_DATE.log"
            fi

            # Cleanup temp file
            rm -f /tmp/failed_run_dir.txt

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
