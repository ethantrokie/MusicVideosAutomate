# TikTok Browser Upload Setup Guide

This guide walks you through setting up TikTok uploads using browser automation - **no API application or sandbox restrictions required!**

## Overview

The browser automation method uses the `tiktok-uploader` package to upload videos by automating your actual browser. This bypasses all the official API restrictions:

- ✅ No developer account needed
- ✅ No app approval process
- ✅ No sandbox mode restrictions
- ✅ Post publicly immediately
- ✅ No test user limitations

**Tradeoff**: Slightly slower uploads (opens browser) and requires cookie management.

## Prerequisites

1. **Google Chrome Browser**
   - Download from: https://www.google.com/chrome/
   - The automation requires Chrome to be installed

2. **TikTok Account**
   - You just need a regular TikTok account
   - No developer account required!

3. **Python Dependencies**
   - Already installed if you ran `./setup.sh`
   - Package: `tiktok-uploader>=1.1.5`

## Step 1: Extract Browser Cookies

The browser automation works by using your login cookies from a real browser session.

### Option A: Using Browser Extension (Recommended)

1. **Install "Get cookies.txt LOCALLY" extension**
   - **Chrome**: https://chrome.google.com/webstore/detail/get-cookiestxt-locally/cclelndahbckbenkjhflpdbgdldlbecc
   - **Firefox**: https://addons.mozilla.org/en-US/firefox/addon/cookies-txt/
   - **Edge**: https://microsoftedge.microsoft.com/addons/detail/get-cookiestxt-locally/eoaobghbnnngdcnbpkgmljokgpfiffnm

2. **Log into TikTok**
   - Go to https://www.tiktok.com
   - Log in to your account
   - Make sure you're fully logged in (can see your profile)

3. **Export Cookies**
   - Click the extension icon (looks like a cookie 🍪)
   - Click "Export" or "Get cookies.txt"
   - Save the file as: `config/tiktok_cookies.txt`

### Option B: Manual Cookie Extraction

If you prefer not to use an extension:

1. **Log into TikTok** at https://www.tiktok.com

2. **Open Developer Tools**
   - Chrome/Edge: Press `F12` or right-click → "Inspect"
   - Safari: Enable Develop menu → "Show Web Inspector"

3. **Go to Application/Storage Tab**
   - Chrome/Edge: Click "Application" tab → "Cookies" → "https://www.tiktok.com"
   - Safari: Click "Storage" tab → "Cookies"

4. **Find `sessionid` Cookie**
   - Look for a cookie named `sessionid`
   - Copy its value (long string of characters)

5. **Create Cookie File**
   ```bash
   # Create config/tiktok_cookies.txt with this format:
   # Netscape HTTP Cookie File
   .tiktok.com	TRUE	/	TRUE	0	sessionid	YOUR_SESSION_ID_HERE
   ```

   Replace `YOUR_SESSION_ID_HERE` with the actual value you copied.

## Step 2: Configure Upload Method

Edit `automation/config/automation_config.json`:

```json
{
  "tiktok": {
    "enabled": true,
    "method": "browser",
    "username": "@learningsciencemusic",
    "privacy_status": "public_to_everyone",
    "cookies_path": "config/tiktok_cookies.txt"
  }
}
```

**Configuration Options**:
- `method`: `"browser"` for browser automation, `"api"` for official API
- `privacy_status`: `public_to_everyone`, `mutual_follow_friends`, or `self_only`
- `cookies_path`: Path to your cookies file (relative to project root)

## Step 3: Test Upload

Test the browser upload with a sample video:

```bash
# Test with latest video
./upload_to_tiktok.sh --type=full --method=browser

# Test with specific run
./upload_to_tiktok.sh --run=20231125_120000 --type=full --method=browser

# Test with hook short
./upload_to_tiktok.sh --type=short_hook --method=browser
```

The script will:
1. Open Google Chrome in automated mode
2. Navigate to TikTok upload page
3. Use your cookies to authenticate
4. Fill in video details and upload
5. Return the video ID and URL

## How It Works

### Browser Automation Flow

1. **Authentication**: Uses your browser cookies to authenticate (no passwords needed)
2. **Video Upload**: Opens Chrome, navigates to TikTok, and uploads the video
3. **Headless Mode**: Can run without showing the browser window (optional)
4. **Result Extraction**: Captures the video ID after successful upload

### Cookie Lifespan

- Cookies typically last **30-90 days**
- You'll need to refresh them when they expire
- The system will show a clear error message when cookies expire

## Daily Automation

When using `automation/daily_pipeline.sh`, browser uploads happen automatically if enabled:

1. Pipeline generates videos
2. Uploads to YouTube
3. Uploads to TikTok using browser automation
4. Cross-links all videos
5. Sends notification with URLs

Notification example:
```
✅ Daily videos published!
Topic: How Rockets Work
YouTube: https://youtube.com/watch?v=abc123
TikTok (full): https://tiktok.com/@learningsciencemusic/video/7123456...
TikTok (hook): https://tiktok.com/@learningsciencemusic/video/7456789...
Status: public (multi-platform with cross-linking)
Method: Browser automation
```

## Troubleshooting

### "Cookies file not found"

**Problem**: Missing `config/tiktok_cookies.txt`

**Solution**:
1. Follow Step 1 to extract your cookies
2. Save them to `config/tiktok_cookies.txt`
3. Make sure the file is in the correct location

### "Cookie authentication failed"

**Problem**: Cookies have expired or are invalid

**Solution**:
1. Log into TikTok in your browser
2. Extract fresh cookies using the extension
3. Replace `config/tiktok_cookies.txt` with new cookies
4. Try uploading again

### "Browser automation failed" or "Chrome not found"

**Problem**: Google Chrome is not installed or not found

**Solution**:
1. Download and install Chrome: https://www.google.com/chrome/
2. Make sure Chrome is installed in the default location
3. On macOS: Check that Chrome is in `/Applications/`

### Upload succeeds but video doesn't appear

**Problem**: TikTok is still processing the video

**Solution**:
- Wait 2-5 minutes for TikTok to process the video
- Check your TikTok profile manually
- Video processing can take longer for larger files

### "Rate limit" or "Too many requests"

**Problem**: Uploaded too many videos too quickly

**Solution**:
- Wait a few hours before trying again
- TikTok has upload limits to prevent spam
- For daily automation (1-2 videos/day), this shouldn't be an issue

## Browser vs API Comparison

| Feature | Browser Automation | Official API |
|---------|-------------------|--------------|
| Setup Complexity | Low (just cookies) | High (app approval) |
| Public Posts | ✅ Works immediately | ⚠️ Only after app review |
| Sandbox Mode | ✅ No restrictions | ❌ Test users only |
| Upload Speed | Slower (opens browser) | Faster (direct API) |
| Stability | Depends on browser | Officially supported |
| Cookie Management | Manual refresh needed | Auto token refresh |
| Rate Limits | TikTok user limits | API limits (500/day) |

## Security Notes

1. **Never commit cookies**: `config/tiktok_cookies.txt` is in `.gitignore`
2. **Cookie security**: Cookies grant full access to your TikTok account
3. **Refresh cookies**: Re-extract cookies every 30 days for security
4. **Private repository**: Never share your cookies file

## Additional Resources

- [tiktok-uploader GitHub](https://github.com/wkaisertexas/tiktok-uploader)
- [tiktok-uploader Documentation](https://wkaisertexas.github.io/blog/tiktok-uploader/)
- [Get cookies.txt Extension](https://chrome.google.com/webstore/detail/get-cookiestxt-locally/cclelndahbckbenkjhflpdbgdldlbecc)

## Switching Between Methods

You can keep both methods configured and switch between them:

**Use Browser Method**:
```bash
./upload_to_tiktok.sh --method=browser
```

**Use API Method**:
```bash
./upload_to_tiktok.sh --method=api
```

**Default Method**: Set in `automation_config.json` under `tiktok.method`
