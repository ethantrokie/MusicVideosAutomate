# Multi-Format Video Pipeline Testing Guide

This guide walks you through testing the complete multi-format video generation system, from a simple idea to three uploaded YouTube videos with cross-links.

## Prerequisites Verification

Before starting, verify all dependencies are installed:

```bash
# Check Python environment
./venv/bin/python --version  # Should be 3.9+

# Check FFmpeg
ffmpeg -version
ffprobe -version

# Check pycaps (karaoke subtitles)
./venv/bin/python -c "import pycaps; print('pycaps OK')"

# Check Playwright (required by pycaps)
./venv/bin/playwright --version

# Check Claude CLI
claude --version
```

If any checks fail, run:
```bash
./setup.sh
./venv/bin/playwright install chromium
```

## Unit Tests

First, run the unit tests to verify core components:

```bash
# Test segment analyzer
./venv/bin/python tests/test_segment_analyzer.py
# Expected: All tests pass ✅

# Test subtitle generator
./venv/bin/python tests/test_subtitle_generator.py
# Expected: All tests pass ✅
```

If tests fail, check the error output and verify dependencies are installed correctly.

## Integration Test: Complete Pipeline

This test runs the entire pipeline from idea to final videos.

### Step 1: Prepare Test Input

Create a simple test topic:

```bash
echo "Explain photosynthesis in plants. Tone: upbeat and educational" > input/idea.txt
```

### Step 2: Verify Configuration

Check that multi-format is enabled:

```bash
python3 << 'EOF'
import json
with open('config/config.json') as f:
    config = json.load(f)

# Check required settings
assert config['video_formats']['full_video']['enabled'] == True
assert config['video_formats']['shorts']['enabled'] == True
assert config['video_formats']['shorts']['count'] == 2

print("✅ Configuration verified")
print(f"  Full video: {config['video_formats']['full_video']['resolution']}")
print(f"  Shorts: {config['video_formats']['shorts']['count']}x {config['video_formats']['shorts']['resolution']}")
EOF
```

### Step 3: Run Pipeline (Without Upload)

Run the pipeline up to video assembly, skipping upload to test the core functionality:

```bash
# Run in express mode to skip manual approval
./pipeline.sh --express

# This will run stages 1-7:
# 1. Research
# 2. Visual Ranking
# 3. Lyrics Generation
# 4. Music Composition
# 4.5. Segment Analysis
# 5. Media Curation & Download
# 6. Video Assembly (Multi-Format)
# 7. Subtitle Generation
# (Stages 8-9 require user confirmation)
```

### Step 4: Verify Outputs

Check that all expected files were created:

```bash
# Get the latest run directory
RUN_DIR=$(ls -t outputs/runs/ | head -1)
OUTPUT_DIR="outputs/runs/$RUN_DIR"

echo "Checking outputs in: $OUTPUT_DIR"
echo

# Stage outputs
echo "📋 Research outputs:"
ls -lh "$OUTPUT_DIR/research.txt" 2>/dev/null && echo "✅ research.txt" || echo "❌ research.txt missing"
ls -lh "$OUTPUT_DIR/image_urls.json" 2>/dev/null && echo "✅ image_urls.json" || echo "❌ image_urls.json missing"

echo
echo "🎵 Music outputs:"
ls -lh "$OUTPUT_DIR/lyrics.json" 2>/dev/null && echo "✅ lyrics.json" || echo "❌ lyrics.json missing"
ls -lh "$OUTPUT_DIR/music.mp3" 2>/dev/null && echo "✅ music.mp3" || echo "❌ music.mp3 missing"

echo
echo "🎯 Segment analysis:"
ls -lh "$OUTPUT_DIR/segments.json" 2>/dev/null && echo "✅ segments.json" || echo "❌ segments.json missing"

echo
echo "📹 Media files:"
ls -lh "$OUTPUT_DIR/media/" 2>/dev/null && echo "✅ media directory" || echo "❌ media directory missing"

echo
echo "🎬 Final videos:"
ls -lh "$OUTPUT_DIR/full.mp4" 2>/dev/null && echo "✅ full.mp4" || echo "❌ full.mp4 missing"
ls -lh "$OUTPUT_DIR/short_hook.mp4" 2>/dev/null && echo "✅ short_hook.mp4" || echo "❌ short_hook.mp4 missing"
ls -lh "$OUTPUT_DIR/short_educational.mp4" 2>/dev/null && echo "✅ short_educational.mp4" || echo "❌ short_educational.mp4 missing"

echo
echo "📝 Subtitle files:"
ls -lh "$OUTPUT_DIR/subtitles/" 2>/dev/null && echo "✅ subtitles directory" || echo "❌ subtitles directory missing"
```

### Step 5: Validate Video Properties

Check that videos have correct dimensions and durations:

```bash
RUN_DIR=$(ls -t outputs/runs/ | head -1)
OUTPUT_DIR="outputs/runs/$RUN_DIR"

echo "🔍 Validating video properties..."
echo

# Check full video (should be 16:9, 2-4 minutes)
echo "Full video:"
ffprobe -v error -select_streams v:0 -show_entries stream=width,height,duration -of json "$OUTPUT_DIR/full.mp4" | python3 -c "
import json, sys
data = json.load(sys.stdin)
width = data['streams'][0]['width']
height = data['streams'][0]['height']
duration = float(data['streams'][0]['duration'])

print(f'  Resolution: {width}x{height}')
print(f'  Duration: {duration:.1f}s')

# Verify aspect ratio (16:9)
aspect = width / height
expected_aspect = 16 / 9
if abs(aspect - expected_aspect) < 0.1:
    print('  ✅ Aspect ratio correct (16:9)')
else:
    print(f'  ⚠️  Aspect ratio: {aspect:.2f}, expected ~{expected_aspect:.2f}')

# Verify duration (120-240 seconds)
if 120 <= duration <= 240:
    print('  ✅ Duration in expected range (2-4 min)')
else:
    print(f'  ⚠️  Duration {duration:.1f}s, expected 120-240s')
"

echo
echo "Hook short:"
ffprobe -v error -select_streams v:0 -show_entries stream=width,height,duration -of json "$OUTPUT_DIR/short_hook.mp4" | python3 -c "
import json, sys
data = json.load(sys.stdin)
width = data['streams'][0]['width']
height = data['streams'][0]['height']
duration = float(data['streams'][0]['duration'])

print(f'  Resolution: {width}x{height}')
print(f'  Duration: {duration:.1f}s')

# Verify aspect ratio (9:16)
aspect = width / height
expected_aspect = 9 / 16
if abs(aspect - expected_aspect) < 0.1:
    print('  ✅ Aspect ratio correct (9:16)')
else:
    print(f'  ⚠️  Aspect ratio: {aspect:.2f}, expected ~{expected_aspect:.2f}')

# Verify duration (30-60 seconds)
if 30 <= duration <= 60:
    print('  ✅ Duration in expected range (30-60s)')
else:
    print(f'  ⚠️  Duration {duration:.1f}s, expected 30-60s')
"

echo
echo "Educational short:"
ffprobe -v error -select_streams v:0 -show_entries stream=width,height,duration -of json "$OUTPUT_DIR/short_educational.mp4" | python3 -c "
import json, sys
data = json.load(sys.stdin)
width = data['streams'][0]['width']
height = data['streams'][0]['height']
duration = float(data['streams'][0]['duration'])

print(f'  Resolution: {width}x{height}')
print(f'  Duration: {duration:.1f}s')

# Verify aspect ratio (9:16)
aspect = width / height
expected_aspect = 9 / 16
if abs(aspect - expected_aspect) < 0.1:
    print('  ✅ Aspect ratio correct (9:16)')
else:
    print(f'  ⚠️  Aspect ratio: {aspect:.2f}, expected ~{expected_aspect:.2f}')

# Verify duration (30-60 seconds)
if 30 <= duration <= 60:
    print('  ✅ Duration in expected range (30-60s)')
else:
    print(f'  ⚠️  Duration {duration:.1f}s, expected 30-60s')
"
```

### Step 6: Manual Review

Watch the generated videos to verify quality:

```bash
RUN_DIR=$(ls -t outputs/runs/ | head -1)
OUTPUT_DIR="outputs/runs/$RUN_DIR"

# Watch full video
open "$OUTPUT_DIR/full.mp4"

# Watch hook short
open "$OUTPUT_DIR/short_hook.mp4"

# Watch educational short
open "$OUTPUT_DIR/short_educational.mp4"
```

**Check for:**
- ✅ Audio plays correctly
- ✅ Visuals match the topic
- ✅ Subtitles appear at correct times
- ✅ Full video has traditional subtitles (phrase-level)
- ✅ Shorts have karaoke subtitles (word-level with highlighting)
- ✅ Shorts are cropped to vertical format
- ✅ No audio/video sync issues

### Step 7: Test Segment Analysis

Verify that segments were intelligently selected:

```bash
RUN_DIR=$(ls -t outputs/runs/ | head -1)
OUTPUT_DIR="outputs/runs/$RUN_DIR"

echo "📊 Segment Analysis Results:"
cat "$OUTPUT_DIR/segments.json" | python3 -m json.tool
```

**Expected output:**
```json
{
  "full": {
    "start": 0,
    "end": 180.5,
    "duration": 180.5,
    "rationale": "Complete song"
  },
  "hook": {
    "start": 45.2,
    "end": 75.8,
    "duration": 30.6,
    "rationale": "Repeated chorus section detected"
  },
  "educational": {
    "start": 12.5,
    "end": 43.1,
    "duration": 30.6,
    "rationale": "Segment contains key educational content about chlorophyll..."
  }
}
```

**Verify:**
- Hook segment should ideally be a repeated section (chorus)
- Educational segment should contain key learning concepts
- Both shorts should be 30-60 seconds
- Segments should not overlap if possible

## Testing Individual Components

### Test Segment Analyzer

```bash
# Requires a valid lyrics.json in output directory
RUN_DIR=$(ls -t outputs/runs/ | head -1)
OUTPUT_DIR="outputs/runs/$RUN_DIR"

# Run analyzer standalone
python3 agents/analyze_segments.py

# Check output
cat "$OUTPUT_DIR/segments.json"
```

### Test Subtitle Generator

```bash
RUN_DIR=$(ls -t outputs/runs/ | head -1)
OUTPUT_DIR="outputs/runs/$RUN_DIR"

# Generate traditional subtitles
./agents/generate_subtitles.py \
  --lyrics "$OUTPUT_DIR/lyrics.json" \
  --output "$OUTPUT_DIR/test_traditional.srt" \
  --style traditional

# Generate karaoke subtitles
./agents/generate_subtitles.py \
  --lyrics "$OUTPUT_DIR/lyrics.json" \
  --output "$OUTPUT_DIR/test_karaoke.srt" \
  --style karaoke

# Check SRT files
cat "$OUTPUT_DIR/test_traditional.srt"
cat "$OUTPUT_DIR/test_karaoke.srt"
```

### Test Video Builder

```bash
# Requires completed stages 1-5
RUN_DIR=$(ls -t outputs/runs/ | head -1)
export OUTPUT_DIR="outputs/runs/$RUN_DIR"

python3 agents/build_multiformat_videos.py
```

## Testing YouTube Upload (Optional)

**⚠️ Warning:** This will actually upload videos to YouTube. Only run if you want to publish the test video.

### Setup YouTube Credentials

If you haven't already:

1. Follow the YouTube setup instructions in README.md
2. Place `youtube_credentials.json` in `config/`
3. Run the first upload to authenticate

### Test Upload

```bash
RUN_DIR=$(ls -t outputs/runs/ | head -1)

# Upload full video
./upload_to_youtube.sh --run=$RUN_DIR --type=full --privacy=unlisted

# Upload hook short
./upload_to_youtube.sh --run=$RUN_DIR --type=short_hook --privacy=unlisted

# Upload educational short
./upload_to_youtube.sh --run=$RUN_DIR --type=short_educational --privacy=unlisted
```

### Test Cross-Linking

After uploading all three videos, test cross-linking:

```bash
RUN_DIR=$(ls -t outputs/runs/ | head -1)
OUTPUT_DIR="outputs/runs/$RUN_DIR"

# Get video IDs from upload logs or manually
FULL_ID="your_full_video_id"
HOOK_ID="your_hook_short_id"
EDU_ID="your_edu_short_id"

# Run cross-linking
python3 agents/crosslink_videos.py "$FULL_ID" "$HOOK_ID" "$EDU_ID"

# Verify upload_results.json was created
cat "$OUTPUT_DIR/upload_results.json"
```

## Common Issues and Solutions

### Issue: Tests fail with "ModuleNotFoundError"

**Solution:** Activate virtual environment:
```bash
source venv/bin/activate
# Or use ./venv/bin/python directly
```

### Issue: pycaps fails with Playwright error

**Solution:** Reinstall Playwright:
```bash
./venv/bin/playwright install chromium
```

### Issue: Segment analysis fails

**Solution:** Check Claude CLI authentication:
```bash
claude --version
# Re-authenticate if needed
```

If Claude CLI is unavailable, the system will use fallback heuristics (middle section for hook, intro for educational).

### Issue: Videos have wrong aspect ratio

**Solution:** Check FFmpeg version and crop filter support:
```bash
ffmpeg -version
ffmpeg -filters | grep crop
```

### Issue: Subtitles not appearing

**Solution:**
- For traditional (FFmpeg): Check subtitle file exists and FFmpeg burn-in command succeeded
- For karaoke (pycaps): Check Playwright is installed and CSS template exists

### Issue: Upload fails with authentication error

**Solution:** Re-authenticate YouTube:
```bash
rm config/youtube_token.pickle
./upload_to_youtube.sh  # Will prompt for authentication
```

## Performance Benchmarks

Expected timings for a 3-minute song (on Mac Studio):

| Stage | Time | Notes |
|-------|------|-------|
| Research | 30-60s | Claude API |
| Visual Ranking | 10-20s | Local processing |
| Lyrics Generation | 20-40s | Claude API |
| Music Composition | 60-120s | Suno API |
| Segment Analysis | 10-30s | Claude CLI |
| Media Download | 30-90s | Network dependent |
| Video Assembly | 2-4min | MoviePy, 3 videos |
| Subtitle Generation | 1-2min | pycaps (slower), FFmpeg (fast) |
| YouTube Upload | 1-3min | Network dependent |
| Cross-Linking | 5-10s | YouTube API |
| **Total** | **8-15min** | Full pipeline |

pycaps is slower than FFmpeg because it uses browser rendering, but produces better visual results for karaoke subtitles.

## Success Criteria

A successful test run should produce:

✅ Three video files (full, hook short, educational short)
✅ Correct aspect ratios (16:9 and 9:16)
✅ Correct durations (2-4min and 30-60s)
✅ Working subtitles in all videos
✅ Different subtitle styles (traditional vs karaoke)
✅ Intelligently selected segments (not just arbitrary cuts)
✅ Audio/video sync in all formats
✅ (Optional) Uploaded to YouTube with cross-links

## Next Steps

Once all tests pass:

1. **Customize styling**: Edit `templates/shorts_karaoke.css` for your brand
2. **Tune segments**: Adjust duration ranges in `config/config.json`
3. **Daily automation**: Integrate with automation system
4. **Monitor performance**: Track which format gets the most engagement

## Troubleshooting Resources

- [Main README](../README.md) - Overview and quick start
- [Setup Guide](SETUP_GUIDE.md) - Detailed installation
- [Troubleshooting](TROUBLESHOOTING.md) - Common issues
- [Multi-Format Usage](MULTI_FORMAT_USAGE.md) - Feature-specific guide
- [GitHub Issues](https://github.com/anthropics/claude-code/issues) - Report bugs
