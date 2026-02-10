# PRD: AI-Generated Singing Video Clips

## Overview

Add AI-generated video clips featuring realistic humans singing/lip-syncing to Suno audio, placed in topic-matched scientific environments. Three 8-second clips are generated per video and placed within the first 60 seconds of the full-length music video. Shorts (15s, 33s, 60s) pull from this same first-60-second segment rather than generating new clips.

## Goals

1. Increase engagement with realistic performer visuals that feel like a music video
2. Reinforce educational content through topic-matched environments (e.g., underwater for sonar, lab for chemistry)
3. Maintain cost-effectiveness at under $2 per video
4. Seamlessly integrate with existing stock footage workflow

## Requirements

### Functional Requirements

#### FR1: AI Video Generation
- Generate 3 video clips, each exactly 8 seconds long
- Use Kling AI API for generation (~$0.07-0.14/sec) + Kling LipSync (~$0.014/5-sec)
- Realistic human performer style (not cartoon/stylized)
- Full lyric synchronization - mouth movements match actual sung words
- Same performer (face/appearance) maintained across all 3 clips within a video

#### FR2: Topic-Matched Environments
- Claude AI analyzes the topic and generates environment prompts
- Examples:
  - Sonar topic → underwater cave, submarine interior, ocean depths
  - DNA replication → molecular biology lab, microscopic cellular view
  - Jet engines → aircraft hangar, cockpit, wind tunnel
  - Ball bearings → industrial factory, machine shop, racing pit
- Each of the 3 clips can have different but related environments

#### FR3: Performer Matching
- Match performer gender to Suno-generated singing voice
- Analyze Suno output metadata or audio characteristics to determine voice type
- Use consistent reference image for Kling Elements feature to maintain appearance

#### FR4: Clip Placement
- All 3 clips placed within first 60 seconds of full video
- Placement determined by song structure using `segments.json`:
  - Clip 1: At intro segment
  - Clip 2: At first verse start
  - Clip 3: At first chorus or bridge
- Intercut with existing stock footage (not replacing all footage)

#### FR5: Shorts Compatibility
- 15-second hook short: Pulls from first 60 seconds (includes AI clips)
- 33-second educational short: Pulls from first 60 seconds (includes AI clips)
- 60-second intro short: Uses full first 60 seconds (includes all 3 AI clips)
- No additional AI clip generation for shorts

#### FR6: Fallback Handling
- If AI clip generation fails, fall back to stock footage seamlessly
- Log failure reason for debugging
- Continue pipeline without blocking

### Non-Functional Requirements

#### NFR1: Cost
- Target: Under $2.50 per video for all 3 AI clips
- Kling AI generation (via fal.ai): $0.56 per 8-sec clip ($0.07/sec)
- Kling LipSync: $0.14 per 8-sec clip ($0.014/sec, rounded to 10s)
- Total per clip: $0.70
- **Total for 3 clips: $2.10**

Note: Pricing is identical between fal.ai and direct Kling API. fal.ai recommended for pay-as-you-go billing (no upfront package purchase required).

#### NFR2: Quality
- Resolution: 1080p minimum (matching existing video formats)
- Frame rate: 30 FPS (matching pipeline standard)
- Lip-sync accuracy: Word-level synchronization using Suno timestamps

#### NFR3: Performance
- Generation time: ~2-5 minutes per clip (acceptable for batch processing)
- Should not significantly extend overall pipeline runtime beyond 10-15 minutes

## Technical Design

### API Integration

**Primary API: Kling AI**
- Base URL: `https://api.klingai.com` (or via fal.ai: `https://fal.ai/models/fal-ai/kling-video`)
- Authentication: API key in `config/config.json`
- Endpoints:
  - Video generation: `/v1/generate`
  - LipSync: `/v1/lipsync` (or fal.ai endpoint)
  - Status polling: `/v1/status/{task_id}`

### New Files

```
agents/
├── generate_ai_clips.py          # Main AI clip generation agent
├── prompts/
│   └── environment_prompt.md     # Claude prompt for environment generation
config/
└── config.json                   # Add kling_api section
outputs/runs/{timestamp}/
├── ai_clips/
│   ├── clip_1.mp4
│   ├── clip_2.mp4
│   ├── clip_3.mp4
│   └── ai_clip_manifest.json     # Metadata for generated clips
```

### Configuration Schema

Add to `config/config.json`:

```json
{
  "kling_api": {
    "base_url": "https://api.klingai.com",
    "api_key": "YOUR_API_KEY",
    "model": "kling-v1",
    "lipsync_enabled": true
  },
  "ai_clips": {
    "enabled": true,
    "count": 3,
    "duration_seconds": 8,
    "placement_strategy": "song_structure",
    "placement_window_seconds": 60,
    "performer_style": "realistic",
    "environment_source": "claude_ai",
    "fallback_to_stock": true,
    "max_retries": 2
  }
}
```

### Pipeline Integration

Insert new stage between Stage 4 (Segment Analysis) and Stage 5 (Media Curation):

```
Stage 4: Segment Analysis
    ↓
Stage 4.5: AI Clip Generation (NEW)
    - Read segments.json for placement timing
    - Read research.json for topic context
    - Read lyrics.json for lyric text
    - Read suno_output.json for audio file + timestamps
    - Call Claude for environment prompts
    - Generate 3 clips via Kling AI
    - Apply lip-sync via Kling LipSync
    - Save to outputs/runs/{timestamp}/ai_clips/
    ↓
Stage 5: Media Curation
    - Modified to incorporate AI clips at specified timestamps
```

### Data Flow

```
Input:
├── segments.json        → Clip placement timing (intro, verse, chorus)
├── research.json        → Topic, key_facts for environment context
├── lyrics.json          → Lyric text for the first 60 seconds
├── suno_output.json     → Audio file path + alignedWords timestamps
└── song.mp3             → Audio for lip-sync input

Processing:
1. Parse segments.json to determine 3 clip start times
2. Extract relevant lyrics for each 8-second window using alignedWords
3. Call Claude to generate 3 environment prompts based on topic
4. Determine performer gender from Suno metadata/audio
5. Generate base videos via Kling AI (3 parallel requests)
6. Apply lip-sync using song.mp3 audio slices
7. Download and save clips

Output:
├── ai_clips/clip_1.mp4  → 8-sec clip for intro
├── ai_clips/clip_2.mp4  → 8-sec clip for verse
├── ai_clips/clip_3.mp4  → 8-sec clip for chorus
└── ai_clip_manifest.json → Metadata (timing, prompts, success status)
```

### AI Clip Manifest Schema

```json
{
  "generated_at": "2026-02-09T10:30:00Z",
  "topic": "How sonar technology maps ocean floors",
  "performer_gender": "male",
  "total_cost_usd": 1.15,
  "clips": [
    {
      "id": 1,
      "file": "clip_1.mp4",
      "start_time": 0.0,
      "end_time": 8.0,
      "segment_type": "intro",
      "environment_prompt": "underwater cave with bioluminescent organisms, submarine control room visible through porthole, deep ocean blue lighting",
      "lyrics_excerpt": "Ever wonder how we see beneath the waves...",
      "generation_status": "success",
      "lipsync_status": "success",
      "cost_usd": 0.38
    },
    {
      "id": 2,
      "file": "clip_2.mp4",
      "start_time": 15.0,
      "end_time": 23.0,
      "segment_type": "verse",
      "environment_prompt": "inside a research submarine, sonar screens glowing green, ocean visible through window",
      "lyrics_excerpt": "Sound waves bouncing off the floor...",
      "generation_status": "success",
      "lipsync_status": "success",
      "cost_usd": 0.38
    },
    {
      "id": 3,
      "file": "clip_3.mp4",
      "start_time": 42.0,
      "end_time": 50.0,
      "segment_type": "chorus",
      "environment_prompt": "standing on submarine deck at night, stars above, ocean waves, dramatic lighting",
      "lyrics_excerpt": "Sonar shows the way, through the dark we play...",
      "generation_status": "success",
      "lipsync_status": "success",
      "cost_usd": 0.39
    }
  ]
}
```

### Media Plan Integration

Modify `media_plan_full.json` generation to reserve slots for AI clips:

```json
{
  "shots": [
    {
      "shot_number": 1,
      "source": "ai_generated",
      "file": "ai_clips/clip_1.mp4",
      "start_time": 0.0,
      "duration": 8.0,
      "type": "ai_clip"
    },
    {
      "shot_number": 2,
      "source": "stock",
      "file": "media/shot_01.mp4",
      "start_time": 8.0,
      "duration": 7.0,
      "type": "stock_footage"
    },
    ...
  ]
}
```

## Environment Prompt Generation

### Claude Prompt Template

```markdown
You are generating environment descriptions for AI video generation.

Topic: {topic}
Key Facts: {key_facts}
Clip Number: {clip_number} of 3
Segment Type: {segment_type} (intro/verse/chorus)

Generate a vivid, cinematic environment description for a music video scene.
The performer will be singing in this environment.

Requirements:
- Must relate to the educational topic
- Cinematic and visually striking
- Appropriate for a realistic human performer
- 2-3 sentences maximum
- Include lighting description
- Include specific visual elements

Example for "How sonar technology maps ocean floors":
- Clip 1 (intro): "Inside a dimly lit submarine control room, green sonar screens casting an eerie glow on the performer's face, ocean pressure visible through reinforced portholes"
- Clip 2 (verse): "Standing on a research vessel deck at sunset, hydrophone equipment visible, calm ocean stretching to horizon with research buoys"
- Clip 3 (chorus): "Underwater scene with the performer in diving gear, bioluminescent creatures floating past, ancient shipwreck visible in background"

Now generate environment for clip {clip_number}:
```

## Error Handling

### Failure Scenarios

| Scenario | Handling |
|----------|----------|
| Kling API timeout | Retry up to 2 times with exponential backoff |
| Kling API rate limit | Wait and retry, log warning |
| LipSync fails | Use base video without lip-sync, log warning |
| All 3 clips fail | Fall back to stock footage, log error |
| Partial failure (1-2 clips) | Use successful clips + stock for failed slots |
| Invalid audio format | Convert to supported format, retry |

### Logging

```python
# Log levels
INFO: "Generating AI clip 1/3 for topic: {topic}"
INFO: "Environment prompt: {prompt}"
INFO: "Kling generation complete: {task_id}"
WARNING: "LipSync failed for clip 2, using base video"
ERROR: "All AI clips failed, falling back to stock footage"
```

## Testing Plan

### Unit Tests
- Environment prompt generation with various topics
- Clip timing calculation from segments.json
- Manifest JSON generation and validation

### Integration Tests
- Full pipeline run with AI clips enabled
- Fallback behavior when Kling API unavailable
- Media plan integration with mixed AI/stock clips

### Manual Validation
- Visual quality check of generated clips
- Lip-sync accuracy assessment
- Environment appropriateness for topic

## Rollout Plan

### Phase 1: Development
- Implement `generate_ai_clips.py` agent
- Add Kling API integration
- Create environment prompt template
- Unit tests

### Phase 2: Integration
- Integrate with pipeline.sh as Stage 4.5
- Modify media plan generation
- Modify video assembly to handle AI clips
- Integration tests

### Phase 3: Testing
- Run 5-10 test videos with AI clips enabled
- Evaluate quality, cost, and timing
- Gather feedback and iterate

### Phase 4: Production
- Enable by default in config
- Monitor costs and quality
- Document in README

## Success Metrics

| Metric | Target |
|--------|--------|
| Cost per video | < $2.00 |
| Generation success rate | > 90% |
| Lip-sync quality (subjective) | 7/10 or higher |
| Pipeline time increase | < 15 minutes |
| Viewer engagement (future) | +10% watch time |

## Open Questions

1. **Kling API Access**: Need to get fal.ai API key from https://fal.ai
2. **Character Consistency**: Kling Elements feature may require additional setup for face consistency
3. **Audio Slicing**: Confirmed - ffmpeg with libmp3lame encoder, 44100 Hz sample rate
4. **Voice Gender Detection**: Use Suno tags metadata (contains "male vocals" or "female vocals")

## Implementation Plan

**See separate implementation document:** [`docs/plans/2026-02-09-ai-video-clips.md`](plans/2026-02-09-ai-video-clips.md)

The implementation plan includes 11 detailed tasks with:
- Exact file paths and code
- TDD approach with tests first
- Step-by-step verification commands
- Commit checkpoints

### Files to Create/Modify

| File | Action |
|------|--------|
| `config/config.json` | Add `fal_api` and `ai_clips` sections |
| `agents/kling_api_client.py` | Create - fal.ai Kling API client |
| `agents/audio_utils.py` | Create - Audio slicing with ffmpeg |
| `agents/clip_placement.py` | Create - Song structure analysis |
| `agents/environment_generator.py` | Create - Claude prompt generation |
| `agents/generate_ai_clips.py` | Create - Main agent |
| `pipeline.sh` | Modify - Add Stage 4.5 |
| `agents/build_format_media_plan.py` | Modify - Integrate AI clips |

### Research Summary

**API Pricing Comparison (for 3x 8-sec clips):**

| Provider | Per-Second Rate | 8s Video | Lip-Sync (10s) | Per Clip | 3 Clips |
|----------|----------------|----------|----------------|----------|---------|
| Direct Kling API | $0.07/sec | $0.56 | $0.14 | $0.70 | **$2.10** |
| fal.ai | $0.07/sec | $0.56 | $0.14 | $0.70 | **$2.10** |

**Recommendation:** fal.ai (same pricing, pay-as-you-go, no upfront package required)

**API Alternatives:**

| API | Cost | Lip-Sync | Environments | Recommendation |
|-----|------|----------|--------------|----------------|
| Kling AI (fal.ai) | $2.10 | Excellent (native) | Good | **Selected** |
| HeyGen | $2.40-4.80 | Excellent | Limited | Backup option |
| Runway + Sync Labs | $2.40 | Good | Excellent | Higher quality alternative |
| Pika Labs | $1.20-2.40 | Good | Good | Limited API access |

### Current Pipeline Stages

1. Research
2. Lyrics Generation
3. Lyric-Based Media Search
4. Visual Ranking
5. Music Composition
6. Segment Analysis
7. **AI Clip Generation (NEW - Stage 4.5)**
8. Media Curation (modified to include AI clips)
9. Multi-Format Video Assembly
10. Subtitle Generation
11. Video Overlays
12. Video LLM Analysis
13. YouTube Upload
14. Cross-Link Videos
