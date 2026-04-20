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
import re
import sys
from difflib import SequenceMatcher
from pathlib import Path
from typing import Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).parent))
from output_helper import get_output_path


def _normalize_line(line: str) -> str:
    """Normalize a lyrics line for comparison (lowercase, strip tags, punctuation)."""
    line = line.strip()
    line = re.sub(r'\[.*?\]', '', line).strip()
    line = re.sub(r'[^\w\s]', '', line.lower()).strip()
    return line


def _extract_lyrics_lines(lyrics_text: str) -> List[str]:
    """Extract non-empty content lines from lyrics text."""
    lines = []
    for line in lyrics_text.split('\n'):
        stripped = line.strip()
        if stripped:
            lines.append(stripped)
    return lines


def _extract_aligned_lines(aligned_words: List[Dict]) -> List[Dict]:
    """Group aligned words into lines based on newlines in word text."""
    lines = []
    current_words = []

    for w in aligned_words:
        word_text = w.get("word", "")
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
    threshold: float = 0.6,
) -> List[Tuple[int, Optional[int]]]:
    """Match lyrics lines to aligned lines using fuzzy string matching."""
    matches = []
    used_aligned = set()

    for lyr_idx, lyr_line in enumerate(lyrics_lines):
        lyr_norm = _normalize_line(lyr_line)
        if not lyr_norm:
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

        # Enforce sequential order: only search aligned lines at or after
        # the last matched index to prevent out-of-order matching
        min_ali_idx = max(used_aligned) + 1 if used_aligned else 0

        for ali_idx, ali_line in enumerate(aligned_lines):
            if ali_idx in used_aligned or ali_idx < min_ali_idx:
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
    """Build repaired aligned lines with interpolated timestamps for dropped lines."""
    repaired = []

    for i, (lyr_idx, ali_idx) in enumerate(matches):
        lyr_text = lyrics_lines[lyr_idx]

        if ali_idx is not None:
            repaired.append({
                "text": lyr_text,
                "start_s": aligned_lines[ali_idx]["start_s"],
                "end_s": aligned_lines[ali_idx]["end_s"],
                "words": aligned_lines[ali_idx]["words"],
                "source": "suno",
            })
        else:
            prev_end = 0.0
            next_start = None

            for j in range(i - 1, -1, -1):
                if matches[j][1] is not None:
                    prev_end = aligned_lines[matches[j][1]]["end_s"]
                    break

            for j in range(i + 1, len(matches)):
                if matches[j][1] is not None:
                    next_start = aligned_lines[matches[j][1]]["start_s"]
                    break

            if next_start is None:
                next_start = prev_end + 3.0

            gap_start = i
            gap_end = i
            while gap_end < len(matches) - 1 and matches[gap_end + 1][1] is None:
                gap_end += 1
            gap_count = gap_end - gap_start + 1
            gap_duration = next_start - prev_end
            per_line_duration = gap_duration / max(gap_count, 1)
            line_offset = i - gap_start

            est_start = prev_end + line_offset * per_line_duration
            est_end = est_start + per_line_duration

            words_in_line = lyr_text.split()
            synthetic_words = []
            if words_in_line:
                word_duration = (est_end - est_start) / len(words_in_line)
                for wi, word in enumerate(words_in_line):
                    w_start = est_start + wi * word_duration
                    w_end = w_start + word_duration
                    suffix = " " if wi < len(words_in_line) - 1 else "\n"
                    synthetic_words.append({
                        "word": word + suffix,
                        "startS": round(w_start, 3),
                        "endS": round(w_end, 3),
                    })

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
    """Compare lyrics to aligned words and repair if mismatched."""
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
    """Repair suno_output.json alignment if needed."""
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
        backup_path = run_dir / "suno_output_original.json"
        if not backup_path.exists():
            with open(backup_path, "w") as f:
                json.dump(suno_data, f, indent=2)

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
