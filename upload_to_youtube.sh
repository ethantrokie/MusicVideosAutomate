#!/bin/bash

# YouTube Upload Script
# Manually uploads final video to YouTube with metadata

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}================================${NC}"
echo -e "${BLUE}  YouTube Upload Tool${NC}"
echo -e "${BLUE}================================${NC}\n"

# Parse arguments
RUN_DIR=""
PRIVACY="unlisted"  # Default to unlisted for safety

for arg in "$@"; do
    case $arg in
        --run=*)
            RUN_DIR="${arg#*=}"
            ;;
        --privacy=*)
            PRIVACY="${arg#*=}"
            ;;
        --help)
            echo "Usage: ./upload_to_youtube.sh [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --run=TIMESTAMP        Upload specific run (e.g., 20250116_143025)"
            echo "  --privacy=STATUS       Privacy status: public, unlisted, private (default: unlisted)"
            echo "  --help                 Show this help message"
            echo ""
            echo "Examples:"
            echo "  ./upload_to_youtube.sh                           # Upload latest run as unlisted"
            echo "  ./upload_to_youtube.sh --privacy=public          # Upload latest as public"
            echo "  ./upload_to_youtube.sh --run=20250116_143025     # Upload specific run"
            exit 0
            ;;
    esac
done

# Determine which run to upload
if [ -z "$RUN_DIR" ]; then
    # Use latest run via symlink
    if [ -L "outputs/current" ]; then
        # Read the symlink target (relative path like "runs/20251117_113254")
        SYMLINK_TARGET=$(readlink "outputs/current")
        RUN_TIMESTAMP=$(basename "$SYMLINK_TARGET")
        RUN_DIR="outputs/runs/${RUN_TIMESTAMP}"
        echo -e "${YELLOW}📂 Using latest run: ${RUN_TIMESTAMP}${NC}\n"
    else
        echo -e "${RED}❌ Error: No runs found. Run the pipeline first.${NC}"
        exit 1
    fi
else
    # Use specified run
    RUN_TIMESTAMP="$RUN_DIR"
    RUN_DIR="outputs/runs/${RUN_DIR}"
    echo -e "${YELLOW}📂 Using run: ${RUN_TIMESTAMP}${NC}\n"
fi

# Verify run directory exists
if [ ! -d "$RUN_DIR" ]; then
    echo -e "${RED}❌ Error: Run directory not found: ${RUN_DIR}${NC}"
    exit 1
fi

# Verify video exists
VIDEO_PATH="${RUN_DIR}/final_video.mp4"
if [ ! -f "$VIDEO_PATH" ]; then
    echo -e "${RED}❌ Error: Video not found at ${VIDEO_PATH}${NC}"
    echo -e "${YELLOW}💡 Tip: Run the pipeline first or check if video assembly completed successfully.${NC}"
    exit 1
fi

# Load metadata from research.json
RESEARCH_PATH="${RUN_DIR}/research.json"
if [ ! -f "$RESEARCH_PATH" ]; then
    echo -e "${RED}❌ Error: research.json not found at ${RESEARCH_PATH}${NC}"
    exit 1
fi

# Extract topic and key facts using Python
METADATA=$(python3 << PYMETA
import json
import sys

try:
    with open('${RESEARCH_PATH}') as f:
        research = json.load(f)

    topic = research.get('topic', 'Educational Video')
    key_facts = research.get('key_facts', [])

    # Create title from topic (capitalize first letter of each word)
    title = topic.title() if topic else 'Educational Video'

    # Create a more descriptive summary from first few facts
    if key_facts:
        # Take first 2-3 facts and combine them
        summary_facts = key_facts[:3]
        description = ' '.join(summary_facts)
        # Limit to ~300 characters for description
        if len(description) > 300:
            description = description[:297] + '...'
    else:
        description = f"An educational video exploring {topic}"

    print(f"{title}|||{description}")
except Exception as e:
    print("Educational Video|||Learn something new today!", file=sys.stderr)
    sys.exit(0)
PYMETA
)

# Parse metadata (|||  = 3 pipes as separator)
TITLE=$(echo "$METADATA" | cut -d'|' -f1)
FACT_DESCRIPTION=$(echo "$METADATA" | cut -d'|' -f4)

# Generate enhanced description with hashtags
DESCRIPTION="${FACT_DESCRIPTION}

#education #learning #science #shorts #educational #stem #knowledge #facts #learnontiktok #edutok"

# Show upload details
echo -e "${GREEN}📹 Video Details:${NC}"
echo -e "  Path:        ${VIDEO_PATH}"
echo -e "  Title:       ${TITLE}"
echo -e "  Privacy:     ${PRIVACY}"
echo -e "  Description: ${DESCRIPTION:0:100}..."
echo ""

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo -e "${RED}❌ Error: Virtual environment not found${NC}"
    echo -e "${YELLOW}Run ./setup.sh first to create the virtual environment${NC}"
    exit 1
fi

# Activate virtual environment
source venv/bin/activate

# Check if Google API libraries are installed
echo -e "${BLUE}Checking dependencies...${NC}"
python3 -c "import google.oauth2.credentials" 2>/dev/null
if [ $? -ne 0 ]; then
    echo -e "${YELLOW}Installing YouTube API dependencies...${NC}\n"
    pip install --upgrade google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client
    echo -e "${GREEN}✅ Dependencies installed${NC}\n"
fi

# Check for YouTube credentials
CREDENTIALS_PATH="config/youtube_credentials.json"
if [ ! -f "$CREDENTIALS_PATH" ]; then
    echo -e "${YELLOW}⚠️  YouTube credentials not found at ${CREDENTIALS_PATH}${NC}"
    echo ""
    echo -e "${BLUE}📋 Setup Instructions:${NC}"
    echo "1. Go to https://console.cloud.google.com/"
    echo "2. Create a new project (or select existing)"
    echo "3. Enable YouTube Data API v3"
    echo "4. Create OAuth 2.0 credentials (Desktop app)"
    echo "5. Download credentials JSON"
    echo "6. Save as: config/youtube_credentials.json"
    echo ""
    echo -e "${YELLOW}Once you have credentials, run this script again.${NC}"
    exit 1
fi

# Confirm upload
echo -e "${YELLOW}⚠️  Ready to upload to YouTube as '${PRIVACY}'${NC}"
read -p "Continue? (y/N): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${YELLOW}Upload cancelled.${NC}"
    exit 0
fi

echo ""
echo -e "${BLUE}📤 Uploading to YouTube...${NC}"

# Upload using Python script with Google API
python3 << EOF
import os
import pickle
from pathlib import Path
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# Scopes for YouTube upload
SCOPES = ['https://www.googleapis.com/auth/youtube.upload']

def get_authenticated_service():
    creds = None
    token_path = Path('config/youtube_token.pickle')

    # Load saved credentials
    if token_path.exists():
        with open(token_path, 'rb') as token:
            creds = pickle.load(token)

    # Refresh or get new credentials
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                '${CREDENTIALS_PATH}', SCOPES)
            creds = flow.run_local_server(port=0)

        # Save credentials for next run
        with open(token_path, 'wb') as token:
            pickle.dump(creds, token)

    return build('youtube', 'v3', credentials=creds)

def upload_video(youtube, video_path, title, description, privacy):
    body = {
        'snippet': {
            'title': title,
            'description': description,
            'categoryId': '27',  # Education category
        },
        'status': {
            'privacyStatus': privacy,
            'selfDeclaredMadeForKids': False
        }
    }

    media = MediaFileUpload(video_path, resumable=True)

    request = youtube.videos().insert(
        part='snippet,status',
        body=body,
        media_body=media
    )

    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            print(f"  Upload progress: {int(status.progress() * 100)}%")

    return response

try:
    youtube = get_authenticated_service()
    response = upload_video(
        youtube,
        '${VIDEO_PATH}',
        '''${TITLE}''',
        '''${DESCRIPTION}''',
        '${PRIVACY}'
    )

    video_id = response['id']
    print(f"\n✅ Upload successful!")
    print(f"🎬 Video ID: {video_id}")
    print(f"🔗 Watch: https://www.youtube.com/watch?v={video_id}")
    print(f"📝 Studio: https://studio.youtube.com/video/{video_id}/edit")

except Exception as e:
    print(f"\n❌ Upload failed: {e}")
    exit(1)
EOF

UPLOAD_STATUS=$?

if [ $UPLOAD_STATUS -ne 0 ]; then
    echo ""
    echo -e "${RED}❌ Upload failed${NC}"
    exit 1
fi
