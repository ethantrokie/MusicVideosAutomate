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
claude -p "$(cat $TEMP_PROMPT)" --output-format json > outputs/research.json

# Clean up
rm "$TEMP_PROMPT"

# Validate JSON output
if ! python3 -c "import json; json.load(open('outputs/research.json'))" 2>/dev/null; then
    echo "❌ Error: Invalid JSON output from Claude"
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
