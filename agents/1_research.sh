#!/bin/bash

set -e

echo "🔬 Research Agent: Starting web research..."

# Read input
if [ ! -f "input/idea.txt" ]; then
    echo "❌ Error: input/idea.txt not found"
    echo "Create it with: echo 'Your topic. Tone: description' > input/idea.txt"
    exit 1
fi

IDEA=$(cat input/idea.txt)

# Parse topic and tone (simple split on "Tone:")
if [[ $IDEA == *"Tone:"* ]]; then
    TOPIC="${IDEA%%Tone:*}"
    TONE="${IDEA##*Tone:}"
else
    TOPIC="$IDEA"
    TONE="educational and clear"
fi

# Clean up whitespace
TOPIC=$(echo "$TOPIC" | xargs)
TONE=$(echo "$TONE" | xargs)

echo "  Topic: $TOPIC"
echo "  Tone: $TONE"

# Create temp file with substituted prompt
TEMP_PROMPT=$(mktemp)
sed "s/{{TOPIC}}/$TOPIC/g; s/{{TONE}}/$TONE/g" agents/prompts/researcher_prompt.md > "$TEMP_PROMPT"

# Call Claude Code CLI
echo "  Calling Claude Code for research..."
claude -p "$(cat $TEMP_PROMPT)" --output-format json --dangerously-skip-permissions > outputs/research_raw.json

# Clean up temp prompt
rm "$TEMP_PROMPT"

# Extract the actual result from Claude's wrapper and parse the embedded JSON string
python3 << 'EOF'
import json
import sys
import re

try:
    # Read Claude's output wrapper
    with open('outputs/research_raw.json') as f:
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
                    with open('outputs/research.json', 'w') as f:
                        json.dump(data, f, indent=2)
                    print("✅ Extracted research data from Claude response")
                    sys.exit(0)

    # Strategy 2: Look for JSON in the result field (markdown code block)
    result_text = wrapper.get('result', '')
    if result_text:
        # Try markdown code block first
        json_match = re.search(r'```json\s*\n(.*?)\n```', result_text, re.DOTALL)
        if json_match:
            json_str = json_match.group(1)
            data = json.loads(json_str)
            with open('outputs/research.json', 'w') as f:
                json.dump(data, f, indent=2)
            print("✅ Extracted research data from Claude response")
            sys.exit(0)

        # Strategy 3: Try to parse result as raw JSON
        try:
            data = json.loads(result_text)
            with open('outputs/research.json', 'w') as f:
                json.dump(data, f, indent=2)
            print("✅ Extracted research data from Claude response")
            sys.exit(0)
        except json.JSONDecodeError:
            pass

    print("❌ Could not find valid JSON in Claude response")
    sys.exit(1)

except Exception as e:
    print(f"❌ Error processing Claude output: {e}")
    sys.exit(1)
EOF

if [ $? -ne 0 ]; then
    echo "❌ Failed to extract research data"
    exit 1
fi

echo "✅ Research complete: outputs/research.json"
echo ""
python3 -c "
import json
data = json.load(open('outputs/research.json'))
print(f\"  Found {len(data['key_facts'])} facts\")
print(f\"  Found {len(data['media_suggestions'])} media suggestions\")
"
