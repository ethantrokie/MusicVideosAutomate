#!/Users/ethantrokie/SoftwareDevProjects/MusicVideosAutomate/venv/bin/python3
"""
YouTube channel selection helper.
Lists channels and uploads to specific channel by handle.
"""

import os
import sys
import json
import pickle
from pathlib import Path
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.auth.exceptions import RefreshError


SCOPES = [
    'https://www.googleapis.com/auth/youtube.force-ssl'
]


def get_authenticated_service():
    """Authenticate and return YouTube API service."""
    creds = None
    token_path = Path('config/youtube_token.pickle')
    creds_path = Path('config/youtube_credentials.json')

    if token_path.exists():
        with open(token_path, 'rb') as token:
            creds = pickle.load(token)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except RefreshError as e:
                # Token has been revoked or expired, need to re-authenticate
                # Check if running in automated mode (no terminal)
                import sys
                if not sys.stdin.isatty():
                    # Automated mode - cannot re-authenticate
                    print("=" * 80)
                    print("❌ YOUTUBE OAUTH TOKEN EXPIRED OR REVOKED")
                    print("=" * 80)
                    print("The automated pipeline cannot re-authenticate without manual intervention.")
                    print("The refresh token has expired and requires interactive browser authentication.")
                    print("")
                    print("To fix this issue:")
                    print("  1. Delete the expired token:")
                    print("     rm config/youtube_token.pickle")
                    print("")
                    print("  2. Run an interactive upload to re-authenticate:")
                    print("     ./upload_to_youtube.sh outputs/runs/<latest_run>/full.mp4")
                    print("")
                    print("  3. Complete the browser OAuth flow when prompted")
                    print("")
                    print("  4. The new token will be saved and future automated runs will work")
                    print("=" * 80)
                    raise Exception("YouTube token expired - manual re-authentication required") from e
                else:
                    # Interactive mode - can re-authenticate
                    print("  ⚠️  Refresh token expired/revoked, re-authenticating...")
                    flow = InstalledAppFlow.from_client_secrets_file(
                        str(creds_path), SCOPES)
                    creds = flow.run_local_server(port=0)
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                str(creds_path), SCOPES)
            creds = flow.run_local_server(port=0)

        with open(token_path, 'wb') as token:
            pickle.dump(creds, token)

    return build('youtube', 'v3', credentials=creds)


def list_channels(youtube):
    """List all channels for authenticated user."""
    request = youtube.channels().list(
        part='snippet,contentDetails',
        mine=True
    )
    response = request.execute()

    channels = []
    for item in response.get('items', []):
        channels.append({
            'id': item['id'],
            'title': item['snippet']['title'],
            'handle': item['snippet'].get('customUrl', 'N/A')
        })

    return channels


def get_channel_id_by_handle(youtube, handle):
    """Get channel ID by handle (e.g., @LearningScienceMusic)."""
    channels = list_channels(youtube)

    for channel in channels:
        if channel['handle'] == handle or f"@{channel['handle']}" == handle:
            return channel['id']

    raise ValueError(f"Channel with handle '{handle}' not found. Available: {channels}")


def upload_video(youtube, video_path, title, description, category, privacy, channel_id=None):
    """Upload video to YouTube."""
    # YouTube title limit is 100 characters
    if len(title) > 100:
        print(f"  ⚠️  Title too long ({len(title)} chars), truncating to 100...")
        title = title[:97] + "..."

    body = {
        'snippet': {
            'title': title,
            'description': description,
            'categoryId': category
        },
        'status': {
            'privacyStatus': privacy
        }
    }

    # If channel_id provided, set it (though mine=True should handle this)
    if channel_id:
        body['snippet']['channelId'] = channel_id

    media = MediaFileUpload(video_path, chunksize=-1, resumable=True)

    request = youtube.videos().insert(
        part=','.join(body.keys()),
        body=body,
        media_body=media
    )

    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            print(f"  Uploaded {int(status.progress() * 100)}%")

    return response['id']


def main():
    """Main CLI interface."""
    import argparse

    parser = argparse.ArgumentParser(description='YouTube channel helper')
    parser.add_argument('--list-channels', action='store_true',
                       help='List available channels')
    parser.add_argument('--channel', type=str,
                       help='Channel handle (e.g., @LearningScienceMusic)')
    parser.add_argument('--video', type=str,
                       help='Path to video file')
    parser.add_argument('--title', type=str,
                       help='Video title')
    parser.add_argument('--description', type=str, default='',
                       help='Video description')
    parser.add_argument('--category', type=str, default='27',
                       help='Category ID (27=Education)')
    parser.add_argument('--privacy', type=str, default='private',
                       choices=['public', 'private', 'unlisted'],
                       help='Privacy status')

    args = parser.parse_args()

    # Authenticate
    youtube = get_authenticated_service()

    # List channels
    if args.list_channels:
        channels = list_channels(youtube)
        print("Available channels:")
        for ch in channels:
            print(f"  - {ch['title']} ({ch['handle']}) [ID: {ch['id']}]")
        return

    # Upload video
    if args.video and args.title:
        # Get channel ID if handle provided
        channel_id = None
        if args.channel:
            channel_id = get_channel_id_by_handle(youtube, args.channel)
            print(f"Uploading to channel: {args.channel} (ID: {channel_id})")

        video_id = upload_video(
            youtube,
            args.video,
            args.title,
            args.description,
            args.category,
            args.privacy,
            channel_id
        )
        print(f"✅ Video uploaded: https://youtube.com/watch?v={video_id}")

        # Return video ID for scripting
        return video_id

    parser.print_help()


if __name__ == '__main__':
    main()
