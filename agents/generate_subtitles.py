#!/usr/bin/env python3
"""
Unified subtitle generator supporting both traditional and karaoke styles.
"""

import json
import os
import sys
import subprocess
import shutil
from pathlib import Path
from typing import Dict, List


def get_executable_path(cmd: str) -> str:
    """Find executable path, checking common locations."""
    # Check if in PATH
    path = shutil.which(cmd)
    if path:
        return path
        
    # Check common locations
    common_paths = [
        f"/opt/homebrew/bin/{cmd}",
        f"/usr/local/bin/{cmd}",
        f"/usr/bin/{cmd}",
        f"/bin/{cmd}"
    ]
    
    for p in common_paths:
        if os.path.exists(p) and os.access(p, os.X_OK):
            return p
            
    # Return command as-is and hope for the best
    return cmd



def load_config() -> Dict:
    """Load configuration."""
    with open('config/config.json') as f:
        return json.load(f)


def load_lyrics() -> Dict:
    """Load Suno lyrics with word-level timestamps."""
    # Try lyrics_aligned.json first (word-level timestamps from Suno API)
    lyrics_file = Path(f"{os.environ['OUTPUT_DIR']}/lyrics_aligned.json")
    if not lyrics_file.exists():
        # Fallback to suno_output.json if aligned lyrics not available
        lyrics_file = Path(f"{os.environ['OUTPUT_DIR']}/suno_output.json")

    with open(lyrics_file) as f:
        return json.load(f)


def normalize_lyrics_format(lyrics: Dict) -> List[Dict]:
    """
    Normalize lyrics format to standard word list.
    Handles both lyrics_aligned.json and suno_output.json formats.
    """
    # Check if this is lyrics_aligned.json format (alignedWords with startS/endS)
    if 'alignedWords' in lyrics:
        words = []
        for w in lyrics['alignedWords']:
            words.append({
                'word': w['word'],
                'start': w['startS'],
                'end': w['endS']
            })
        return words

    # Otherwise assume it's suno_output.json format (words with start/end)
    elif 'words' in lyrics:
        return lyrics['words']

    else:
        raise ValueError("Invalid lyrics format - missing 'alignedWords' or 'words' field")


def format_srt_timestamp(seconds: float) -> str:
    """Convert seconds to SRT timestamp format (HH:MM:SS,mmm)."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds % 1) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def generate_traditional_srt(words: List[Dict], output_file: Path, min_duration: float = 2.0, max_duration: float = 3.5) -> None:
    """
    Generate traditional phrase-level SRT subtitles.
    Groups words into 2-3 second readable phrases.
    """
    phrases = []
    current_phrase = []
    current_start = None

    for word_data in words:
        word = word_data['word']
        start = word_data['start']
        end = word_data['end']

        if current_start is None:
            current_start = start

        current_phrase.append(word)

        # End phrase on punctuation or duration limits
        duration = end - current_start
        ends_sentence = word.rstrip().endswith(('.', '!', '?'))

        if duration >= min_duration and (ends_sentence or duration >= max_duration):
            phrases.append({
                'start': current_start,
                'end': end,
                'text': ' '.join(current_phrase)
            })
            current_phrase = []
            current_start = None

    # Add remaining words as final phrase
    if current_phrase:
        phrases.append({
            'start': current_start,
            'end': words[-1]['end'],
            'text': ' '.join(current_phrase)
        })

    # Write SRT format
    with open(output_file, 'w') as f:
        for i, phrase in enumerate(phrases, 1):
            start_time = format_srt_timestamp(phrase['start'])
            end_time = format_srt_timestamp(phrase['end'])

            f.write(f"{i}\n")
            f.write(f"{start_time} --> {end_time}\n")
            f.write(f"{phrase['text']}\n")
            f.write("\n")


def generate_karaoke_srt(words: List[Dict], output_file: Path) -> None:
    """
    Generate word-level SRT for karaoke highlighting.
    Each word gets its own subtitle entry with precise timing.
    """
    with open(output_file, 'w') as f:
        for i, word_data in enumerate(words, 1):
            start_time = format_srt_timestamp(word_data['start'])
            end_time = format_srt_timestamp(word_data['end'])

            f.write(f"{i}\n")
            f.write(f"{start_time} --> {end_time}\n")
            f.write(f"{word_data['word']}\n")
            f.write("\n")


def format_ass_timestamp(seconds: float) -> str:
    """Convert seconds to ASS timestamp format (H:MM:SS.cc)."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    centisecs = int((seconds % 1) * 100)
    return f"{hours}:{minutes:02d}:{secs:02d}.{centisecs:02d}"


def create_ass_header(resolution_x: int = 1080, resolution_y: int = 1920, is_short: bool = True) -> str:
    """
    Create ASS file header with karaoke styles.
    
    Args:
        resolution_x: Video width
        resolution_y: Video height
        is_short: If True, use larger font for vertical shorts
    
    Returns:
        ASS header string
    """
    # Font size: larger for shorts (central focus), 50% larger for full videos for readability
    font_size = 48 if is_short else 54
    
    # Margin from bottom - 25% for shorts, 10% for full
    margin_v = int(resolution_y * 0.25) if is_short else int(resolution_y * 0.10)
    
    header = f"""[Script Info]
Title: Karaoke Subtitles
ScriptType: v4.00+
PlayResX: {resolution_x}
PlayResY: {resolution_y}
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Karaoke,Arial,{font_size},&H00FFFF,&HFFFFFF,&H000000,&H80000000,1,0,0,0,100,100,0,0,1,3,1,2,10,10,{margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    return header


def generate_phrase_highlight_ass(
    words: List[Dict], 
    output_file: Path, 
    min_words: int = 3, 
    max_words: int = 7,
    resolution_x: int = 1080,
    resolution_y: int = 1920,
    is_short: bool = True
) -> None:
    """
    Generate ASS subtitles with phrase-level display and word-by-word highlighting.
    
    Shows multiple words at once with the active word highlighted using karaoke effect.
    Uses \\kf tags for progressive color sweep from secondary (white) to primary (yellow).
    
    Args:
        words: List of word dicts with 'word', 'start', 'end' keys
        output_file: Path to output .ass file
        min_words: Minimum words per phrase
        max_words: Maximum words per phrase  
        resolution_x: Video width
        resolution_y: Video height
        is_short: If True, use short video settings
    """
    # Group words into phrases based on NEWLINES in lyrics (musical phrasing)
    # Newlines in lyrics represent natural line breaks in the song
    phrases = []
    current_phrase = []
    
    for word_data in words:
        raw_word = word_data['word']
        
        # Check if this word ends with a newline (end of lyric line)
        ends_line = '\n' in raw_word
        
        current_phrase.append(word_data)
        
        # End phrase when:
        # 1. Word contains newline (end of lyric line) - PRIMARY
        # 2. Reached max words (safety for very long lines) - SECONDARY
        if ends_line or len(current_phrase) >= max_words:
            phrases.append(current_phrase)
            current_phrase = []
    
    # Add remaining words as final phrase
    if current_phrase:
        phrases.append(current_phrase)
    
    # Note: We don't merge short phrases anymore since line breaks are intentional

    
    # Generate ASS file
    with open(output_file, 'w') as f:
        # Write header
        f.write(create_ass_header(resolution_x, resolution_y, is_short))
        
        # Write dialogue lines with karaoke tags
        for phrase in phrases:
            if not phrase:
                continue
                
            # Phrase timing
            start_time = format_ass_timestamp(phrase[0]['start'])
            end_time = format_ass_timestamp(phrase[-1]['end'])
            
            # Build karaoke text with \kf tags
            # \kf<duration> creates progressive fill from secondary to primary color
            # Duration is in centiseconds (1/100th of a second)
            karaoke_text = ""
            for word_data in phrase:
                # Clean the word: remove newlines and excess whitespace
                word = word_data['word'].replace('\n', ' ').replace('\r', '').strip()
                # Skip empty words (can happen after stripping)
                if not word:
                    continue
                duration_cs = int((word_data['end'] - word_data['start']) * 100)
                # Minimum duration of 10cs (0.1s) to ensure visibility
                duration_cs = max(duration_cs, 10)
                karaoke_text += f"{{\\kf{duration_cs}}}{word} "
            
            karaoke_text = karaoke_text.strip()

            
            # Write dialogue line
            f.write(f"Dialogue: 0,{start_time},{end_time},Karaoke,,0,0,0,,{karaoke_text}\n")
    
    print(f"  Generated phrase-highlight ASS: {output_file}")
    print(f"  Phrases: {len(phrases)}, Words per phrase: {min_words}-{max_words}")


def convert_srt_to_pycaps_format(srt_path: Path) -> Dict:
    """
    Convert SRT word-level timestamps to pycaps Document JSON format.

    pycaps expects:
    {
      "segments": [
        {
          "lines": [
            {
              "words": [
                {
                  "text": "word",
                  "time": {"start": 0.0, "end": 1.0},
                  "clips": [],
                  "semantic_tags": [],
                  "structure_tags": [],
                  "max_layout": {"position": {"x": 0, "y": 0}, "size": {"width": 0, "height": 0}}
                }
              ],
              "time": {"start": 0.0, "end": 1.0},
              "structure_tags": [],
              "max_layout": {"position": {"x": 0, "y": 0}, "size": {"width": 0, "height": 0}}
            }
          ],
          "time": {"start": 0.0, "end": 1.0},
          "structure_tags": [],
          "max_layout": {"position": {"x": 0, "y": 0}, "size": {"width": 0, "height": 0}}
        }
      ]
    }
    """
    import re

    words = []

    # Parse SRT file
    with open(srt_path, 'r') as f:
        content = f.read()

    # SRT format: index, timestamp, text, blank line
    entries = content.strip().split('\n\n')

    for entry in entries:
        lines_in_entry = entry.split('\n')
        if len(lines_in_entry) < 3:
            continue

        # Parse timestamp line (format: HH:MM:SS,mmm --> HH:MM:SS,mmm)
        timestamp_line = lines_in_entry[1]
        match = re.match(r'(\d+):(\d+):(\d+),(\d+) --> (\d+):(\d+):(\d+),(\d+)', timestamp_line)
        if not match:
            continue

        # Convert to seconds
        start_h, start_m, start_s, start_ms, end_h, end_m, end_s, end_ms = map(int, match.groups())
        start_time = start_h * 3600 + start_m * 60 + start_s + start_ms / 1000
        end_time = end_h * 3600 + end_m * 60 + end_s + end_ms / 1000

        # Get word text
        text = lines_in_entry[2]

        # Create word entry
        words.append({
            "text": text,
            "time": {"start": start_time, "end": end_time},
            "clips": [],
            "semantic_tags": [],
            "structure_tags": [],
            "max_layout": {
                "position": {"x": 0, "y": 0},
                "size": {"width": 0, "height": 0}
            }
        })

    # Group all words into one line and one segment
    if not words:
        raise ValueError("No words found in SRT file")

    line = {
        "words": words,
        "time": {"start": words[0]["time"]["start"], "end": words[-1]["time"]["end"]},
        "structure_tags": [],
        "max_layout": {
            "position": {"x": 0, "y": 0},
            "size": {"width": 0, "height": 0}
        }
    }

    segment = {
        "lines": [line],
        "time": {"start": words[0]["time"]["start"], "end": words[-1]["time"]["end"]},
        "structure_tags": [],
        "max_layout": {
            "position": {"x": 0, "y": 0},
            "size": {"width": 0, "height": 0}
        }
    }

    return {"segments": [segment]}


def apply_pycaps_subtitles(video_path: Path, srt_path: Path, output_path: Path, css_template: Path) -> None:
    """Apply karaoke subtitles using pycaps."""
    from pycaps import CapsPipelineBuilder

    print(f"  Applying karaoke subtitles with pycaps...")
    print(f"  Video: {video_path}")
    print(f"  SRT: {srt_path}")
    print(f"  CSS: {css_template}")

    # Convert SRT to pycaps Document format
    pycaps_data = convert_srt_to_pycaps_format(srt_path)

    # Save as JSON for pycaps to load
    json_path = srt_path.with_suffix('.json')
    with open(json_path, 'w') as f:
        json.dump(pycaps_data, f)

    print(f"  Converted SRT to pycaps format: {json_path}")

    # Build pipeline with subtitle data and output path
    pipeline = (CapsPipelineBuilder()
        .with_input_video(str(video_path))
        .with_output_video(str(output_path))
        .with_subtitle_data_path(str(json_path))
        .add_css(str(css_template))
        .build())

    pipeline.run()
    print(f"  ✅ Karaoke subtitles applied")


def apply_ffmpeg_subtitles(video_path: Path, srt_path: Path, output_path: Path, config: Dict, subtitle_type: str = 'traditional', is_short: bool = False) -> None:
    """Apply subtitles using FFmpeg."""
    subtitle_config = config['subtitle_settings'][subtitle_type]
    font = subtitle_config['font']
    base_font_size = subtitle_config['font_size']

    # Increase font size by 50% for full-length videos for better readability
    font_size = base_font_size if is_short else int(base_font_size * 1.5)

    print(f"  Burning {subtitle_type} subtitles with FFmpeg...")
    print(f"  Font: {font}, Size: {font_size} ({'shorts' if is_short else 'full video - 50% larger'})")

    # Convert SRT to ASS for better styling control
    ass_path = srt_path.with_suffix('.ass')

    # First convert SRT to ASS with styling
    cmd_convert = [
        get_executable_path('ffmpeg'), '-y',
        '-i', str(srt_path),
        '-f', 'ass',
        str(ass_path)
    ]

    result = subprocess.run(cmd_convert, capture_output=True, text=True)
    if result.returncode != 0:
        raise Exception(f"FFmpeg SRT->ASS conversion failed: {result.stderr}")

    # For shorts (9:16 vertical), calculate vertical margin to position subtitles ~25% from bottom
    # We detect actual video height and calculate margin proportionally
    margin_v = 0
    if is_short:
        # Get actual video dimensions using ffprobe
        probe_cmd = [
            get_executable_path('ffprobe'), '-v', 'error',
            '-select_streams', 'v:0',
            '-show_entries', 'stream=height',
            '-of', 'csv=p=0',
            str(video_path)
        ]
        probe_result = subprocess.run(probe_cmd, capture_output=True, text=True)
        if probe_result.returncode == 0:
            try:
                video_height = int(probe_result.stdout.strip())
                # ASS uses PlayResY of 288 by default, so we need to scale the margin
                # 25% of video height, scaled to ASS canvas
                # For a 1920px video at 25% from bottom = 480px real margin
                # Scaled to 288px canvas: 480 * (288/1920) = 72
                ass_canvas_height = 288  # FFmpeg default
                real_margin = int(video_height * 0.25)
                margin_v = int(real_margin * (ass_canvas_height / video_height))
                print(f"  Detected video height: {video_height}px")
                print(f"  Applying vertical margin for shorts: {margin_v}px in ASS canvas (25% from bottom)")
            except ValueError:
                print(f"  ⚠️  Could not detect video height, using default margin")
                margin_v = 72  # Fallback: 25% of 288
        else:
            margin_v = 72  # Fallback

    # Burn ASS subtitles into video
    # Note: force_style overrides the style defined in the ASS file
    # Explicitly set Alignment=2 (Bottom Center) to ensure MarginV is from bottom
    style = f"FontName={font},FontSize={font_size},PrimaryColour=&HFFFFFF&,OutlineColour=&H000000&,Outline=3,Shadow=2,Alignment=2,MarginV={margin_v}"
    cmd_burn = [
        get_executable_path('ffmpeg'), '-y',
        '-i', str(video_path),
        '-vf', f"subtitles={ass_path}:force_style='{style}'",
        '-c:v', 'libx264',
        '-c:a', 'copy',
        str(output_path)
    ]

    result = subprocess.run(cmd_burn, capture_output=True, text=True)
    if result.returncode != 0:
        raise Exception(f"FFmpeg subtitle burn failed: {result.stderr}")


    print(f"  ✅ Traditional subtitles burned")


def burn_ass_subtitles(video_path: Path, ass_path: Path, output_path: Path) -> None:
    """
    Burn pre-styled ASS subtitles into video.
    
    Uses the styles defined in the ASS file directly without force_style override.
    This preserves karaoke effects and custom styling.
    """
    print(f"  Burning ASS subtitles with FFmpeg...")
    print(f"  ASS file: {ass_path}")
    
    cmd = [
        get_executable_path('ffmpeg'), '-y',
        '-i', str(video_path),
        '-vf', f"ass={ass_path}",
        '-c:v', 'libx264',
        '-c:a', 'copy',
        str(output_path)
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise Exception(f"FFmpeg ASS burn failed: {result.stderr}")
    
    print(f"  ✅ Karaoke subtitles burned")


def main():
    """Main execution."""
    import argparse

    parser = argparse.ArgumentParser(description='Generate and apply video subtitles')
    parser.add_argument('--engine', choices=['pycaps', 'ffmpeg'], required=True,
                       help='Subtitle engine to use')
    parser.add_argument('--type', choices=['karaoke', 'traditional'], required=True,
                       help='Subtitle style')
    parser.add_argument('--video', choices=['full', 'short_hook', 'short_educational'], required=True,
                       help='Which video to subtitle')
    parser.add_argument('--segment', help='Segment name for loading correct timestamps')

    args = parser.parse_args()

    print(f"🎬 Generating {args.type} subtitles with {args.engine}...")

    config = load_config()
    lyrics = load_lyrics()

    # Normalize lyrics format (handles both alignedWords and words formats)
    all_words = normalize_lyrics_format(lyrics)

    output_dir = Path(os.environ['OUTPUT_DIR'])
    subtitles_dir = output_dir / 'subtitles'
    subtitles_dir.mkdir(exist_ok=True)

    # Determine segment for timestamp filtering
    segment = args.segment or args.video.replace('short_', '')

    # Load segment info if needed
    if segment != 'full':
        segments_file = output_dir / 'segments.json'
        with open(segments_file) as f:
            segments = json.load(f)

        segment_info = segments[segment]

        # Filter words to segment timeframe
        words = [
            w for w in all_words
            if segment_info['start'] <= w['start'] <= segment_info['end']
        ]

        # Adjust timestamps to start from 0
        offset = segment_info['start']
        for w in words:
            w['start'] -= offset
            w['end'] -= offset
    else:
        words = all_words

    # Detect if this is a short video (9:16 vertical format)
    is_short = args.video in ['short_hook', 'short_educational']
    
    # Get video dimensions for ASS file
    video_file = output_dir / f"{args.video}.mp4"
    resolution_x, resolution_y = 1080, 1920  # Default for shorts
    
    probe_cmd = [
        get_executable_path('ffprobe'), '-v', 'error',
        '-select_streams', 'v:0',
        '-show_entries', 'stream=width,height',
        '-of', 'csv=p=0',
        str(video_file)
    ]
    probe_result = subprocess.run(probe_cmd, capture_output=True, text=True)
    if probe_result.returncode == 0:
        try:
            dims = probe_result.stdout.strip().split(',')
            resolution_x, resolution_y = int(dims[0]), int(dims[1])
            print(f"  Detected video resolution: {resolution_x}x{resolution_y}")
        except (ValueError, IndexError):
            print(f"  ⚠️  Could not parse video dimensions, using defaults")

    # Generate subtitles
    if args.type == 'karaoke':
        # Use new phrase-highlight ASS generation with word highlighting
        ass_file = subtitles_dir / f"{args.video}_karaoke.ass"
        
        # Word count per phrase: shorts get fewer words for readability
        min_words = 3
        max_words = 7 if is_short else 10
        
        generate_phrase_highlight_ass(
            words, ass_file, 
            min_words=min_words, 
            max_words=max_words,
            resolution_x=resolution_x,
            resolution_y=resolution_y,
            is_short=is_short
        )
        
        print(f"  Generated: {ass_file}")
        
        # Burn ASS subtitles directly (preserves karaoke styling)
        output_file = output_dir / f"{args.video}_subtitled.mp4"
        burn_ass_subtitles(video_file, ass_file, output_file)
        
    else:
        # Traditional subtitles (SRT-based)
        srt_file = subtitles_dir / f"{args.video}_traditional.srt"
        min_dur = config['subtitle_settings']['traditional']['phrase_min_duration']
        max_dur = config['subtitle_settings']['traditional']['phrase_max_duration']
        generate_traditional_srt(words, srt_file, min_dur, max_dur)
        
        print(f"  Generated: {srt_file}")
        
        # Apply subtitles to video
        output_file = output_dir / f"{args.video}_subtitled.mp4"
        
        if args.engine == 'pycaps':
            # Check if css_template is configured for pycaps
            karaoke_config = config.get('subtitle_settings', {}).get('karaoke', {})
            css_template_path = karaoke_config.get('css_template', '').strip()
            if css_template_path:
                css_template = Path(css_template_path)
                apply_pycaps_subtitles(video_file, srt_file, output_file, css_template)
            else:
                print("  ⚠️  pycaps requested but css_template not configured, falling back to ffmpeg")
                apply_ffmpeg_subtitles(video_file, srt_file, output_file, config, args.type, is_short)
        else:
            apply_ffmpeg_subtitles(video_file, srt_file, output_file, config, args.type, is_short)

    # Replace original with subtitled version
    video_file.unlink()
    output_file.rename(video_file)

    print("✅ Subtitles applied successfully")


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
