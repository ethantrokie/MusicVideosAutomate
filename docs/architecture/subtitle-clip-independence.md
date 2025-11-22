# Subtitle and Clip Timing Independence

## Overview

The subtitle system operates independently from video clip timing, allowing phrase-level subtitle animation even when video clips span multiple phrases.

## Data Flow

1. **Lyric Timestamps** (`lyrics_aligned.json`)
   - Word-level timestamps from Suno API
   - Filtered to actual audio duration
   - Source of truth for subtitle timing

2. **Phrase Groups** (`phrase_groups.json`)
   - Grouped words by semantic topic
   - Used for video semantic matching
   - NOT used directly for subtitle timing

3. **Video Clips** (`synchronized_plan.json`)
   - Consolidated phrase groups (5-15s each)
   - Used for video assembly and cuts
   - Each clip contains `phrase_groups` metadata

4. **Subtitle Files** (`.srt`, `.ass`)
   - Generated from `lyrics_aligned.json` word timestamps
   - Phrase-level or word-level depending on style
   - Independent of video clip boundaries

## Example

A 10-second video clip might show a beach scene while 3 different subtitle phrases appear:

```
Clip 1 (0s-10s): Beach with palm trees
  Subtitle 1 (0s-3s): "Leaves are green as can be"
  Subtitle 2 (3s-6s): "Chlorophyll's the molecule"
  Subtitle 3 (6s-10s): "That helps them capture energy"
```

The video doesn't cut, but subtitles change every 3 seconds.

## Benefits

- Smoother visual experience (fewer jarring cuts)
- Precise lyric synchronization (word/phrase level)
- Semantic visual matching (relevant videos for topic)
