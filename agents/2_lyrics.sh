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
claude -p "$(cat $TEMP_PROMPT)" --output-format json > outputs/lyrics_raw.json

# Clean up temp prompt
rm "$TEMP_PROMPT"

# Extract the actual result from Claude's wrapper and parse the embedded JSON string
python3 << 'EOF'
import json
import sys

try:
    # Read Claude's output wrapper
    with open('outputs/lyrics_raw.json') as f:
        wrapper = json.load(f)

    # Check if it's an error
    if wrapper.get('is_error', False):
        print(f"❌ Error from Claude: {wrapper.get('result', 'Unknown error')}")
        sys.exit(1)

    # Look for JSON in permission denials (where Claude tried to write)
    if 'permission_denials' in wrapper and wrapper['permission_denials']:
        for denial in wrapper['permission_denials']:
            if denial.get('tool_name') == 'Write' and 'tool_input' in denial:
                content = denial['tool_input'].get('content', '')
                if content:
                    # This is the actual JSON we want
                    data = json.loads(content)
                    with open('outputs/lyrics.json', 'w') as f:
                        json.dump(data, f, indent=2)
                    print("✅ Extracted lyrics data from Claude response")
                    sys.exit(0)

    print("❌ Could not find valid JSON in Claude response")
    sys.exit(1)

except Exception as e:
    print(f"❌ Error processing Claude output: {e}")
    sys.exit(1)
EOF

if [ $? -ne 0 ]; then
    echo "❌ Failed to extract lyrics data"
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
