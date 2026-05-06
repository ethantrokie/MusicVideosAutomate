# Subtitle Timing Fix Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix two subtitle timing issues: (1) shorts get full-song timestamps instead of segment-relative timestamps, causing wrong lyrics to display, and (2) word-to-phrase matching has minor ~100-200ms drift at phrase boundaries.

**Architecture:** The props builder receives the segment start time and filters/shifts phrase timestamps to be segment-relative. The word enrichment function clamps word times to their parent phrase boundaries.

**Tech Stack:** Python (remotion_props_builder.py), Bash (pipeline.sh, render_remotion_overlays.py)

---

## Issue 1: Shorts Get Full-Song Timestamps

### Root Cause

`build_overlay_props()` passes ALL phrase groups with absolute song timestamps to every video format. For `short_hook` (audio starts at ~44s of the song), frame 0 in Remotion = 0ms, but the phrases say the hook lyrics start at 44270ms. The karaoke shows intro lyrics (at 638ms) instead of hook lyrics.

### Fix

Add a `segment_start_s` parameter to `build_overlay_props()`. When building phrases:
1. Filter to only phrases that overlap the segment time range
2. Subtract `segment_start_s` from all timestamps so they're segment-relative
3. Also shift edu image timestamps the same way

### Files
- Modify: `agents/remotion_props_builder.py`
- Modify: `agents/render_remotion_overlays.py` (pass segment_start_s from segments.json)
- Modify: `tests/test_remotion_props_builder.py` (add segment offset test)

### Changes to `remotion_props_builder.py`

**Update `build_overlay_props` signature:**

```python
def build_overlay_props(
    run_dir: Path,
    config: Dict,
    format_type: FormatType,
    duration_ms: int,
    segment_start_s: float = 0.0,  # NEW: segment start time in seconds
) -> Dict:
```

**Add filtering and shifting logic after building phrases:**

```python
    # Filter and shift phrases to segment-relative timestamps
    segment_start_ms = _seconds_to_ms(segment_start_s)
    segment_end_ms = segment_start_ms + duration_ms

    shifted_phrases = []
    for phrase in all_phrases:
        # Keep phrases that overlap the segment range
        if phrase["endMs"] <= segment_start_ms or phrase["startMs"] >= segment_end_ms:
            continue

        # Shift to segment-relative time
        shifted = {
            **phrase,
            "startMs": max(0, phrase["startMs"] - segment_start_ms),
            "endMs": min(duration_ms, phrase["endMs"] - segment_start_ms),
            "words": [
                {
                    **w,
                    "startMs": max(0, w["startMs"] - segment_start_ms),
                    "endMs": min(duration_ms, w["endMs"] - segment_start_ms),
                }
                for w in phrase.get("words", [])
                if w["endMs"] > segment_start_ms and w["startMs"] < segment_end_ms
            ],
        }
        shifted_phrases.append(shifted)
```

**Same for edu images:**

```python
    shifted_edu = []
    for img in edu_images:
        if img["endMs"] <= segment_start_ms or img["startMs"] >= segment_end_ms:
            continue
        shifted_edu.append({
            **img,
            "startMs": max(0, img["startMs"] - segment_start_ms),
            "endMs": min(duration_ms, img["endMs"] - segment_start_ms),
        })
```

**Same for shot boundaries:**

```python
    shifted_boundaries = []
    for b in boundaries:
        if segment_start_ms <= b["timeMs"] <= segment_end_ms:
            shifted_boundaries.append({
                **b,
                "timeMs": b["timeMs"] - segment_start_ms,
            })
```

### Changes to `render_remotion_overlays.py`

**Pass segment_start_s when calling `build_overlay_props`:**

Read `segments.json` to determine the segment start for each format type.

```python
def _get_segment_start(run_dir: Path, format_type: FormatType) -> float:
    """Get segment start time in seconds for a given format."""
    segments_path = run_dir / "segments.json"
    if not segments_path.exists():
        return 0.0

    with open(segments_path) as f:
        segments = json.load(f)

    segment_map = {
        "full": "full",
        "short_hook": "hook",
        "short_educational": "educational",
        "short_intro": "intro",
    }
    segment_key = segment_map.get(format_type, "full")
    return segments.get(segment_key, {}).get("start", 0.0)
```

Then in `render_overlay()`:

```python
    segment_start_s = _get_segment_start(run_dir, format_type)
    props = build_overlay_props(run_dir, config, format_type, duration_ms, segment_start_s)
```

### Test

```python
def test_segment_offset_shifts_timestamps(tmp_path: Path):
    """Phrases and edu images are shifted by segment start time."""
    # Create artifacts with absolute timestamps
    (tmp_path / "research.json").write_text(json.dumps({"video_title": "Test"}))
    (tmp_path / "approved_media.json").write_text(json.dumps({"shot_list": []}))

    # Phrases at absolute times: 5s, 15s, 45s, 50s
    groups = [
        {"text": "early phrase", "startS": 5.0, "endS": 10.0},
        {"text": "mid phrase", "startS": 15.0, "endS": 20.0},
        {"text": "hook phrase", "startS": 45.0, "endS": 48.0},
        {"text": "hook phrase 2", "startS": 50.0, "endS": 53.0},
    ]
    (tmp_path / "phrase_groups.json").write_text(json.dumps(groups))

    config = {
        "video_settings": {"resolution": [1080, 1920], "fps": 30},
        "remotion_overlay": {"enabled": True},
    }

    # Build props for hook short starting at 44s, 15s duration
    props = build_overlay_props(tmp_path, config, "short_hook", 15000, segment_start_s=44.0)

    # Should only have the two hook phrases, shifted to 0-relative
    assert len(props["phrases"]) == 2
    assert props["phrases"][0]["text"] == "hook phrase"
    assert props["phrases"][0]["startMs"] == 1000  # 45000 - 44000
    assert props["phrases"][0]["endMs"] == 4000    # 48000 - 44000
    assert props["phrases"][1]["startMs"] == 6000  # 50000 - 44000
```

---

## Issue 2: Word-to-Phrase Boundary Drift

### Root Cause

`_enrich_phrases_with_words` matches words to phrases using the word's midpoint time. A word that starts before the phrase boundary but whose midpoint is inside the phrase gets assigned to that phrase. During playback, the word highlights ~100-200ms before the phrase is "supposed" to begin.

### Fix

After enriching phrases with words, clamp each word's `startMs` and `endMs` to be within its parent phrase's time range.

### Files
- Modify: `agents/remotion_props_builder.py` (in `_build_phrases`)

### Change

At the end of `_build_phrases`, after building each phrase dict, clamp the word times:

```python
        # Clamp word times to parent phrase boundaries
        phrase_start = _seconds_to_ms(start_s)
        phrase_end = _seconds_to_ms(end_s)
        for w in words:
            w["startMs"] = max(w["startMs"], phrase_start)
            w["endMs"] = min(w["endMs"], phrase_end)
```

### Test

```python
def test_word_times_clamped_to_phrase_bounds(tmp_path: Path):
    """Words that extend outside their phrase are clamped."""
    (tmp_path / "research.json").write_text(json.dumps({"video_title": "Test"}))
    (tmp_path / "approved_media.json").write_text(json.dumps({"shot_list": []}))

    # Phrase from 5.0-8.0s, but word starts at 4.8s (before phrase)
    groups = [
        {"text": "test phrase", "startS": 5.0, "endS": 8.0, "words": [
            {"word": "test", "startS": 4.8, "endS": 5.5},
            {"word": "phrase", "startS": 5.5, "endS": 8.2},
        ]},
    ]
    (tmp_path / "phrase_groups.json").write_text(json.dumps(groups))

    config = {"video_settings": {"resolution": [1080, 1920], "fps": 30}, "remotion_overlay": {"enabled": True}}
    props = build_overlay_props(tmp_path, config, "full", 30000)

    words = props["phrases"][0]["words"]
    assert words[0]["startMs"] == 5000  # clamped from 4800 to 5000
    assert words[1]["endMs"] == 8000    # clamped from 8200 to 8000
```

---

## Execution Order

1. **Issue 2 (word clamping)** -- small change in props builder, add test
2. **Issue 1 (segment offset)** -- props builder + render orchestrator + test
3. **E2E verification** -- rebuild hook short, verify correct lyrics display
