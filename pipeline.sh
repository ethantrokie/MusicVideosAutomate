#!/bin/bash

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Parse arguments
EXPRESS_MODE=false
START_STAGE=1
RESUME_DIR=""

for arg in "$@"; do
    case $arg in
        --express)
            EXPRESS_MODE=true
            ;;
        --start=*)
            START_STAGE="${arg#*=}"
            ;;
        --resume)
            # Resume from latest run
            RESUME_DIR="latest"
            ;;
        --resume=*)
            # Resume from specific run directory
            RESUME_DIR="${arg#*=}"
            ;;
    esac
done

echo -e "${BLUE}🎬 Educational Video Automation Pipeline${NC}"
echo "=========================================="
echo ""

# Check for input
if [ ! -f "input/idea.txt" ]; then
    echo -e "${RED}❌ Error: input/idea.txt not found${NC}"
    echo ""
    echo "Create your input file with:"
    echo "  echo 'Your topic description. Tone: your desired tone' > input/idea.txt"
    echo ""
    echo "Example:"
    echo "  echo 'Explain photosynthesis in plants. Tone: upbeat and fun' > input/idea.txt"
    exit 1
fi

echo -e "${BLUE}📄 Input:${NC}"
cat input/idea.txt
echo ""
echo ""

# Create/activate virtual environment
if [ ! -d "venv" ]; then
    echo -e "${YELLOW}⚠️  Virtual environment not found. Run ./setup.sh first${NC}"
    exit 1
fi

source venv/bin/activate

# Determine run directory
if [ -n "$RESUME_DIR" ]; then
    # Resuming from existing run
    if [ "$RESUME_DIR" = "latest" ]; then
        # Use the current symlink (most recent run)
        if [ -L "outputs/current" ]; then
            RUN_DIR=$(readlink -f "outputs/current" 2>/dev/null || readlink "outputs/current")
            RUN_DIR="outputs/${RUN_DIR}"
            RUN_TIMESTAMP=$(basename "$RUN_DIR")
            echo -e "${YELLOW}📂 Resuming latest run: ${RUN_TIMESTAMP}${NC}"
        else
            echo -e "${RED}❌ Error: No previous runs found (outputs/current doesn't exist)${NC}"
            exit 1
        fi
    else
        # Use specified run directory
        if [ -d "outputs/runs/${RESUME_DIR}" ]; then
            RUN_DIR="outputs/runs/${RESUME_DIR}"
            RUN_TIMESTAMP="${RESUME_DIR}"
            echo -e "${YELLOW}📂 Resuming run: ${RUN_TIMESTAMP}${NC}"
        else
            echo -e "${RED}❌ Error: Run directory not found: outputs/runs/${RESUME_DIR}${NC}"
            echo ""
            echo "Available runs:"
            ls -1 outputs/runs/ 2>/dev/null || echo "  (none)"
            exit 1
        fi
    fi
else
    # Create new timestamped run directory
    RUN_TIMESTAMP=$(date +%Y%m%d_%H%M%S)
    RUN_DIR="outputs/runs/${RUN_TIMESTAMP}"
    mkdir -p "${RUN_DIR}/media" logs

    # Create symlink to latest run
    rm -f outputs/current
    ln -sf "runs/${RUN_TIMESTAMP}" outputs/current

    echo -e "${GREEN}📂 New run: ${RUN_TIMESTAMP}${NC}"
fi

# Ensure media directory exists
mkdir -p "${RUN_DIR}/media" logs

# Export for agents to use
export OUTPUT_DIR="${RUN_DIR}"
export RUN_TIMESTAMP="${RUN_TIMESTAMP}"

# Log file
LOG_FILE="logs/pipeline_${RUN_TIMESTAMP}.log"
exec > >(tee -a "$LOG_FILE") 2>&1

echo -e "${GREEN}Starting pipeline from stage $START_STAGE...${NC}"
echo "Run directory: ${RUN_DIR}"
echo "Log: $LOG_FILE"
echo ""

# Stage 1: Research
if [ $START_STAGE -le 1 ]; then
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}Stage 1/5: Research${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    ./agents/1_research.sh
    if [ $? -ne 0 ]; then
        echo -e "${RED}❌ Research failed${NC}"
        exit 1
    fi
    echo ""
fi

# Stage 2: Visual Ranking
if [ $START_STAGE -le 2 ]; then
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}Stage 2/6: Visual Ranking${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

    echo "🎨 Visual Ranking Agent: Analyzing media diversity..."

    if python3 agents/3_rank_visuals.py; then
        echo "✅ Visual ranking complete"
    else
        echo -e "${YELLOW}⚠️  Visual ranking failed, continuing without rankings${NC}"
        # Not critical - curator can work without rankings
    fi
    echo ""
fi

# Stage 3: Lyrics
if [ $START_STAGE -le 3 ]; then
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}Stage 3/6: Lyrics Generation${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    ./agents/2_lyrics.sh
    if [ $? -ne 0 ]; then
        echo -e "${RED}❌ Lyrics generation failed${NC}"
        exit 1
    fi
    echo ""
fi

# Stage 4: Music
if [ $START_STAGE -le 4 ]; then
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}Stage 4/6: Music Composition${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    ./agents/3_compose.py
    if [ $? -ne 0 ]; then
        echo -e "${RED}❌ Music composition failed${NC}"
        exit 1
    fi
    echo ""
fi

# Stage 5: Media Curation
if [ $START_STAGE -le 5 ]; then
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}Stage 5/6: Media Curation${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    ./agents/4_curate_media.sh
    if [ $? -ne 0 ]; then
        echo -e "${RED}❌ Media curation failed${NC}"
        exit 1
    fi
    echo ""

    # Stage 4.5: Media Approval (unless express mode)
    if [ "$EXPRESS_MODE" = false ]; then
        echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
        echo -e "${YELLOW}Human Review: Media Approval${NC}"
        echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
        echo ""
        ./approve_media.sh
        if [ $? -ne 0 ]; then
            echo -e "${RED}❌ Media approval cancelled${NC}"
            exit 1
        fi
    else
        echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
        echo -e "${YELLOW}Express Mode: Auto-approving media${NC}"
        echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
        # Copy media plan to approved
        cp "${OUTPUT_DIR}/media_plan.json" "${OUTPUT_DIR}/approved_media.json"
        # Add local_path to approved media
        python3 << EOF
import json
import os

output_dir = os.getenv('OUTPUT_DIR', 'outputs')

with open(f'{output_dir}/media_plan.json') as f:
    plan = json.load(f)

with open(f'{output_dir}/media_manifest.json') as f:
    manifest = json.load(f)

for shot in plan['shot_list']:
    downloaded = [d for d in manifest['downloaded'] if d['shot_number'] == shot['shot_number']]
    if downloaded:
        shot['local_path'] = downloaded[0]['local_path']

with open(f'{output_dir}/approved_media.json', 'w') as f:
    json.dump(plan, f, indent=2)

print("✅ Auto-approved all downloaded media")
EOF
    fi
    echo ""
fi

# Stage 6: Video Assembly
if [ $START_STAGE -le 6 ]; then
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}Stage 6/6: Video Assembly${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    ./agents/5_assemble_video.py
    if [ $? -ne 0 ]; then
        echo -e "${RED}❌ Video assembly failed${NC}"
        exit 1
    fi
    echo ""
fi

# Success!
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}✅ Pipeline Complete!${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo -e "${GREEN}📹 Final video: outputs/final_video.mp4${NC}"
echo ""
echo "Generated files:"
echo "  - outputs/research.json       (research data)"
echo "  - outputs/lyrics.txt           (song lyrics)"
echo "  - outputs/song.mp3             (AI-generated music)"
echo "  - outputs/media_plan.json      (shot list)"
echo "  - outputs/final_video.mp4      (final video)"
echo ""
echo "Next steps:"
echo "  - Preview: open outputs/final_video.mp4"
echo "  - Edit in iMovie if needed"
echo "  - Share to social media!"
echo ""
echo -e "${BLUE}Cost estimate for this video: ~\$0.02-\$0.04${NC}"
