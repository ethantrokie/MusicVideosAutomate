#!/usr/bin/env python3
"""
Video overlay generator.
Adds title cards and call-to-action end screens to videos.
"""

import os
import sys
import json
import argparse
from pathlib import Path
from typing import Optional, Tuple

# Add agents directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))
from output_helper import get_output_path
from engagement_experiments import is_engagement_feature_enabled

# Monkey patch for Pillow 10+ compatibility with moviepy 1.0.3
try:
    from PIL import Image
    if not hasattr(Image, 'ANTIALIAS'):
        Image.ANTIALIAS = Image.LANCZOS
except ImportError:
    pass

# Configure ImageMagick for MoviePy text rendering
# Prevents "unset" binary path errors in launchd environment
import moviepy.config as mpconfig
import shutil

def find_imagemagick():
    """Find ImageMagick binary, including fallback paths for launchd."""
    # Try shutil.which first (works when PATH is set correctly)
    binary = shutil.which('magick') or shutil.which('convert')
    if binary:
        return binary

    # Fallback to common absolute paths (needed for launchd)
    fallback_paths = [
        '/opt/homebrew/bin/magick',      # Apple Silicon Homebrew
        '/opt/homebrew/bin/convert',
        '/usr/local/bin/magick',         # Intel Homebrew
        '/usr/local/bin/convert',
        '/usr/bin/convert',              # System default
    ]
    for path in fallback_paths:
        if os.path.exists(path) and os.access(path, os.X_OK):
            return path
    return None

imagemagick_binary = find_imagemagick()
if imagemagick_binary:
    mpconfig.change_settings({"IMAGEMAGICK_BINARY": imagemagick_binary})
else:
    print("⚠️  Warning: ImageMagick not found, text overlays may fail")

from moviepy.editor import (
    VideoFileClip,
    TextClip,
    CompositeVideoClip,
    ColorClip,
)


# Fun fonts available on macOS
TITLE_FONTS = [
    '/System/Library/Fonts/Supplemental/Impact.ttf',
    '/System/Library/Fonts/Supplemental/Arial Black.ttf',
    '/System/Library/Fonts/Supplemental/Futura.ttc',
    '/System/Library/Fonts/Helvetica.ttc',
]

CTA_FONTS = [
    '/System/Library/Fonts/Supplemental/Arial Bold.ttf',
    '/System/Library/Fonts/Helvetica.ttc',
]


def get_available_font(font_list: list) -> str:
    """Get first available font from list."""
    for font in font_list:
        if os.path.exists(font):
            return font
    return 'Helvetica'  # Fallback


def create_title_overlay(
    title: str,
    video_size: Tuple[int, int],
    duration: float = 2.0,
    is_short: bool = False
) -> TextClip:
    """
    Create title text overlay for beginning of video.

    Args:
        title: Video title text
        video_size: (width, height) tuple
        duration: How long to show title
        is_short: Whether this is a short-form video

    Returns:
        TextClip with title
    """
    width, height = video_size

    # Adjust font size based on video format and title length
    if is_short:
        # Vertical video - larger text
        base_size = 60
        max_width = width - 80  # 40px padding each side
    else:
        # Horizontal video - slightly smaller
        base_size = 70
        max_width = width - 160  # 80px padding each side

    # Reduce font size for longer titles
    if len(title) > 40:
        base_size = int(base_size * 0.75)
    elif len(title) > 25:
        base_size = int(base_size * 0.85)

    font = get_available_font(TITLE_FONTS)

    # Create text clip with stroke for visibility
    txt_clip = TextClip(
        title,
        fontsize=base_size,
        font=font,
        color='white',
        stroke_color='black',
        stroke_width=3,
        method='caption',  # Enables word wrapping
        size=(max_width, None),
        align='center'
    )

    # Position in upper third of video
    txt_clip = txt_clip.set_position(('center', height * 0.15))
    txt_clip = txt_clip.set_duration(duration)

    # Instant appearance, smooth exit (no fade-in delay — first frame must have text)
    txt_clip = txt_clip.crossfadeout(0.3)

    return txt_clip


def generate_hook_text(title: str) -> str:
    """
    Transform a video title into a short 3-7 word hook.
    Prioritizes curiosity-gap questions and surprising claims.
    """
    # Remove common suffixes
    clean = title.replace(" Explained", "").replace(" (Music Video)", "").strip()
    lower = clean.lower()

    # Common patterns for science topics
    if lower.startswith("how "):
        # "How Chocolate Gets Its Snap" -> "Chocolate Gets Its Snap?!"
        subject = clean[4:]  # Remove "How "
        return f"{subject}?!"
    elif lower.startswith("why "):
        return clean + "?"
    elif lower.startswith("what "):
        return clean + "?"
    elif lower.startswith("the "):
        # "The Chemistry of Rust" -> "Chemistry of Rust?!"
        return clean[4:] + "?!"
    else:
        # Default: add question mark for curiosity
        return f"{clean}?!"


def create_hook_overlay(
    hook_text: str,
    video_size: Tuple[int, int],
    duration: float = 2.0,
    is_short: bool = False,
    animate: bool = False
) -> TextClip:
    """
    Create bold hook text overlay for frame 0.
    Larger and bolder than the title — designed to stop scrolling.
    Yellow text with thick black outline for maximum visibility.

    Args:
        hook_text: Short 3-7 word hook
        video_size: (width, height) tuple
        duration: How long to show hook text
        is_short: Whether this is short-form video
        animate: If True, apply 0.15s scale-up pop-in animation (80% -> 100%)

    Returns:
        TextClip/VideoClip with hook text
    """
    width, height = video_size

    if is_short:
        base_size = 72  # Bigger than title (60)
        max_width = width - 60
        y_position = height * 0.12
    else:
        base_size = 80  # Bigger than title (70)
        max_width = width - 120
        y_position = height * 0.12

    # Reduce for long hooks
    if len(hook_text) > 35:
        base_size = int(base_size * 0.8)

    font = get_available_font(TITLE_FONTS)

    txt_clip = TextClip(
        hook_text,
        fontsize=base_size,
        font=font,
        color='yellow',
        stroke_color='black',
        stroke_width=4,
        method='caption',
        size=(max_width, None),
        align='center'
    )

    # Position at top — instant appearance, no fade-in
    txt_clip = txt_clip.set_position(('center', y_position))
    txt_clip = txt_clip.set_duration(duration)

    # A/B tested: animated pop-in (0.15s scale 80% -> 100%)
    if animate:
        txt_clip = txt_clip.resize(lambda t: min(1.0, 0.8 + (t / 0.15) * 0.2))

    txt_clip = txt_clip.crossfadeout(0.3)  # Smooth exit only

    return txt_clip


def create_end_screen(
    video_size: Tuple[int, int],
    duration: float = 3.0,
    is_short: bool = False,
    channel_name: str = "@learningsciencemusic"
) -> CompositeVideoClip:
    """
    Create end screen with call-to-action.

    Args:
        video_size: (width, height) tuple
        duration: How long to show end screen
        is_short: Whether this is a short-form video
        channel_name: YouTube channel handle

    Returns:
        CompositeVideoClip with CTA elements
    """
    width, height = video_size
    font = get_available_font(CTA_FONTS)

    clips = []

    # Semi-transparent background overlay
    bg = ColorClip(size=(width, height), color=(0, 0, 0))
    bg = bg.set_opacity(0.5)
    bg = bg.set_duration(duration)
    clips.append(bg)

    if is_short:
        # Vertical short - stack text vertically
        # Main CTA
        main_cta = TextClip(
            "Like & Subscribe!",
            fontsize=50,
            font=font,
            color='yellow',
            stroke_color='black',
            stroke_width=2
        )
        main_cta = main_cta.set_position(('center', height * 0.35))
        main_cta = main_cta.set_duration(duration)
        clips.append(main_cta)

        # Channel promo for shorts
        channel_promo = TextClip(
            f"Full song on\n{channel_name}",
            fontsize=40,
            font=font,
            color='white',
            stroke_color='black',
            stroke_width=2,
            align='center'
        )
        channel_promo = channel_promo.set_position(('center', height * 0.50))
        channel_promo = channel_promo.set_duration(duration)
        clips.append(channel_promo)

        # Subscribe emoji/icon
        subscribe_icon = TextClip(
            "👆",
            fontsize=80,
            font=font,
            color='white'
        )
        subscribe_icon = subscribe_icon.set_position(('center', height * 0.68))
        subscribe_icon = subscribe_icon.set_duration(duration)
        clips.append(subscribe_icon)

    else:
        # Horizontal full video - wider layout
        main_cta = TextClip(
            "Enjoyed this? Like & Subscribe!",
            fontsize=55,
            font=font,
            color='yellow',
            stroke_color='black',
            stroke_width=2
        )
        main_cta = main_cta.set_position(('center', height * 0.40))
        main_cta = main_cta.set_duration(duration)
        clips.append(main_cta)

        # Secondary text
        secondary = TextClip(
            "More educational music videos coming soon!",
            fontsize=35,
            font=font,
            color='white',
            stroke_color='black',
            stroke_width=1
        )
        secondary = secondary.set_position(('center', height * 0.55))
        secondary = secondary.set_duration(duration)
        clips.append(secondary)

    # Composite all elements
    end_screen = CompositeVideoClip(clips, size=video_size)
    end_screen = end_screen.set_duration(duration)
    end_screen = end_screen.crossfadein(0.5)

    return end_screen


def add_overlays_to_video(
    video_path: Path,
    output_path: Path,
    title: str,
    is_short: bool = False,
    title_duration: float = 2.0,
    end_screen_duration: float = 3.0,
    channel_name: str = "@learningsciencemusic",
    hook_text: str = None,
    animate_hook: bool = False
) -> Path:
    """
    Add title, hook text, and end screen overlays to a video.

    Args:
        video_path: Path to input video
        output_path: Path for output video
        title: Video title for title card
        is_short: Whether this is a short-form video
        title_duration: Duration of title overlay
        end_screen_duration: Duration of end screen
        channel_name: Channel name for shorts CTA
        hook_text: Bold hook text for frame 0 (auto-generated from title if None)

    Returns:
        Path to output video
    """
    print(f"  Loading video: {video_path}")
    video = VideoFileClip(str(video_path))
    video_size = video.size
    video_duration = video.duration
    width, height = video_size

    print(f"  Video size: {width}x{height}, duration: {video_duration:.1f}s")

    # Auto-generate hook text if not provided
    if hook_text is None:
        hook_text = generate_hook_text(title)

    # Create hook text overlay (bold, yellow, appears instantly at frame 0)
    print(f"  Creating hook overlay: '{hook_text}'")
    hook_clip = create_hook_overlay(hook_text, video_size, min(title_duration, 2.0), is_short, animate=animate_hook)
    hook_clip = hook_clip.set_start(0)

    # Create title overlay (appears at start, positioned below hook)
    print(f"  Creating title overlay: '{title[:50]}...' " if len(title) > 50 else f"  Creating title overlay: '{title}'")
    title_clip = create_title_overlay(title, video_size, title_duration, is_short)
    title_clip = title_clip.set_start(0)
    # Move title below hook text to avoid overlap
    title_clip = title_clip.set_position(('center', height * 0.25))

    # Create end screen (appears at end)
    print(f"  Creating end screen ({'shorts' if is_short else 'full video'})...")
    end_screen = create_end_screen(video_size, end_screen_duration, is_short, channel_name)
    end_screen = end_screen.set_start(video_duration - end_screen_duration)

    # Composite all layers: video -> hook -> title -> end screen
    print("  Compositing overlays...")
    final = CompositeVideoClip([video, hook_clip, title_clip, end_screen])
    final = final.set_duration(video_duration)

    # Write output
    print(f"  Rendering to {output_path}...")
    final.write_videofile(
        str(output_path),
        fps=video.fps,
        codec='libx264',
        audio_codec='aac',
        preset='medium',
        threads=4
    )

    # Cleanup
    video.close()
    final.close()

    print(f"  ✅ Overlays added successfully")
    return output_path


def get_hook_line_from_lyrics(run_dir: Path = None) -> Optional[str]:
    """
    Read hook text from lyrics.json viral_elements.

    Priority: display_hook_text > hook_line (truncated to 7 words) > None (fallback).

    Args:
        run_dir: Directory containing lyrics.json

    Returns:
        Hook text string or None if not available
    """
    if run_dir is None:
        run_dir = get_output_path("").parent

    lyrics_path = run_dir / "lyrics.json"
    if not lyrics_path.exists():
        return None

    try:
        with open(lyrics_path) as f:
            lyrics_data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return None

    viral = lyrics_data.get("viral_elements", {})

    # Priority 1: display_hook_text (purpose-built for overlay)
    display_hook = viral.get("display_hook_text", "").strip()
    if display_hook:
        words = display_hook.split()
        if len(words) <= 7:
            return display_hook
        return " ".join(words[:7]) + "..."

    # Priority 2: hook_line (truncate if >7 words)
    hook_line = viral.get("hook_line", "").strip()
    if hook_line:
        words = hook_line.split()
        if len(words) <= 7:
            return hook_line
        return " ".join(words[:7]) + "..."

    return None


def get_video_title(run_dir: Path = None) -> str:
    """Get video title from research.json or idea.txt."""
    if run_dir is None:
        run_dir = get_output_path("").parent

    # Try research.json first
    research_path = run_dir / "research.json"
    if research_path.exists():
        with open(research_path) as f:
            research = json.load(f)
            title = research.get('video_title', '')
            if title:
                return title

    # Fallback to idea.txt
    idea_path = Path("input/idea.txt")
    if idea_path.exists():
        topic = idea_path.read_text().strip().split('.')[0]
        return topic

    return "Educational Video"


def main():
    """Main execution for standalone overlay processing."""
    parser = argparse.ArgumentParser(description='Add overlays to video')
    parser.add_argument('--video', type=str, required=True, help='Input video path')
    parser.add_argument('--output', type=str, help='Output video path (default: replaces input)')
    parser.add_argument('--title', type=str, help='Video title (default: from research.json)')
    parser.add_argument('--type', choices=['full', 'short_hook', 'short_educational', 'short_intro'],
                        default='full', help='Video type')
    parser.add_argument('--title-duration', type=float, default=2.0,
                        help='Title overlay duration in seconds')
    parser.add_argument('--end-duration', type=float, default=3.0,
                        help='End screen duration in seconds')
    parser.add_argument('--channel', type=str, default='@learningsciencemusic',
                        help='Channel name for CTA')
    parser.add_argument('--hook-text', type=str,
                        help='Hook text overlay (default: auto-generated from title)')

    args = parser.parse_args()

    # Skip if Remotion overlay already applied
    remotion_flag = Path(args.video).parent / ".remotion_overlay_applied"
    if remotion_flag.exists():
        print("  ⏭️  Skipping MoviePy overlays (Remotion overlay already applied)")
        return

    video_path = Path(args.video)
    if not video_path.exists():
        print(f"❌ Error: Video not found: {video_path}")
        sys.exit(1)

    # Determine output path
    if args.output:
        output_path = Path(args.output)
    else:
        # Create temp output, then replace original
        output_path = video_path.with_suffix('.overlay.mp4')

    # Get title
    title = args.title or get_video_title(video_path.parent)

    # Determine hook text source (A/B tested: lyrics vs title-derived)
    hook = args.hook_text
    if hook is None:
        use_lyrics_hook = is_engagement_feature_enabled("engagement_hook_source")
        if use_lyrics_hook:
            hook = get_hook_line_from_lyrics(video_path.parent)
            if hook:
                print(f"  🧪 A/B: Using lyrics hook_line: '{hook}'")
        if hook is None:
            hook = generate_hook_text(title)
            print(f"  Using title-derived hook: '{hook}'")

    # Determine if short
    is_short = args.type in ['short_hook', 'short_educational', 'short_intro']

    # A/B tested: animated hook text pop-in
    animate_hook = is_engagement_feature_enabled("engagement_animated_hook")
    if animate_hook:
        print(f"  🧪 A/B: Animated hook text enabled")

    print(f"🎬 Adding overlays to video...")
    print(f"  Type: {args.type}")
    print(f"  Title: {title}")
    print(f"  Hook: {hook}")

    add_overlays_to_video(
        video_path=video_path,
        output_path=output_path,
        title=title,
        is_short=is_short,
        title_duration=args.title_duration,
        end_screen_duration=args.end_duration,
        channel_name=args.channel,
        hook_text=hook,
        animate_hook=animate_hook
    )

    # Replace original if no explicit output specified
    if not args.output:
        import shutil
        shutil.move(str(output_path), str(video_path))
        print(f"  Replaced original video")

    print(f"✅ Overlay processing complete!")


if __name__ == "__main__":
    main()
