#!/usr/bin/env python3
"""
Unified subtitle generator supporting both traditional and karaoke styles.
"""

import json
import os
import sys
import subprocess
from pathlib import Path
from typing import Dict, List


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


def apply_ffmpeg_subtitles(video_path: Path, srt_path: Path, output_path: Path, config: Dict, subtitle_type: str = 'traditional') -> None:
    """Apply subtitles using FFmpeg."""
    subtitle_config = config['subtitle_settings'][subtitle_type]
    font = subtitle_config['font']
    font_size = subtitle_config['font_size']

    print(f"  Burning {subtitle_type} subtitles with FFmpeg...")
    print(f"  Font: {font}, Size: {font_size}")

    # Convert SRT to ASS for better styling control
    ass_path = srt_path.with_suffix('.ass')

    # First convert SRT to ASS with styling
    cmd_convert = [
        'ffmpeg', '-y',
        '-i', str(srt_path),
        '-f', 'ass',
        str(ass_path)
    ]

    result = subprocess.run(cmd_convert, capture_output=True, text=True)
    if result.returncode != 0:
        raise Exception(f"FFmpeg SRT->ASS conversion failed: {result.stderr}")

    # Burn ASS subtitles into video
    # Note: force_style doesn't work in newer FFmpeg, use subtitles filter instead
    cmd_burn = [
        'ffmpeg', '-y',
        '-i', str(video_path),
        '-vf', f"subtitles={ass_path}:force_style='FontName={font},FontSize={font_size},PrimaryColour=&HFFFFFF&,OutlineColour=&H000000&,Outline=3,Shadow=2'",
        '-c:v', 'libx264',
        '-c:a', 'copy',
        str(output_path)
    ]

    result = subprocess.run(cmd_burn, capture_output=True, text=True)
    if result.returncode != 0:
        raise Exception(f"FFmpeg subtitle burn failed: {result.stderr}")

    print(f"  ✅ Traditional subtitles burned")


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

    # Generate appropriate SRT
    if args.type == 'karaoke':
        srt_file = subtitles_dir / f"{args.video}_karaoke.srt"
        generate_karaoke_srt(words, srt_file)
    else:
        srt_file = subtitles_dir / f"{args.video}_traditional.srt"
        min_dur = config['subtitle_settings']['traditional']['phrase_min_duration']
        max_dur = config['subtitle_settings']['traditional']['phrase_max_duration']
        generate_traditional_srt(words, srt_file, min_dur, max_dur)

    print(f"  Generated: {srt_file}")

    # Apply subtitles to video
    video_file = output_dir / f"{args.video}.mp4"
    output_file = output_dir / f"{args.video}_subtitled.mp4"

    if args.engine == 'pycaps':
        # Check if css_template is configured for pycaps
        karaoke_config = config.get('subtitle_settings', {}).get('karaoke', {})
        if 'css_template' in karaoke_config:
            css_template = Path(karaoke_config['css_template'])
            apply_pycaps_subtitles(video_file, srt_file, output_file, css_template)
        else:
            print("  ⚠️  pycaps requested but css_template not configured, falling back to ffmpeg")
            apply_ffmpeg_subtitles(video_file, srt_file, output_file, config, args.type)
    else:
        apply_ffmpeg_subtitles(video_file, srt_file, output_file, config, args.type)

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
