# Video-Only Mode & Resize Updates

## Changes Summary

### 1. Video-Only Media Search

**Problem**: Mixed images and videos caused inconsistent results
**Solution**: Updated all prompts to request ONLY videos and animated GIFs

**Files Updated**:
- `agents/prompts/researcher_prompt.md`
  - Changed: "30 total media items" → "30 total VIDEO items"
  - Added: "ONLY videos and animated GIFs (NO static images)"
  - Search strategy now explicitly states "ONLY search for videos and animated GIFs"
  - Removed all image-related instructions
  - Added note: GIFs count as videos

- `agents/prompts/curator_prompt.md`
  - Selection criteria now requires `"media_type": "video"`
  - Explicitly rejects static images
  - Updated quality criteria to emphasize motion and movement

### 2. Letterbox/Pillarbox Instead of Crop

**Problem**: Horizontal videos were cropped, losing valuable content
**Solution**: Resize to fit + add black bars (letterbox/pillarbox) instead of cropping

**File Updated**: `agents/5_assemble_video.py:84-123`

**How it works**:
```python
# Calculate aspect ratios
clip_aspect = clip.w / clip.h
target_aspect = target_width / target_height

if clip_aspect > target_aspect:
    # Horizontal video → fit to width, add black bars top/bottom
    clip = clip.resize(width=target_width)
else:
    # Vertical video → fit to height, add black bars left/right
    clip = clip.resize(height=target_height)

# Center on black canvas
```

**Benefits**:
- ✅ No content loss from cropping
- ✅ All video content visible
- ✅ Professional letterbox/pillarbox effect
- ✅ Works for any aspect ratio (horizontal, vertical, square)

### 3. Example Scenarios

#### Horizontal Video (16:9) → Vertical Format (9:16)
**Before (Crop)**:
- Resized to 1920px height
- Cropped left/right sides → lost 50%+ of content

**After (Letterbox)**:
- Resized to 1080px width
- Black bars added top/bottom
- 100% of content preserved

#### Vertical Video (9:16) → Vertical Format (9:16)
**Before & After**:
- Perfect fit, no changes needed

#### Square Video (1:1) → Vertical Format (9:16)
**Before (Crop)**:
- Cropped top/bottom

**After (Pillarbox)**:
- Resized to fit height
- Black bars left/right
- All content preserved

## Testing

To test with the new video-only mode:

```bash
# 1. Delete old research with images
rm outputs/research.json

# 2. Run research to get 30 videos
./agents/1_research.sh

# 3. Continue pipeline normally
./pipeline.sh --start=2
```

## Media Type Distribution

**Target**: 30 videos total
- ~10 from Pexels (videos)
- ~10 from Pixabay (videos)
- ~10 from Giphy (animated GIFs)

**File Types**:
- `.mp4` - Video files from Pexels/Pixabay
- `.gif` - Animated GIFs from Giphy
- NO `.jpg`, `.jpeg`, `.png` files

## Visual Ranking Compatibility

The visual ranking workflow fully supports video analysis:
- Claude Code can view video files
- Analyzes motion, educational value, and content
- All 5 scoring criteria work for videos:
  - Educational value
  - Visual clarity
  - Engagement (motion enhances this!)
  - Scientific accuracy
  - Relevance

## Aspect Ratio Handling

The new resize logic handles all aspect ratios:

| Input Aspect | Target (9:16) | Result |
|--------------|---------------|--------|
| 16:9 (landscape) | Vertical | Letterbox (black top/bottom) |
| 4:3 (standard) | Vertical | Letterbox (black top/bottom) |
| 1:1 (square) | Vertical | Pillarbox (black left/right) |
| 9:16 (vertical) | Vertical | Perfect fit |
| 2.35:1 (ultra-wide) | Vertical | Large letterbox bars |

All content is preserved, none is cropped!

## Video Duration Notes

- Research requests videos 5-20 seconds long
- Videos can be looped if too short for the shot duration
- Videos are trimmed if too long for the shot duration
- GIFs naturally loop, perfect for continuous motion

## Fallback Behavior

If the image code path is still executed (shouldn't happen with video-only):
- ImageClips are still supported by the code
- Will also be letterboxed/pillarboxed
- No functionality removed, just not the primary use case
