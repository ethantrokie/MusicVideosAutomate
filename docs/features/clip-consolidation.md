# Clip Consolidation Feature

## Overview

The clip consolidation feature merges consecutive phrase groups into longer video segments (5-15 seconds each) to reduce jarring cuts while maintaining semantic video matching and phrase-level subtitle timing.

## Benefits

- **Smoother Visual Experience**: Fewer video cuts (reduces 80+ clips to 10-15)
- **Semantic Matching**: Videos remain relevant to lyrical content
- **Independent Subtitles**: Phrase-level timing preserved regardless of video clip duration
- **Configurable**: Control via config or command-line flag

## How It Works

### 1. Phrase Group Generation
The AI generates semantic phrase groups from lyrics with topic keywords:
```json
{
  "group_id": 1,
  "topic": "chlorophyll basics",
  "key_terms": ["chlorophyll", "green", "molecule"],
  "start_time": 0.0,
  "end_time": 2.5,
  "duration": 2.5
}
```

### 2. Consolidation Algorithm
Using Jaccard similarity, consecutive groups are merged based on:
- **Semantic coherence**: Key term overlap (configurable threshold: 0.7)
- **Duration constraints**:
  - Target: 8s (ideal clip length)
  - Minimum: 4s (must merge if under)
  - Maximum: 15s (never exceed)

### 3. Video Matching
Each consolidated clip gets one video based on combined topics:
```json
{
  "clip_id": 1,
  "start_time": 0.0,
  "end_time": 10.5,
  "duration": 10.5,
  "topics": ["chlorophyll basics", "molecular structure", "photosynthesis"],
  "phrase_groups": [...],  // Preserved for subtitle timing
  "video_url": "beach-palm-trees.mp4"
}
```

### 4. Subtitle Independence
Subtitles are generated from word-level timestamps (`lyrics_aligned.json`), not video clip boundaries. A single 10s video clip can display 3-4 different subtitle phrases.

## Configuration

### Config File (`config/config.json`)
```json
{
  "lyric_sync": {
    "clip_consolidation": {
      "enabled": true,
      "target_clip_duration": 8.0,
      "min_clip_duration": 4.0,
      "max_clip_duration": 15.0,
      "semantic_coherence_threshold": 0.7
    }
  }
}
```

### Command-Line Override
```bash
# Disable consolidation for this run
./venv/bin/python3 agents/5_assemble_video.py --no-consolidation

# Use config setting (default)
./venv/bin/python3 agents/5_assemble_video.py
```

## Example

**Input**: 86 phrase groups (avg 1-2s each)

**Without Consolidation**:
- 86 video clips
- Rapid cuts every 1-2 seconds
- Precise semantic matching per phrase

**With Consolidation** (default):
- 12 video clips (avg 5-8s each)
- Smoother visual flow
- Broader semantic matching (multiple related topics per video)
- Same precise subtitle timing

```
Clip 1 (0s-10s): Beach scene with palm trees
  Subtitle 1 (0s-3s): "Leaves are green as can be"
  Subtitle 2 (3s-6s): "Chlorophyll's the molecule"
  Subtitle 3 (6s-10s): "That helps them capture energy"

(Video doesn't cut, but subtitles animate independently)
```

## Testing

### Unit Tests
```bash
./venv/bin/python3 tests/test_clip_consolidation.py
```

Verifies:
- Merging logic with semantic similarity
- Duration constraint enforcement
- Phrase metadata preservation

### Integration Testing
Run full pipeline and verify:
```bash
./pipeline.sh --express

# Check consolidation occurred
jq '.total_shots, .pacing' outputs/runs/*/synchronized_plan.json
```

Expected:
- `pacing`: "consolidated"
- `total_shots`: 10-15 (vs 80+ without)

## Architecture

See [`docs/architecture/subtitle-clip-independence.md`](../architecture/subtitle-clip-independence.md) for details on how subtitles remain independent of video clip timing.

## Future Enhancements

- **Smart Breaks**: Detect natural breaks (chorus/verse boundaries) to avoid mid-section cuts
- **Transition Hints**: Add crossfade hints based on topic similarity scores
- **Adaptive Thresholds**: Adjust coherence threshold based on genre/content density
