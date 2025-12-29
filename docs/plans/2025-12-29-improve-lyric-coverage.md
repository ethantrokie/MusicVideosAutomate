# Improve Lyric Coverage Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Improve lyric media search coverage from 45% to 80-90% by enhancing the prompt to group related lyric lines and implement retry logic for failed searches.

**Architecture:** Modify `agents/prompts/lyric_media_search_prompt.md` with phrase-based grouping instructions, increased concept targets (25-35 vs 15-20), intelligent filler word skipping, and retry fallback logic. No code changes required - purely prompt engineering to guide the LLM agent.

**Tech Stack:** Markdown prompt engineering, Claude CLI (claude-haiku-4-5 model), Pexels/Pixabay/Giphy APIs

---

## Background Context

**Problem:** Hook segment videos repeat because only 2/7 lyric lines have videos searched for them. Root cause: lyric media search extracts only 18 concepts for 40-line songs (~45% coverage), leaving gaps that break segment-based filtering.

**Current Behavior:**
- `lyric_media_search_prompt.md` targets "15-20 visual concepts" (line 48)
- Result: 18 concepts for 219-second song
- Hook segment (30-45s) contains 7 lyric lines
- Only 2/7 have videos → repetitive output

**Solution:** Enhance prompt to target 25-35 concepts with phrase-based grouping and retry logic.

---

## Task 1: Update Coverage Target Section

**Files:**
- Modify: `agents/prompts/lyric_media_search_prompt.md:44-48`

**Step 1: Read current coverage section**

Run: `cat agents/prompts/lyric_media_search_prompt.md | sed -n '44,48p'`

Expected output:
```
## Target Coverage

- **Goal**: 20-30 videos total for ~180s video
- **Per Concept**: 1-2 videos
- **Concepts**: Extract 15-20 visual concepts from lyrics
```

**Step 2: Replace with enhanced coverage targets**

```markdown
## Target Coverage & Grouping Strategy

**Coverage Goal: 80-90% of lyric lines (excluding intelligent filler word detection)**

- **Total Videos**: 25-35 for ~180s video (roughly 1 concept per 5-7 seconds)
- **Per Concept**: 1-2 videos
- **Concepts to Extract**: 25-35 visual concepts using phrase-based grouping
- **Grouping Strategy**: Cluster 2-4 related lyric lines into cohesive visual concepts
- **Skip Intelligently**: Repeated filler words ("oh", "yeah", "[Instrumental]"), but PRESERVE all educational/topic-specific content

**Why Phrase-Based Grouping?**
- Reduces total searches (faster execution, lower cost)
- Improves lyric coverage (no orphaned lines)
- Creates more cohesive visual segments
- Better handles poetic language that needs context

**Example Grouping:**

Bad (line-by-line, gaps):
- "Planetary gears, spinning all around" → 1 concept
- "Sun, planets, and ring - that's the sound" → SKIPPED (no video)
- "Hold one still, spin another one fast" → SKIPPED (no video)

Good (phrase-based, full coverage):
- "Planetary gears, spinning all around / Sun, planets, and ring - that's the sound / Hold one still, spin another one fast" → "Planetary gear components (sun, ring, carrier) and their mechanical interaction" → 2-3 videos ✓
```

Run:
```bash
# Create the edit (this is the exact content to replace lines 44-48)
```

**Step 3: Verify the change**

Run: `cat agents/prompts/lyric_media_search_prompt.md | sed -n '44,75p'`

Expected: New coverage section with phrase-based grouping explanation

**Step 4: Commit the coverage enhancement**

```bash
git add agents/prompts/lyric_media_search_prompt.md
git commit -m "feat: enhance lyric coverage target from 15-20 to 25-35 concepts

- Increase coverage goal from ~45% to 80-90%
- Add phrase-based grouping strategy (2-4 lines per concept)
- Document intelligent filler word detection
- Include grouping examples for clarity"
```

---

## Task 2: Add Phrase Construction Guidelines

**Files:**
- Modify: `agents/prompts/lyric_media_search_prompt.md` (insert after line 48, before "## IMPORTANT")

**Step 1: Insert new section for phrase construction**

Insert this section after the "Target Coverage" section:

```markdown
## Phrase Construction Guidelines

**When analyzing lyrics, group related lines into visual concepts:**

### 1. Identify Natural Phrase Boundaries

Look for:
- **Repeated concepts** across 2-4 consecutive lines
- **Cause-and-effect sequences** ("X happens, which causes Y")
- **Component listings** ("Part A, Part B, Part C")
- **Process descriptions** spanning multiple lines
- **Complete thoughts** that need full context

### 2. Create Searchable Visual Concepts

For each phrase group, extract:
- **Core visual**: What can be filmed or animated?
- **Key components**: Which elements must appear in the video?
- **Action/motion**: Is something moving, changing, or interacting?

### 3. Generate Effective Search Terms

Convert phrase to 2-4 word search query:
- **Remove poetic language**: "meshing teeth on this power ride" → "interlocking gears rotating"
- **Use technical terms when appropriate**: "planetary gears" (good for mechanical topics)
- **Prioritize visual action**: "gears spinning" > "gear concepts"

### 4. Examples

**Topic: Planetary Gears in Transmissions**

Lyric Phrase (3 lines grouped):
```
Planetary gears, spinning all around
Sun, planets, and ring - that's the sound
Hold one still, spin another one fast
```

Visual Concept: "Planetary gear set showing sun gear, planet gears, and ring gear in mechanical interaction"

Search Term: "planetary gear transmission animation"

**Topic: Photosynthesis**

Lyric Phrase (2 lines grouped):
```
Chloroplasts trap the photons flying in
Converting light to chemical energy within
```

Visual Concept: "Chloroplast structure absorbing light and converting to chemical energy"

Search Term: "chloroplast photosynthesis animation"

**Filler to Skip:**
```
[Chorus]
Oh, oh, oh yeah!
Mmm, mmm
```

Rationale: No educational value, purely musical filler
```

Run: Edit to insert this section

**Step 2: Verify insertion**

Run: `grep -A 5 "## Phrase Construction Guidelines" agents/prompts/lyric_media_search_prompt.md`

Expected: New section appears with all guidelines

**Step 3: Commit phrase construction guidelines**

```bash
git add agents/prompts/lyric_media_search_prompt.md
git commit -m "feat: add phrase construction guidelines for lyric grouping

- Document how to identify natural phrase boundaries
- Provide visual concept extraction process
- Include search term generation best practices
- Add concrete examples for mechanical and biological topics"
```

---

## Task 3: Add Retry Logic with Fallback Search Terms

**Files:**
- Modify: `agents/prompts/lyric_media_search_prompt.md:17-42` (Media Search Tool section)

**Step 1: Enhance media search section with retry logic**

Replace the existing "Media Search Tool" section (lines 17-42) with:

```markdown
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

**CRITICAL: Retry Logic for Failed Searches**

If a search returns **0 results** or fails:

1. **Simplify the search term** by:
   - Removing technical jargon → broader concepts
   - Abstracting to parent category
   - Using more common terminology
   - Reducing to 1-2 core visual words

2. **Retry ONCE** with simplified term

3. **Document in output** which searches failed and used fallback

**Retry Examples:**

| Original Search | Result | Fallback Search | Result |
|----------------|--------|----------------|--------|
| "planetary gear sun ring carrier" | 0 videos | "mechanical gears rotating" | 3 videos ✓ |
| "epicyclic transmission mechanism" | 0 videos | "car transmission gears" | 5 videos ✓ |
| "torque multiplication ratio change" | 0 videos | "gear ratio mechanics" | 2 videos ✓ |
| "chloroplast thylakoid stroma" | 0 videos | "plant cell photosynthesis" | 4 videos ✓ |

**Implementation Pattern:**

```bash
# Try primary search
python agents/search_media.py "planetary gear sun ring carrier" --type=video --max=2 --json

# If 0 results → retry with simplified term
python agents/search_media.py "mechanical gears rotating" --type=video --max=2 --json
```

**Document Fallbacks in Output:**

In the JSON output, mark which searches used fallback:

```json
{
  "lyric_line": "Sun, planets, and ring - that's the sound",
  "visual_concept": "Planetary gear components",
  "search_term": "mechanical gears rotating",
  "search_fallback": true,
  "original_search_term": "planetary gear sun ring carrier",
  "fallback_reason": "Original search returned 0 results",
  "videos": [...]
}
```
```

**Step 2: Verify the retry logic is clear**

Run: `grep -A 10 "CRITICAL: Retry Logic" agents/prompts/lyric_media_search_prompt.md`

Expected: Full retry logic section with examples table

**Step 3: Commit retry logic enhancement**

```bash
git add agents/prompts/lyric_media_search_prompt.md
git commit -m "feat: add retry logic with fallback search terms

- Implement automatic retry for failed searches (0 results)
- Define simplification strategy (remove jargon, broaden terms)
- Add retry examples table showing before/after
- Document fallback tracking in JSON output schema"
```

---

## Task 4: Update Output Schema with Coverage Metrics

**Files:**
- Modify: `agents/prompts/lyric_media_search_prompt.md:66-90` (Output Format section)

**Step 1: Enhance JSON schema with new fields**

Replace the output schema section with:

```markdown
## Output Format

Write your output to `{{OUTPUT_PATH}}` in the following JSON format.

**Requirements**:
- **URLs must be DIRECT media page URLs**, not search/explore pages
- **Media must be from Pexels, Pixabay, or Giphy only**
- **Output valid JSON only**
- **Include coverage metrics** for debugging and validation

```json
{
  "media_by_lyric": [
    {
      "lyric_line": "Exact lyric line or phrase group from the song",
      "visual_concept": "Brief description of what this represents visually",
      "search_term": "The actual search query used (may be fallback)",
      "search_fallback": false,
      "original_search_term": null,
      "fallback_reason": null,
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
  "coverage_metrics": {
    "total_lyric_lines": 40,
    "lines_with_videos": 35,
    "coverage_percentage": 87.5,
    "filler_lines_skipped": 5,
    "skipped_lines": [
      "[Chorus]",
      "Oh, oh, oh yeah!",
      "Mmm, mmm",
      "[Instrumental Break]",
      "Yeah, yeah!"
    ],
    "skip_rationale": "Musical filler with no educational content"
  },
  "search_metrics": {
    "total_searches": 28,
    "successful_searches": 26,
    "failed_searches": 2,
    "fallback_searches_used": 4,
    "total_videos_found": 32
  },
  "concepts_extracted": 28,
  "total_videos": 32
}
```

**Coverage Validation:**

After generating output, verify:
- `coverage_percentage` ≥ 80%
- `skipped_lines` only contains true filler (no educational content)
- `fallback_searches_used` < 30% of total searches (if higher, topic may be too obscure)

Begin analysis.
```

**Step 2: Verify schema update**

Run: `grep -A 20 "coverage_metrics" agents/prompts/lyric_media_search_prompt.md`

Expected: New coverage_metrics and search_metrics sections in JSON schema

**Step 3: Commit output schema enhancement**

```bash
git add agents/prompts/lyric_media_search_prompt.md
git commit -m "feat: enhance output schema with coverage and search metrics

- Add coverage_metrics object tracking percentage and skipped lines
- Add search_metrics object tracking success/failure/fallback rates
- Include validation criteria (≥80% coverage target)
- Document fallback fields in media_by_lyric entries"
```

---

## Task 5: End-to-End Testing with Real Lyrics

**Files:**
- Test with: `outputs/runs/20251224_090030/suno_output.json`
- Expected output: `outputs/runs/20251224_090030/lyric_media.json` (regenerated)

**Step 1: Back up existing lyric media output**

```bash
cp outputs/runs/20251224_090030/lyric_media.json outputs/runs/20251224_090030/lyric_media.json.backup_before_enhancement
```

Run: `ls -lh outputs/runs/20251224_090030/lyric_media.json*`

Expected: Both original and backup files exist

**Step 2: Run lyric media search with enhanced prompt**

```bash
# Set OUTPUT_DIR for test
export OUTPUT_DIR="outputs/runs/20251224_090030"

# Run the lyric media search agent (Stage 2.5)
# This uses the updated prompt automatically
./agents/2_5_lyric_media.sh
```

Expected: Agent runs and generates new `lyric_media.json`

**Step 3: Verify coverage improvement**

```bash
# Check coverage metrics
jq '.coverage_metrics' outputs/runs/20251224_090030/lyric_media.json
```

Expected output structure:
```json
{
  "total_lyric_lines": 40,
  "lines_with_videos": 34,
  "coverage_percentage": 85.0,
  "filler_lines_skipped": 6,
  "skipped_lines": ["[Chorus]", "Oh, oh", ...],
  "skip_rationale": "Musical filler with no educational content"
}
```

Validation criteria:
- ✅ `coverage_percentage` ≥ 80
- ✅ `concepts_extracted` ≥ 25
- ✅ Hook segment lyrics (30-45s) should have videos for 5-7 out of 7 lines

**Step 4: Compare before/after coverage**

```bash
# Before (from backup)
echo "=== BEFORE ==="
jq '{concepts_extracted, total_videos}' outputs/runs/20251224_090030/lyric_media.json.backup_before_enhancement

# After (new)
echo "=== AFTER ==="
jq '{coverage_metrics, concepts_extracted, total_videos}' outputs/runs/20251224_090030/lyric_media.json
```

Expected improvement:
- Before: 18 concepts, ~45% coverage
- After: 25-35 concepts, 80-90% coverage

**Step 5: Verify hook segment coverage specifically**

```bash
# Extract hook segment lyrics (30-45s from segments.json)
jq '.hook' outputs/runs/20251224_090030/segments.json

# Check which hook lyrics now have videos
# This requires manual inspection of lyric_media.json
echo "=== Hook Segment Lyrics (30-45s) ==="
echo "around the outside"
echo "They're all meshing teeth on this power ride!"
echo "[Chorus]"
echo "Planetary gears, spinning all around"
echo "Sun, planets, and ring - that's the sound"
echo "Hold one still, spin another one fast"
echo "Different speeds from"

# Count how many are in lyric_media.json
jq '.media_by_lyric[] | select(.lyric_line | contains("meshing teeth") or contains("Planetary gears") or contains("Sun, planets") or contains("Hold one still"))' outputs/runs/20251224_090030/lyric_media.json | jq -s 'length'
```

Expected: At least 3-4 of the 7 hook lines have videos (previously only 2)

**Step 6: Commit test results**

```bash
# Document test in commit
git add outputs/runs/20251224_090030/lyric_media.json.backup_before_enhancement
git commit -m "test: verify lyric coverage enhancement with real planetary gears song

Before: 18 concepts, ~45% coverage, hook segment had 2/7 lines
After: [ACTUAL_CONCEPTS] concepts, [ACTUAL_PERCENTAGE]% coverage, hook segment has [ACTUAL_COUNT]/7 lines

Backup of original output preserved for comparison."
```

---

## Task 6: Run Full Pipeline to Verify Fixed Repetition

**Files:**
- Run: `./pipeline.sh --resume=20251224_090030 --start=6` (rebuild format videos with new lyric_media.json)
- Verify: `outputs/runs/20251224_090030/media_plan_hook.json` no longer has repetitive clips

**Step 1: Rebuild format media plans with improved coverage**

```bash
# Resume from Stage 6 (build format plans) using new lyric_media.json
./pipeline.sh --resume=20251224_090030 --start=6
```

Expected: Stage 6 completes successfully, new `media_plan_hook.json` generated

**Step 2: Analyze hook video plan for repetition**

```bash
# Check how many unique shots are used
echo "=== Hook Video Shot Analysis ==="
jq '.shot_list | map(.original_shot) | unique | length' outputs/runs/20251224_090030/media_plan_hook.json

# Before enhancement: 2 unique shots (shot_04 and shot_05 repeated 12 times)
# After enhancement: Should be 5-8 unique shots
```

Run: Verify unique shot count

Expected: 5-8 unique shots (vs 2 before)

**Step 3: Verify lyric match distribution**

```bash
# Count shots per lyric match
echo "=== Lyric Match Distribution ==="
jq '.shot_list | group_by(.lyrics_match) | map({lyric: .[0].lyrics_match, count: length})' outputs/runs/20251224_090030/media_plan_hook.json
```

Expected: Multiple different lyric matches (vs only 2 before)

**Step 4: Check filtering log for segment matches**

```bash
# Look for the segment filtering output in pipeline log
grep "Using.*clips matching segment lyrics" logs/pipeline_*.log | tail -1
```

Before: `Using 2/30 clips matching segment lyrics`
After: `Using 12-18/30 clips matching segment lyrics` (should be higher)

**Step 5: Visual spot check of generated video**

```bash
# Play the hook video to visually verify variety
# (Requires video player)
open outputs/runs/20251224_090030/videos/short_hook.mp4
```

Manual verification:
- ✅ No obvious repetition of same clips back-to-back
- ✅ Visual variety throughout 15-second hook
- ✅ Clips align well with lyric content

**Step 6: Commit verification results**

```bash
git add outputs/runs/20251224_090030/media_plan_hook.json
git commit -m "test: verify hook video no longer has repetitive clips

Before: 2 unique shots repeated 12 times (only 2/7 hook lyrics had videos)
After: [ACTUAL_COUNT] unique shots with better distribution

Segment filtering now matches [ACTUAL_MATCH_COUNT]/30 clips vs 2/30 before.
Lyric coverage improvement successfully fixed repetition issue."
```

---

## Task 7: Document Enhancement in FIXES_APPLIED.md

**Files:**
- Modify: `automation/FIXES_APPLIED.md` (append new entry)

**Step 1: Add fix documentation**

```bash
cat >> automation/FIXES_APPLIED.md << 'EOF'

## 2025-12-29: Lyric Coverage Enhancement (Repetitive Hook Clips Fix)

**Issue**: Hook segment videos showed repetitive clips because only 2 out of 7 lyric lines had videos searched for them. Root cause was insufficient lyric coverage in media search stage (18 concepts for 40-line song = 45% coverage).

**Fix**: Enhanced `agents/prompts/lyric_media_search_prompt.md` with:
- Increased concept target from 15-20 to 25-35 (targeting 80-90% coverage)
- Phrase-based grouping strategy (cluster 2-4 related lyric lines)
- Intelligent filler word detection (skip "oh yeah" but preserve educational content)
- Retry logic with fallback search terms for failed searches
- Coverage metrics in JSON output for validation

**Testing**: Ran full pipeline on planetary gears song (run 20251224_090030):
- Before: 18 concepts, 2/7 hook lyrics had videos → 2 unique shots repeated
- After: [ACTUAL] concepts, [ACTUAL]/7 hook lyrics with videos → [ACTUAL] unique shots

**Impact**: Segment-based filtering now works correctly because lyric coverage is comprehensive. Multi-format videos (full, hook short, educational short) no longer suffer from repetitive clips due to missing lyric matches.

**Files Modified**:
- agents/prompts/lyric_media_search_prompt.md
- docs/plans/2025-12-29-improve-lyric-coverage.md (this plan)

**Verification Command**:
```bash
# Run pipeline and check hook video coverage
./pipeline.sh
jq '.coverage_metrics.coverage_percentage' outputs/runs/*/lyric_media.json | tail -1
# Should show ≥80%
```
EOF
```

**Step 2: Verify documentation**

Run: `tail -40 automation/FIXES_APPLIED.md`

Expected: New entry with complete fix description

**Step 3: Commit documentation**

```bash
git add automation/FIXES_APPLIED.md
git commit -m "docs: document lyric coverage enhancement fix

Records enhancement of media search prompt to achieve 80-90% lyric
coverage, fixing repetitive clips issue in hook/educational shorts."
```

---

## Verification Summary

After completing all tasks, verify:

1. ✅ Prompt file updated with all enhancements
2. ✅ Coverage target: 25-35 concepts (was 15-20)
3. ✅ Phrase-based grouping guidelines added
4. ✅ Retry logic with fallback search terms implemented
5. ✅ Output schema includes coverage metrics
6. ✅ Test shows ≥80% coverage (was ~45%)
7. ✅ Hook video no longer repetitive (5-8 unique shots vs 2)
8. ✅ Documentation updated in FIXES_APPLIED.md

**Success Criteria:**
- `lyric_media.json` shows `coverage_percentage` ≥ 80
- `media_plan_hook.json` uses 5-8+ unique shots (not just 2)
- Visual inspection shows variety in hook video

**Rollback Plan (if needed):**
```bash
# Restore original prompt
git checkout HEAD~7 -- agents/prompts/lyric_media_search_prompt.md

# Restore original lyric_media.json
cp outputs/runs/20251224_090030/lyric_media.json.backup_before_enhancement outputs/runs/20251224_090030/lyric_media.json
```
