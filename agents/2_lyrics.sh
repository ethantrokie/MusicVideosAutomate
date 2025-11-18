#!/bin/bash

set -e

# Use OUTPUT_DIR from pipeline or default to outputs/
OUTPUT_DIR="${OUTPUT_DIR:-outputs}"

echo "🎵 Lyrics Agent: Generating song lyrics..."

# Check for research output
if [ ! -f "${OUTPUT_DIR}/research.json" ]; then
    echo "❌ Error: ${OUTPUT_DIR}/research.json not found"
    echo "Run research agent first: ./agents/1_research.sh"
    exit 1
fi

# Read research data
RESEARCH=$(cat ${OUTPUT_DIR}/research.json)
TONE=$(python3 -c "import json; print(json.load(open('${OUTPUT_DIR}/research.json'))['tone'])")

echo "  Tone: $TONE"

# Create temp file with substituted prompt
TEMP_PROMPT=$(mktemp)
sed "s/{{TONE}}/$TONE/g; s|{{OUTPUT_PATH}}|${OUTPUT_DIR}/lyrics.json|g" agents/prompts/lyricist_prompt.md > "$TEMP_PROMPT"

# Add research data to the end
echo "" >> "$TEMP_PROMPT"
echo "## Research Data" >> "$TEMP_PROMPT"
echo '```json' >> "$TEMP_PROMPT"
echo "$RESEARCH" >> "$TEMP_PROMPT"
echo '```' >> "$TEMP_PROMPT"

# Call Claude Code CLI - it will write directly to outputs/lyrics.json
echo "  Calling Claude Code for lyrics..."
claude -p "$(cat $TEMP_PROMPT)" --dangerously-skip-permissions > /dev/null 2>&1

# Clean up temp prompt
rm "$TEMP_PROMPT"

# Verify the file was created and is valid JSON
if [ ! -f "${OUTPUT_DIR}/lyrics.json" ]; then
    echo "❌ Error: Claude did not create ${OUTPUT_DIR}/lyrics.json"
    exit 1
fi

if ! python3 -c "import json; json.load(open('${OUTPUT_DIR}/lyrics.json'))" 2>/dev/null; then
    echo "❌ Error: ${OUTPUT_DIR}/lyrics.json is not valid JSON"
    exit 1
fi

# Extract lyrics and music prompt to separate files for easier access
python3 -c "
import json
data = json.load(open('${OUTPUT_DIR}/lyrics.json'))
with open('${OUTPUT_DIR}/lyrics.txt', 'w') as f:
    f.write(data['lyrics'])
with open('${OUTPUT_DIR}/music_prompt.txt', 'w') as f:
    f.write(data['music_prompt'])
print(f\"  Duration: {data['estimated_duration_seconds']} seconds\")
print(f\"  Structure: {data['structure']}\")
"

echo "✅ Lyrics complete: ${OUTPUT_DIR}/lyrics.txt, ${OUTPUT_DIR}/music_prompt.txt"
