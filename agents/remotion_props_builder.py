#!/usr/bin/env python3
"""
Builds Remotion overlay props JSON from pipeline artifacts.

Reads: research.json, lyrics_aligned.json, phrase_groups.json,
       approved_media.json, educational_images/edu_image_manifest.json
Produces: OverlayProps dict matching agents/remotion/src/types.ts
"""

import json
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Literal

FormatType = Literal["full", "short_hook", "short_educational", "short_intro"]


def _read_json(path: Path) -> Any:
    """Read and parse a JSON file. Returns empty dict/list on failure."""
    if not path.exists():
        return {}
    with open(path) as f:
        return json.load(f)


def _seconds_to_ms(seconds: float) -> int:
    """Convert seconds to integer milliseconds."""
    return int(round(seconds * 1000))


def _load_aligned_words(run_dir: Path) -> List[Dict]:
    """Load word-level timestamps from suno_output.json or lyrics_aligned.json."""
    for filename in ("lyrics_aligned.json", "suno_output.json"):
        path = run_dir / filename
        if not path.exists():
            continue
        data = _read_json(path)
        if "alignedWords" in data:
            return [
                {
                    "word": w["word"].replace("\n", " ").strip(),
                    "startS": w["startS"],
                    "endS": w["endS"],
                }
                for w in data["alignedWords"]
                if w.get("word", "").strip()
            ]
    return []


def _enrich_phrases_with_words(
    phrase_groups: List[Dict], aligned_words: List[Dict]
) -> List[Dict]:
    """
    Attach word-level timing to phrase groups that lack it.

    Matches aligned words to phrases by time overlap: a word belongs to
    the phrase whose time range contains the word's midpoint.
    """
    if not aligned_words:
        return phrase_groups

    enriched = []
    for group in phrase_groups:
        if group.get("words"):
            enriched.append(group)
            continue

        start_s = group.get("startS", group.get("start_time", 0))
        end_s = group.get("endS", group.get("end_time", 0))

        matched_words = [
            w for w in aligned_words
            if start_s <= (w["startS"] + w["endS"]) / 2 <= end_s
        ]

        enriched.append({**group, "words": matched_words})

    return enriched


def _build_phrases(phrase_groups: List[Dict]) -> List[Dict]:
    """Convert pipeline phrase groups to Remotion PhraseGroup format."""
    phrases = []
    for group in phrase_groups:
        start_s = group.get("startS", group.get("start_time", 0))
        end_s = group.get("endS", group.get("end_time", 0))

        phrase_start_ms = _seconds_to_ms(start_s)
        phrase_end_ms = _seconds_to_ms(end_s)

        words = []
        for w in group.get("words", []):
            w_start = w.get("startS", w.get("start", 0))
            w_end = w.get("endS", w.get("end", 0))
            words.append({
                "word": w.get("word", ""),
                "startMs": max(_seconds_to_ms(w_start), phrase_start_ms),
                "endMs": min(_seconds_to_ms(w_end), phrase_end_ms),
            })

        phrases.append({
            "text": group.get("text", ""),
            "startMs": phrase_start_ms,
            "endMs": phrase_end_ms,
            "words": words,
        })

    return phrases


def _build_edu_images(run_dir: Path) -> List[Dict]:
    """Read educational image manifest and convert to Remotion format."""
    # If SVG manifest exists, raster images are not used (SVG replaces raster)
    svg_manifest = run_dir / "educational_images" / "edu_svg_manifest.json"
    if svg_manifest.exists():
        return []

    edu_dir = run_dir / "educational_images"
    manifest_path = edu_dir / "edu_image_manifest.json"
    manifest = _read_json(manifest_path)

    images = []
    for img in manifest.get("images", []):
        if img.get("generation_status") not in (None, "success"):
            continue

        # Resolve image path: local_path (absolute) or file (relative to edu dir)
        src = img.get("local_path", "")
        if not src or not Path(src).exists():
            filename = img.get("file", "")
            if filename:
                src = str(edu_dir / filename)

        if not src or not Path(src).exists():
            continue

        # Convert region data, using camelCase for TypeScript
        regions = []
        for region in img.get("regions", []):
            bounds = region.get("bounds", {})
            regions.append({
                "label": region.get("label", ""),
                "bounds": {
                    "x": bounds.get("x", 0),
                    "y": bounds.get("y", 0),
                    "w": bounds.get("w", 100),
                    "h": bounds.get("h", 100),
                },
                "order": region.get("order", 1),
                "fromDirection": region.get("from_direction", "left"),
                "delayMs": region.get("delay_ms", 300),
            })

        # Use suggested duration from region analysis if available
        start_time_s = img.get("start_time", 0)
        end_time_s = img.get("end_time", 0)
        suggested = img.get("suggested_duration")
        if suggested and suggested > (end_time_s - start_time_s):
            end_time_s = start_time_s + suggested
            # Don't extend more than 3s beyond original
            original_end = img.get("end_time", 0)
            end_time_s = min(end_time_s, original_end + 3.0)

        # Get image dimensions for Remotion coordinate mapping
        img_width, img_height = 1248, 832  # defaults
        try:
            result = subprocess.run(
                ["ffprobe", "-v", "error", "-select_streams", "v:0",
                 "-show_entries", "stream=width,height", "-of", "csv=p=0",
                 str(Path(src).resolve())],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode == 0:
                parts = result.stdout.strip().split(",")
                img_width, img_height = int(parts[0]), int(parts[1])
        except Exception:
            pass

        images.append({
            "src": str(Path(src).resolve()),
            "startMs": _seconds_to_ms(start_time_s),
            "endMs": _seconds_to_ms(end_time_s),
            "concept": img.get("concept", img.get("key_fact", "")),
            "regions": regions,
            "imageWidth": img_width,
            "imageHeight": img_height,
        })

    return images


def _build_edu_diagrams(run_dir: Path) -> List[Dict]:
    """Read SVG diagram manifest and convert to Remotion format."""
    edu_dir = run_dir / "educational_images"
    svg_manifest_path = edu_dir / "edu_svg_manifest.json"

    if not svg_manifest_path.exists():
        return []

    manifest = _read_json(svg_manifest_path)

    # Support both manifest formats: "diagrams" (spec) and "svgs" (actual agent output)
    entries = manifest.get("diagrams", manifest.get("svgs", []))

    diagrams = []
    for d in entries:
        if d.get("generation_status") != "success":
            continue

        # SVG content can be inline ("svg_content") or in a file ("svg_file")
        svg_content = d.get("svg_content", "")
        if not svg_content and d.get("svg_file"):
            svg_path = edu_dir / d["svg_file"]
            if svg_path.exists():
                svg_content = svg_path.read_text()

        if not svg_content:
            continue

        diagrams.append({
            "svgContent": svg_content,
            "concept": d.get("key_fact", ""),
            "startMs": _seconds_to_ms(d.get("start_time", 0)),
            "endMs": _seconds_to_ms(d.get("end_time", 0)),
        })

    return diagrams


def _determine_transition_type(prev_shot: Dict, next_shot: Dict) -> str:
    """Pick transition type based on media types at the boundary."""
    next_source = next_shot.get("source", "")
    prev_source = prev_shot.get("source", "")

    if next_source == "educational_image" or prev_source == "educational_image":
        return "iris"
    if next_source == "ai_generated" or prev_source == "ai_generated":
        return "fade"
    return "wipe"


def _build_shot_boundaries(approved_data: Dict) -> List[Dict]:
    """Extract shot boundary times and assign transition types."""
    shots = approved_data.get("shot_list", [])
    boundaries = []

    for i in range(len(shots) - 1):
        boundary_time = shots[i].get("end_time", 0)
        transition_type = _determine_transition_type(shots[i], shots[i + 1])
        boundaries.append({
            "timeMs": _seconds_to_ms(boundary_time),
            "transitionType": transition_type,
        })

    return boundaries


def _is_short_format(format_type: FormatType) -> bool:
    """Return True if the format is a short-form vertical video."""
    return format_type in ("short_hook", "short_educational", "short_intro")


def _get_hook_text(run_dir: Path, title: str) -> str:
    """Generate hook text from lyrics or title."""
    lyrics_path = run_dir / "lyrics.json"
    if lyrics_path.exists():
        try:
            lyrics_data = json.loads(lyrics_path.read_text())
            viral = lyrics_data.get("viral_elements", {})
            display_hook = viral.get("display_hook_text", "").strip()
            if display_hook:
                words = display_hook.split()
                return " ".join(words[:7]) + ("..." if len(words) > 7 else "")
            hook_line = viral.get("hook_line", "").strip()
            if hook_line:
                words = hook_line.split()
                return " ".join(words[:7]) + ("..." if len(words) > 7 else "")
        except (json.JSONDecodeError, OSError):
            pass

    # Fallback: derive from title
    clean = title.replace(" Explained", "").replace(" (Music Video)", "").strip()
    lower = clean.lower()
    if lower.startswith("how "):
        return f"{clean[4:]}?!"
    elif lower.startswith(("why ", "what ")):
        return f"{clean}?"
    elif lower.startswith("the "):
        return f"{clean[4:]}?!"
    return f"{clean}?!"


def _shift_to_segment(items: List[Dict], segment_start_ms: int, segment_end_ms: int) -> List[Dict]:
    """
    Filter and shift timed items to segment-relative timestamps.

    Items must have startMs/endMs fields. Only items overlapping the
    segment range are kept, and their times are shifted so segment
    start becomes 0ms.
    """
    shifted = []
    for item in items:
        if item["endMs"] <= segment_start_ms or item["startMs"] >= segment_end_ms:
            continue

        result = {
            **item,
            "startMs": max(0, item["startMs"] - segment_start_ms),
            "endMs": min(segment_end_ms - segment_start_ms, item["endMs"] - segment_start_ms),
        }

        # Shift word timestamps too if present
        if "words" in item:
            result["words"] = [
                {
                    **w,
                    "startMs": max(0, w["startMs"] - segment_start_ms),
                    "endMs": min(segment_end_ms - segment_start_ms, w["endMs"] - segment_start_ms),
                }
                for w in item.get("words", [])
                if w["endMs"] > segment_start_ms and w["startMs"] < segment_end_ms
            ]

        shifted.append(result)

    return shifted


def build_overlay_props(
    run_dir: Path,
    config: Dict,
    format_type: FormatType,
    duration_ms: int,
    segment_start_s: float = 0.0,
) -> Dict:
    """
    Build complete OverlayProps dict for Remotion render.

    Args:
        run_dir: Pipeline run directory containing all artifacts
        config: Loaded config/config.json
        format_type: Video format being rendered
        duration_ms: Total video duration in milliseconds
        segment_start_s: Start time of this segment in the full song (seconds).
                         All timestamps are shifted so this becomes 0ms.

    Returns:
        Dict matching OverlayProps TypeScript interface
    """
    video_settings = config.get("video_settings", {})
    resolution = video_settings.get("resolution", [1080, 1920])
    fps = video_settings.get("fps", 30)

    research = _read_json(run_dir / "research.json")
    title = research.get("video_title", "Educational Video")

    phrase_groups = _read_json(run_dir / "phrase_groups.json")
    if isinstance(phrase_groups, dict):
        phrase_groups = phrase_groups.get("phrase_groups", [])

    # Enrich phrase groups with word-level timing from Suno aligned words
    aligned_words = _load_aligned_words(run_dir)
    if isinstance(phrase_groups, list):
        phrase_groups = _enrich_phrases_with_words(phrase_groups, aligned_words)

    approved = _read_json(run_dir / "approved_media.json")

    is_short = _is_short_format(format_type)
    remotion_config = config.get("remotion_overlay", {})

    all_phrases = _build_phrases(phrase_groups if isinstance(phrase_groups, list) else [])
    all_edu_images = _build_edu_images(run_dir)
    all_edu_diagrams = _build_edu_diagrams(run_dir)
    all_boundaries = _build_shot_boundaries(approved)

    # Shift to segment-relative timestamps for shorts that start mid-song
    segment_start_ms = _seconds_to_ms(segment_start_s)
    segment_end_ms = segment_start_ms + duration_ms

    phrases = _shift_to_segment(all_phrases, segment_start_ms, segment_end_ms)
    edu_images = _shift_to_segment(all_edu_images, segment_start_ms, segment_end_ms)
    edu_diagrams = _shift_to_segment(all_edu_diagrams, segment_start_ms, segment_end_ms)
    shot_boundaries = [
        {**b, "timeMs": b["timeMs"] - segment_start_ms}
        for b in all_boundaries
        if segment_start_ms <= b["timeMs"] <= segment_end_ms
    ]

    return {
        "durationMs": duration_ms,
        "fps": fps,
        "width": resolution[0],
        "height": resolution[1],
        "hookText": _get_hook_text(run_dir, title),
        "titleText": title,
        "channelName": remotion_config.get("channel_name", "@learningsciencemusic"),
        "isShort": is_short,
        "phrases": phrases,
        "eduImages": edu_images,
        "eduDiagrams": edu_diagrams,
        "shotBoundaries": shot_boundaries,
        "animateHook": False,
        "karaokeEnabled": remotion_config.get("karaoke_enabled", True),
        "eduRevealEnabled": remotion_config.get("edu_reveal_enabled", True),
        "transitionsEnabled": remotion_config.get("transitions_enabled", False),
    }
