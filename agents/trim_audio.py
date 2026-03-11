#!/usr/bin/env python3
"""
Trim audio intro so the song starts at most N seconds before the first lyric.

Stage 3.1 in the pipeline — runs after music composition (Stage 3)
and before phrase grouping (Stage 3.5).

Modifies suno_output.json and song.mp3 in-place so all downstream
stages automatically pick up the shifted timestamps.
"""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Dict, List

from agents.audio_utils import _find_binary


# ── Pure functions ────────────────────────────────────────────────────────────


def compute_crop_offset(
    aligned_words: List[Dict], max_intro_seconds: float = 2.0
) -> float:
    """Return how many seconds to trim from the start of the audio.

    Returns 0.0 if the intro is already short enough (first lyric
    starts within *max_intro_seconds*, or offset <= 0.1s tolerance).
    """
    if not aligned_words:
        return 0.0

    first_start = aligned_words[0]["startS"]
    raw_offset = first_start - max_intro_seconds

    if raw_offset <= 0.1:
        return 0.0

    return raw_offset


def shift_timestamps(
    aligned_words: List[Dict], crop_offset: float
) -> List[Dict]:
    """Return a *new* list with every startS/endS shifted by -crop_offset.

    Values are clamped to >= 0.
    """
    shifted = []
    for word in aligned_words:
        shifted.append(
            {
                **word,
                "startS": max(0.0, word["startS"] - crop_offset),
                "endS": max(0.0, word["endS"] - crop_offset),
            }
        )
    return shifted


def build_crop_metadata(
    crop_offset: float, original_first_lyric: float, new_first_lyric: float
) -> Dict:
    """Build the metadata dict written to audio_crop.json."""
    return {
        "crop_offset": crop_offset,
        "original_first_lyric": original_first_lyric,
        "new_first_lyric": new_first_lyric,
    }


# ── I/O helpers ───────────────────────────────────────────────────────────────


def load_config(project_root: Path) -> Dict:
    """Load audio_trim config from config/config.json. Returns defaults if missing."""
    defaults = {"enabled": True, "max_intro_seconds": 2.0}
    config_path = project_root / "config" / "config.json"
    if not config_path.exists():
        return defaults
    try:
        full_config = json.loads(config_path.read_text())
        return {**defaults, **full_config.get("audio_trim", {})}
    except (json.JSONDecodeError, KeyError):
        return defaults


def crop_audio_file(song_path: Path, crop_offset: float) -> bool:
    """Use ffmpeg to crop song.mp3 starting at crop_offset seconds.

    Writes to a temp file first, then replaces the original.
    Returns True on success.
    """
    ffmpeg = _find_binary("ffmpeg")
    tmp_fd, tmp_path = tempfile.mkstemp(suffix=".mp3")
    os.close(tmp_fd)

    try:
        result = subprocess.run(
            [
                ffmpeg, "-y",
                "-i", str(song_path),
                "-ss", str(crop_offset),
                "-acodec", "copy",
                tmp_path,
            ],
            capture_output=True,
            timeout=60,
        )

        if result.returncode != 0:
            print(f"  ⚠️ ffmpeg crop error: {result.stderr.decode()[:300]}")
            return False

        tmp = Path(tmp_path)
        if not tmp.exists() or tmp.stat().st_size == 0:
            return False

        # Replace original with cropped version
        tmp.replace(song_path)
        return True

    except subprocess.TimeoutExpired:
        print("  ⚠️ ffmpeg crop timed out")
        return False
    except Exception as e:
        print(f"  ⚠️ ffmpeg crop failed: {e}")
        return False
    finally:
        # Clean up temp file if it still exists
        tmp = Path(tmp_path)
        if tmp.exists():
            tmp.unlink()


# ── Main orchestrator ─────────────────────────────────────────────────────────


def run_trim(
    output_dir: Path,
    max_intro_seconds: float = 2.0,
    enabled: bool = True,
) -> Dict:
    """Trim the audio intro and shift timestamps.

    Returns a result dict with cropping details.
    """
    if not enabled:
        return {"cropped": False, "crop_offset": 0.0, "skipped_reason": "disabled"}

    suno_path = output_dir / "suno_output.json"
    song_path = output_dir / "song.mp3"

    suno_data = json.loads(suno_path.read_text())
    aligned_words = suno_data.get("alignedWords", [])

    crop_offset = compute_crop_offset(aligned_words, max_intro_seconds)

    if crop_offset == 0.0:
        print(f"  ℹ️  Intro already short enough, skipping trim")
        return {"cropped": False, "crop_offset": 0.0}

    original_first = aligned_words[0]["startS"]

    # Crop the audio file
    print(f"  ✂️  Cropping {crop_offset:.1f}s from start of song.mp3")
    if not crop_audio_file(song_path, crop_offset):
        raise RuntimeError(
            f"ffmpeg failed to crop song.mp3 at offset {crop_offset:.1f}s"
        )

    # Shift all timestamps
    shifted_words = shift_timestamps(aligned_words, crop_offset)
    new_first = shifted_words[0]["startS"]

    # Update suno_output.json (immutable update of the data structure)
    updated_data = {**suno_data, "alignedWords": shifted_words}

    # Update duration metadata if present
    if "song" in updated_data and "duration" in updated_data["song"]:
        updated_data = {
            **updated_data,
            "song": {
                **updated_data["song"],
                "duration": updated_data["song"]["duration"] - crop_offset,
            },
        }
    if "metadata" in updated_data and "duration" in updated_data["metadata"]:
        updated_data = {
            **updated_data,
            "metadata": {
                **updated_data["metadata"],
                "duration": updated_data["metadata"]["duration"] - crop_offset,
            },
        }

    # Write updated files
    suno_path.write_text(json.dumps(updated_data, indent=2))

    crop_meta = build_crop_metadata(crop_offset, original_first, new_first)
    (output_dir / "audio_crop.json").write_text(json.dumps(crop_meta, indent=2))

    print(f"  ✅ Trimmed {crop_offset:.1f}s — first lyric now at {new_first:.1f}s")

    return {"cropped": True, "crop_offset": crop_offset}


# ── CLI entry point ──────────────────────────────────────────────────────────


def main():
    output_dir = Path(os.environ.get("OUTPUT_DIR", "outputs/current"))
    project_root = Path(__file__).resolve().parent.parent

    config = load_config(project_root)

    if not config["enabled"]:
        print("  ℹ️  Audio trimming disabled in config")
        sys.exit(0)

    if not (output_dir / "suno_output.json").exists():
        print(f"  ⚠️ No suno_output.json in {output_dir}")
        sys.exit(1)

    if not (output_dir / "song.mp3").exists():
        print(f"  ⚠️ No song.mp3 in {output_dir}")
        sys.exit(1)

    result = run_trim(
        output_dir,
        max_intro_seconds=config["max_intro_seconds"],
        enabled=config["enabled"],
    )

    if result["cropped"]:
        print(f"  📊 Crop offset: {result['crop_offset']:.1f}s")


if __name__ == "__main__":
    main()
