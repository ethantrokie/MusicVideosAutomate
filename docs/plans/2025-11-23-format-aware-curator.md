# Format-Aware Media Curator Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix video duration issues by making the media curator format-aware, allowing it to generate appropriate media plans for full videos (180s) versus shorts (30s).

**Architecture:** The curator will accept a target duration parameter and dynamically adjust its media plan. The build_multiformat_videos.py script will call the curator three times (once per format) to generate format-specific media plans. The video assembly will use these format-specific plans instead of extracting shorts from a truncated full video.

**Tech Stack:** Python 3, Bash, MoviePy, FFmpeg, Claude Code CLI

---

## Problem Summary

**Root Causes Identified:**
1. Curator hardcoded to 60s (agents/prompts/curator_prompt.md:13)
2. Multi-format system expects 180s full video (segments.json)
3. Media download failures reduce video further (60s → 36s)
4. Shorts extracted using fixed timestamps from truncated video

**Current Flow (BROKEN):**
```
Curator → 60s media plan → Video assembly → 36s video (due to download failures)
                                                ↓
                        build_multiformat_videos.py extracts shorts with fixed timestamps
                                                ↓
                        Educational: 10-40s from 36s video = 26s (WRONG)
                        Hook: 30-60s from 36s video = 6s (WRONG)
```

**Target Flow (FIXED):**
```
For full video:    Curator(180s) → 180s media plan → 180s video
For edu short:     Curator(30s)  → 30s media plan  → 30s video
For hook short:    Curator(30s)  → 30s media plan  → 30s video
```

---

## Task 1: Add Duration Parameter to Curator Script

**Files:**
- Modify: `agents/4_curate_media.sh`

**Step 1: Add duration parameter to curator script**

Modify `agents/4_curate_media.sh` to accept `--duration` parameter:

```bash
# After line 5, add parameter parsing
DURATION="${DURATION:-60}"  # Default to 60 for backward compatibility

# Parse command-line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --duration)
            DURATION="$2"
            shift 2
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done
```

**Step 2: Pass duration to prompt template**

Modify the prompt substitution (around line 34) to include duration:

```bash
# Replace the sed command with:
TEMP_PROMPT=$(mktemp)
sed -e "s|{{OUTPUT_PATH}}|${OUTPUT_DIR}/media_plan.json|g" \
    -e "s|{{VIDEO_DURATION}}|${DURATION}|g" \
    agents/prompts/curator_prompt.md > "$TEMP_PROMPT"
```

**Step 3: Update output message to show duration**

Around line 76, modify the output to include duration:

```bash
echo "✅ Media curation complete: ${OUTPUT_DIR}/media_plan.json"
echo "  Target duration: ${DURATION}s"
echo ""
python3 -c "
import json
data = json.load(open('${OUTPUT_DIR}/media_plan.json'))
print(f\"  Total shots: {data['total_shots']}\")
print(f\"  Duration: {data['total_duration']} seconds\")
print(f\"  Pacing: {data['pacing']}\")
"
```

**Step 4: Test the parameter**

Run: `DURATION=180 ./agents/4_curate_media.sh --duration 120`
Expected: Should fail gracefully with "Unknown option" since both methods provided

Run: `OUTPUT_DIR=outputs/test DURATION=90 ./agents/4_curate_media.sh`
Expected: Should pick up DURATION from environment

**Step 5: Commit**

```bash
git add agents/4_curate_media.sh
git commit -m "feat: add duration parameter to curator script

- Accept --duration flag and DURATION env var
- Pass duration to prompt template
- Default to 60s for backward compatibility"
```

---

## Task 2: Make Curator Prompt Template Duration-Aware

**Files:**
- Modify: `agents/prompts/curator_prompt.md:13`

**Step 1: Replace hardcoded duration with template variable**

Change line 13 from:
```markdown
**Video Duration**: 60 seconds
```

To:
```markdown
**Video Duration**: {{VIDEO_DURATION}} seconds
```

**Step 2: Update timing guidelines to be dynamic**

Replace the "Timing Guidelines" section (lines 43-48) with:

```markdown
## Timing Guidelines

**Total video**: {{VIDEO_DURATION}} seconds

**Calculate shots needed**: For {{VIDEO_DURATION}}s, aim for {{SHOT_COUNT}} shots
- Short format (30s): 6-8 shots (4-5s each)
- Medium format (60s): 12-15 shots (4-5s each)
- Long format (180s): 35-45 shots (4-5s each)

**Typical shot**: 4-5 seconds per media
**Fast cuts**: 3-4 seconds (energetic moments)
**Slow shots**: 6-8 seconds (important concepts)
```

**Step 3: Update total_duration in output example**

Around line 84, change:
```json
"total_duration": 60,
```

To:
```json
"total_duration": {{VIDEO_DURATION}},
```

**Step 4: Verify template variables**

Check that all occurrences of hardcoded "60" are replaced:

Run: `grep -n "60" agents/prompts/curator_prompt.md`
Expected: Only in examples or context, not as requirements

**Step 5: Commit**

```bash
git add agents/prompts/curator_prompt.md
git commit -m "feat: make curator prompt duration-aware

- Replace hardcoded 60s with {{VIDEO_DURATION}} template variable
- Add dynamic shot count guidelines based on duration
- Update examples to use template variable"
```

---

## Task 3: Create Format-Specific Media Plan Builder

**Files:**
- Create: `agents/build_format_media_plan.py`

**Step 1: Create new Python script for format-specific curation**

Create `agents/build_format_media_plan.py`:

```python
#!/usr/bin/env python3
"""
Build format-specific media plans for multi-format video generation.
Creates separate media plans optimized for each format's duration and aspect ratio.
"""

import os
import sys
import json
import subprocess
from pathlib import Path
from typing import Dict, Literal

FormatType = Literal["full", "hook", "educational"]


def get_output_path(filename: str) -> Path:
    """Get path in OUTPUT_DIR."""
    output_dir = os.getenv("OUTPUT_DIR", "outputs")
    return Path(output_dir) / filename


def get_format_config(format_type: FormatType, segments: Dict) -> Dict:
    """Get duration and configuration for each format."""
    configs = {
        "full": {
            "duration": segments["full"]["duration"],
            "output_file": "media_plan_full.json",
            "description": "Full horizontal video"
        },
        "hook": {
            "duration": segments["hook"]["duration"],
            "output_file": "media_plan_hook.json",
            "description": "Hook short vertical video"
        },
        "educational": {
            "duration": segments["educational"]["duration"],
            "output_file": "media_plan_educational.json",
            "description": "Educational short vertical video"
        }
    }
    return configs[format_type]


def build_media_plan(format_type: FormatType, duration: int, output_file: str) -> bool:
    """
    Call curator to build media plan for specific format.

    Args:
        format_type: Type of video format
        duration: Target duration in seconds
        output_file: Output filename for media plan

    Returns:
        True if successful, False otherwise
    """
    print(f"  Building {format_type} media plan ({duration}s)...")

    # Set output path for this format's media plan
    output_dir = os.getenv("OUTPUT_DIR", "outputs")
    format_output = os.path.join(output_dir, output_file)

    # Temporarily override OUTPUT_PATH in curator
    original_output = get_output_path("media_plan.json")

    try:
        # Call curator with format-specific duration
        env = os.environ.copy()
        env["DURATION"] = str(duration)
        env["OUTPUT_DIR"] = output_dir

        # Run curator, capturing output to avoid cluttering logs
        result = subprocess.run(
            ["./agents/4_curate_media.sh"],
            env=env,
            capture_output=True,
            text=True,
            timeout=120
        )

        if result.returncode != 0:
            print(f"    ❌ Curator failed for {format_type}")
            print(f"    Error: {result.stderr}")
            return False

        # Rename media_plan.json to format-specific file
        if original_output.exists():
            original_output.rename(format_output)
            print(f"    ✅ Created {output_file}")
            return True
        else:
            print(f"    ❌ Curator didn't create media_plan.json")
            return False

    except subprocess.TimeoutExpired:
        print(f"    ❌ Curator timed out for {format_type}")
        return False
    except Exception as e:
        print(f"    ❌ Error building {format_type} plan: {e}")
        return False


def main():
    """Build format-specific media plans based on segments.json."""
    print("🎨 Building format-specific media plans...")

    # Load segments to get durations
    segments_path = get_output_path("segments.json")
    if not segments_path.exists():
        print(f"❌ Error: {segments_path} not found")
        print("Segment analysis must run before media planning")
        sys.exit(1)

    with open(segments_path) as f:
        segments = json.load(f)

    # Build media plan for each format
    formats: list[FormatType] = ["full", "hook", "educational"]
    success_count = 0

    for format_type in formats:
        config = get_format_config(format_type, segments)
        success = build_media_plan(
            format_type,
            config["duration"],
            config["output_file"]
        )
        if success:
            success_count += 1

    # Summary
    print(f"\n✅ Built {success_count}/{len(formats)} format-specific media plans")

    if success_count < len(formats):
        print("⚠️  Some media plans failed - videos may have incorrect durations")
        sys.exit(1)


if __name__ == "__main__":
    main()
```

**Step 2: Make script executable**

Run: `chmod +x agents/build_format_media_plan.py`
Expected: Script is now executable

**Step 3: Test the script with existing run**

Run: `OUTPUT_DIR=outputs/runs/20251123_104729 ./agents/build_format_media_plan.py`
Expected: Should create three media plan files or fail gracefully with descriptive error

**Step 4: Commit**

```bash
git add agents/build_format_media_plan.py
git commit -m "feat: add format-specific media plan builder

- Creates separate media plans for full, hook, and educational formats
- Reads target durations from segments.json
- Calls curator three times with appropriate durations
- Generates media_plan_full.json, media_plan_hook.json, media_plan_educational.json"
```

---

## Task 4: Update build_multiformat_videos.py to Use Format-Specific Plans

**Files:**
- Modify: `agents/build_multiformat_videos.py`

**Step 1: Add function to build videos with format-specific media plans**

Add after imports (around line 20):

```python
def build_video_with_format_plan(
    format_type: str,
    resolution: str,
    output_name: str,
    media_plan_file: str
) -> bool:
    """
    Build a video using a format-specific media plan.

    Args:
        format_type: "full", "hook", or "educational"
        resolution: Video resolution (e.g., "1920x1080")
        output_name: Output filename (e.g., "full.mp4")
        media_plan_file: Media plan JSON file (e.g., "media_plan_full.json")

    Returns:
        True if successful, False otherwise
    """
    print(f"🎬 Building {format_type} video from {media_plan_file}...")

    output_dir = Path(os.getenv("OUTPUT_DIR", "outputs"))
    media_plan_path = output_dir / media_plan_file

    if not media_plan_path.exists():
        print(f"  ❌ Media plan not found: {media_plan_path}")
        return False

    # Temporarily swap approved_media.json with format-specific plan
    approved_media_path = output_dir / "approved_media.json"
    backup_path = output_dir / "approved_media.json.backup"

    # Backup original approved_media.json
    if approved_media_path.exists():
        approved_media_path.rename(backup_path)

    try:
        # Copy format-specific plan to approved_media.json
        import shutil
        shutil.copy(media_plan_path, approved_media_path)

        # Call video assembly with appropriate resolution
        result = subprocess.run(
            ['./venv/bin/python3', 'agents/5_assemble_video.py', '--resolution', resolution],
            capture_output=True,
            text=True,
            timeout=600
        )

        if result.returncode != 0:
            print(f"  ❌ Video assembly failed")
            print(f"  Error: {result.stderr[-500:]}")  # Last 500 chars
            return False

        # Rename final_video.mp4 to format-specific name
        final_video = output_dir / "final_video.mp4"
        if final_video.exists():
            final_video.rename(output_dir / output_name)
            print(f"  ✅ Created {output_name}")
            return True
        else:
            print(f"  ❌ Video assembly didn't create final_video.mp4")
            return False

    finally:
        # Restore original approved_media.json
        if backup_path.exists():
            if approved_media_path.exists():
                approved_media_path.unlink()
            backup_path.rename(approved_media_path)

    return False
```

**Step 2: Replace build_full_video() function**

Replace the existing `build_full_video()` function (around line 90) with:

```python
def build_full_video() -> Path:
    """Build full horizontal video using format-specific media plan."""
    print("🎬 Building full video (16:9) with 180s media plan...")

    success = build_video_with_format_plan(
        format_type="full",
        resolution="1920x1080",
        output_name="full.mp4",
        media_plan_file="media_plan_full.json"
    )

    if not success:
        print("❌ Failed to build full video")
        sys.exit(1)

    output_dir = Path(os.getenv("OUTPUT_DIR", "outputs"))
    return output_dir / "full.mp4"
```

**Step 3: Replace short building with direct format-specific builds**

Replace both `build_hook_short()` and `build_educational_short()` functions with:

```python
def build_hook_short() -> Path:
    """Build hook short using format-specific media plan."""
    print("🎬 Building hook short (9:16) with 30s media plan...")

    success = build_video_with_format_plan(
        format_type="hook",
        resolution="1080x1920",
        output_name="short_hook.mp4",
        media_plan_file="media_plan_hook.json"
    )

    if not success:
        print("❌ Failed to build hook short")
        sys.exit(1)

    output_dir = Path(os.getenv("OUTPUT_DIR", "outputs"))
    return output_dir / "short_hook.mp4"


def build_educational_short() -> Path:
    """Build educational short using format-specific media plan."""
    print("🎬 Building educational short (9:16) with 30s media plan...")

    success = build_video_with_format_plan(
        format_type="educational",
        resolution="1080x1920",
        output_name="short_educational.mp4",
        media_plan_file="media_plan_educational.json"
    )

    if not success:
        print("❌ Failed to build educational short")
        sys.exit(1)

    output_dir = Path(os.getenv("OUTPUT_DIR", "outputs"))
    return output_dir / "short_educational.mp4"
```

**Step 4: Remove extract_short_from_full() function**

Delete the entire `extract_short_from_full()` function (around line 120) since we no longer extract shorts from the full video.

**Step 5: Update main() to call format plan builder first**

In `main()` function, add after loading segments (around line 180):

```python
    # Build format-specific media plans based on segments
    print("\n📋 Creating format-specific media plans...")
    result = subprocess.run(
        ['./venv/bin/python3', 'agents/build_format_media_plan.py'],
        env=os.environ.copy()
    )

    if result.returncode != 0:
        print("❌ Failed to create format-specific media plans")
        sys.exit(1)
```

**Step 6: Test the updated script**

Run: `OUTPUT_DIR=outputs/test_multiformat ./agents/build_multiformat_videos.py`
Expected: Should fail gracefully if segments.json missing, or attempt to build three videos

**Step 7: Commit**

```bash
git add agents/build_multiformat_videos.py
git commit -m "feat: use format-specific media plans for each video

- Add build_video_with_format_plan() to build from specific media plan
- Replace extraction approach with direct format-specific builds
- Remove extract_short_from_full() - no longer needed
- Each format gets optimal media selection for its duration
- Fixes issue where shorts were extracted from truncated full video"
```

---

## Task 5: Update Pipeline to Call Format Plan Builder

**Files:**
- Modify: `pipeline.sh` (Stage 6/8 multi-format video building)

**Step 1: Find the multi-format video building section**

Run: `grep -n "build_multiformat_videos" pipeline.sh`
Expected: Shows line number where multiformat script is called

**Step 2: Verify segments.json exists before calling multiformat builder**

The build_multiformat_videos.py script now expects segments.json, and it will call build_format_media_plan.py internally. No changes needed to pipeline.sh since build_multiformat_videos.py handles everything.

Just verify the flow is correct:

Run: `grep -B5 -A5 "build_multiformat_videos" pipeline.sh`
Expected: Should show segment analysis happens before multiformat building

**Step 3: Test pipeline.sh with --express mode**

This will be tested in the integration test task.

**Step 4: Commit (documentation only)**

```bash
git add pipeline.sh
git commit -m "docs: document format-aware media plan flow

No code changes needed - build_multiformat_videos.py now handles
format-specific media plan creation internally"
```

---

## Task 6: Update FIXES_APPLIED.md Documentation

**Files:**
- Modify: `automation/FIXES_APPLIED.md`

**Step 1: Add new section documenting this fix**

Add to the end of `automation/FIXES_APPLIED.md`:

```markdown
---

## ✅ FIXED: Video duration issues with multi-format generation (2025-11-23)

### Issue: Incorrect video durations across all formats

**Symptoms:**
- Full video only 36 seconds instead of 180 seconds
- Educational short 26 seconds instead of 30 seconds
- Hook short 6 seconds instead of 30 seconds

**Root Causes:**

1. **Primary**: Curator hardcoded to 60 seconds
   - `agents/prompts/curator_prompt.md:13` had hardcoded `**Video Duration**: 60 seconds`
   - Multi-format system expected 180s for full video per segments.json
   - Architectural mismatch between single-format (60s) and multi-format (180s) design

2. **Secondary**: Media download failures
   - 5 out of 12 media downloads failed (all from Giphy)
   - Video assembly skipped failed downloads, reducing duration from 60s to 36s

3. **Tertiary**: Fixed timestamp extraction
   - build_multiformat_videos.py extracted shorts using fixed timestamps (10-40s, 30-60s)
   - Extracted from truncated 36s video instead of proper length videos
   - Educational: tried 10-40s, got 10-36s = 26s
   - Hook: tried 30-60s, got 30-36s = 6s

**Fix:**

Made curator format-aware to generate appropriate media plans for each video format:

1. **Modified `agents/4_curate_media.sh`:**
   - Added `--duration` parameter and `DURATION` environment variable
   - Passes duration to curator prompt template
   - Defaults to 60s for backward compatibility

2. **Modified `agents/prompts/curator_prompt.md`:**
   - Replaced hardcoded `60 seconds` with `{{VIDEO_DURATION}}` template variable
   - Added dynamic shot count guidelines based on duration
   - Now adapts media selection to target duration

3. **Created `agents/build_format_media_plan.py`:**
   - Reads segments.json to get target durations for each format
   - Calls curator three times with appropriate durations:
     - Full video: 180s
     - Hook short: 30s
     - Educational short: 30s
   - Generates format-specific media plans:
     - `media_plan_full.json`
     - `media_plan_hook.json`
     - `media_plan_educational.json`

4. **Modified `agents/build_multiformat_videos.py`:**
   - Added `build_video_with_format_plan()` to build from specific media plan
   - Replaced extraction approach with direct format-specific builds
   - Removed `extract_short_from_full()` - no longer needed
   - Each format now gets optimal media selection for its duration

**Result:**
- Full video: Uses 180s media plan with ~36-45 shots → proper 180s video
- Educational short: Uses 30s media plan with ~6-8 shots → proper 30s video
- Hook short: Uses 30s media plan with ~6-8 shots → proper 30s video
- Each format optimized independently instead of extracting from truncated source

**Files affected:**
- `agents/4_curate_media.sh`
- `agents/prompts/curator_prompt.md`
- `agents/build_format_media_plan.py` (new)
- `agents/build_multiformat_videos.py`

**Commit:** [To be filled in after implementation]

---
```

**Step 2: Commit documentation**

```bash
git add automation/FIXES_APPLIED.md
git commit -m "docs: document format-aware curator fix for video durations

Add comprehensive documentation of root cause analysis and fix
implementation for multi-format video duration issues"
```

---

## Task 7: Integration Test with Real Pipeline

**Files:**
- Test: Full pipeline execution

**Step 1: Clean test run directory**

Run: `rm -rf outputs/test_integration_*`
Expected: Removes any previous integration test outputs

**Step 2: Run full pipeline with --express mode**

Run: `OUTPUT_DIR=outputs/test_integration_$(date +%Y%m%d_%H%M%S) ./pipeline.sh --express 2>&1 | tee /tmp/integration_test.log`
Expected: Pipeline runs through all stages, creates three videos

**Step 3: Verify format-specific media plans were created**

Run: `ls -lh outputs/test_integration_*/media_plan_*.json`
Expected: Three files exist:
- media_plan_full.json
- media_plan_hook.json
- media_plan_educational.json

**Step 4: Check media plan durations**

Run:
```bash
for f in outputs/test_integration_*/media_plan_*.json; do
    echo "=== $f ==="
    python3 -c "import json; d=json.load(open('$f')); print(f'Duration: {d[\"total_duration\"]}s, Shots: {d[\"total_shots\"]}')"
done
```

Expected output similar to:
```
=== media_plan_full.json ===
Duration: 180s, Shots: 38
=== media_plan_hook.json ===
Duration: 30s, Shots: 7
=== media_plan_educational.json ===
Duration: 30s, Shots: 7
```

**Step 5: Verify video durations are correct**

Run:
```bash
for f in outputs/test_integration_*/{full,short_hook,short_educational}.mp4; do
    echo "=== $f ==="
    ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "$f"
done
```

Expected output close to:
```
=== full.mp4 ===
180.xx
=== short_hook.mp4 ===
30.xx
=== short_educational.mp4 ===
30.xx
```

**Step 6: If test fails, debug**

If durations are still wrong:
1. Check logs: `grep -E "media_plan|Building.*video|Duration" /tmp/integration_test.log`
2. Check media plans: `cat outputs/test_integration_*/media_plan_full.json | jq '.total_duration,.total_shots'`
3. Check approved_media.json wasn't used: `diff outputs/test_integration_*/approved_media.json outputs/test_integration_*/media_plan_full.json`

**Step 7: Document test results**

Create test summary:
```bash
cat > /tmp/integration_test_summary.txt <<EOF
Integration Test Results - $(date)

Full video duration: $(ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 outputs/test_integration_*/full.mp4)s
Hook short duration: $(ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 outputs/test_integration_*/short_hook.mp4)s
Educational short duration: $(ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 outputs/test_integration_*/short_educational.mp4)s

Expected: Full=180s, Hook=30s, Educational=30s
Status: $([ "$(ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 outputs/test_integration_*/full.mp4 | cut -d. -f1)" -gt 170 ] && echo "PASS" || echo "FAIL")
EOF

cat /tmp/integration_test_summary.txt
```

**Step 8: Commit test results if passing**

```bash
git add automation/FIXES_APPLIED.md  # Update with commit hash
git commit -m "test: verify format-aware curator produces correct durations

Integration test confirms:
- Full video: 180s (was 36s)
- Hook short: 30s (was 6s)
- Educational short: 30s (was 26s)

All formats now have correct durations using format-specific media plans"
```

---

## Verification Checklist

After completing all tasks, verify:

- [ ] Curator accepts `--duration` parameter
- [ ] Curator prompt uses `{{VIDEO_DURATION}}` template variable
- [ ] `build_format_media_plan.py` creates three media plan files
- [ ] Each media plan has appropriate duration (180s, 30s, 30s)
- [ ] `build_multiformat_videos.py` uses format-specific media plans
- [ ] Full video is ~180 seconds (±10s for shot boundaries)
- [ ] Hook short is ~30 seconds (±2s for shot boundaries)
- [ ] Educational short is ~30 seconds (±2s for shot boundaries)
- [ ] No extraction logic remains in build_multiformat_videos.py
- [ ] Integration test passes with real pipeline
- [ ] Documentation updated in FIXES_APPLIED.md

---

## Rollback Plan

If issues arise after implementation:

**Quick rollback:**
```bash
git revert HEAD~7..HEAD  # Revert last 7 commits
```

**Selective rollback:**
1. Keep format plan builder: `git revert <commit-hash-of-task-4>`
2. Keep updated build script: `git revert <commit-hash-of-task-3>`
3. Restore old curator: `git revert <commit-hash-of-task-1> <commit-hash-of-task-2>`

**Test after rollback:**
```bash
OUTPUT_DIR=outputs/rollback_test ./pipeline.sh --express
```

---

## Future Enhancements

After this fix is stable, consider:

1. **Segment-aware media selection**: Pass segment boundaries to curator so it can select media that aligns with lyric timestamps
2. **Fallback media**: If downloads fail, have curator suggest backup media sources
3. **Format-specific media criteria**: Different selection criteria for vertical vs horizontal
4. **Duration tolerance**: Allow ±10% duration flexibility for better media selection
5. **Media reuse optimization**: Reuse high-quality media across formats where appropriate
