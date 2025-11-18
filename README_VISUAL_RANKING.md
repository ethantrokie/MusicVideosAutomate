# Visual Ranking Workflow

This feature uses Claude Code's visual capabilities to analyze and rank media for educational quality.

## Quick Start

### Option 1: Automatic Visual Analysis (Recommended)

Run the research phase, then manually trigger visual analysis:

```bash
# 1. Run research to get ~30 media candidates
./agents/1_research.sh

# 2. Download candidates for analysis
python3 agents/visual_ranker.py

# 3. Ask Claude Code to analyze the media (see prompt below)
# [This is where you interact with Claude Code in this conversation]

# 4. Continue pipeline - curator will use the rankings
./agents/2_lyrics.sh
./pipeline.sh --start=3
```

### Option 2: Skip Visual Ranking

The pipeline works fine without visual ranking - it will use all research suggestions:

```bash
./pipeline.sh
```

## Visual Analysis Prompt

After running `python3 agents/visual_ranker.py`, ask Claude Code:

```
Please analyze all the media files in outputs/temp_media/ for educational quality.

Read the analysis context from outputs/visual_analysis_input.json, then view each
image/GIF/video in outputs/temp_media/ using the Read tool.

For each file, score it on:
- Educational value (1-10): Does it clearly illustrate scientific concepts?
- Visual clarity (1-10): Is it clear, high-quality, easy to understand?
- Engagement (1-10): Will it capture attention on social media?
- Scientific accuracy (1-10): Does it accurately represent the concept?
- Relevance (1-10): How well does it match the topic?

Provide an overall score (1-100) for each.

Then rank ALL files from best to worst and save your analysis to
outputs/visual_rankings.json in this format:

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
      "reasoning": "Brief explanation of why this ranks highly...",
      "original_data": { ...copy from visual_analysis_input.json... }
    },
    ...ALL files ranked from best to worst...
  ],
  "top_10_indices": [5, 12, 3, 18, 7, 22, 1, 15, 9, 20],
  "analysis_notes": "Overall observations about the media quality..."
}

Make sure to include ALL analyzed files in the rankings array, sorted by overall_score.
```

## How It Works

### 1. Research Agent (Enhanced)
- Now requests ~30 media items (10 from each source: Pexels, Pixabay, Giphy)
- Focuses on scientific and educational imagery
- Searches using specific science terms (chloroplast, molecule, DNA, etc.)

### 2. Visual Ranker Script
- Downloads all candidate media to `outputs/temp_media/`
- Uses stock photo API to resolve URLs
- Prepares data for Claude Code analysis
- Creates `outputs/visual_analysis_input.json`

### 3. Claude Code Analysis (You!)
- Claude Code views each image/GIF/video
- Scores on 5 criteria (educational value, clarity, engagement, accuracy, relevance)
- Provides reasoning for each score
- Ranks all media from best to worst
- Outputs `outputs/visual_rankings.json`

### 4. Curator Agent (Enhanced)
- Checks for `outputs/visual_rankings.json`
- If found: prioritizes top-ranked media for shot list
- If not found: uses all research suggestions (original behavior)
- Creates final shot list with 6-10 items

### 5. Rest of Pipeline
- Downloads media from shot list
- Continues normally with music composition, approval, and video assembly

## Benefits

✅ **Quality Control**: Every image is visually inspected by Claude Code
✅ **Scientific Accuracy**: Filters out misleading or incorrect visuals
✅ **Engagement**: Selects most attention-grabbing media for social media
✅ **Relevance**: Ensures media actually matches the educational content
✅ **Efficiency**: Filters 30 candidates → top 10 best options

## File Structure

```
outputs/
├── research.json              # ~30 media candidates from research
├── visual_analysis_input.json # Context + download info for Claude Code
├── visual_rankings.json       # Claude Code's visual analysis results
├── temp_media/                # Downloaded candidate files for analysis
│   ├── candidate_01.jpg
│   ├── candidate_02.gif
│   ├── candidate_03.mp4
│   └── ...
└── media_plan.json            # Final shot list (uses top-ranked if available)
```

## Scoring Criteria

### Educational Value (1-10)
- Does it clearly show the scientific concept?
- Would a student learn something from this visual?
- Is it appropriate for educational content?

### Visual Clarity (1-10)
- Is the image high resolution and clear?
- Can you see important details?
- Is it well-lit and well-composed?

### Engagement (1-10)
- Will this capture attention on TikTok/Instagram?
- Is it visually interesting or dynamic?
- Does it have the "scroll-stopping" quality?

### Scientific Accuracy (1-10)
- Does it correctly represent the concept?
- Are there any misleading elements?
- Is it scientifically sound?

### Relevance (1-10)
- How well does it match the specific topic?
- Does it illustrate the exact concept being taught?
- Is the connection obvious or tenuous?

## Example Workflow

```bash
# 1. Create input
echo "Explain photosynthesis. Tone: upbeat and fun" > input/idea.txt

# 2. Run research
./agents/1_research.sh
# Output: ~30 media candidates in outputs/research.json

# 3. Download for analysis
python3 agents/visual_ranker.py
# Output: Files in outputs/temp_media/, creates visual_analysis_input.json

# 4. Visual analysis (manual - talk to Claude Code)
# Use the prompt above in this conversation
# Output: outputs/visual_rankings.json

# 5. Continue pipeline
./agents/2_lyrics.sh
python3 agents/3_compose.py
./agents/4_curate_media.sh  # Will use visual rankings!
# ... rest of pipeline
```

## Troubleshooting

**Q: Can I skip visual ranking?**
A: Yes! The pipeline works without it. The curator will use all research suggestions.

**Q: How long does visual analysis take?**
A: Depends on how many files. Expect ~30-60 seconds for Claude Code to analyze 30 images.

**Q: What if Claude Code makes a mistake?**
A: You can manually edit `outputs/visual_rankings.json` to adjust rankings before running the curator.

**Q: Can I re-run visual analysis?**
A: Yes! Just run `python3 agents/visual_ranker.py` again and re-do the Claude Code prompt.

**Q: Does this work with videos?**
A: Yes! The system is optimized for videos and animated GIFs. Claude Code can view video files and analyze their content, motion, and educational value.
