#!/bin/bash

set -e

# Use OUTPUT_DIR from pipeline or default to outputs/
OUTPUT_DIR="${OUTPUT_DIR:-outputs}"

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

# Clean up whitespace (without using xargs which breaks with apostrophes)
TOPIC="${TOPIC#"${TOPIC%%[![:space:]]*}"}"  # Remove leading whitespace
TOPIC="${TOPIC%"${TOPIC##*[![:space:]]}"}"  # Remove trailing whitespace
TONE="${TONE#"${TONE%%[![:space:]]*}"}"     # Remove leading whitespace
TONE="${TONE%"${TONE##*[![:space:]]}"}"     # Remove trailing whitespace

echo "  Topic: $TOPIC"
echo "  Tone: $TONE"

# Create temp file with substituted prompt
TEMP_PROMPT=$(mktemp)
sed "s/{{TOPIC}}/$TOPIC/g; s/{{TONE}}/$TONE/g; s|outputs/research.json|${OUTPUT_DIR}/research.json|g" agents/prompts/researcher_prompt.md > "$TEMP_PROMPT"

# Call Claude Code CLI - it will write directly to the timestamped research.json
echo "  Calling Claude Code for research..."
claude -p "$(cat $TEMP_PROMPT)" --dangerously-skip-permissions > /dev/null 2>&1

# Clean up temp prompt
rm "$TEMP_PROMPT"

# Verify the file was created and is valid JSON
if [ ! -f "${OUTPUT_DIR}/research.json" ]; then
    echo "❌ Error: Claude did not create ${OUTPUT_DIR}/research.json"
    exit 1
fi

if ! python3 -c "import json; json.load(open('${OUTPUT_DIR}/research.json'))" 2>/dev/null; then
    echo "❌ Error: ${OUTPUT_DIR}/research.json is not valid JSON"
    exit 1
fi

echo "✅ Research complete: ${OUTPUT_DIR}/research.json"
echo ""
python3 -c "
import json
data = json.load(open('${OUTPUT_DIR}/research.json'))
print(f\"  Found {len(data['key_facts'])} facts\")
print(f\"  Found {len(data['media_suggestions'])} media suggestions\")
"
