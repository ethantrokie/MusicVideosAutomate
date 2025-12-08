# MusicVideosAutomate Pipeline Documentation

**Last Updated:** December 1, 2025

## Table of Contents
- [Overview](#overview)
- [Architecture](#architecture)
- [Pipeline Entry Points](#pipeline-entry-points)
- [Pipeline Stages](#pipeline-stages)
- [Data Flow](#data-flow)
- [Key Agents & Functions](#key-agents--functions)
- [Automation Layer](#automation-layer)
- [Multi-Format Video Architecture](#multi-format-video-architecture)
- [Resume & Recovery](#resume--recovery)
- [Known Issues & Considerations](#known-issues--considerations)

---

## Overview

The MusicVideosAutomate pipeline generates educational music videos from a topic description. It creates:
- **Full video** (16:9, ~180s) - comprehensive horizontal video
- **Hook short** (9:16, ~30s) - engaging vertical clip
- **Educational short** (9:16, ~30s) - teaching-focused vertical clip

The pipeline orchestrates AI agents (via Claude Code CLI), music generation (Suno API), visual ranking (CLIP), media curation, and video assembly (MoviePy).

---

## Architecture

### High-Level Flow
```
Input (topic) → Research → Visual Ranking → Lyrics → Music → Segments → Media Curation → Multi-Format Videos → Subtitles → Upload → Cross-link
```

### Key Design Principles
1. **Timestamped Runs**: Each pipeline run creates `outputs/runs/YYYYMMDD_HHMMSS/` with all artifacts
2. **Resume Support**: Can resume from any stage using `--resume` and `--start` flags
3. **Express Mode**: Auto-approves media for fully automated runs
4. **Format-Specific Media Plans**: Each video format gets its own optimized media plan
5. **Context Pruning**: Large research data is pruned before being passed to lyricist/curator to reduce token usage

### Directory Structure
```
agents/               # All pipeline agents (research, lyrics, video, etc.)
automation/           # Daily automation & topic generation
config/               # Configuration files (API keys, video settings)
input/                # Input file (idea.txt)
outputs/
  runs/
    YYYYMMDD_HHMMSS/  # Timestamped run directory
      research.json
      lyrics.json
      song.mp3
      segments.json
      media_plan_*.json
      full.mp4, short_hook.mp4, short_educational.mp4
  current -> runs/YYYYMMDD_HHMMSS/  # Symlink to latest run
logs/                 # Pipeline execution logs
```

---

## Pipeline Entry Points

### 1. Main Pipeline (`pipeline.sh`)
Primary entry point for video generation.

**Location**: `pipeline.sh`

**Usage**:
```bash
# New run
./pipeline.sh --express

# Resume from specific run at stage 6
./pipeline.sh --resume=20251201_094527 --start=6 --express

# Resume latest run
./pipeline.sh --resume --express
```

**Key Features**:
- Creates timestamped output directories
- Exports `OUTPUT_DIR` and `RUN_TIMESTAMP` environment variables
- Supports `--express` for automated runs (skips human approval)
- Supports `--start=N` to begin at specific stage
- Supports `--resume=DIR` to continue failed runs
- Logs all output to `logs/pipeline_TIMESTAMP.log`

**Implementation**: pipeline.sh:1-681

---

### 2. Daily Automation (`automation/daily_pipeline.sh`)
Automated daily video generation with topic generation and retry logic.

**Location**: `automation/daily_pipeline.sh`

**Features**:
- Generates new topic via `automation/topic_generator.py`
- Runs pipeline in express mode
- Retry logic: 1 initial attempt + 2 resume attempts
- Auto-detects resume stage based on completed artifacts
- Sends notifications on success/failure (if configured)
- Cross-links YouTube and TikTok videos

**Stage Detection Logic** (daily_pipeline.sh:31-100):
```bash
detect_resume_stage() {
  # Checks for completion markers in reverse order:
  # - upload_results.json → Stage 10 (complete)
  # - video_id_full.txt → Stage 9 (upload done, need cross-link)
  # - subtitles/*.srt → Stage 8 (videos built with subtitles)
  # - full.mp4 + shorts → Stage 7 (videos built, need subtitles)
  # - approved_media.json → Stage 6 (ready for video assembly)
  # - segments.json → Stage 5 (ready for media curation)
  # - song.mp3 → Stage 5 (ready for segment analysis)
  # - lyrics.json → Stage 4 (ready for music)
  # - visual_rankings.json → Stage 3 (ready for lyrics)
  # - research.json → Stage 2 (ready for visual ranking)
}
```

**Implementation**: automation/daily_pipeline.sh:1-240

---

## Pipeline Stages

### Stage 1: Research (agents/1_research.sh)

**Purpose**: Generate key facts and media suggestions for topic

**Agent**: `agents/1_research.sh`

**How It Works**:
1. Reads topic and tone from `input/idea.txt`
2. Substitutes variables into `agents/prompts/researcher_prompt.md`
3. Calls Claude Code CLI (Sonnet 4.5) with prompt
4. Claude generates `research.json` with:
   - `key_facts`: Educational concepts to cover
   - `media_suggestions`: Stock footage/images with search terms
   - `tone`: Video tone/style

**Output**: `$OUTPUT_DIR/research.json`

**Key Functions**:
- Uses prompt template substitution (`sed` with `{{TOPIC}}`, `{{TONE}}` placeholders)
- Validates JSON output before continuing

**Implementation**: agents/1_research.sh:1-67

---

### Stage 2: Visual Ranking (agents/3_rank_visuals.py)

**Purpose**: Rank media suggestions by visual diversity using CLIP embeddings

**Agent**: `agents/3_rank_visuals.py`

**How It Works**:
1. Loads `research.json` and enriches with thumbnail URLs
2. Downloads thumbnails in parallel (with caching to `$OUTPUT_DIR/thumbnails/`)
3. Generates CLIP embeddings for images and key facts
4. Applies MMR (Maximal Marginal Relevance) algorithm:
   - Lambda = 0.7 (70% relevance, 30% diversity)
   - For each fact, selects most relevant yet diverse media
5. Ranks all media by visual_score and diversity

**Output**: `$OUTPUT_DIR/visual_rankings.json`

**Key Classes**:
- `VisualRanker` (agents/3_rank_visuals.py:27-288):
  - `rank_media()`: Main ranking function
  - `_calculate_mmr_scores()`: MMR algorithm implementation
  - `_download_thumbnails_parallel()`: Parallel thumbnail fetching
  - `_encode_images/texts()`: CLIP embedding generation

**Implementation**: agents/3_rank_visuals.py:1-341

---

### Stage 3: Lyrics Generation (agents/2_lyrics.sh)

**Purpose**: Generate song lyrics based on educational content

**Agent**: `agents/2_lyrics.sh`

**Context Pruning**: Before lyrics generation, `agents/context_pruner.py lyricist` reduces research data size by:
- Keeping only top 15 media suggestions (ranked by visual_score)
- Preserving key_facts and tone
- Saves to `research_pruned_for_lyrics.json`

**How It Works**:
1. Reads pruned research data
2. Substitutes into `agents/prompts/lyricist_prompt.md`
3. Appends research JSON to prompt
4. Calls Claude Code CLI (Sonnet 4.5)
5. Claude generates `lyrics.json` with:
   - `lyrics`: Full song lyrics
   - `music_prompt`: Suno style description
   - `structure`: Song structure (verse/chorus/etc)
   - `estimated_duration_seconds`: Target duration

**Output**:
- `$OUTPUT_DIR/lyrics.json`
- `$OUTPUT_DIR/lyrics.txt` (extracted)
- `$OUTPUT_DIR/music_prompt.txt` (extracted)

**Implementation**: agents/2_lyrics.sh:1-65

---

### Stage 4: Music Composition (agents/3_compose.py)

**Purpose**: Generate music from lyrics using Suno API

**Agent**: `agents/3_compose.py`

**How It Works**:
1. Loads `lyrics.json`
2. Calls Suno API V5 with:
   - `prompt`: Lyrics (max 5000 chars)
   - `style`: Music style description (max 1000 chars)
   - `model`: "V5" (configurable)
   - `customMode`: true
3. Polls for completion (max 300s timeout)
4. Downloads audio to `song.mp3`
5. Fetches word-level timestamps from Suno API
6. Saves full response to `suno_output.json` with:
   - `alignedWords`: Word-level timestamps with `word`, `startS`, `endS`
   - `metadata`: Duration, title, model
   - `song`: Full Suno response

**Output**:
- `$OUTPUT_DIR/song.mp3`
- `$OUTPUT_DIR/music_metadata.json`
- `$OUTPUT_DIR/suno_output.json` (with word timestamps)

**Key Classes**:
- `SunoAPIClient` (agents/3_compose.py:24-149):
  - `generate_music()`: Initiate music generation
  - `wait_for_completion()`: Poll for completion
  - `download_audio()`: Download MP3
- `SunoLyricsSync` (agents/suno_lyrics_sync.py): Fetches word-level timestamps

**Implementation**: agents/3_compose.py:1-291

---

### Stage 4.5: Segment Analysis (agents/analyze_segments.py)

**Purpose**: Identify best segments for multi-format videos

**Agent**: `agents/analyze_segments.py`

**How It Works**:
1. Loads `suno_output.json` with word-level timestamps
2. Detects **musical hook** (30-60s):
   - Analyzes lyric repetition (finds chorus)
   - Identifies first complete repetition
   - Fallback: seconds 30-90 (typical hook placement)
3. Identifies **educational peak** (30-60s):
   - Uses Claude CLI (Haiku 4.5) to analyze lyrics
   - Finds segment with highest educational value
   - Looks for definitions, examples, cause-effect
   - Fallback: first 10-70s after intro
4. Creates full video segment (entire song)

**Output**: `$OUTPUT_DIR/segments.json`
```json
{
  "full": {"start": 0, "end": 180, "duration": 180, "rationale": "..."},
  "hook": {"start": 35, "end": 65, "duration": 30, "rationale": "..."},
  "educational": {"start": 15, "end": 45, "duration": 30, "rationale": "..."}
}
```

**Key Functions**:
- `detect_musical_hook()` (analyze_segments.py:36-134): Finds chorus via lyric repetition
- `analyze_educational_peak()` (analyze_segments.py:137-217): Uses Claude to identify educational segment

**Implementation**: agents/analyze_segments.py:1-273

---

### Stage 5: Media Curation (agents/4_curate_media.sh)

**Purpose**: Create shot list matching lyrics to media

**Agent**: `agents/4_curate_media.sh`

**Context Pruning**: Before curation, `agents/context_pruner.py curator` reduces research data.

**How It Works**:
1. Reads pruned research, lyrics, and visual rankings
2. Substitutes into `agents/prompts/curator_prompt.md`
3. Appends all data to prompt
4. Calls Claude Code CLI (Sonnet 4.5) with `--duration` parameter
5. Claude generates `media_plan.json` with:
   - `shot_list`: Array of shots with media_url, duration, rationale
   - `total_duration`: Planned video duration
   - `pacing`: Shot pacing strategy
6. Downloads all media via `agents/download_media.py`
   - Saves to `$OUTPUT_DIR/media/`
   - Creates `media_manifest.json` with download status

**Output**:
- `$OUTPUT_DIR/media_plan.json` (initial plan, for backwards compatibility)
- `$OUTPUT_DIR/media_manifest.json` (download status)
- `$OUTPUT_DIR/media/shot_*.{mp4,jpg,jpeg,png}` (downloaded files)

**Note**: In multi-format pipeline, this stage creates the initial media pool. Format-specific plans are created in Stage 6 by `build_format_media_plan.py`.

**Media Approval** (non-express mode):
- Human reviews shots via `./approve_media.sh`
- Creates `approved_media.json` with selected shots
- Express mode auto-approves all media

**Implementation**: agents/4_curate_media.sh:1-105

---

### Stage 6: Multi-Format Video Assembly

**Purpose**: Build three videos (full + 2 shorts) from one song

**Orchestrator**: `agents/build_multiformat_videos.py`

**Architecture** (Critical Change):
Previously, shorts were extracted from full video, causing duration mismatches. Now, each format is built independently with format-specific media plans.

**How It Works**:

#### 6.1: Create Format-Specific Media Plans
**Agent**: `agents/build_format_media_plan.py`

For each format (full, hook, educational):
1. Loads `segments.json` to get target duration
2. Calls `agents/4_curate_media.sh` with `--duration=X`
3. Claude creates format-optimized shot list
4. Saves to:
   - `media_plan_full.json` (180s plan)
   - `media_plan_hook.json` (30s plan)
   - `media_plan_educational.json` (30s plan)

**Key**: Each plan is optimized for its segment's characteristics and duration.

**Implementation**: agents/build_format_media_plan.py:1-165

#### 6.2: Build Each Video
**Agent**: `agents/build_multiformat_videos.py` calls `agents/5_assemble_video.py` for each format

**Process**:
```python
for format in ["full", "hook", "educational"]:
    1. Swap approved_media.json with media_plan_{format}.json
    2. Delete synchronized_plan.json cache (prevents reuse bug)
    3. Call 5_assemble_video.py with:
       - --resolution (1920x1080 or 1080x1920)
       - --audio-start (segment start time)
       - --audio-duration (segment duration)
    4. Rename final_video.mp4 → {format}.mp4
    5. Restore original approved_media.json
```

**Critical Bug Fix** (build_multiformat_videos.py:58-67):
The pipeline deletes `synchronized_plan.json` before each video build. Without this, all videos would use the cached plan from the first build, causing identical shot lists.

**Output**:
- `$OUTPUT_DIR/full.mp4` (16:9, ~180s)
- `$OUTPUT_DIR/short_hook.mp4` (9:16, ~30s)
- `$OUTPUT_DIR/short_educational.mp4` (9:16, ~30s)

**Implementation**: agents/build_multiformat_videos.py:1-255

---

### Stage 6.3: Video Assembly Core (agents/5_assemble_video.py)

**Purpose**: Combine media clips with music using MoviePy

**How It Works**:
1. Loads `approved_media.json` (or format-specific plan during multi-format builds)
2. Fetches word-level timestamps from Suno
3. Groups words into phrase groups (using `agents/phrase_grouper.py`)
4. Matches phrases to shots via semantic similarity (using `agents/semantic_matcher.py`)
5. Consolidates consecutive shots from same clip (using `agents/consolidate_clips.py`)
6. Trims audio to specified duration (if `--audio-duration` provided)
7. Creates video clips:
   - Images: ImageClip with specified duration
   - Videos: Trimmed/looped to match duration
   - Resized to target resolution (letterbox/pillarbox, no cropping)
   - Hard cuts (no transitions)
8. Concatenates clips with audio

**Key Functions**:
- `create_clip_from_shot()` (5_assemble_video.py:80-151): Creates MoviePy clip from shot
- `fetch_and_process_lyrics()` (5_assemble_video.py:153-230): Fetches timestamps and creates phrase groups
- Leverages helper agents:
  - `phrase_grouper.py`: Groups words into logical phrases
  - `semantic_matcher.py`: Matches phrases to media via CLIP
  - `consolidate_clips.py`: Merges consecutive shots from same source

**Arguments**:
- `--resolution WIDTHxHEIGHT`: Target resolution (default: 1920x1080)
- `--audio-start SECONDS`: Audio trim start time (default: 0)
- `--audio-duration SECONDS`: Audio duration (optional, defaults to video duration)

**Output**: `$OUTPUT_DIR/final_video.mp4`

**Implementation**: agents/5_assemble_video.py:1-500+

---

### Stage 7: Subtitle Generation (agents/generate_subtitles.py)

**Purpose**: Add subtitles to all videos

**Agent**: `agents/generate_subtitles.py`

**How It Works**:
1. Loads word-level timestamps from `suno_output.json` or `lyrics_aligned.json`
2. For **full video** (traditional subtitles):
   - Groups words into 2-3 second phrases
   - Generates SRT file with phrase-level timing
   - Burns in with FFmpeg
3. For **shorts** (karaoke subtitles):
   - Creates word-level SRT file
   - Converts to pycaps format
   - Applies karaoke-style highlighting

**Output**: `$OUTPUT_DIR/subtitles/*.srt`

**Key Functions**:
- `generate_traditional_srt()` (generate_subtitles.py:65-115): Phrase-level SRT
- `generate_karaoke_srt()` (generate_subtitles.py:117-131): Word-level SRT
- `convert_srt_to_pycaps_format()` (generate_subtitles.py:133-200+): pycaps JSON conversion

**Arguments**:
- `--engine`: ffmpeg or pycaps
- `--type`: traditional or karaoke
- `--video`: full, short_hook, short_educational
- `--segment`: hook or educational (for shorts)

**Implementation**: agents/generate_subtitles.py:1-300+

---

### Stage 8: YouTube & TikTok Upload (upload_to_youtube.sh, upload_to_tiktok.sh)

**Purpose**: Upload videos to YouTube and TikTok

**Agents**:
- `upload_to_youtube.sh`: YouTube upload via YouTube Data API v3
- `upload_to_tiktok.sh`: TikTok upload via unofficial API

**How It Works**:
1. Reads video metadata from run directory
2. Creates format-specific title/description
3. Uploads with privacy settings from `automation/config/automation_config.json`
4. Saves video IDs to:
   - `video_id_full.txt`
   - `video_id_short_hook.txt`
   - `video_id_short_educational.txt`
   - `tiktok_video_id_*.txt` (if TikTok enabled)

**Privacy Levels**:
- YouTube: public, unlisted, private
- TikTok: public_to_everyone, mutual_follow_friends, self_only

**Configuration** (automation/config/automation_config.json):
```json
{
  "youtube": {
    "privacy_status": "unlisted",
    "channel_handle": "@YourChannel"
  },
  "tiktok": {
    "enabled": true,
    "privacy_status": "public_to_everyone"
  }
}
```

**Implementation**:
- upload_to_youtube.sh
- upload_to_tiktok.sh

---

### Stage 9: Cross-Linking (agents/crosslink_videos.py)

**Purpose**: Update video descriptions with links to other formats

**Agent**: `agents/crosslink_videos.py`

**How It Works**:
1. Takes video IDs for all formats (YouTube + TikTok)
2. Updates YouTube descriptions with:
   - Links to other YouTube formats
   - TikTok links (if available)
3. Saves final URLs to `upload_results.json`:
```json
{
  "youtube": {
    "full_video": {"id": "...", "url": "..."},
    "hook_short": {"id": "...", "url": "..."},
    "educational_short": {"id": "...", "url": "..."}
  },
  "tiktok": {
    "full_video": {"url": "..."},
    "hook_short": {"url": "..."}
  }
}
```

**Implementation**: agents/crosslink_videos.py

---

## Data Flow

### Intermediate Artifacts by Stage

| Stage | Input Files | Output Files | Purpose |
|-------|------------|--------------|---------|
| 1 | input/idea.txt | research.json | Topic research |
| 2 | research.json | visual_rankings.json, thumbnails/* | Media diversity ranking |
| 3 | research_pruned_for_lyrics.json | lyrics.json, lyrics.txt, music_prompt.txt | Song lyrics |
| 4 | lyrics.json | song.mp3, music_metadata.json, suno_output.json | AI-generated music |
| 4.5 | suno_output.json | segments.json | Segment identification |
| 5 | research_pruned_for_curator.json, lyrics.json | media_plan.json, media_manifest.json, media/* | Media curation & download |
| 6 | segments.json, approved_media.json | media_plan_*.json, *.mp4 | Format-specific plans & videos |
| 7 | suno_output.json, *.mp4 | subtitles/*.srt | Subtitles |
| 8 | *.mp4 | video_id_*.txt | Platform uploads |
| 9 | video_id_*.txt | upload_results.json | Cross-linking |

### Environment Variables

**Set by pipeline.sh**:
- `OUTPUT_DIR`: Current run directory (e.g., `outputs/runs/20251201_094527`)
- `RUN_TIMESTAMP`: Run timestamp (e.g., `20251201_094527`)

**Used by agents**:
All Python/bash agents respect `OUTPUT_DIR` via `agents/output_helper.py`:
```python
def get_output_path(filename):
    return Path(os.getenv('OUTPUT_DIR', 'outputs')) / filename
```

---

## Key Agents & Functions

### Utility Modules

#### output_helper.py
**Location**: agents/output_helper.py

**Functions**:
- `get_output_dir()`: Returns `$OUTPUT_DIR` or fallback to `outputs/`
- `get_output_path(filename)`: Full path to file in OUTPUT_DIR
- `ensure_output_dir(subdir)`: Creates directory if not exists
- `get_run_timestamp()`: Current run timestamp or 'standalone'

**Used by**: Nearly all Python agents

#### context_pruner.py
**Location**: agents/context_pruner.py

**Purpose**: Reduce research.json size before passing to lyricist/curator to save tokens

**Usage**:
```bash
python3 agents/context_pruner.py lyricist   # Prunes for lyrics generation
python3 agents/context_pruner.py curator    # Prunes for media curation
```

**Pruning Strategy**:
- Keeps all key_facts
- Keeps top 15 media_suggestions (ranked by visual_score)
- Preserves tone and metadata
- Saves to `research_pruned_for_{agent}.json`

#### phrase_grouper.py
**Location**: agents/phrase_grouper.py

**Purpose**: Group word-level timestamps into logical phrase groups

**Class**: `PhraseGrouper`
- `group_words()`: Groups words into phrases based on:
  - Punctuation boundaries
  - Time gaps (>0.3s by default)
  - Max phrase duration (3.5s by default)
  - Min phrase duration (1.5s by default)

**Used by**: 5_assemble_video.py during sync planning

#### semantic_matcher.py
**Location**: agents/semantic_matcher.py

**Purpose**: Match phrase groups to media shots via CLIP semantic similarity

**Class**: `SemanticMatcher`
- `match_phrases_to_media()`: Uses CLIP to find best media for each phrase
- `create_synchronized_plan()`: Builds shot list synchronized to lyrics

**Algorithm**:
1. Encode phrase text and media descriptions with CLIP
2. Calculate cosine similarity
3. Boost keyword matches (2x multiplier for exact keyword matches)
4. Select highest-scoring media for each phrase
5. Ensure no shot is used twice in a row

**Used by**: 5_assemble_video.py

#### consolidate_clips.py
**Location**: agents/consolidate_clips.py

**Purpose**: Merge consecutive shots from same media source to reduce cuts

**Function**: `consolidate_phrase_groups()`

**Algorithm**:
1. Identifies consecutive shots from same `local_path`
2. Merges them into single extended shot
3. Updates duration and rationale
4. Returns consolidated shot list

**Effect**: Reduces jarring cuts, creates smoother video flow

**Used by**: 5_assemble_video.py

#### suno_lyrics_sync.py
**Location**: agents/suno_lyrics_sync.py

**Purpose**: Fetch word-level timestamps from Suno API

**Class**: `SunoLyricsSync`
- `fetch_aligned_lyrics(task_id, audio_id)`: Calls Suno /sync/lyrics endpoint
- Returns: `{"alignedWords": [{"word": "...", "startS": 0.0, "endS": 0.5}, ...]}`

**Used by**: 3_compose.py, 5_assemble_video.py, generate_subtitles.py

---

## Automation Layer

### Topic Generation (automation/topic_generator.py)

**Purpose**: Generate novel educational science topics

**How It Works**:
1. Loads topic history from `automation/state/topic_history.json`
2. Gets recent topics (last 30 days) to avoid repeats
3. Calls Claude Code CLI (Sonnet 4.5) with prompt:
   - Categories: physics, chemistry, biology, astronomy, earth science
   - K-12 appropriate (ages 10-18)
   - Visually interesting
   - Avoids recent topics
4. Parses output: `Topic: ... / Tone: ...`
5. Saves topic to `input/idea.txt`
6. Updates topic history

**Configuration** (automation/config/automation_config.json):
```json
{
  "topic_generation": {
    "categories": ["physics", "chemistry", "biology", "astronomy", "earth science"],
    "avoid_recent_days": 30
  }
}
```

**Output**: input/idea.txt
```
Explain how DNA replication works in cells. Tone: energetic pop punk with driving guitars, fast tempo, and rebellious educational energy
```

**Implementation**: automation/topic_generator.py:1-150+

---

## Multi-Format Video Architecture

### Why Format-Specific Media Plans?

**Previous Approach** (deprecated):
1. Build full 180s video
2. Extract 30s segments from full video
3. **Problem**: Duration mismatches, wrong aspect ratio

**Current Approach**:
1. Analyze song for best segments (analyze_segments.py)
2. Build **separate media plans** for each format (build_format_media_plan.py)
3. Build each video **independently** (build_multiformat_videos.py)

### Benefits
- **Correct durations**: Each video matches target exactly
- **Native aspect ratios**: Full is 16:9, shorts are 9:16
- **Optimized content**: Media selection tailored to segment characteristics
- **No extraction artifacts**: Videos built from scratch, not extracted

### Critical Implementation Details

**Synchronized Plan Cache Bug** (build_multiformat_videos.py:65):
```python
sync_plan_path = output_dir / "synchronized_plan.json"
if sync_plan_path.exists():
    sync_plan_path.unlink()  # MUST DELETE to prevent reuse
```

Without this deletion, all three videos would use the same cached plan from the first build, causing identical shot lists despite different media plans.

**Approved Media Swap** (build_multiformat_videos.py:54-108):
```python
# Backup original
approved_media_path.rename(backup_path)

# Use format-specific plan
shutil.copy(media_plan_path, approved_media_path)

# Build video
subprocess.run(['./venv/bin/python3', 'agents/5_assemble_video.py', ...])

# Restore original
backup_path.rename(approved_media_path)
```

This allows reusing 5_assemble_video.py without modification while providing different media for each format.

---

## Resume & Recovery

### Automatic Resume Detection

The `detect_resume_stage()` function in `automation/daily_pipeline.sh` automatically determines where to resume based on completed artifacts:

```bash
# Stage 9: Cross-linking complete
if upload_results.json exists with youtube+tiktok → Stage 10 (done)

# Stage 8: Upload complete
if video_id_full.txt exists → Stage 9 (cross-link)

# Stage 7: Subtitles complete
if subtitles/*.srt exist → Stage 8 (upload)

# Stage 6: Videos complete
if full.mp4 + short_hook.mp4 + short_educational.mp4 exist → Stage 7 (subtitles)

# Stage 5: Media approved
if approved_media.json exists → Stage 6 (video assembly)

# Stage 4.5: Segments analyzed
if segments.json exists → Stage 5 (media curation)

# Stage 4: Music complete
if song.mp3 exists → Stage 5 (segment analysis)

# Stage 3: Lyrics complete
if lyrics.json exists → Stage 4 (music)

# Stage 2: Visual ranking complete
if visual_rankings.json exists → Stage 3 (lyrics)

# Stage 1: Research complete
if research.json exists → Stage 2 (visual ranking)

# No stages complete
→ Stage 1 (start from beginning)
```

### Manual Resume

```bash
# Resume from stage 6 (video assembly)
./pipeline.sh --resume=20251201_094527 --start=6 --express

# Resume latest run from auto-detected stage
./automation/daily_pipeline.sh  # Will detect and resume automatically
```

### Resume Caveats

1. **Context Pruning**: Pruned files are not regenerated on resume. If resuming after Stage 2, ensure `research_pruned_for_*.json` exist.

2. **Media Downloads**: If resuming Stage 6, ensure media files in `media/` directory still exist.

3. **Synchronized Plan Cache**: The `synchronized_plan.json` cache may cause issues during partial reruns. Delete it manually if rebuilding specific formats.

---

## Known Issues & Considerations

### 1. Context Pruning Files Not Regenerated
**Issue**: If you resume from Stage 3+ but delete pruned files, the pipeline will fail.

**Solution**: Keep `research_pruned_for_lyricist.json` and `research_pruned_for_curator.json` when resuming.

### 2. Synchronized Plan Cache
**Issue**: `synchronized_plan.json` caches shot-to-phrase mapping. Reusing it across formats causes identical videos.

**Status**: Fixed in build_multiformat_videos.py:65 (deletes cache before each build).

**Manual Fix** (if needed):
```bash
rm $OUTPUT_DIR/synchronized_plan.json
```

### 3. Suno Timestamp Availability
**Issue**: Word-level timestamps may not always be available from Suno API.

**Fallback**: System uses Hoot alignment as backup (less accurate).

**Check**: Look for "⚠️ No aligned words" warnings in logs.

### 4. Media Download Failures
**Issue**: Stock photo APIs may fail or media URLs may be unavailable.

**Handling**:
- visual_rankings.py appends failed downloads to end of ranking
- Curator still uses them (downloads may succeed later)
- Video assembly creates black placeholder for failed media

### 5. Claude API Timeouts
**Issue**: Curator may timeout on long videos (180s) with many media items.

**Timeout**: 600s (10 minutes) in build_format_media_plan.py:78

**Mitigation**: If curator fails, try:
- Reduce media pool size
- Increase timeout in build_format_media_plan.py

### 6. Multi-Format Build Order
**Current Order**: Full → Hook → Educational

**Consideration**: Builds are sequential, not parallel. Total time ≈ 3x single video build time.

**Future Improvement**: Could parallelize builds, but requires careful state management (approved_media swap).

---

## Function Reference

### Pipeline Orchestration
| Function/File | Location | Purpose |
|---------------|----------|---------|
| `pipeline.sh` | pipeline.sh:1-681 | Main pipeline orchestrator |
| `daily_pipeline.sh` | automation/daily_pipeline.sh:1-240 | Daily automation wrapper |
| `detect_resume_stage()` | automation/daily_pipeline.sh:31-100 | Auto-detect resume point |
| `build_multiformat_videos.py` | agents/build_multiformat_videos.py:1-255 | Multi-format video orchestrator |

### Research & Content
| Function/File | Location | Purpose |
|---------------|----------|---------|
| `1_research.sh` | agents/1_research.sh:1-67 | Educational content research |
| `topic_generator.py` | automation/topic_generator.py:1-150+ | Autonomous topic generation |
| `VisualRanker.rank_media()` | agents/3_rank_visuals.py:242-287 | CLIP-based media ranking |
| `context_pruner.py` | agents/context_pruner.py | Reduce research data size |

### Music & Lyrics
| Function/File | Location | Purpose |
|---------------|----------|---------|
| `2_lyrics.sh` | agents/2_lyrics.sh:1-65 | Lyrics generation |
| `SunoAPIClient` | agents/3_compose.py:24-149 | Suno API music generation |
| `SunoLyricsSync` | agents/suno_lyrics_sync.py | Word-level timestamp fetching |
| `analyze_segments.py` | agents/analyze_segments.py:1-273 | Segment identification |

### Media & Video
| Function/File | Location | Purpose |
|---------------|----------|---------|
| `4_curate_media.sh` | agents/4_curate_media.sh:1-105 | Media curation |
| `build_format_media_plan.py` | agents/build_format_media_plan.py:1-165 | Format-specific media plans |
| `5_assemble_video.py` | agents/5_assemble_video.py:1-500+ | Video assembly with MoviePy |
| `PhraseGrouper` | agents/phrase_grouper.py | Group words into phrases |
| `SemanticMatcher` | agents/semantic_matcher.py | Match phrases to media |
| `consolidate_phrase_groups()` | agents/consolidate_clips.py | Merge consecutive clips |
| `generate_subtitles.py` | agents/generate_subtitles.py:1-300+ | Subtitle generation |

### Utilities
| Function/File | Location | Purpose |
|---------------|----------|---------|
| `get_output_path()` | agents/output_helper.py:27-37 | Get file path in OUTPUT_DIR |
| `ensure_output_dir()` | agents/output_helper.py:40-56 | Create output directory |

---

## Configuration Files

### config/config.json
```json
{
  "suno_api": {
    "api_key": "...",
    "base_url": "https://api.sunoapi.org",
    "model": "V5"
  },
  "video_settings": {
    "resolution": [1920, 1080],
    "fps": 30
  },
  "video_formats": {
    "full_video": {"enabled": true},
    "shorts": {"enabled": true}
  },
  "lyric_sync": {
    "enabled": true,
    "min_phrase_duration": 1.5,
    "phrase_gap_threshold": 0.3
  }
}
```

### automation/config/automation_config.json
```json
{
  "topic_generation": {
    "categories": ["physics", "chemistry", "biology", "astronomy", "earth science"],
    "avoid_recent_days": 30
  },
  "youtube": {
    "privacy_status": "unlisted",
    "channel_handle": "@YourChannel"
  },
  "tiktok": {
    "enabled": true,
    "privacy_status": "public_to_everyone"
  },
  "notifications": {
    "notify_on_success": true,
    "notify_on_failure": true
  }
}
```

---

## End-to-End Example

### Full Pipeline Run
```bash
# 1. Set topic
echo "Explain how photosynthesis works. Tone: energetic pop punk" > input/idea.txt

# 2. Run pipeline
./pipeline.sh --express

# 3. Monitor logs
tail -f logs/pipeline_20251201_*.log

# 4. Output structure
outputs/runs/20251201_094527/
  research.json                    # Stage 1: Research
  visual_rankings.json             # Stage 2: Visual ranking
  thumbnails/                      # Stage 2: Thumbnail cache
  research_pruned_for_lyrics.json  # Stage 3: Context pruning
  lyrics.json                      # Stage 3: Lyrics
  lyrics.txt                       # Stage 3: Extracted lyrics
  music_prompt.txt                 # Stage 3: Music style
  song.mp3                         # Stage 4: Generated music
  suno_output.json                 # Stage 4: Suno metadata
  music_metadata.json              # Stage 4: Music info
  segments.json                    # Stage 4.5: Segment analysis
  research_pruned_for_curator.json # Stage 5: Context pruning
  media_plan.json                  # Stage 5: Initial media plan
  media_manifest.json              # Stage 5: Download status
  media/                           # Stage 5: Downloaded media
    shot_001.mp4
    shot_002.jpg
    ...
  approved_media.json              # Stage 5: Approved shots
  media_plan_full.json             # Stage 6: Full video plan
  media_plan_hook.json             # Stage 6: Hook short plan
  media_plan_educational.json      # Stage 6: Educational short plan
  full.mp4                         # Stage 6: Full video
  short_hook.mp4                   # Stage 6: Hook short
  short_educational.mp4            # Stage 6: Educational short
  subtitles/                       # Stage 7: Subtitles
    full.srt
    short_hook.srt
    short_educational.srt
  video_id_full.txt                # Stage 8: YouTube IDs
  video_id_short_hook.txt
  video_id_short_educational.txt
  tiktok_video_id_full.txt         # Stage 8: TikTok IDs (if enabled)
  tiktok_video_id_short_hook.txt
  upload_results.json              # Stage 9: Cross-linking complete

# 5. Logs
logs/pipeline_20251201_094527.log  # Full execution log
```

### Daily Automated Run
```bash
# Cron job: Run daily at 9 AM
0 9 * * * cd /path/to/MusicVideosAutomate && ./automation/daily_pipeline.sh

# What happens:
# 1. Generates new topic (avoiding recent topics)
# 2. Runs pipeline in express mode
# 3. If fails, retries with --resume (up to 2 retry attempts)
# 4. Uploads to YouTube + TikTok
# 5. Cross-links videos
# 6. Sends notification (if configured)
```

---

**Last Updated:** December 1, 2025

**Maintainer**: Document the current state of implementation. This documentation reflects the actual working pipeline architecture as of December 2025.
