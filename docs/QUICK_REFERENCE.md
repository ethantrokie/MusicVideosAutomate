# Quick Reference

## Pipeline Commands

```bash
# Create new video
./pipeline.sh

# Express mode (skip media approval)
./pipeline.sh --express

# Resume latest run from specific stage
./pipeline.sh --start=3 --resume

# Resume specific run
./pipeline.sh --start=5 --resume=20250116_143025
```

## YouTube Upload

```bash
# Upload latest video (unlisted)
./upload_to_youtube.sh

# Upload as public
./upload_to_youtube.sh --privacy=public

# Upload as private
./upload_to_youtube.sh --privacy=private

# Upload specific run
./upload_to_youtube.sh --run=20250116_143025

# Upload specific run as public
./upload_to_youtube.sh --run=20250116_143025 --privacy=public
```

## File Locations

```
outputs/current/final_video.mp4    # Latest video
outputs/runs/TIMESTAMP/            # Specific run directory
config/youtube_credentials.json    # YouTube OAuth credentials
logs/                              # Pipeline logs
```

## Pipeline Stages

1. **Research** - Gather facts and find media
2. **Lyrics** - Generate song lyrics
3. **Compose** - Create music via Suno API
4. **Curate** - Select and download media
5. **Assemble** - Combine into final video

## Common Workflows

### Create and publish video
```bash
./pipeline.sh --express                    # Create video
./upload_to_youtube.sh --privacy=public    # Upload to YouTube
```

### Fix failed stage and upload
```bash
./pipeline.sh --start=5 --resume    # Re-run video assembly
./upload_to_youtube.sh              # Upload result
```

### Review before publishing
```bash
./pipeline.sh                       # Create with media review
open outputs/current/final_video.mp4
./upload_to_youtube.sh              # Upload as unlisted (default)
```

## Privacy Levels

- `unlisted` - Not searchable, only accessible via link (default, safest)
- `private` - Only you can see it
- `public` - Anyone can find and watch

## Tips

- Always start with `--privacy=unlisted` to review the upload before making it public
- Use `outputs/current/` symlink to always access the latest run
- Check `logs/` if something goes wrong
- The upload script extracts title/description from research.json automatically
