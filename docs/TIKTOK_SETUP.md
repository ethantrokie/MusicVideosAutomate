# TikTok Integration Setup Guide

This guide walks you through setting up TikTok uploads for the automated video pipeline.

## Overview

The pipeline now supports uploading videos to both YouTube and TikTok simultaneously:
- **Full video** (16:9, ~180s) → YouTube + TikTok
- **Hook short** (9:16, ~30s) → YouTube Shorts + TikTok
- **Educational short** (9:16, ~30s) → YouTube Shorts only

Videos are cross-linked across platforms in their descriptions.

## Prerequisites

1. **TikTok Developer Account**
   - Sign up at https://developers.tiktok.com
   - Create a new app in the developer portal
   - App must have "Content Posting API" access

2. **Python Dependencies**
   - The `requests` library is required (already added to requirements.txt)
   - Install with: `pip install -r requirements.txt`

## Step 1: Get TikTok API Credentials

1. Go to https://developers.tiktok.com/apps
2. Create a new app or select an existing one
3. Navigate to "Manage apps" → Your app → "Client Key"
4. Copy your **Client Key** and **Client Secret**

## Step 2: Configure Credentials

1. Copy the credentials template:
   ```bash
   cp config/tiktok_credentials.json.template config/tiktok_credentials.json
   ```

2. Edit `config/tiktok_credentials.json` with your credentials:
   ```json
   {
     "client_key": "YOUR_CLIENT_KEY_HERE",
     "client_secret": "YOUR_CLIENT_SECRET_HERE",
     "redirect_uri": "http://localhost:8080/callback"
   }
   ```

   **Note**: The redirect URI must match exactly what you configured in the TikTok developer portal.

## Step 3: Authenticate

Run the authentication flow to obtain OAuth tokens:

```bash
./automation/tiktok_uploader.py --auth
```

This will:
1. Open your browser to TikTok's authorization page
2. Start a local callback server on port 8080
3. Save your access token and refresh token to `config/tiktok_token.pickle`

**Important**: You only need to do this once. Tokens are automatically refreshed when they expire.

## Step 4: Configure Platform Settings

Edit `automation/config/automation_config.json` to enable TikTok uploads:

```json
{
  "tiktok": {
    "enabled": true,
    "username": "@learningsciencemusic",
    "privacy_status": "public_to_everyone",
    "credentials_path": "config/tiktok_credentials.json"
  }
}
```

**Privacy Options**:
- `public_to_everyone` - Public to all TikTok users
- `mutual_follow_friends` - Friends only
- `self_only` - Private (only you can see)

## Step 5: Test Upload

Test the TikTok upload manually:

```bash
# Upload a specific run's full video
./upload_to_tiktok.sh --run=20231125_120000 --type=full

# Upload the hook short
./upload_to_tiktok.sh --run=20231125_120000 --type=short_hook
```

## How It Works

### Pipeline Integration

The main pipeline (`pipeline.sh`) now includes TikTok uploads:

**Stage 8: Upload Videos**
1. Uploads to YouTube (full, hook short, educational short)
2. If TikTok is enabled, uploads to TikTok (full, hook short)
3. TikTok failures are non-fatal (won't stop YouTube uploads)

**Stage 9: Cross-Link Videos**
- YouTube descriptions include TikTok links
- TikTok captions reference YouTube channel
- Creates unified `upload_results.json` with both platforms

### Video ID Tracking

After uploads, video IDs are saved in the run directory:
- `video_id_full.txt` - YouTube full video ID
- `video_id_short_hook.txt` - YouTube hook short ID
- `tiktok_video_id_full.txt` - TikTok full video ID
- `tiktok_video_id_short_hook.txt` - TikTok hook short ID

### Upload Results Structure

`upload_results.json` contains nested platform data:

```json
{
  "youtube": {
    "full_video": {"id": "...", "url": "..."},
    "hook_short": {"id": "...", "url": "..."},
    "educational_short": {"id": "...", "url": "..."}
  },
  "tiktok": {
    "full_video": {"id": "...", "url": "..."},
    "hook_short": {"id": "...", "url": "..."}
  }
}
```

## Troubleshooting

### Authentication Issues

**Problem**: "Authorization timeout - no code received"
- **Solution**: Check that port 8080 is not in use. Try closing other applications.

**Problem**: "Token refresh failed"
- **Solution**: Delete `config/tiktok_token.pickle` and re-run `./automation/tiktok_uploader.py --auth`

### Upload Issues

**Problem**: "Video upload failed: Invalid format"
- **Solution**: TikTok requires MP4 format with H.264 codec. Our pipeline creates compatible videos.

**Problem**: "Upload succeeded but no video ID returned"
- **Solution**: TikTok processing can take time. Check your TikTok account manually after a few minutes.

### Configuration Issues

**Problem**: Pipeline skips TikTok uploads
- **Solution**: Verify `"enabled": true` in `automation_config.json` under the `tiktok` section

**Problem**: TikTok uploads fail but pipeline continues
- **Solution**: This is expected behavior! TikTok failures are non-fatal to avoid blocking YouTube uploads.

## Daily Automation

When using `automation/daily_pipeline.sh`, TikTok uploads happen automatically if enabled:

1. Pipeline generates videos
2. Uploads to YouTube
3. Uploads to TikTok (if enabled)
4. Cross-links all videos
5. Sends notification with both YouTube and TikTok URLs

Notification example:
```
✅ Daily videos published!
Topic: How Rockets Work
YouTube: https://youtube.com/watch?v=abc123
TikTok (full): https://tiktok.com/@learningsciencemusic/video/7123456...
TikTok (hook): https://tiktok.com/@learningsciencemusic/video/7456789...
Status: public (multi-platform with cross-linking)
```

## API Limits

TikTok API has rate limits:
- **Video uploads**: 500 per day per app
- **Token refresh**: Handled automatically

For daily automation (1-2 videos/day), you won't hit these limits.

## Security Notes

1. **Never commit credentials**: `config/tiktok_credentials.json` and `config/tiktok_token.pickle` are in `.gitignore`
2. **Token storage**: OAuth tokens are stored securely in pickle format
3. **HTTPS redirect**: For production, use HTTPS redirect URI (requires domain)

## Additional Resources

- [TikTok Content Posting API Docs](https://developers.tiktok.com/doc/content-posting-api-get-started)
- [TikTok Developer Portal](https://developers.tiktok.com)
- [OAuth 2.0 Authorization Flow](https://developers.tiktok.com/doc/login-kit-web)
