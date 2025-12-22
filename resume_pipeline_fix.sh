#!/bin/bash
# Temporary script to resume pipeline from subtitle generation
# Run ID: 20251213_090022

set -e
source venv/bin/activate

RUN_TIMESTAMP="20251213_090022"
RUN_DIR="outputs/runs/${RUN_TIMESTAMP}"
export OUTPUT_DIR="${RUN_DIR}"
export PYTHONUNBUFFERED=1

echo "🚀 Resuming pipeline for run: ${RUN_TIMESTAMP}"
echo "------------------------------------------------"

# 1. Generate Subtitles
# Using engine=ffmpeg for all to ensure the new karaoke fix is used
echo "📝 Generating subtitles (Karaoke style)..."

echo "  - Full Video..."
python3 agents/generate_subtitles.py --engine=ffmpeg --type=karaoke --video=full

if [ -f "${RUN_DIR}/short_hook.mp4" ]; then
    echo "  - Hook Short..."
    # Note: Using ffmpeg engine to force new karaoke implementation
    python3 agents/generate_subtitles.py --engine=ffmpeg --type=karaoke --video=short_hook --segment=hook
fi

if [ -f "${RUN_DIR}/short_educational.mp4" ]; then
    echo "  - Educational Short..."
    # Note: Using ffmpeg engine to force new karaoke implementation
    python3 agents/generate_subtitles.py --engine=ffmpeg --type=karaoke --video=short_educational --segment=educational
fi

echo "✅ Subtitles generation complete."
echo ""

# 2. Upload to YouTube
# Re-using logic from pipeline.sh, assuming user wants to upload now
echo "📤 Uploading to YouTube..."

# Load privacy from config or default
# Simplified: defaulting to unlisted as per common defaults in user scripts if not set
YOUTUBE_PRIVACY="unlisted" 

# Upload Full
if [ -f "${RUN_DIR}/full.mp4" ]; then
    echo "  Uploading full video..."
    ./upload_to_youtube.sh --run="${RUN_TIMESTAMP}" --type=full --privacy="${YOUTUBE_PRIVACY}"
    FULL_ID=$(cat "${RUN_DIR}/video_id_full.txt" 2>/dev/null || echo "")
fi

# Upload Hook
if [ -f "${RUN_DIR}/short_hook.mp4" ]; then
    echo "  Uploading hook short..."
    ./upload_to_youtube.sh --run="${RUN_TIMESTAMP}" --type=short_hook --privacy="${YOUTUBE_PRIVACY}"
    HOOK_ID=$(cat "${RUN_DIR}/video_id_short_hook.txt" 2>/dev/null || echo "")
fi

# Upload Educ
if [ -f "${RUN_DIR}/short_educational.mp4" ]; then
    echo "  Uploading educational short..."
    ./upload_to_youtube.sh --run="${RUN_TIMESTAMP}" --type=short_educational --privacy="${YOUTUBE_PRIVACY}"
    EDU_ID=$(cat "${RUN_DIR}/video_id_short_educational.txt" 2>/dev/null || echo "")
fi

echo "✅ YouTube uploads complete."
echo ""

# 3. Upload to TikTok via Dropbox + Zapier
TIKTOK_ENABLED=$(jq -r '.tiktok.enabled // false' config/config.json 2>/dev/null)
if [ "$TIKTOK_ENABLED" = "true" ]; then
    echo "📤 Uploading to TikTok via Zapier..."

    if [ -f "${RUN_DIR}/full.mp4" ]; then
        echo "  Uploading full video to TikTok..."
        if ./venv/bin/python3 agents/6_upload_dropbox_zapier.py --run="${RUN_TIMESTAMP}" --type=full; then
            echo "    ✅ TikTok full video uploaded via Zapier"
        else
            echo "    ⚠️ TikTok full video upload failed (non-fatal)"
        fi
    fi

    if [ -f "${RUN_DIR}/short_hook.mp4" ]; then
        echo "  Uploading hook short to TikTok..."
        if ./venv/bin/python3 agents/6_upload_dropbox_zapier.py --run="${RUN_TIMESTAMP}" --type=short_hook; then
            echo "    ✅ TikTok hook short uploaded via Zapier"
        else
            echo "    ⚠️ TikTok hook short upload failed (non-fatal)"
        fi
    fi

    if [ -f "${RUN_DIR}/short_educational.mp4" ]; then
        echo "  Uploading educational short to TikTok..."
        if ./venv/bin/python3 agents/6_upload_dropbox_zapier.py --run="${RUN_TIMESTAMP}" --type=short_educational; then
            echo "    ✅ TikTok educational short uploaded via Zapier"
        else
            echo "    ⚠️ TikTok educational short upload failed (non-fatal)"
        fi
    fi

    echo "✅ TikTok uploads complete (via Zapier)"
else
    echo "⏭️  TikTok uploads disabled in config"
fi
echo ""

# 4. Cross-Linking
if [ -n "$FULL_ID" ] && [ -n "$HOOK_ID" ] && [ -n "$EDU_ID" ]; then
    echo "🔗 Cross-linking videos..."
    CROSSLINK_CMD="python3 agents/crosslink_videos.py \"$FULL_ID\" \"$HOOK_ID\" \"$EDU_ID\""
    if [ -n "$TIKTOK_FULL_ID" ]; then CROSSLINK_CMD="$CROSSLINK_CMD \"$TIKTOK_FULL_ID\""; fi
    if [ -n "$TIKTOK_HOOK_ID" ]; then CROSSLINK_CMD="$CROSSLINK_CMD \"$TIKTOK_HOOK_ID\""; fi

    eval "$CROSSLINK_CMD" || echo "  ⚠️ Cross-linking failed"
else
    echo "⚠️ Skipping cross-linking (missing some video IDs)"
fi

echo "🎉 Resume complete!"
