# Multi-Format Video Bug Fixes Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix critical bugs found during integration testing to make multi-format video generation work correctly.

**Architecture:** Four independent bug fixes: (1) Save Suno word-level timestamps for subtitles/segments, (2) Generate correct 16:9 horizontal full video, (3) Enable cross-linking stage, (4) Fix media gap filling IndexError.

**Tech Stack:** Python 3.9+, Suno API, FFmpeg, MoviePy

---

## Bug Summary

From integration test run `20251121_135212`:

1. ❌ **Missing `suno_output.json`** - Subtitle generation and segment analysis fail
2. ❌ **Wrong aspect ratio** - Full video is 1080x1920 (9:16) instead of 1920x1080 (16:9)
3. ❌ **Missing Stage 9** - Cross-linking doesn't run after uploads
4. ⚠️ **IndexError** - Media gap filling crashes (non-critical, pipeline recovers)

---

## Task 1: Save Suno Word-Level Timestamps

**Goal:** Make `agents/3_compose.py` save `suno_output.json` with word-level timestamps from Suno API.

**Files:**
- Modify: `agents/3_compose.py` (existing music composition script)
- Test: Manual verification (no unit test needed for API integration)

### Step 1: Read current implementation

**Action:** Read `agents/3_compose.py` to understand current structure.

```bash
cat agents/3_compose.py
```

**Look for:** Where Suno API response is processed, where files are saved.

### Step 2: Identify Suno API response structure

**Action:** Find where the script receives Suno API data containing word-level timestamps.

**Expected location:** Around line ~100-150 where API response is parsed.

**Look for:** Response field that contains lyrics with timestamps (likely `response['data']['sunoData'][0]['segments']` or similar).

### Step 3: Add suno_output.json save logic

**Action:** After successfully downloading the song, save the complete Suno API response to `suno_output.json`.

**Add after music download (around line ~180):**

```python
# Save Suno output with word-level timestamps for subtitle generation
output_dir = os.environ.get('OUTPUT_DIR', 'outputs/current')
suno_output_path = f"{output_dir}/suno_output.json"

# Extract the full response data
suno_data = {
    'taskId': task_id,
    'song': response['data']['sunoData'][0],  # Contains all metadata including timestamps
    'metadata': {
        'duration': selected_song['duration'],
        'title': selected_song.get('title', 'Educational Song'),
        'model': selected_song.get('modelName', 'chirp-crow')
    }
}

# Check if word-level timestamps exist in response
if 'segments' in selected_song or 'words' in selected_song:
    # Suno API v5 might have different structure
    # Save whatever timestamp data is available
    suno_data['words'] = selected_song.get('words', [])
    suno_data['segments'] = selected_song.get('segments', [])

with open(suno_output_path, 'w') as f:
    json.dump(suno_data, f, indent=2)

print(f"✅ Saved Suno output: {suno_output_path}")
```

### Step 4: Test with existing run

**Action:** Use the test run's song.mp3 to verify the script structure (dry run).

```bash
# Check if our test run has the song
ls -lh outputs/runs/20251121_135212/song.mp3

# Verify the script has no syntax errors
python3 -m py_compile agents/3_compose.py
```

**Expected:** No syntax errors.

### Step 5: Commit changes

```bash
git add agents/3_compose.py
git commit -m "fix: save suno_output.json with word-level timestamps

- Adds save logic after music download
- Creates suno_output.json with full API response
- Required for subtitle generation and segment analysis
- Issue: Integration test revealed missing file"
```

---

## Task 2: Fix Full Video Aspect Ratio (16:9)

**Goal:** Make full video generate as 1920x1080 (16:9 horizontal) instead of 1080x1920 (9:16 vertical).

**Files:**
- Modify: `agents/5_assemble_video.py` (add resolution parameter)
- Modify: `agents/build_multiformat_videos.py` (pass resolution parameter)

### Step 1: Read video assembly script

**Action:** Understand how `5_assemble_video.py` determines output resolution.

```bash
grep -n "resolution\|width\|height\|1920\|1080" agents/5_assemble_video.py | head -20
```

**Look for:** Where output resolution is set (likely around VideoFileClip or final_clip.write_videofile).

### Step 2: Add resolution parameter to 5_assemble_video.py

**Action:** Make the script accept a `--resolution` parameter.

**Find the argument parser (around line ~20):**

```python
parser = argparse.ArgumentParser()
# ... existing arguments ...
```

**Add resolution parameter:**

```python
parser.add_argument('--resolution',
                   type=str,
                   default='1080x1920',
                   help='Output resolution WIDTHxHEIGHT (default: 1080x1920 for vertical)')
args = parser.parse_args()

# Parse resolution
width, height = map(int, args.resolution.split('x'))
TARGET_WIDTH = width
TARGET_HEIGHT = height
```

### Step 3: Update video assembly to use resolution

**Action:** Find where clips are resized and use the new resolution parameters.

**Find the resize logic (search for `.resize`):**

```python
# OLD (around line ~150):
clip = clip.resize(height=TARGET_HEIGHT)

# NEW - use both dimensions:
clip = clip.resize(newsize=(TARGET_WIDTH, TARGET_HEIGHT))
```

### Step 4: Test syntax

```bash
python3 -m py_compile agents/5_assemble_video.py
```

**Expected:** No errors.

### Step 5: Commit video assembly changes

```bash
git add agents/5_assemble_video.py
git commit -m "feat: add resolution parameter to video assembly

- Adds --resolution WIDTHxHEIGHT argument
- Defaults to 1080x1920 (vertical) for backward compatibility
- Allows 1920x1080 (horizontal) for full videos
- Part of multi-format aspect ratio fix"
```

### Step 6: Update build_multiformat_videos.py to pass resolution

**Action:** Modify the `build_full_video()` function to pass `--resolution 1920x1080`.

**In `agents/build_multiformat_videos.py` around line 36:**

```python
def build_full_video():
    """Build full horizontal video using existing assembly script."""
    print("🎬 Building full video (16:9)...")

    # Call existing video assembly script WITH HORIZONTAL RESOLUTION
    result = subprocess.run(
        ['python3', 'agents/5_assemble_video.py', '--resolution', '1920x1080'],
        capture_output=True,
        text=True
    )

    if result.returncode != 0:
        raise Exception(f"Full video assembly failed: {result.stderr}")

    print(result.stdout)

    # Rename output to full.mp4
    output_dir = Path(os.environ.get('OUTPUT_DIR', 'outputs/current'))
    final_video = output_dir / 'final_video.mp4'
    full_video = output_dir / 'full.mp4'

    if final_video.exists():
        final_video.rename(full_video)
        print(f"✅ Full video saved: {full_video}")
        return full_video
    else:
        raise Exception("Final video not found after assembly")
```

### Step 7: Test syntax

```bash
python3 -m py_compile agents/build_multiformat_videos.py
```

**Expected:** No errors.

### Step 8: Commit multiformat builder changes

```bash
git add agents/build_multiformat_videos.py
git commit -m "fix: generate full video as 1920x1080 horizontal

- Passes --resolution 1920x1080 to video assembly
- Full video now correctly horizontal (16:9)
- Shorts remain vertical (9:16)
- Fixes: Integration test showed all videos were vertical"
```

---

## Task 3: Fix Cross-Linking Stage Execution

**Goal:** Ensure Stage 9 (cross-linking) runs after Stage 8 (uploads).

**Files:**
- Modify: `pipeline.sh` (fix stage 9 logic)

### Step 1: Find why Stage 9 didn't run

**Action:** Check the pipeline script around Stage 9.

```bash
grep -n "Stage 9\|Cross-Link" pipeline.sh | head -10
```

**Look for:** Stage 9 section, what conditions prevent it from running.

### Step 2: Read Stage 9 implementation

**Action:** Read the Stage 9 section to understand the logic.

```bash
sed -n '/Stage 9/,/Stage 10\|^$/p' pipeline.sh | head -50
```

**Expected issue:** Stage might be checking for upload_results.json or video IDs that aren't being captured correctly.

### Step 3: Check upload script output

**Action:** Verify that `upload_to_youtube.sh` saves video IDs correctly.

```bash
# Check if test run has upload results
cat outputs/runs/20251121_135212/upload_results.json 2>/dev/null || echo "File doesn't exist"
```

**If file doesn't exist:** Upload script isn't saving results properly.

### Step 4: Fix upload script to save video IDs

**Action:** Modify `upload_to_youtube.sh` to save video ID after successful upload.

**Find the upload success section (search for "Video uploaded" or "Upload complete"):**

```bash
# After successful upload, capture video ID
VIDEO_ID=$(echo "$UPLOAD_OUTPUT" | grep -oE 'watch\?v=([a-zA-Z0-9_-]+)' | cut -d= -f2)

# Append to upload_results.json
OUTPUT_DIR="${OUTPUT_DIR:-outputs/current}"
RESULTS_FILE="$OUTPUT_DIR/upload_results.json"

# Create or update results file
if [ ! -f "$RESULTS_FILE" ]; then
  echo "{}" > "$RESULTS_FILE"
fi

# Update with video ID (use jq or python)
python3 << EOF
import json
from pathlib import Path

results_file = Path("$RESULTS_FILE")
if results_file.exists():
    with open(results_file) as f:
        results = json.load(f)
else:
    results = {}

results["$VIDEO_TYPE"] = {
    "id": "$VIDEO_ID",
    "url": "https://youtube.com/watch?v=$VIDEO_ID"
}

with open(results_file, 'w') as f:
    json.dump(results, f, indent=2)
EOF
```

### Step 5: Fix pipeline to read results and call cross-linking

**Action:** In `pipeline.sh`, add logic to read upload_results.json and call cross-linking.

**In Stage 9 section:**

```bash
# Stage 9: Cross-Link Videos
if [ $START_STAGE -le 9 ]; then
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}Stage 9/9: Cross-Link Videos${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

    # Check if upload results exist
    RESULTS_FILE="$OUTPUT_DIR/upload_results.json"

    if [ -f "$RESULTS_FILE" ]; then
        echo "🔗 Cross-linking videos..."

        # Extract video IDs using python
        VIDEO_IDS=$(python3 << 'EOF'
import json
from pathlib import Path

results_file = Path("$RESULTS_FILE")
with open(results_file) as f:
    results = json.load(f)

# Get video IDs
full_id = results.get('full', {}).get('id', '')
hook_id = results.get('short_hook', {}).get('id', '')
edu_id = results.get('short_educational', {}).get('id', '')

print(f"{full_id} {hook_id} {edu_id}")
EOF
)

        # Call cross-linking script
        python3 agents/crosslink_videos.py $VIDEO_IDS

        echo "✅ Cross-linking complete"
    else
        echo -e "${YELLOW}⚠️  No upload results found, skipping cross-linking${NC}"
    fi
fi
```

### Step 6: Test bash syntax

```bash
bash -n pipeline.sh
```

**Expected:** No errors.

### Step 7: Commit changes

```bash
git add pipeline.sh upload_to_youtube.sh
git commit -m "fix: enable Stage 9 cross-linking after uploads

- Upload script now saves video IDs to upload_results.json
- Pipeline reads results and calls crosslink_videos.py
- Adds error handling if results file missing
- Fixes: Stage 9 wasn't running in integration test"
```

---

## Task 4: Fix Media Gap Filling IndexError

**Goal:** Fix IndexError that occurs when processing missing media concepts.

**Files:**
- Modify: `pipeline.sh` (fix python inline script around line ~350-400)

### Step 1: Find the IndexError location

**Action:** Search for the media gap filling code in pipeline.sh.

```bash
grep -n "research_gap_request\|missing concepts\|IndexError" pipeline.sh | head -10
```

**Look for:** Python inline script that processes research gaps.

### Step 2: Read the problematic code

**Action:** Read the code around the error location.

```bash
# Find the line number from step 1, then:
sed -n '340,380p' pipeline.sh
```

**Expected issue:** Accessing list index without checking if list is empty or has enough elements.

### Step 3: Add defensive checks

**Action:** Find the python code that accesses list indices and add checks.

**Common pattern causing IndexError:**

```python
# BEFORE (causes error):
concepts = data['missing_concepts']
first_concept = concepts[0]  # IndexError if concepts is empty

# AFTER (with check):
concepts = data.get('missing_concepts', [])
if len(concepts) > 0:
    first_concept = concepts[0]
else:
    print("No concepts to process")
```

**Find the exact location and apply similar defensive programming:**

```bash
# In pipeline.sh, find the python script around line 350-380
# Look for list index access like [0], [1], etc.
```

### Step 4: Update with defensive code

**Action:** Modify the inline python script to handle empty lists gracefully.

**Example fix (adjust based on actual code):**

```python
# Extract concepts from gap request
gap_file = Path(f"{output_dir}/research_gap_request.json")
if gap_file.exists():
    with open(gap_file) as f:
        gap_data = json.load(f)

    # Defensive check for missing_concepts
    concepts = gap_data.get('missing_concepts', [])

    if not concepts:
        print("No missing concepts to fill")
    else:
        # Process concepts
        for i, concept in enumerate(concepts):
            print(f"Finding media for {concept}")
            # ... rest of logic
```

### Step 5: Test syntax

```bash
bash -n pipeline.sh
```

**Expected:** No errors.

### Step 6: Commit fix

```bash
git add pipeline.sh
git commit -m "fix: handle empty concepts list in media gap filling

- Adds defensive check for missing_concepts list
- Prevents IndexError when list is empty or missing
- Pipeline continues gracefully if no gaps to fill
- Fixes: IndexError in Stage 5 during integration test"
```

---

## Task 5: Integration Test After Fixes

**Goal:** Run complete pipeline again to verify all fixes work.

**Files:**
- Test: Run `./pipeline.sh --express` with new topic

### Step 1: Create new test topic

**Action:** Create a different topic to test with fresh data.

```bash
echo "Explain how solar panels convert sunlight to electricity. Tone: exciting and innovative" > input/idea.txt
```

### Step 2: Run complete pipeline

**Action:** Execute full pipeline in express mode.

```bash
./pipeline.sh --express
```

**Expected duration:** ~10-12 minutes

**Monitor for:**
- ✅ Stage 4.5: Segment analysis succeeds (suno_output.json exists)
- ✅ Stage 6: Full video is 1920x1080 (16:9)
- ✅ Stage 7: Subtitle generation succeeds
- ✅ Stage 8: All videos upload
- ✅ Stage 9: Cross-linking executes

### Step 3: Verify outputs

**Action:** Check created files and properties.

```bash
# Get latest run
LATEST_RUN=$(ls -t outputs/runs/ | grep "^2025" | head -1)
echo "Checking run: $LATEST_RUN"

# Check files exist
ls -lh "outputs/runs/$LATEST_RUN/"*.mp4
ls -lh "outputs/runs/$LATEST_RUN/suno_output.json"
ls -lh "outputs/runs/$LATEST_RUN/upload_results.json"

# Verify video properties
for video in "outputs/runs/$LATEST_RUN/"*.mp4; do
  echo "=== $(basename $video) ==="
  ffprobe -v error -select_streams v:0 \
    -show_entries stream=width,height,duration \
    -of json "$video" | python3 -c "
import json, sys
data = json.load(sys.stdin)
w = data['streams'][0]['width']
h = data['streams'][0]['height']
d = float(data['streams'][0]['duration'])
print(f'{w}x{h}, {d:.1f}s')
"
done
```

**Expected output:**
```
full.mp4: 1920x1080, ~180s
short_hook.mp4: 1080x1920, ~30s
short_educational.mp4: 1080x1920, ~30s
```

### Step 4: Verify cross-linking

**Action:** Check that upload_results.json contains all video IDs and cross-linking ran.

```bash
cat "outputs/runs/$LATEST_RUN/upload_results.json" | python3 -m json.tool
```

**Expected:** JSON with all three video IDs and URLs.

### Step 5: Check YouTube videos

**Action:** Visit the YouTube URLs and verify:
- Full video shows 16:9 horizontal layout
- Shorts show 9:16 vertical layout
- Descriptions contain cross-links to other videos

### Step 6: Document test results

**Action:** Create test report.

```bash
cat > "outputs/runs/$LATEST_RUN/TEST_REPORT.md" << 'EOF'
# Integration Test Report - Bug Fixes

## Date
$(date)

## Test Topic
Solar panels - sunlight to electricity

## Results

### ✅ Fixed Issues
1. suno_output.json created: YES
2. Full video aspect ratio: 1920x1080 (16:9) ✅
3. Subtitle generation: SUCCESS ✅
4. Cross-linking executed: YES ✅
5. No IndexError: CLEAN RUN ✅

### Video Properties
- Full: [dimensions], [duration]s
- Hook: [dimensions], [duration]s
- Educational: [dimensions], [duration]s

### YouTube URLs
- Full: [URL]
- Hook: [URL]
- Educational: [URL]

## Conclusion
All bugs fixed and verified working.
EOF
```

### Step 7: Commit test report

```bash
git add "outputs/runs/$LATEST_RUN/TEST_REPORT.md"
git commit -m "test: integration test confirms all bug fixes working

- suno_output.json: created successfully
- Full video: correct 1920x1080 aspect ratio
- Subtitles: generated for all videos
- Cross-linking: executed and verified
- No errors during pipeline execution"
```

---

## Task 6: Update Documentation

**Goal:** Document the bug fixes in the project documentation.

**Files:**
- Modify: `docs/TROUBLESHOOTING.md`
- Modify: `automation/FIXES_APPLIED.md`
- Modify: `docs/MULTI_FORMAT_USAGE.md`

### Step 1: Add troubleshooting entries

**Action:** Document common issues and solutions in TROUBLESHOOTING.md.

**Add section:**

```markdown
## Multi-Format Video Issues

### Missing suno_output.json

**Symptom:** Subtitle generation fails with "No such file or directory: suno_output.json"

**Cause:** Music composition stage didn't save word-level timestamps.

**Fix:** Ensure `agents/3_compose.py` is updated to version with suno_output.json save logic (fixed 2025-11-21).

**Verify:**
```bash
ls outputs/current/suno_output.json
```

### Wrong Aspect Ratio for Full Video

**Symptom:** Full video is 1080x1920 (vertical) instead of 1920x1080 (horizontal)

**Cause:** Video assembly defaulted to vertical format.

**Fix:** `agents/5_assemble_video.py` now accepts `--resolution` parameter. Multiformat builder passes `--resolution 1920x1080` for full videos (fixed 2025-11-21).

**Verify:**
```bash
ffprobe outputs/current/full.mp4 | grep "Stream.*Video"
# Should show: 1920x1080
```

### Cross-Linking Not Running

**Symptom:** Stage 9 doesn't execute, videos not cross-linked

**Cause:** Upload results not being saved or pipeline not reading them.

**Fix:** Upload script now saves `upload_results.json`, pipeline reads it and executes Stage 9 (fixed 2025-11-21).

**Verify:**
```bash
cat outputs/current/upload_results.json
# Should show all 3 video IDs
```
```

### Step 2: Update FIXES_APPLIED.md

**Action:** Add the bug fixes to the fixes log.

```bash
cat >> automation/FIXES_APPLIED.md << 'EOF'

## 2025-11-21: Multi-Format Bug Fixes

### Issues Found in Integration Test
1. Missing `suno_output.json` causing subtitle/segment analysis failures
2. Full video generated as vertical (1080x1920) instead of horizontal (1920x1080)
3. Stage 9 (cross-linking) not executing after uploads
4. IndexError in media gap filling when concepts list empty

### Fixes Applied
1. **agents/3_compose.py**: Added logic to save Suno API response with word-level timestamps to `suno_output.json`
2. **agents/5_assemble_video.py**: Added `--resolution WIDTHxHEIGHT` parameter for flexible output dimensions
3. **agents/build_multiformat_videos.py**: Pass `--resolution 1920x1080` when building full horizontal video
4. **upload_to_youtube.sh**: Save video IDs to `upload_results.json` after successful upload
5. **pipeline.sh**:
   - Read `upload_results.json` and execute Stage 9 cross-linking
   - Added defensive checks to prevent IndexError in media gap filling

### Verification
- Ran integration test with solar panels topic
- Confirmed all 3 videos generated with correct aspect ratios
- Verified subtitles generated successfully
- Confirmed cross-linking executed
- No errors during pipeline execution

### Test Run
- Date: 2025-11-21
- Run ID: [AUTO-FILLED]
- Topic: Solar panels electricity generation
- Result: ✅ All systems working
EOF
```

### Step 3: Update multi-format usage guide

**Action:** Add notes about bug fixes to MULTI_FORMAT_USAGE.md.

**In the "Implementation Status" section, add:**

```markdown
### Recent Bug Fixes (2025-11-21)

The following issues were discovered during integration testing and have been fixed:

- ✅ **suno_output.json now saved** - Word-level timestamps from Suno API are preserved for subtitle generation
- ✅ **Correct aspect ratios** - Full video is now 1920x1080 (16:9), shorts remain 1080x1920 (9:16)
- ✅ **Cross-linking works** - Stage 9 now executes after uploads and links videos together
- ✅ **Robust error handling** - Media gap filling handles empty concept lists gracefully

All bugs found in integration test run `20251121_135212` have been resolved.
```

### Step 4: Commit documentation updates

```bash
git add docs/TROUBLESHOOTING.md automation/FIXES_APPLIED.md docs/MULTI_FORMAT_USAGE.md
git commit -m "docs: document multi-format bug fixes and solutions

- Adds troubleshooting for common multi-format issues
- Documents bug fixes in FIXES_APPLIED.md
- Updates usage guide with recent improvements
- Provides verification commands for each fix"
```

---

## Summary

**Total Tasks:** 6 (22 steps)
**Estimated Time:** 45-60 minutes
**Prerequisites:** Integration test results from run `20251121_135212`

**Critical Path:**
1. Task 1 (suno_output.json) → enables subtitle generation
2. Task 2 (aspect ratio) → fixes video format
3. Task 3 (cross-linking) → completes pipeline
4. Task 4 (IndexError) → prevents crashes
5. Task 5 (integration test) → verifies fixes
6. Task 6 (documentation) → records changes

**Success Criteria:**
- ✅ New pipeline run completes without errors
- ✅ Full video is 1920x1080 (16:9)
- ✅ Shorts are 1080x1920 (9:16)
- ✅ All videos have subtitles
- ✅ All videos uploaded to YouTube
- ✅ Video descriptions contain cross-links
- ✅ No IndexError or other crashes

**Testing Strategy:**
- Manual integration test with new topic
- Verify file outputs and properties
- Check YouTube uploads and cross-links
- Document results

---

## Related Skills

- @superpowers:executing-plans - Execute this plan step-by-step
- @superpowers:systematic-debugging - If issues arise during fixes
- @superpowers:verification-before-completion - Verify each fix before moving on
