#!/bin/bash
# Upload video to YouTube with channel selection support

set -e

# Default values
PRIVACY="unlisted"
RUN_DIR=""
CHANNEL=""
VIDEO_TYPE="full"  # full, short_hook, short_educational

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
        --type=*)
            VIDEO_TYPE="${1#*=}"
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

# Function to generate topic-based hashtags
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
            TITLE="${topic}"
            DESCRIPTION="Learn about ${topic} through music! Full version.

Watch the Shorts versions:
- Musical Hook: [PLACEHOLDER_HOOK]
- Educational Highlight: [PLACEHOLDER_EDU]

${hashtags}"
            VIDEO_FILE="full.mp4"
            ;;
        short_hook)
            TITLE="${topic} 🎵"
            DESCRIPTION="${topic}

Watch the full version: [PLACEHOLDER_FULL]

${hashtags}"
            VIDEO_FILE="short_hook.mp4"
            ;;
        short_educational)
            TITLE="${topic} 🎵"
            DESCRIPTION="${topic} - Key concept explained!

Watch the full version: [PLACEHOLDER_FULL]

${hashtags}"
            VIDEO_FILE="short_educational.mp4"
            ;;
        *)
            # Default fallback
            TITLE="${topic}"
            DESCRIPTION="Learn about ${topic}!

${hashtags}"
            VIDEO_FILE="final_video.mp4"
            ;;
    esac
}

# Use latest run if not specified
if [ -z "$RUN_DIR" ]; then
    RUN_DIR="outputs/current"
fi

# Try to get video_title from research.json first (preferred)
RESEARCH_FILE="${RUN_DIR}/research.json"
if [ -f "$RESEARCH_FILE" ]; then
    TOPIC=$(python3 -c "import json; data=json.load(open('$RESEARCH_FILE')); print(data.get('video_title', ''))" 2>/dev/null)
fi

# Fallback to old method if video_title not available
if [ -z "$TOPIC" ]; then
    echo "  ⚠️  No video_title in research.json, falling back to idea.txt extraction"
    RAW_TOPIC=$(head -1 input/idea.txt | cut -d'.' -f1)
    # Extract core topic: Take first 3-6 words, capitalize properly
    TOPIC=$(echo "$RAW_TOPIC" | sed -E 's/^Explain //' | awk '{for(i=1;i<=6 && i<=NF;i++) printf "%s ", $i}' | sed 's/ $//' | awk '{print toupper(substr($0,1,1)) substr($0,2)}')
    # If topic is still too long (>65 chars), truncate to first 5 words
    if [ ${#TOPIC} -gt 65 ]; then
        TOPIC=$(echo "$RAW_TOPIC" | sed -E 's/^Explain //' | awk '{printf "%s %s %s %s %s", $1, $2, $3, $4, $5}' | awk '{print toupper(substr($0,1,1)) substr($0,2)}')
    fi
fi

# Generate metadata based on video type
generate_metadata "$VIDEO_TYPE" "$TOPIC"

VIDEO_PATH="$RUN_DIR/$VIDEO_FILE"

if [ ! -f "$VIDEO_PATH" ]; then
    echo "❌ Error: Video not found at $VIDEO_PATH"
    exit 1
fi

echo "📤 Uploading to YouTube..."
echo "  Type: $VIDEO_TYPE"
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

# Capture output which includes video ID
UPLOAD_OUTPUT=$(eval $UPLOAD_CMD)
echo "$UPLOAD_OUTPUT"

# Extract video ID from output URL format: "Video uploaded: https://youtube.com/watch?v=VIDEO_ID"
VIDEO_ID=$(echo "$UPLOAD_OUTPUT" | grep -oE 'watch\?v=([A-Za-z0-9_-]+)' | cut -d= -f2)

if [ -n "$VIDEO_ID" ]; then
    # Save video ID to file for cross-linking
    echo "$VIDEO_ID" > "${RUN_DIR}/video_id_${VIDEO_TYPE}.txt"
    echo "  Video ID: $VIDEO_ID"
    echo "  Saved to: ${RUN_DIR}/video_id_${VIDEO_TYPE}.txt"
fi

echo "✅ Upload complete!"
