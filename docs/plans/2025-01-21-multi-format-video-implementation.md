# Multi-Format Video Generation Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Transform the pipeline to generate three optimized videos from one song: full horizontal video (16:9, 2-4min) with traditional subtitles, and two vertical shorts (9:16, 30-60s) with karaoke subtitles.

**Architecture:** Build each format separately with format-specific media. Use hybrid subtitle system (pycaps for karaoke, FFmpeg for traditional). Auto-detect musical hook and AI-analyze educational peak for short extraction.

**Tech Stack:** Python, pycaps, FFmpeg, Playwright, Claude CLI, YouTube API, existing MoviePy pipeline

---

## Prerequisites

### Install Dependencies

**Step 1: Install pycaps**

```bash
./venv/bin/pip install "git+https://github.com/francozanardi/pycaps.git#egg=pycaps[all]"
```

Expected: Installation completes successfully

**Step 2: Install Playwright browser**

```bash
./venv/bin/playwright install chromium
```

Expected: Chromium browser downloads and installs

**Step 3: Verify installations**

```bash
./venv/bin/python -c "from pycaps import CapsPipelineBuilder; print('pycaps OK')"
./venv/bin/playwright --version
```

Expected: Both commands succeed without errors

**Step 4: Commit dependency updates**

```bash
echo "pycaps @ git+https://github.com/francozanardi/pycaps.git#egg=pycaps[all]" >> requirements.txt
git add requirements.txt
git commit -m "deps: add pycaps for karaoke subtitles"
```

---

## Task 1: Configuration Schema

**Files:**
- Modify: `config/config.json`

**Step 1: Add video_formats configuration**

Add to `config/config.json` after `suno_api` section:

```json
  "video_formats": {
    "full_video": {
      "enabled": true,
      "resolution": [1920, 1080],
      "aspect_ratio": "16:9",
      "subtitle_style": "traditional"
    },
    "shorts": {
      "enabled": true,
      "count": 2,
      "resolution": [1080, 1920],
      "aspect_ratio": "9:16",
      "subtitle_style": "karaoke",
      "duration_range": [30, 60],
      "extraction_methods": ["musical_hook", "educational_peak"]
    }
  },
```

**Step 2: Add subtitle_settings configuration**

Add after `video_formats`:

```json
  "subtitle_settings": {
    "karaoke": {
      "engine": "pycaps",
      "font": "Montserrat ExtraBold",
      "css_template": "templates/shorts_karaoke.css",
      "highlight_color": "#FFD700",
      "animation": "pop-in"
    },
    "traditional": {
      "engine": "ffmpeg",
      "font": "Montserrat Bold",
      "font_size": 48,
      "phrase_min_duration": 2.0,
      "phrase_max_duration": 3.5
    }
  },
```

**Step 3: Update media_sources with orientation preferences**

Add to existing `media_sources` section:

```json
    "orientation_preference": {
      "full_video": "landscape",
      "shorts": "portrait"
    }
```

**Step 4: Verify JSON is valid**

```bash
python -m json.tool config/config.json > /dev/null
```

Expected: No errors

**Step 5: Commit configuration changes**

```bash
git add config/config.json
git commit -m "config: add multi-format video settings"
```

---

## Task 2: CSS Template for Karaoke Subtitles

**Files:**
- Create: `templates/shorts_karaoke.css`

**Step 1: Create templates directory**

```bash
mkdir -p templates
```

**Step 2: Write karaoke CSS template**

Create `templates/shorts_karaoke.css`:

```css
/* Karaoke subtitle styling for YouTube Shorts */

.word {
  font-family: 'Montserrat ExtraBold', 'Arial Black', sans-serif;
  font-size: 72px;
  font-weight: 900;
  color: white;
  text-transform: uppercase;
  letter-spacing: 2px;

  /* Bold black outline for readability */
  text-shadow:
    -4px -4px 0 #000,
     4px -4px 0 #000,
    -4px  4px 0 #000,
     4px  4px 0 #000,
    -4px  0   0 #000,
     4px  0   0 #000,
     0   -4px 0 #000,
     0    4px 0 #000;

  /* Pop-in animation */
  animation: pop-in 0.2s ease-out;
}

/* Currently narrated word - bright gold highlight */
.word-being-narrated {
  color: #FFD700;
  transform: scale(1.15);
  filter: drop-shadow(0 0 10px rgba(255, 215, 0, 0.8));
}

/* Pop-in animation keyframes */
@keyframes pop-in {
  0% {
    transform: scale(0.7);
    opacity: 0;
  }
  50% {
    transform: scale(1.05);
  }
  100% {
    transform: scale(1);
    opacity: 1;
  }
}

/* Positioning - centered vertically, allow horizontal flow */
.subtitle-container {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  text-align: center;
  width: 90%;
  z-index: 100;
}
```

**Step 3: Commit CSS template**

```bash
git add templates/shorts_karaoke.css
git commit -m "feat: add karaoke subtitle CSS template"
```

---

## Task 3: Segment Analysis Script

**Files:**
- Create: `agents/analyze_segments.py`

**Step 1: Write segment analyzer stub**

Create `agents/analyze_segments.py`:

```python
#!/usr/bin/env python3
"""
Segment analyzer for multi-format video generation.
Identifies musical hook and educational peak segments from full song.
"""

import json
import sys
from pathlib import Path
from typing import Dict, List, Tuple


def load_lyrics() -> Dict:
    """Load Suno lyrics with word-level timestamps."""
    lyrics_file = Path(f"{os.environ['OUTPUT_DIR']}/suno_output.json")
    with open(lyrics_file) as f:
        return json.load(f)


def detect_musical_hook(lyrics: Dict, min_duration: float = 30, max_duration: float = 60) -> Dict:
    """
    Detect chorus/hook section using lyric repetition analysis.

    Returns segment with start/end timestamps and rationale.
    """
    # TODO: Implement chorus detection
    pass


def analyze_educational_peak(lyrics: Dict, topic: str, min_duration: float = 30, max_duration: float = 60) -> Dict:
    """
    Use Claude CLI to identify the most educational segment.

    Returns segment with start/end timestamps and rationale.
    """
    # TODO: Implement educational analysis via Claude
    pass


def main():
    """Main execution."""
    print("🎯 Analyzing song segments...")

    # Load config
    with open('config/config.json') as f:
        config = json.load(f)

    # Load lyrics
    lyrics = load_lyrics()

    # Load topic
    topic_file = Path('input/idea.txt')
    topic = topic_file.read_text().strip().split('.')[0]

    # Get duration range from config
    duration_range = config['video_formats']['shorts']['duration_range']
    min_dur, max_dur = duration_range

    # Analyze segments
    print("  Detecting musical hook...")
    hook_segment = detect_musical_hook(lyrics, min_dur, max_dur)

    print("  Analyzing educational peak...")
    edu_segment = analyze_educational_peak(lyrics, topic, min_dur, max_dur)

    # Full video segment
    full_duration = lyrics['metadata']['duration']
    full_segment = {
        'start': 0,
        'end': full_duration,
        'duration': full_duration,
        'rationale': 'Complete song for full video'
    }

    # Save segments
    output = {
        'full': full_segment,
        'hook': hook_segment,
        'educational': edu_segment
    }

    segments_file = Path(f"{os.environ['OUTPUT_DIR']}/segments.json")
    with open(segments_file, 'w') as f:
        json.dump(output, f, indent=2)

    print(f"✅ Segments analyzed:")
    print(f"  Full: 0-{full_duration:.1f}s")
    print(f"  Hook: {hook_segment['start']:.1f}-{hook_segment['end']:.1f}s ({hook_segment['duration']:.1f}s)")
    print(f"  Educational: {edu_segment['start']:.1f}-{edu_segment['end']:.1f}s ({edu_segment['duration']:.1f}s)")


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        sys.exit(1)
```

**Step 2: Make script executable**

```bash
chmod +x agents/analyze_segments.py
```

**Step 3: Commit stub**

```bash
git add agents/analyze_segments.py
git commit -m "feat: add segment analyzer stub"
```

**Step 4: Implement musical hook detection**

Replace the `detect_musical_hook` function in `agents/analyze_segments.py`:

```python
def detect_musical_hook(lyrics: Dict, min_duration: float = 30, max_duration: float = 60) -> Dict:
    """
    Detect chorus/hook section using lyric repetition analysis.

    Strategy:
    1. Find phrases that repeat 2+ times (likely chorus)
    2. Locate first complete repetition within duration range
    3. Fallback to seconds 30-90 if no clear chorus

    Returns segment with start/end timestamps and rationale.
    """
    words = lyrics.get('words', [])
    if not words:
        raise ValueError("No word-level timestamps in lyrics")

    # Build phrases (group by punctuation or 5-word chunks)
    phrases = []
    current_phrase = []

    for word_data in words:
        current_phrase.append(word_data['word'].lower().strip())

        # End phrase on punctuation or max 8 words
        if word_data['word'].endswith(('.', ',', '!', '?')) or len(current_phrase) >= 8:
            phrase_text = ' '.join(current_phrase)
            phrases.append({
                'text': phrase_text,
                'start': words[len(phrases) * 8]['start'] if phrases else 0,
                'word_indices': list(range(len(phrases) * 8, len(phrases) * 8 + len(current_phrase)))
            })
            current_phrase = []

    # Find repeated phrases
    phrase_counts = {}
    for i, phrase in enumerate(phrases):
        text = phrase['text']
        if text not in phrase_counts:
            phrase_counts[text] = []
        phrase_counts[text].append(i)

    # Find chorus (most repeated phrase with 2+ occurrences)
    repeated = {text: indices for text, indices in phrase_counts.items() if len(indices) >= 2}

    if repeated:
        # Get most common phrase
        chorus_text = max(repeated, key=lambda x: len(repeated[x]))
        chorus_indices = repeated[chorus_text]

        # Use first occurrence
        first_idx = chorus_indices[0]
        phrase_group = phrases[first_idx:first_idx+3]  # Take 3 phrases for full chorus

        start_time = phrase_group[0]['start']
        end_word_idx = phrase_group[-1]['word_indices'][-1]
        end_time = words[end_word_idx]['end'] if end_word_idx < len(words) else words[-1]['end']

        duration = end_time - start_time

        # Adjust to fit duration range
        if duration < min_duration:
            # Extend forward
            end_time = min(start_time + max_duration, words[-1]['end'])
        elif duration > max_duration:
            # Trim to max
            end_time = start_time + max_duration

        return {
            'start': round(start_time, 2),
            'end': round(end_time, 2),
            'duration': round(end_time - start_time, 2),
            'rationale': f'First chorus repetition: "{chorus_text[:50]}..."'
        }

    # Fallback: Use seconds 30-90 (typical hook placement)
    fallback_start = 30
    fallback_end = min(90, words[-1]['end'])
    fallback_duration = fallback_end - fallback_start

    # Adjust to min duration
    if fallback_duration < min_duration:
        fallback_end = min(fallback_start + max_duration, words[-1]['end'])

    return {
        'start': fallback_start,
        'end': round(fallback_end, 2),
        'duration': round(fallback_end - fallback_start, 2),
        'rationale': 'Fallback: typical hook placement (30-90s)'
    }
```

**Step 5: Implement educational peak analysis**

Replace the `analyze_educational_peak` function in `agents/analyze_segments.py`:

```python
import subprocess


def analyze_educational_peak(lyrics: Dict, topic: str, min_duration: float = 30, max_duration: float = 60) -> Dict:
    """
    Use Claude CLI to identify the most educational segment.

    Returns segment with start/end timestamps and rationale.
    """
    # Get full lyrics text
    words = lyrics.get('words', [])
    lyrics_text = ' '.join([w['word'] for w in words])

    # Build prompt for Claude
    prompt = f"""Analyze these song lyrics about "{topic}" and identify the {min_duration}-{max_duration} second segment with the HIGHEST EDUCATIONAL VALUE.

LYRICS WITH TIMESTAMPS:
{json.dumps(words, indent=2)}

TASK:
1. Identify the segment where the key concept is explained most clearly
2. Look for definitions, examples, or cause-and-effect explanations
3. Segment must be {min_duration}-{max_duration} seconds long
4. Return ONLY valid JSON with this exact schema:

{{
  "start_timestamp": <float>,
  "end_timestamp": <float>,
  "rationale": "<brief explanation of educational value>"
}}

CRITICAL: Respond with ONLY the JSON object, no markdown, no explanation."""

    try:
        result = subprocess.run(
            ['claude', '-p', prompt, '--dangerously-skip-permissions'],
            capture_output=True,
            text=True,
            timeout=60
        )

        if result.returncode != 0:
            raise Exception(f"Claude CLI failed: {result.stderr}")

        # Parse JSON response
        output = result.stdout.strip()

        # Remove markdown code blocks if present
        if '```json' in output:
            output = output.split('```json')[1].split('```')[0].strip()
        elif '```' in output:
            output = output.split('```')[1].split('```')[0].strip()

        analysis = json.loads(output)

        start = analysis['start_timestamp']
        end = analysis['end_timestamp']
        duration = end - start

        # Validate duration
        if duration < min_duration or duration > max_duration:
            raise ValueError(f"Claude returned invalid duration: {duration}s")

        return {
            'start': round(start, 2),
            'end': round(end, 2),
            'duration': round(duration, 2),
            'rationale': analysis['rationale']
        }

    except Exception as e:
        print(f"  ⚠️  Claude analysis failed: {e}", file=sys.stderr)
        print(f"  Using fallback: first {min_duration}s of song", file=sys.stderr)

        # Fallback: First segment after intro
        fallback_start = 10  # Skip intro
        fallback_end = min(fallback_start + max_duration, words[-1]['end'])

        return {
            'start': fallback_start,
            'end': round(fallback_end, 2),
            'duration': round(fallback_end - fallback_start, 2),
            'rationale': 'Fallback: first educational segment after intro'
        }
```

**Step 6: Add missing import**

Add at top of `agents/analyze_segments.py`:

```python
import os
```

**Step 7: Test segment analyzer (will fail without real data)**

```bash
# This will fail without OUTPUT_DIR set, which is expected
./agents/analyze_segments.py 2>&1 | head -5
```

Expected: Script runs but fails looking for environment variable (proves syntax is correct)

**Step 8: Commit implementation**

```bash
git add agents/analyze_segments.py
git commit -m "feat: implement segment analysis with hook detection and Claude AI"
```

---

## Task 4: Media Fetcher Enhancement

**Files:**
- Modify: `agents/download_media.py`

**Step 1: Add aspect ratio parameter**

Add to argument parser in `agents/download_media.py` (find the argparse section):

```python
parser.add_argument('--aspect-ratio', choices=['landscape', 'portrait', 'any'],
                   default='any', help='Preferred media orientation')
parser.add_argument('--segment', choices=['full', 'hook', 'educational'],
                   default='full', help='Which segment to fetch media for')
```

**Step 2: Add orientation filtering to API calls**

Find the Pexels API call section and add orientation parameter:

```python
# In pexels_search function or similar
params = {
    'query': query,
    'per_page': per_page,
    'page': page
}

# Add orientation if specified
if aspect_ratio == 'landscape':
    params['orientation'] = 'landscape'
elif aspect_ratio == 'portrait':
    params['orientation'] = 'portrait'
# 'any' means no filter
```

**Step 3: Update output directory based on segment**

Add segment-based subdirectory logic:

```python
# After OUTPUT_DIR is set
segment = args.segment
if segment != 'full':
    output_dir = os.path.join(output_dir, segment)
    os.makedirs(output_dir, exist_ok=True)
```

**Step 4: Commit media fetcher enhancements**

```bash
git add agents/download_media.py
git commit -m "feat: add aspect ratio and segment support to media fetcher"
```

---

## Task 5: Subtitle Generation Scripts

**Files:**
- Create: `agents/generate_subtitles.py`

**Step 1: Create subtitle generator stub**

Create `agents/generate_subtitles.py`:

```python
#!/usr/bin/env python3
"""
Unified subtitle generator supporting both traditional and karaoke styles.
"""

import json
import os
import sys
import subprocess
from pathlib import Path
from typing import Dict, List


def load_config() -> Dict:
    """Load configuration."""
    with open('config/config.json') as f:
        return json.load(f)


def load_lyrics() -> Dict:
    """Load Suno lyrics with word-level timestamps."""
    lyrics_file = Path(f"{os.environ['OUTPUT_DIR']}/suno_output.json")
    with open(lyrics_file) as f:
        return json.load(f)


def generate_traditional_srt(words: List[Dict], output_file: Path) -> None:
    """
    Generate traditional phrase-level SRT subtitles.
    Groups words into 2-3 second readable phrases.
    """
    # TODO: Implement traditional subtitle generation
    pass


def generate_karaoke_srt(words: List[Dict], output_file: Path) -> None:
    """
    Generate word-level SRT for karaoke highlighting.
    Each word gets its own subtitle entry with precise timing.
    """
    # TODO: Implement karaoke SRT generation
    pass


def apply_pycaps_subtitles(video_path: Path, srt_path: Path, output_path: Path, css_template: Path) -> None:
    """Apply karaoke subtitles using pycaps."""
    # TODO: Implement pycaps integration
    pass


def apply_ffmpeg_subtitles(video_path: Path, srt_path: Path, output_path: Path, config: Dict) -> None:
    """Apply traditional subtitles using FFmpeg."""
    # TODO: Implement FFmpeg subtitle burning
    pass


def main():
    """Main execution."""
    import argparse

    parser = argparse.ArgumentParser(description='Generate and apply video subtitles')
    parser.add_argument('--engine', choices=['pycaps', 'ffmpeg'], required=True,
                       help='Subtitle engine to use')
    parser.add_argument('--type', choices=['karaoke', 'traditional'], required=True,
                       help='Subtitle style')
    parser.add_argument('--video', choices=['full', 'short_hook', 'short_educational'], required=True,
                       help='Which video to subtitle')
    parser.add_argument('--segment', help='Segment name for loading correct timestamps')

    args = parser.parse_args()

    print(f"🎬 Generating {args.type} subtitles with {args.engine}...")

    # TODO: Implement main logic

    print("✅ Subtitles applied successfully")


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
```

**Step 2: Make executable**

```bash
chmod +x agents/generate_subtitles.py
```

**Step 3: Commit stub**

```bash
git add agents/generate_subtitles.py
git commit -m "feat: add subtitle generator stub"
```

**Step 4: Implement traditional SRT generation**

Replace `generate_traditional_srt` function:

```python
def generate_traditional_srt(words: List[Dict], output_file: Path, min_duration: float = 2.0, max_duration: float = 3.5) -> None:
    """
    Generate traditional phrase-level SRT subtitles.
    Groups words into 2-3 second readable phrases.
    """
    phrases = []
    current_phrase = []
    current_start = None

    for word_data in words:
        word = word_data['word']
        start = word_data['start']
        end = word_data['end']

        if current_start is None:
            current_start = start

        current_phrase.append(word)

        # End phrase on punctuation or duration limits
        duration = end - current_start
        ends_sentence = word.rstrip().endswith(('.', '!', '?'))

        if duration >= min_duration and (ends_sentence or duration >= max_duration):
            phrases.append({
                'start': current_start,
                'end': end,
                'text': ' '.join(current_phrase)
            })
            current_phrase = []
            current_start = None

    # Add remaining words as final phrase
    if current_phrase:
        phrases.append({
            'start': current_start,
            'end': words[-1]['end'],
            'text': ' '.join(current_phrase)
        })

    # Write SRT format
    with open(output_file, 'w') as f:
        for i, phrase in enumerate(phrases, 1):
            start_time = format_srt_timestamp(phrase['start'])
            end_time = format_srt_timestamp(phrase['end'])

            f.write(f"{i}\n")
            f.write(f"{start_time} --> {end_time}\n")
            f.write(f"{phrase['text']}\n")
            f.write("\n")


def format_srt_timestamp(seconds: float) -> str:
    """Convert seconds to SRT timestamp format (HH:MM:SS,mmm)."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds % 1) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"
```

**Step 5: Implement karaoke SRT generation**

Replace `generate_karaoke_srt` function:

```python
def generate_karaoke_srt(words: List[Dict], output_file: Path) -> None:
    """
    Generate word-level SRT for karaoke highlighting.
    Each word gets its own subtitle entry with precise timing.
    """
    with open(output_file, 'w') as f:
        for i, word_data in enumerate(words, 1):
            start_time = format_srt_timestamp(word_data['start'])
            end_time = format_srt_timestamp(word_data['end'])

            f.write(f"{i}\n")
            f.write(f"{start_time} --> {end_time}\n")
            f.write(f"{word_data['word']}\n")
            f.write("\n")
```

**Step 6: Implement pycaps integration**

Replace `apply_pycaps_subtitles` function:

```python
def apply_pycaps_subtitles(video_path: Path, srt_path: Path, output_path: Path, css_template: Path) -> None:
    """Apply karaoke subtitles using pycaps."""
    from pycaps import CapsPipelineBuilder

    print(f"  Applying karaoke subtitles with pycaps...")
    print(f"  Video: {video_path}")
    print(f"  SRT: {srt_path}")
    print(f"  CSS: {css_template}")

    pipeline = (CapsPipelineBuilder()
        .with_input_video(str(video_path))
        .with_srt_file(str(srt_path))
        .add_css(str(css_template))
        .build())

    pipeline.run(output=str(output_path))
    print(f"  ✅ Karaoke subtitles applied")
```

**Step 7: Implement FFmpeg integration**

Replace `apply_ffmpeg_subtitles` function:

```python
def apply_ffmpeg_subtitles(video_path: Path, srt_path: Path, output_path: Path, config: Dict) -> None:
    """Apply traditional subtitles using FFmpeg."""
    subtitle_config = config['subtitle_settings']['traditional']
    font = subtitle_config['font']
    font_size = subtitle_config['font_size']

    print(f"  Burning subtitles with FFmpeg...")
    print(f"  Font: {font}, Size: {font_size}")

    # Convert SRT to ASS for better styling control
    ass_path = srt_path.with_suffix('.ass')

    # First convert SRT to ASS with styling
    cmd_convert = [
        'ffmpeg', '-y',
        '-i', str(srt_path),
        '-f', 'ass',
        str(ass_path)
    ]

    result = subprocess.run(cmd_convert, capture_output=True, text=True)
    if result.returncode != 0:
        raise Exception(f"FFmpeg SRT->ASS conversion failed: {result.stderr}")

    # Burn ASS subtitles into video
    style = f"FontName={font},FontSize={font_size},PrimaryColour=&HFFFFFF&,OutlineColour=&H000000&,Outline=3,Shadow=2"

    cmd_burn = [
        'ffmpeg', '-y',
        '-i', str(video_path),
        '-vf', f"ass={ass_path}:force_style='{style}'",
        '-c:v', 'libx264',
        '-c:a', 'copy',
        str(output_path)
    ]

    result = subprocess.run(cmd_burn, capture_output=True, text=True)
    if result.returncode != 0:
        raise Exception(f"FFmpeg subtitle burn failed: {result.stderr}")

    print(f"  ✅ Traditional subtitles burned")
```

**Step 8: Implement main logic**

Replace the `main()` function TODO section:

```python
    config = load_config()
    lyrics = load_lyrics()

    output_dir = Path(os.environ['OUTPUT_DIR'])
    subtitles_dir = output_dir / 'subtitles'
    subtitles_dir.mkdir(exist_ok=True)

    # Determine segment for timestamp filtering
    segment = args.segment or args.video.replace('short_', '')

    # Load segment info if needed
    if segment != 'full':
        segments_file = output_dir / 'segments.json'
        with open(segments_file) as f:
            segments = json.load(f)

        segment_info = segments[segment]

        # Filter words to segment timeframe
        words = [
            w for w in lyrics['words']
            if segment_info['start'] <= w['start'] <= segment_info['end']
        ]

        # Adjust timestamps to start from 0
        offset = segment_info['start']
        for w in words:
            w['start'] -= offset
            w['end'] -= offset
    else:
        words = lyrics['words']

    # Generate appropriate SRT
    if args.type == 'karaoke':
        srt_file = subtitles_dir / f"{args.video}_karaoke.srt"
        generate_karaoke_srt(words, srt_file)
    else:
        srt_file = subtitles_dir / f"{args.video}_traditional.srt"
        min_dur = config['subtitle_settings']['traditional']['phrase_min_duration']
        max_dur = config['subtitle_settings']['traditional']['phrase_max_duration']
        generate_traditional_srt(words, srt_file, min_dur, max_dur)

    print(f"  Generated: {srt_file}")

    # Apply subtitles to video
    video_file = output_dir / f"{args.video}.mp4"
    output_file = output_dir / f"{args.video}_subtitled.mp4"

    if args.engine == 'pycaps':
        css_template = Path(config['subtitle_settings']['karaoke']['css_template'])
        apply_pycaps_subtitles(video_file, srt_file, output_file, css_template)
    else:
        apply_ffmpeg_subtitles(video_file, srt_file, output_file, config)

    # Replace original with subtitled version
    video_file.unlink()
    output_file.rename(video_file)
```

**Step 9: Test syntax**

```bash
./agents/generate_subtitles.py --help
```

Expected: Help message displays without errors

**Step 10: Commit subtitle implementation**

```bash
git add agents/generate_subtitles.py
git commit -m "feat: implement subtitle generation with pycaps and FFmpeg"
```

---

## Task 6: Upload Script Enhancement

**Files:**
- Modify: `upload_to_youtube.sh`

**Step 1: Add video type parameter**

Add after existing argument parsing in `upload_to_youtube.sh`:

```bash
VIDEO_TYPE="full"  # Default

for arg in "$@"; do
    case $arg in
        --type=*)
            VIDEO_TYPE="${arg#*=}"
            ;;
        # ... existing args ...
    esac
done
```

**Step 2: Add metadata templates based on type**

Add function to generate metadata:

```bash
generate_metadata() {
    local video_type=$1
    local topic=$2

    case $video_type in
        full)
            TITLE="${topic} - Full Educational Song"
            DESCRIPTION="Learn about ${topic} through music! Full version.

Watch the Shorts versions:
- Musical Hook: [PLACEHOLDER_HOOK]
- Educational Highlight: [PLACEHOLDER_EDU]

#education #learning #science"
            ;;
        short_hook)
            TITLE="${topic} 🎵 #Shorts"
            DESCRIPTION="${topic}

Watch the full version: [PLACEHOLDER_FULL]

#shorts #education #learning"
            ;;
        short_educational)
            TITLE="${topic} Explained 📚 #Shorts"
            DESCRIPTION="${topic} - Key concept explained!

Watch the full version: [PLACEHOLDER_FULL]

#shorts #education #learning"
            ;;
    esac
}
```

**Step 3: Call metadata generation**

Add before upload:

```bash
# Extract topic from idea.txt
TOPIC=$(head -1 input/idea.txt | cut -d'.' -f1)

# Generate metadata
generate_metadata "$VIDEO_TYPE" "$TOPIC"
```

**Step 4: Output video ID for cross-linking**

Add after successful upload:

```bash
# Extract video ID from response
VIDEO_ID=$(echo "$UPLOAD_RESPONSE" | jq -r '.id')

# Output for cross-linking script
echo "$VIDEO_ID" > "${OUTPUT_DIR}/video_id_${VIDEO_TYPE}.txt"

# Also print to stdout for capture
echo "$VIDEO_ID"
```

**Step 5: Commit upload enhancements**

```bash
git add upload_to_youtube.sh
git commit -m "feat: add video type parameter and metadata templates"
```

---

## Task 7: Cross-Linking Script

**Files:**
- Create: `agents/crosslink_videos.py`

**Step 1: Create cross-linker**

Create `agents/crosslink_videos.py`:

```python
#!/usr/bin/env python3
"""
Cross-link uploaded videos by updating descriptions.
"""

import os
import sys
import pickle
from pathlib import Path
from googleapiclient.discovery import build


def get_youtube_service():
    """Get authenticated YouTube API service."""
    token_path = Path('config/youtube_token.pickle')

    with open(token_path, 'rb') as token:
        creds = pickle.load(token)

    return build('youtube', 'v3', credentials=creds)


def update_video_description(youtube, video_id: str, new_description: str):
    """Update video description."""
    # Get current video details
    response = youtube.videos().list(
        part='snippet',
        id=video_id
    ).execute()

    if not response['items']:
        raise ValueError(f"Video not found: {video_id}")

    snippet = response['items'][0]['snippet']

    # Update description
    snippet['description'] = new_description

    # Update video
    youtube.videos().update(
        part='snippet',
        body={
            'id': video_id,
            'snippet': snippet
        }
    ).execute()


def main(full_id: str, hook_id: str, edu_id: str):
    """Cross-link three videos."""
    print("🔗 Cross-linking videos...")

    youtube = get_youtube_service()

    # Build URLs
    full_url = f"https://youtube.com/watch?v={full_id}"
    hook_url = f"https://youtube.com/shorts/{hook_id}"
    edu_url = f"https://youtube.com/shorts/{edu_id}"

    # Load topic
    topic = Path('input/idea.txt').read_text().strip().split('.')[0]

    # Update full video description
    full_desc = f"""Learn about {topic} through music! Full version.

Watch the Shorts versions:
- Musical Hook: {hook_url}
- Educational Highlight: {edu_url}

#education #learning #science"""

    print(f"  Updating full video description...")
    update_video_description(youtube, full_id, full_desc)

    # Update hook short description
    hook_desc = f"""{topic} 🎵

Watch the full version: {full_url}
See the educational highlight: {edu_url}

#shorts #education #learning"""

    print(f"  Updating hook short description...")
    update_video_description(youtube, hook_id, hook_desc)

    # Update educational short description
    edu_desc = f"""{topic} - Key concept explained! 📚

Watch the full version: {full_url}
See the musical hook: {hook_url}

#shorts #education #learning"""

    print(f"  Updating educational short description...")
    update_video_description(youtube, edu_id, edu_desc)

    print("✅ Cross-linking complete")

    # Save results
    output_dir = Path(os.environ.get('OUTPUT_DIR', 'outputs/current'))
    results = {
        'full_video': {'id': full_id, 'url': full_url},
        'hook_short': {'id': hook_id, 'url': hook_url},
        'educational_short': {'id': edu_id, 'url': edu_url}
    }

    import json
    with open(output_dir / 'upload_results.json', 'w') as f:
        json.dump(results, f, indent=2)


if __name__ == '__main__':
    if len(sys.argv) != 4:
        print("Usage: crosslink_videos.py <full_video_id> <hook_short_id> <edu_short_id>")
        sys.exit(1)

    try:
        main(sys.argv[1], sys.argv[2], sys.argv[3])
    except Exception as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
```

**Step 2: Make executable**

```bash
chmod +x agents/crosslink_videos.py
```

**Step 3: Commit cross-linker**

```bash
git add agents/crosslink_videos.py
git commit -m "feat: add video cross-linking script"
```

---

## Task 8: Pipeline Orchestration

**Files:**
- Modify: `pipeline.sh`

**Step 1: Add new stage for segment analysis**

Add after Stage 1 (Research) in `pipeline.sh`:

```bash
# Stage 1.5: Segment Analysis
if [ $START_STAGE -le 2 ]; then
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}Stage 1.5/8: Segment Analysis${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

    if python3 agents/analyze_segments.py; then
        echo "✅ Segments analyzed"
    else
        echo -e "${RED}❌ Segment analysis failed${NC}"
        exit 1
    fi
    echo ""
fi
```

**Step 2: Modify media download for multi-format**

Replace the media download stage to fetch for all three formats:

```bash
# Stage 3: Media Download (parallel for all formats)
if [ $START_STAGE -le 3 ]; then
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}Stage 3/8: Media Download${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

    echo "📥 Downloading media for all formats..."

    # Create subdirectories
    mkdir -p "${RUN_DIR}/media/full"
    mkdir -p "${RUN_DIR}/media/hook"
    mkdir -p "${RUN_DIR}/media/educational"

    # Download in parallel
    python3 agents/download_media.py --aspect-ratio=landscape --segment=full &
    PID_FULL=$!

    python3 agents/download_media.py --aspect-ratio=portrait --segment=hook &
    PID_HOOK=$!

    python3 agents/download_media.py --aspect-ratio=portrait --segment=educational &
    PID_EDU=$!

    # Wait for all downloads
    wait $PID_FULL && echo "  ✅ Full video media downloaded" || exit 1
    wait $PID_HOOK && echo "  ✅ Hook short media downloaded" || exit 1
    wait $PID_EDU && echo "  ✅ Educational short media downloaded" || exit 1

    echo ""
fi
```

**Step 3: Add subtitle generation stage**

Add new stage after video assembly:

```bash
# Stage 6: Subtitle Generation
if [ $START_STAGE -le 6 ]; then
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}Stage 6/8: Subtitle Generation${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

    echo "📝 Adding subtitles to all videos..."

    # Traditional subtitles for full video (FFmpeg)
    python3 agents/generate_subtitles.py --engine=ffmpeg --type=traditional --video=full

    # Karaoke subtitles for shorts (pycaps)
    python3 agents/generate_subtitles.py --engine=pycaps --type=karaoke --video=short_hook --segment=hook
    python3 agents/generate_subtitles.py --engine=pycaps --type=karaoke --video=short_educational --segment=educational

    echo "✅ All subtitles applied"
    echo ""
fi
```

**Step 4: Add upload and cross-linking stage**

Add new final stage:

```bash
# Stage 7: Upload and Cross-Link
if [ $START_STAGE -le 7 ]; then
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}Stage 7/8: Upload and Cross-Link${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

    echo "📤 Uploading all videos..."

    # Upload all three (upload script saves IDs to files)
    ./upload_to_youtube.sh --type=full
    FULL_ID=$(cat "${RUN_DIR}/video_id_full.txt")

    ./upload_to_youtube.sh --type=short_hook
    HOOK_ID=$(cat "${RUN_DIR}/video_id_short_hook.txt")

    ./upload_to_youtube.sh --type=short_educational
    EDU_ID=$(cat "${RUN_DIR}/video_id_short_educational.txt")

    echo "✅ All videos uploaded"
    echo ""

    # Cross-link descriptions
    echo "🔗 Cross-linking videos..."
    python3 agents/crosslink_videos.py "$FULL_ID" "$HOOK_ID" "$EDU_ID"

    echo ""
fi
```

**Step 5: Update final output message**

Replace final success message:

```bash
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}✅ Pipeline Complete!${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo "📹 Videos created:"
echo "  Full: ${RUN_DIR}/full.mp4"
echo "  Hook Short: ${RUN_DIR}/short_hook.mp4"
echo "  Educational Short: ${RUN_DIR}/short_educational.mp4"
echo ""
if [ -f "${RUN_DIR}/upload_results.json" ]; then
    echo "🔗 YouTube URLs:"
    cat "${RUN_DIR}/upload_results.json" | jq -r '.full_video.url, .hook_short.url, .educational_short.url'
fi
```

**Step 6: Commit pipeline orchestration**

```bash
git add pipeline.sh
git commit -m "feat: orchestrate multi-format video generation pipeline"
```

---

## Task 9: Testing and Documentation

**Files:**
- Create: `docs/MULTI_FORMAT_USAGE.md`

**Step 1: Create usage documentation**

Create `docs/MULTI_FORMAT_USAGE.md`:

```markdown
# Multi-Format Video Generation Usage Guide

## Overview

The pipeline now generates **three optimized videos** from one educational song:

1. **Full Horizontal Video** (1920x1080, 2-4min) - Traditional subtitles
2. **Short #1: Musical Hook** (1080x1920, 30-60s) - Karaoke subtitles
3. **Short #2: Educational Peak** (1080x1920, 30-60s) - Karaoke subtitles

All three are uploaded to YouTube with cross-linked descriptions.

## Quick Start

```bash
# Run the pipeline as normal
./pipeline.sh

# Or in express mode
./pipeline.sh --express
```

The pipeline automatically:
- Generates full-length song (2-4 minutes)
- Analyzes and extracts best segments for Shorts
- Fetches format-specific media (16:9 and 9:16)
- Builds three separate videos
- Applies appropriate subtitles to each
- Uploads all three with cross-links

## Output Structure

```
outputs/runs/YYYYMMDD_HHMMSS/
├── segments.json              # Extracted time ranges
├── media/
│   ├── full/                  # Horizontal clips
│   ├── hook/                  # Vertical clips (hook)
│   └── educational/           # Vertical clips (educational)
├── subtitles/
│   ├── full_traditional.srt
│   ├── hook_karaoke.srt
│   └── educational_karaoke.srt
├── full.mp4                   # Final horizontal video
├── short_hook.mp4             # Final hook short
├── short_educational.mp4      # Final educational short
└── upload_results.json        # YouTube URLs
```

## Configuration

### Enable/Disable Formats

Edit `config/config.json`:

```json
"video_formats": {
  "full_video": {
    "enabled": true  // Set to false to skip full video
  },
  "shorts": {
    "enabled": true,  // Set to false to skip shorts
    "count": 2
  }
}
```

### Customize Subtitle Styling

Edit CSS template: `templates/shorts_karaoke.css`

Adjust colors, fonts, animations to match your brand.

### Adjust Segment Duration

```json
"shorts": {
  "duration_range": [30, 60]  // Min and max seconds
}
```

## Daily Automation

No changes needed! The existing automation works:

```bash
./automation/daily_pipeline.sh
```

Notifications will include all three video URLs.

## Troubleshooting

### pycaps Installation Issues

```bash
# Reinstall pycaps
./venv/bin/pip uninstall pycaps
./venv/bin/pip install "git+https://github.com/francozanardi/pycaps.git#egg=pycaps[all]"

# Reinstall Playwright
./venv/bin/playwright install chromium
```

### Segment Analysis Fails

Check `logs/pipeline_*.log` for Claude CLI errors.

Fallback: The system uses heuristics if Claude analysis fails.

### Upload Fails

Verify YouTube authentication:
```bash
./automation/youtube_channel_helper.py --list-channels
```

## Performance Notes

- **Total time**: 3-4x longer than single video (3 videos + subtitles)
- **pycaps**: Slower than FFmpeg (browser rendering), acceptable for daily automation
- **Parallel processing**: Media download and video assembly run in parallel

## Future Enhancements

- A/B test segment extraction strategies
- Animated thumbnails for Shorts
- Custom segment selection via config
- Analytics tracking per format type
```

**Step 2: Commit documentation**

```bash
git add docs/MULTI_FORMAT_USAGE.md
git commit -m "docs: add multi-format usage guide"
```

**Step 3: Update main README**

Add to `README.md` after existing pipeline description:

```markdown
### Multi-Format Generation

The pipeline generates **three videos** from each song:

- **Full Video** (16:9, 2-4min): Complete educational content with traditional subtitles
- **Hook Short** (9:16, 30-60s): Most catchy musical moment with karaoke subtitles
- **Educational Short** (9:16, 30-60s): Key learning moment with karaoke subtitles

All three are automatically uploaded to YouTube with cross-linked descriptions.

See [Multi-Format Usage Guide](docs/MULTI_FORMAT_USAGE.md) for details.
```

**Step 4: Commit README update**

```bash
git add README.md
git commit -m "docs: add multi-format generation to README"
```

---

## Task 10: Final Integration Test

**Step 1: Create test topic**

```bash
echo "How ocean waves form and move energy across water. Tone: calming and rhythmic" > input/idea.txt
```

**Step 2: Run pipeline in test mode**

```bash
# Start from segment analysis to test new components
./pipeline.sh --start=2
```

**Step 3: Verify outputs**

```bash
# Check segments were analyzed
cat outputs/current/segments.json

# Check all three videos exist
ls -lh outputs/current/*.mp4

# Check subtitles were generated
ls -lh outputs/current/subtitles/
```

**Step 4: Check for errors**

```bash
tail -50 logs/pipeline_*.log
```

**Step 5: If successful, create final commit**

```bash
git add .
git commit -m "feat: complete multi-format video generation implementation

- Three videos per song: full (16:9) + two shorts (9:16)
- Hybrid subtitle system: pycaps karaoke + FFmpeg traditional
- Auto-detect musical hook and AI-analyze educational peak
- Cross-linked YouTube uploads
- Maintains daily automation compatibility

Tested with full pipeline run."
```

---

## Execution Complete

**Plan saved to:** `docs/plans/2025-01-21-multi-format-video-implementation.md`

This plan implements the complete multi-format video generation system with:
- ✅ Segment analysis (hook detection + AI educational analysis)
- ✅ Aspect ratio-aware media fetching
- ✅ Hybrid subtitle system (pycaps + FFmpeg)
- ✅ Three-video upload with cross-linking
- ✅ Pipeline orchestration
- ✅ Configuration and documentation

Each task follows TDD principles where applicable and includes frequent commits. The implementation maintains compatibility with existing automation while adding powerful new capabilities.
