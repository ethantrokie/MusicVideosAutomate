# Enable Lyric Synchronization Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Enable word-level lyric synchronization so video clips appear exactly when those lyrics are sung, rather than being placed sequentially.

**Architecture:** Modify `agents/build_format_media_plan.py` to load phrase groups with lyric timestamps from `phrase_groups.json` and assign clips to their actual song timestamps instead of sequential video timeline positions. The existing semantic matching logic remains unchanged; only the timing source changes from sequential counters to actual lyric timestamps.

**Tech Stack:** Python 3, JSON, ffprobe (for media duration), existing semantic matching infrastructure

---

## Background

**Current Problem:**
- Clips are placed sequentially (0s, 16s, 24s, etc.) in output video timeline
- This is disconnected from when lyrics are actually sung (0.39s, 1.13s, 2.23s, etc.)
- Word-level timestamps from Suno exist but are unused for clip placement

**Current Architecture:**
- `lyrics_aligned.json` has word-level timestamps from Suno ✓
- `phrase_groups.json` has consolidated phrase timing ✓
- `build_format_media_plan.py` creates sequential timing (WRONG) ✗
- Config has `lyric_sync.enabled: true` but it's bypassed ✗

**Files Involved:**
- **Main file:** `agents/build_format_media_plan.py` (needs modification)
- **Data source:** `phrase_groups.json` (already exists, needs loading)
- **Alternative data:** `lyrics_aligned.json` (fallback if phrase_groups missing)
- **Config:** `config/config.json` (lyric_sync settings)

---

## Task 1: Add Phrase Groups Loading Function

**Files:**
- Modify: `agents/build_format_media_plan.py:27-47`

**Step 1: Add function to load phrase groups**

Add this function after the `get_media_duration()` function:

```python
def load_phrase_groups() -> List[Dict]:
    """
    Load phrase groups with lyric timestamps.
    Returns empty list if file doesn't exist (graceful degradation).
    """
    phrase_groups_path = get_output_path("phrase_groups.json")

    if not phrase_groups_path.exists():
        print("  ⚠️  phrase_groups.json not found, will use sequential timing")
        return []

    try:
        with open(phrase_groups_path) as f:
            phrase_groups = json.load(f)

        print(f"  ✓ Loaded {len(phrase_groups)} phrase groups with lyric timestamps")
        return phrase_groups
    except Exception as e:
        print(f"  ⚠️  Error loading phrase_groups.json: {e}, using sequential timing")
        return []
```

**Step 2: Verify the function compiles**

Run: `python3 -m py_compile agents/build_format_media_plan.py`
Expected: No output (success)

**Step 3: Commit**

```bash
git add agents/build_format_media_plan.py
git commit -m "feat: add phrase groups loading function for lyric sync"
```

---

## Task 2: Add Semantic Phrase-to-Clip Matcher

**Files:**
- Modify: `agents/build_format_media_plan.py` (add after `load_phrase_groups()`)

**Step 1: Add phrase matching function**

```python
def match_clips_to_phrase_groups(
    phrase_groups: List[Dict],
    available_clips: List[Dict]
) -> List[Dict]:
    """
    Match each phrase group to the best available clip using semantic similarity.

    Args:
        phrase_groups: List of phrase groups with start_time, end_time, key_terms
        available_clips: List of clips with description, lyrics_match metadata

    Returns:
        List of phrase groups with matched clip data added
    """
    from difflib import SequenceMatcher

    matched_groups = []
    used_clip_indices = set()

    for group in phrase_groups:
        # Build search text from phrase group
        phrase_text = group.get("topic", "")
        key_terms = " ".join(group.get("key_terms", []))
        search_text = f"{phrase_text} {key_terms}".lower()

        # Find best matching clip
        best_score = 0
        best_clip_idx = None

        for idx, clip in enumerate(available_clips):
            # Prefer unused clips, but allow reuse if needed
            reuse_penalty = 0.3 if idx in used_clip_indices else 0

            # Score based on description and lyrics_match
            clip_text = f"{clip.get('description', '')} {clip.get('lyrics_match', '')}".lower()

            # Simple word overlap score
            search_words = set(search_text.split())
            clip_words = set(clip_text.split())
            overlap = len(search_words & clip_words)
            total = len(search_words | clip_words)
            score = (overlap / total if total > 0 else 0) - reuse_penalty

            if score > best_score:
                best_score = score
                best_clip_idx = idx

        # Add matched clip data to group
        if best_clip_idx is not None:
            matched_group = group.copy()
            matched_group["matched_clip"] = available_clips[best_clip_idx]
            matched_group["match_score"] = best_score
            matched_groups.append(matched_group)
            used_clip_indices.add(best_clip_idx)
        else:
            print(f"  ⚠️  No clip match for phrase group {group.get('group_id', '?')}")

    return matched_groups
```

**Step 2: Verify compilation**

Run: `python3 -m py_compile agents/build_format_media_plan.py`
Expected: No output

**Step 3: Commit**

```bash
git add agents/build_format_media_plan.py
git commit -m "feat: add semantic phrase-to-clip matcher for lyric sync"
```

---

## Task 3: Create Synchronized Shot List Builder

**Files:**
- Modify: `agents/build_format_media_plan.py` (add after `match_clips_to_phrase_groups()`)

**Step 1: Add function to build synchronized shots**

```python
def build_synchronized_shot_list(
    matched_groups: List[Dict],
    segment_start: float,
    segment_end: float
) -> List[Dict]:
    """
    Build shot list with lyric-synchronized timing.
    Filters phrase groups to segment time range and creates shots with actual timestamps.

    Args:
        matched_groups: Phrase groups with matched clips
        segment_start: Segment start time in seconds (e.g., 30 for hook)
        segment_end: Segment end time in seconds (e.g., 45 for hook)

    Returns:
        List of shots with synchronized start_time, end_time from lyrics
    """
    shots = []
    shot_number = 1

    # Filter groups to this segment's time range
    segment_groups = [
        g for g in matched_groups
        if g["start_time"] < segment_end and g["end_time"] > segment_start
    ]

    print(f"    📍 Found {len(segment_groups)} phrase groups in segment range {segment_start}-{segment_end}s")

    for group in segment_groups:
        clip = group.get("matched_clip")
        if not clip:
            continue

        # Use ACTUAL lyric timestamps from phrase group
        lyric_start = max(group["start_time"], segment_start)
        lyric_end = min(group["end_time"], segment_end)
        duration = lyric_end - lyric_start

        # Adjust timing to segment-relative (0-based for this segment)
        relative_start = lyric_start - segment_start
        relative_end = lyric_end - segment_start

        shot = {
            "shot_number": shot_number,
            "local_path": clip["local_path"],
            "media_type": clip.get("media_type", "video"),
            "media_url": clip.get("media_url", ""),
            "description": clip.get("description", ""),
            "lyrics_match": group.get("topic", ""),
            "source": clip.get("source", ""),
            "transition": clip.get("transition", "crossfade"),
            "priority": clip.get("priority", "normal"),
            # SYNCHRONIZED TIMING - from actual lyrics
            "start_time": relative_start,
            "end_time": relative_end,
            "duration": duration,
            # Preserve phrase group for debugging
            "phrase_group_id": group.get("group_id"),
            "absolute_start": lyric_start,  # For debugging
            "absolute_end": lyric_end,
            "match_score": group.get("match_score", 0)
        }

        shots.append(shot)
        shot_number += 1

    return shots
```

**Step 2: Verify compilation**

Run: `python3 -m py_compile agents/build_format_media_plan.py`
Expected: No output

**Step 3: Commit**

```bash
git add agents/build_format_media_plan.py
git commit -m "feat: add synchronized shot list builder with lyric timestamps"
```

---

## Task 4: Integrate Synchronized Timing into build_format_plan()

**Files:**
- Modify: `agents/build_format_media_plan.py:362-500`

**Step 1: Find the build_format_plan() function**

Locate this function around line 362. It currently has sequential timing logic.

**Step 2: Add phrase groups loading at function start**

Find the line with `available_clips = load_available_media()` (around line 382) and add after it:

```python
    # Load phrase groups for lyric synchronization
    phrase_groups = load_phrase_groups()
    use_lyric_sync = len(phrase_groups) > 0

    if use_lyric_sync:
        print(f"  ✓ Lyric synchronization ENABLED - using phrase group timestamps")
        # Match clips to phrase groups semantically
        matched_groups = match_clips_to_phrase_groups(phrase_groups, available_clips)
        print(f"    Matched {len(matched_groups)} phrase groups to clips")
    else:
        print(f"  ⚠️  Lyric synchronization DISABLED - using sequential timing fallback")
        matched_groups = []
```

**Step 3: Replace sequential timing logic with synchronized timing**

Find the shot list building section (around line 393-440). Replace the entire loop that builds `shot_list` with:

```python
    # Build shot list with synchronized or sequential timing
    if use_lyric_sync:
        # Get segment boundaries from segments.json
        segment_info = segments.get(format_type, {})
        segment_start = segment_info.get("start", 0)
        segment_end = segment_info.get("end", target_duration)

        # Build synchronized shots
        shot_list = build_synchronized_shot_list(
            matched_groups,
            segment_start,
            segment_end
        )

        # Calculate total duration from shots
        total_duration = max((s["end_time"] for s in shot_list), default=0) if shot_list else 0

        print(f"    ✓ Created {len(shot_list)} synchronized shots (duration: {total_duration:.1f}s)")

    else:
        # FALLBACK: Sequential timing (original logic)
        shot_list = []
        current_duration = 0.0
        shot_number = 1

        # Cycle through clips to fill duration
        clip_cycle = itertools.cycle(available_clips)

        while current_duration < target_duration and shot_number <= len(available_clips) * 3:
            clip = next(clip_cycle)
            clip_duration = min(
                clip["actual_duration"],
                target_duration - current_duration
            )

            if clip_duration <= 0:
                break

            shot = {
                "shot_number": shot_number,
                "local_path": clip["local_path"],
                "media_type": clip.get("media_type", "video"),
                "media_url": clip.get("media_url", ""),
                "description": clip.get("description", ""),
                "lyrics_match": clip.get("lyrics_match", ""),
                "source": clip.get("source", ""),
                "transition": clip.get("transition", "crossfade"),
                "priority": clip.get("priority", "normal"),
                "start_time": current_duration,
                "end_time": current_duration + clip_duration,
                "duration": clip_duration,
                "original_shot": clip["shot_number"]
            }

            shot_list.append(shot)
            current_duration += clip_duration
            shot_number += 1

        total_duration = current_duration
        print(f"    ✓ Created {len(shot_list)} sequential shots (duration: {total_duration:.1f}s)")
```

**Step 4: Verify compilation**

Run: `python3 -m py_compile agents/build_format_media_plan.py`
Expected: No output

**Step 5: Commit**

```bash
git add agents/build_format_media_plan.py
git commit -m "feat: integrate lyric synchronization into format plan builder"
```

---

## Task 5: Test with Existing Run Data

**Files:**
- Test data: `outputs/runs/20251229_090019/`

**Step 1: Run the modified script on existing data**

```bash
# Set environment to use specific run directory
export OUTPUT_DIR="outputs/runs/20251229_090019"

# Run the format plan builder
python3 agents/build_format_media_plan.py
```

Expected output:
```
✓ Loaded 27 phrase groups with lyric timestamps
✓ Lyric synchronization ENABLED - using phrase group timestamps
Matched 27 phrase groups to clips
📍 Found X phrase groups in segment range 30-45s
✓ Created X synchronized shots (duration: 15.0s)
```

**Step 2: Verify generated media plan has lyric timestamps**

```bash
# Check hook media plan
jq '.shot_list[0:3] | .[] | {shot: .shot_number, start: .start_time, end: .end_time, lyrics: .lyrics_match}' outputs/runs/20251229_090019/media_plan_hook.json
```

Expected: Should show non-sequential timing (e.g., 0.0, 2.47, 5.23) not (0, 16, 24)

**Step 3: Commit test verification**

```bash
git add outputs/runs/20251229_090019/media_plan_*.json
git commit -m "test: verify lyric synchronization with run 20251229_090019"
```

---

## Task 6: Add Graceful Degradation Test

**Files:**
- Test: Manual testing with missing phrase_groups.json

**Step 1: Test fallback to sequential timing**

```bash
# Temporarily move phrase_groups.json
mv outputs/runs/20251229_090019/phrase_groups.json outputs/runs/20251229_090019/phrase_groups.json.backup

# Run format plan builder
export OUTPUT_DIR="outputs/runs/20251229_090019"
python3 agents/build_format_media_plan.py
```

Expected output:
```
⚠️  phrase_groups.json not found, will use sequential timing
⚠️  Lyric synchronization DISABLED - using sequential timing fallback
✓ Created X sequential shots (duration: 15.0s)
```

**Step 2: Verify sequential timing is used as fallback**

```bash
jq '.shot_list[0:3] | .[] | {shot: .shot_number, start: .start_time, end: .end_time}' outputs/runs/20251229_090019/media_plan_hook.json
```

Expected: Sequential timing (0, 16, 24, etc.)

**Step 3: Restore phrase_groups.json**

```bash
mv outputs/runs/20251229_090019/phrase_groups.json.backup outputs/runs/20251229_090019/phrase_groups.json
```

**Step 4: Document test results**

```bash
git add docs/plans/2025-12-29-enable-lyric-synchronization.md
git commit -m "test: verify graceful degradation to sequential timing"
```

---

## Task 7: Run End-to-End Pipeline Test

**Files:**
- Test: Full pipeline run from scratch

**Step 1: Run complete pipeline with fresh topic**

```bash
# Create test topic
echo "How radar systems detect and track aircraft using electromagnetic waves and doppler shift. Tone: energetic electronic with driving synths" > input/idea.txt

# Run pipeline
./pipeline.sh
```

**Step 2: Monitor for synchronized timing being used**

During Stage 6 (Multi-format videos), look for:
```
✓ Loaded X phrase groups with lyric timestamps
✓ Lyric synchronization ENABLED - using phrase group timestamps
```

**Step 3: Verify output video timing**

After pipeline completes, check the media plan:

```bash
# Find the latest run
LATEST_RUN=$(ls -t outputs/runs/ | head -1)

# Check synchronized timing
jq '.shot_list[0:5] | .[] | {shot: .shot_number, start: .start_time, end: .end_time, absolute_start: .absolute_start, lyrics: .lyrics_match}' outputs/runs/$LATEST_RUN/media_plan_hook.json
```

Expected:
- Non-sequential timing
- `absolute_start` values match actual lyric timestamps
- Different clips for different lyrics (not just 2 repeated)

**Step 4: Commit successful test**

```bash
git add docs/plans/2025-12-29-enable-lyric-synchronization.md
git commit -m "test: verify end-to-end lyric synchronization in full pipeline"
```

---

## Task 8: Create Summary Documentation

**Files:**
- Create: `automation/LYRIC_SYNC_IMPLEMENTATION_2025-12-29.md`

**Step 1: Create implementation summary**

```markdown
# Lyric Synchronization Implementation - December 29, 2025

## Problem Solved

Video clips were placed sequentially (0s, 16s, 24s) instead of being synchronized to when lyrics are actually sung (0.39s, 1.13s, 2.23s), causing visual-audio mismatch.

## Solution Implemented

Modified `agents/build_format_media_plan.py` to:
1. Load phrase groups with lyric timestamps from `phrase_groups.json`
2. Match clips to phrase groups using semantic similarity
3. Assign clips to their actual lyric timestamps instead of sequential positions
4. Gracefully degrade to sequential timing if phrase groups unavailable

## Files Modified

1. `agents/build_format_media_plan.py`
   - Added `load_phrase_groups()` - loads lyric timing data
   - Added `match_clips_to_phrase_groups()` - semantic clip matching
   - Added `build_synchronized_shot_list()` - creates shots with lyric timestamps
   - Modified `build_format_plan()` - integrates synchronized timing

## How It Works

**Before:**
```python
"start_time": current_duration,  # Sequential: 0, 16, 24, 32...
"end_time": current_duration + clip_duration
```

**After:**
```python
"start_time": phrase_group["start_time"],  # Lyric sync: 0.39, 1.13, 2.23...
"end_time": phrase_group["end_time"]
```

## Testing

- ✓ Tested with existing run 20251229_090019 - synchronized timing works
- ✓ Tested fallback without phrase_groups.json - sequential timing works
- ✓ End-to-end pipeline test - verified in production

## Impact

- Clips now appear exactly when those lyrics are sung
- Natural rhythm alignment between visuals and music
- Maintains backward compatibility via graceful degradation

## Configuration

No config changes needed. Feature automatically enabled when `phrase_groups.json` exists (created by existing Stage 3 lyric generation).
```

**Step 2: Save documentation**

```bash
git add automation/LYRIC_SYNC_IMPLEMENTATION_2025-12-29.md
git commit -m "docs: add lyric synchronization implementation summary"
```

---

## Verification Commands

After implementation, verify the fix:

```bash
# 1. Check if phrase groups are being loaded
export OUTPUT_DIR="outputs/runs/$(ls -t outputs/runs/ | head -1)"
python3 agents/build_format_media_plan.py 2>&1 | grep -i "phrase groups"

# 2. Compare timing: old vs new
echo "Old sequential timing:"
jq '.shot_list[0:3] | .[] | .start_time' outputs/runs/20251224_090030/media_plan_hook.json

echo "New synchronized timing:"
jq '.shot_list[0:3] | .[] | .start_time' outputs/runs/$(ls -t outputs/runs/ | head -1)/media_plan_hook.json

# 3. Verify absolute timestamps match lyrics
jq '.shot_list[0] | {lyrics: .lyrics_match, absolute_start: .absolute_start, absolute_end: .absolute_end}' outputs/runs/$(ls -t outputs/runs/ | head -1)/media_plan_hook.json
```

---

## Rollback Plan

If issues arise, revert with:

```bash
git revert HEAD~8..HEAD  # Revert all 8 commits from this plan
```

The system will gracefully fall back to sequential timing if `phrase_groups.json` is missing.
