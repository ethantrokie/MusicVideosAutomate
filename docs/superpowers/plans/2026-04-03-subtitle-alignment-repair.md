# Subtitle Alignment Repair Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix subtitle desync caused by Suno API's word alignment dropping or misaligning lyrics lines. When the aligned words don't match the actual lyrics, repair the alignment by detecting dropped lines and interpolating timestamps.

**Architecture:** A new repair step runs after Suno output is received (Stage 3.2). It compares the lyrics text (ground truth of what was sung) against the aligned words text (what Suno claims the timestamps map to). When lines are missing from the alignment, it inserts them with interpolated timestamps. When lines are shifted, it re-maps the timestamps to the correct lyrics lines.

**Tech Stack:** Python, difflib (sequence matching), no external dependencies

---

## The Problem

Suno's word alignment API sometimes returns aligned words that don't match the input lyrics:

| Run | Lines Mismatched | Example |
|-----|-----------------|---------|
| 20260403 | 39/40 | First line "You click a lighter" completely missing |
| 20260401 | 31/39 | 5 lines dropped, everything shifted |
| 20260324 | 23/40 | 2 lines dropped mid-song |

When lines are dropped, every subsequent subtitle appears at the wrong time because the timestamps are assigned to the wrong text.

## The Fix

### Detection

Compare lyrics.json text (what Suno was asked to sing) against the text reconstructed from alignedWords (what Suno claims to have aligned). Use `difflib.SequenceMatcher` to find:
- **Dropped lines**: lyrics lines with no corresponding aligned line
- **Shifted lines**: aligned lines that appear at the wrong position

### Repair Strategy

1. **Match aligned lines to lyrics lines** using fuzzy string matching (lines may have minor wording differences)
2. **For matched lines**: keep the Suno timestamps (they're accurate for the audio)
3. **For dropped lines**: interpolate timestamps from the surrounding matched lines
4. **Rebuild alignedWords**: reconstruct the word list with corrected timestamps

### Interpolation Logic

If lyrics lines A, B, C exist but aligned words only have A and C:
- A is at 2.0-5.0s, C is at 10.0-13.0s
- B should be between them: estimate B at 5.0-10.0s
- Split B's duration evenly across its words

---

## File Structure

### New files
```
agents/repair_suno_alignment.py        # Alignment repair logic
tests/test_repair_suno_alignment.py    # Tests
```

### Modified files
```
pipeline.sh                             # Add Stage 3.2 after Suno output
```

---

## Task 1: Alignment Repair Module

**Files:**
- Create: `agents/repair_suno_alignment.py`
- Create: `tests/test_repair_suno_alignment.py`

### repair_suno_alignment.py

```python
#!/usr/bin/env python3
"""
Repair Suno word alignment when it drops or misaligns lyrics lines.

Compares lyrics.json (ground truth) against suno_output.json alignedWords
and repairs the alignment by inserting missing lines with interpolated
timestamps.

Pipeline Stage: 3.2 (after Suno output, before phrase grouping)
"""

import json
import os
import sys
from difflib import SequenceMatcher
from pathlib import Path
from typing import Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).parent))
from output_helper import get_output_path


def _normalize_line(line: str) -> str:
    """Normalize a lyrics line for comparison (lowercase, strip tags, punctuation)."""
    import re
    line = line.strip()
    # Remove section tags like [Intro], [Verse 1], [Chorus]
    line = re.sub(r'\[.*?\]', '', line).strip()
    # Lowercase and remove punctuation for fuzzy matching
    line = re.sub(r'[^\w\s]', '', line.lower()).strip()
    return line


def _extract_lyrics_lines(lyrics_text: str) -> List[str]:
    """Extract non-empty content lines from lyrics text, preserving section tags."""
    lines = []
    for line in lyrics_text.split('\n'):
        stripped = line.strip()
        if stripped:
            lines.append(stripped)
    return lines


def _extract_aligned_lines(aligned_words: List[Dict]) -> List[Dict]:
    """
    Group aligned words into lines based on newlines in word text.
    Returns list of {text, start_s, end_s, words}.
    """
    lines = []
    current_words = []

    for w in aligned_words:
        word_text = w.get("word", "")
        # Check if this word contains a newline (end of line)
        has_newline = '\n' in word_text

        current_words.append(w)

        if has_newline and current_words:
            text = ' '.join(cw['word'].replace('\n', ' ').strip()
                          for cw in current_words).strip()
            if text:
                lines.append({
                    "text": text,
                    "start_s": current_words[0]["startS"],
                    "end_s": current_words[-1]["endS"],
                    "words": list(current_words),
                })
            current_words = []

    # Last line (no trailing newline)
    if current_words:
        text = ' '.join(cw['word'].replace('\n', ' ').strip()
                      for cw in current_words).strip()
        if text:
            lines.append({
                "text": text,
                "start_s": current_words[0]["startS"],
                "end_s": current_words[-1]["endS"],
                "words": list(current_words),
            })

    return lines


def _match_lines(
    lyrics_lines: List[str],
    aligned_lines: List[Dict],
    threshold: float = 0.5,
) -> List[Tuple[int, Optional[int]]]:
    """
    Match lyrics lines to aligned lines using fuzzy string matching.

    Returns list of (lyrics_idx, aligned_idx_or_None) pairs.
    None means the lyrics line has no matching aligned line (dropped).
    """
    matches = []
    used_aligned = set()

    for lyr_idx, lyr_line in enumerate(lyrics_lines):
        lyr_norm = _normalize_line(lyr_line)
        if not lyr_norm:
            # Section tags -- try exact match
            matches.append((lyr_idx, None))
            for ali_idx, ali_line in enumerate(aligned_lines):
                if ali_idx in used_aligned:
                    continue
                if lyr_line.strip().lower() in ali_line["text"].lower():
                    matches[-1] = (lyr_idx, ali_idx)
                    used_aligned.add(ali_idx)
                    break
            continue

        best_match = None
        best_score = 0.0

        for ali_idx, ali_line in enumerate(aligned_lines):
            if ali_idx in used_aligned:
                continue
            ali_norm = _normalize_line(ali_line["text"])
            score = SequenceMatcher(None, lyr_norm, ali_norm).ratio()
            if score > best_score:
                best_score = score
                best_match = ali_idx

        if best_match is not None and best_score >= threshold:
            matches.append((lyr_idx, best_match))
            used_aligned.add(best_match)
        else:
            matches.append((lyr_idx, None))

    return matches


def _interpolate_timestamps(
    lyrics_lines: List[str],
    aligned_lines: List[Dict],
    matches: List[Tuple[int, Optional[int]]],
) -> List[Dict]:
    """
    Build repaired aligned lines with interpolated timestamps for dropped lines.
    """
    repaired = []

    for i, (lyr_idx, ali_idx) in enumerate(matches):
        lyr_text = lyrics_lines[lyr_idx]

        if ali_idx is not None:
            # Matched -- use Suno's timestamps
            repaired.append({
                "text": lyr_text,
                "start_s": aligned_lines[ali_idx]["start_s"],
                "end_s": aligned_lines[ali_idx]["end_s"],
                "words": aligned_lines[ali_idx]["words"],
                "source": "suno",
            })
        else:
            # Dropped -- interpolate from neighbors
            prev_end = 0.0
            next_start = None

            # Find previous matched line's end time
            for j in range(i - 1, -1, -1):
                if matches[j][1] is not None:
                    prev_end = aligned_lines[matches[j][1]]["end_s"]
                    break

            # Find next matched line's start time
            for j in range(i + 1, len(matches)):
                if matches[j][1] is not None:
                    next_start = aligned_lines[matches[j][1]]["start_s"]
                    break

            if next_start is None:
                # No next match -- estimate duration from song duration
                next_start = prev_end + 3.0  # Default 3s per line

            # Count consecutive dropped lines to share the gap
            gap_start = i
            gap_end = i
            while gap_end < len(matches) - 1 and matches[gap_end + 1][1] is None:
                gap_end += 1
            gap_count = gap_end - gap_start + 1
            gap_duration = next_start - prev_end
            per_line_duration = gap_duration / gap_count
            line_offset = i - gap_start

            est_start = prev_end + line_offset * per_line_duration
            est_end = est_start + per_line_duration

            # Create synthetic words from the lyrics text
            words_in_line = lyr_text.split()
            if words_in_line:
                word_duration = (est_end - est_start) / len(words_in_line)
                synthetic_words = []
                for wi, word in enumerate(words_in_line):
                    w_start = est_start + wi * word_duration
                    w_end = w_start + word_duration
                    synthetic_words.append({
                        "word": word + (" " if wi < len(words_in_line) - 1 else "\n"),
                        "startS": round(w_start, 3),
                        "endS": round(w_end, 3),
                    })
            else:
                synthetic_words = []

            repaired.append({
                "text": lyr_text,
                "start_s": round(est_start, 3),
                "end_s": round(est_end, 3),
                "words": synthetic_words,
                "source": "interpolated",
            })

    return repaired


def _rebuild_aligned_words(repaired_lines: List[Dict]) -> List[Dict]:
    """Flatten repaired lines back into a single aligned words list."""
    all_words = []
    for line in repaired_lines:
        all_words.extend(line["words"])
    return all_words


def detect_and_repair(
    lyrics_text: str,
    aligned_words: List[Dict],
) -> Tuple[List[Dict], dict]:
    """
    Compare lyrics to aligned words and repair if mismatched.

    Returns:
        (repaired_aligned_words, stats_dict)
    """
    lyrics_lines = _extract_lyrics_lines(lyrics_text)
    aligned_lines = _extract_aligned_lines(aligned_words)

    matches = _match_lines(lyrics_lines, aligned_lines)

    matched_count = sum(1 for _, ali in matches if ali is not None)
    dropped_count = sum(1 for _, ali in matches if ali is None)
    total = len(lyrics_lines)

    stats = {
        "total_lyrics_lines": total,
        "matched": matched_count,
        "dropped": dropped_count,
        "match_rate": round(matched_count / total * 100, 1) if total else 0,
        "repair_needed": dropped_count > 0,
    }

    if dropped_count == 0:
        return aligned_words, stats

    repaired_lines = _interpolate_timestamps(lyrics_lines, aligned_lines, matches)
    repaired_words = _rebuild_aligned_words(repaired_lines)

    stats["repaired_lines"] = dropped_count
    stats["interpolated_words"] = sum(
        len(line["words"]) for line in repaired_lines if line["source"] == "interpolated"
    )

    return repaired_words, stats


def repair_suno_output(run_dir: Path) -> dict:
    """
    Repair suno_output.json alignment if needed.

    Reads lyrics.json and suno_output.json, compares them,
    and overwrites suno_output.json with repaired alignment if mismatched.
    """
    lyrics_path = run_dir / "lyrics.json"
    suno_path = run_dir / "suno_output.json"

    if not lyrics_path.exists() or not suno_path.exists():
        return {"repair_needed": False, "reason": "missing files"}

    with open(lyrics_path) as f:
        lyrics_data = json.load(f)
    with open(suno_path) as f:
        suno_data = json.load(f)

    lyrics_text = lyrics_data.get("lyrics", lyrics_data.get("text", ""))
    aligned_words = suno_data.get("alignedWords", [])

    if not lyrics_text or not aligned_words:
        return {"repair_needed": False, "reason": "no data"}

    repaired_words, stats = detect_and_repair(lyrics_text, aligned_words)

    if stats["repair_needed"]:
        # Backup original
        backup_path = run_dir / "suno_output_original.json"
        if not backup_path.exists():
            with open(backup_path, "w") as f:
                json.dump(suno_data, f, indent=2)

        # Overwrite with repaired alignment
        suno_data["alignedWords"] = repaired_words
        suno_data.setdefault("metadata", {})["alignment_repaired"] = True
        suno_data["metadata"]["repair_stats"] = stats

        with open(suno_path, "w") as f:
            json.dump(suno_data, f, indent=2)

        print(f"  Repaired alignment: {stats['dropped']} dropped lines interpolated")
    else:
        print(f"  Alignment OK: {stats['matched']}/{stats['total_lyrics_lines']} lines matched")

    return stats


def main():
    run_dir = Path(os.environ.get("OUTPUT_DIR", ""))
    if not run_dir.exists():
        print("ERROR: OUTPUT_DIR not set")
        sys.exit(1)

    print("Checking Suno word alignment...")
    stats = repair_suno_output(run_dir)
    print(f"  Stats: {json.dumps(stats)}")


if __name__ == "__main__":
    main()
```

### tests/test_repair_suno_alignment.py

```python
import json
import pytest
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "agents"))


def test_detect_no_repair_needed():
    """Perfect alignment needs no repair."""
    from repair_suno_alignment import detect_and_repair

    lyrics = "[Intro]\nLine one here\nLine two here\n"
    aligned = [
        {"word": "[Intro]\n", "startS": 0.0, "endS": 0.1},
        {"word": "Line ", "startS": 0.5, "endS": 0.7},
        {"word": "one ", "startS": 0.7, "endS": 0.9},
        {"word": "here\n", "startS": 0.9, "endS": 1.2},
        {"word": "Line ", "startS": 1.5, "endS": 1.7},
        {"word": "two ", "startS": 1.7, "endS": 1.9},
        {"word": "here\n", "startS": 1.9, "endS": 2.2},
    ]

    repaired, stats = detect_and_repair(lyrics, aligned)
    assert not stats["repair_needed"]


def test_detect_dropped_first_line():
    """First lyrics line missing from alignment is detected and repaired."""
    from repair_suno_alignment import detect_and_repair

    lyrics = "[Intro]\nYou click a lighter\nNo batteries no fuel\nBut hidden inside\n"
    # Alignment is missing "You click a lighter"
    aligned = [
        {"word": "[Intro]\nNo ", "startS": 0.08, "endS": 0.32},
        {"word": "batteries ", "startS": 0.32, "endS": 0.74},
        {"word": "no ", "startS": 0.85, "endS": 1.0},
        {"word": "fuel\n", "startS": 1.0, "endS": 1.5},
        {"word": "But ", "startS": 2.0, "endS": 2.2},
        {"word": "hidden ", "startS": 2.2, "endS": 2.5},
        {"word": "inside\n", "startS": 2.5, "endS": 3.0},
    ]

    repaired, stats = detect_and_repair(lyrics, aligned)
    assert stats["repair_needed"]
    assert stats["dropped"] >= 1

    # Repaired words should include "You click a lighter" with interpolated timestamps
    repaired_text = ' '.join(w['word'].strip() for w in repaired)
    assert "click" in repaired_text.lower() or "lighter" in repaired_text.lower()


def test_interpolated_timestamps_between_neighbors():
    """Dropped line gets timestamps between its matched neighbors."""
    from repair_suno_alignment import detect_and_repair

    lyrics = "Line A\nLine B dropped\nLine C\n"
    # Only A and C aligned, B is missing
    aligned = [
        {"word": "Line ", "startS": 1.0, "endS": 1.2},
        {"word": "A\n", "startS": 1.2, "endS": 2.0},
        {"word": "Line ", "startS": 5.0, "endS": 5.2},
        {"word": "C\n", "startS": 5.2, "endS": 6.0},
    ]

    repaired, stats = detect_and_repair(lyrics, aligned)
    assert stats["repair_needed"]

    # Find the interpolated "Line B dropped" words
    b_words = [w for w in repaired if "B" in w.get("word", "") or "dropped" in w.get("word", "")]
    assert len(b_words) > 0

    # Interpolated timestamps should be between A's end (2.0) and C's start (5.0)
    for w in b_words:
        assert 2.0 <= w["startS"] <= 5.0
        assert 2.0 <= w["endS"] <= 5.0


def test_normalize_line_strips_tags():
    from repair_suno_alignment import _normalize_line

    assert _normalize_line("[Intro]") == ""
    assert _normalize_line("[Verse 1]") == ""
    assert _normalize_line("Hello world!") == "hello world"
    assert _normalize_line("  No batteries, no fuel  ") == "no batteries no fuel"


def test_extract_aligned_lines():
    from repair_suno_alignment import _extract_aligned_lines

    aligned = [
        {"word": "Hello ", "startS": 0.0, "endS": 0.5},
        {"word": "world\n", "startS": 0.5, "endS": 1.0},
        {"word": "Next ", "startS": 1.5, "endS": 1.8},
        {"word": "line\n", "startS": 1.8, "endS": 2.2},
    ]

    lines = _extract_aligned_lines(aligned)
    assert len(lines) == 2
    assert lines[0]["text"] == "Hello world"
    assert lines[0]["start_s"] == 0.0
    assert lines[1]["text"] == "Next line"
```

---

## Task 2: Pipeline Integration

**Files:**
- Modify: `pipeline.sh`

Add Stage 3.2 after Suno output (Stage 3) and audio trimming (Stage 3.1), before phrase grouping (Stage 3.5).

```bash
# Stage 3.2: Suno Alignment Repair
if [ $START_STAGE -le 3 ]; then
    echo -e "${BLUE}Stage 3.2: Suno Alignment Repair${NC}"
    if ./venv/bin/python3 agents/repair_suno_alignment.py; then
        echo "✅ Alignment check complete"
    else
        echo -e "${YELLOW}⚠️  Alignment repair failed, using raw Suno alignment${NC}"
    fi
    echo ""
fi
```

---

## Task 3: E2E Test

Re-run repair on today's run (20260403), then rebuild video and verify subtitles match audio.
