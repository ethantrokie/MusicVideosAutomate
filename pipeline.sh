#!/bin/bash

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Error logging function
log_error() {
    local message="$1"
    echo -e "${RED}❌ ERROR: ${message}${NC}" >&2
    # Also log to file if LOG_FILE is set
    if [ -n "$LOG_FILE" ]; then
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] ERROR: ${message}" >> "$LOG_FILE"
    fi
}

# Load config for privacy setting (used in express mode)
CONFIG_FILE="automation/config/automation_config.json"
if [ -f "$CONFIG_FILE" ]; then
    YOUTUBE_PRIVACY=$(jq -r '.youtube.privacy_status' "$CONFIG_FILE" 2>/dev/null || echo "unlisted")
    YOUTUBE_CHANNEL=$(jq -r '.youtube.channel_handle' "$CONFIG_FILE" 2>/dev/null || echo "")
else
    YOUTUBE_PRIVACY="unlisted"
    YOUTUBE_CHANNEL=""
fi

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
    echo -e "${BLUE}Stage 1/7: Research${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    ./agents/1_research.sh
    if [ $? -ne 0 ]; then
        echo -e "${RED}❌ Research failed${NC}"
        exit 1
    fi
    echo ""

    # Stage 1.5: URL Validation (REMOVED - obsolete with lyric-based media search)
    # Media URLs are now validated in Stage 2.5 during lyric-based media search
fi

# Stage 2: Lyrics
if [ $START_STAGE -le 2 ]; then
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}Stage 2/7: Lyrics Generation${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo "✂️ Pruning context for lyricist..."
    python3 agents/context_pruner.py lyricist
    ./agents/2_lyrics.sh
    if [ $? -ne 0 ]; then
        echo -e "${RED}❌ Lyrics generation failed${NC}"
        exit 1
    fi
    echo ""
fi

# Stage 2.5: Lyric-Based Media Search
if [ $START_STAGE -le 3 ]; then
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}Stage 2.5/7: Lyric-Based Media Search${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    ./agents/3.5_lyric_media_search.sh
    if [ $? -ne 0 ]; then
        echo -e "${RED}❌ Lyric media search failed${NC}"
        exit 1
    fi
    echo ""
fi

# Stage 2.6: Visual Ranking
if [ $START_STAGE -le 3 ]; then
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}Stage 2.6/7: Visual Ranking${NC}"
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

# Stage 3: Music
if [ $START_STAGE -le 3 ]; then
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}Stage 3/7: Music Composition${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    ./agents/3_compose.py
    if [ $? -ne 0 ]; then
        echo -e "${RED}❌ Music composition failed${NC}"
        exit 1
    fi

    # Stage 3.5: Create phrase groups for curator
    echo "📝 Creating phrase groups from word-level timestamps..."
    ./agents/3_5_create_phrase_groups.sh
    if [ $? -ne 0 ]; then
        echo -e "${RED}❌ Phrase grouping failed${NC}"
        exit 1
    fi
    echo ""
fi

# Stage 4: Segment Analysis (for multi-format videos)
if [ $START_STAGE -le 4 ]; then
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}Stage 4/7: Segment Analysis${NC}"
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
    echo -e "${BLUE}Stage 5/7: Media Curation${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

    # Get audio duration from segments.json
    AUDIO_DURATION=$(./venv/bin/python3 -c "
import json
import os
segments_file = os.path.join(os.getenv('OUTPUT_DIR', 'outputs/current'), 'segments.json')
try:
    with open(segments_file) as f:
        segments = json.load(f)
        # Use full duration from segments
        print(int(segments.get('full', {}).get('duration', 180)))
except:
    print(180)  # Fallback to 180s
")

    echo "  📏 Audio duration: ${AUDIO_DURATION}s"
    echo "✂️ Pruning context for curator..."
    python3 agents/context_pruner.py curator
    ./agents/4_curate_media.sh --duration ${AUDIO_DURATION}
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
        echo -e "${YELLOW}Express Mode: Smart Media Processing${NC}"
        echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
        
        # Video LLM Enhancements (if available)
        if [ -d "venv_video_llm" ]; then
            echo "🤖 Video LLM enhancements enabled"
            
            # Step 1: Enhance media descriptions with video LLM
            echo "🔍 Enhancing media descriptions with Video LLM..."
            source venv_video_llm/bin/activate
            if python3 agents/analyze_downloaded_media.py 2>/dev/null; then
                echo "  ✅ Media descriptions enhanced"
            else
                echo "  ⚠️ Enhancement skipped (non-fatal)"
            fi
            
            # Step 2: Quality filter media
            echo "🔍 Quality filtering media..."
            FILTER_EXIT=0
            if python3 agents/filter_media_quality.py 2>/dev/null; then
                echo "  ✅ Quality filtering complete"
            else
                FILTER_EXIT=$?
                if [ $FILTER_EXIT -eq 1 ]; then
                    # CRITICAL: All clips rejected - trigger recovery
                    echo "  ❌ CRITICAL: All clips rejected by quality filter"
                    echo "  🔄 Attempting recovery: Re-running curator with improved search terms..."

                    if python3 agents/retry_curator_with_better_terms.py; then
                        echo "  ✅ Recovery successful, re-running quality filter with threshold=4..."
                        if python3 agents/filter_media_quality.py --threshold 4 2>/dev/null; then
                            echo "  ✅ Quality filtering complete (relaxed threshold)"
                            FILTER_EXIT=0
                        else
                            RECOVERY_EXIT=$?
                            if [ $RECOVERY_EXIT -eq 1 ]; then
                                echo "  ❌ FATAL: Still no approved clips after recovery"
                                log_error "Quality filter rejected all clips even after recovery"
                                deactivate
                                exit 1
                            else
                                echo "  ⚠️ Few clips approved after recovery, continuing"
                                FILTER_EXIT=0
                            fi
                        fi
                    else
                        echo "  ❌ Recovery failed"
                        log_error "Failed to recover from quality filter rejection"
                        deactivate
                        exit 1
                    fi
                elif [ $FILTER_EXIT -eq 2 ]; then
                    echo "  ⚠️ Few clips approved, continuing with available media"
                else
                    echo "  ⚠️ Quality filter error (continuing with all media)"
                    FILTER_EXIT=999  # Mark as skipped
                fi
            fi
            deactivate
            source venv/bin/activate
        else
            echo "⏭️ Video LLM not available, using standard express mode"
            FILTER_EXIT=999  # Mark as skipped
        fi

        # Use quality filter results if available, otherwise fallback to auto-approve
        if [ -f "${OUTPUT_DIR}/quality_filter_results.json" ] && [ $FILTER_EXIT -ne 999 ]; then
            echo "📋 Using quality-filtered media..."
            python3 << EOF
import json
import os

output_dir = os.getenv('OUTPUT_DIR', 'outputs')

# Load quality filter results
with open(f'{output_dir}/quality_filter_results.json') as f:
    filter_results = json.load(f)

# Load media plan for shot metadata
with open(f'{output_dir}/media_plan.json') as f:
    plan = json.load(f)

approved_clips = filter_results.get('approved', [])

if not approved_clips:
    print("⚠️ No approved clips in filter results, this should not happen")
    exit(1)

# Create approved media by matching filtered clips with shot plan
approved_shots = []
for clip in approved_clips:
    shot_num = clip.get('shot_number')
    # Find corresponding shot in plan
    matching_shots = [s for s in plan['shot_list'] if s['shot_number'] == shot_num]
    if matching_shots:
        shot = matching_shots[0].copy()
        shot['local_path'] = clip['local_path']
        shot['quality_score'] = clip.get('quality_score', 0)
        if 'enhanced_description' in clip:
            shot['enhanced_description'] = clip['enhanced_description']
        approved_shots.append(shot)

# Update plan with only approved shots
plan['shot_list'] = approved_shots
plan['quality_filtered'] = True
plan['original_count'] = len(plan.get('shot_list', []))
plan['approved_count'] = len(approved_shots)

with open(f'{output_dir}/approved_media.json', 'w') as f:
    json.dump(plan, f, indent=2)

print(f"✅ Using {len(approved_shots)} quality-approved clips (rejected {filter_results.get('threshold', 0)} low quality + {len(filter_results.get('ads_rejected', []))} ads)")
EOF
        else
            echo "⏭️ Quality filter not available, auto-approving all media..."
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
        # Also copy enhanced_description if available
        if 'enhanced_description' in downloaded[0]:
            shot['enhanced_description'] = downloaded[0]['enhanced_description']

with open(f'{output_dir}/approved_media.json', 'w') as f:
    json.dump(plan, f, indent=2)

print("✅ Auto-approved all downloaded media")
EOF
        fi
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
                /Users/ethantrokie/.npm-global/bin/claude -p "$(cat $TEMP_GAP_PROMPT)" --model claude-sonnet-4-5 --dangerously-skip-permissions

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
    # Initialize media_suggestions if it doesn't exist
    if 'media_suggestions' not in research:
        research['media_suggestions'] = []
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

                    # Download the gap-fill media
                    if [ -f "${OUTPUT_DIR}/gap_fill_media.json" ]; then
                        echo "  📥 Downloading gap-fill media..."

                        # Convert gap_fill_media.json to a temporary shot list for download
                        ./venv/bin/python3 << 'EOF'
import json
import os

output_dir = os.getenv('OUTPUT_DIR', 'outputs')

# Load gap-fill media
with open(f'{output_dir}/gap_fill_media.json') as f:
    gap_data = json.load(f)

# Load current approved_media to get next shot number
approved_path = f'{output_dir}/approved_media.json'
if os.path.exists(approved_path):
    with open(approved_path) as f:
        approved = json.load(f)
    next_shot_num = max([s['shot_number'] for s in approved.get('shot_list', [])]) + 1
else:
    next_shot_num = 1

# Convert gap-fill media to shot list format
gap_media = gap_data.get('gap_fill_media', [])
shot_list = []
for i, media in enumerate(gap_media):
    shot_list.append({
        'shot_number': next_shot_num + i,
        'media_url': media.get('url', ''),
        'media_type': media.get('type', 'video'),
        'source': media.get('source', 'gap_fill'),
        'description': media.get('description', ''),
        'lyrics_match': media.get('concept', ''),
        'transition': 'fade',
        'priority': 'high'
    })

# Create temporary shot list for download
temp_shots = {
    'shot_list': shot_list,
    'total_shots': len(shot_list)
}

with open(f'{output_dir}/gap_fill_shots.json', 'w') as f:
    json.dump(temp_shots, f, indent=2)

print(f'Created {len(shot_list)} gap-fill shots for download')
EOF

                        # Download gap-fill shots
                        if [ -f "${OUTPUT_DIR}/gap_fill_shots.json" ]; then
                            ./venv/bin/python3 agents/download_media.py "${OUTPUT_DIR}/gap_fill_shots.json"

                            # Merge downloaded gap-fill media into approved_media.json
                            ./venv/bin/python3 << 'EOF'
import json
import os
from pathlib import Path

output_dir = os.getenv('OUTPUT_DIR', 'outputs')

# Load approved media
approved_path = f'{output_dir}/approved_media.json'
with open(approved_path) as f:
    approved = json.load(f)

# Load gap-fill shots to see what was downloaded
gap_shots_path = f'{output_dir}/gap_fill_shots.json'
with open(gap_shots_path) as f:
    gap_shots = json.load(f)

# Load manifest to see which ones succeeded
manifest_path = f'{output_dir}/media_manifest.json'
if os.path.exists(manifest_path):
    with open(manifest_path) as f:
        manifest = json.load(f)

    # Add successfully downloaded gap-fill shots to approved_media
    downloaded_nums = {d['shot_number'] for d in manifest.get('downloaded', [])}

    added = 0
    for shot in gap_shots['shot_list']:
        if shot['shot_number'] in downloaded_nums:
            # Add local_path from manifest
            for d in manifest['downloaded']:
                if d['shot_number'] == shot['shot_number']:
                    shot['local_path'] = d['local_path']
                    break

            approved['shot_list'].append(shot)
            added += 1

    if added > 0:
        # Update totals
        approved['total_shots'] = len(approved['shot_list'])

        # Save updated approved_media.json
        with open(approved_path, 'w') as f:
            json.dump(approved, f, indent=2)

        print(f'  ✅ Added {added} gap-fill clips to approved media')
    else:
        print(f'  ⚠️  No gap-fill media was successfully downloaded')
EOF

                            # Clean up temporary file
                            rm -f "${OUTPUT_DIR}/gap_fill_shots.json"
                        fi
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
    if ./venv/bin/python3 -c "import json; c=json.load(open('config/config.json')); print(c.get('video_formats',{}).get('full_video',{}).get('enabled',True))" | grep -q "True"; then
        echo "🎬 Building multi-format videos with format-specific media plans..."
        echo "  • Full video (16:9, 180s) - comprehensive coverage"
        echo "  • Hook short (9:16, 30s) - most engaging segment"
        echo "  • Educational short (9:16, 30s) - key teaching moments"
        ./venv/bin/python3 agents/build_multiformat_videos.py
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

        # 10. Generate Subtitles (Karaoke style for all formats)
        echo "📝 Generating subtitles..."
        if python3 agents/generate_subtitles.py --engine=ffmpeg --type=karaoke --video=full; then
            echo "✅ Full video subtitles generated"
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

        if [ -f "${RUN_DIR}/short_intro.mp4" ]; then
            if python3 agents/generate_subtitles.py --engine=pycaps --type=karaoke --video=short_intro --segment=intro; then
                echo "  ✅ Intro short subtitles applied"
            else
                echo -e "${YELLOW}  ⚠️  Intro short subtitles failed, continuing...${NC}"
            fi
        fi
    else
        echo -e "${YELLOW}⚠️  No multi-format videos found, skipping subtitles${NC}"
    fi
    echo ""
fi

# Stage 7.5: Video Overlays (Title Cards and End Screens)
if [ $START_STAGE -le 8 ] && [ -f "${RUN_DIR}/full.mp4" ]; then
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}Stage 7.5: Adding Video Overlays${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

    # Get video title from research.json
    VIDEO_TITLE=$(python3 -c "import json; data=json.load(open('${RUN_DIR}/research.json')); print(data.get('video_title', 'Educational Video'))" 2>/dev/null || echo "Educational Video")
    echo "  Video title: ${VIDEO_TITLE}"

    # Add overlays to full video
    if [ -f "${RUN_DIR}/full.mp4" ]; then
        echo "  📝 Adding overlays to full video..."
        if ./venv/bin/python3 agents/video_overlays.py --video="${RUN_DIR}/full.mp4" --title="${VIDEO_TITLE}" --type=full; then
            echo "  ✅ Full video overlays added"
        else
            echo -e "${YELLOW}  ⚠️  Full video overlays failed, continuing...${NC}"
        fi
    fi

    # Add overlays to shorts
    if [ -f "${RUN_DIR}/short_hook.mp4" ]; then
        echo "  📝 Adding overlays to hook short..."
        if ./venv/bin/python3 agents/video_overlays.py --video="${RUN_DIR}/short_hook.mp4" --title="${VIDEO_TITLE}" --type=short_hook; then
            echo "  ✅ Hook short overlays added"
        else
            echo -e "${YELLOW}  ⚠️  Hook short overlays failed, continuing...${NC}"
        fi
    fi

    if [ -f "${RUN_DIR}/short_educational.mp4" ]; then
        echo "  📝 Adding overlays to educational short..."
        if ./venv/bin/python3 agents/video_overlays.py --video="${RUN_DIR}/short_educational.mp4" --title="${VIDEO_TITLE}" --type=short_educational; then
            echo "  ✅ Educational short overlays added"
        else
            echo -e "${YELLOW}  ⚠️  Educational short overlays failed, continuing...${NC}"
        fi
    fi

    if [ -f "${RUN_DIR}/short_intro.mp4" ]; then
        echo "  📝 Adding overlays to intro short..."
        if ./venv/bin/python3 agents/video_overlays.py --video="${RUN_DIR}/short_intro.mp4" --title="${VIDEO_TITLE}" --type=short_intro; then
            echo "  ✅ Intro short overlays added"
        else
            echo -e "${YELLOW}  ⚠️  Intro short overlays failed, continuing...${NC}"
        fi
    fi

    echo ""
fi

# Stage 7.6: Video LLM Validation and Description Generation
if [ $START_STAGE -le 8 ] && [ -d "venv_video_llm" ] && [ -f "${RUN_DIR}/full.mp4" ]; then
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}Stage 7.6: Video LLM Analysis${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    
    source venv_video_llm/bin/activate
    
    # Validate visual-lyric sync with two-tier recovery
    echo "🔍 Validating visual-lyric synchronization..."
    SYNC_EXIT=0
    if python3 agents/validate_visual_sync.py --video=full 2>/dev/null; then
        echo "  ✅ Sync validation complete"
    else
        SYNC_EXIT=$?
        if [ $SYNC_EXIT -eq 1 ]; then
            # CRITICAL: Very poor sync - attempt recovery
            echo "  ❌ CRITICAL: Very poor visual-lyric sync detected"
            echo "  🔄 Attempting recovery 1/2: Re-running semantic matcher with adjusted parameters..."

            if python3 agents/retry_semantic_matching.py; then
                echo "  ✅ Semantic matching retry complete, re-validating sync..."

                # Re-run sync validation
                if python3 agents/validate_visual_sync.py --video=full 2>/dev/null; then
                    echo "  ✅ Sync improved after semantic matching retry"
                    SYNC_EXIT=0
                else
                    RETRY_EXIT=$?
                    if [ $RETRY_EXIT -eq 1 ]; then
                        # Still critical - trigger full recovery
                        echo "  ❌ Sync still poor after semantic matching retry"
                        echo "  🔄 Attempting recovery 2/2: Re-downloading media with improved search terms..."

                        deactivate
                        source venv/bin/activate

                        if python3 agents/retry_curator_with_better_terms.py; then
                            echo "  ✅ Media re-downloaded, re-running quality filter with threshold=4..."

                            source venv_video_llm/bin/activate
                            if python3 agents/filter_media_quality.py --threshold 4 2>/dev/null; then
                                echo "  ✅ Quality filter passed with new media"

                                # Re-assemble video with new media
                                deactivate
                                source venv/bin/activate

                                echo "  🎬 Re-assembling video with new media..."
                                if python3 agents/5_assemble_video.py; then
                                    echo "  ✅ Video re-assembled"

                                    # Final sync validation
                                    source venv_video_llm/bin/activate
                                    if python3 agents/validate_visual_sync.py --video=full 2>/dev/null; then
                                        echo "  ✅ Sync validation passed after full recovery"
                                        SYNC_EXIT=0
                                    else
                                        FINAL_EXIT=$?
                                        if [ $FINAL_EXIT -eq 1 ]; then
                                            echo "  ❌ FATAL: Sync still critical after full recovery"
                                            log_error "Visual-lyric sync failed even after full recovery"
                                            deactivate
                                            exit 1
                                        else
                                            echo "  ⚠️ Sync acceptable after full recovery (non-critical)"
                                            SYNC_EXIT=0
                                        fi
                                    fi
                                else
                                    echo "  ❌ Video assembly failed after recovery"
                                    log_error "Failed to re-assemble video after media recovery"
                                    deactivate
                                    exit 1
                                fi
                            else
                                echo "  ❌ Quality filter still rejecting media after recovery"
                                log_error "No acceptable media found even after recovery"
                                deactivate
                                exit 1
                            fi
                        else
                            echo "  ❌ Media recovery failed"
                            log_error "Failed to recover media for sync improvement"
                            deactivate
                            exit 1
                        fi
                    else
                        # Retry improved sync to acceptable level (exit code 2 or 0)
                        echo "  ✅ Sync improved to acceptable level"
                        SYNC_EXIT=0
                    fi
                fi
            else
                echo "  ❌ Semantic matching retry failed"
                log_error "Failed to retry semantic matching"
                deactivate
                exit 1
            fi
        elif [ $SYNC_EXIT -eq 2 ]; then
            echo "  ⚠️ Warning: Some segments have weak visual matches (continuing)"
        else
            echo "  ⚠️ Sync validation skipped"
        fi
    fi
    
    # Generate AI descriptions for all videos
    echo "📝 Generating AI video descriptions..."
    for VIDEO_TYPE in full short_hook short_educational short_intro; do
        if [ -f "${RUN_DIR}/${VIDEO_TYPE}.mp4" ]; then
            if python3 agents/generate_video_description.py --video="${VIDEO_TYPE}" --platform=youtube 2>/dev/null; then
                echo "  ✅ ${VIDEO_TYPE} YouTube description generated"
            fi
            if python3 agents/generate_video_description.py --video="${VIDEO_TYPE}" --platform=tiktok 2>/dev/null; then
                echo "  ✅ ${VIDEO_TYPE} TikTok description generated"
            fi
        fi
    done
    
    deactivate
    source venv/bin/activate
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
        if [ -f "${RUN_DIR}/short_intro.mp4" ]; then
            echo "  - Intro short (${RUN_DIR}/short_intro.mp4)"
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
            echo "  ./upload_to_youtube.sh --run=${RUN_TIMESTAMP} --type=short_intro"
            START_STAGE=10  # Skip remaining stages
        fi
    fi

    if [ $START_STAGE -le 8 ]; then
        echo "📤 Uploading all videos..."

        # Build upload args
        UPLOAD_ARGS="--privacy=${YOUTUBE_PRIVACY}"
        if [ -n "$YOUTUBE_CHANNEL" ]; then
            UPLOAD_ARGS="$UPLOAD_ARGS --channel=${YOUTUBE_CHANNEL}"
        fi

        # Upload full video
        if [ -f "${RUN_DIR}/full.mp4" ]; then
            echo "  Uploading full video..."
            ./upload_to_youtube.sh --run="${RUN_TIMESTAMP}" --type=full $UPLOAD_ARGS
            FULL_ID=$(cat "${RUN_DIR}/video_id_full.txt" 2>/dev/null || echo "")
        fi

        # Upload hook short
        if [ -f "${RUN_DIR}/short_hook.mp4" ]; then
            echo "  Uploading hook short..."
            ./upload_to_youtube.sh --run="${RUN_TIMESTAMP}" --type=short_hook $UPLOAD_ARGS
            HOOK_ID=$(cat "${RUN_DIR}/video_id_short_hook.txt" 2>/dev/null || echo "")
        fi

        # Upload educational short
        if [ -f "${RUN_DIR}/short_educational.mp4" ]; then
            echo "  Uploading educational short..."
            ./upload_to_youtube.sh --run="${RUN_TIMESTAMP}" --type=short_educational $UPLOAD_ARGS
            EDU_ID=$(cat "${RUN_DIR}/video_id_short_educational.txt" 2>/dev/null || echo "")
        fi

        # Upload intro short
        if [ -f "${RUN_DIR}/short_intro.mp4" ]; then
            echo "  Uploading intro short..."
            ./upload_to_youtube.sh --run="${RUN_TIMESTAMP}" --type=short_intro $UPLOAD_ARGS
            INTRO_ID=$(cat "${RUN_DIR}/video_id_short_intro.txt" 2>/dev/null || echo "")
        fi

        echo "✅ YouTube uploads complete"
        echo ""

        # Upload to TikTok (if enabled) - via Dropbox + Zapier
        TIKTOK_ENABLED=$(jq -r '.tiktok.enabled // false' "$CONFIG_FILE" 2>/dev/null)
        if [ "$TIKTOK_ENABLED" = "true" ]; then
            echo "📤 Uploading to TikTok via Zapier..."

            # Upload full video to TikTok
            if [ -f "${RUN_DIR}/full.mp4" ]; then
                echo "  Uploading full video to TikTok..."
                if ./venv/bin/python3 agents/6_upload_dropbox_zapier.py --run="${RUN_TIMESTAMP}" --type=full; then
                    echo "    ✅ TikTok full video uploaded via Zapier"
                else
                    echo -e "    ${YELLOW}⚠️  TikTok full video upload failed (non-fatal)${NC}"
                fi
            fi

            # Upload hook short to TikTok
            if [ -f "${RUN_DIR}/short_hook.mp4" ]; then
                echo "  Uploading hook short to TikTok..."
                if ./venv/bin/python3 agents/6_upload_dropbox_zapier.py --run="${RUN_TIMESTAMP}" --type=short_hook; then
                    echo "    ✅ TikTok hook short uploaded via Zapier"
                else
                    echo -e "    ${YELLOW}⚠️  TikTok hook short upload failed (non-fatal)${NC}"
                fi
            fi

            # Upload educational short to TikTok
            if [ -f "${RUN_DIR}/short_educational.mp4" ]; then
                echo "  Uploading educational short to TikTok..."
                if ./venv/bin/python3 agents/6_upload_dropbox_zapier.py --run="${RUN_TIMESTAMP}" --type=short_educational; then
                    echo "    ✅ TikTok educational short uploaded via Zapier"
                else
                    echo -e "    ${YELLOW}⚠️  TikTok educational short upload failed (non-fatal)${NC}"
                fi
            fi

            # Upload intro short to TikTok
            if [ -f "${RUN_DIR}/short_intro.mp4" ]; then
                echo "  Uploading intro short to TikTok..."
                if ./venv/bin/python3 agents/6_upload_dropbox_zapier.py --run="${RUN_TIMESTAMP}" --type=short_intro; then
                    echo "    ✅ TikTok intro short uploaded via Zapier"
                else
                    echo -e "    ${YELLOW}⚠️  TikTok intro short upload failed (non-fatal)${NC}"
                fi
            fi

            echo "✅ TikTok uploads complete (via Zapier)"
        else
            echo "⏭️  TikTok uploads disabled in config"
        fi
        echo ""
    fi
fi

# Stage 9: Cross-Link Videos
if [ $START_STAGE -le 9 ] && [ -n "$FULL_ID" ] && [ -n "$HOOK_ID" ] && [ -n "$EDU_ID" ]; then
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}Stage 9/9: Cross-Link Videos${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

    echo "🔗 Cross-linking video descriptions..."

    # Build command with optional intro and TikTok IDs
    CROSSLINK_CMD="python3 agents/crosslink_videos.py \"$FULL_ID\" \"$HOOK_ID\" \"$EDU_ID\""
    # Add intro ID if available (required before TikTok IDs due to positional args)
    if [ -n "$INTRO_ID" ]; then
        CROSSLINK_CMD="$CROSSLINK_CMD \"$INTRO_ID\""
    else
        CROSSLINK_CMD="$CROSSLINK_CMD \"\""  # Empty placeholder for positional args
    fi
    if [ -n "$TIKTOK_FULL_ID" ]; then
        CROSSLINK_CMD="$CROSSLINK_CMD \"$TIKTOK_FULL_ID\""
    fi
    if [ -n "$TIKTOK_HOOK_ID" ]; then
        CROSSLINK_CMD="$CROSSLINK_CMD \"$TIKTOK_HOOK_ID\""
    fi

    if eval "$CROSSLINK_CMD"; then
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
    if [ -f "${RUN_DIR}/short_intro.mp4" ]; then
        echo "  - ${RUN_DIR}/short_intro.mp4 (Intro short)"
    fi
else
    echo -e "${GREEN}📹 Final video: ${RUN_DIR}/final_video.mp4${NC}"
fi
echo ""

# Show upload results if available
if [ -f "${RUN_DIR}/upload_results.json" ]; then
    echo -e "${GREEN}🔗 YouTube URLs:${NC}"
    python3 -c "import json; r=json.load(open('${RUN_DIR}/upload_results.json')); print(f\"  Full: {r['youtube']['full_video']['url']}\"); print(f\"  Hook: {r['youtube']['hook_short']['url']}\"); print(f\"  Educational: {r['youtube']['educational_short']['url']}\")"
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
