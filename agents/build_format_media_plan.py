#!/usr/bin/env python3
"""
Build format-specific media plans for multi-format video generation.
Creates separate media plans optimized for each format's duration and aspect ratio.
"""

import os
import sys
import json
import subprocess
from pathlib import Path
from typing import Dict, Literal

FormatType = Literal["full", "hook", "educational"]


def get_output_path(filename: str) -> Path:
    """Get path in OUTPUT_DIR."""
    output_dir = os.getenv("OUTPUT_DIR", "outputs")
    return Path(output_dir) / filename


def get_format_config(format_type: FormatType, segments: Dict) -> Dict:
    """Get duration and configuration for each format."""
    configs = {
        "full": {
            "duration": segments["full"]["duration"],
            "output_file": "media_plan_full.json",
            "description": "Full horizontal video"
        },
        "hook": {
            "duration": segments["hook"]["duration"],
            "output_file": "media_plan_hook.json",
            "description": "Hook short vertical video"
        },
        "educational": {
            "duration": segments["educational"]["duration"],
            "output_file": "media_plan_educational.json",
            "description": "Educational short vertical video"
        }
    }
    return configs[format_type]


def build_media_plan(format_type: FormatType, duration: int, output_file: str) -> bool:
    """
    Call curator to build media plan for specific format.

    Args:
        format_type: Type of video format
        duration: Target duration in seconds
        output_file: Output filename for media plan

    Returns:
        True if successful, False otherwise
    """
    print(f"  Building {format_type} media plan ({duration}s)...")

    # Set output path for this format's media plan
    output_dir = os.getenv("OUTPUT_DIR", "outputs")
    format_output = os.path.join(output_dir, output_file)

    # Temporarily override OUTPUT_PATH in curator
    original_output = get_output_path("media_plan.json")

    try:
        # Call curator with format-specific duration
        env = os.environ.copy()
        env["DURATION"] = str(duration)
        env["OUTPUT_DIR"] = output_dir

        # Run curator, capturing output to avoid cluttering logs
        result = subprocess.run(
            ["./agents/4_curate_media.sh"],
            env=env,
            capture_output=True,
            text=True,
            timeout=600  # 10 minutes - max allowed, needed for 180s full video curation
        )

        if result.returncode != 0:
            print(f"    ❌ Curator failed for {format_type}")
            print(f"    Error: {result.stderr}")
            return False

        # Rename media_plan.json to format-specific file
        if original_output.exists():
            original_output.rename(format_output)

            # Enrich format-specific plan with local_path fields from approved_media.json
            approved_media_path = get_output_path("approved_media.json")
            if approved_media_path.exists():
                with open(approved_media_path) as f:
                    approved_data = json.load(f)

                # Build lookup from media_url to local_path
                url_to_path = {}
                for shot in approved_data.get("shot_list", []):
                    if "media_url" in shot and "local_path" in shot:
                        url_to_path[shot["media_url"]] = shot["local_path"]

                # Add local_path to format-specific plan
                with open(format_output) as f:
                    format_data = json.load(f)

                for shot in format_data.get("shot_list", []):
                    if "media_url" in shot and shot["media_url"] in url_to_path:
                        shot["local_path"] = url_to_path[shot["media_url"]]

                # Save enriched plan
                with open(format_output, 'w') as f:
                    json.dump(format_data, f, indent=2)

            print(f"    ✅ Created {output_file}")
            return True
        else:
            print(f"    ❌ Curator didn't create media_plan.json")
            return False

    except subprocess.TimeoutExpired:
        print(f"    ❌ Curator timed out for {format_type}")
        return False
    except Exception as e:
        print(f"    ❌ Error building {format_type} plan: {e}")
        return False


def main():
    """Build format-specific media plans based on segments.json."""
    print("🎨 Building format-specific media plans...")

    # Load segments to get durations
    segments_path = get_output_path("segments.json")
    if not segments_path.exists():
        print(f"❌ Error: {segments_path} not found")
        print("Segment analysis must run before media planning")
        sys.exit(1)

    with open(segments_path) as f:
        segments = json.load(f)

    # Build media plan for each format
    formats: list[FormatType] = ["full", "hook", "educational"]
    success_count = 0

    for format_type in formats:
        config = get_format_config(format_type, segments)
        success = build_media_plan(
            format_type,
            config["duration"],
            config["output_file"]
        )
        if success:
            success_count += 1

    # Summary
    print(f"\n✅ Built {success_count}/{len(formats)} format-specific media plans")

    if success_count < len(formats):
        print("⚠️  Some media plans failed - videos may have incorrect durations")
        sys.exit(1)


if __name__ == "__main__":
    main()
