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
