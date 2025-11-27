# Hybrid Clip Consolidation Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Decouple video clip duration from lyric phrase duration - allow longer video clips (5-15s) while maintaining phrase-level subtitle synchronization and semantic visual matching.

**Architecture:** Currently, the synchronized mode creates a 1:1 mapping between phrase groups and video clips, resulting in rapid cutting (86 clips for 65s). The hybrid approach will consolidate consecutive phrase groups into longer video segments while preserving semantic matching for visual relevance and phrase-level subtitle timing.

**Tech Stack:** Python, MoviePy, existing phrase grouper and semantic matcher

---

## Current State Analysis

**Files to understand:**
- `agents/5_assemble_video.py:217-285` - `create_synchronized_plan()` function
- `agents/5_assemble_video.py:145-214` - `fetch_and_process_lyrics()` function
- `config/config.json:61-69` - Lyric sync configuration
- `agents/semantic_matcher.py` - Semantic matching logic

**Current flow:**
1. Phrase grouper creates 86 semantic phrase groups (with 0.05s gap threshold)
2. Semantic matcher assigns one video to each phrase group
3. Video assembly creates 86 clips with rapid cuts
4. Each clip duration = phrase group duration (0.5-5s typically)

**Desired flow:**
1. Phrase grouper creates 86 semantic phrase groups (unchanged)
2. **NEW:** Consolidate consecutive phrase groups into longer segments (5-15s target)
3. Semantic matcher assigns one video to each consolidated segment
4. Video assembly creates ~10-15 clips with smooth pacing
5. Subtitles still animate at original phrase-level timing

---

## Task 1: Add Configuration Parameters

**Files:**
- Modify: `config/config.json:61-69`

**Step 1: Add clip consolidation settings to config**

Add new parameters to the `lyric_sync` section:

```json
  "lyric_sync": {
    "enabled": true,
    "min_phrase_duration": 1.5,
    "max_phrase_duration": 10.0,
    "phrase_gap_threshold": 0.05,
    "keyword_boost_multiplier": 2.0,
    "diversity_penalty": 0.1,
    "transition_duration": 0.3,
    "clip_consolidation": {
      "enabled": true,
      "target_clip_duration": 8.0,
      "min_clip_duration": 4.0,
      "max_clip_duration": 15.0,
      "semantic_coherence_threshold": 0.7
    }
  }
```

**Explanation:**
- `enabled`: Toggle clip consolidation on/off
- `target_clip_duration`: Ideal clip length in seconds (8s for shorts, could be longer for full videos)
- `min_clip_duration`: Minimum acceptable clip length (4s)
- `max_clip_duration`: Maximum clip length before forcing a cut (15s)
- `semantic_coherence_threshold`: Similarity threshold for merging phrase groups (0.7 = 70% topic overlap)

**Step 2: Verify configuration loads correctly**

Run:
```bash
./venv/bin/python3 -c "import json; print(json.load(open('config/config.json'))['lyric_sync']['clip_consolidation'])"
```

Expected output:
```json
{'enabled': True, 'target_clip_duration': 8.0, 'min_clip_duration': 4.0, 'max_clip_duration': 15.0, 'semantic_coherence_threshold': 0.7}
```

**Step 3: Commit configuration changes**

```bash
git add config/config.json
git commit -m "feat: add clip consolidation configuration"
```

---

## Task 2: Implement Clip Consolidation Logic

**Files:**
- Modify: `agents/5_assemble_video.py` (add new function before `create_synchronized_plan()`)

**Step 1: Write test for clip consolidation**

Create: `tests/test_clip_consolidation.py`

```python
#!/usr/bin/env python3
"""Tests for clip consolidation logic."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / 'agents'))

from consolidate_clips import consolidate_phrase_groups


def test_consolidate_merges_short_consecutive_groups():
    """Should merge consecutive phrase groups under target duration."""
    phrase_groups = [
        {
            "group_id": 1,
            "topic": "chlorophyll",
            "start_time": 0.0,
            "end_time": 2.0,
            "duration": 2.0,
            "key_terms": ["chlorophyll", "green"]
        },
        {
            "group_id": 2,
            "topic": "chlorophyll structure",
            "start_time": 2.1,
            "end_time": 4.0,
            "duration": 1.9,
            "key_terms": ["chlorophyll", "molecule"]
        },
        {
            "group_id": 3,
            "topic": "photosynthesis",
            "start_time": 4.2,
            "end_time": 7.0,
            "duration": 2.8,
            "key_terms": ["photosynthesis", "light"]
        }
    ]

    config = {
        "target_clip_duration": 8.0,
        "min_clip_duration": 4.0,
        "max_clip_duration": 15.0,
        "semantic_coherence_threshold": 0.7
    }

    result = consolidate_phrase_groups(phrase_groups, config)

    # Should consolidate groups 1+2 (similar topics) into one clip
    assert len(result) == 2
    assert result[0]["duration"] >= 3.9  # Groups 1+2 combined
    assert len(result[0]["phrase_groups"]) == 2
    assert result[1]["duration"] == 2.8  # Group 3 alone


def test_consolidate_respects_max_duration():
    """Should not exceed max_clip_duration."""
    phrase_groups = [
        {"group_id": i, "topic": "test", "start_time": i*5.0,
         "end_time": (i+1)*5.0, "duration": 5.0, "key_terms": ["test"]}
        for i in range(5)
    ]

    config = {
        "target_clip_duration": 8.0,
        "min_clip_duration": 4.0,
        "max_clip_duration": 12.0,
        "semantic_coherence_threshold": 0.9
    }

    result = consolidate_phrase_groups(phrase_groups, config)

    # No clip should exceed 12s
    for clip in result:
        assert clip["duration"] <= 12.0


def test_consolidate_preserves_phrase_group_metadata():
    """Should keep original phrase groups for subtitle timing."""
    phrase_groups = [
        {
            "group_id": 1,
            "topic": "test",
            "phrases": [{"text": "hello", "startS": 0.0, "endS": 1.0}],
            "start_time": 0.0,
            "end_time": 2.0,
            "duration": 2.0,
            "key_terms": ["test"]
        },
        {
            "group_id": 2,
            "topic": "test2",
            "phrases": [{"text": "world", "startS": 2.0, "endS": 3.0}],
            "start_time": 2.0,
            "end_time": 4.0,
            "duration": 2.0,
            "key_terms": ["test"]
        }
    ]

    config = {
        "target_clip_duration": 8.0,
        "min_clip_duration": 4.0,
        "max_clip_duration": 15.0,
        "semantic_coherence_threshold": 0.8
    }

    result = consolidate_phrase_groups(phrase_groups, config)

    # Should preserve phrase data for subtitles
    assert len(result[0]["phrase_groups"]) == 2
    assert result[0]["phrase_groups"][0]["phrases"][0]["text"] == "hello"
    assert result[0]["phrase_groups"][1]["phrases"][0]["text"] == "world"
```

**Step 2: Run test to verify it fails**

Run:
```bash
./venv/bin/python3 -m pytest tests/test_clip_consolidation.py -v
```

Expected: FAIL with "ModuleNotFoundError: No module named 'consolidate_clips'"

**Step 3: Implement consolidate_phrase_groups function**

Create: `agents/consolidate_clips.py`

```python
#!/usr/bin/env python3
"""
Clip consolidation logic for merging phrase groups into longer video segments.
"""

from typing import List, Dict


def calculate_topic_similarity(group1: Dict, group2: Dict) -> float:
    """
    Calculate semantic similarity between two phrase groups.

    Args:
        group1: First phrase group with key_terms
        group2: Second phrase group with key_terms

    Returns:
        Similarity score between 0.0 and 1.0
    """
    terms1 = set(group1.get("key_terms", []))
    terms2 = set(group2.get("key_terms", []))

    if not terms1 or not terms2:
        return 0.0

    # Jaccard similarity: intersection / union
    intersection = len(terms1 & terms2)
    union = len(terms1 | terms2)

    return intersection / union if union > 0 else 0.0


def consolidate_phrase_groups(phrase_groups: List[Dict], config: Dict) -> List[Dict]:
    """
    Consolidate consecutive phrase groups into longer video clips.

    Args:
        phrase_groups: List of phrase group dicts with timing and topics
        config: Consolidation config with target/min/max durations

    Returns:
        List of consolidated clip dicts, each containing multiple phrase groups
    """
    if not phrase_groups:
        return []

    target_duration = config["target_clip_duration"]
    min_duration = config["min_clip_duration"]
    max_duration = config["max_clip_duration"]
    coherence_threshold = config["semantic_coherence_threshold"]

    consolidated = []
    current_clip = {
        "clip_id": 1,
        "phrase_groups": [phrase_groups[0]],
        "start_time": phrase_groups[0]["start_time"],
        "end_time": phrase_groups[0]["end_time"],
        "duration": phrase_groups[0]["duration"],
        "topics": [phrase_groups[0]["topic"]],
        "key_terms": phrase_groups[0].get("key_terms", [])
    }

    for i in range(1, len(phrase_groups)):
        group = phrase_groups[i]
        current_duration = current_clip["duration"]

        # Calculate if adding this group would exceed max duration
        potential_duration = group["end_time"] - current_clip["start_time"]

        # Check semantic similarity with current clip
        similarity = calculate_topic_similarity(
            {"key_terms": current_clip["key_terms"]},
            group
        )

        # Decision: merge or start new clip
        should_merge = (
            # Under target duration - always try to merge
            (current_duration < target_duration and similarity >= coherence_threshold)
            # Or under min duration - must merge regardless of similarity
            or (current_duration < min_duration)
        ) and potential_duration <= max_duration

        if should_merge:
            # Merge into current clip
            current_clip["phrase_groups"].append(group)
            current_clip["end_time"] = group["end_time"]
            current_clip["duration"] = current_clip["end_time"] - current_clip["start_time"]
            current_clip["topics"].append(group["topic"])

            # Add unique key terms
            for term in group.get("key_terms", []):
                if term not in current_clip["key_terms"]:
                    current_clip["key_terms"].append(term)
        else:
            # Start new clip
            consolidated.append(current_clip)

            current_clip = {
                "clip_id": len(consolidated) + 1,
                "phrase_groups": [group],
                "start_time": group["start_time"],
                "end_time": group["end_time"],
                "duration": group["duration"],
                "topics": [group["topic"]],
                "key_terms": group.get("key_terms", [])
            }

    # Add final clip
    consolidated.append(current_clip)

    return consolidated
```

**Step 4: Run tests to verify they pass**

Run:
```bash
./venv/bin/python3 -m pytest tests/test_clip_consolidation.py -v
```

Expected: All tests PASS

**Step 5: Commit consolidation logic**

```bash
git add agents/consolidate_clips.py tests/test_clip_consolidation.py
git commit -m "feat: implement phrase group consolidation logic"
```

---

## Task 3: Integrate Consolidation into Video Assembly

**Files:**
- Modify: `agents/5_assemble_video.py:217-285` (update `create_synchronized_plan()`)

**Step 1: Import consolidation module**

At top of `agents/5_assemble_video.py`, add import after line 35:

```python
from consolidate_clips import consolidate_phrase_groups
```

**Step 2: Modify create_synchronized_plan to use consolidation**

Replace the current `create_synchronized_plan()` function (lines 217-285) with:

```python
def create_synchronized_plan(phrase_groups: List[Dict], approved_media: List[Dict], sync_config: dict) -> Dict:
    """
    Create synchronized media plan using semantic matching with clip consolidation.

    Args:
        phrase_groups: Phrase groups from AI
        approved_media: Available media from curator
        sync_config: Sync configuration including clip consolidation settings

    Returns:
        Synchronized plan dict
    """
    from semantic_matcher import SemanticMatcher

    logger = logging.getLogger(__name__)

    # Check if consolidation is enabled
    consolidation_config = sync_config.get("clip_consolidation", {})
    if consolidation_config.get("enabled", False):
        logger.info(f"Consolidating {len(phrase_groups)} phrase groups into longer clips...")

        # Consolidate phrase groups into longer segments
        consolidated_clips = consolidate_phrase_groups(phrase_groups, consolidation_config)

        logger.info(f"Created {len(consolidated_clips)} consolidated clips (avg {sum(c['duration'] for c in consolidated_clips)/len(consolidated_clips):.1f}s each)")

        # Match videos to consolidated clips (not individual phrase groups)
        matcher = SemanticMatcher(keyword_boost=sync_config["keyword_boost_multiplier"])

        shots = []
        for clip in consolidated_clips:
            # Use combined key terms from all phrase groups in this clip
            clip_description = f"{' / '.join(clip['topics'])}"
            clip_key_terms = clip['key_terms']

            # Create a temporary group for matching
            temp_group = {
                "topic": clip_description,
                "key_terms": clip_key_terms,
                "start_time": clip["start_time"],
                "end_time": clip["end_time"],
                "duration": clip["duration"],
                "phrases": []
            }

            # Flatten all phrases from all phrase groups in this clip
            for pg in clip["phrase_groups"]:
                temp_group["phrases"].extend(pg.get("phrases", []))

            # Match video to this consolidated clip
            matched_groups = matcher.match_videos_to_groups([temp_group], approved_media)

            if not matched_groups:
                logger.warning(f"No match for consolidated clip {clip['clip_id']}")
                continue

            matched = matched_groups[0]

            # Find media object
            media = next((m for m in approved_media if m.get("url") == matched["video_url"] or m.get("media_url") == matched["video_url"]), None)

            if not media or "local_path" not in media:
                logger.warning(f"No local media found for {matched['video_url']}, skipping")
                continue

            shot = {
                "shot_number": len(shots) + 1,
                "local_path": media["local_path"],
                "media_type": media.get("media_type", "video"),
                "description": clip_description,
                "start_time": clip["start_time"],
                "end_time": clip["end_time"],
                "duration": clip["duration"],
                "lyrics_match": " / ".join([p["text"] for pg in clip["phrase_groups"] for p in pg.get("phrases", [])]),
                "topic": clip_description,
                "key_terms": clip_key_terms,
                "match_score": matched["match_score"],
                "transition": "crossfade",
                "phrase_groups": clip["phrase_groups"]  # Preserve for subtitle timing
            }
            shots.append(shot)

    else:
        # Original behavior: match videos to individual phrase groups
        logger.info(f"Using original phrase-level matching for {len(phrase_groups)} groups")

        matcher = SemanticMatcher(keyword_boost=sync_config["keyword_boost_multiplier"])
        matched_groups = matcher.match_videos_to_groups(phrase_groups, approved_media)

        shots = []
        for group in matched_groups:
            media = next((m for m in approved_media if m.get("url") == group["video_url"] or m.get("media_url") == group["video_url"]), None)

            if not media or "local_path" not in media:
                logger.warning(f"No local media found for {group['video_url']}, skipping")
                continue

            shot = {
                "shot_number": len(shots) + 1,
                "local_path": media["local_path"],
                "media_type": media.get("media_type", "video"),
                "description": group["video_description"],
                "start_time": group["start_time"],
                "end_time": group["end_time"],
                "duration": max(group["duration"], sync_config["min_phrase_duration"]),
                "lyrics_match": " / ".join([p["text"] for p in group["phrases"]]),
                "topic": group["topic"],
                "key_terms": group["key_terms"],
                "match_score": group["match_score"],
                "transition": "crossfade",
                "phrase_groups": [group]  # Single phrase group
            }
            shots.append(shot)

    # Set first and last transitions to fade
    if shots:
        shots[0]["transition"] = "fade"
        shots[-1]["transition"] = "fade"

    total_duration = shots[-1]["end_time"] if shots else 0

    plan = {
        "shot_list": shots,
        "total_duration": total_duration,
        "total_shots": len(shots),
        "transition_style": "smooth",
        "pacing": "consolidated" if consolidation_config.get("enabled", False) else "synchronized",
        "sync_method": "suno_timestamps"
    }

    # Save synchronized plan
    sync_path = get_output_path("synchronized_plan.json")
    with open(sync_path, 'w') as f:
        json.dump(plan, f, indent=2)
    logger.info(f"Saved synchronized plan to {sync_path}")

    return plan
```

**Step 3: Test with existing run**

Run:
```bash
OUTPUT_DIR=outputs/runs/20251121_214448 ./venv/bin/python3 agents/5_assemble_video.py --resolution 1920x1080 2>&1 | grep -E "Consolidating|Created.*consolidated|Creating.*clips"
```

Expected output:
```
Consolidating 86 phrase groups into longer clips...
Created 10 consolidated clips (avg 6.5s each)
Creating 10 video clips...
```

**Step 4: Verify reduced clip count**

Run:
```bash
cat outputs/runs/20251121_214448/synchronized_plan.json | grep "total_shots"
```

Expected: `"total_shots": 10` (or similar, down from 86)

**Step 5: Commit integration**

```bash
git add agents/5_assemble_video.py
git commit -m "feat: integrate clip consolidation into synchronized plan"
```

---

## Task 4: Handle Subtitle Timing Independence

**Context:** Subtitles should still animate at phrase-level timing even though clips are longer.

**Files:**
- Verify: `agents/generate_subtitles.py` already handles this correctly
- The subtitle generator uses `lyrics_aligned.json` directly, independent of video clip duration

**Step 1: Verify subtitle generation is decoupled from clip timing**

Check that `generate_subtitles.py:336-357` filters words by segment timing, not by clip:

```python
# Load segment info if needed
if segment != 'full':
    segments_file = output_dir / 'segments.json'
    with open(segments_file) as f:
        segments = json.load(f)

    segment_info = segments[segment]

    # Filter words to segment timeframe
    words = [
        w for w in all_words
        if segment_info['start'] <= w['start'] <= segment_info['end']
    ]
```

This is correct - subtitles use lyric timestamps, not video clip boundaries.

**Step 2: Test subtitle generation with consolidated clips**

Run:
```bash
OUTPUT_DIR=outputs/runs/20251121_214448 ./venv/bin/python3 agents/generate_subtitles.py --engine ffmpeg --type traditional --video full
```

Expected: Subtitles generated successfully with phrase-level timing

**Step 3: Verify subtitle file shows phrase-level granularity**

Run:
```bash
head -30 outputs/runs/20251121_214448/subtitles/full_traditional.srt
```

Expected: Multiple subtitle entries spanning different times, not matched to clip boundaries

**No code changes needed** - subtitle system already decoupled from video timing.

**Step 4: Document this behavior**

Create: `docs/architecture/subtitle-clip-independence.md`

```markdown
# Subtitle and Clip Timing Independence

## Overview

The subtitle system operates independently from video clip timing, allowing phrase-level subtitle animation even when video clips span multiple phrases.

## Data Flow

1. **Lyric Timestamps** (`lyrics_aligned.json`)
   - Word-level timestamps from Suno API
   - Filtered to actual audio duration
   - Source of truth for subtitle timing

2. **Phrase Groups** (`phrase_groups.json`)
   - Grouped words by semantic topic
   - Used for video semantic matching
   - NOT used directly for subtitle timing

3. **Video Clips** (`synchronized_plan.json`)
   - Consolidated phrase groups (5-15s each)
   - Used for video assembly and cuts
   - Each clip contains `phrase_groups` metadata

4. **Subtitle Files** (`.srt`, `.ass`)
   - Generated from `lyrics_aligned.json` word timestamps
   - Phrase-level or word-level depending on style
   - Independent of video clip boundaries

## Example

A 10-second video clip might show a beach scene while 3 different subtitle phrases appear:

```
Clip 1 (0s-10s): Beach with palm trees
  Subtitle 1 (0s-3s): "Leaves are green as can be"
  Subtitle 2 (3s-6s): "Chlorophyll's the molecule"
  Subtitle 3 (6s-10s): "That helps them capture energy"
```

The video doesn't cut, but subtitles change every 3 seconds.

## Benefits

- Smoother visual experience (fewer jarring cuts)
- Precise lyric synchronization (word/phrase level)
- Semantic visual matching (relevant videos for topic)
```

**Step 5: Commit documentation**

```bash
git add docs/architecture/subtitle-clip-independence.md
git commit -m "docs: document subtitle and clip timing independence"
```

---

## Task 5: Add Toggle and Testing

**Files:**
- Modify: `agents/5_assemble_video.py` (add command-line flag)

**Step 1: Add --consolidate flag to argument parser**

In `agents/5_assemble_video.py:379-381`, add new argument:

```python
parser.add_argument('--no-sync',
                   action='store_true',
                   help='Disable synchronized assembly, use curator plan directly')
parser.add_argument('--no-consolidation',
                   action='store_true',
                   help='Disable clip consolidation, use phrase-level clips')
```

**Step 2: Pass flag to sync config**

In `agents/5_assemble_video.py:391`, after loading sync_config:

```python
sync_config = load_sync_config()

# Override consolidation setting if flag provided
if args.no_consolidation:
    if "clip_consolidation" not in sync_config:
        sync_config["clip_consolidation"] = {}
    sync_config["clip_consolidation"]["enabled"] = False
```

**Step 3: Test both modes side-by-side**

Test with consolidation (default):
```bash
OUTPUT_DIR=outputs/runs/20251121_214448 ./venv/bin/python3 agents/5_assemble_video.py --resolution 1920x1080 2>&1 | grep "Creating.*clips"
```

Expected: `Creating 10 video clips...` (or similar low number)

Test without consolidation:
```bash
OUTPUT_DIR=outputs/runs/20251121_214448 ./venv/bin/python3 agents/5_assemble_video.py --resolution 1920x1080 --no-consolidation 2>&1 | grep "Creating.*clips"
```

Expected: `Creating 86 video clips...` (original behavior)

**Step 4: Commit toggle feature**

```bash
git add agents/5_assemble_video.py
git commit -m "feat: add --no-consolidation flag for testing"
```

---

## Task 6: Integration Testing

**Files:**
- Create: `tests/test_integration_consolidation.py`

**Step 1: Write integration test**

```python
#!/usr/bin/env python3
"""Integration test for clip consolidation feature."""

import os
import json
import subprocess
from pathlib import Path


def test_consolidation_reduces_clip_count():
    """Verify consolidation creates fewer clips than phrase groups."""
    output_dir = "outputs/runs/20251121_214448"

    # Run with consolidation enabled
    result = subprocess.run(
        [
            "./venv/bin/python3",
            "agents/5_assemble_video.py",
            "--resolution", "1920x1080"
        ],
        env={**os.environ, "OUTPUT_DIR": output_dir},
        capture_output=True,
        text=True
    )

    assert result.returncode == 0, f"Assembly failed: {result.stderr}"

    # Load results
    plan_path = Path(output_dir) / "synchronized_plan.json"
    assert plan_path.exists(), "Synchronized plan not created"

    with open(plan_path) as f:
        plan = json.load(f)

    phrase_groups_path = Path(output_dir) / "phrase_groups.json"
    with open(phrase_groups_path) as f:
        phrase_groups = json.load(f)

    # Verify clip count is significantly reduced
    num_clips = plan["total_shots"]
    num_phrase_groups = len(phrase_groups)

    assert num_clips < num_phrase_groups * 0.3, \
        f"Expected <30% clips, got {num_clips}/{num_phrase_groups}"

    # Verify average clip duration increased
    avg_duration = plan["total_duration"] / num_clips
    assert avg_duration >= 4.0, \
        f"Expected avg clip duration >= 4s, got {avg_duration:.1f}s"

    print(f"✅ Consolidation: {num_phrase_groups} phrase groups → {num_clips} clips (avg {avg_duration:.1f}s)")


def test_consolidation_preserves_phrase_metadata():
    """Verify consolidated clips preserve phrase groups for subtitles."""
    output_dir = "outputs/runs/20251121_214448"
    plan_path = Path(output_dir) / "synchronized_plan.json"

    with open(plan_path) as f:
        plan = json.load(f)

    # Check each shot has phrase_groups metadata
    for shot in plan["shot_list"]:
        assert "phrase_groups" in shot, \
            f"Shot {shot['shot_number']} missing phrase_groups"
        assert len(shot["phrase_groups"]) >= 1, \
            f"Shot {shot['shot_number']} has no phrase groups"

        # Verify phrase groups have required fields for subtitles
        for pg in shot["phrase_groups"]:
            assert "phrases" in pg or "start_time" in pg, \
                f"Phrase group missing subtitle timing data"

    print(f"✅ All {len(plan['shot_list'])} shots have phrase metadata")


if __name__ == "__main__":
    test_consolidation_reduces_clip_count()
    test_consolidation_preserves_phrase_metadata()
    print("\n✅ All integration tests passed!")
```

**Step 2: Run integration test**

Run:
```bash
./venv/bin/python3 tests/test_integration_consolidation.py
```

Expected output:
```
✅ Consolidation: 86 phrase groups → 10 clips (avg 6.5s)
✅ All 10 shots have phrase metadata

✅ All integration tests passed!
```

**Step 3: Commit integration tests**

```bash
git add tests/test_integration_consolidation.py
git commit -m "test: add integration tests for clip consolidation"
```

---

## Task 7: Update Documentation

**Files:**
- Create: `docs/features/clip-consolidation.md`
- Modify: `README.md` (add feature documentation)

**Step 1: Document the feature**

Create: `docs/features/clip-consolidation.md`

```markdown
# Clip Consolidation Feature

## Overview

Clip consolidation merges consecutive semantic phrase groups into longer video segments, creating smoother visual pacing while maintaining phrase-level subtitle synchronization.

## Problem Solved

Without consolidation:
- 86 phrase groups → 86 video clips for a 65s song
- Rapid cutting every 0.5-2 seconds
- Jarring viewing experience

With consolidation:
- 86 phrase groups → ~10-15 video clips
- Smooth cuts every 5-10 seconds
- Professional pacing
- Subtitles still sync at phrase level

## Configuration

Edit `config/config.json`:

```json
{
  "lyric_sync": {
    "clip_consolidation": {
      "enabled": true,
      "target_clip_duration": 8.0,
      "min_clip_duration": 4.0,
      "max_clip_duration": 15.0,
      "semantic_coherence_threshold": 0.7
    }
  }
}
```

### Parameters

- **enabled**: Toggle consolidation on/off
- **target_clip_duration**: Ideal clip length (8s recommended for shorts)
- **min_clip_duration**: Minimum before forcing merge (4s)
- **max_clip_duration**: Maximum before forcing cut (15s)
- **semantic_coherence_threshold**: Min similarity to merge (0.7 = 70% topic overlap)

## Algorithm

1. **Start with first phrase group** as current clip
2. **For each subsequent phrase group:**
   - Calculate semantic similarity (Jaccard index of key terms)
   - Check if adding would exceed max duration
   - **Merge if:**
     - Under target duration AND similarity ≥ threshold
     - OR under min duration (force merge)
     - AND won't exceed max duration
   - **Start new clip if** merge conditions not met
3. **Result:** Consolidated clips with metadata

## Example

Input (3 phrase groups):
```
Group 1: "Chlorophyll" (0-2s, terms: [chlorophyll, green])
Group 2: "Chlorophyll structure" (2-4s, terms: [chlorophyll, molecule])
Group 3: "Photosynthesis" (4-7s, terms: [photosynthesis, light])
```

Output (2 consolidated clips):
```
Clip 1: "Chlorophyll / Chlorophyll structure" (0-4s)
  - Phrase groups: [1, 2]
  - Similarity: 50% (chlorophyll in common)
  - Duration: 4s

Clip 2: "Photosynthesis" (4-7s)
  - Phrase groups: [3]
  - Similarity: 0% (no overlap)
  - Duration: 3s
```

## Testing

Disable consolidation:
```bash
./agents/5_assemble_video.py --no-consolidation
```

Compare results:
```bash
# With consolidation (default)
grep "total_shots" outputs/current/synchronized_plan.json
# "total_shots": 12

# Without consolidation
./agents/5_assemble_video.py --no-consolidation
grep "total_shots" outputs/current/synchronized_plan.json
# "total_shots": 86
```

## Subtitle Independence

Subtitles are generated from `lyrics_aligned.json` word timestamps, independent of video clip boundaries. A single 10s clip can show 3-4 different subtitle phrases.

See: [Subtitle and Clip Timing Independence](../architecture/subtitle-clip-independence.md)
```

**Step 2: Add to main README**

In `README.md`, add section after existing features:

```markdown
## Features

- Automated educational music video generation
- Multi-format output (1 full 16:9 + 2 vertical 9:16 shorts)
- Lyric-synchronized video with semantic visual matching
- **Clip consolidation** for smooth pacing (configurable)
- Karaoke and traditional subtitle styles
- YouTube upload automation

### Clip Consolidation

Creates professional pacing by merging phrase groups into longer clips (5-15s) while maintaining phrase-level subtitle sync. Configure in `config/config.json`:

```json
{
  "lyric_sync": {
    "clip_consolidation": {
      "enabled": true,
      "target_clip_duration": 8.0
    }
  }
}
```

See [docs/features/clip-consolidation.md](docs/features/clip-consolidation.md) for details.
```

**Step 3: Commit documentation**

```bash
git add docs/features/clip-consolidation.md README.md
git commit -m "docs: add clip consolidation feature documentation"
```

---

## Final Verification Steps

**Step 1: Run full end-to-end test**

```bash
./pipeline.sh --express
```

Expected:
- Pipeline completes successfully
- Videos created with ~10-15 clips instead of 86
- Subtitles still sync at phrase level
- Audio matches video duration

**Step 2: Verify video quality**

```bash
# Check full video
ffprobe outputs/current/full.mp4 2>&1 | grep Duration

# Count clips in synchronized plan
jq '.total_shots' outputs/current/synchronized_plan.json
```

Expected:
- Full video duration matches audio
- Clip count: 10-20 (reasonable range)

**Step 3: Manual QA**

Open and review:
```bash
open outputs/current/full.mp4
```

Verify:
- [ ] Smooth video pacing (not too many cuts)
- [ ] Subtitles change at appropriate times
- [ ] Videos match lyric topics semantically
- [ ] No audio cutoff issues
- [ ] Subtitle font sizes are readable

---

## Rollback Plan

If issues arise, disable consolidation:

**Quick disable:**
```bash
# Edit config
sed -i '' 's/"enabled": true/"enabled": false/' config/config.json

# Or use flag
./agents/5_assemble_video.py --no-consolidation
```

**Full revert:**
```bash
git revert HEAD~7  # Revert last 7 commits (all tasks)
```

---

## Success Criteria

- [ ] Configuration added and loads correctly
- [ ] Unit tests pass for consolidation logic
- [ ] Integration tests pass for full pipeline
- [ ] Clip count reduced from 86 to 10-20
- [ ] Average clip duration 5-15 seconds
- [ ] Subtitles still sync at phrase level
- [ ] Video quality maintained
- [ ] Documentation complete
- [ ] Feature toggleable via config and flag
