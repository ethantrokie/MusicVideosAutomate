# Automation System Testing Guide

## What Was Tested During Implementation

✅ **Tested and Working:**
1. Directory structure creation
2. Notification helper (iMessage to 914-844-4402)
3. Topic generator (generates topics via Claude CLI, stores history)
4. YouTube API dependencies installation
5. Change guardian validation logic
6. launchd jobs loading

❌ **Not Yet Fully Tested:**
1. Complete daily pipeline end-to-end (topic → video → upload)
2. Weekly optimizer with real YouTube analytics data
3. YouTube channel-specific upload to @LearningScienceMusic
4. Config change application

## How to Test Each Component

### 1. Test Notification System

```bash
# Test iMessage notifications
./automation/notification_helper.sh "Test notification from automation system"
```

**Expected:** iMessage received at 914-844-4402
**Check:** `automation/logs/notifications.log` for logged message

---

### 2. Test Topic Generator

```bash
# Generate a science topic
./automation/topic_generator.py
```

**Expected:**
- New topic in `input/idea.txt`
- Entry added to `automation/state/topic_history.json`
- No duplicate topics for 30 days

**Verify:**
```bash
cat input/idea.txt
cat automation/state/topic_history.json
```

---

### 3. Test Change Guardian

```bash
# Run validation tests
./automation/change_guardian.py
```

**Expected:** Test cases validated with results showing auto-apply/needs-review/rejected

---

### 4. Test YouTube Channel Helper

```bash
# List your YouTube channels
./automation/youtube_channel_helper.py --list-channels
```

**Expected:** Lists all channels including @LearningScienceMusic

**Note:** First run will trigger OAuth browser flow to authenticate with YouTube

---

### 5. Test Daily Pipeline (DRY RUN - Without Upload)

**IMPORTANT:** This will generate a topic and create a video but NOT upload it.

```bash
# Step 1: Generate topic
./automation/topic_generator.py

# Step 2: Create video (takes ~2-5 minutes)
./pipeline.sh --express

# Step 3: Verify video was created
ls -lh outputs/current/final_video.mp4
```

**Expected:**
- Video file created in `outputs/current/`
- Log in `automation/logs/` (if run through daily_pipeline.sh)

**To test with upload:**
```bash
# Upload the generated video to @LearningScienceMusic (PRIVATE)
./upload_to_youtube.sh --channel="@LearningScienceMusic" --privacy=private
```

---

### 6. Test Complete Daily Pipeline (FULL END-TO-END)

**WARNING:** This will create and upload a real video to YouTube as PRIVATE.

```bash
# Run full pipeline (topic → video → upload → notify)
./automation/daily_pipeline.sh
```

**Expected:**
- Topic generated in `input/idea.txt`
- Video created in `outputs/current/`
- Video uploaded to @LearningScienceMusic as private
- Success notification via iMessage
- Logs in `automation/logs/daily_YYYY-MM-DD.log`

**Verify:**
1. Check YouTube Studio: https://studio.youtube.com
2. Navigate to @LearningScienceMusic channel
3. Verify video is there (status: Private)

---

### 7. Test Weekly Optimizer (DRY RUN - No Changes Applied)

**Prerequisites:**
- Must have at least 1 video uploaded to @LearningScienceMusic in the last 7 days
- YouTube Analytics API must be enabled
- Optimization must be DISABLED (default)

```bash
# Run optimizer with optimization disabled (analysis only)
./automation/weekly_optimizer.py
```

**Expected:**
- Fetches YouTube analytics for recent videos
- Analyzes performance with Claude Code
- Validates recommendations through change guardian
- Generates report in `automation/reports/YYYY-MM-DD-analysis.md`
- Sends notification with report summary
- NO changes applied to `config/config.json` (optimization disabled)

**Verify:**
```bash
# View the generated report
cat automation/reports/$(date +%Y-%m-%d)-analysis.md

# Check that config wasn't modified
git diff config/config.json  # Should show no changes
```

---

### 8. Test Weekly Optimizer (LIVE - With Changes)

**WARNING:** This will automatically modify `config/config.json` based on analytics.

```bash
# Enable optimization
jq '.optimization.enabled = true' automation/config/automation_config.json > tmp.json && mv tmp.json automation/config/automation_config.json

# Run optimizer
./automation/weekly_optimizer.py

# Check what changed
git diff config/config.json
```

**Expected:**
- High-confidence recommendations applied to `config/config.json`
- Medium-confidence recommendations saved to `automation/pending_changes.json`
- Changes logged in `automation/state/optimization_state.json`

---

### 9. Test Scheduled Jobs

```bash
# Verify launchd jobs are loaded
launchctl list | grep learningscience
```

**Expected:** Shows both jobs with status 0

**To test scheduling without waiting:**
```bash
# Trigger daily job manually (doesn't wait for 9 AM)
launchctl start com.learningscience.daily

# Check logs
tail -f automation/logs/launchd_daily.log
```

---

## Understanding the Optimization System

### What is "Optimization"?

The weekly optimizer is a **self-improving system** that:

1. **Every Sunday at 10 AM:**
   - Fetches YouTube Analytics for videos from the past 7 days
   - Analyzes: views, watch time, likes, comments, shares, retention %

2. **Sends data to Claude Code CLI:**
   - Claude analyzes performance patterns
   - Suggests 1-2 optimizations (e.g., "Shorten videos to 45s for better retention")
   - Provides confidence score (0-1) for each suggestion

3. **Change Guardian validates suggestions:**
   - **AUTO_APPLY** (confidence ≥ 0.8): Safe, high-confidence changes
   - **NEEDS_REVIEW** (confidence 0.5-0.8): Flagged for human review
   - **REJECTED**: Forbidden changes (API keys, channel selection, etc.)
   - **DOCUMENT_ONLY** (confidence < 0.5): Too uncertain, just documented

4. **If optimization is enabled:**
   - High-confidence changes automatically applied to `config/config.json`
   - Future videos use the new settings
   - Example: If Claude finds 45-second videos perform better, it changes `"duration": 60` → `"duration": 45`

5. **Tracks results:**
   - Stores what changed and when in `optimization_state.json`
   - Next week, analyzes if the change helped or hurt
   - Self-corrects if changes made things worse

### Safe Ranges (Guardrails)

From `automation/config/guardrails.json`:

```json
{
  "safe_ranges": {
    "video_duration": [15, 120],      // 15s - 2min
    "max_media_items": [5, 30],       // 5-30 clips
    "min_media_items": [3, 15],
    "tone_description_max_length": 200
  },
  "allowed_changes": [
    "tone adjustments",     // Music/pacing style
    "duration tweaks",      // Video length
    "media variety",        // Number of clips
    "posting time"          // When to publish
  ],
  "forbidden_changes": [
    "API keys",            // Security
    "channel selection",   // Can't change @LearningScienceMusic
    "privacy status",      // Can't auto-make public
    "resolution",          // Video quality locked
    "system commands"      // No shell injection
  ]
}
```

**Claude CANNOT:**
- Change which YouTube channel to upload to
- Make videos public automatically
- Modify API keys
- Run system commands
- Suggest changes outside safe ranges

### Why is Optimization Disabled by Default?

**Safety:** You should:
1. Run the system for 1-2 weeks first
2. Review several weekly reports manually
3. Verify the suggestions make sense
4. Then enable auto-optimization

**To enable later:**
```bash
jq '.optimization.enabled = true' automation/config/automation_config.json > tmp && mv tmp automation/config/automation_config.json
```

---

## Quick Testing Checklist

Run these in order for comprehensive testing:

```bash
# 1. Basic components
./automation/notification_helper.sh "Testing automation"
./automation/topic_generator.py
./automation/change_guardian.py

# 2. YouTube authentication
./automation/youtube_channel_helper.py --list-channels

# 3. Video pipeline (no upload)
./automation/topic_generator.py
./pipeline.sh --express

# 4. Upload test (PRIVATE)
./upload_to_youtube.sh --channel="@LearningScienceMusic" --privacy=private

# 5. Full daily pipeline
./automation/daily_pipeline.sh

# 6. Weekly optimizer (dry run)
./automation/weekly_optimizer.py

# 7. Verify scheduled jobs
launchctl list | grep learningscience
```

---

## Troubleshooting

### Notifications not working
- Check Messages app is signed in to iMessage
- Verify phone number: `914-844-4402` in config
- Check `automation/logs/notifications.log`

### YouTube authentication fails
- Delete token: `rm config/youtube_token.pickle`
- Re-run: `./automation/youtube_channel_helper.py --list-channels`
- Complete OAuth flow in browser

### Daily pipeline fails
- Check logs: `automation/logs/daily_YYYY-MM-DD.log`
- Check launchd errors: `automation/logs/launchd_daily_error.log`
- Run manually for debugging: `./automation/daily_pipeline.sh`

### Weekly optimizer has no data
- Need at least 1 video uploaded in past 7 days
- Enable YouTube Analytics API in Google Cloud Console
- Check permissions in `config/youtube_credentials.json`

### launchd job not running
```bash
# Unload and reload
launchctl unload ~/Library/LaunchAgents/com.learningscience.daily.plist
launchctl load ~/Library/LaunchAgents/com.learningscience.daily.plist

# Check status
launchctl list | grep learningscience
```

---

## What Files Track System State?

- `automation/state/topic_history.json` - Last 30 days of topics (prevents repeats)
- `automation/state/optimization_state.json` - What was changed and when
- `automation/logs/notifications.log` - All sent notifications
- `automation/logs/daily_YYYY-MM-DD.log` - Daily pipeline execution
- `automation/reports/YYYY-MM-DD-analysis.md` - Weekly performance reports
- `config/config.json` - Current video settings (modified by optimizer)
