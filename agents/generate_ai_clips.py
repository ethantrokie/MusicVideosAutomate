#!/usr/bin/env python3
"""
AI video clip generation agent.

Generates 3x 5-second clips with lip-synced singing using Kling Avatar v2 Pro.
Uses a single API call per clip (image + audio → lip-synced video).

Pipeline Stage: 4.5 (after Segment Analysis, before Media Curation)

Cost: ~$1.73 per video (3 clips x ~$0.575 each)
"""

import os
import sys
import json
import shutil
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Dict, List

# Add agents directory to path
sys.path.insert(0, str(Path(__file__).parent))
from output_helper import get_output_path, ensure_output_dir
from kling_api_client import KlingAPIClient
from audio_utils import slice_audio
from clip_placement import determine_clip_placements, extract_lyrics_for_clip
from environment_generator import (
    generate_environment_prompts,
    detect_voice_gender,
    get_performer_image_path
)

# Force unbuffered output
sys.stdout = os.fdopen(sys.stdout.fileno(), 'w', buffering=1)
sys.stderr = os.fdopen(sys.stderr.fileno(), 'w', buffering=1)


def extract_front_portrait(image_path: str, output_dir: str) -> str:
    """
    Extract the front-facing portrait from a multi-angle composite image.
    If the image is wider than it is tall (landscape), it's likely a multi-angle
    composite — crop the left third to get the front-facing view.

    Args:
        image_path: Path to the source image
        output_dir: Directory to save the cropped image

    Returns:
        Path to the cropped front-facing image, or original path if not a composite
    """
    try:
        # Find ffprobe/ffmpeg, checking Homebrew paths as fallback
        ffprobe = shutil.which("ffprobe") or "/opt/homebrew/bin/ffprobe"
        ffmpeg = shutil.which("ffmpeg") or "/opt/homebrew/bin/ffmpeg"

        # Get image dimensions using ffprobe
        result = subprocess.run(
            [ffprobe, "-v", "error", "-select_streams", "v:0",
             "-show_entries", "stream=width,height",
             "-of", "csv=p=0:s=x", image_path],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode != 0:
            return image_path

        width, height = [int(x) for x in result.stdout.strip().split("x")]

        # If image is roughly square or portrait, it's already a single face
        if width < height * 1.5:
            return image_path

        # Landscape composite detected — crop left third for front-facing view
        crop_width = width // 3
        cropped_path = str(Path(output_dir) / "performer_front.png")

        result = subprocess.run(
            [ffmpeg, "-y", "-i", image_path,
             "-vf", f"crop={crop_width}:{height}:0:0",
             cropped_path],
            capture_output=True, timeout=30
        )

        if result.returncode == 0 and Path(cropped_path).exists():
            print(f"  ✂️  Cropped front portrait from multi-angle composite ({width}x{height} → {crop_width}x{height})")
            return cropped_path

    except Exception as e:
        print(f"  ⚠️ Could not crop portrait, using original: {e}")

    return image_path


def load_config() -> Dict:
    """Load config from config.json."""
    config_path = Path("config/config.json")
    with open(config_path) as f:
        return json.load(f)


def load_suno_output() -> Dict:
    """Load Suno output with aligned words and audio URL."""
    suno_path = get_output_path("suno_output.json")
    with open(suno_path) as f:
        return json.load(f)


def load_research() -> Dict:
    """Load research data for topic context."""
    research_path = get_output_path("research.json")
    with open(research_path) as f:
        return json.load(f)


def main() -> int:
    """Main entry point for AI clip generation."""
    print("🎬 Stage 4.5: AI Video Clip Generation")
    print("=" * 50)

    # Load config
    config = load_config()
    ai_config = config.get("ai_clips", {})

    if not ai_config.get("enabled", False):
        print("  ⏭️  AI clips disabled in config, skipping")
        return 0

    fal_api_key = config.get("fal_api", {}).get("api_key")
    if not fal_api_key or fal_api_key == "YOUR_FAL_API_KEY":
        print("  ⚠️ FAL API key not configured, skipping AI clips")
        return 0

    # Load required data
    print("  📂 Loading pipeline data...")

    try:
        suno_data = load_suno_output()
        research = load_research()
    except FileNotFoundError as e:
        print(f"  ❌ Required file not found: {e}")
        return 1

    aligned_words = suno_data.get("alignedWords", [])
    topic = research.get("topic", "Educational topic")
    key_facts = research.get("key_facts", [])

    if not aligned_words:
        print("  ⚠️ No aligned words found, skipping AI clips")
        return 0

    # Determine clip placements
    print("  🎯 Determining clip placements...")
    clips = determine_clip_placements(aligned_words)

    for clip in clips:
        clip["lyrics"] = extract_lyrics_for_clip(
            aligned_words,
            clip["start_time"],
            clip["end_time"]
        )
        print(f"    Clip {clip['id']}: {clip['start_time']:.1f}s - {clip['end_time']:.1f}s ({clip['segment_type']})")

    # Generate environment prompts
    print("  🌍 Generating environment prompts...")
    environment_prompts = generate_environment_prompts(topic, key_facts, clips)

    for i, prompt in enumerate(environment_prompts):
        clips[i]["environment_prompt"] = prompt
        print(f"    Clip {i+1}: {prompt[:60]}...")

    # Detect voice gender
    gender = detect_voice_gender(suno_data)
    print(f"  🎤 Detected voice: {gender}")

    # Get performer reference image from config
    performer_image_path = get_performer_image_path(gender, config)
    print(f"  🖼️  Performer image: {performer_image_path[:60]}...")

    # Initialize Kling client and pre-check balance
    client = KlingAPIClient(fal_api_key)
    balance_check = client.check_balance()
    if not balance_check["ok"]:
        print(f"  ⚠️ fal.ai balance issue: {balance_check['message']}")
        print("  ⏭️  Skipping AI clips due to billing issue")
        return 0

    # Create output directories (needed early for portrait cropping)
    output_dir = os.getenv("OUTPUT_DIR", "outputs")
    ai_clips_dir = Path(output_dir) / "ai_clips"
    ai_clips_dir.mkdir(exist_ok=True)

    # Extract front-facing portrait from multi-angle composite if needed
    if not performer_image_path.startswith("http"):
        performer_image_path = extract_front_portrait(performer_image_path, str(ai_clips_dir))

    # Upload local performer image if it's not a URL
    if performer_image_path.startswith("http"):
        performer_image_url = performer_image_path
    else:
        print(f"  📤 Uploading local performer image...")
        performer_image_url = client.upload_file(performer_image_path)
        print(f"  ✅ Uploaded: {performer_image_url[:60]}...")

    audio_slices_dir = ai_clips_dir / "audio_slices"
    audio_slices_dir.mkdir(exist_ok=True)

    song_path = get_output_path("song.mp3")

    # Generate clips
    # Record which performer image is being used (for A/B test tracking)
    performer_variant = Path(performer_image_path).name if not performer_image_path.startswith("http") else performer_image_path

    manifest = {
        "generated_at": datetime.now().isoformat(),
        "topic": topic,
        "performer_gender": gender,
        "performer_variant": performer_variant,
        "total_cost_usd": 0,
        "clips": []
    }

    for clip in clips:
        # Skip remaining clips if balance was exhausted on a previous clip
        if client.balance_exhausted:
            print(f"\n  ⏭️  Skipping clip {clip['id']}/3 - fal.ai balance exhausted")
            manifest["clips"].append({
                "id": clip["id"],
                "file": f"clip_{clip['id']}.mp4",
                "start_time": clip["start_time"],
                "end_time": clip["end_time"],
                "segment_type": clip["segment_type"],
                "generation_status": "skipped_balance_exhausted",
                "cost_usd": 0
            })
            continue

        print(f"\n  🎬 Generating clip {clip['id']}/3...")

        clip_duration = 5

        clip_data = {
            "id": clip["id"],
            "file": f"clip_{clip['id']}.mp4",
            "start_time": clip["start_time"],
            "end_time": clip["end_time"],
            "segment_type": clip["segment_type"],
            "environment_prompt": clip["environment_prompt"],
            "lyrics_excerpt": clip["lyrics"][:100] + "..." if len(clip["lyrics"]) > 100 else clip["lyrics"],
            "generation_status": "pending",
            "cost_usd": 0
        }

        try:
            # Slice audio for this clip's time range
            audio_slice_path = str(audio_slices_dir / f"slice_{clip['id']}.mp3")

            if not slice_audio(str(song_path), clip["start_time"], clip_duration, audio_slice_path):
                print(f"    ⚠️ Audio slice failed, skipping clip")
                clip_data["generation_status"] = "audio_slice_failed"
                manifest["clips"].append(clip_data)
                continue

            # Upload audio slice
            print(f"    🎵 Uploading audio slice...")
            audio_url = client.upload_file(audio_slice_path)

            # Generate lip-synced video in a single step with Kling Avatar v2 Pro
            print(f"    🎥 Generating lip-synced video with Kling Avatar v2 Pro...")
            scene_prompt = f"A {gender} singer performing expressively. {clip['environment_prompt']}"

            result = client.generate_avatar_video(
                image_url=performer_image_url,
                audio_url=audio_url,
                prompt=scene_prompt
            )

            clip_data["generation_status"] = result.get("status", "success")
            clip_data["cost_usd"] = 0.575  # ~$0.115/sec * 5 sec

            # Download final video
            output_path = str(ai_clips_dir / f"clip_{clip['id']}.mp4")
            print(f"    💾 Downloading clip...")

            if client.download_video(result["video_url"], output_path):
                clip_data["generation_status"] = "success"
                print(f"    ✅ Clip {clip['id']} complete")
            else:
                clip_data["generation_status"] = "download_failed"
                print(f"    ❌ Clip {clip['id']} download failed")

        except Exception as e:
            print(f"    ❌ Clip {clip['id']} failed: {e}")
            clip_data["generation_status"] = "failed"
            clip_data["error"] = str(e)

        manifest["clips"].append(clip_data)
        manifest["total_cost_usd"] += clip_data["cost_usd"]

    # Save manifest
    manifest_path = ai_clips_dir / "ai_clip_manifest.json"
    with open(manifest_path, 'w') as f:
        json.dump(manifest, f, indent=2)

    # Summary
    successful = sum(1 for c in manifest["clips"] if c["generation_status"] == "success")
    print(f"\n{'=' * 50}")
    print(f"✅ AI Clip Generation Complete")
    print(f"   Successful: {successful}/3 clips")
    print(f"   Total cost: ${manifest['total_cost_usd']:.2f}")
    print(f"   Manifest: {manifest_path}")

    return 0 if successful > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
