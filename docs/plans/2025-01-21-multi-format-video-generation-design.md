# Multi-Format Video Generation System Design

**Date:** 2025-01-21
**Status:** Approved for Implementation

## Overview

Transform the current single-video pipeline into a multi-format system that generates three optimized videos from one educational song:

1. **Full Horizontal Video** (1920x1080, 2-4min) - Complete educational content
2. **Short #1: Musical Hook** (1080x1920, 30-60s) - Viral discovery focused
3. **Short #2: Educational Peak** (1080x1920, 30-60s) - Learning discovery focused

## Goals

- Maximize content reach across YouTube's algorithm (regular videos + Shorts)
- Optimize each format for its discovery mechanism
- Maintain daily automation compatibility
- Provide viral hook content AND educational value content

## System Architecture

### Current Flow
```
Topic → Suno Song (60s) → Vertical Video (1080x1920) → Upload Short
```

### New Flow
```
Topic → Suno Full Song (2-4min) →
  ├─ Build Horizontal Full Video (1920x1080, full length, 16:9 media)
  ├─ Build Vertical Short #1 (1080x1920, 30-60s, 9:16 media) - Musical Hook
  └─ Build Vertical Short #2 (1080x1920, 30-60s, 9:16 media) - Educational Peak
     ↓
  Upload all three with cross-linking
```

## Detailed Design

### 1. Segment Analysis & Extraction

**Purpose:** Identify the best 30-60 second segments from the full song for Shorts

#### Short #1: Musical Hook Detection
**Strategy:** Auto-detect chorus/hook using lyric pattern analysis

**Algorithm:**
1. Parse Suno lyrics with timestamps
2. Identify repeated phrases (appears 2+ times = likely chorus)
3. Find first complete repetition with 30-60s duration
4. Fallback: Use seconds 30-90 if no clear chorus detected

**Implementation:** `scripts/3_analyze_segments.py`

#### Short #2: Educational Peak Detection
**Strategy:** AI-powered educational value analysis

**Algorithm:**
1. Send full lyrics + topic + tone to Claude Code CLI
2. Prompt: "Identify the 30-60 second segment where the key educational concept is explained most clearly and completely"
3. Claude analyzes and returns timestamps with rationale
4. Fallback: Use segment with highest keyword density if Claude unavailable

**Output Format:**
```json
{
  "full": {
    "start": 0,
    "end": 180.5,
    "duration": 180.5
  },
  "hook": {
    "start": 45.2,
    "end": 75.8,
    "duration": 30.6,
    "rationale": "First chorus repetition with complete hook"
  },
  "educational": {
    "start": 90.0,
    "end": 145.0,
    "duration": 55.0,
    "rationale": "Core concept explanation with examples"
  }
}
```

### 2. Media Gathering Strategy

**Enhancement:** Aspect ratio-aware media fetching

#### API Request Parameters

**For Full Horizontal Video (16:9):**
```python
{
  "orientation": "landscape",
  "query": keyword,
  "min_width": 1920,
  "min_height": 1080
}
```

**For Vertical Shorts (9:16):**
```python
{
  "orientation": "portrait",  # Current approach
  "query": keyword,
  "min_width": 1080,
  "min_height": 1920
}
```

#### Handling Mixed Aspect Ratios

Priority order when landscape footage unavailable:
1. **First choice:** Use landscape/square footage, crop to 16:9
2. **Second choice:** Use portrait footage with center-crop or smart-crop
3. **Last resort:** Letterbox with blurred background

#### Implementation
**Enhancement to `scripts/2_fetch_media.py`:**
- Add `--aspect-ratio` parameter: `landscape` or `portrait`
- Add `--segment` parameter: `full`, `hook`, or `educational`
- Filter API results by orientation preference
- Apply smart cropping when needed

### 3. Subtitle System

**Hybrid approach:** Different subtitle engines optimized for each format

#### Karaoke Subtitles (Vertical Shorts)
**Engine:** pycaps (CSS-based, browser-rendered)

**Why pycaps:**
- Built specifically for TikTok/YouTube Shorts style
- CSS-based styling with `.word-being-narrated` highlighting
- Built-in animations (pop, bounce, zoom)
- Perfect for viral content engagement

**Installation:**
```bash
pip install "git+https://github.com/francozanardi/pycaps.git#egg=pycaps[all]"
playwright install chromium
```

**CSS Template (`templates/shorts_karaoke.css`):**
```css
.word {
  font-family: 'Montserrat ExtraBold', sans-serif;
  font-size: 72px;
  color: white;
  text-shadow:
    -3px -3px 0 #000,
     3px -3px 0 #000,
    -3px  3px 0 #000,
     3px  3px 0 #000;
  animation: pop-in 0.2s ease-out;
}

.word-being-narrated {
  color: #FFD700; /* Bright gold highlight */
  transform: scale(1.1);
}

@keyframes pop-in {
  0% { transform: scale(0.8); opacity: 0; }
  100% { transform: scale(1); opacity: 1; }
}
```

**Python Integration:**
```python
from pycaps import CapsPipelineBuilder

def add_karaoke_subtitles(video_path, srt_file, output_path):
    pipeline = (CapsPipelineBuilder()
        .with_input_video(video_path)
        .with_srt_file(srt_file)  # Use Suno word-level timestamps
        .add_css("templates/shorts_karaoke.css")
        .build())
    pipeline.run(output=output_path)
```

#### Traditional Subtitles (Horizontal Full Video)
**Engine:** FFmpeg with ASS subtitle format

**Why FFmpeg:**
- Faster rendering (5-10x faster than MoviePy)
- Lower memory usage
- Better for phrase-level educational content
- No browser dependency

**Subtitle Generation:**
```python
def generate_traditional_subtitles(word_timestamps):
    """Convert word-level to phrase-level subtitles.

    Groups words into 2-3 second phrases for readability.
    """
    phrases = []
    current_phrase = []
    current_start = None

    for word in word_timestamps:
        if not current_start:
            current_start = word['start']
        current_phrase.append(word['text'])

        # End phrase after 2-3 seconds or punctuation
        duration = word['end'] - current_start
        if duration >= 2.0 or word['text'].endswith(('.', '!', '?')):
            phrases.append({
                'start': current_start,
                'end': word['end'],
                'text': ' '.join(current_phrase)
            })
            current_phrase = []
            current_start = None

    return phrases
```

**FFmpeg Burn-in:**
```bash
ffmpeg -i full_video.mp4 \
  -vf "ass=subtitles.ass:force_style='FontName=Montserrat-Bold,FontSize=48,PrimaryColour=&HFFFFFF&,OutlineColour=&H000000&,Outline=3'" \
  output.mp4
```

**Implementation:** New script `scripts/6_add_subtitles.py`
- Dispatcher that chooses engine based on `--engine` parameter
- Handles subtitle format conversion
- Applies appropriate styling

### 4. Multi-Video Upload Strategy

**Three separate uploads** with format-specific metadata and cross-linking

#### Full Horizontal Video (Regular YouTube Video)

```json
{
  "title": "{Topic} - Full Educational Song",
  "description": "Learn about {topic} through music! Full version.\n\n{educational_description}\n\nWatch the Shorts versions:\n- Musical Hook: {hook_link}\n- Educational Highlight: {edu_link}",
  "category": "Education",
  "tags": ["{topic}", "educational music", "science song", "learn {subject}"],
  "privacy": "public",
  "made_for_kids": true
}
```

**NOT marked as Short** - Regular video format for watch time

#### Short #1: Musical Hook (Vertical)

```json
{
  "title": "{Catchy hook phrase} #Shorts",
  "description": "{Topic} 🎵\n\nWatch the full version: {full_link}\n\n#shorts #education #{subject}",
  "category": "Education",
  "tags": ["{topic}", "shorts", "viral education"],
  "privacy": "public",
  "made_for_kids": true
}
```

**Marked as Short** - Vertical aspect ratio + #Shorts tag

#### Short #2: Educational Peak (Vertical)

```json
{
  "title": "{Educational key concept} #Shorts",
  "description": "{Topic} explained! 📚\n\nWatch the full version: {full_link}\n\n#shorts #learning #{subject}",
  "category": "Education",
  "tags": ["{topic}", "educational shorts", "learning"],
  "privacy": "public",
  "made_for_kids": true
}
```

**Marked as Short** - Different optimization for educational discovery

#### Cross-Linking Strategy

**After all uploads complete:**
1. Collect all three video IDs
2. Update descriptions with links to other versions
3. Create YouTube playlist containing all three
4. Send notification with all three links

**Implementation:**
- Enhanced `upload_to_youtube.sh` with `--type` parameter
- New `scripts/7_crosslink_videos.py` for post-upload linking

### 5. Configuration Schema

**Enhanced `config/config.json`:**

```json
{
  "suno_api": {
    "base_url": "https://api.sunoapi.org",
    "api_key": "...",
    "model": "V5"
  },
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
  "media_sources": {
    "pexels_api_key": "...",
    "pixabay_api_key": "...",
    "orientation_preference": {
      "full_video": "landscape",
      "shorts": "portrait"
    }
  },
  "pipeline_settings": {
    "express_mode": false,
    "parallel_processing": true,
    "max_media_items": 20,
    "min_media_items": 12
  }
}
```

### 6. Updated Pipeline Flow

**Modified `pipeline.sh`:**

```bash
#!/bin/bash
# Stage 1: Generate full-length song
./scripts/1_generate_song.py
# Output: song.mp3, lyrics.json with word timestamps

# Stage 2: Analyze segments for extraction
./scripts/3_analyze_segments.py
# Output: segments.json with time ranges

# Stage 3: Fetch media (parallel execution)
./scripts/2_fetch_media.py --aspect=landscape --segment=full &
./scripts/2_fetch_media.py --aspect=portrait --segment=hook &
./scripts/2_fetch_media.py --aspect=portrait --segment=educational &
wait

# Stage 4: Assemble videos (parallel execution)
./scripts/4_assemble_video.py --format=full &
./scripts/4_assemble_video.py --format=short_hook &
./scripts/4_assemble_video.py --format=short_educational &
wait

# Stage 5: Add subtitles (sequential - pycaps uses browser)
./scripts/6_add_subtitles.py --engine=ffmpeg --type=traditional --video=full
./scripts/6_add_subtitles.py --engine=pycaps --type=karaoke --video=short_hook
./scripts/6_add_subtitles.py --engine=pycaps --type=karaoke --video=short_educational

# Stage 6: Upload all three
FULL_ID=$(./upload_to_youtube.sh --type=full)
HOOK_ID=$(./upload_to_youtube.sh --type=short_hook)
EDU_ID=$(./upload_to_youtube.sh --type=short_educational)

# Stage 7: Cross-link videos
./scripts/7_crosslink_videos.py "$FULL_ID" "$HOOK_ID" "$EDU_ID"
```

### 7. Output Directory Structure

```
outputs/runs/YYYYMMDD_HHMMSS/
├── song.mp3                   # Full-length Suno song (2-4min)
├── lyrics.json                # Word-level timestamps
├── segments.json              # Extracted time ranges
├── media/
│   ├── full/                  # Horizontal 16:9 clips
│   │   ├── shot_01.mp4
│   │   ├── shot_02.mp4
│   │   └── ...
│   ├── hook/                  # Vertical 9:16 clips for hook
│   │   ├── shot_01.mp4
│   │   └── ...
│   └── educational/           # Vertical 9:16 clips for edu peak
│       ├── shot_01.mp4
│       └── ...
├── full_video.mp4             # Horizontal with traditional subs
├── short_hook.mp4             # Vertical with karaoke subs
├── short_educational.mp4      # Vertical with karaoke subs
├── subtitles/
│   ├── full_traditional.srt
│   ├── hook_karaoke.srt
│   └── educational_karaoke.srt
└── upload_results.json        # All three video IDs + playlist
```

## Implementation Plan

### New Scripts Required

1. **`scripts/3_analyze_segments.py`**
   - Parse Suno lyrics for repeated patterns (chorus detection)
   - Call Claude CLI for educational peak analysis
   - Generate `segments.json`

2. **`scripts/6_add_subtitles.py`**
   - Unified subtitle dispatcher
   - FFmpeg integration for traditional subtitles
   - pycaps integration for karaoke subtitles
   - Subtitle format conversion utilities

3. **`scripts/7_crosslink_videos.py`**
   - Post-upload cross-linking
   - YouTube API description updates
   - Playlist creation

4. **`templates/shorts_karaoke.css`**
   - pycaps CSS template with bold font and animations

### Enhanced Scripts

1. **`scripts/1_generate_song.py`**
   - Remove duration limit (use full song)
   - Ensure word-level timestamps in output

2. **`scripts/2_fetch_media.py`**
   - Add `--aspect-ratio` parameter
   - Add `--segment` parameter for time-based fetching
   - Add orientation filtering to API calls
   - Implement smart cropping fallbacks

3. **`scripts/4_assemble_video.py`**
   - Add `--format` parameter
   - Support both aspect ratios
   - Load correct media directories

4. **`upload_to_youtube.sh`**
   - Add `--type` parameter for video format
   - Load format-specific metadata templates
   - Return video ID for cross-linking

5. **`pipeline.sh`**
   - Orchestrate 3-video workflow
   - Add parallel processing support
   - Handle segment-based execution

### New Dependencies

```bash
# Python packages
pip install "git+https://github.com/francozanardi/pycaps.git#egg=pycaps[all]"

# System dependencies
playwright install chromium
```

### Configuration Updates

- Add `video_formats` section to `config/config.json`
- Add `subtitle_settings` section
- Update `media_sources` with orientation preferences

## Integration with Existing Automation

**No changes needed to daily automation!**

The existing `automation/daily_pipeline.sh` continues to work:
- Still calls `./pipeline.sh --express`
- Pipeline now automatically produces all three videos
- Upload script handles all three uploads
- Notification includes all three video links

## Success Criteria

- ✅ Three videos generated from one song
- ✅ Full video uses complete song length (2-4 minutes)
- ✅ Shorts extract most engaging 30-60s segments
- ✅ Horizontal video uses 16:9 landscape media
- ✅ Vertical shorts use 9:16 portrait media
- ✅ Karaoke subtitles on shorts (word-by-word highlighting)
- ✅ Traditional subtitles on full video (phrase-level)
- ✅ All three uploaded with cross-links
- ✅ Daily automation remains functional
- ✅ Weekly optimizer can analyze all three video types

## Risk Mitigation

**Performance:**
- pycaps may be slow (browser rendering)
- Mitigation: Run once daily, acceptable overhead
- Parallel processing where possible

**Complexity:**
- More moving parts = more failure points
- Mitigation: Each stage has fallbacks, validation, logging

**Dependencies:**
- pycaps is alpha stage, not on PyPI
- Mitigation: Pin to specific git commit, test thoroughly

## Future Enhancements

- A/B test different Short extraction strategies
- Add animated thumbnails for Shorts
- Support custom segment selection via config
- Add analytics tracking per format type
- Optimize segment selection based on past performance data
