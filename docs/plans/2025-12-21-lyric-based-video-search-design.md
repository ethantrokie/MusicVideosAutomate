# Lyric-Based Video Search System Design

**Date:** 2025-12-21
**Status:** Design Complete, Ready for Implementation

## Problem Statement

Currently, video search happens in Stage 1 (Research) BEFORE lyrics exist. This means:
- Videos are searched using generic topic terms (e.g., "injection molding")
- Curator must guess which videos match which lyrics
- No semantic connection between lyric content and video selection

## Solution Overview

Move video search to AFTER lyrics are generated, using actual lyric content to drive video searches. Each video will be tagged with the lyric line that inspired its search.

## Architecture

### Modified Pipeline Flow

```
1. Stage 1: Research (MODIFIED)
   - Focus: Key facts and concepts only
   - Output: research.json (NO media_suggestions)
   - Purpose: Inform lyric writing with accurate information

2. Stage 3: Lyrics Generation (UNCHANGED)
   - Uses research facts to write accurate lyrics
   - Output: lyrics.json

3. NEW Stage 3.5: Lyric-Based Media Search
   - Analyzes lyrics to extract visual concepts
   - Searches for videos based on lyric content
   - Output: lyric_media.json with videos tagged by source lyric
   - Replaces old researcher's media_suggestions

4. Stage 3.6: Visual Ranking (MOVED + MODIFIED)
   - Was Stage 2, now runs after lyric media search
   - Loads videos from lyric_media.json
   - Preserves lyric_line tags during ranking
   - Output: visual_rankings.json (with lyric tags)

5. Stage 4: Music Composition (UNCHANGED)

6. Stage 5: Media Curation (MODIFIED)
   - Receives lyric-tagged, ranked videos
   - Validates/overrides lyric assignments
   - Creates final shot list with timing
```

### Key Benefits

- **Targeted Search**: Videos searched specifically for lyric content
- **Semantic Alignment**: Strong connection between lyrics and visuals
- **Curator Intelligence**: Curator knows WHY each video was chosen
- **Natural Diversity**: Different lyric concepts → diverse video results
- **Quality Assurance**: Visual ranking still filters for quality

## Detailed Component Design

### Stage 3.5: Lyric-Based Media Search

**Component:** `agents/3.5_lyric_media_search.sh` + `agents/prompts/lyric_media_search_prompt.md`

**Input:**
- `lyrics.json` (from Stage 3)
- Topic from `research.json` for context

**Process:**

1. **Lyric Analysis**
   - Parse lyrics line-by-line or section-by-section
   - Extract visual concepts from meaningful phrases
   - Example:
     - Lyric: "Molecules vibrate billions of times per second"
     - Visual concept: "molecular vibration high frequency"

2. **Search Term Generation**
   - AI converts lyric concepts into effective search terms
   - Avoids literal lyric phrases (too poetic/abstract)
   - Focuses on visual, filmable concepts
   - Example: "microwave ovens making water molecules spin"
     → "molecular motion animation," "microwave radiation," "water heating process"

3. **Video Search**
   - Uses existing `search_media.py` tool (same as current research agent)
   - For each visual concept:
     ```bash
     python agents/search_media.py "molecular motion" --type=video --max=2 --json
     ```
   - Aim for 1-2 videos per concept
   - Target total: 20-30 videos (for ~180s video with 4-5s shots)

**Output Format:** `lyric_media.json`
```json
{
  "media_by_lyric": [
    {
      "lyric_line": "Molecules vibrate billions of times per second",
      "visual_concept": "molecular vibration high frequency",
      "search_term": "molecular motion animation",
      "videos": [
        {
          "url": "https://pexels.com/video/...",
          "source": "pexels",
          "description": "Animated molecules in rapid motion",
          "thumbnail_url": "https://..."
        }
      ]
    }
  ],
  "total_videos": 25,
  "lyric_coverage": "90%"
}
```

### Stage 3.6: Visual Ranking (Modified)

**Component:** Modified `agents/3_rank_visuals.py`

**Input Changes:**
- OLD: `research.json` with `media_suggestions`
- NEW: `lyric_media.json` with lyric-tagged videos
- Still loads `research.json` for `key_facts` (relevance scoring)

**Code Modifications:**

```python
# OLD: Load from research.json
with open('research.json') as f:
    research = json.load(f)
candidates = research.get('media_suggestions', [])

# NEW: Load from lyric_media.json
with open('lyric_media.json') as f:
    lyric_media = json.load(f)

# Flatten media_by_lyric while preserving lyric metadata
candidates = []
for lyric_entry in lyric_media['media_by_lyric']:
    for video in lyric_entry['videos']:
        video['lyric_line'] = lyric_entry['lyric_line']  # Preserve tag!
        video['visual_concept'] = lyric_entry['visual_concept']
        candidates.append(video)
```

**Output:** `visual_rankings.json` (enhanced with lyric metadata)
```json
{
  "ranked_media": [
    {
      "url": "https://pexels.com/video/...",
      "rank": 1,
      "visual_score": 0.87,
      "lyric_line": "Molecules vibrate billions of times per second",
      "visual_concept": "molecular vibration high frequency",
      "source": "pexels"
    }
  ],
  "metadata": {
    "total_analyzed": 25,
    "ranking_method": "mmr",
    "lambda": 0.7
  }
}
```

### Stage 5: Curator (Modified)

**Component:** Modified `agents/4_curate_media.sh` + `agents/prompts/curator_prompt.md`

**Input Changes:**
- OLD: `research_pruned_for_curator.json` with generic `media_suggestions`
- NEW: `visual_rankings.json` with lyric-tagged ranked videos
- UNCHANGED: `lyrics.json`

**Role Changes:**

**OLD Curator Behavior:**
- Received generic media URLs
- Had to guess which media matches which lyric
- Manual lyric→video assignment

**NEW Curator Behavior:**
- Receives videos already tagged with source lyric
- Can validate that tagged lyric still makes sense
- Can override lyric assignment if video fits better elsewhere
- Prioritizes using videos for their intended lyric lines

**Updated Prompt Instructions:**

```markdown
## Input Context
- **Ranked Media**: Each video is tagged with the lyric_line that inspired its search
- **Lyrics Data**: Full song lyrics for timing and flow

## Your Enhanced Task
1. **Review lyric→video mappings**: Each video has a suggested lyric_line match
2. **Validate or override**: Keep suggested matches or reassign if a video fits better elsewhere
3. **Prioritize intended matches**: Prefer using videos for their source lyric when quality is good
4. **Select best-ranked**: Among videos for same lyric, choose highest visual_score
5. **Create shot list**: Assign timing, transitions, and final sequence
```

**Decision-Making Example:**
```json
// Video comes in tagged:
{
  "url": "...",
  "rank": 3,
  "lyric_line": "Molecules vibrate billions of times",
  "visual_concept": "molecular vibration"
}

// Curator can:
// ✅ KEEP: Use for "Molecules vibrate..." (intended)
// OR
// ✅ OVERRIDE: Move to "Creating friction that generates heat" (if better fit)
```

## Implementation Impact

### Files to Create

1. `agents/3.5_lyric_media_search.sh` - New bash script for Stage 3.5
2. `agents/prompts/lyric_media_search_prompt.md` - Prompt for lyric analysis & search

### Files to Modify

1. `agents/prompts/researcher_prompt.md`
   - Remove media search instructions (lines 13-50)
   - Focus only on key facts extraction

2. `agents/3_rank_visuals.py`
   - Change input from `research.json` to `lyric_media.json`
   - Preserve lyric metadata during flattening
   - Add lyric fields to ranked output

3. `agents/4_curate_media.sh`
   - Change input from `research_pruned_for_curator.json` to `visual_rankings.json`
   - Update data loading logic

4. `agents/prompts/curator_prompt.md`
   - Update input context section
   - Add lyric validation/override instructions
   - Update task description

5. `pipeline.sh`
   - Add Stage 3.5 call after Stage 3 (lyrics)
   - Move Stage 2 (visual ranking) to Stage 3.6
   - Update stage numbering

6. `agents/context_pruner.py`
   - Remove researcher pruning for media (or adjust)
   - No longer needed to prune media for curator

## Migration Strategy

### Backward Compatibility

To ensure smooth transition, implement feature flag:

```json
// In config/config.json
{
  "lyric_based_search": {
    "enabled": false  // Start disabled
  }
}
```

**When disabled:**
- Use old flow (research generates media)
- Visual ranking uses research.json
- Curator uses research data

**When enabled:**
- Use new flow (lyric-based search)
- Visual ranking uses lyric_media.json
- Curator uses visual_rankings.json

### Testing Plan

1. **Unit Test**: Test lyric concept extraction
2. **Integration Test**: Run full pipeline with feature flag enabled
3. **Comparison Test**: Compare old vs new video selection quality
4. **A/B Test**: Generate videos both ways, compare engagement

## Risk Mitigation

### Risk 1: Insufficient Videos from Lyric Search
**Mitigation:** If lyric-based search returns < 15 videos, fall back to topic-based search as supplement

### Risk 2: Poor Lyric→Search Term Conversion
**Mitigation:** Provide extensive examples in prompt of good conversions

### Risk 3: Visual Ranking Takes Longer
**Mitigation:** Already minimal change, same algorithm, just different input source

## Success Metrics

- **Coverage**: >80% of lyrics have matching videos
- **Quality**: Visual ranking scores ≥ current baseline
- **Relevance**: Manual review shows strong lyric-video alignment
- **Performance**: Pipeline completes in similar time (±10%)

## Future Enhancements

1. **Multi-pass Search**: If first search yields insufficient results, try alternate search terms
2. **Fallback Pool**: Maintain small pool of generic topic videos as backup
3. **Learning**: Track which lyric→search conversions work best, improve over time
4. **Segment-Specific**: Different search strategies for chorus vs verse

## Appendix: Example End-to-End Flow

**Topic:** "How injection molding creates plastic parts"

**Stage 1 Output (research.json):**
```json
{
  "key_facts": [
    "Injection molding forces molten plastic through heated barrel",
    "Plastic injected into precision mold cavity at high pressure",
    "Cooling solidifies plastic in seconds"
  ]
  // NO media_suggestions
}
```

**Stage 3 Output (lyrics.json):**
```json
{
  "lyrics": "Molten polymer flows through heated steel / High pressure forces plastic into the mold / Cooling down in seconds makes it real / Identical parts from the same old fold"
}
```

**Stage 3.5 Output (lyric_media.json):**
```json
{
  "media_by_lyric": [
    {
      "lyric_line": "Molten polymer flows through heated steel",
      "visual_concept": "molten plastic injection process",
      "search_term": "injection molding machine close up",
      "videos": [
        {"url": "https://pexels.com/video/injection-molding-123/", "source": "pexels"}
      ]
    },
    {
      "lyric_line": "High pressure forces plastic into the mold",
      "visual_concept": "high pressure plastic injection",
      "search_term": "plastic mold filling",
      "videos": [
        {"url": "https://pexels.com/video/mold-filling-456/", "source": "pexels"}
      ]
    }
  ]
}
```

**Stage 3.6 Output (visual_rankings.json):**
```json
{
  "ranked_media": [
    {
      "url": "https://pexels.com/video/injection-molding-123/",
      "rank": 1,
      "visual_score": 0.92,
      "lyric_line": "Molten polymer flows through heated steel"
    },
    {
      "url": "https://pexels.com/video/mold-filling-456/",
      "rank": 2,
      "visual_score": 0.88,
      "lyric_line": "High pressure forces plastic into the mold"
    }
  ]
}
```

**Stage 5 Output (media_plan.json):**
```json
{
  "shot_list": [
    {
      "shot_number": 1,
      "media_url": "https://pexels.com/video/injection-molding-123/",
      "start_time": 0,
      "end_time": 4,
      "lyrics_match": "Molten polymer flows through heated steel",
      "source_lyric_line": "Molten polymer flows through heated steel"
    }
  ]
}
```
