# Educational Video Automation System

> Transform ideas into educational TikTok/Instagram Reels videos automatically with AI-generated music and curated visuals.

## Quick Start

```bash
# 1. Setup (one-time)
./setup.sh

# 2. Configure API keys
nano config/config.json  # Add your Suno API key

# 3. Create your first video
echo "Explain black holes. Tone: mysterious and awe-inspiring" > input/idea.txt
./pipeline.sh

# 4. Watch!
open outputs/current/final_video.mp4
```

## Features

- 🤖 **AI Research**: Automatically gathers facts and finds royalty-free media
- 🎨 **Visual Ranking**: CLIP-powered diversity analysis ensures engaging variety
- 🎵 **Synchronized Video-Lyric Switching**: Videos switch exactly when key scientific terms are sung
- 🎵 **Music Generation**: Creates custom educational songs via Suno API
- 🎬 **Video Assembly**: Combines media, lyrics, and music into polished videos
- 👁️ **Human Review**: Preview media before final assembly
- ⚡ **Express Mode**: Fully automated pipeline for trusted workflows
- 💰 **Cost Effective**: ~$0.02-$0.04 per video
- 📁 **Timestamped Runs**: Each pipeline run creates a unique timestamped directory

### 🎵 Synchronized Video-Lyric Switching

**Word-Level Precision**: Videos switch exactly when key scientific terms are sung, using Suno API's word-level timestamps.

**AI Semantic Grouping**: Phrases discussing the same concept stay on the same video, creating smooth educational flow.

**CLIP + Keyword Boosting**: Videos are matched to phrases using semantic similarity plus 2x boost for exact keyword matches (e.g., "ATP synthase" lyric → ATP synthase animation).

**Graceful Fallback**: If Suno API is unavailable, falls back to curator's timing automatically.

**Configuration**: Control sync behavior in `config/config.json`:
- `phrase_gap_threshold`: Minimum pause to split phrases (default: 0.3s)
- `min_phrase_duration`: Minimum shot duration (default: 1.5s)
- `keyword_boost_multiplier`: Boost for keyword matches (default: 2.0)

## Command-Line Options

```bash
./pipeline.sh [OPTIONS]

Options:
  --express              Auto-approve all media (skip manual review)
  --start=N              Start from stage N (1-6)
  --resume               Resume from latest run
  --resume=TIMESTAMP     Resume from specific run directory

Examples:
  ./pipeline.sh                              # New run, all stages
  ./pipeline.sh --express                    # New run, skip approval
  ./pipeline.sh --start=3 --resume           # Resume latest from stage 3
  ./pipeline.sh --start=5 --resume=20250116_143025  # Resume specific run
```

## YouTube Upload

After creating a video, you can manually upload it to YouTube:

```bash
./upload_to_youtube.sh [OPTIONS]

Options:
  --run=TIMESTAMP        Upload specific run (e.g., 20250116_143025)
  --privacy=STATUS       Privacy status: public, unlisted, private (default: unlisted)
  --help                 Show help message

Examples:
  ./upload_to_youtube.sh                     # Upload latest run as unlisted
  ./upload_to_youtube.sh --privacy=public    # Upload latest as public
  ./upload_to_youtube.sh --run=20250116_143025  # Upload specific run
```

### YouTube Setup (One-Time)

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project (or select existing)
3. Enable **YouTube Data API v3**
4. Create **OAuth 2.0 credentials** (Desktop app)
5. Download credentials JSON
6. Save as: `config/youtube_credentials.json`

The script will guide you through OAuth authentication on first upload.

### Optional: Lyric Synchronization

For synchronized video-lyric switching:

```bash
export SUNO_API_KEY='your_suno_api_key'
```

Get your key from [SunoAPI.org](https://sunoapi.org)

Without this key, the system falls back to curator's timing.

## Documentation

- [Setup Guide](docs/SETUP_GUIDE.md) - Detailed installation and configuration
- [Troubleshooting](docs/TROUBLESHOOTING.md) - Common issues and solutions

---

# Educational Video Automation System

Automatically generate 30-second educational videos with AI-generated music and curated visuals.

## Prerequisites

- macOS (tested on Mac Studio)
- Python 3.9+
- Claude Code CLI (subscription required)
- Suno API account (sunoapi.org)
- viu (terminal image viewer): `brew install viu`

## Installation

1. Clone this repository
2. Run setup: `./setup.sh`
3. Configure API keys in `config/config.json`

## Usage

### Standard Mode (with media review)
```bash
# 1. Write your idea in input/idea.txt
echo "Explain photosynthesis in plants. Tone: upbeat and fun" > input/idea.txt

# 2. Run pipeline
./pipeline.sh

# 3. Review and approve media when prompted
# 4. Find final video at outputs/current/final_video.mp4
```

### Express Mode (auto-approve media)
```bash
./pipeline.sh --express
```

### Resume from Specific Stage
Start the pipeline from a later stage (useful if a stage fails):

```bash
# Resume latest run from stage 3
./pipeline.sh --start=3 --resume

# Resume specific run from stage 5
./pipeline.sh --start=5 --resume=20250116_143025
```

**Available stages:**
1. Research
2. Visual Ranking
3. Lyrics Generation
4. Music Composition
5. Media Curation & Download
6. Video Assembly

### Multiple Runs
Each pipeline run creates a timestamped directory in `outputs/runs/`. The latest run is always symlinked at `outputs/current/` for easy access.

```bash
# Run 1
./pipeline.sh  # Creates outputs/runs/20250116_143025/

# Run 2
./pipeline.sh  # Creates outputs/runs/20250116_150432/

# Access latest run
ls outputs/current/  # Symlink to most recent run

# Resume latest run from stage 5 (video assembly)
./pipeline.sh --start=5 --resume

# Resume specific run
./pipeline.sh --start=4 --resume=20250116_143025

# List all runs
ls outputs/runs/
```

## Project Structure

```
MusicVideosAutomate/
├── input/idea.txt              # Your topic + tone
├── agents/
│   ├── 1_research.sh           # Research agent
│   ├── 2_lyrics.sh             # Lyrics generation
│   ├── 3_compose.py            # Suno API integration
│   ├── 4_curate_media.sh       # Media selection
│   ├── 5_assemble_video.py     # MoviePy assembly
│   ├── output_helper.py        # Path management for timestamped runs
│   └── prompts/                # Claude Code prompts
├── pipeline.sh                 # Master orchestrator
├── approve_media.sh            # Media review UI
├── outputs/                    # Generated files
│   ├── runs/                   # Timestamped run directories
│   │   ├── 20250116_143025/    # Example run
│   │   └── 20250116_150432/    # Example run
│   └── current/                # Symlink to latest run
└── config/config.json          # API keys, settings
```

## Cost Estimate

- ~$0.02-$0.04 per video (Suno API only)
- Claude Code usage: included in subscription
- Media: free (royalty-free sources only)

## License

MIT
