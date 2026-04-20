#!/usr/bin/env python3
"""
Remotion overlay render orchestrator.

Pipeline integration point that:
1. Builds props JSON from pipeline artifacts
2. Invokes Remotion CLI to render transparent overlay video
3. Composites overlay onto base video with FFmpeg
4. Falls back to existing MoviePy overlays on failure
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Dict, List, Optional

sys.path.insert(0, str(Path(__file__).parent))
from remotion_props_builder import build_overlay_props, FormatType
from engagement_experiments import is_engagement_feature_enabled

REMOTION_DIR = Path(__file__).parent / "remotion"
COMPOSITION_ID = "OverlayComposition"


def should_render_remotion_overlay(config: Dict) -> bool:
    """Check if Remotion overlay rendering is enabled."""
    return config.get("remotion_overlay", {}).get("enabled", False)


def _find_executable(name: str) -> str:
    """Find an executable, checking common paths for launchd compatibility."""
    found = shutil.which(name)
    if found:
        return found
    fallback_paths = [
        f"/opt/homebrew/bin/{name}",
        f"/usr/local/bin/{name}",
        f"/usr/bin/{name}",
    ]
    for path in fallback_paths:
        if os.path.exists(path) and os.access(path, os.X_OK):
            return path
    return name


def _get_segment_start(run_dir: Path, format_type: FormatType) -> float:
    """Get segment start time in seconds for a given format."""
    segments_path = run_dir / "segments.json"
    if not segments_path.exists():
        return 0.0

    try:
        with open(segments_path) as f:
            segments = json.load(f)
    except (json.JSONDecodeError, OSError):
        return 0.0

    segment_map = {
        "full": "full",
        "short_hook": "hook",
        "short_educational": "educational",
        "short_intro": "intro",
    }
    segment_key = segment_map.get(format_type, "full")
    return segments.get(segment_key, {}).get("start", 0.0)


def _build_remotion_render_command(
    props_path: Path,
    output_path: Path,
    remotion_dir: Path,
) -> List[str]:
    """Build the npx remotion render CLI command."""
    npx = _find_executable("npx")
    return [
        npx, "remotion", "render",
        "src/index.ts",
        COMPOSITION_ID,
        str(output_path),
        "--codec=prores",
        "--prores-profile=4444",
        "--pixel-format=yuva444p10le",
        "--image-format=png",
        f"--props={props_path}",
        "--log=error",
    ]


def _build_composite_command(
    base_video: Path,
    overlay_video: Path,
    output_path: Path,
) -> List[str]:
    """Build FFmpeg command to composite overlay onto base video."""
    ffmpeg = _find_executable("ffmpeg")
    return [
        ffmpeg, "-y",
        "-i", str(base_video),
        "-i", str(overlay_video),
        "-filter_complex", "[0:v][1:v]overlay=0:0:format=auto[outv]",
        "-map", "[outv]",
        "-map", "0:a?",
        "-c:v", "libx264",
        "-preset", "medium",
        "-c:a", "copy",
        str(output_path),
    ]


def render_overlay(
    run_dir: Path,
    config: Dict,
    format_type: FormatType,
    base_video_path: Path,
    duration_ms: int,
) -> Optional[Path]:
    """
    Render Remotion overlay and composite onto base video.

    Returns: Path to composited video, or None on failure (caller should fall back)
    """
    if not should_render_remotion_overlay(config):
        return None

    if not (REMOTION_DIR / "node_modules").exists():
        print("  ⚠️  Remotion node_modules not found. Run: cd agents/remotion && npm install")
        return None

    segment_start_s = _get_segment_start(run_dir, format_type)
    props = build_overlay_props(run_dir, config, format_type, duration_ms, segment_start_s)
    props["animateHook"] = is_engagement_feature_enabled("engagement_animated_hook")
    props["transitionsEnabled"] = config.get("remotion_overlay", {}).get("transitions_enabled", False)

    # Copy edu images to Remotion's public/ dir so Chrome can serve them
    public_dir = REMOTION_DIR / "public"
    public_dir.mkdir(exist_ok=True)
    for img in props.get("eduImages", []):
        src_path = Path(img["src"])
        if src_path.exists():
            dest = public_dir / src_path.name
            shutil.copy2(str(src_path), str(dest))
            img["src"] = src_path.name  # Remotion staticFile() uses filename only

    # Copy embedded images from SVG diagrams to Remotion's public/
    import re
    for diagram in props.get("eduDiagrams", []):
        svg = diagram.get("svgContent", "")
        for match in re.finditer(r'href="([^"]+\.png)"', svg):
            filename = match.group(1)
            src_path = run_dir.resolve() / "educational_images" / filename
            if src_path.exists():
                dest = public_dir / filename
                shutil.copy2(str(src_path), str(dest))

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(props, f)
        props_path = Path(f.name)

    overlay_path = run_dir.resolve() / f"overlay_{format_type}.mov"
    output_path = run_dir.resolve() / f"{format_type}_with_overlay.mp4"
    base_video_path = base_video_path.resolve()

    try:
        print(f"  🎨 Rendering Remotion overlay for {format_type}...")
        render_cmd = _build_remotion_render_command(props_path.resolve(), overlay_path, REMOTION_DIR.resolve())
        result = subprocess.run(render_cmd, capture_output=True, text=True, cwd=str(REMOTION_DIR), timeout=600)

        if result.returncode != 0:
            print(f"  ❌ Remotion render failed: {result.stderr[:500]}")
            return None

        print(f"  ✅ Overlay rendered: {overlay_path}")

        print(f"  🔧 Compositing overlay onto base video...")
        composite_cmd = _build_composite_command(base_video_path, overlay_path, output_path)
        result = subprocess.run(composite_cmd, capture_output=True, text=True, timeout=300)

        if result.returncode != 0:
            print(f"  ❌ FFmpeg composite failed: {result.stderr[:500]}")
            return None

        shutil.move(str(output_path), str(base_video_path))
        print(f"  ✅ Overlay composited successfully for {format_type}")
        return base_video_path

    except subprocess.TimeoutExpired:
        print(f"  ❌ Remotion render timed out for {format_type}")
        return None
    except Exception as e:
        print(f"  ❌ Remotion overlay failed: {e}")
        return None
    finally:
        props_path.unlink(missing_ok=True)
        # Clean up copied edu images from public/
        for f in public_dir.glob("edu_image_*"):
            f.unlink(missing_ok=True)
        if overlay_path.exists():
            overlay_path.unlink(missing_ok=True)


def main():
    """CLI entry point for pipeline integration."""
    import argparse

    parser = argparse.ArgumentParser(description="Render Remotion overlay onto video")
    parser.add_argument("--run-dir", type=str, required=True)
    parser.add_argument("--format", type=str, required=True,
                        choices=["full", "short_hook", "short_educational", "short_intro"])
    parser.add_argument("--video", type=str, required=True)
    parser.add_argument("--duration-ms", type=int, required=True)

    args = parser.parse_args()

    config_path = Path("config/config.json")
    with open(config_path) as f:
        config = json.load(f)

    result = render_overlay(
        run_dir=Path(args.run_dir),
        config=config,
        format_type=args.format,
        base_video_path=Path(args.video),
        duration_ms=args.duration_ms,
    )
    sys.exit(0 if result else 1)


if __name__ == "__main__":
    main()
