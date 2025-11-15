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

# Call Claude Code CLI
echo "  Calling Claude Code for media curation..."
claude -p "$(cat $TEMP_PROMPT)" --output-format json > outputs/media_plan_raw.json

# Clean up temp prompt
rm "$TEMP_PROMPT"

# Extract the actual result from Claude's wrapper and parse the embedded JSON string
python3 << 'EOF'
import json
import sys
import re

try:
    # Read Claude's output wrapper
    with open('outputs/media_plan_raw.json') as f:
        wrapper = json.load(f)

    # Check if it's an error
    if wrapper.get('is_error', False):
        print(f"❌ Error from Claude: {wrapper.get('result', 'Unknown error')}")
        sys.exit(1)

    # Strategy 1: Look for JSON in permission denials (where Claude tried to write)
    if 'permission_denials' in wrapper and wrapper['permission_denials']:
        for denial in wrapper['permission_denials']:
            if denial.get('tool_name') == 'Write' and 'tool_input' in denial:
                content = denial['tool_input'].get('content', '')
                if content:
                    # This is the actual JSON we want
                    data = json.loads(content)
                    with open('outputs/media_plan.json', 'w') as f:
                        json.dump(data, f, indent=2)
                    print("✅ Extracted media plan data from Claude response")
                    sys.exit(0)

    # Strategy 2: Look for JSON in the result field (markdown code block)
    result_text = wrapper.get('result', '')
    if result_text:
        # Extract JSON from markdown code block
        json_match = re.search(r'```json\s*\n(.*?)\n```', result_text, re.DOTALL)
        if json_match:
            json_str = json_match.group(1)
            data = json.loads(json_str)
            with open('outputs/media_plan.json', 'w') as f:
                json.dump(data, f, indent=2)
            print("✅ Extracted media plan data from Claude response")
            sys.exit(0)

    print("❌ Could not find valid JSON in Claude response")
    sys.exit(1)

except Exception as e:
    print(f"❌ Error processing Claude output: {e}")
    sys.exit(1)
EOF

if [ $? -ne 0 ]; then
    echo "❌ Failed to extract media plan data"
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
