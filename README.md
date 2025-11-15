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
# 4. Find final video at outputs/final_video.mp4
```

### Express Mode (auto-approve media)
```bash
./pipeline.sh --express
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
│   └── prompts/                # Claude Code prompts
├── pipeline.sh                 # Master orchestrator
├── approve_media.sh            # Media review UI
├── outputs/                    # Generated files
└── config/config.json          # API keys, settings
```

## Cost Estimate

- ~$0.02-$0.04 per video (Suno API only)
- Claude Code usage: included in subscription
- Media: free (royalty-free sources only)

## License

MIT
