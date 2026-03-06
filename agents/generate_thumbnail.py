#!/Users/ethantrokie/SoftwareDevProjects/MusicVideosAutomate/venv/bin/python3
"""
Thumbnail generator for YouTube videos.

Extracts the most visually interesting frame from a video,
adds bold text overlay and optional logo, then saves as
a 1280x720 JPEG suitable for YouTube custom thumbnails.
"""

import argparse
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

# Monkey patch for Pillow 10+ compatibility with moviepy 1.0.3
if not hasattr(Image, 'ANTIALIAS'):
    Image.ANTIALIAS = Image.LANCZOS

from moviepy.editor import VideoFileClip


# --- Constants ---

THUMBNAIL_WIDTH = 1280
THUMBNAIL_HEIGHT = 720
SAMPLE_POSITIONS = (0.10, 0.25, 0.50, 0.75)

# Font search order (first match wins)
FONT_CANDIDATES = [
    "/System/Library/Fonts/Supplemental/Impact.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/System/Library/Fonts/HelveticaNeue.ttc",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
]

FONT_SIZE_RATIO = 0.08  # Font height as fraction of thumbnail height
MIN_FONT_SIZE = 48
MAX_FONT_SIZE = 120

TEXT_OUTLINE_WIDTH = 4
TEXT_SHADOW_OFFSET = 4

LOGO_MAX_SIZE = 100
LOGO_OPACITY = 180  # 0-255, where 255 is fully opaque
LOGO_MARGIN = 20


# --- Frame scoring ---

def score_frame(frame: np.ndarray) -> float:
    """
    Score a video frame for visual interest.

    Combines color variance, contrast, and a penalty for
    frames that are mostly black or mostly white.

    Args:
        frame: RGB numpy array of shape (H, W, 3).

    Returns:
        Weighted score (higher is better).
    """
    gray = np.mean(frame, axis=2)
    mean_brightness = np.mean(gray)

    # Color variance: standard deviation across all channels
    color_variance = float(np.std(frame))

    # Contrast: difference between 95th and 5th percentile
    # (more robust than simple max-min)
    p5 = float(np.percentile(gray, 5))
    p95 = float(np.percentile(gray, 95))
    contrast = p95 - p5

    # Penalty for very dark or very bright frames
    brightness_penalty = 0.0
    if mean_brightness < 30:
        brightness_penalty = 0.5
    elif mean_brightness > 230:
        brightness_penalty = 0.5
    elif mean_brightness < 60:
        brightness_penalty = 0.2

    score = (color_variance * 0.6) + (contrast * 0.4)
    score *= (1.0 - brightness_penalty)

    return score


def extract_best_frame(video_path: str) -> Image.Image:
    """
    Sample frames from a video and return the most visually interesting one.

    Samples at 10%, 25%, 50%, and 75% of the video duration, scores
    each frame, and returns the highest-scoring one as a PIL Image.

    Args:
        video_path: Path to the video file.

    Returns:
        PIL Image of the best frame.

    Raises:
        FileNotFoundError: If the video file does not exist.
        RuntimeError: If no valid frames could be extracted.
    """
    path = Path(video_path)
    if not path.exists():
        raise FileNotFoundError(f"Video file not found: {video_path}")

    clip = VideoFileClip(video_path)
    duration = clip.duration

    if duration <= 0:
        clip.close()
        raise RuntimeError(f"Video has zero or negative duration: {video_path}")

    best_frame = None
    best_score = -1.0
    best_time = 0.0

    for position in SAMPLE_POSITIONS:
        t = duration * position
        try:
            frame = clip.get_frame(t)
            s = score_frame(frame)
            if s > best_score:
                best_score = s
                best_frame = frame
                best_time = t
        except Exception as e:
            print(f"Warning: could not extract frame at {t:.2f}s: {e}", file=sys.stderr)
            continue

    clip.close()

    if best_frame is None:
        raise RuntimeError(f"Could not extract any valid frame from: {video_path}")

    print(
        f"Selected frame at {best_time:.2f}s "
        f"(score={best_score:.1f})",
        file=sys.stderr,
    )

    return Image.fromarray(best_frame)


# --- Text rendering ---

def load_font(size: int) -> ImageFont.FreeTypeFont:
    """
    Load the first available bold font at the given size.

    Falls back to the default bitmap font if no TrueType font
    is found.

    Args:
        size: Desired font size in pixels.

    Returns:
        PIL font object.
    """
    for font_path in FONT_CANDIDATES:
        try:
            return ImageFont.truetype(font_path, size)
        except (OSError, IOError):
            continue

    print(
        "Warning: no TrueType font found, using default bitmap font",
        file=sys.stderr,
    )
    return ImageFont.load_default()


def calculate_font_size(text: str, max_width: int) -> int:
    """
    Calculate the largest font size that fits the text within max_width.

    Starts from the ideal size (based on FONT_SIZE_RATIO) and shrinks
    until the rendered text fits.

    Args:
        text: The text string to render.
        max_width: Maximum allowed width in pixels.

    Returns:
        Font size in pixels.
    """
    ideal_size = int(THUMBNAIL_HEIGHT * FONT_SIZE_RATIO)
    ideal_size = max(MIN_FONT_SIZE, min(ideal_size, MAX_FONT_SIZE))

    size = ideal_size
    while size > MIN_FONT_SIZE:
        font = load_font(size)
        bbox = font.getbbox(text)
        text_width = bbox[2] - bbox[0]
        if text_width <= max_width:
            return size
        size -= 4

    return size


def draw_text_with_outline(
    draw: ImageDraw.ImageDraw,
    position: tuple,
    text: str,
    font: ImageFont.FreeTypeFont,
    fill: tuple = (255, 255, 255, 255),
    outline_color: tuple = (0, 0, 0, 255),
    outline_width: int = TEXT_OUTLINE_WIDTH,
    shadow_offset: int = TEXT_SHADOW_OFFSET,
) -> None:
    """
    Draw text with a dark shadow and outline for readability.

    Renders a drop shadow first, then an outline by drawing
    the text at offset positions, and finally the main text
    on top.

    Args:
        draw: PIL ImageDraw object.
        position: (x, y) tuple for text placement.
        text: The text string.
        font: PIL font object.
        fill: RGBA tuple for the main text color.
        outline_color: RGBA tuple for the outline/shadow.
        outline_width: Thickness of the outline in pixels.
        shadow_offset: Pixel offset for the drop shadow.
    """
    x, y = position

    # Drop shadow
    shadow_color = (0, 0, 0, 180)
    draw.text(
        (x + shadow_offset, y + shadow_offset),
        text,
        font=font,
        fill=shadow_color,
    )

    # Outline: draw text at each offset around the center
    for dx in range(-outline_width, outline_width + 1):
        for dy in range(-outline_width, outline_width + 1):
            if dx == 0 and dy == 0:
                continue
            draw.text((x + dx, y + dy), text, font=font, fill=outline_color)

    # Main text
    draw.text(position, text, font=font, fill=fill)


def add_text_overlay(image: Image.Image, text: str) -> Image.Image:
    """
    Add bold text in the lower-third of the thumbnail.

    Text is centered horizontally and positioned at roughly
    75% of the image height.

    Args:
        image: Base PIL Image (RGBA).
        text: Short text to overlay (3-5 words).

    Returns:
        New PIL Image with text overlay applied.
    """
    result = image.copy()
    draw = ImageDraw.Draw(result)

    text_upper = text.upper()
    padding = 40
    max_text_width = THUMBNAIL_WIDTH - (padding * 2)

    font_size = calculate_font_size(text_upper, max_text_width)
    font = load_font(font_size)

    bbox = font.getbbox(text_upper)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]

    # Center horizontally, position in lower-third
    text_x = (THUMBNAIL_WIDTH - text_width) // 2
    text_y = int(THUMBNAIL_HEIGHT * 0.75) - (text_height // 2)

    draw_text_with_outline(draw, (text_x, text_y), text_upper, font)

    return result


# --- Logo overlay ---

def add_logo_overlay(image: Image.Image, logo_path: str) -> Image.Image:
    """
    Overlay a semi-transparent logo in the top-right corner.

    The logo is resized to fit within LOGO_MAX_SIZE pixels
    while preserving aspect ratio, and its opacity is reduced.

    Args:
        image: Base PIL Image (RGBA).
        logo_path: Path to the logo image file.

    Returns:
        New PIL Image with logo overlay applied.

    Raises:
        FileNotFoundError: If the logo file does not exist.
    """
    path = Path(logo_path)
    if not path.exists():
        raise FileNotFoundError(f"Logo file not found: {logo_path}")

    result = image.copy()
    logo = Image.open(logo_path).convert("RGBA")

    # Resize logo preserving aspect ratio
    logo.thumbnail((LOGO_MAX_SIZE, LOGO_MAX_SIZE), Image.LANCZOS)

    # Apply semi-transparency
    alpha = logo.split()[3]
    alpha = alpha.point(lambda p: min(p, LOGO_OPACITY))
    logo.putalpha(alpha)

    # Position in top-right corner
    logo_x = THUMBNAIL_WIDTH - logo.width - LOGO_MARGIN
    logo_y = LOGO_MARGIN

    result.paste(logo, (logo_x, logo_y), logo)

    return result


# --- Main pipeline ---

def generate_thumbnail(
    video_path: str,
    title: str,
    output_path: str,
    logo_path: str = None,
) -> str:
    """
    Generate a YouTube thumbnail from a video file.

    Pipeline:
      1. Extract the most visually interesting frame
      2. Resize/crop to 1280x720
      3. Add text overlay
      4. Add optional logo
      5. Save as JPEG

    Args:
        video_path: Path to the source video.
        title: Short text for the overlay (3-5 words).
        output_path: Where to save the thumbnail JPEG.
        logo_path: Optional path to a logo image.

    Returns:
        Absolute path to the saved thumbnail.
    """
    # Step 1: Extract best frame
    frame_image = extract_best_frame(video_path)

    # Step 2: Resize to thumbnail dimensions
    # Use cover-crop strategy: resize to fill, then center-crop
    img_ratio = frame_image.width / frame_image.height
    thumb_ratio = THUMBNAIL_WIDTH / THUMBNAIL_HEIGHT

    if img_ratio > thumb_ratio:
        # Image is wider -- fit height, crop width
        new_height = THUMBNAIL_HEIGHT
        new_width = int(new_height * img_ratio)
    else:
        # Image is taller -- fit width, crop height
        new_width = THUMBNAIL_WIDTH
        new_height = int(new_width / img_ratio)

    resized = frame_image.resize((new_width, new_height), Image.LANCZOS)

    # Center crop to exact thumbnail size
    left = (new_width - THUMBNAIL_WIDTH) // 2
    top = (new_height - THUMBNAIL_HEIGHT) // 2
    cropped = resized.crop((left, top, left + THUMBNAIL_WIDTH, top + THUMBNAIL_HEIGHT))

    # Convert to RGBA for compositing
    thumbnail = cropped.convert("RGBA")

    # Step 3: Add text overlay
    thumbnail = add_text_overlay(thumbnail, title)

    # Step 4: Add logo if provided
    if logo_path:
        thumbnail = add_logo_overlay(thumbnail, logo_path)

    # Step 5: Save as JPEG
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    # Convert to RGB for JPEG (no alpha channel)
    final = thumbnail.convert("RGB")
    final.save(str(output), "JPEG", quality=95)

    absolute_path = str(output.resolve())
    print(absolute_path)

    return absolute_path


def parse_args(argv=None):
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Generate a YouTube thumbnail from a video file."
    )
    parser.add_argument(
        "--video",
        required=True,
        help="Path to the source video file",
    )
    parser.add_argument(
        "--title",
        required=True,
        help="Short text for the thumbnail (3-5 words)",
    )
    parser.add_argument(
        "--output",
        required=True,
        help="Output path for the thumbnail JPEG",
    )
    parser.add_argument(
        "--logo",
        default=None,
        help="Optional path to a logo image to overlay",
    )
    return parser.parse_args(argv)


def main():
    """Entry point."""
    args = parse_args()

    try:
        generate_thumbnail(
            video_path=args.video,
            title=args.title,
            output_path=args.output,
            logo_path=args.logo,
        )
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except RuntimeError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
