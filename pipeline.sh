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

# Stage 4.5: Segment Analysis (for multi-format videos)
if [ $START_STAGE -le 5 ]; then
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}Stage 4.5: Segment Analysis${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

    echo "🎯 Analyzing song segments for multi-format videos..."
    if python3 agents/analyze_segments.py; then
        echo "✅ Segment analysis complete"
    else
        echo -e "${YELLOW}⚠️  Segment analysis failed, will use full song for all formats${NC}"
        # Create fallback segments
        python3 << 'EOF'
import json
import os
from pathlib import Path

output_dir = os.getenv('OUTPUT_DIR', 'outputs/current')
segments_file = Path(f"{output_dir}/segments.json")

# Create fallback segments (full song for all)
fallback = {
    'full': {'start': 0, 'end': 180, 'duration': 180, 'rationale': 'Fallback: using full song'},
    'hook': {'start': 30, 'end': 60, 'duration': 30, 'rationale': 'Fallback: middle section'},
    'educational': {'start': 10, 'end': 40, 'duration': 30, 'rationale': 'Fallback: intro section'}
}

with open(segments_file, 'w') as f:
    json.dump(fallback, f, indent=2)
EOF
    fi
    echo ""
fi

# Stage 5: Media Curation
# Note: This creates initial media_plan.json for backwards compatibility.
# Multi-format builds create format-specific plans (media_plan_full.json, etc.) in Stage 6.
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

    # Check for research gaps
    if python3 agents/3.5_fill_research_gaps.py; then
        echo "✅ No research gaps"
    else
        GAP_EXIT_CODE=$?
        if [ $GAP_EXIT_CODE -eq 2 ]; then
            echo -e "${YELLOW}⚠️  Research gaps detected, running targeted research to fill gaps${NC}"

            # Load gap request to get parameters
            GAP_REQUEST="${OUTPUT_DIR}/research_gap_request.json"

            if [ -f "$GAP_REQUEST" ]; then
                # Extract parameters using Python
                TARGET_COUNT=$(python3 - "$GAP_REQUEST" << 'EOF'
import json
import sys

# Check if file argument provided
if len(sys.argv) < 2:
    print("5", file=sys.stderr)  # Default value
    sys.exit(0)

with open(sys.argv[1]) as f:
    data = json.load(f)

print(data.get('target_media_count', 5))
EOF
)

                TONE=$(python3 - "$GAP_REQUEST" << 'EOF'
import json
import sys

if len(sys.argv) < 2:
    print("educational")
    sys.exit(0)

with open(sys.argv[1]) as f:
    data = json.load(f)

print(data.get('tone', 'educational'))
EOF
)

                # Format missing concepts as numbered list
                CONCEPTS_LIST=$(python3 - "$GAP_REQUEST" << 'EOF'
import json
import sys

if len(sys.argv) < 2:
    sys.exit(1)

with open(sys.argv[1]) as f:
    data = json.load(f)

concepts = data.get('missing_concepts', [])
if not concepts:
    sys.exit(1)

formatted = '\n'.join([f"{i+1}. {c}" for i, c in enumerate(concepts)])
print(formatted)
EOF
)

                # Get topic from original input
                IDEA=$(cat input/idea.txt)
                if [[ $IDEA == *"Tone:"* ]]; then
                    TOPIC="${IDEA%%Tone:*}"
                else
                    TOPIC="$IDEA"
                fi
                # Trim whitespace without using xargs (which breaks with apostrophes)
                TOPIC="${TOPIC#"${TOPIC%%[![:space:]]*}"}"  # Remove leading whitespace
                TOPIC="${TOPIC%"${TOPIC##*[![:space:]]}"}"  # Remove trailing whitespace

                # Create gap-fill prompt
                TEMP_GAP_PROMPT=$(mktemp)
                sed "s/{{TOPIC}}/$TOPIC/g; \
                     s/{{TONE}}/$TONE/g; \
                     s|{{OUTPUT_PATH}}|${OUTPUT_DIR}/gap_fill_media.json|g; \
                     s|{{TARGET_COUNT}}|$TARGET_COUNT|g" \
                    agents/prompts/researcher_gap_fill_prompt.md > "$TEMP_GAP_PROMPT"

                # Insert missing concepts list
                python3 << EOF
import sys
concepts_list = '''$CONCEPTS_LIST'''
with open('$TEMP_GAP_PROMPT', 'r') as f:
    content = f.read()
content = content.replace('{{MISSING_CONCEPTS}}', concepts_list)
with open('$TEMP_GAP_PROMPT', 'w') as f:
    f.write(content)
EOF

                # Run gap-filling research
                echo "  Finding media for $TARGET_COUNT missing concepts..."
                claude -p "$(cat $TEMP_GAP_PROMPT)" --dangerously-skip-permissions > /dev/null 2>&1

                rm "$TEMP_GAP_PROMPT"

                # Merge gap-fill media into original research
                if [ -f "${OUTPUT_DIR}/gap_fill_media.json" ]; then
                    python3 << 'EOF'
import json
import sys
import os

output_dir = os.getenv('OUTPUT_DIR', 'outputs')

# Load original research
with open(f'{output_dir}/research.json') as f:
    research = json.load(f)

# Load gap-fill media
with open(f'{output_dir}/gap_fill_media.json') as f:
    gap_data = json.load(f)

# Merge gap-fill media into research
gap_media = gap_data.get('gap_fill_media', [])
if gap_media:
    research['media_suggestions'].extend(gap_media)

    # Save updated research
    with open(f'{output_dir}/research.json', 'w') as f:
        json.dump(research, f, indent=2)

    print(f"  ✅ Added {len(gap_media)} new media items to research")
    print(f"  Total media now: {len(research['media_suggestions'])}")
else:
    print("  ⚠️  No gap-fill media found")
EOF

                    # Re-run visual ranking with updated research
                    echo "  Re-running visual ranking with expanded media set..."
                    if python3 agents/3_rank_visuals.py; then
                        echo "  ✅ Visual ranking updated"
                    else
                        echo -e "  ${YELLOW}⚠️  Visual ranking failed, continuing${NC}"
                    fi
                fi
            else
                echo -e "${YELLOW}⚠️  Gap request file not found, skipping gap-fill${NC}"
            fi
        fi
    fi
    echo ""
fi

# Stage 6: Video Assembly (Multi-Format)
# Architecture: Each format (full, hook, educational) is built independently with:
#   1. Format-specific media plans optimized for target duration
#   2. Native resolution (16:9 for full, 9:16 for shorts)
#   3. Media selections tailored to segment characteristics
# This replaces the old extraction approach which caused duration mismatches.
if [ $START_STAGE -le 6 ]; then
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}Stage 6/9: Multi-Format Video Assembly${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

    # Check if multi-format is enabled
    if python3 -c "import json; c=json.load(open('config/config.json')); print(c.get('video_formats',{}).get('full_video',{}).get('enabled',True))" | grep -q "True"; then
        echo "🎬 Building multi-format videos with format-specific media plans..."
        echo "  • Full video (16:9, 180s) - comprehensive coverage"
        echo "  • Hook short (9:16, 30s) - most engaging segment"
        echo "  • Educational short (9:16, 30s) - key teaching moments"
        python3 agents/build_multiformat_videos.py
        if [ $? -ne 0 ]; then
            echo -e "${RED}❌ Multi-format video assembly failed${NC}"
            exit 1
        fi
    else
        echo "📹 Building single video..."
        ./agents/5_assemble_video.py
        if [ $? -ne 0 ]; then
            echo -e "${RED}❌ Video assembly failed${NC}"
            exit 1
        fi
    fi
    echo ""
fi

# Stage 7: Subtitle Generation
if [ $START_STAGE -le 7 ]; then
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}Stage 7/9: Subtitle Generation${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

    # Check if videos exist for subtitling
    if [ -f "${RUN_DIR}/full.mp4" ]; then
        echo "📝 Adding subtitles to all videos..."

        # Traditional subtitles for full video (FFmpeg)
        if python3 agents/generate_subtitles.py --engine=ffmpeg --type=traditional --video=full; then
            echo "  ✅ Full video subtitles applied"
        else
            echo -e "${YELLOW}  ⚠️  Full video subtitles failed, continuing...${NC}"
        fi

        # Karaoke subtitles for shorts (pycaps)
        if [ -f "${RUN_DIR}/short_hook.mp4" ]; then
            if python3 agents/generate_subtitles.py --engine=pycaps --type=karaoke --video=short_hook --segment=hook; then
                echo "  ✅ Hook short subtitles applied"
            else
                echo -e "${YELLOW}  ⚠️  Hook short subtitles failed, continuing...${NC}"
            fi
        fi

        if [ -f "${RUN_DIR}/short_educational.mp4" ]; then
            if python3 agents/generate_subtitles.py --engine=pycaps --type=karaoke --video=short_educational --segment=educational; then
                echo "  ✅ Educational short subtitles applied"
            else
                echo -e "${YELLOW}  ⚠️  Educational short subtitles failed, continuing...${NC}"
            fi
        fi
    else
        echo -e "${YELLOW}⚠️  No multi-format videos found, skipping subtitles${NC}"
    fi
    echo ""
fi

# Stage 8: Upload to YouTube
if [ $START_STAGE -le 8 ]; then
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}Stage 8/9: YouTube Upload${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

    # Ask user if they want to upload
    if [ "$EXPRESS_MODE" = false ]; then
        echo "📤 Upload videos to YouTube?"
        echo ""
        echo "Videos ready:"
        if [ -f "${RUN_DIR}/full.mp4" ]; then
            echo "  - Full video (${RUN_DIR}/full.mp4)"
        fi
        if [ -f "${RUN_DIR}/short_hook.mp4" ]; then
            echo "  - Hook short (${RUN_DIR}/short_hook.mp4)"
        fi
        if [ -f "${RUN_DIR}/short_educational.mp4" ]; then
            echo "  - Educational short (${RUN_DIR}/short_educational.mp4)"
        fi
        echo ""
        read -p "Upload now? [y/N] " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            echo "⏭️  Skipping upload"
            echo ""
            echo "To upload later, run:"
            echo "  ./upload_to_youtube.sh --run=${RUN_TIMESTAMP} --type=full"
            echo "  ./upload_to_youtube.sh --run=${RUN_TIMESTAMP} --type=short_hook"
            echo "  ./upload_to_youtube.sh --run=${RUN_TIMESTAMP} --type=short_educational"
            START_STAGE=10  # Skip remaining stages
        fi
    fi

    if [ $START_STAGE -le 8 ]; then
        echo "📤 Uploading all videos..."

        # Upload full video
        if [ -f "${RUN_DIR}/full.mp4" ]; then
            echo "  Uploading full video..."
            ./upload_to_youtube.sh --run="${RUN_TIMESTAMP}" --type=full --privacy=unlisted
            FULL_ID=$(cat "${RUN_DIR}/video_id_full.txt" 2>/dev/null || echo "")
        fi

        # Upload hook short
        if [ -f "${RUN_DIR}/short_hook.mp4" ]; then
            echo "  Uploading hook short..."
            ./upload_to_youtube.sh --run="${RUN_TIMESTAMP}" --type=short_hook --privacy=unlisted
            HOOK_ID=$(cat "${RUN_DIR}/video_id_short_hook.txt" 2>/dev/null || echo "")
        fi

        # Upload educational short
        if [ -f "${RUN_DIR}/short_educational.mp4" ]; then
            echo "  Uploading educational short..."
            ./upload_to_youtube.sh --run="${RUN_TIMESTAMP}" --type=short_educational --privacy=unlisted
            EDU_ID=$(cat "${RUN_DIR}/video_id_short_educational.txt" 2>/dev/null || echo "")
        fi

        echo "✅ All uploads complete"
        echo ""
    fi
fi

# Stage 9: Cross-Link Videos
if [ $START_STAGE -le 9 ] && [ -n "$FULL_ID" ] && [ -n "$HOOK_ID" ] && [ -n "$EDU_ID" ]; then
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}Stage 9/9: Cross-Link Videos${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

    echo "🔗 Cross-linking video descriptions..."
    if python3 agents/crosslink_videos.py "$FULL_ID" "$HOOK_ID" "$EDU_ID"; then
        echo "✅ Cross-linking complete"
    else
        echo -e "${YELLOW}⚠️  Cross-linking failed${NC}"
    fi
    echo ""
fi

# Success!
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}✅ Pipeline Complete!${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# Show generated videos
if [ -f "${RUN_DIR}/full.mp4" ]; then
    echo -e "${GREEN}📹 Videos Generated:${NC}"
    echo "  - ${RUN_DIR}/full.mp4 (Full horizontal video)"
    if [ -f "${RUN_DIR}/short_hook.mp4" ]; then
        echo "  - ${RUN_DIR}/short_hook.mp4 (Hook short)"
    fi
    if [ -f "${RUN_DIR}/short_educational.mp4" ]; then
        echo "  - ${RUN_DIR}/short_educational.mp4 (Educational short)"
    fi
else
    echo -e "${GREEN}📹 Final video: ${RUN_DIR}/final_video.mp4${NC}"
fi
echo ""

# Show upload results if available
if [ -f "${RUN_DIR}/upload_results.json" ]; then
    echo -e "${GREEN}🔗 YouTube URLs:${NC}"
    python3 -c "import json; r=json.load(open('${RUN_DIR}/upload_results.json')); print(f\"  Full: {r['full_video']['url']}\"); print(f\"  Hook: {r['hook_short']['url']}\"); print(f\"  Educational: {r['educational_short']['url']}\")"
    echo ""
fi

echo "Generated files:"
echo "  - ${RUN_DIR}/research.json       (research data)"
echo "  - ${RUN_DIR}/lyrics.txt          (song lyrics)"
echo "  - ${RUN_DIR}/song.mp3            (AI-generated music)"
echo "  - ${RUN_DIR}/media_plan.json     (shot list)"
if [ -f "${RUN_DIR}/segments.json" ]; then
    echo "  - ${RUN_DIR}/segments.json       (segment analysis)"
fi
echo ""

echo "Next steps:"
if [ -f "${RUN_DIR}/full.mp4" ]; then
    echo "  - Preview: open ${RUN_DIR}/full.mp4"
    echo "  - Preview shorts: open ${RUN_DIR}/short_hook.mp4"
else
    echo "  - Preview: open ${RUN_DIR}/final_video.mp4"
fi
echo "  - Edit in iMovie if needed"
if [ ! -f "${RUN_DIR}/upload_results.json" ]; then
    echo "  - Upload: ./upload_to_youtube.sh --run=${RUN_TIMESTAMP} --type=full"
fi
echo ""
echo -e "${BLUE}Cost estimate for this pipeline run: ~\$0.02-\$0.04${NC}"
