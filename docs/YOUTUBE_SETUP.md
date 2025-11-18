# YouTube Upload Setup Guide

This guide walks you through setting up YouTube API credentials for automated uploads.

## Prerequisites

- Google account
- Access to [Google Cloud Console](https://console.cloud.google.com/)

## Step-by-Step Setup

### 1. Create Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Click **Select a Project** → **New Project**
3. Enter project name (e.g., "Educational Video Automation")
4. Click **Create**

### 2. Enable YouTube Data API

1. In your project, go to **APIs & Services** → **Library**
2. Search for "YouTube Data API v3"
3. Click on it and press **Enable**

### 3. Create OAuth 2.0 Credentials

1. Go to **APIs & Services** → **Credentials**
2. Click **+ Create Credentials** → **OAuth client ID**
3. If prompted, configure consent screen:
   - User Type: **External**
   - App name: Your choice (e.g., "Video Uploader")
   - User support email: Your email
   - Developer contact: Your email
   - Click **Save and Continue** through all steps
4. Back on Credentials page, click **+ Create Credentials** → **OAuth client ID**
5. Application type: **Desktop app**
6. Name: Your choice (e.g., "Video Upload Script")
7. Click **Create**

### 4. Download Credentials

1. You'll see a dialog with your credentials
2. Click **Download JSON**
3. Save the file as `youtube_credentials.json`
4. Move it to your project's `config/` directory:
   ```bash
   mv ~/Downloads/client_secret_*.json config/youtube_credentials.json
   ```

### 5. First Upload (OAuth Authorization)

The first time you run the upload script, you'll need to authorize it:

```bash
./upload_to_youtube.sh
```

This will:
1. Open your browser
2. Ask you to sign in to Google
3. Show permissions request (allow the app to upload videos)
4. Redirect back to confirm authorization

After this, credentials are cached and you won't need to authorize again.

## Privacy Settings

The upload script supports three privacy levels:

- `unlisted` (default) - Video is not searchable, only accessible via link
- `private` - Only you can see the video
- `public` - Anyone can find and watch the video

Change privacy with the `--privacy` flag:

```bash
# Upload as public
./upload_to_youtube.sh --privacy=public

# Upload as private
./upload_to_youtube.sh --privacy=private
```

## Troubleshooting

### "Access blocked: This app's request is invalid"

This happens if the OAuth consent screen is not configured correctly.

**Fix:**
1. Go to **APIs & Services** → **OAuth consent screen**
2. Add your Google account email under "Test users"
3. Try uploading again

### "The request cannot be completed because you have exceeded your quota"

YouTube API has daily quotas. Free tier allows ~10,000 units/day, and a video upload costs ~1,600 units.

**Fix:**
- Wait until tomorrow
- Or request quota increase in Google Cloud Console

### "youtube-upload: command not found"

The script auto-installs this, but if it fails:

```bash
pip3 install --upgrade google-auth google-auth-oauthlib google-api-python-client
pip3 install youtube-upload
```

## Advanced: Custom Metadata

To customize upload metadata (title, description, tags), edit `upload_to_youtube.sh`:

```bash
# Around line 85-90
TITLE="${TOPIC} - Educational Video"
DESCRIPTION="Your custom description here"
TAGS="education,science,learning"
```

## Security Notes

- **Never commit `youtube_credentials.json` to git** - it's already in `.gitignore`
- **Never share your credentials file** - it provides access to your YouTube account
- If credentials are compromised, delete them in Google Cloud Console and create new ones
