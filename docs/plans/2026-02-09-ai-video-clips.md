# AI Video Clips Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add 3 AI-generated 8-second video clips featuring realistic humans lip-syncing to Suno audio in topic-matched scientific environments, placed in the first 60 seconds of each music video.

**Architecture:** New pipeline stage (4.5) generates clips via fal.ai Kling API after segment analysis. Clips are integrated into media plans and assembled with existing stock footage. Shorts pull from the same first 60 seconds.

**Tech Stack:** Python 3, fal-client (Kling API), ffmpeg (audio slicing), Claude CLI (environment prompts), MoviePy (assembly)

---

## Task 1: Install Dependencies

**Files:**
- Modify: `requirements.txt` (if exists) or install directly

**Step 1: Install fal-client package**

Run:
```bash
cd /Users/ethantrokie/SoftwareDevProjects/MusicVideosAutomate
source venv/bin/activate
pip install fal-client
```

Expected: Successfully installed fal-client

**Step 2: Verify installation**

Run:
```bash
python3 -c "import fal_client; print('fal_client imported successfully')"
```

Expected: `fal_client imported successfully`

**Step 3: Commit**

```bash
git add -A
git commit -m "chore: add fal-client dependency for Kling AI integration"
```

---

## Task 2: Add Configuration Schema

**Files:**
- Modify: `config/config.json` (add after line 93, before closing brace)

**Step 1: Read current config**

Run:
```bash
cat config/config.json | tail -10
```

Expected: See current end of config file

**Step 2: Add fal_api and ai_clips configuration**

Add these sections before the final `}` in `config/config.json`:

```json
  "fal_api": {
    "api_key": "YOUR_FAL_API_KEY"
  },
  "ai_clips": {
    "enabled": false,
    "count": 3,
    "duration_seconds": 8,
    "placement_window_seconds": 60,
    "fallback_to_stock": true,
    "max_retries": 2
  }
```

Note: `enabled: false` by default until API key is configured.

**Step 3: Validate JSON syntax**

Run:
```bash
python3 -c "import json; json.load(open('config/config.json')); print('Valid JSON')"
```

Expected: `Valid JSON`

**Step 4: Commit**

```bash
git add config/config.json
git commit -m "feat: add fal_api and ai_clips configuration schema"
```

---

## Task 3: Create Kling API Client

**Files:**
- Create: `agents/kling_api_client.py`
- Test: `tests/test_kling_api_client.py`

**Step 1: Create test file**

Create `tests/test_kling_api_client.py`:

```python
#!/usr/bin/env python3
"""Tests for Kling API client."""

import pytest
import os
import sys
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'agents'))


class TestKlingAPIClient:
    """Test Kling API client initialization and methods."""

    def test_client_initialization(self):
        """Test client initializes with API key."""
        from kling_api_client import KlingAPIClient

        client = KlingAPIClient("test_api_key")

        assert client.api_key == "test_api_key"
        assert client.max_retries == 5
        assert os.environ.get("FAL_KEY") == "test_api_key"

    def test_transient_errors_defined(self):
        """Test transient error codes are defined for retry logic."""
        from kling_api_client import KlingAPIClient

        client = KlingAPIClient("test_key")

        assert 502 in client.transient_errors
        assert 503 in client.transient_errors
        assert 429 in client.transient_errors

    @patch('kling_api_client.fal_client')
    def test_generate_video_success(self, mock_fal):
        """Test successful video generation."""
        from kling_api_client import KlingAPIClient

        mock_fal.subscribe.return_value = {
            "video": {"url": "https://example.com/video.mp4"}
        }

        client = KlingAPIClient("test_key")
        result = client.generate_video(
            image_url="https://example.com/image.png",
            prompt="Test environment",
            duration=8
        )

        assert result["status"] == "success"
        assert result["video_url"] == "https://example.com/video.mp4"

    @patch('kling_api_client.fal_client')
    def test_apply_lipsync_success(self, mock_fal):
        """Test successful lip-sync application."""
        from kling_api_client import KlingAPIClient

        mock_fal.subscribe.return_value = {
            "video": {"url": "https://example.com/synced.mp4"}
        }

        client = KlingAPIClient("test_key")
        result = client.apply_lipsync(
            video_url="https://example.com/video.mp4",
            audio_url="https://example.com/audio.mp3"
        )

        assert result["status"] == "success"
        assert result["video_url"] == "https://example.com/synced.mp4"

    @patch('kling_api_client.fal_client')
    def test_apply_lipsync_failure_returns_original(self, mock_fal):
        """Test lip-sync failure returns original video."""
        from kling_api_client import KlingAPIClient

        mock_fal.subscribe.side_effect = Exception("API Error")

        client = KlingAPIClient("test_key")
        client.max_retries = 1  # Speed up test

        result = client.apply_lipsync(
            video_url="https://example.com/video.mp4",
            audio_url="https://example.com/audio.mp3"
        )

        assert result["status"] == "lipsync_failed"
        assert result["video_url"] == "https://example.com/video.mp4"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
```

**Step 2: Run test to verify it fails**

Run:
```bash
cd /Users/ethantrokie/SoftwareDevProjects/MusicVideosAutomate
python3 -m pytest tests/test_kling_api_client.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'kling_api_client'`

**Step 3: Create kling_api_client.py**

Create `agents/kling_api_client.py`:

```python
#!/usr/bin/env python3
"""
Kling AI API client for video generation and lip-sync.
Uses fal.ai as the API provider for pay-as-you-go pricing.

Pricing (identical to direct Kling API):
- Video generation: $0.07/second (Kling 2.6 Pro)
- Lip-sync: $0.014/second (rounded to 5s increments)
- Total for 8s clip with lip-sync: ~$0.70
"""

import os
import time
import requests
from typing import Dict

import fal_client


class KlingAPIClient:
    """Client for Kling AI video generation via fal.ai."""

    def __init__(self, api_key: str):
        """
        Initialize client with fal.ai API key.

        Args:
            api_key: fal.ai API key
        """
        self.api_key = api_key
        os.environ["FAL_KEY"] = api_key

        # Transient errors for retry logic (matches SunoAPIClient pattern)
        self.transient_errors = {502, 503, 504, 429, 408, 520, 521, 522, 523, 524, 525, 526}
        self.max_retries = 5

    def generate_video(
        self,
        image_url: str,
        prompt: str,
        duration: int = 8,
        aspect_ratio: str = "16:9"
    ) -> Dict:
        """
        Generate video from image using Kling 2.6 Pro.

        Args:
            image_url: URL of reference image (performer)
            prompt: Environment/scene description
            duration: Video duration in seconds (max 10 for v2.6)
            aspect_ratio: "16:9" for landscape, "9:16" for portrait

        Returns:
            Dict with video_url, duration, status
        """
        for attempt in range(self.max_retries):
            try:
                print(f"    Calling Kling API (attempt {attempt + 1}/{self.max_retries})...")

                result = fal_client.subscribe(
                    "fal-ai/kling-video/v2.6/pro/image-to-video",
                    arguments={
                        "start_image_url": image_url,
                        "prompt": prompt,
                        "duration": str(min(duration, 10)),
                        "aspect_ratio": aspect_ratio,
                        "negative_prompt": "blur, distort, low quality, static face, frozen expression"
                    }
                )

                return {
                    "video_url": result["video"]["url"],
                    "duration": duration,
                    "status": "success"
                }

            except Exception as e:
                error_msg = str(e)
                if attempt < self.max_retries - 1:
                    wait_time = (2 ** attempt) * 2
                    print(f"    ⚠️ Generation error: {error_msg}")
                    print(f"    Retrying in {wait_time}s...")
                    time.sleep(wait_time)
                    continue
                raise Exception(f"Video generation failed after {self.max_retries} retries: {error_msg}")

    def apply_lipsync(
        self,
        video_url: str,
        audio_url: str
    ) -> Dict:
        """
        Apply lip-sync to video using audio.

        Args:
            video_url: URL of generated video
            audio_url: URL of audio segment for lip-sync

        Returns:
            Dict with video_url and status
        """
        for attempt in range(self.max_retries):
            try:
                print(f"    Applying lip-sync (attempt {attempt + 1}/{self.max_retries})...")

                result = fal_client.subscribe(
                    "fal-ai/kling-video/lipsync/audio-to-video",
                    arguments={
                        "video_url": video_url,
                        "audio_url": audio_url
                    }
                )

                return {
                    "video_url": result["video"]["url"],
                    "status": "success"
                }

            except Exception as e:
                error_msg = str(e)
                if attempt < self.max_retries - 1:
                    wait_time = (2 ** attempt) * 2
                    print(f"    ⚠️ LipSync error: {error_msg}")
                    print(f"    Retrying in {wait_time}s...")
                    time.sleep(wait_time)
                    continue

                # Return original video without lip-sync on final failure
                print(f"    ⚠️ LipSync failed after {self.max_retries} retries, using base video")
                return {
                    "video_url": video_url,
                    "status": "lipsync_failed"
                }

    def upload_file(self, local_path: str) -> str:
        """
        Upload local file to fal.ai and return URL.

        Args:
            local_path: Path to local file

        Returns:
            URL of uploaded file
        """
        return fal_client.upload_file(local_path)

    def download_video(self, video_url: str, output_path: str) -> bool:
        """
        Download video from URL to local path.

        Args:
            video_url: URL of video to download
            output_path: Local path to save video

        Returns:
            True if successful, False otherwise
        """
        try:
            response = requests.get(video_url, stream=True, timeout=120)
            if response.status_code != 200:
                raise Exception(f"Download error: {response.status_code}")

            with open(output_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            return True

        except Exception as e:
            print(f"    ❌ Download failed: {e}")
            return False
```

**Step 4: Run tests to verify they pass**

Run:
```bash
python3 -m pytest tests/test_kling_api_client.py -v
```

Expected: All 5 tests PASS

**Step 5: Commit**

```bash
git add agents/kling_api_client.py tests/test_kling_api_client.py
git commit -m "feat: add Kling API client with video generation and lip-sync"
```

---

## Task 4: Create Audio Slicing Utility

**Files:**
- Create: `agents/audio_utils.py`
- Test: `tests/test_audio_utils.py`

**Step 1: Create test file**

Create `tests/test_audio_utils.py`:

```python
#!/usr/bin/env python3
"""Tests for audio utilities."""

import pytest
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'agents'))


class TestAudioSlicing:
    """Test audio slicing functionality."""

    def test_slice_audio_creates_file(self):
        """Test that slice_audio creates output file."""
        from audio_utils import slice_audio

        # Use an existing song file from outputs if available
        test_songs = list(Path("outputs/runs").glob("*/song.mp3"))
        if not test_songs:
            pytest.skip("No song.mp3 files available for testing")

        song_path = str(test_songs[0])

        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
            output_path = tmp.name

        try:
            result = slice_audio(song_path, start=5.0, duration=8.0, output_path=output_path)

            assert result is True
            assert os.path.exists(output_path)
            assert os.path.getsize(output_path) > 0
        finally:
            if os.path.exists(output_path):
                os.unlink(output_path)

    def test_slice_audio_invalid_path_returns_false(self):
        """Test that invalid input path returns False."""
        from audio_utils import slice_audio

        result = slice_audio(
            "/nonexistent/path.mp3",
            start=0,
            duration=8,
            output_path="/tmp/test_output.mp3"
        )

        assert result is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
```

**Step 2: Run test to verify it fails**

Run:
```bash
python3 -m pytest tests/test_audio_utils.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'audio_utils'`

**Step 3: Create audio_utils.py**

Create `agents/audio_utils.py`:

```python
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
```

**Step 4: Run tests to verify they pass**

Run:
```bash
python3 -m pytest tests/test_audio_utils.py -v
```

Expected: Tests PASS (or skip if no song.mp3 available)

**Step 5: Commit**

```bash
git add agents/audio_utils.py tests/test_audio_utils.py
git commit -m "feat: add audio slicing utility for clip generation"
```

---

## Task 5: Create Clip Placement Logic

**Files:**
- Create: `agents/clip_placement.py`
- Test: `tests/test_clip_placement.py`

**Step 1: Create test file**

Create `tests/test_clip_placement.py`:

```python
#!/usr/bin/env python3
"""Tests for clip placement logic."""

import pytest
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'agents'))


class TestClipPlacement:
    """Test clip placement determination."""

    def test_determine_placements_returns_three_clips(self):
        """Test that we always get 3 clip placements."""
        from clip_placement import determine_clip_placements

        # Minimal aligned words
        aligned_words = [
            {"word": "[Verse 1]\nTest ", "startS": 0.5, "endS": 1.0},
            {"word": "lyrics ", "startS": 1.0, "endS": 1.5},
            {"word": "[Chorus]\nMore ", "startS": 30.0, "endS": 30.5},
        ]

        clips = determine_clip_placements(aligned_words)

        assert len(clips) == 3
        assert all("id" in c for c in clips)
        assert all("start_time" in c for c in clips)
        assert all("end_time" in c for c in clips)
        assert all("segment_type" in c for c in clips)

    def test_clips_within_60_seconds(self):
        """Test all clips are placed within first 60 seconds."""
        from clip_placement import determine_clip_placements

        aligned_words = [
            {"word": "Test ", "startS": 0.5, "endS": 1.0},
            {"word": "[Chorus]\nChorus ", "startS": 45.0, "endS": 46.0},
        ]

        clips = determine_clip_placements(aligned_words)

        for clip in clips:
            assert clip["end_time"] <= 60, f"Clip {clip['id']} ends at {clip['end_time']}s"

    def test_clips_are_8_seconds(self):
        """Test each clip is 8 seconds long."""
        from clip_placement import determine_clip_placements

        aligned_words = [{"word": "Test ", "startS": 0.5, "endS": 1.0}]

        clips = determine_clip_placements(aligned_words)

        for clip in clips:
            duration = clip["end_time"] - clip["start_time"]
            assert duration == 8, f"Clip {clip['id']} is {duration}s, expected 8s"

    def test_extract_lyrics_for_window(self):
        """Test lyrics extraction for time window."""
        from clip_placement import extract_lyrics_for_clip

        aligned_words = [
            {"word": "[Verse 1]\nHello ", "startS": 0.0, "endS": 0.5},
            {"word": "world ", "startS": 0.5, "endS": 1.0},
            {"word": "test ", "startS": 1.0, "endS": 1.5},
            {"word": "outside ", "startS": 10.0, "endS": 10.5},
        ]

        lyrics = extract_lyrics_for_clip(aligned_words, start=0.0, end=2.0)

        assert "world" in lyrics
        assert "test" in lyrics
        assert "outside" not in lyrics
        assert "[Verse" not in lyrics  # Section markers removed


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
```

**Step 2: Run test to verify it fails**

Run:
```bash
python3 -m pytest tests/test_clip_placement.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'clip_placement'`

**Step 3: Create clip_placement.py**

Create `agents/clip_placement.py`:

```python
#!/usr/bin/env python3
"""Clip placement logic for AI video generation."""

from typing import Dict, List


def determine_clip_placements(aligned_words: List[Dict], clip_duration: int = 8) -> List[Dict]:
    """
    Determine 3 clip placements within first 60 seconds based on song structure.

    Args:
        aligned_words: List of aligned word dicts with startS, endS, word
        clip_duration: Duration of each clip in seconds

    Returns:
        List of 3 clip definitions with id, start_time, end_time, segment_type
    """
    clips = []

    # Find verse and chorus markers
    verse_start = None
    chorus_start = None
    first_word_start = 0.5  # Default if no words found

    for word in aligned_words:
        text = word.get("word", "")
        start = word.get("startS", 0)

        # Track first actual word
        if first_word_start == 0.5 and start > 0:
            first_word_start = start

        # Find section markers
        if "[Verse" in text and verse_start is None:
            verse_start = start
        if "[Chorus]" in text and chorus_start is None:
            chorus_start = start

    # Clip 1: Intro (start of song)
    intro_start = max(0, first_word_start - 0.5)
    clips.append({
        "id": 1,
        "start_time": intro_start,
        "end_time": intro_start + clip_duration,
        "segment_type": "intro"
    })

    # Clip 2: Verse (around 15-20 seconds)
    if verse_start and 10 < verse_start < 52:
        verse_placement = verse_start
    else:
        verse_placement = 15

    # Ensure we don't overlap with clip 1
    if verse_placement < clips[0]["end_time"] + 2:
        verse_placement = clips[0]["end_time"] + 2

    clips.append({
        "id": 2,
        "start_time": verse_placement,
        "end_time": verse_placement + clip_duration,
        "segment_type": "verse"
    })

    # Clip 3: Chorus (around 30-45 seconds)
    if chorus_start and 25 < chorus_start < 52:
        chorus_placement = chorus_start
    else:
        chorus_placement = 38

    # Ensure we don't overlap with clip 2
    if chorus_placement < clips[1]["end_time"] + 2:
        chorus_placement = clips[1]["end_time"] + 2

    # Ensure clip ends within 60 seconds
    if chorus_placement + clip_duration > 60:
        chorus_placement = 52  # 52 + 8 = 60

    clips.append({
        "id": 3,
        "start_time": chorus_placement,
        "end_time": chorus_placement + clip_duration,
        "segment_type": "chorus"
    })

    return clips


def extract_lyrics_for_clip(aligned_words: List[Dict], start: float, end: float) -> str:
    """
    Extract lyrics text for a specific time window.

    Args:
        aligned_words: List of aligned word dicts
        start: Start time in seconds
        end: End time in seconds

    Returns:
        Concatenated lyrics for the time window
    """
    lyrics = []

    for word in aligned_words:
        word_start = word.get("startS", 0)
        word_end = word.get("endS", 0)

        # Include words that overlap with our window
        if word_start < end and word_end > start:
            text = word.get("word", "").strip()
            # Remove section markers like [Verse 1]
            if not text.startswith("["):
                # Clean up newlines from section markers
                text = text.replace("\n", " ").strip()
                if text:
                    lyrics.append(text)

    return " ".join(lyrics)
```

**Step 4: Run tests to verify they pass**

Run:
```bash
python3 -m pytest tests/test_clip_placement.py -v
```

Expected: All 4 tests PASS

**Step 5: Commit**

```bash
git add agents/clip_placement.py tests/test_clip_placement.py
git commit -m "feat: add clip placement logic for song structure analysis"
```

---

## Task 6: Create Environment Prompt Generator

**Files:**
- Create: `agents/environment_generator.py`
- Test: `tests/test_environment_generator.py`

**Step 1: Create test file**

Create `tests/test_environment_generator.py`:

```python
#!/usr/bin/env python3
"""Tests for environment prompt generation."""

import pytest
import os
import sys
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'agents'))


class TestEnvironmentGenerator:
    """Test environment prompt generation."""

    def test_generate_fallback_prompt(self):
        """Test fallback prompt when Claude fails."""
        from environment_generator import generate_fallback_prompt

        prompt = generate_fallback_prompt("sonar technology", "intro")

        assert len(prompt) > 20
        assert "lighting" in prompt.lower() or "studio" in prompt.lower()

    def test_detect_voice_gender_male(self):
        """Test male voice detection from tags."""
        from environment_generator import detect_voice_gender

        suno_data = {
            "song": {"tags": "upbeat pop rock, male vocals, energetic"}
        }

        gender = detect_voice_gender(suno_data)

        assert gender == "male"

    def test_detect_voice_gender_female(self):
        """Test female voice detection from tags."""
        from environment_generator import detect_voice_gender

        suno_data = {
            "song": {"tags": "soft ballad, female vocals, emotional"}
        }

        gender = detect_voice_gender(suno_data)

        assert gender == "female"

    def test_detect_voice_gender_default(self):
        """Test default gender when not specified."""
        from environment_generator import detect_voice_gender

        suno_data = {"song": {"tags": "instrumental"}}

        gender = detect_voice_gender(suno_data)

        assert gender == "male"  # Default


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
```

**Step 2: Run test to verify it fails**

Run:
```bash
python3 -m pytest tests/test_environment_generator.py -v
```

Expected: FAIL with `ModuleNotFoundError`

**Step 3: Create environment_generator.py**

Create `agents/environment_generator.py`:

```python
#!/usr/bin/env python3
"""Environment prompt generation for AI video clips."""

import subprocess
from typing import Dict, List


def generate_environment_prompts(
    topic: str,
    key_facts: List[str],
    clips: List[Dict]
) -> List[str]:
    """
    Use Claude to generate environment prompts for each clip.

    Args:
        topic: Educational topic
        key_facts: Key facts about the topic
        clips: List of clip definitions with segment_type

    Returns:
        List of environment prompt strings
    """
    prompts = []

    for clip in clips:
        prompt = _build_claude_prompt(topic, key_facts, clip)

        try:
            result = subprocess.run(
                [
                    "/Users/ethantrokie/.local/bin/claude",
                    "-p", prompt,
                    "--model", "claude-sonnet-4-5",
                    "--dangerously-skip-permissions"
                ],
                capture_output=True,
                text=True,
                timeout=60
            )

            if result.returncode == 0 and result.stdout.strip():
                prompts.append(result.stdout.strip())
            else:
                prompts.append(generate_fallback_prompt(topic, clip["segment_type"]))

        except Exception as e:
            print(f"    ⚠️ Claude prompt failed: {e}")
            prompts.append(generate_fallback_prompt(topic, clip["segment_type"]))

    return prompts


def _build_claude_prompt(topic: str, key_facts: List[str], clip: Dict) -> str:
    """Build the Claude prompt for environment generation."""
    facts_str = ", ".join(key_facts[:5]) if key_facts else "general science concepts"

    return f"""You are generating an environment description for an AI video.

Topic: {topic}
Key Facts: {facts_str}
Clip: {clip['id']} of 3
Segment: {clip['segment_type']}

Generate a vivid, cinematic environment description for a music video scene.
A realistic human performer will be singing in this environment.

Requirements:
- Must relate to the educational topic above
- Cinematic and visually striking
- Appropriate for a person to be standing/performing in
- 2-3 sentences maximum
- Include lighting description
- Include specific visual elements related to the topic

Output ONLY the environment description, nothing else. No quotes, no prefix."""


def generate_fallback_prompt(topic: str, segment_type: str) -> str:
    """
    Generate fallback prompt when Claude is unavailable.

    Args:
        topic: Educational topic
        segment_type: intro, verse, or chorus

    Returns:
        Generic but topic-aware environment prompt
    """
    topic_lower = topic.lower()

    # Topic-based environment hints
    if any(w in topic_lower for w in ["ocean", "water", "sonar", "submarine", "marine"]):
        base = "Deep ocean research facility with blue-green ambient lighting"
    elif any(w in topic_lower for w in ["space", "star", "planet", "rocket", "astronaut"]):
        base = "Futuristic space station interior with starfield visible through windows"
    elif any(w in topic_lower for w in ["lab", "chemistry", "molecule", "dna", "cell", "biology"]):
        base = "High-tech laboratory with glowing equipment and holographic displays"
    elif any(w in topic_lower for w in ["engine", "machine", "bearing", "mechanical", "factory"]):
        base = "Modern industrial facility with polished metal surfaces and dramatic lighting"
    elif any(w in topic_lower for w in ["electric", "circuit", "computer", "digital"]):
        base = "Neon-lit tech studio with circuit patterns and digital screens"
    else:
        base = "Professional studio with dramatic lighting and scientific equipment"

    return f"{base}, cinematic atmosphere, modern and sleek environment"


def detect_voice_gender(suno_data: Dict) -> str:
    """
    Detect voice gender from Suno metadata.

    Args:
        suno_data: Suno output data with song tags

    Returns:
        "male" or "female"
    """
    tags = suno_data.get("song", {}).get("tags", "").lower()

    if "female" in tags or "woman" in tags:
        return "female"
    elif "male" in tags or "man" in tags:
        return "male"
    else:
        return "male"  # Default


def get_performer_image_url(gender: str) -> str:
    """
    Get a stock performer image URL for video generation.

    Args:
        gender: "male" or "female"

    Returns:
        URL to performer reference image
    """
    # Stock images for performer reference
    if gender == "female":
        return "https://images.pexels.com/photos/3771089/pexels-photo-3771089.jpeg"
    else:
        return "https://images.pexels.com/photos/2531728/pexels-photo-2531728.jpeg"
```

**Step 4: Run tests to verify they pass**

Run:
```bash
python3 -m pytest tests/test_environment_generator.py -v
```

Expected: All 4 tests PASS

**Step 5: Commit**

```bash
git add agents/environment_generator.py tests/test_environment_generator.py
git commit -m "feat: add environment prompt generator with Claude integration"
```

---

## Task 7: Create Main AI Clip Generation Agent

**Files:**
- Create: `agents/generate_ai_clips.py`

**Step 1: Create the main agent file**

Create `agents/generate_ai_clips.py`:

```python
#!/usr/bin/env python3
"""
AI video clip generation agent.
Generates 3x 8-second clips with lip-synced singing in topic-matched environments.

Pipeline Stage: 4.5 (after Segment Analysis, before Media Curation)

Cost: ~$2.10 per video (3 clips x $0.70 each)
"""

import os
import sys
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List

# Add agents directory to path
sys.path.insert(0, str(Path(__file__).parent))
from output_helper import get_output_path, ensure_output_dir
from kling_api_client import KlingAPIClient
from audio_utils import slice_audio
from clip_placement import determine_clip_placements, extract_lyrics_for_clip
from environment_generator import (
    generate_environment_prompts,
    detect_voice_gender,
    get_performer_image_url
)

# Force unbuffered output
sys.stdout = os.fdopen(sys.stdout.fileno(), 'w', buffering=1)
sys.stderr = os.fdopen(sys.stderr.fileno(), 'w', buffering=1)


def load_config() -> Dict:
    """Load config from config.json."""
    config_path = Path("config/config.json")
    with open(config_path) as f:
        return json.load(f)


def load_suno_output() -> Dict:
    """Load Suno output with aligned words and audio URL."""
    suno_path = get_output_path("suno_output.json")
    with open(suno_path) as f:
        return json.load(f)


def load_research() -> Dict:
    """Load research data for topic context."""
    research_path = get_output_path("research.json")
    with open(research_path) as f:
        return json.load(f)


def main() -> int:
    """Main entry point for AI clip generation."""
    print("🎬 Stage 4.5: AI Video Clip Generation")
    print("=" * 50)

    # Load config
    config = load_config()
    ai_config = config.get("ai_clips", {})

    if not ai_config.get("enabled", False):
        print("  ⏭️  AI clips disabled in config, skipping")
        return 0

    fal_api_key = config.get("fal_api", {}).get("api_key")
    if not fal_api_key or fal_api_key == "YOUR_FAL_API_KEY":
        print("  ⚠️ FAL API key not configured, skipping AI clips")
        return 0

    # Load required data
    print("  📂 Loading pipeline data...")

    try:
        suno_data = load_suno_output()
        research = load_research()
    except FileNotFoundError as e:
        print(f"  ❌ Required file not found: {e}")
        return 1

    aligned_words = suno_data.get("alignedWords", [])
    topic = research.get("topic", "Educational topic")
    key_facts = research.get("key_facts", [])

    if not aligned_words:
        print("  ⚠️ No aligned words found, skipping AI clips")
        return 0

    # Determine clip placements
    print("  🎯 Determining clip placements...")
    clips = determine_clip_placements(aligned_words)

    for clip in clips:
        clip["lyrics"] = extract_lyrics_for_clip(
            aligned_words,
            clip["start_time"],
            clip["end_time"]
        )
        print(f"    Clip {clip['id']}: {clip['start_time']:.1f}s - {clip['end_time']:.1f}s ({clip['segment_type']})")

    # Generate environment prompts
    print("  🌍 Generating environment prompts...")
    environment_prompts = generate_environment_prompts(topic, key_facts, clips)

    for i, prompt in enumerate(environment_prompts):
        clips[i]["environment_prompt"] = prompt
        print(f"    Clip {i+1}: {prompt[:60]}...")

    # Detect voice gender
    gender = detect_voice_gender(suno_data)
    print(f"  🎤 Detected voice: {gender}")

    # Get performer reference image
    performer_image = get_performer_image_url(gender)

    # Initialize Kling client
    client = KlingAPIClient(fal_api_key)

    # Create output directories
    output_dir = os.getenv("OUTPUT_DIR", "outputs")
    ai_clips_dir = Path(output_dir) / "ai_clips"
    ai_clips_dir.mkdir(exist_ok=True)

    audio_slices_dir = ai_clips_dir / "audio_slices"
    audio_slices_dir.mkdir(exist_ok=True)

    song_path = get_output_path("song.mp3")

    # Generate clips
    manifest = {
        "generated_at": datetime.now().isoformat(),
        "topic": topic,
        "performer_gender": gender,
        "total_cost_usd": 0,
        "clips": []
    }

    for clip in clips:
        print(f"\n  🎬 Generating clip {clip['id']}/3...")

        clip_data = {
            "id": clip["id"],
            "file": f"clip_{clip['id']}.mp4",
            "start_time": clip["start_time"],
            "end_time": clip["end_time"],
            "segment_type": clip["segment_type"],
            "environment_prompt": clip["environment_prompt"],
            "lyrics_excerpt": clip["lyrics"][:100] + "..." if len(clip["lyrics"]) > 100 else clip["lyrics"],
            "generation_status": "pending",
            "lipsync_status": "pending",
            "cost_usd": 0
        }

        try:
            # Generate base video
            print(f"    🎥 Generating video...")
            full_prompt = f"A {gender} performer singing with emotion and energy. {clip['environment_prompt']}"

            video_result = client.generate_video(
                image_url=performer_image,
                prompt=full_prompt,
                duration=8,
                aspect_ratio="16:9"
            )

            clip_data["generation_status"] = video_result.get("status", "success")
            clip_data["cost_usd"] += 0.56  # $0.07/sec * 8 sec

            # Slice audio for lip-sync
            audio_slice_path = str(audio_slices_dir / f"slice_{clip['id']}.mp3")

            if slice_audio(str(song_path), clip["start_time"], 8, audio_slice_path):
                print(f"    🎵 Applying lip-sync...")

                # Upload audio slice
                audio_url = client.upload_file(audio_slice_path)

                # Apply lip-sync
                lipsync_result = client.apply_lipsync(
                    video_url=video_result["video_url"],
                    audio_url=audio_url
                )

                clip_data["lipsync_status"] = lipsync_result.get("status", "success")
                clip_data["cost_usd"] += 0.14  # $0.014/sec * 10 sec (rounded)

                final_video_url = lipsync_result["video_url"]
            else:
                print(f"    ⚠️ Audio slice failed, using video without lip-sync")
                clip_data["lipsync_status"] = "audio_slice_failed"
                final_video_url = video_result["video_url"]

            # Download final video
            output_path = str(ai_clips_dir / f"clip_{clip['id']}.mp4")
            print(f"    💾 Downloading clip...")

            if client.download_video(final_video_url, output_path):
                clip_data["generation_status"] = "success"
                print(f"    ✅ Clip {clip['id']} complete")
            else:
                clip_data["generation_status"] = "download_failed"
                print(f"    ❌ Clip {clip['id']} download failed")

        except Exception as e:
            print(f"    ❌ Clip {clip['id']} failed: {e}")
            clip_data["generation_status"] = "failed"
            clip_data["error"] = str(e)

        manifest["clips"].append(clip_data)
        manifest["total_cost_usd"] += clip_data["cost_usd"]

    # Save manifest
    manifest_path = ai_clips_dir / "ai_clip_manifest.json"
    with open(manifest_path, 'w') as f:
        json.dump(manifest, f, indent=2)

    # Summary
    successful = sum(1 for c in manifest["clips"] if c["generation_status"] == "success")
    print(f"\n{'=' * 50}")
    print(f"✅ AI Clip Generation Complete")
    print(f"   Successful: {successful}/3 clips")
    print(f"   Total cost: ${manifest['total_cost_usd']:.2f}")
    print(f"   Manifest: {manifest_path}")

    return 0 if successful > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
```

**Step 2: Verify the agent runs (dry run)**

Run:
```bash
python3 -c "import agents.generate_ai_clips; print('Module loads successfully')"
```

Expected: `Module loads successfully`

**Step 3: Commit**

```bash
git add agents/generate_ai_clips.py
git commit -m "feat: add main AI clip generation agent"
```

---

## Task 8: Add Pipeline Stage

**Files:**
- Modify: `pipeline.sh` (insert after line 256)

**Step 1: Locate insertion point**

Run:
```bash
sed -n '254,262p' pipeline.sh
```

Expected: See end of Stage 4 and start of Stage 5

**Step 2: Insert Stage 4.5 block**

Insert after line 256 (after `fi` that closes Stage 4, before Stage 5 comment):

```bash
# Stage 4.5: AI Video Clip Generation
if [ $START_STAGE -le 4 ]; then
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}Stage 4.5/7: AI Video Clip Generation${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

    echo "🎬 Generating AI video clips with lip-sync..."
    if python3 agents/generate_ai_clips.py; then
        echo "✅ AI clip generation complete"
    else
        echo -e "${YELLOW}⚠️  AI clip generation failed or skipped, will use stock footage only${NC}"
        # Non-critical failure - continue pipeline
    fi
    echo ""
fi
```

**Step 3: Verify syntax**

Run:
```bash
bash -n pipeline.sh && echo "Syntax OK"
```

Expected: `Syntax OK`

**Step 4: Commit**

```bash
git add pipeline.sh
git commit -m "feat: add Stage 4.5 for AI clip generation to pipeline"
```

---

## Task 9: Integrate AI Clips into Media Plans

**Files:**
- Modify: `agents/build_format_media_plan.py`

**Step 1: Add integrate_ai_clips function**

Add this function after the existing imports (around line 20):

```python
def integrate_ai_clips(shots: List[Dict], output_dir: str) -> List[Dict]:
    """
    Integrate AI-generated clips into the shot list at their designated times.
    AI clips take priority over stock footage at their placement times.

    Args:
        shots: Existing shot list from stock footage
        output_dir: Output directory path

    Returns:
        Modified shot list with AI clips integrated
    """
    ai_manifest_path = Path(output_dir) / "ai_clips" / "ai_clip_manifest.json"

    if not ai_manifest_path.exists():
        return shots  # No AI clips available

    try:
        with open(ai_manifest_path) as f:
            manifest = json.load(f)
    except Exception as e:
        print(f"  ⚠️ Could not load AI clip manifest: {e}")
        return shots

    # Get successful AI clips
    ai_clips = [
        clip for clip in manifest.get("clips", [])
        if clip.get("generation_status") == "success"
    ]

    if not ai_clips:
        return shots

    print(f"  📎 Integrating {len(ai_clips)} AI clips into media plan")

    # Create AI clip shots
    ai_shots = []
    for clip in ai_clips:
        ai_shot = {
            "shot_number": 0,  # Will be renumbered
            "local_path": str(Path(output_dir) / "ai_clips" / clip["file"]),
            "media_type": "video",
            "source": "ai_generated",
            "description": clip.get("environment_prompt", "AI generated clip"),
            "lyrics_match": clip.get("lyrics_excerpt", ""),
            "start_time": clip["start_time"],
            "end_time": clip["end_time"],
            "duration": clip["end_time"] - clip["start_time"],
            "absolute_start": clip["start_time"],
            "absolute_end": clip["end_time"],
            "priority": "high",
            "transition": "cut"
        }
        ai_shots.append(ai_shot)

    # Remove stock shots that overlap with AI clip times
    filtered_shots = []
    for shot in shots:
        shot_start = shot.get("absolute_start", shot.get("start_time", 0))
        shot_end = shot.get("absolute_end", shot.get("end_time", shot_start + shot.get("duration", 3)))

        # Check if this shot overlaps with any AI clip
        overlaps = False
        for ai_shot in ai_shots:
            ai_start = ai_shot["start_time"]
            ai_end = ai_shot["end_time"]

            if shot_start < ai_end and shot_end > ai_start:
                overlaps = True
                break

        if not overlaps:
            filtered_shots.append(shot)

    # Combine and sort by start time
    all_shots = filtered_shots + ai_shots
    all_shots.sort(key=lambda s: s.get("absolute_start", s.get("start_time", 0)))

    # Renumber shots
    for i, shot in enumerate(all_shots, 1):
        shot["shot_number"] = i

    print(f"  ✓ Final shot count: {len(all_shots)} (was {len(shots)}, +{len(ai_shots)} AI, -{len(shots) - len(filtered_shots)} replaced)")

    return all_shots
```

**Step 2: Call integrate_ai_clips in build_format_plan**

Find the `build_format_plan` function and add this call after shots are built (before returning):

```python
    # Integrate AI clips if available (only for full and intro formats that use first 60s)
    if format_type in ["full", "intro"]:
        shots = integrate_ai_clips(shots, os.getenv("OUTPUT_DIR", "outputs"))
```

**Step 3: Verify syntax**

Run:
```bash
python3 -m py_compile agents/build_format_media_plan.py && echo "Syntax OK"
```

Expected: `Syntax OK`

**Step 4: Commit**

```bash
git add agents/build_format_media_plan.py
git commit -m "feat: integrate AI clips into media plan generation"
```

---

## Task 10: Create Tests Directory (if needed)

**Step 1: Ensure tests directory exists**

Run:
```bash
mkdir -p tests
touch tests/__init__.py
```

**Step 2: Commit**

```bash
git add tests/__init__.py
git commit -m "chore: add tests directory"
```

---

## Task 11: End-to-End Test

**Step 1: Run unit tests**

Run:
```bash
python3 -m pytest tests/ -v --tb=short
```

Expected: All tests pass

**Step 2: Test agent standalone (with config disabled)**

Run:
```bash
export OUTPUT_DIR="outputs/runs/20260209_090015"
python3 agents/generate_ai_clips.py
```

Expected: `AI clips disabled in config, skipping` (since enabled=false)

**Step 3: Commit all work**

```bash
git add -A
git commit -m "feat: complete AI video clip generation feature

- Add Kling API client with fal.ai integration
- Add clip placement logic based on song structure
- Add environment prompt generation with Claude
- Add audio slicing utility
- Add main generate_ai_clips.py agent
- Add Stage 4.5 to pipeline.sh
- Integrate AI clips into media plan generation
- Add unit tests for all components

Cost: ~$2.10 per video (3 clips @ $0.70 each)
"
```

---

## Summary

| Task | Component | Status |
|------|-----------|--------|
| 1 | Install dependencies | |
| 2 | Add config schema | |
| 3 | Create Kling API client | |
| 4 | Create audio slicing utility | |
| 5 | Create clip placement logic | |
| 6 | Create environment generator | |
| 7 | Create main agent | |
| 8 | Add pipeline stage | |
| 9 | Integrate into media plans | |
| 10 | Create tests directory | |
| 11 | End-to-end test | |

## Next Steps After Implementation

1. Get fal.ai API key from https://fal.ai
2. Add API key to `config/config.json`
3. Set `"enabled": true` in `ai_clips` config
4. Run a test video with `./pipeline.sh`
5. Review generated clips for quality
