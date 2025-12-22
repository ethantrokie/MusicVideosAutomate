#!/bin/bash

set -e

# Use OUTPUT_DIR from pipeline or default to outputs/
OUTPUT_DIR="${OUTPUT_DIR:-outputs}"
DURATION="${DURATION:-60}"  # Default to 60 for backward compatibility

# Parse command-line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --duration)
            DURATION="$2"
            shift 2
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

echo "🎨 Media Curator Agent: Selecting visuals..."

# Check for required inputs
if [ ! -f "${OUTPUT_DIR}/visual_rankings.json" ]; then
    echo "❌ Error: ${OUTPUT_DIR}/visual_rankings.json not found"
    echo "Run Stage 3.6 (visual ranking) first"
    exit 1
fi

if [ ! -f "${OUTPUT_DIR}/lyrics.json" ]; then
    echo "❌ Error: ${OUTPUT_DIR}/lyrics.json not found"
    exit 1
fi

# Read data
VISUAL_RANKINGS=$(cat ${OUTPUT_DIR}/visual_rankings.json)
LYRICS=$(cat ${OUTPUT_DIR}/lyrics.json)

echo "  📊 Using lyric-tagged ranked media"

# Create temp file with substituted prompt
TEMP_PROMPT=$(mktemp)
sed -e "s|{{OUTPUT_PATH}}|${OUTPUT_DIR}/media_plan.json|g" \
    -e "s|{{VIDEO_DURATION}}|${DURATION}|g" \
    agents/prompts/curator_prompt.md > "$TEMP_PROMPT"

# Add data to the end
echo "" >> "$TEMP_PROMPT"
echo "## Lyric-Tagged Ranked Media" >> "$TEMP_PROMPT"
echo '```json' >> "$TEMP_PROMPT"
echo "$VISUAL_RANKINGS" >> "$TEMP_PROMPT"
echo '```' >> "$TEMP_PROMPT"
echo "" >> "$TEMP_PROMPT"
echo "## Lyrics Data" >> "$TEMP_PROMPT"
echo '```json' >> "$TEMP_PROMPT"
echo "$LYRICS" >> "$TEMP_PROMPT"
echo '```' >> "$TEMP_PROMPT"

# Call Claude Code CLI - it will write directly to outputs/media_plan.json
echo "  Calling Claude Code for media curation..."
/Users/ethantrokie/.npm-global/bin/claude -p "$(cat $TEMP_PROMPT)" --model claude-sonnet-4-5 --dangerously-skip-permissions

# Clean up temp prompt
rm "$TEMP_PROMPT"

# Verify the file was created and is valid JSON
if [ ! -f "${OUTPUT_DIR}/media_plan.json" ]; then
    echo "❌ Error: Claude did not create ${OUTPUT_DIR}/media_plan.json"
    exit 1
fi

if ! python3 -c "import json; json.load(open('${OUTPUT_DIR}/media_plan.json'))" 2>/dev/null; then
    echo "❌ Error: ${OUTPUT_DIR}/media_plan.json is not valid JSON"
    exit 1
fi

echo "✅ Media curation complete: ${OUTPUT_DIR}/media_plan.json"
echo "  Target duration: ${DURATION}s"
echo ""
python3 -c "
import json
data = json.load(open('${OUTPUT_DIR}/media_plan.json'))
print(f\"  Total shots: {data['total_shots']}\")
print(f\"  Duration: {data['total_duration']} seconds\")
print(f\"  Pacing: {data['pacing']}\")
"

# Download media
echo ""
./venv/bin/python3 agents/download_media.py
