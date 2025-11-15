#!/bin/bash

set -e

echo "🎵 Lyrics Agent: Generating song lyrics..."

# Check for research output
if [ ! -f "outputs/research.json" ]; then
    echo "❌ Error: outputs/research.json not found"
    echo "Run research agent first: ./agents/1_research.sh"
    exit 1
fi

# Read research data
RESEARCH=$(cat outputs/research.json)
TONE=$(python3 -c "import json; print(json.load(open('outputs/research.json'))['tone'])")

echo "  Tone: $TONE"

# Create temp file with substituted prompt
TEMP_PROMPT=$(mktemp)
sed "s/{{TONE}}/$TONE/g" agents/prompts/lyricist_prompt.md > "$TEMP_PROMPT"

# Add research data to the end
echo "" >> "$TEMP_PROMPT"
echo "## Research Data" >> "$TEMP_PROMPT"
echo '```json' >> "$TEMP_PROMPT"
echo "$RESEARCH" >> "$TEMP_PROMPT"
echo '```' >> "$TEMP_PROMPT"

# Call Claude Code CLI
echo "  Calling Claude Code for lyrics..."
claude -p "$(cat $TEMP_PROMPT)" --output-format json > outputs/lyrics.json

# Clean up
rm "$TEMP_PROMPT"

# Validate JSON output
if ! python3 -c "import json; json.load(open('outputs/lyrics.json'))" 2>/dev/null; then
    echo "❌ Error: Invalid JSON output from Claude"
    exit 1
fi

# Extract lyrics and music prompt to separate files for easier access
python3 -c "
import json
data = json.load(open('outputs/lyrics.json'))
with open('outputs/lyrics.txt', 'w') as f:
    f.write(data['lyrics'])
with open('outputs/music_prompt.txt', 'w') as f:
    f.write(data['music_prompt'])
print(f\"  Duration: {data['estimated_duration_seconds']} seconds\")
print(f\"  Structure: {data['structure']}\")
"

echo "✅ Lyrics complete: outputs/lyrics.txt, outputs/music_prompt.txt"
