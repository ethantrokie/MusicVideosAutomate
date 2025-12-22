#!/usr/bin/env python3
"""
Segment analyzer for multi-format video generation.
Identifies musical hook and educational peak segments from full song.
"""

import json
import os
import sys
import subprocess
from pathlib import Path
from typing import Dict, List, Tuple


def load_lyrics() -> Dict:
    """Load Suno lyrics with word-level timestamps."""
    lyrics_file = Path(f"{os.environ['OUTPUT_DIR']}/suno_output.json")
    with open(lyrics_file) as f:
        data = json.load(f)

    # Handle both old and new Suno API formats
    if 'alignedWords' in data:
        # New format: convert alignedWords to words
        words = []
        for word_data in data['alignedWords']:
            words.append({
                'word': word_data['word'],
                'start': word_data['startS'],
                'end': word_data['endS']
            })
        data['words'] = words

    return data


def detect_musical_hook(lyrics: Dict, min_duration: float = 30, max_duration: float = 60) -> Dict:
    """
    Detect chorus/hook section using lyric repetition analysis.

    Strategy:
    1. Find phrases that repeat 2+ times (likely chorus)
    2. Locate first complete repetition within duration range
    3. Fallback to seconds 30-90 if no clear chorus

    Returns segment with start/end timestamps and rationale.
    """
    words = lyrics.get('words', [])
    if not words:
        raise ValueError("No word-level timestamps in lyrics")

    # Build phrases (group by punctuation or 5-word chunks)
    phrases = []
    current_phrase = []
    phrase_start_idx = 0

    for i, word_data in enumerate(words):
        current_phrase.append(word_data['word'].lower().strip())

        # End phrase on punctuation or max 8 words
        if word_data['word'].endswith(('.', ',', '!', '?')) or len(current_phrase) >= 8:
            phrase_text = ' '.join(current_phrase)
            phrases.append({
                'text': phrase_text,
                'start': words[phrase_start_idx]['start'],
                'word_indices': list(range(phrase_start_idx, i + 1))
            })
            current_phrase = []
            phrase_start_idx = i + 1

    # Add remaining words as final phrase
    if current_phrase:
        phrase_text = ' '.join(current_phrase)
        phrases.append({
            'text': phrase_text,
            'start': words[phrase_start_idx]['start'],
            'word_indices': list(range(phrase_start_idx, len(words)))
        })

    # Find repeated phrases
    phrase_counts = {}
    for i, phrase in enumerate(phrases):
        text = phrase['text']
        if text not in phrase_counts:
            phrase_counts[text] = []
        phrase_counts[text].append(i)

    # Find chorus (most repeated phrase with 2+ occurrences)
    repeated = {text: indices for text, indices in phrase_counts.items() if len(indices) >= 2}

    if repeated:
        # Get most common phrase
        chorus_text = max(repeated, key=lambda x: len(repeated[x]))
        chorus_indices = repeated[chorus_text]

        # Use first occurrence
        first_idx = chorus_indices[0]
        phrase_group = phrases[first_idx:min(first_idx+3, len(phrases))]  # Take up to 3 phrases for full chorus

        start_time = phrase_group[0]['start']
        end_word_idx = phrase_group[-1]['word_indices'][-1]
        end_time = words[min(end_word_idx, len(words)-1)]['end']

        duration = end_time - start_time

        # Adjust to fit duration range
        if duration < min_duration:
            # Extend forward
            end_time = min(start_time + max_duration, words[-1]['end'])
        elif duration > max_duration:
            # Trim to max
            end_time = start_time + max_duration

        return {
            'start': round(start_time, 2),
            'end': round(end_time, 2),
            'duration': round(end_time - start_time, 2),
            'rationale': f'First chorus repetition: "{chorus_text[:50]}..."'
        }

    # Fallback: Use seconds 30+ with max_duration constraint (typically 30s for shorts)
    fallback_start = 30
    fallback_end = min(fallback_start + max_duration, words[-1]['end'])
    fallback_duration = fallback_end - fallback_start

    # Adjust to min duration if needed
    if fallback_duration < min_duration:
        fallback_end = min(fallback_start + max_duration, words[-1]['end'])

    return {
        'start': fallback_start,
        'end': round(fallback_end, 2),
        'duration': round(fallback_end - fallback_start, 2),
        'rationale': 'Fallback: typical hook placement (30-90s)'
    }


def analyze_educational_peak(lyrics: Dict, topic: str, min_duration: float = 30, max_duration: float = 60) -> Dict:
    """
    Use Claude CLI to identify the most educational segment.

    Returns segment with start/end timestamps and rationale.
    """
    # Get full lyrics text
    words = lyrics.get('words', [])
    lyrics_text = ' '.join([w['word'] for w in words])

    # Build prompt for Claude
    prompt = f"""Analyze these song lyrics about "{topic}" and identify the {min_duration}-{max_duration} second segment with the HIGHEST EDUCATIONAL VALUE.

LYRICS WITH TIMESTAMPS:
{json.dumps(words, indent=2)}

TASK:
1. Identify the segment where the key concept is explained most clearly
2. Look for definitions, examples, or cause-and-effect explanations
3. Segment must be {min_duration}-{max_duration} seconds long
4. Return ONLY valid JSON with this exact schema:

{{
  "start_timestamp": <float>,
  "end_timestamp": <float>,
  "rationale": "<brief explanation of educational value>"
}}

CRITICAL: Respond with ONLY the JSON object, no markdown, no explanation."""

    try:
        result = subprocess.run(
            ['claude', '-p', prompt, '--model', 'claude-haiku-4-5', '--dangerously-skip-permissions'],
            capture_output=True,
            text=True,
            timeout=60
        )

        if result.returncode != 0:
            raise Exception(f"Claude CLI failed: {result.stderr}")

        # Parse JSON response
        output = result.stdout.strip()

        # Remove markdown code blocks if present
        if '```json' in output:
            output = output.split('```json')[1].split('```')[0].strip()
        elif '```' in output:
            output = output.split('```')[1].split('```')[0].strip()

        analysis = json.loads(output)

        start = analysis['start_timestamp']
        end = analysis['end_timestamp']
        duration = end - start

        # Validate duration
        if duration < min_duration or duration > max_duration:
            raise ValueError(f"Claude returned invalid duration: {duration}s")

        return {
            'start': round(start, 2),
            'end': round(end, 2),
            'duration': round(duration, 2),
            'rationale': analysis['rationale']
        }

    except Exception as e:
        print(f"  ⚠️  Claude analysis failed: {e}", file=sys.stderr)
        print(f"  Using fallback: first {min_duration}s of song", file=sys.stderr)

        # Fallback: First segment after intro
        fallback_start = 10  # Skip intro
        fallback_end = min(fallback_start + max_duration, words[-1]['end'])

        return {
            'start': fallback_start,
            'end': round(fallback_end, 2),
            'duration': round(fallback_end - fallback_start, 2),
            'rationale': 'Fallback: first educational segment after intro'
        }


def main():
    """Main execution."""
    print("🎯 Analyzing song segments...")

    # Load lyrics
    lyrics = load_lyrics()

    # Load topic
    topic_file = Path('input/idea.txt')
    topic = topic_file.read_text().strip().split('.')[0]

    # Load shorts duration from config
    with open('config/config.json') as f:
        config = json.load(f)
    shorts_duration = config.get('video_formats', {}).get('shorts', {}).get('hook_duration', 35)
    min_dur, max_dur = shorts_duration, shorts_duration

    # Analyze segments
    print("  Detecting musical hook...")
    hook_segment = detect_musical_hook(lyrics, min_dur, max_dur)

    print("  Analyzing educational peak...")
    edu_segment = analyze_educational_peak(lyrics, topic, min_dur, max_dur)

    # Full video segment
    full_duration = lyrics['metadata']['duration']
    full_segment = {
        'start': 0,
        'end': full_duration,
        'duration': full_duration,
        'rationale': 'Complete song for full video'
    }

    # Save segments
    output = {
        'full': full_segment,
        'hook': hook_segment,
        'educational': edu_segment
    }

    segments_file = Path(f"{os.environ['OUTPUT_DIR']}/segments.json")
    with open(segments_file, 'w') as f:
        json.dump(output, f, indent=2)

    print(f"✅ Segments analyzed:")
    print(f"  Full: 0-{full_duration:.1f}s")
    print(f"  Hook: {hook_segment['start']:.1f}-{hook_segment['end']:.1f}s ({hook_segment['duration']:.1f}s)")
    print(f"  Educational: {edu_segment['start']:.1f}-{edu_segment['end']:.1f}s ({edu_segment['duration']:.1f}s)")


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        sys.exit(1)
