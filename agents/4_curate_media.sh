#!/bin/bash

set -e

echo "🎨 Media Curator Agent: Selecting visuals..."

# Check for required inputs
if [ ! -f "outputs/research.json" ]; then
    echo "❌ Error: outputs/research.json not found"
    exit 1
fi

if [ ! -f "outputs/lyrics.json" ]; then
    echo "❌ Error: outputs/lyrics.json not found"
    exit 1
fi

# Read data
RESEARCH=$(cat outputs/research.json)
LYRICS=$(cat outputs/lyrics.json)

# Create temp file with substituted prompt
TEMP_PROMPT=$(mktemp)
cp agents/prompts/curator_prompt.md "$TEMP_PROMPT"

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

# Call Claude Code CLI - it will write directly to outputs/media_plan.json
echo "  Calling Claude Code for media curation..."
claude -p "$(cat $TEMP_PROMPT)" --dangerously-skip-permissions > /dev/null 2>&1

# Clean up temp prompt
rm "$TEMP_PROMPT"

# Verify the file was created and is valid JSON
if [ ! -f "outputs/media_plan.json" ]; then
    echo "❌ Error: Claude did not create outputs/media_plan.json"
    exit 1
fi

if ! python3 -c "import json; json.load(open('outputs/media_plan.json'))" 2>/dev/null; then
    echo "❌ Error: outputs/media_plan.json is not valid JSON"
    exit 1
fi

echo "✅ Media curation complete: outputs/media_plan.json"
echo ""
python3 -c "
import json
data = json.load(open('outputs/media_plan.json'))
print(f\"  Total shots: {data['total_shots']}\")
print(f\"  Duration: {data['total_duration']} seconds\")
print(f\"  Pacing: {data['pacing']}\")
"

# Download media
echo ""
python3 agents/download_media.py
