#!/bin/bash
# Upload video to TikTok using TikTok Content Posting API

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
            echo "  --type=TYPE            Video type: full, short_hook (default: full)"
            echo "  --privacy=LEVEL        Privacy: public_to_everyone, mutual_follow_friends, self_only (default: public_to_everyone)"
            echo "  --help                 Show this help"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Function to generate topic-based hashtags (reused from upload_to_youtube.sh)
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
            TITLE="${topic} - Educational Music Video"
            CAPTION="Learn about ${topic} through music!

View full version on YouTube @learningsciencemusic

${hashtags}"
            VIDEO_FILE="full.mp4"
            ;;
        short_hook)
            TITLE="${topic}"
            CAPTION="${topic}

View full video on YouTube @learningsciencemusic

${hashtags}"
            VIDEO_FILE="short_hook.mp4"
            ;;
        *)
            # Default fallback
            TITLE="${topic} | Educational Video"
            CAPTION="Learn about ${topic}!

${hashtags}"
            VIDEO_FILE="final_video.mp4"
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
UPLOAD_OUTPUT=$(./automation/tiktok_uploader.py \
    --video "$VIDEO_PATH" \
    --title "$TITLE" \
    --caption "$CAPTION" \
    --privacy "$PRIVACY")

echo "$UPLOAD_OUTPUT"

# Extract video ID from JSON output
VIDEO_ID=$(echo "$UPLOAD_OUTPUT" | grep -o '"id": *"[^"]*"' | cut -d'"' -f4)

if [ -n "$VIDEO_ID" ]; then
    # Save video ID to file for cross-linking
    echo "$VIDEO_ID" > "${RUN_DIR}/tiktok_video_id_${VIDEO_TYPE}.txt"
    echo "  Video ID: $VIDEO_ID"
    echo "  Saved to: ${RUN_DIR}/tiktok_video_id_${VIDEO_TYPE}.txt"
fi

echo "✅ Upload complete!"
