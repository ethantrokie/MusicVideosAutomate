#!/bin/bash

set -e

# Use OUTPUT_DIR from pipeline or default to outputs/
OUTPUT_DIR="${OUTPUT_DIR:-outputs}"

echo "📝 Creating phrase groups from word-level timestamps..."

# Check for required input
if [ ! -f "${OUTPUT_DIR}/suno_output.json" ]; then
    echo "❌ Error: ${OUTPUT_DIR}/suno_output.json not found"
    echo "Run Stage 3 (music generation) first"
    exit 1
fi

# Create phrase groups using Python script
./venv/bin/python3 -c "
import json
import sys
sys.path.insert(0, 'agents')
from phrase_grouper import PhraseGrouper

# Load Suno output
with open('${OUTPUT_DIR}/suno_output.json') as f:
    suno_data = json.load(f)

# Extract aligned words
aligned_words = suno_data.get('alignedWords', [])

if not aligned_words:
    print('⚠️  Warning: No aligned words found in suno_output.json')
    # Create empty phrase groups file
    with open('${OUTPUT_DIR}/phrase_groups.json', 'w') as f:
        json.dump([], f, indent=2)
    sys.exit(0)

# Initialize grouper
grouper = PhraseGrouper()

# Step 1: Parse into basic phrases based on timing gaps
phrases = grouper.parse_into_phrases(aligned_words)
print(f'📝 Parsed {len(phrases)} phrases based on timing gaps')

# Step 2: Try to load research data for key term extraction
key_terms = []
try:
    with open('${OUTPUT_DIR}/research.json') as f:
        research_data = json.load(f)
        key_facts = research_data.get('key_facts', [])

        # Extract lyrics text from aligned words
        lyrics_text = ' '.join([w['word'] for w in aligned_words])

        # Extract key scientific terms
        key_terms = grouper.extract_key_terms(lyrics_text, key_facts)
        if key_terms:
            print(f'🔑 Extracted {len(key_terms)} key scientific terms')
except FileNotFoundError:
    print('   ℹ️  No research.json found, skipping semantic merging')
except Exception as e:
    print(f'   ⚠️  Could not extract key terms: {e}')

# Step 3: Merge related consecutive phrases if we have key terms
if key_terms and len(phrases) > 1:
    phrase_groups = grouper.merge_related_phrases(phrases, key_terms)
    print(f'🧠 Smart merging: {len(phrases)} phrases → {len(phrase_groups)} semantic groups')
else:
    phrase_groups = phrases
    print(f'   Using timing-based phrases (no semantic merging)')

# Save phrase groups
with open('${OUTPUT_DIR}/phrase_groups.json', 'w') as f:
    json.dump(phrase_groups, f, indent=2)

print(f'✅ Created {len(phrase_groups)} phrase groups')

# Print duration stats
if phrase_groups:
    durations = [(p['endS'] - p['startS']) for p in phrase_groups]
    long_phrases = [p for p in phrase_groups if (p['endS'] - p['startS']) > 8]
    print(f'   Phrases >8 seconds: {len(long_phrases)}/{len(phrase_groups)}')
    if long_phrases:
        print(f'   These phrases need multiple clips:')
        for p in long_phrases[:5]:  # Show first 5
            dur = p['endS'] - p['startS']
            text = p['text'][:50] + '...' if len(p['text']) > 50 else p['text']
            print(f'     - {dur:.1f}s: \"{text}\"')
"

# Verify output
if [ ! -f "${OUTPUT_DIR}/phrase_groups.json" ]; then
    echo "❌ Error: Failed to create phrase_groups.json"
    exit 1
fi

echo "✅ Phrase groups created: ${OUTPUT_DIR}/phrase_groups.json"
