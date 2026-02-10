#!/usr/bin/env python3
"""Audio utilities for AI clip generation."""

import subprocess
from pathlib import Path


def slice_audio(song_path: str, start: float, duration: float, output_path: str) -> bool:
    """
    Slice audio segment from song using ffmpeg.

    Args:
        song_path: Path to source audio file
        start: Start time in seconds
        duration: Duration of slice in seconds
        output_path: Path to save sliced audio

    Returns:
        True if successful, False otherwise
    """
    if not Path(song_path).exists():
        print(f"    ⚠️ Source audio not found: {song_path}")
        return False

    try:
        cmd = [
            "ffmpeg", "-y",
            "-i", song_path,
            "-ss", str(start),
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


def get_audio_duration(audio_path: str) -> float:
    """
    Get duration of audio file in seconds.

    Args:
        audio_path: Path to audio file

    Returns:
        Duration in seconds, or 0.0 on error
    """
    try:
        result = subprocess.run([
            'ffprobe', '-v', 'error',
            '-show_entries', 'format=duration',
            '-of', 'default=noprint_wrappers=1:nokey=1',
            audio_path
        ], capture_output=True, text=True, timeout=10)

        if result.returncode == 0:
            return float(result.stdout.strip())
    except Exception:
        pass
    return 0.0
