# Visual Analysis Workflow

This document explains how to use Claude Code's visual analysis to rank media.

## Workflow Steps

### 1. Research Phase (Normal)
Run the research agent to gather ~30 media candidates from Pexels, Pixabay, and Giphy:
```bash
./agents/1_research.sh "Your topic here" "tone"
```

### 2. Download Candidates
Run the visual ranker to download all candidate media files:
```bash
python3 agents/visual_ranker.py
```

This will:
- Download all media from research.json
- Save files to `outputs/temp_media/`
- Create `outputs/visual_analysis_input.json`

### 3. Visual Analysis (Interactive with Claude Code)

**Ask Claude Code to analyze the media files:**

> "Please analyze all the media files in outputs/temp_media/ for educational quality.
>
> Read the analysis context from outputs/visual_analysis_input.json, then view each image/GIF in outputs/temp_media/ using the Read tool.
>
> For each file, score it on:
> - Educational value (1-10): Does it clearly illustrate scientific concepts?
> - Visual clarity (1-10): Is it clear, high-quality, easy to understand?
> - Engagement (1-10): Will it capture attention on social media?
> - Scientific accuracy (1-10): Does it accurately represent the concept?
> - Relevance (1-10): How well does it match the topic?
>
> Provide an overall score (1-100) for each.
>
> Then rank the top 10 media files and save your analysis to outputs/visual_rankings.json in this format:
>
> ```json
> {
>   "rankings": [
>     {
>       "rank": 1,
>       "candidate_index": 5,
>       "local_path": "outputs/temp_media/candidate_06.jpg",
>       "overall_score": 95,
>       "scores": {
>         "educational_value": 10,
>         "visual_clarity": 9,
>         "engagement": 10,
>         "scientific_accuracy": 9,
>         "relevance": 10
>       },
>       "reasoning": "Brief explanation...",
>       "original_data": { ... from visual_analysis_input.json }
>     }
>   ],
>   "top_10_indices": [5, 12, 3, 18, 7, 22, 1, 15, 9, 20],
>   "analysis_notes": "Overall observations..."
> }
> ```
"

### 4. Update Media Plan
After visual_rankings.json is created, update the curator to use only the top-ranked media:
```bash
./agents/4_curate_media.sh
```

The curator will now use the top 10 visually-ranked media instead of all research suggestions.

### 5. Continue Pipeline Normally
```bash
./agents/download_media.py
python3 agents/3_compose.py
./approve_media.sh
python3 agents/5_assemble_video.py
```

## Benefits

- **Quality Control**: Claude visually inspects each image for educational value
- **Relevance**: Only scientifically accurate and topic-relevant media is used
- **Engagement**: Media is scored for social media appeal
- **Efficiency**: Filter 30 candidates down to the best 10
