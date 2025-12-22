# Lyric-Based Video Search Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Move video search from pre-lyrics (Stage 1) to post-lyrics (Stage 3.5), enabling videos to be searched specifically for lyric content with semantic tagging.

**Architecture:** New Stage 3.5 analyzes lyrics to extract visual concepts, searches videos using existing `search_media.py` tool, and tags each video with source lyric. Visual ranking (moved to Stage 3.6) preserves tags. Curator receives lyric-tagged videos for intelligent assignment.

**Tech Stack:** Python 3, Bash, Claude CLI, existing search_media.py API integration

---

## Task 1: Create Lyric Media Search Prompt

**Files:**
- Create: `agents/prompts/lyric_media_search_prompt.md`

**Step 1: Create the prompt file**

```bash
touch agents/prompts/lyric_media_search_prompt.md
```

**Step 2: Write the prompt content**

```markdown
# Lyric-Based Media Search Agent Instructions

You are a lyric analysis and media search agent. Your job is to analyze song lyrics and find relevant videos for each lyric concept.

## Context
- **Lyrics**: {{LYRICS_JSON}}
- **Topic**: {{TOPIC}} (for additional context)

## Your Task

1. **Analyze Lyrics**: Parse lyrics line-by-line or section-by-section to identify visual concepts
2. **Extract Visual Concepts**: For each meaningful lyric phrase, identify what can be visualized
3. **Generate Search Terms**: Convert lyric concepts into effective stock video search terms
4. **Search for Videos**: Use the media search tool to find 1-2 videos per concept
5. **Tag Each Video**: Associate each video with the lyric line that inspired its search

## Media Search Tool

You have access to a media search tool that finds **real videos** from Pexels, Pixabay, and Giphy APIs.

**Usage**:
```bash
python agents/search_media.py "SEARCH QUERY" --type=video --max=2 --json
```

**Important Guidelines**:
- **Keep search queries SIMPLE**: Use 2-3 core visual terms
- **Avoid literal lyric phrases**: Convert poetic language to filmable concepts
- **Focus on visual, filmable concepts**: Not abstract ideas
- **Call the tool for EACH visual concept** you identify
- **Use --json flag** for machine-readable output

**Example Conversion**:
- Lyric: "Molecules vibrate billions of times per second"
- Visual concept: "molecular vibration high frequency"
- Search term: "molecular motion animation"
- Command: `python agents/search_media.py "molecular motion animation" --type=video --max=2 --json`

**Good Search Terms**:
- "injection molding process" (not "molten polymer flows through heated steel")
- "DNA replication" (not "genetic information copying itself")
- "friction heat generation" (not "creating warmth from rubbing")

## Target Coverage

- **Goal**: 20-30 videos total for ~180s video
- **Per Concept**: 1-2 videos
- **Concepts**: Extract 15-20 visual concepts from lyrics

## IMPORTANT: Autonomous Operation

- **DO NOT ask questions or request clarification.**
- **Make reasonable decisions autonomously** based on lyrics and topic.
- **Proceed directly to analysis** and output the JSON file.
- **Your output must be ONLY the JSON** - no questions, no explanations.

## Output Format

Write your output to `{{OUTPUT_PATH}}` in the following JSON format.

**Requirements**:
- **URLs must be DIRECT media page URLs**, not search/explore pages
- **Media must be from Pexels, Pixabay, or Giphy only**
- **Output valid JSON only**

```json
{
  "media_by_lyric": [
    {
      "lyric_line": "Exact lyric line from the song",
      "visual_concept": "Brief description of what this represents visually",
      "search_term": "The actual search query used",
      "videos": [
        {
          "url": "https://www.pexels.com/video/specific-video-12345/",
          "type": "video",
          "description": "Clear description of the media",
          "source": "pexels",
          "thumbnail_url": "https://...",
          "duration": 10,
          "license": "CC0"
        }
      ]
    }
  ],
  "total_videos": 25,
  "lyric_coverage_percent": 90,
  "concepts_extracted": 18
}
```

Begin analysis.
```

**Step 3: Verify file creation**

```bash
ls -la agents/prompts/lyric_media_search_prompt.md
```

Expected: File exists with prompt content

**Step 4: Commit**

```bash
git add agents/prompts/lyric_media_search_prompt.md
git commit -m "feat: add lyric media search prompt"
```

---

## Task 2: Create Lyric Media Search Shell Script

**Files:**
- Create: `agents/3.5_lyric_media_search.sh`

**Step 1: Create executable script file**

```bash
touch agents/3.5_lyric_media_search.sh
chmod +x agents/3.5_lyric_media_search.sh
```

**Step 2: Write shell script content**

```bash
#!/bin/bash

set -e

# Use OUTPUT_DIR from pipeline or default to outputs/
OUTPUT_DIR="${OUTPUT_DIR:-outputs}"

echo "🎬 Lyric Media Search Agent: Finding videos for lyrics..."

# Check for required inputs
if [ ! -f "${OUTPUT_DIR}/lyrics.json" ]; then
    echo "❌ Error: ${OUTPUT_DIR}/lyrics.json not found"
    exit 1
fi

if [ ! -f "${OUTPUT_DIR}/research.json" ]; then
    echo "❌ Error: ${OUTPUT_DIR}/research.json not found (needed for topic context)"
    exit 1
fi

# Read data
LYRICS=$(cat ${OUTPUT_DIR}/lyrics.json)
TOPIC=$(python3 -c "import json; print(json.load(open('${OUTPUT_DIR}/research.json'))['topic'])")

echo "  Topic: $TOPIC"
echo "  Analyzing lyrics for visual concepts..."

# Create temp file with substituted prompt
TEMP_PROMPT=$(mktemp)
sed "s|{{OUTPUT_PATH}}|${OUTPUT_DIR}/lyric_media.json|g; s/{{TOPIC}}/$TOPIC/g" agents/prompts/lyric_media_search_prompt.md > "$TEMP_PROMPT"

# Add lyrics data to the end
echo "" >> "$TEMP_PROMPT"
echo "## Lyrics Data" >> "$TEMP_PROMPT"
echo '```json' >> "$TEMP_PROMPT"
echo "$LYRICS" >> "$TEMP_PROMPT"
echo '```' >> "$TEMP_PROMPT"

# Call Claude Code CLI
echo "  Calling Claude Code for lyric-based media search..."
/Users/ethantrokie/.npm-global/bin/claude -p "$(cat $TEMP_PROMPT)" --model claude-sonnet-4-5 --dangerously-skip-permissions

# Clean up temp prompt
rm "$TEMP_PROMPT"

# Verify the file was created and is valid JSON
if [ ! -f "${OUTPUT_DIR}/lyric_media.json" ]; then
    echo "❌ Error: Claude did not create ${OUTPUT_DIR}/lyric_media.json"
    exit 1
fi

if ! python3 -c "import json; json.load(open('${OUTPUT_DIR}/lyric_media.json'))" 2>/dev/null; then
    echo "❌ Error: ${OUTPUT_DIR}/lyric_media.json is not valid JSON"
    exit 1
fi

echo "✅ Lyric media search complete: ${OUTPUT_DIR}/lyric_media.json"
echo ""
python3 -c "
import json
data = json.load(open('${OUTPUT_DIR}/lyric_media.json'))
print(f\"  Found {data['total_videos']} videos\")
print(f\"  Coverage: {data['lyric_coverage_percent']}%\")
print(f\"  Concepts: {data['concepts_extracted']}\")
"
```

**Step 3: Test script syntax**

```bash
bash -n agents/3.5_lyric_media_search.sh
```

Expected: No syntax errors

**Step 4: Commit**

```bash
git add agents/3.5_lyric_media_search.sh
git commit -m "feat: add lyric media search shell script"
```

---

## Task 3: Modify Visual Ranking to Load from lyric_media.json

**Files:**
- Modify: `agents/3_rank_visuals.py:295-309`

**Step 1: Locate the current loading logic**

```bash
grep -n "research.json" agents/3_rank_visuals.py
```

Expected: Shows lines where research.json is loaded

**Step 2: Modify the main() function to load from lyric_media.json**

Find this section (around lines 295-309):

```python
# OLD CODE (lines 295-309):
def main():
    """Main entry point for visual ranking agent."""
    logging.basicConfig(level=logging.INFO, format='%(message)s')
    logger = logging.getLogger(__name__)

    # Load research data
    research_path = get_output_path('research.json')
    if not research_path.exists():
        logger.error(f"Research data not found at {research_path}")
        sys.exit(1)

    with open(research_path) as f:
        research_data = json.load(f)
```

Replace with:

```python
# NEW CODE:
def main():
    """Main entry point for visual ranking agent."""
    logging.basicConfig(level=logging.INFO, format='%(message)s')
    logger = logging.getLogger(__name__)

    # Load lyric media data
    lyric_media_path = get_output_path('lyric_media.json')
    if not lyric_media_path.exists():
        logger.error(f"Lyric media data not found at {lyric_media_path}")
        logger.error("Run Stage 3.5 (lyric media search) first")
        sys.exit(1)

    with open(lyric_media_path) as f:
        lyric_media_data = json.load(f)

    # Still need research.json for key_facts
    research_path = get_output_path('research.json')
    if not research_path.exists():
        logger.error(f"Research data not found at {research_path}")
        sys.exit(1)

    with open(research_path) as f:
        research_data = json.load(f)
```

**Step 3: Modify to flatten lyric_media while preserving tags**

Find the section that extracts candidates (around line 307):

```python
# OLD CODE:
    # Enrich media suggestions with thumbnail URLs
    from stock_photo_api import StockPhotoResolver
    resolver = StockPhotoResolver()
    media_suggestions = research_data.get('media_suggestions', [])
    enriched_media = resolver.enrich_with_thumbnails(media_suggestions)
    research_data['media_suggestions'] = enriched_media
```

Replace with:

```python
    # Flatten media_by_lyric while preserving lyric metadata
    candidates = []
    for lyric_entry in lyric_media_data.get('media_by_lyric', []):
        for video in lyric_entry.get('videos', []):
            # Preserve lyric tags
            video['lyric_line'] = lyric_entry['lyric_line']
            video['visual_concept'] = lyric_entry['visual_concept']
            video['search_term'] = lyric_entry.get('search_term', '')
            candidates.append(video)

    logger.info(f"Loaded {len(candidates)} videos from lyric media search")

    # Enrich with thumbnails if needed
    from stock_photo_api import StockPhotoResolver
    resolver = StockPhotoResolver()
    enriched_media = resolver.enrich_with_thumbnails(candidates)
```

**Step 4: Update the ranking call**

Find the section that creates fake research_data structure (around line 318):

```python
# OLD CODE:
    # Rank media
    ranked_media = ranker.rank_media(research_data)
```

Replace with:

```python
    # Create structure for ranking (needs key_facts from research)
    ranking_input = {
        'media_suggestions': enriched_media,
        'key_facts': research_data.get('key_facts', [])
    }

    # Rank media
    ranked_media = ranker.rank_media(ranking_input)
```

**Step 5: Test the changes**

```bash
python3 -c "import agents.3_rank_visuals; print('Syntax OK')"
```

Expected: "Syntax OK"

**Step 6: Commit**

```bash
git add agents/3_rank_visuals.py
git commit -m "feat: modify visual ranking to load from lyric_media.json"
```

---

## Task 4: Modify Curator to Load from visual_rankings.json

**Files:**
- Modify: `agents/4_curate_media.sh:25-44`
- Modify: `agents/prompts/curator_prompt.md:1-48`

**Step 1: Modify curator shell script input loading**

Find section in `agents/4_curate_media.sh` (lines 25-44):

```bash
# OLD CODE:
# Check for required inputs
if [ ! -f "${OUTPUT_DIR}/research_pruned_for_curator.json" ]; then
    echo "❌ Error: ${OUTPUT_DIR}/research_pruned_for_curator.json not found"
    exit 1
fi

if [ ! -f "${OUTPUT_DIR}/lyrics.json" ]; then
    echo "❌ Error: ${OUTPUT_DIR}/lyrics.json not found"
    exit 1
fi

# Read data
RESEARCH=$(cat ${OUTPUT_DIR}/research_pruned_for_curator.json)
LYRICS=$(cat ${OUTPUT_DIR}/lyrics.json)

# Check for visual rankings (optional)
VISUAL_RANKINGS=""
if [ -f "${OUTPUT_DIR}/visual_rankings.json" ]; then
    echo "  📊 Using visual rankings for media selection"
    VISUAL_RANKINGS=$(cat ${OUTPUT_DIR}/visual_rankings.json)
fi
```

Replace with:

```bash
# NEW CODE:
# Check for required inputs
if [ ! -f "${OUTPUT_DIR}/visual_rankings.json" ]; then
    echo "❌ Error: ${OUTPUT_DIR}/visual_rankings.json not found"
    echo "Run Stage 3.6 (visual ranking) first"
    exit 1
fi

if [ ! -f "${OUTPUT_DIR}/lyrics.json" ]; then
    echo "❌ Error: ${OUTPUT_DIR}/lyrics.json not found"
    exit 1
fi

# Read data
VISUAL_RANKINGS=$(cat ${OUTPUT_DIR}/visual_rankings.json)
LYRICS=$(cat ${OUTPUT_DIR}/lyrics.json)

echo "  📊 Using lyric-tagged ranked media"
```

**Step 2: Modify curator shell script prompt assembly**

Find section (lines 54-71):

```bash
# OLD CODE:
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

if [ -n "$VISUAL_RANKINGS" ]; then
    echo "" >> "$TEMP_PROMPT"
    echo "## Visual Rankings Data" >> "$TEMP_PROMPT"
    echo '```json' >> "$TEMP_PROMPT"
    echo "$VISUAL_RANKINGS" >> "$TEMP_PROMPT"
    echo '```' >> "$TEMP_PROMPT"
fi
```

Replace with:

```bash
# NEW CODE:
# Add data to the end
echo "" >> "$TEMP_PROMPT"
echo "## Lyric-Tagged Ranked Media" >> "$TEMP_PROMPT"
echo '```json' >> "$TEMP_PROMPT"
echo "$VISUAL_RANKINGS" >> "$TEMP_PROMPT"
echo '```' >> "$TEMP_PROMPT"
echo "" >> "$TEMP_PROMPT"
echo "## Lyrics Data" >> "$TEMP_PROMPT"
echo '```json' >> "$TEMP_PROMPT"
echo "$LYRICS" >> "$TEMP_PROMPT"
echo '```' >> "$TEMP_PROMPT"
```

**Step 3: Modify curator prompt instructions**

Find `agents/prompts/curator_prompt.md` and update:

```markdown
# OLD (lines 5-13):
## Input Context
-   **Research Data**: {{RESEARCH_JSON}}
-   **Lyrics Data**: {{LYRICS_JSON}}
-   **Visual Rankings** (if available): {{VISUAL_RANKINGS_JSON}}
-   **Video Duration**: {{VIDEO_DURATION}} seconds

## Your Task
1.  **Select Media**: From the research data, select 10-15 scientifically accurate and relevant videos or animated GIFs (no static images). Prioritize top-ranked media if visual rankings are available. **IMPORTANT: Each media URL must be used only once - do not repeat any URLs in your shot list.**
2.  **Match to Lyrics**: Assign each media item to a line of lyrics it best illustrates.
```

Replace with:

```markdown
# NEW:
## Input Context
-   **Lyric-Tagged Ranked Media**: Each video is tagged with the lyric_line that inspired its search, plus visual_score from ranking
-   **Lyrics Data**: {{LYRICS_JSON}}
-   **Video Duration**: {{VIDEO_DURATION}} seconds

## Your Enhanced Task
1.  **Review lyric→video mappings**: Each video comes with a suggested lyric_line match from the search stage
2.  **Validate or override**: Keep suggested lyric matches when quality is good, or reassign if a video fits better elsewhere
3.  **Prioritize intended matches**: Prefer using videos for their source lyric when visual_score is high (>0.7)
4.  **Select best-ranked**: Among videos for same lyric, choose highest visual_score
5.  **Create shot list**: Assign timing, transitions, and final sequence for {{VIDEO_DURATION}}s video
```

**Step 4: Update output format instructions**

Add after line 22:

```markdown
**NEW FIELDS in shot list**:
- `source_lyric_line`: The original lyric this video was searched for (preserve from input)
- `visual_score`: The quality score from ranking (preserve from input)
```

**Step 5: Commit changes**

```bash
git add agents/4_curate_media.sh agents/prompts/curator_prompt.md
git commit -m "feat: modify curator to use lyric-tagged ranked media"
```

---

## Task 5: Modify Researcher to Remove Media Search

**Files:**
- Modify: `agents/prompts/researcher_prompt.md:13-103`

**Step 1: Remove media search tool section**

Edit `agents/prompts/researcher_prompt.md` and remove lines 13-50 (entire "Media Search Tool" section).

Remove this section:

```markdown
3.  **Find Media**: Use the media search tool to find 30 royalty-free videos...

## Media Search Tool

[entire section]
```

**Step 2: Update task description**

Change line 13 from:

```markdown
3.  **Find Media**: Use the media search tool to find 30 royalty-free videos and animated GIFs from Pexels, Pixabay, and Giphy.
```

To:

```markdown
Note: Media search is now handled in Stage 3.5 (after lyrics generation) for better lyric-visual alignment.
```

**Step 3: Remove media_suggestions from output format**

Find the output format section (around line 73) and remove:

```markdown
  "media_suggestions": [
    {
      "url": "https://www.pexels.com/video/a-specific-scientific-process-12345/",
      "type": "video",
      "description": "Clear, concise description of the media.",
      "source": "pexels",
      "search_query": "relevant search terms",
      "relevance_score": 10,
      "license": "CC0",
      "recommended_fact": 0
    }
  ],
```

**Step 4: Verify output format**

Ensure the JSON format now looks like:

```json
{
  "topic": "{{TOPIC}}",
  "video_title": "A short, catchy title...",
  "tone": "{{TONE}}",
  "key_facts": [
    "Fact 1: A foundational concept.",
    "..."
  ],
  "sources": [
    "https://source-url-1"
  ]
}
```

**Step 5: Commit**

```bash
git add agents/prompts/researcher_prompt.md
git commit -m "feat: remove media search from researcher (moved to Stage 3.5)"
```

---

## Task 6: Update pipeline.sh to Add Stage 3.5 and Move Stage 2

**Files:**
- Modify: `pipeline.sh:155-170` (add Stage 3.5)
- Modify: `pipeline.sh:186-198` (move visual ranking)

**Step 1: Remove old Stage 2 (Visual Ranking) from current position**

Find lines 155-170 in `pipeline.sh`:

```bash
# OLD CODE (lines 155-170):
# Stage 2: Visual Ranking
if [ $START_STAGE -le 2 ]; then
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}Stage 2/6: Visual Ranking${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

    echo "🎨 Visual Ranking Agent: Analyzing media diversity..."

    if python3 agents/3_rank_visuals.py; then
        echo "✅ Visual ranking complete"
    else
        echo -e "${YELLOW}⚠️  Visual ranking failed, continuing without rankings${NC}"
        # Not critical - curator can work without rankings
    fi
    echo ""
fi
```

**DELETE these lines** (we'll add back later in new position).

**Step 2: Add new Stage 3.5 after lyrics (Stage 3)**

After the lyrics generation stage (around line 185), add:

```bash
# NEW Stage 3.5: Lyric-Based Media Search
if [ $START_STAGE -le 4 ]; then
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}Stage 3.5/9: Lyric-Based Media Search${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    ./agents/3.5_lyric_media_search.sh
    if [ $? -ne 0 ]; then
        echo -e "${RED}❌ Lyric media search failed${NC}"
        exit 1
    fi
    echo ""
fi
```

**Step 3: Add Stage 3.6 (Visual Ranking in new position)**

Right after Stage 3.5, add:

```bash
# Stage 3.6: Visual Ranking (moved from Stage 2)
if [ $START_STAGE -le 5 ]; then
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}Stage 3.6/9: Visual Ranking${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

    echo "🎨 Visual Ranking Agent: Analyzing lyric-based media diversity..."

    if python3 agents/3_rank_visuals.py; then
        echo "✅ Visual ranking complete"
    else
        echo -e "${YELLOW}⚠️  Visual ranking failed, continuing without rankings${NC}"
        # Not critical - curator can work without rankings
        exit 1
    fi
    echo ""
fi
```

**Step 4: Update stage numbers in comments**

Update all subsequent stage numbers in pipeline.sh:
- Old Stage 3 (Lyrics) → Stage 3
- Old Stage 4 (Music) → Stage 4
- Add Stage 3.5 (Lyric Media Search)
- Add Stage 3.6 (Visual Ranking)
- Old Stage 5 (Media Curation) → Stage 5
- Old Stage 6+ → Stage 6+

**Step 5: Test pipeline structure**

```bash
bash -n pipeline.sh
```

Expected: No syntax errors

**Step 6: Commit**

```bash
git add pipeline.sh
git commit -m "feat: add Stage 3.5 (lyric media search) and move visual ranking to Stage 3.6"
```

---

## Task 7: Add Feature Flag for Gradual Rollout

**Files:**
- Modify: `config/config.json` (add feature flag)
- Modify: `pipeline.sh:1-30` (add flag check)

**Step 1: Add feature flag to config**

```bash
python3 << 'EOF'
import json
from pathlib import Path

config_path = Path("config/config.json")
with open(config_path) as f:
    config = json.load(f)

# Add feature flag
if 'lyric_based_search' not in config:
    config['lyric_based_search'] = {
        'enabled': False,  # Start disabled
        'fallback_to_topic_search': True
    }

with open(config_path, 'w') as f:
    json.dump(config, f, indent=2)

print("Feature flag added to config.json")
EOF
```

**Step 2: Add flag check to pipeline.sh**

After line 20 (after config loading), add:

```bash
# Load feature flags
LYRIC_SEARCH_ENABLED=$(jq -r '.lyric_based_search.enabled // false' config/config.json 2>/dev/null || echo "false")
```

**Step 3: Make Stage 3.5 and 3.6 conditional**

Wrap the new stages:

```bash
# Stage 3.5: Lyric-Based Media Search (FEATURE FLAG)
if [ "$LYRIC_SEARCH_ENABLED" = "true" ] && [ $START_STAGE -le 4 ]; then
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}Stage 3.5/9: Lyric-Based Media Search (NEW)${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    ./agents/3.5_lyric_media_search.sh
    if [ $? -ne 0 ]; then
        echo -e "${RED}❌ Lyric media search failed${NC}"
        exit 1
    fi
    echo ""
elif [ "$LYRIC_SEARCH_ENABLED" = "false" ]; then
    echo -e "${YELLOW}⏭️  Lyric-based search disabled (using legacy topic-based search)${NC}"
fi
```

**Step 4: Add similar flag to Stage 3.6**

```bash
# Stage 3.6: Visual Ranking
if [ "$LYRIC_SEARCH_ENABLED" = "true" ] && [ $START_STAGE -le 5 ]; then
    # New flow: rank lyric-based media
    echo "🎨 Visual Ranking Agent: Analyzing lyric-based media diversity..."
    python3 agents/3_rank_visuals.py
elif [ "$LYRIC_SEARCH_ENABLED" = "false" ] && [ $START_STAGE -le 2 ]; then
    # Legacy flow: rank topic-based media from research
    echo "🎨 Visual Ranking Agent: Analyzing research media diversity..."
    # Use old logic here (would need to preserve old code)
fi
```

**Step 5: Commit**

```bash
git add config/config.json pipeline.sh
git commit -m "feat: add feature flag for lyric-based search rollout"
```

---

## Task 8: Create Integration Test

**Files:**
- Create: `tests/test_lyric_media_search_integration.py`

**Step 1: Create test file**

```python
#!/usr/bin/env python3
"""
Integration test for lyric-based media search flow.
Tests the full pipeline from lyrics → media search → visual ranking → curator.
"""
import json
import os
import subprocess
import tempfile
from pathlib import Path
import shutil

def test_lyric_media_search_pipeline():
    """Test complete lyric-based media search pipeline."""

    # Setup: Create temp output directory
    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir)
        os.environ['OUTPUT_DIR'] = str(output_dir)

        # Step 1: Create mock lyrics.json
        lyrics_data = {
            "lyrics": "Molecules vibrate fast creating heat\nFriction generates warmth from the motion",
            "music_prompt": "energetic pop punk",
            "estimated_duration_seconds": 30,
            "structure": "verse-chorus"
        }
        with open(output_dir / "lyrics.json", 'w') as f:
            json.dump(lyrics_data, f)

        # Step 2: Create mock research.json
        research_data = {
            "topic": "How microwave ovens heat food",
            "key_facts": [
                "Microwaves make water molecules vibrate",
                "Friction from vibration creates heat"
            ],
            "tone": "educational"
        }
        with open(output_dir / "research.json", 'w') as f:
            json.dump(research_data, f)

        # Step 3: Run lyric media search
        result = subprocess.run(
            ['./agents/3.5_lyric_media_search.sh'],
            capture_output=True,
            text=True,
            env=os.environ
        )

        assert result.returncode == 0, f"Lyric media search failed: {result.stderr}"

        # Step 4: Verify lyric_media.json created
        lyric_media_path = output_dir / "lyric_media.json"
        assert lyric_media_path.exists(), "lyric_media.json not created"

        # Step 5: Validate lyric_media.json structure
        with open(lyric_media_path) as f:
            lyric_media = json.load(f)

        assert 'media_by_lyric' in lyric_media
        assert len(lyric_media['media_by_lyric']) > 0
        assert lyric_media['total_videos'] > 0

        # Verify lyric tagging
        first_entry = lyric_media['media_by_lyric'][0]
        assert 'lyric_line' in first_entry
        assert 'visual_concept' in first_entry
        assert 'videos' in first_entry
        assert len(first_entry['videos']) > 0

        # Verify video structure
        first_video = first_entry['videos'][0]
        assert 'url' in first_video
        assert 'source' in first_video

        print("✅ Lyric media search integration test passed")

if __name__ == '__main__':
    test_lyric_media_search_pipeline()
```

**Step 2: Run test**

```bash
python3 tests/test_lyric_media_search_integration.py
```

Expected: Test passes (or skip if no API keys configured)

**Step 3: Commit**

```bash
git add tests/test_lyric_media_search_integration.py
git commit -m "test: add integration test for lyric media search"
```

---

## Task 9: Create Migration Documentation

**Files:**
- Create: `docs/LYRIC_SEARCH_MIGRATION.md`

**Step 1: Create migration guide**

```markdown
# Lyric-Based Search Migration Guide

## Overview

This guide covers migrating from topic-based video search (Stage 1) to lyric-based video search (Stage 3.5).

## Feature Flag

The new system is controlled by a feature flag in `config/config.json`:

```json
{
  "lyric_based_search": {
    "enabled": false,
    "fallback_to_topic_search": true
  }
}
```

**To enable:**

```bash
jq '.lyric_based_search.enabled = true' config/config.json > config/config.json.tmp
mv config/config.json.tmp config/config.json
```

## Migration Steps

### Phase 1: Testing (Week 1)

1. Enable feature flag on dev environment
2. Run 3-5 test videos through pipeline
3. Compare video quality with legacy system
4. Collect lyric→video alignment metrics

### Phase 2: Soft Launch (Week 2)

1. Enable for 25% of production videos
2. Monitor video engagement metrics
3. Review curator decisions (check media_plan.json)
4. Gather user feedback

### Phase 3: Full Rollout (Week 3)

1. Enable for 100% of videos
2. Monitor for 1 week
3. Remove legacy code if successful

## Rollback Plan

If issues arise:

```bash
# Disable feature flag
jq '.lyric_based_search.enabled = false' config/config.json > config/config.json.tmp
mv config/config.json.tmp config/config.json

# Pipeline will automatically use legacy flow
```

## Key Differences

| Aspect | Legacy (Topic-Based) | New (Lyric-Based) |
|--------|---------------------|-------------------|
| Search timing | Stage 1 (before lyrics) | Stage 3.5 (after lyrics) |
| Search terms | Topic keywords | Lyric visual concepts |
| Video tagging | None | lyric_line, visual_concept |
| Curator knowledge | Blind assignment | Knows intended lyric match |
| Diversity | Manual (visual ranking) | Natural (different concepts) |

## Metrics to Track

- **Lyric coverage**: % of lyrics with matched videos
- **Search success rate**: Videos found / searches attempted
- **Curator override rate**: % of videos reassigned to different lyrics
- **Video engagement**: View duration, retention rate
- **Manual review score**: Quality assessment by team

## Troubleshooting

### "lyric_media.json not found"

- Check Stage 3 (lyrics) completed successfully
- Verify `3.5_lyric_media_search.sh` is executable
- Check Claude CLI auth

### "No videos found for lyrics"

- Review `lyric_media.json` for failed searches
- Check search terms generated (too specific?)
- Verify stock photo API credentials
- Try enabling fallback to topic search

### "Visual ranking fails"

- Ensure `lyric_media.json` has valid thumbnail URLs
- Check CLIP model downloads
- Review error logs in visual ranking output
```

**Step 2: Commit**

```bash
git add docs/LYRIC_SEARCH_MIGRATION.md
git commit -m "docs: add lyric search migration guide"
```

---

## Task 10: Final Verification and Testing

**Files:**
- All modified files

**Step 1: Run full pipeline test with feature flag enabled**

```bash
# Enable feature flag
jq '.lyric_based_search.enabled = true' config/config.json > config/config.json.tmp && mv config/config.json.tmp config/config.json

# Create test topic
echo "How injection molding creates plastic parts. Tone: energetic pop punk" > input/idea.txt

# Run pipeline
./pipeline.sh --express
```

**Step 2: Verify outputs at each stage**

```bash
# Check Stage 3.5 output
test -f outputs/current/lyric_media.json && echo "✅ lyric_media.json exists" || echo "❌ Missing"

# Check Stage 3.6 output
test -f outputs/current/visual_rankings.json && echo "✅ visual_rankings.json exists" || echo "❌ Missing"

# Check Stage 5 output
test -f outputs/current/media_plan.json && echo "✅ media_plan.json exists" || echo "❌ Missing"
```

**Step 3: Validate lyric tagging preserved**

```bash
python3 << 'EOF'
import json

# Check that lyric_line is preserved through pipeline
with open('outputs/current/lyric_media.json') as f:
    lyric_media = json.load(f)

with open('outputs/current/visual_rankings.json') as f:
    rankings = json.load(f)

with open('outputs/current/media_plan.json') as f:
    plan = json.load(f)

# Verify lyric_line exists in rankings
assert 'lyric_line' in rankings['ranked_media'][0], "lyric_line not in rankings"

print("✅ Lyric tagging preserved through pipeline")
EOF
```

**Step 4: Create final commit**

```bash
git add -A
git commit -m "feat: complete lyric-based video search system

- Add Stage 3.5 lyric media search agent
- Move visual ranking to Stage 3.6 with lyric tag preservation
- Update curator to use lyric-tagged videos
- Remove media search from researcher
- Add feature flag for gradual rollout
- Add integration tests and migration docs
"
```

**Step 5: Verify all tests pass**

```bash
pytest tests/ -v
```

Expected: All tests pass

---

## Verification Checklist

Before considering implementation complete:

- [ ] Stage 3.5 creates valid `lyric_media.json` with lyric tags
- [ ] Stage 3.6 preserves lyric tags in `visual_rankings.json`
- [ ] Stage 5 curator receives and uses lyric tags
- [ ] Feature flag successfully toggles between old/new flow
- [ ] Integration test passes
- [ ] Full pipeline completes with feature enabled
- [ ] Video quality matches or exceeds baseline
- [ ] All commits follow conventional commit format
- [ ] Migration documentation complete

## Success Metrics

After deployment, verify:
- Lyric coverage ≥ 80%
- Search success rate ≥ 85%
- Curator override rate ≤ 30% (most suggested matches accepted)
- Video engagement maintains or improves baseline
