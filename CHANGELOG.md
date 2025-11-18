# Changelog

## 2024-11-16 - Major Updates

### Video Duration Changed: 30s → 60s

All components updated to support 1-minute educational videos:

#### Configuration
- `config/config.json`: `duration: 30` → `duration: 60`

#### Lyricist Agent
- Target: 60 seconds when sung (16-24 lines)
- Structure: Full verse-chorus-verse-chorus format
- Allows for fuller instrumentation and more complete songs
- Example now shows proper 60-second song structure

#### Researcher Agent
- Extract 8-12 key facts (was 5-7)
- Each fact explained in ~5-8 seconds (was ~5 seconds)

#### Curator Agent
- Total duration: 60 seconds (was 30)
- Select 10-15 media items (was 6-10)
- Typical shot: 4-6 seconds (was 3-5)
- Fast cuts: 3-4 seconds (was 2-3)
- Slow shots: 6-8 seconds (was 5-7)

#### Music Composer
- Audio trimming: 65 seconds (was 35 seconds)
- Calculation: video duration (60s) + 5s outro fade
- Uses config value dynamically

### Visual Ranking System Added

New workflow for analyzing and ranking media using Claude Code's vision:

#### New Files
- `agents/visual_ranker.py` - Downloads ~30 media candidates
- `README_VISUAL_RANKING.md` - Complete workflow guide
- `VISUAL_ANALYSIS_INSTRUCTIONS.md` - Quick reference

#### Enhanced Components
- **Researcher**: Now requests 30 media items (~10 per source)
- **Curator**: Checks for `visual_rankings.json` and prioritizes top-ranked media
- **Stock Photo API**: Added support for Giphy

#### Visual Analysis Features
- Download 30 candidates (10 from Pexels, Pixabay, Giphy)
- Claude Code analyzes each for:
  - Educational value (1-10)
  - Visual clarity (1-10)
  - Engagement (1-10)
  - Scientific accuracy (1-10)
  - Relevance (1-10)
- Ranks all media and outputs top 10 for video
- Curator uses rankings when available

### Giphy Integration

- Added Giphy API support for animated science GIFs
- API key configuration in `config/config.json`
- URL resolution for Giphy URLs in `stock_photo_api.py`
- Researcher prompt updated with Giphy search strategy

#### Giphy Features
- Supports both GIF and MP4 formats
- Extracts GIF ID from various URL formats
- Uses Giphy API to get download URLs
- Prioritizes original quality, falls back to downsized_large

### Science-Focused Media

Updated researcher prompt to prioritize scientific imagery:
- Microscope views and lab equipment
- Diagrams and scientific illustrations
- Specific science terms (chloroplast, molecule, atom, DNA)
- Animated processes and visualizations
- Technical and educational content

### Bug Fixes

- Fixed Pillow 10+ compatibility (ANTIALIAS → LANCZOS)
- Fixed moviepy 1.0.3 ImageClip usage
- Fixed fade effects in video assembly
- Added pydub for audio trimming
- Updated all duration references across prompts

### Audio Handling

- Suno API generates full-length songs (no duration parameter exists)
- Audio is trimmed after download to match video length
- Uses pydub for MP3 trimming
- Graceful fallback if pydub not available
- Dynamic calculation: `video_duration + 5s`

## Impact Summary

**Before:**
- 30-second videos with 8-12 lines of lyrics
- 6-10 media items from Pexels/Pixabay only
- No visual quality control
- Manual media selection

**After:**
- 60-second videos with 16-24 lines of lyrics
- 30 candidates → visually ranked → top 10-15 selected
- Pexels + Pixabay + Giphy support
- Claude Code vision-based quality control
- Science-focused, educationally accurate media
