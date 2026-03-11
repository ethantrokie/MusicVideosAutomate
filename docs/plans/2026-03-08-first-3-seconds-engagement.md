# First 3 Seconds Engagement Optimization

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Improve video opening sequences so topic-relevant visuals appear at frame 0, AI avatar moves to ~3-5s, and bold hook text appears immediately — targeting a jump from 1.47% to 3-4% engagement rate.

**Architecture:** Three changes work together: (1) `clip_placement.py` shifts the AI intro clip from 0s to 3s so stock footage leads, (2) `build_format_media_plan.py` selects the highest-scoring topic-relevant clip as shot 1 for all formats, (3) `video_overlays.py` adds a new hook text overlay at frame 0 (separate from the existing title) and removes the title's fade-in delay.

**Tech Stack:** Python 3, moviepy (TextClip, CompositeVideoClip), existing pipeline infrastructure

---

### Task 1: Shift AI Avatar Clip From 0s to 3s

**Files:**
- Modify: `agents/clip_placement.py:122-130`

**Context:** Currently, `determine_clip_placements()` hard-codes `intro_start = 0.0` with the comment "always starts at 0s so the AI artist is the first thing viewers see". Research shows leading with the topic subject (not an avatar) increases retention by 23%. The avatar should appear AFTER the first stock clip.

**Step 1: Change intro clip start time from 0.0 to 3.0**

In `agents/clip_placement.py`, replace lines 122-130:

```python
    # Clip 1: Intro - always starts at 0s so the AI artist is the first thing viewers see
    intro_start = 0.0
    clips.append({
        "id": 1,
        "start_time": intro_start,
        "end_time": round(intro_start + clip_duration, 3),
        "segment_type": "intro"
    })
    print(f"    Clip 1 (intro): starts at {intro_start:.2f}s (always first)")
```

With:

```python
    # Clip 1: Intro - starts at 3s so topic-relevant stock footage leads (improves first-3s retention)
    # Research: 23% higher retention when topic subject is visible in frame 0, not an avatar
    intro_start = 3.0
    clips.append({
        "id": 1,
        "start_time": intro_start,
        "end_time": round(intro_start + clip_duration, 3),
        "segment_type": "intro"
    })
    print(f"    Clip 1 (intro): starts at {intro_start:.2f}s (after topic-relevant opening)")
```

**Step 2: Adjust Clip 2 minimum gap**

Line 134 currently uses `clips[0]["end_time"] + 1` as min_verse. With the new intro at 3-8s, this means clip 2 can't start until 9s. That's fine — the current target is 15-20s. No change needed, but verify the math:
- Clip 1: 3.0-8.0s (intro avatar)
- Clip 2: 9.0+ target 15-20s (verse) — still works
- Clip 3: 16.0+ target 32-38s (chorus) — still works

**Step 3: Verify no other code depends on clip 1 starting at 0.0**

Check `agents/generate_ai_clips.py` and `agents/build_format_media_plan.py` — the `integrate_ai_clips()` function reads `clip["start_time"]` from the manifest. The manifest is written by `generate_ai_clips.py` which calls `determine_clip_placements()`. So the shift propagates automatically.

**Step 4: Commit**

```bash
git add agents/clip_placement.py
git commit -m "feat: shift AI avatar from 0s to 3s — topic-relevant visuals first"
```

---

### Task 2: Select Best Topic-Relevant Clip as Shot 1

**Files:**
- Modify: `agents/build_format_media_plan.py` (the main `build_media_plan_for_format()` function, after shot list is built)

**Context:** Currently, clips are ordered chronologically by their matched phrase time. The first stock clip may have a low match score or show irrelevant footage (e.g., military parade for a chocolate video). We need to ensure shot 1 is the most topic-relevant clip.

**Step 1: Add a `promote_best_opening_clip()` function**

Add this function before `integrate_ai_clips()` (around line 27):

```python
def promote_best_opening_clip(shots: List[Dict]) -> List[Dict]:
    """
    Move the highest-scoring topic-relevant video clip to position 1.
    This ensures the first thing viewers see is directly related to the topic.

    Only promotes clips that are actual video files (not images) and
    have a meaningful match score.
    """
    if len(shots) < 2:
        return shots

    # Find the best-scoring video clip (not image, not AI-generated)
    best_idx = -1
    best_score = -1.0

    for i, shot in enumerate(shots):
        is_video = shot.get("media_type", "").startswith("video")
        is_stock = shot.get("source", "") != "ai_generated"
        score = shot.get("match_score", 0.0)

        if is_video and is_stock and score > best_score:
            best_score = score
            best_idx = i

    if best_idx <= 0:
        # Already first, or no suitable clip found
        return shots

    # Swap: move best clip to position 0, shift others
    best_clip = shots[best_idx]
    new_shots = [best_clip] + [s for i, s in enumerate(shots) if i != best_idx]

    # Recalculate start_time/end_time based on new order
    current_time = 0.0
    for shot in new_shots:
        duration = shot.get("duration", shot.get("end_time", 3) - shot.get("start_time", 0))
        shot["start_time"] = current_time
        shot["end_time"] = current_time + duration
        current_time += duration

    # Renumber
    for i, shot in enumerate(new_shots, 1):
        shot["shot_number"] = i

    print(f"  🎯 Promoted shot '{best_clip.get('description', '?')[:60]}' to opening (score: {best_score:.2f})")

    return new_shots
```

**Step 2: Call `promote_best_opening_clip()` in the media plan builder**

Find the location in `build_format_media_plan.py` where shots are finalized (after `match_clips_to_phrase_groups()` is called, before `integrate_ai_clips()`). Insert the call:

```python
# Promote best topic-relevant clip to opening position
shots = promote_best_opening_clip(shots)
```

This must be called BEFORE `integrate_ai_clips()` so the AI clip carving logic works on the reordered shot list.

**Step 3: Commit**

```bash
git add agents/build_format_media_plan.py
git commit -m "feat: promote highest-scoring topic clip to opening position"
```

---

### Task 3: Add Hook Text Overlay

**Files:**
- Modify: `agents/video_overlays.py`

**Context:** Research shows text overlays at frame 0 increase watch time by up to 37%. 60%+ of viewers watch with sound off. Currently there's no hook text — just the title overlay that fades in over 0.3s. We need a bold, short hook question/claim that appears instantly.

**Step 1: Add hook text generation function**

Add after the `create_title_overlay()` function (after line 145):

```python
def generate_hook_text(title: str) -> str:
    """
    Transform a video title into a short 3-7 word hook.
    Prioritizes curiosity-gap questions and surprising claims.
    """
    # Remove common suffixes
    clean = title.replace(" Explained", "").replace(" (Music Video)", "").strip()

    # Common patterns for science topics
    if clean.lower().startswith("how "):
        # "How Chocolate Gets Its Snap" -> "Why Does Chocolate SNAP?"
        subject = clean[4:]  # Remove "How "
        return f"Why Does {subject}?"
    elif clean.lower().startswith("why "):
        return clean + "?"
    elif clean.lower().startswith("what "):
        return clean + "?"
    else:
        # Default: add "The Science of" prefix or question mark
        return f"The Science of {clean}"


def create_hook_overlay(
    hook_text: str,
    video_size: tuple,
    duration: float = 2.0,
    is_short: bool = False
) -> TextClip:
    """
    Create bold hook text overlay for frame 0.
    Larger and bolder than the title — designed to stop scrolling.

    Args:
        hook_text: Short 3-7 word hook
        video_size: (width, height) tuple
        duration: How long to show hook text
        is_short: Whether this is short-form video

    Returns:
        TextClip with hook text
    """
    width, height = video_size

    if is_short:
        base_size = 72  # Bigger than title (60)
        max_width = width - 60
        y_position = height * 0.12
    else:
        base_size = 80  # Bigger than title (70)
        max_width = width - 120
        y_position = height * 0.12

    # Reduce for long hooks
    if len(hook_text) > 35:
        base_size = int(base_size * 0.8)

    font = get_available_font(TITLE_FONTS)

    txt_clip = TextClip(
        hook_text,
        fontsize=base_size,
        font=font,
        color='yellow',
        stroke_color='black',
        stroke_width=4,
        method='caption',
        size=(max_width, None),
        align='center'
    )

    # Position at top — instant appearance, no fade-in
    txt_clip = txt_clip.set_position(('center', y_position))
    txt_clip = txt_clip.set_duration(duration)
    txt_clip = txt_clip.crossfadeout(0.3)  # Smooth exit only

    return txt_clip
```

**Step 2: Modify `add_overlays_to_video()` to include hook overlay**

Update the function signature at line 252 to accept `hook_text`:

```python
def add_overlays_to_video(
    video_path: Path,
    output_path: Path,
    title: str,
    is_short: bool = False,
    title_duration: float = 2.0,
    end_screen_duration: float = 3.0,
    channel_name: str = "@learningsciencemusic",
    hook_text: str = None
) -> Path:
```

Add hook overlay creation after the title overlay (after line 286):

```python
    # Create hook text overlay (appears at frame 0, bolder than title)
    overlays = [video, title_clip, end_screen]
    if hook_text:
        print(f"  Creating hook overlay: '{hook_text}'")
        hook_clip = create_hook_overlay(hook_text, video_size, min(title_duration, 2.0), is_short)
        hook_clip = hook_clip.set_start(0)
        overlays.insert(2, hook_clip)  # After video and title, before end screen

    # Composite all layers
    print("  Compositing overlays...")
    final = CompositeVideoClip(overlays)
```

Also remove the old compositing line (line 295):
```python
    # OLD: final = CompositeVideoClip([video, title_clip, end_screen])
```

**Step 3: Remove title fade-in delay**

In `create_title_overlay()` line 143, change:

```python
    txt_clip = txt_clip.crossfadein(0.3).crossfadeout(0.3)
```

To:

```python
    txt_clip = txt_clip.crossfadeout(0.3)  # Instant appearance, smooth exit
```

**Step 4: Update `main()` to support hook_text CLI arg**

Add after line 353 (in the argparse section):

```python
    parser.add_argument('--hook-text', type=str, help='Hook text overlay (default: auto-generated from title)')
```

And in the function call around line 379, add:

```python
    hook = args.hook_text or generate_hook_text(title)
```

Pass `hook_text=hook` to `add_overlays_to_video()`.

**Step 5: Commit**

```bash
git add agents/video_overlays.py
git commit -m "feat: add bold hook text overlay at frame 0 for engagement"
```

---

### Task 4: Wire Hook Text Into Pipeline

**Files:**
- Modify: `agents/5_assemble_video.py` (wherever `add_overlays_to_video` is called)

**Context:** The overlay function now accepts `hook_text` but the assembly pipeline needs to pass it. The hook text should be auto-generated from the title.

**Step 1: Find where overlays are applied in the assembly pipeline**

Search for `add_overlays_to_video` or `video_overlays` import in `agents/5_assemble_video.py`. If it's called there, add the `hook_text` parameter. If overlays are applied in a separate stage (e.g., pipeline.sh calls video_overlays.py directly), update that callsite instead.

**Step 2: Generate and pass hook_text**

```python
from video_overlays import generate_hook_text

hook_text = generate_hook_text(title)
add_overlays_to_video(..., hook_text=hook_text)
```

**Step 3: Commit**

```bash
git add agents/5_assemble_video.py
git commit -m "feat: wire hook text generation into video assembly pipeline"
```

---

### Task 5: Adjust Title Overlay Position When Hook Is Present

**Files:**
- Modify: `agents/video_overlays.py`

**Context:** With both hook text and title appearing at frame 0, they need different vertical positions to avoid overlap. Hook text at top (12%), title slightly below (25%).

**Step 1: Move title position down when hook is present**

In `add_overlays_to_video()`, after creating both overlays, adjust title position:

```python
    if hook_text:
        # Move title below the hook text
        title_clip = title_clip.set_position(('center', height * 0.25))
```

**Step 2: Commit**

```bash
git add agents/video_overlays.py
git commit -m "feat: adjust title position below hook text overlay"
```

---

### Task 6: Test With Today's Video Run

**Step 1: Run a test build of one format to verify visuals**

```bash
cd /Users/ethantrokie/SoftwareDevProjects/MusicVideosAutomate
export OUTPUT_DIR=outputs/runs/20260308_090033

# Rebuild just the intro short to test
python3 agents/build_format_media_plan.py
```

Verify in the output:
- "Promoted shot '...' to opening" message appears
- AI clip starts at 3.0s, not 0.0s

**Step 2: Extract and visually inspect frame 0 of rebuilt video**

```bash
ffmpeg -ss 0 -i outputs/runs/20260308_090033/short_intro.mp4 -frames:v 1 /tmp/test_frame0.jpg
```

Verify: Topic-relevant footage visible, hook text visible, no AI avatar.

**Step 3: Commit any adjustments**

```bash
git add -A
git commit -m "test: verify first-3-seconds engagement improvements"
```
