#!/bin/bash

set -e

# Use OUTPUT_DIR from pipeline or default to outputs/
OUTPUT_DIR="${OUTPUT_DIR:-outputs}"

echo "🎬 Lyric Media Search Agent: Finding videos for lyrics..."

# Check for required inputs
if [ ! -f "${OUTPUT_DIR}/lyrics.json" ]; then
    echo "❌ Error: ${OUTPUT_DIR}/lyrics.json not found"
    exit 1
fi

if [ ! -f "${OUTPUT_DIR}/research.json" ]; then
    echo "❌ Error: ${OUTPUT_DIR}/research.json not found (needed for topic context)"
    exit 1
fi

# Read data
LYRICS=$(cat ${OUTPUT_DIR}/lyrics.json)
TOPIC=$(python3 -c "import json; print(json.load(open('${OUTPUT_DIR}/research.json'))['topic'])")

echo "  Topic: $TOPIC"
echo "  Analyzing lyrics for visual concepts..."

# Create temp file with substituted prompt
TEMP_PROMPT=$(mktemp)
sed "s|{{OUTPUT_PATH}}|${OUTPUT_DIR}/lyric_media.json|g; s/{{TOPIC}}/$TOPIC/g" agents/prompts/lyric_media_search_prompt.md > "$TEMP_PROMPT"

# Add lyrics data to the end
echo "" >> "$TEMP_PROMPT"
echo "## Lyrics Data" >> "$TEMP_PROMPT"
echo '```json' >> "$TEMP_PROMPT"
echo "$LYRICS" >> "$TEMP_PROMPT"
echo '```' >> "$TEMP_PROMPT"

# Call Claude Code CLI
echo "  Calling Claude Code for lyric-based media search..."
/Users/ethantrokie/.npm-global/bin/claude -p "$(cat $TEMP_PROMPT)" --model claude-sonnet-4-5 --dangerously-skip-permissions

# Clean up temp prompt
rm "$TEMP_PROMPT"

# Verify the file was created and is valid JSON
if [ ! -f "${OUTPUT_DIR}/lyric_media.json" ]; then
    echo "❌ Error: Claude did not create ${OUTPUT_DIR}/lyric_media.json"
    exit 1
fi

if ! python3 -c "import json; json.load(open('${OUTPUT_DIR}/lyric_media.json'))" 2>/dev/null; then
    echo "❌ Error: ${OUTPUT_DIR}/lyric_media.json is not valid JSON"
    exit 1
fi

echo "✅ Lyric media search complete: ${OUTPUT_DIR}/lyric_media.json"
echo ""
python3 -c "
import json
data = json.load(open('${OUTPUT_DIR}/lyric_media.json'))
print(f\"  Found {data['total_videos']} videos\")
print(f\"  Coverage: {data['lyric_coverage_percent']}%\")
print(f\"  Concepts: {data['concepts_extracted']}\")
"
