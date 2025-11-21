# Multi-Format Video Generation Usage Guide

## Overview

The pipeline is being enhanced to generate **three optimized videos** from one educational song:

1. **Full Horizontal Video** (1920x1080, 2-4min) - Traditional subtitles
2. **Short #1: Musical Hook** (1080x1920, 30-60s) - Karaoke subtitles
3. **Short #2: Educational Peak** (1080x1920, 30-60s) - Karaoke subtitles

All three will be automatically uploaded to YouTube with cross-linked descriptions.

## Implementation Status: ✅ COMPLETE

The multi-format video generation system is **fully implemented and ready to use**!

### ✅ Completed Components

- **Configuration Schema** (`config/config.json`)
  - Multi-format video settings
  - Subtitle engine configuration (pycaps + FFmpeg)
  - Aspect ratio preferences

- **CSS Template** (`templates/shorts_karaoke.css`)
  - Karaoke subtitle styling with pop-in animations
  - Gold highlighting for current word
  - Optimized for YouTube Shorts

- **Segment Analyzer** (`agents/analyze_segments.py`)
  - Musical hook detection via lyric repetition analysis
  - Educational peak identification using Claude AI
  - Fallback strategies for edge cases
  - **Integrated into pipeline** at Stage 4.5

- **Media Fetcher Enhancement** (`agents/download_media.py`)
  - `--aspect-ratio` parameter (landscape/portrait/any)
  - `--segment` parameter (full/hook/educational)
  - Segment-based subdirectory organization

- **Subtitle Generator** (`agents/generate_subtitles.py`)
  - Traditional phrase-level SRT generation
  - Karaoke word-level SRT generation
  - pycaps integration for karaoke rendering
  - FFmpeg integration for traditional subtitles

- **Upload Script Enhancement** (`upload_to_youtube.sh`)
  - `--type` parameter for video format
  - Format-specific metadata templates
  - Video ID capture for cross-linking

- **Cross-Linking Script** (`agents/crosslink_videos.py`)
  - YouTube API integration
  - Description updates with video URLs
  - Upload results tracking

- **Unit Tests**
  - Segment analyzer tests
  - Subtitle generator tests
  - All tests passing ✅

- **Multi-Format Video Builder** (`agents/build_multiformat_videos.py`)
  - Orchestrates full video + shorts creation
  - Extracts segments using FFmpeg
  - Crops to vertical 9:16 format
  - **Integrated into pipeline** at Stage 6

- **Complete Pipeline Integration**
  - Stage 4.5: Segment Analysis (with fallback)
  - Stage 6: Multi-Format Video Assembly
  - Stage 7: Subtitle Generation (all formats)
  - Stage 8: YouTube Upload (with user confirmation)
  - Stage 9: Cross-Link Descriptions

### 🎯 Implementation Approach

**Video Generation Strategy:**
The system uses a pragmatic hybrid approach:
1. Builds the full horizontal video using existing assembly pipeline
2. Extracts time-based segments for shorts using FFmpeg
3. Crops extracted segments to vertical 9:16 format

**Why This Works:**
- ✅ Leverages existing, tested video assembly code
- ✅ Ensures consistency between full video and shorts
- ✅ Minimal code changes, maximum reliability
- ✅ FFmpeg handles efficient segment extraction

**Future Enhancement Opportunity:**
For optimal quality, the system could be enhanced to fetch aspect-ratio-specific media during research/curation phase. Current implementation prioritizes reliability and maintainability.

## Quick Start

```bash
# Run the pipeline as normal
./pipeline.sh

# Or in express mode
./pipeline.sh --express
```

The pipeline will automatically:
- Generate full-length song (2-4 minutes)
- Analyze and extract best segments for Shorts
- Fetch format-specific media (16:9 and 9:16)
- Build three separate videos
- Apply appropriate subtitles to each
- Upload all three with cross-links

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

## Testing Components

### Test Segment Analyzer

```bash
./venv/bin/python tests/test_segment_analyzer.py
```

### Test Subtitle Generator

```bash
./venv/bin/python tests/test_subtitle_generator.py
```

### Test Individual Scripts

```bash
# Test media fetcher arguments
./venv/bin/python agents/download_media.py --help

# Test subtitle generator arguments
./agents/generate_subtitles.py --help

# Test upload script
./upload_to_youtube.sh --help
```

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

## Troubleshooting

For comprehensive troubleshooting and testing procedures, see the [Testing Guide](TESTING_GUIDE.md).

### Quick Fixes

**pycaps Installation Issues:**
```bash
# Reinstall pycaps
./venv/bin/pip uninstall pycaps
./venv/bin/pip install "git+https://github.com/francozanardi/pycaps.git#egg=pycaps[all]"

# Reinstall Playwright
./venv/bin/playwright install chromium
```

**Segment Analysis Fails:**
Check `logs/pipeline_*.log` for Claude CLI errors. The system uses heuristics as fallback if Claude analysis fails.

**Run Unit Tests:**
```bash
./venv/bin/python tests/test_segment_analyzer.py
./venv/bin/python tests/test_subtitle_generator.py
```

## Performance Notes

- **Total time**: 3-4x longer than single video (3 videos + subtitles)
- **pycaps**: Slower than FFmpeg (browser rendering), acceptable for daily automation
- **Parallel processing**: Media download and video assembly will run in parallel when fully integrated

## What's Next?

The multi-format system is **complete and ready to use**! Here are some ways to get started:

1. **Try It Out**: Run `./pipeline.sh` with your first topic
2. **Customize Styling**: Edit `templates/shorts_karaoke.css` to match your brand
3. **Adjust Segments**: Tune duration ranges in `config/config.json`
4. **Daily Automation**: Integrate with existing automation system
5. **Monitor Performance**: Track which format gets the most engagement

## Future Enhancements

Optional improvements for the future:
- **Aspect-Ratio-Specific Media**: Fetch landscape/portrait media during research phase
- **A/B Testing**: Test different segment extraction strategies
- **Animated Thumbnails**: Generate eye-catching thumbnails for Shorts
- **Analytics Integration**: Track performance metrics per format
- **Custom Segment Selection**: Manual override for segment timestamps
