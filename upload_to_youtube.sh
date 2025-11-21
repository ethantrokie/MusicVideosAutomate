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

# Function to generate metadata based on video type
generate_metadata() {
    local video_type=$1
    local topic=$2

    case $video_type in
        full)
            TITLE="${topic} - Full Educational Song"
            DESCRIPTION="Learn about ${topic} through music! Full version.

Watch the Shorts versions:
- Musical Hook: [PLACEHOLDER_HOOK]
- Educational Highlight: [PLACEHOLDER_EDU]

#education #learning #science"
            VIDEO_FILE="full.mp4"
            ;;
        short_hook)
            TITLE="${topic} 🎵 #Shorts"
            DESCRIPTION="${topic}

Watch the full version: [PLACEHOLDER_FULL]

#shorts #education #learning"
            VIDEO_FILE="short_hook.mp4"
            ;;
        short_educational)
            TITLE="${topic} Explained 📚 #Shorts"
            DESCRIPTION="${topic} - Key concept explained!

Watch the full version: [PLACEHOLDER_FULL]

#shorts #education #learning"
            VIDEO_FILE="short_educational.mp4"
            ;;
        *)
            # Default fallback
            TITLE="${topic} | Educational Video"
            DESCRIPTION="Learn about ${topic}!

#education #learning"
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

# Extract video ID from output (youtube_channel_helper.py prints it)
# Assuming output format contains "Video ID: ABC123"
VIDEO_ID=$(echo "$UPLOAD_OUTPUT" | grep -o "Video ID: [A-Za-z0-9_-]*" | cut -d' ' -f3)

if [ -n "$VIDEO_ID" ]; then
    # Save video ID to file for cross-linking
    echo "$VIDEO_ID" > "${RUN_DIR}/video_id_${VIDEO_TYPE}.txt"
    echo "  Video ID: $VIDEO_ID"
    echo "  Saved to: ${RUN_DIR}/video_id_${VIDEO_TYPE}.txt"
fi

echo "✅ Upload complete!"
