# TikTok Integration Design

**Date:** 2025-01-25
**Status:** Approved for Implementation

## Overview

Add TikTok upload functionality to the automated video system, enabling daily posts to both YouTube and TikTok platforms with cross-platform linking and independent error handling.

## Scope

**Videos to Upload:**
- Full song video (16:9 horizontal)
- Hook short video (9:16 vertical)

**Key Features:**
- OAuth 2.0 authentication with TikTok Content Posting API
- Independent platform uploads (best-effort on both)
- Topic-aware hashtags (same as YouTube)
- Cross-platform references in descriptions/captions
- Unified configuration and result tracking

## Architecture

### New Components

1. **`automation/tiktok_uploader.py`**
   - Python helper using TikTok Content Posting API
   - OAuth authentication and token management
   - Chunked video upload (5-64 MB chunks)
   - Status polling until publish complete

2. **`upload_to_tiktok.sh`**
   - Bash wrapper for TikTok uploads
   - Generates TikTok-optimized metadata
   - Calls Python uploader with video path and metadata
   - Saves video IDs for cross-linking

3. **`config/tiktok_credentials.json`**
   - OAuth app credentials (Client Key/Secret)

4. **`config/tiktok_token.pickle`**
   - Cached OAuth access and refresh tokens

### Modified Components

1. **`pipeline.sh` Stage 8**
   - Add TikTok uploads in parallel with YouTube
   - Independent error handling (failures don't block other platform)

2. **`pipeline.sh` Stage 9**
   - Update cross-linking to include TikTok URLs
   - Generate platform-specific upload results

3. **`automation_config.json`**
   - Add `tiktok` configuration section

4. **`upload_results.json`**
   - Track video IDs from both platforms
   - Nested structure: `youtube` and `tiktok` sections

## TikTok API Integration

### Prerequisites

1. Create TikTok developer account at developers.tiktok.com
2. Register application to get Client Key and Client Secret
3. Request "Content Posting API" access with `video.publish` scope
4. **Important:** Unaudited apps post videos as PRIVATE by default - request audit approval for public posting
5. Configure OAuth redirect URI (e.g., `http://localhost:8080/callback`)

### API Endpoints

Base URL: `https://open.tiktokapis.com`

1. **POST /v2/post/publish/video/init/**
   - Initialize direct post to TikTok profile
   - Returns upload_url (valid for 1 hour)

2. **PUT [upload_url]**
   - Upload video chunks (5-64 MB, final chunk up to 128 MB)

3. **POST /v2/post/publish/status/fetch/**
   - Check upload status and processing completion

4. **POST /v2/post/publish/creator_info/query/**
   - Get creator account information

### OAuth Flow

1. First run: Opens browser for user consent
2. Exchange authorization code for access token
3. Store tokens in `config/tiktok_token.pickle`
4. Auto-refresh expired tokens (TikTok tokens typically last 24 hours)

## Upload Flow

### Stage 8: Platform Uploads (Modified)

```bash
# YouTube uploads (existing - 3 videos)
./upload_to_youtube.sh --run="${RUN_TIMESTAMP}" --type=full $YOUTUBE_ARGS
./upload_to_youtube.sh --run="${RUN_TIMESTAMP}" --type=short_hook $YOUTUBE_ARGS
./upload_to_youtube.sh --run="${RUN_TIMESTAMP}" --type=short_educational $YOUTUBE_ARGS

# TikTok uploads (new - 2 videos, independent error handling)
./upload_to_tiktok.sh --run="${RUN_TIMESTAMP}" --type=full $TIKTOK_ARGS || echo "⚠️  TikTok full upload failed"
./upload_to_tiktok.sh --run="${RUN_TIMESTAMP}" --type=short_hook $TIKTOK_ARGS || echo "⚠️  TikTok short upload failed"
```

### Error Handling Strategy

- **Independent uploads:** Each platform operates separately
- **Best-effort approach:** YouTube success doesn't depend on TikTok
- **Status tracking:** Record success/failure per video per platform
- **Notifications:** Report which platforms succeeded in daily summary

### Stage 9: Cross-Platform Linking (Modified)

Update video descriptions/captions to reference other platforms:

**YouTube descriptions** - add TikTok links:
```
Watch on TikTok: https://tiktok.com/@user/video/7123...
```

**TikTok captions** - reference YouTube channel:
```
View full video on YouTube @learningsciencemusic

#lasers #light #physics #education #learning #science
```

## Configuration

### automation_config.json (New Section)

```json
{
  "youtube": {
    "channel_handle": "@learningsciencemusic",
    "privacy_status": "public",
    "credentials_path": "config/youtube_credentials.json"
  },
  "tiktok": {
    "enabled": true,
    "username": "@learningsciencemusic",
    "privacy_status": "public_to_everyone",
    "credentials_path": "config/tiktok_credentials.json"
  },
  "notifications": {
    "notify_on_success": true,
    "notify_on_failure": true
  }
}
```

**TikTok Privacy Options:**
- `public_to_everyone` - visible to all users
- `mutual_follow_friends` - followers only
- `self_only` - private

### upload_results.json (Enhanced)

```json
{
  "youtube": {
    "full_video": {
      "id": "abc123",
      "url": "https://youtube.com/watch?v=abc123"
    },
    "hook_short": {
      "id": "def456",
      "url": "https://youtube.com/shorts/def456"
    },
    "educational_short": {
      "id": "ghi789",
      "url": "https://youtube.com/shorts/ghi789"
    }
  },
  "tiktok": {
    "full_video": {
      "id": "7123456789012345678",
      "url": "https://tiktok.com/@learningsciencemusic/video/7123456789012345678"
    },
    "hook_short": {
      "id": "7456789012345678901",
      "url": "https://tiktok.com/@learningsciencemusic/video/7456789012345678901"
    }
  }
}
```

## Metadata Generation

### Hashtags (Reuse YouTube Logic)

Use the same topic-aware hashtag generator as YouTube:
- Extract keywords from topic (4+ letters)
- Generate topic-specific hashtags
- Add generic educational hashtags
- Total: 8-10 hashtags per video

Example for "How lasers produce coherent light":
```
#lasers #produce #coherent #light #physics #education #learning #science #stem
```

### Title/Caption Formatting

**Full Video:**
```
Title: [Topic] - Full Educational Song
Caption: Learn about [topic] through music!

View full version on YouTube @learningsciencemusic

[hashtags]
```

**Hook Short:**
```
Title: [Topic] 🎵
Caption: [Topic]

View full video on YouTube @learningsciencemusic

[hashtags]
```

## Testing Strategy

### Phase 1: Authentication Setup
1. Test OAuth flow manually with `tiktok_uploader.py --auth`
2. Verify token refresh works after expiry
3. Confirm token persists in pickle file

### Phase 2: Manual Upload Testing
1. Upload test videos manually via `upload_to_tiktok.sh`
2. Verify both full video and short upload successfully
3. Check metadata, captions, and hashtags appear correctly
4. Confirm videos are visible (not private)

### Phase 3: Pipeline Integration
1. Run full pipeline with `--express` flag
2. Verify independent error handling works
3. Check upload_results.json contains both platforms
4. Verify cross-platform links in descriptions

### Phase 4: Daily Automation
1. Test daily_pipeline.sh end-to-end
2. Verify notifications include both platform statuses
3. Monitor for OAuth token refresh issues
4. Confirm daily posting reliability over 1 week

## Implementation Order

1. **Create `automation/tiktok_uploader.py`**
   - Implement OAuth 2.0 flow
   - Implement video upload logic (chunked)
   - Add status polling

2. **Create `upload_to_tiktok.sh`**
   - Metadata generation function
   - Hashtag generation (reuse YouTube logic)
   - Call Python uploader
   - Save video IDs

3. **Update `automation_config.json`**
   - Add `tiktok` configuration section
   - Document privacy options

4. **Modify `pipeline.sh` Stage 8**
   - Add TikTok upload calls
   - Implement independent error handling

5. **Modify `pipeline.sh` Stage 9**
   - Update cross-linking logic
   - Generate unified upload_results.json

6. **Update `automation/daily_pipeline.sh`**
   - Update notifications to include TikTok status
   - Handle partial success scenarios

7. **Testing**
   - Complete all 4 testing phases
   - Document any TikTok-specific quirks
   - Verify daily automation reliability

## Key Technical Notes

### TikTok API Limitations
- Unaudited apps: Videos default to PRIVATE visibility
- Upload URL: Valid for 1 hour only
- Chunk size: 5-64 MB (final chunk up to 128 MB)
- Required scope: `video.publish`
- Token lifetime: Typically 24 hours (auto-refresh needed)

### Error Handling
- Each platform upload is independent
- Failed TikTok upload won't block YouTube
- Partial success is acceptable
- Notifications indicate which platforms succeeded

### Cross-Platform Linking
- YouTube descriptions: Include clickable TikTok URLs
- TikTok captions: Reference YouTube by @handle (links not clickable)
- upload_results.json tracks all video IDs for both platforms

## Dependencies

**Python packages:**
- `requests` - HTTP client for TikTok API
- `pickle` - Token storage (already used for YouTube)

**Existing codebase:**
- Hashtag generation logic from `upload_to_youtube.sh`
- OAuth pattern from `youtube_channel_helper.py`
- Cross-linking from `agents/crosslink_videos.py`

## Success Criteria

1. ✅ Videos upload to TikTok with correct metadata
2. ✅ OAuth authentication works reliably with auto-refresh
3. ✅ Independent error handling (YouTube succeeds even if TikTok fails)
4. ✅ Cross-platform references work correctly
5. ✅ Daily automation runs without manual intervention
6. ✅ Notifications accurately report status for both platforms
7. ✅ Public posting works after TikTok app audit approval
