#!/usr/bin/env python3
"""Audio utilities for AI clip generation."""

import shutil
import subprocess
from pathlib import Path


def _find_binary(name: str) -> str:
    """Find ffmpeg/ffprobe binary, checking common Homebrew paths as fallback."""
    path = shutil.which(name)
    if path:
        return path
    for candidate in [f"/opt/homebrew/bin/{name}", f"/usr/local/bin/{name}"]:
        if Path(candidate).exists():
            return candidate
    return name  # Fall back to bare name, will raise FileNotFoundError if missing


def slice_audio(song_path: str, start: float, duration: float, output_path: str, offset_ms: float = 0) -> bool:
    """
    Slice audio segment from song using ffmpeg.

    Args:
        song_path: Path to source audio file
        start: Start time in seconds
        duration: Duration of slice in seconds
        output_path: Path to save sliced audio
        offset_ms: Offset in milliseconds to compensate for lipsync latency.
                   Positive values start the audio earlier (for models with lag).

    Returns:
        True if successful, False otherwise
    """
    if not Path(song_path).exists():
        print(f"    ⚠️ Source audio not found: {song_path}")
        return False

    # Apply offset: positive offset means we start earlier in the song
    # so the lipsync model's output aligns with the actual audio position
    adjusted_start = max(0, start - (offset_ms / 1000.0))

    if offset_ms != 0:
        print(f"    📍 Lipsync offset: {offset_ms}ms (audio starts at {adjusted_start:.3f}s instead of {start:.3f}s)")

    try:
        ffmpeg = _find_binary("ffmpeg")
        cmd = [
            ffmpeg, "-y",
            "-i", song_path,
            "-ss", str(adjusted_start),
            "-t", str(duration),
            "-acodec", "libmp3lame",
            "-ar", "44100",
            "-q:a", "2",
            output_path
        ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            timeout=30
        )

        if result.returncode != 0:
            print(f"    ⚠️ ffmpeg error: {result.stderr.decode()[:200]}")
            return False

        return Path(output_path).exists() and Path(output_path).stat().st_size > 0

    except subprocess.TimeoutExpired:
        print("    ⚠️ Audio slice timed out")
        return False
    except Exception as e:
        print(f"    ⚠️ Audio slice failed: {e}")
        return False


def generate_hook_sfx(output_path: str = "/tmp/hook_sfx.wav") -> str:
    """
    Generate a short bass-thud impact sound for use at t=0 of a video.

    Creates a 0.1s 200Hz sine wave with fade-out — a subtle audio
    pattern interrupt that research shows improves retention by ~19%.

    Args:
        output_path: Where to save the generated SFX.

    Returns:
        Path to the generated WAV file, or empty string on failure.
    """
    try:
        ffmpeg = _find_binary("ffmpeg")
        cmd = [
            ffmpeg, "-y",
            "-f", "lavfi",
            "-i", "sine=frequency=200:duration=0.1",
            "-af", "afade=t=out:d=0.1,volume=0.3",
            output_path
        ]

        result = subprocess.run(cmd, capture_output=True, timeout=10)

        if result.returncode == 0 and Path(output_path).exists():
            return output_path
    except Exception as e:
        print(f"    Warning: Hook SFX generation failed: {e}")

    return ""


def get_audio_duration(audio_path: str) -> float:
    """
    Get duration of audio file in seconds.

    Args:
        audio_path: Path to audio file

    Returns:
        Duration in seconds, or 0.0 on error
    """
    try:
        ffprobe = _find_binary("ffprobe")
        result = subprocess.run([
            ffprobe, '-v', 'error',
            '-show_entries', 'format=duration',
            '-of', 'default=noprint_wrappers=1:nokey=1',
            audio_path
        ], capture_output=True, text=True, timeout=10)

        if result.returncode == 0:
            return float(result.stdout.strip())
    except Exception:
        pass
    return 0.0
