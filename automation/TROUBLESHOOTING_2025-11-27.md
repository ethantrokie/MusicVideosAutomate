# Daily Automation Failure Investigation - Nov 27, 2025

## Problem Summary

The daily automation pipeline failed to run on November 27, 2025 at 9:00 AM with a `KeyError: 'suno_api'` error during the Music Composition stage.

## Root Cause Analysis

### Primary Issue: Config File Corruption

**What happened:**
- On **November 25, 2025 at 2:01 PM**, the test file `tests/reproduce_audio_sync.py` was executed
- This test **directly overwrote** the production `config/config.json` file with a minimal test configuration
- The test never restored the original configuration
- This left the production config in a corrupted state with only:
  ```json
  {
    "video_settings": {"fps": 24, "resolution": [100, 100]},
    "lyric_sync": {"enabled": false}
  }
  ```

**What was missing:**
- `suno_api` section (with api_key, base_url, model)
- `pipeline_settings` section
- `media_sources` section
- `youtube` section
- Proper video settings

**Impact:**
- All pipeline runs from Nov 25-27 failed with `KeyError: 'suno_api'` at `agents/3_compose.py:165`
- Daily automation on Nov 27 attempted twice (9:00 AM and 9:27 AM) and failed both times

### Timeline

- **Before Nov 25**: Pipeline working correctly with full config
- **Nov 25, 2:01 PM**: Test file corrupts config.json
- **Nov 27, 9:00 AM**: Daily automation fails (Attempt 1)
- **Nov 27, 9:27 AM**: Daily automation fails (Attempt 2)
- **Nov 27**: Investigation and fix

## Resolution

### 1. Config File Restored

✅ **Completed**: Restored `config/config.json` from `config/config.json.template`

### 2. Test File Fixed

✅ **Completed**: Fixed `tests/reproduce_audio_sync.py` to use test-specific config directory instead of overwriting production config at tests/reproduce_audio_sync.py:79-93

### 3. Backup Created

✅ **Completed**: Saved corrupted config as `config/config.json.corrupted_backup`

## Action Required

### Add Suno API Key

The config file has been restored but needs your Suno API key:

1. Open `config/config.json`
2. Find line 4: `"api_key": "YOUR_SUNO_API_KEY_HERE"`
3. Replace `YOUR_SUNO_API_KEY_HERE` with your actual Suno API key
4. Save the file

The pipeline will fail until this is completed.

## Prevention

### Config File Protection

The config file is gitignored (for security), but this means:
- ✅ API keys stay private
- ❌ No version history to recover from corruption
- ❌ Easy to accidentally overwrite

**Recommendation:** Consider creating a backup script that saves config periodically:
```bash
cp config/config.json config/config.json.backup.$(date +%Y%m%d)
```

### Test Isolation

The test file has been fixed to prevent future config corruption, but consider:
- Using pytest fixtures for config management
- Environment variables for test configuration
- Mocking config loading in tests

## Files Modified

1. `config/config.json` - Restored from template
2. `tests/reproduce_audio_sync.py:79-93` - Fixed to use test-specific config directory
3. `config/config.json.corrupted_backup` - Backup of corrupted config

## Related Issues

- Daily automation scheduler was never set up (separate issue)
- TikTok browser upload selectors outdated (separate issue)

## Verification Steps

After adding your Suno API key:

1. Test the config: `./venv/bin/python3 -c "import json; print(json.load(open('config/config.json'))['suno_api']['api_key'])"`
2. Run a test pipeline: `./pipeline.sh --express`
3. Verify music composition stage completes successfully
4. Enable daily automation: `./automation/setup_launchd.sh`
