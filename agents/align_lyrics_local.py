#!/usr/bin/env python3
"""
Local forced alignment of lyrics to audio.

Uses demucs for vocal isolation and ctc-forced-aligner for word-level
timestamp alignment. Replaces the flaky Suno API alignment endpoint.

Pipeline Stage: 3.2 (after music generation, before phrase grouping)

Dependencies: demucs, ctc-forced-aligner, onnxruntime, unidecode
"""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Dict, List, Tuple

sys.path.insert(0, str(Path(__file__).parent))
from output_helper import get_output_path


def isolate_vocals(audio_path: str, output_dir: str) -> str:
    """
    Isolate vocals from a song using demucs.

    Args:
        audio_path: Path to the input audio file (mp3/wav)
        output_dir: Directory to write the isolated vocals

    Returns:
        Path to the isolated vocals audio file
    """
    print("  Isolating vocals with demucs...")

    result = subprocess.run(
        [
            sys.executable, "-m", "demucs",
            "--two-stems", "vocals",
            "-o", output_dir,
            "--mp3",
            audio_path,
        ],
        capture_output=True,
        text=True,
        timeout=300,
    )

    if result.returncode != 0:
        raise RuntimeError(f"Demucs failed: {result.stderr[:500]}")

    # Find the vocals output
    stem = Path(audio_path).stem
    vocals_path = Path(output_dir) / "htdemucs" / stem / "vocals.mp3"
    if not vocals_path.exists():
        # Try wav extension
        vocals_path = Path(output_dir) / "htdemucs" / stem / "vocals.wav"

    if not vocals_path.exists():
        raise FileNotFoundError(f"Vocals not found at {vocals_path}")

    print(f"  Vocals isolated: {vocals_path}")
    return str(vocals_path)


def align_lyrics_to_audio(
    vocals_path: str,
    lyrics_text: str,
    language: str = "eng",
) -> List[Dict]:
    """
    Force-align lyrics text to audio using ctc-forced-aligner.

    Args:
        vocals_path: Path to the isolated vocals audio
        lyrics_text: The lyrics text to align
        language: Language code (default: eng)

    Returns:
        List of aligned word dicts in Suno-compatible format:
        [{"word": "text ", "startS": 0.5, "endS": 1.0, "success": True, "palign": 0}]
    """
    from ctc_forced_aligner import (
        load_audio, generate_emissions, preprocess_text,
        get_alignments, get_spans, postprocess_results,
        MODEL_URL, ensure_onnx_model, Tokenizer,
    )
    import onnxruntime

    # Load model
    model_dir = os.path.expanduser("~/.cache/ctc_forced_aligner")
    os.makedirs(model_dir, exist_ok=True)
    model_path = os.path.join(model_dir, "model.onnx")
    ensure_onnx_model(model_path, MODEL_URL)
    session = onnxruntime.InferenceSession(model_path)
    tokenizer = Tokenizer()

    # Load audio
    print("  Loading vocals for alignment...")
    audio = load_audio(vocals_path)

    # Clean lyrics: remove section tags and normalize for alignment
    import re
    clean_lines = []
    line_map = []  # Maps clean line index to original line text
    for line in lyrics_text.split("\n"):
        stripped = line.strip()
        if not stripped:
            continue
        # Remove section tags like [Intro], [Verse 1], [Chorus]
        cleaned = re.sub(r"\[.*?\]", "", stripped).strip()
        if cleaned:
            clean_lines.append(cleaned)
            line_map.append(stripped)

    flat_text = " ".join(clean_lines)

    print(f"  Aligning {len(flat_text.split())} words...")
    emissions, stride = generate_emissions(session, audio, batch_size=16)
    tokens_starred, text_starred = preprocess_text(
        flat_text, romanize=True, language=language
    )
    segments, scores, blank = get_alignments(
        emissions, tokens_starred, tokenizer
    )
    spans = get_spans(tokens_starred, segments, blank)
    results = postprocess_results(text_starred, spans, stride, scores)

    # Convert to Suno-compatible alignedWords format
    # We need to rebuild the text with section tags and newlines
    aligned_words = []
    result_idx = 0
    original_words = []

    # Build a flat list of original words with their line info
    for line_idx, line in enumerate(line_map):
        words_in_line = line.split()
        for word_idx, word in enumerate(words_in_line):
            is_last_in_line = word_idx == len(words_in_line) - 1
            # Check if this word is a section tag
            is_tag = word.startswith("[") and word.endswith("]")
            original_words.append({
                "text": word,
                "is_tag": is_tag,
                "is_last_in_line": is_last_in_line,
            })

    # Map the alignment results back to original words
    for orig_word in original_words:
        if orig_word["is_tag"]:
            # Section tags don't appear in the aligned results
            # Give them the timestamp of the next word
            suffix = "\n" if orig_word["is_last_in_line"] else " "
            aligned_words.append({
                "word": orig_word["text"] + suffix,
                "startS": results[result_idx]["start"] if result_idx < len(results) else 0.0,
                "endS": results[result_idx]["start"] if result_idx < len(results) else 0.0,
                "success": True,
                "palign": 0,
            })
        else:
            if result_idx < len(results):
                r = results[result_idx]
                suffix = "\n" if orig_word["is_last_in_line"] else " "
                aligned_words.append({
                    "word": orig_word["text"] + suffix,
                    "startS": round(r["start"], 3),
                    "endS": round(r["end"], 3),
                    "success": True,
                    "palign": 0,
                })
                result_idx += 1
            else:
                # Ran out of alignment results -- shouldn't happen
                suffix = "\n" if orig_word["is_last_in_line"] else " "
                aligned_words.append({
                    "word": orig_word["text"] + suffix,
                    "startS": 0.0,
                    "endS": 0.0,
                    "success": False,
                    "palign": 0,
                })

    print(f"  Aligned {len(aligned_words)} words ({result_idx} from forced alignment)")
    return aligned_words


def align_run(run_dir: Path) -> dict:
    """
    Run local forced alignment on a pipeline run.

    Reads lyrics.json and song.mp3, isolates vocals, aligns lyrics,
    and updates suno_output.json with corrected alignedWords.
    """
    lyrics_path = run_dir / "lyrics.json"
    audio_path = run_dir / "song.mp3"
    suno_path = run_dir / "suno_output.json"

    if not lyrics_path.exists() or not audio_path.exists():
        return {"success": False, "reason": "missing lyrics.json or song.mp3"}

    with open(lyrics_path) as f:
        lyrics_data = json.load(f)
    lyrics_text = lyrics_data.get("lyrics", lyrics_data.get("text", ""))

    if not lyrics_text:
        return {"success": False, "reason": "empty lyrics"}

    with tempfile.TemporaryDirectory() as tmpdir:
        # Step 1: Isolate vocals
        vocals_path = isolate_vocals(str(audio_path), tmpdir)

        # Step 2: Force-align lyrics to vocals
        aligned_words = align_lyrics_to_audio(vocals_path, lyrics_text)

    # Step 3: Update suno_output.json
    if suno_path.exists():
        with open(suno_path) as f:
            suno_data = json.load(f)

        # Backup original Suno alignment
        backup_path = run_dir / "suno_output_suno_alignment.json"
        if not backup_path.exists():
            with open(backup_path, "w") as f:
                json.dump(suno_data, f, indent=2)
    else:
        suno_data = {}

    suno_data["alignedWords"] = aligned_words
    suno_data.setdefault("metadata", {})["alignment_source"] = "local_forced_alignment"
    suno_data["metadata"]["alignment_method"] = "ctc-forced-aligner + demucs"

    with open(suno_path, "w") as f:
        json.dump(suno_data, f, indent=2)

    stats = {
        "success": True,
        "total_words": len(aligned_words),
        "aligned_words": sum(1 for w in aligned_words if w["success"]),
        "method": "ctc-forced-aligner + demucs",
    }

    print(f"  Local alignment complete: {stats['aligned_words']}/{stats['total_words']} words aligned")
    return stats


def main():
    run_dir = Path(os.environ.get("OUTPUT_DIR", ""))
    if not run_dir.exists():
        print("ERROR: OUTPUT_DIR not set")
        sys.exit(1)

    print("Running local forced alignment...")
    stats = align_run(run_dir)
    print(f"  Stats: {json.dumps(stats)}")

    if not stats.get("success"):
        sys.exit(1)


if __name__ == "__main__":
    main()
