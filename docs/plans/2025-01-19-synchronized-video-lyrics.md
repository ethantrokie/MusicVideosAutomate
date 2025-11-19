# Synchronized Video-Lyric System Design

**Date**: 2025-01-19
**Status**: Approved
**Author**: Claude Code

## Problem Statement

Currently, videos switch at fixed intervals determined by the media curator, without synchronization to the actual sung lyrics. This causes two issues:

1. **Timing misalignment**: Videos don't switch when key scientific terms are actually sung
2. **Semantic mismatch**: Videos sometimes don't match the specific concepts being discussed at that moment

**Goal**: Synchronize video switching to word-level lyric timestamps and improve semantic matching between visuals and sung content.

## Solution Overview

Enhance the video assembly stage to:
1. Fetch word-level timestamps from Suno API
2. Use AI to group lyric phrases by semantic topic
3. Apply CLIP + keyword boosting for better video-to-phrase matching
4. Align video shots to natural phrase boundaries while keeping related concepts together

## Architecture

### System Flow

```
┌─────────────────────────────────────────────────────────────┐
│ Video Assembly (agents/5_assemble_video.py) - ENHANCED     │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  1. Fetch Timestamps                                        │
│     └─> Call Suno API for word-level timestamps            │
│     └─> Save to lyrics_aligned.json                        │
│                                                             │
│  2. AI Phrase Grouping                                      │
│     └─> Extract key scientific terms (AI)                  │
│     └─> Group phrases by semantic topic (AI)               │
│     └─> Save to phrase_groups.json                         │
│                                                             │
│  3. Enhanced Semantic Matching                              │
│     └─> CLIP embeddings for videos & phrase groups         │
│     └─> Keyword boost (2x) for exact term matches          │
│     └─> Assign best video to each phrase group             │
│                                                             │
│  4. Synchronized Assembly                                   │
│     └─> Align shots to phrase boundaries                   │
│     └─> Keep same video for semantically grouped phrases   │
│     └─> Output synchronized_plan.json + final_video.mp4    │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### Data Flow

**Inputs** (existing):
- `outputs/{run}/lyrics.json` - Plain lyrics from composer
- `outputs/{run}/song.mp3` - Generated music
- `outputs/{run}/music_metadata.json` - Contains task_id and audio_id
- `outputs/{run}/approved_media.json` - Curator's shot list

**New Intermediate Files**:
- `outputs/{run}/lyrics_aligned.json` - Word timestamps from Suno
- `outputs/{run}/phrase_groups.json` - AI semantic groupings
- `outputs/{run}/synchronized_plan.json` - Final timed shot list

**Output** (existing):
- `outputs/{run}/final_video.mp4` - Final synchronized video

## Component Design

### 1. Timestamp Fetching

**Module**: `agents/suno_lyrics_sync.py`

```python
class SunoLyricsSync:
    def fetch_aligned_lyrics(self, task_id: str, audio_id: str) -> dict:
        """
        Fetch word-level timestamps from Suno API.

        Returns:
        {
          "alignedWords": [
            {
              "word": "[Verse] Look",
              "startS": 0.5,
              "endS": 0.8,
              "success": true
            },
            ...
          ]
        }
        """
```

**API Details**:
- Endpoint: `https://api.sunoapi.org/api/v1/generate/get-timestamped-lyrics`
- Method: POST
- Auth: Bearer token from environment variable `SUNO_API_KEY`
- Request: `{"taskId": "...", "audioId": "..."}`

**Error Handling**:
- If API fails, fall back to curator's timing (graceful degradation)
- Retry up to 3 times with exponential backoff
- Log warning and continue with original media_plan.json

### 2. AI Phrase Grouping

**Module**: `agents/phrase_grouper.py`

```python
class PhraseGrouper:
    def extract_key_terms(self, lyrics: str, key_facts: list) -> list[str]:
        """
        Use AI to extract key scientific terms from lyrics.

        Prompt strategy:
        - Provide lyrics and key_facts from research
        - Ask to identify: enzyme names, molecule names,
          processes, organelles, key concepts
        - Return structured list
        """

    def group_phrases_by_topic(self,
                                aligned_words: list,
                                key_terms: list) -> list[dict]:
        """
        Use AI to group consecutive phrases by semantic topic.

        Returns:
        [
          {
            "group_id": 1,
            "topic": "chlorophyll and light absorption",
            "phrases": [
              {"text": "Look at a leaf...", "startS": 0.5, "endS": 3.2},
              {"text": "It's a tiny green...", "startS": 3.2, "endS": 5.8}
            ],
            "key_terms": ["chlorophyll", "leaf"],
            "start_time": 0.5,
            "end_time": 5.8,
            "duration": 5.3
          },
          ...
        ]
        """
```

**Phrase Boundary Detection**:
- Use timestamp gaps > 0.3 seconds as phrase boundaries
- Merge words until natural pause detected
- AI validates phrase completeness

**Semantic Grouping Logic**:
- AI prompt: "Group these phrases by the scientific concept they discuss. Keep groups as large as possible while maintaining topic coherence."
- Input: List of phrases with text and timestamps
- Output: Grouped phrases with topic labels and key terms

### 3. Enhanced Semantic Matching

**Module**: `agents/semantic_matcher.py`

```python
class SemanticMatcher:
    def __init__(self):
        self.clip_model = SentenceTransformer('clip-ViT-B-32')

    def match_videos_to_groups(self,
                                phrase_groups: list[dict],
                                available_media: list[dict]) -> list[dict]:
        """
        Assign best video to each phrase group using CLIP + keyword boosting.

        Algorithm:
        1. Generate CLIP embeddings for:
           - Each phrase group's topic + combined phrase text
           - Each video's description

        2. Calculate similarity scores:
           base_score = cosine_similarity(group_emb, video_emb)

        3. Apply keyword boost:
           for each key_term in group.key_terms:
               if key_term in video.description.lower():
                   base_score *= 2.0

        4. For each group, assign video with highest score

        5. Handle video reuse:
           - Allow same video for consecutive groups with same topic
           - Prefer diversity: penalize recently used videos (-0.1 per recent use)

        Returns: phrase_groups with assigned video_url and match_score
        """
```

**Diversity Handling**:
- Track last 3 videos used
- Apply small penalty (-0.1) to recently used videos
- Exception: If same topic continues, allow video reuse

### 4. Synchronized Video Assembly

**Module**: Enhanced `agents/5_assemble_video.py`

```python
def assemble_synchronized_video(
    phrase_groups: list[dict],
    audio_path: str,
    video_settings: dict
) -> str:
    """
    Create final video with phrase-synchronized switching.

    Process:
    1. For each phrase group:
       - Load assigned video
       - Trim/loop to match group duration (start_time to end_time)
       - Apply transitions (0.3s crossfade at boundaries)

    2. Concatenate all clips in sequence

    3. Attach audio (song.mp3)

    4. Render final video

    Transition Logic:
    - Between different videos: 0.3s crossfade
    - Same video continuing: no transition (seamless)
    """
```

**Timing Precision**:
- Use timestamps directly from Suno (accurate to 0.01s)
- Align clip start/end exactly to phrase boundaries
- No rounding or fixed intervals

## Edge Cases & Error Handling

### 1. Suno API Unavailable
- Fallback: Use curator's media_plan.json as-is
- Log warning: "Timestamp sync unavailable, using curator timing"
- Video still assembles successfully

### 2. Insufficient Videos for All Groups
- Reuse videos with best semantic match
- Prefer spreading reuse across non-consecutive groups
- Log info about video reuse statistics

### 3. Very Short Phrases (< 1.5 seconds)
- Merge with next phrase if same topic
- Minimum shot duration: 1.5 seconds for visual comprehension

### 4. API Rate Limits
- Implement exponential backoff (1s, 2s, 4s)
- Cache aligned lyrics by audio_id
- Only re-fetch if audio_id changed

### 5. Phrase Grouping Failures
- Fallback: Treat each phrase as separate group
- Continue with individual phrase matching

## Configuration

**New Environment Variables**:
- `SUNO_API_KEY` - API key for Suno (required for sync)
- `ENABLE_LYRIC_SYNC` - Boolean flag (default: true)

**New Config Settings** (config/config.json):
```json
{
  "lyric_sync": {
    "enabled": true,
    "min_phrase_duration": 1.5,
    "max_phrase_duration": 10.0,
    "phrase_gap_threshold": 0.3,
    "keyword_boost_multiplier": 2.0,
    "diversity_penalty": 0.1,
    "transition_duration": 0.3
  }
}
```

## Testing Strategy

### Unit Tests
- `test_suno_api.py`: Mock API responses, test error handling
- `test_phrase_grouper.py`: Test phrase boundary detection
- `test_semantic_matcher.py`: Test CLIP scoring and keyword boosting

### Integration Tests
- Use existing run outputs (20251117_185735)
- Compare synchronized vs original timing
- Verify video switches align with timestamps

### Manual Testing
1. Run full pipeline with sample topic
2. Verify keywords appear when relevant videos show
3. Check transition smoothness
4. Validate total duration matches song length

## Implementation Plan

### Task 1: Suno API Integration
- Create `agents/suno_lyrics_sync.py`
- Implement `fetch_aligned_lyrics()` with retry logic
- Add error handling and caching
- Test with real audio_id from existing run

### Task 2: Phrase Grouping System
- Create `agents/phrase_grouper.py`
- Implement AI prompt for key term extraction
- Implement AI prompt for semantic grouping
- Parse aligned words into phrase boundaries
- Test grouping quality with sample lyrics

### Task 3: Enhanced Semantic Matching
- Create `agents/semantic_matcher.py`
- Implement CLIP embedding generation
- Implement keyword boosting algorithm
- Add diversity penalty logic
- Test matching accuracy with existing media

### Task 4: Video Assembly Enhancement
- Modify `agents/5_assemble_video.py`
- Integrate all new modules
- Implement synchronized clip timing
- Add fallback to original behavior
- Handle edge cases

### Task 5: Configuration & Setup
- Update `config/config.json` with lyric_sync settings
- Add `SUNO_API_KEY` to setup instructions
- Update README with new feature documentation

### Task 6: Testing & Validation
- Create test suite for new modules
- Run integration test with existing data
- Validate synchronized output quality
- Document any tuning needed

### Task 7: Documentation
- Update README with synchronized feature
- Add troubleshooting guide
- Document configuration options
- Add example output comparison

## Success Metrics

- **Timing Accuracy**: Videos switch within 0.1s of target phrase boundary
- **Semantic Relevance**: Key terms have matching video >90% of time
- **Smooth Transitions**: No jarring cuts mid-phrase
- **Robustness**: Graceful fallback when API unavailable
- **Performance**: Assembly time increases < 30% vs original

## Future Enhancements

1. **Visual Effects**: Add text overlays showing key terms as they're sung
2. **Multi-language**: Support lyrics in other languages
3. **Custom Timing**: Allow manual timing adjustments via UI
4. **Analytics**: Track which videos get most reuse, optimize library
5. **Live Preview**: Show synchronized preview before final render
