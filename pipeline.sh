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
if [[ "$1" == "--express" ]]; then
    EXPRESS_MODE=true
fi

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

# Create outputs directory
mkdir -p outputs/media logs

# Log file
LOG_FILE="logs/pipeline_$(date +%Y%m%d_%H%M%S).log"
exec > >(tee -a "$LOG_FILE") 2>&1

echo -e "${GREEN}Starting pipeline...${NC}"
echo "Log: $LOG_FILE"
echo ""

# Stage 1: Research
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}Stage 1/5: Research${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
./agents/1_research.sh
if [ $? -ne 0 ]; then
    echo -e "${RED}❌ Research failed${NC}"
    exit 1
fi
echo ""

# Stage 2: Lyrics
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}Stage 2/5: Lyrics Generation${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
./agents/2_lyrics.sh
if [ $? -ne 0 ]; then
    echo -e "${RED}❌ Lyrics generation failed${NC}"
    exit 1
fi
echo ""

# Stage 3: Music
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}Stage 3/5: Music Composition${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
./agents/3_compose.py
if [ $? -ne 0 ]; then
    echo -e "${RED}❌ Music composition failed${NC}"
    exit 1
fi
echo ""

# Stage 4: Media Curation
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}Stage 4/5: Media Curation${NC}"
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
    cp outputs/media_plan.json outputs/approved_media.json
    # Add local_path to approved media
    python3 << 'EOF'
import json

with open('outputs/media_plan.json') as f:
    plan = json.load(f)

with open('outputs/media_manifest.json') as f:
    manifest = json.load(f)

for shot in plan['shot_list']:
    downloaded = [d for d in manifest['downloaded'] if d['shot_number'] == shot['shot_number']]
    if downloaded:
        shot['local_path'] = downloaded[0]['local_path']

with open('outputs/approved_media.json', 'w') as f:
    json.dump(plan, f, indent=2)

print("✅ Auto-approved all downloaded media")
EOF
fi
echo ""

# Stage 5: Video Assembly
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}Stage 5/5: Video Assembly${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
./agents/5_assemble_video.py
if [ $? -ne 0 ]; then
    echo -e "${RED}❌ Video assembly failed${NC}"
    exit 1
fi
echo ""

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
