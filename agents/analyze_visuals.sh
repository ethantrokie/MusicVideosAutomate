#!/bin/bash
# Visual Analysis Script
# This script prompts Claude Code to analyze downloaded media using vision capabilities

set -e

echo "👁️  Visual Analysis: Preparing for Claude Code analysis..."

# Check if input file exists
if [ ! -f "outputs/visual_analysis_input.json" ]; then
    echo "❌ Error: outputs/visual_analysis_input.json not found"
    echo "   Run the visual_ranker.py script first"
    exit 1
fi

# Load the analysis input
TOPIC=$(jq -r '.topic' outputs/visual_analysis_input.json)
TONE=$(jq -r '.tone' outputs/visual_analysis_input.json)
NUM_MEDIA=$(jq '.downloaded_media | length' outputs/visual_analysis_input.json)

echo ""
echo "Topic: $TOPIC"
echo "Tone: $TONE"
echo "Media files to analyze: $NUM_MEDIA"
echo ""
echo "================================================"
echo "CLAUDE CODE VISUAL ANALYSIS PROMPT"
echo "================================================"
echo ""
echo "Please analyze the following $NUM_MEDIA media files for educational quality."
echo ""
echo "Topic: $TOPIC"
echo "Tone: $TONE"
echo ""
echo "For each image/GIF in outputs/temp_media/, please:"
echo ""
echo "1. Read and view the image using the Read tool"
echo "2. Evaluate it on these criteria (score 1-10 each):"
echo "   - Educational value: Does it clearly illustrate scientific concepts?"
echo "   - Visual clarity: Is it clear, high-quality, and easy to understand?"
echo "   - Engagement: Will it capture attention on social media?"
echo "   - Scientific accuracy: Does it accurately represent the concept?"
echo "   - Relevance: How well does it match the topic '$TOPIC'?"
echo ""
echo "3. Provide an overall score (1-100) and brief reasoning"
echo ""
echo "4. Rank the top 10 media files for use in the final video"
echo ""
echo "5. Output your rankings to outputs/visual_rankings.json in this format:"
echo ""
cat <<'EOF'
{
  "rankings": [
    {
      "rank": 1,
      "candidate_index": 5,
      "local_path": "outputs/temp_media/candidate_06.jpg",
      "overall_score": 95,
      "scores": {
        "educational_value": 10,
        "visual_clarity": 9,
        "engagement": 10,
        "scientific_accuracy": 9,
        "relevance": 10
      },
      "reasoning": "Excellent microscopic view of chloroplasts showing clear detail...",
      "original_data": { ... }
    },
    ...
  ],
  "top_10": [5, 12, 3, 18, 7, 22, 1, 15, 9, 20],
  "analysis_notes": "Overall the Giphy animations scored highest for engagement..."
}
EOF
echo ""
echo "================================================"
echo ""
echo "Copy the prompt above and paste into Claude Code."
echo "Claude Code will analyze each image and generate the rankings."
