#!/bin/bash

set -e

# Use OUTPUT_DIR from pipeline or default to outputs/
OUTPUT_DIR="${OUTPUT_DIR:-outputs}"

echo "🎨 Media Curator Agent: Selecting visuals..."

# Check for required inputs
if [ ! -f "${OUTPUT_DIR}/research.json" ]; then
    echo "❌ Error: ${OUTPUT_DIR}/research.json not found"
    exit 1
fi

if [ ! -f "${OUTPUT_DIR}/lyrics.json" ]; then
    echo "❌ Error: ${OUTPUT_DIR}/lyrics.json not found"
    exit 1
fi

# Read data
RESEARCH=$(cat ${OUTPUT_DIR}/research.json)
LYRICS=$(cat ${OUTPUT_DIR}/lyrics.json)

# Check for visual rankings (optional)
VISUAL_RANKINGS=""
if [ -f "${OUTPUT_DIR}/visual_rankings.json" ]; then
    echo "  📊 Using visual rankings for media selection"
    VISUAL_RANKINGS=$(cat ${OUTPUT_DIR}/visual_rankings.json)
fi

# Create temp file with substituted prompt
TEMP_PROMPT=$(mktemp)
sed "s|{{OUTPUT_PATH}}|${OUTPUT_DIR}/media_plan.json|g" agents/prompts/curator_prompt.md > "$TEMP_PROMPT"

# Add data to the end
echo "" >> "$TEMP_PROMPT"
echo "## Research Data" >> "$TEMP_PROMPT"
echo '```json' >> "$TEMP_PROMPT"
echo "$RESEARCH" >> "$TEMP_PROMPT"
echo '```' >> "$TEMP_PROMPT"
echo "" >> "$TEMP_PROMPT"
echo "## Lyrics Data" >> "$TEMP_PROMPT"
echo '```json' >> "$TEMP_PROMPT"
echo "$LYRICS" >> "$TEMP_PROMPT"
echo '```' >> "$TEMP_PROMPT"

if [ -n "$VISUAL_RANKINGS" ]; then
    echo "" >> "$TEMP_PROMPT"
    echo "## Visual Rankings Data" >> "$TEMP_PROMPT"
    echo '```json' >> "$TEMP_PROMPT"
    echo "$VISUAL_RANKINGS" >> "$TEMP_PROMPT"
    echo '```' >> "$TEMP_PROMPT"
fi

# Call Claude Code CLI - it will write directly to outputs/media_plan.json
echo "  Calling Claude Code for media curation..."
claude -p "$(cat $TEMP_PROMPT)" --dangerously-skip-permissions > /dev/null 2>&1

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
python3 agents/download_media.py
