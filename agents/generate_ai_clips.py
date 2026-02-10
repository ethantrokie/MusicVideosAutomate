#!/usr/bin/env python3
"""
AI video clip generation agent.

Generates 3x 8-second clips with lip-synced singing in topic-matched environments.

Pipeline Stage: 4.5 (after Segment Analysis, before Media Curation)

Cost: ~$2.10 per video (3 clips x $0.70 each)
"""

import os
import sys
import json
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
    get_performer_image_url
)

# Force unbuffered output
sys.stdout = os.fdopen(sys.stdout.fileno(), 'w', buffering=1)
sys.stderr = os.fdopen(sys.stderr.fileno(), 'w', buffering=1)


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

    # Get performer reference image
    performer_image = get_performer_image_url(gender)

    # Initialize Kling client
    client = KlingAPIClient(fal_api_key)

    # Create output directories
    output_dir = os.getenv("OUTPUT_DIR", "outputs")
    ai_clips_dir = Path(output_dir) / "ai_clips"
    ai_clips_dir.mkdir(exist_ok=True)

    audio_slices_dir = ai_clips_dir / "audio_slices"
    audio_slices_dir.mkdir(exist_ok=True)

    song_path = get_output_path("song.mp3")

    # Generate clips
    manifest = {
        "generated_at": datetime.now().isoformat(),
        "topic": topic,
        "performer_gender": gender,
        "total_cost_usd": 0,
        "clips": []
    }

    for clip in clips:
        print(f"\n  🎬 Generating clip {clip['id']}/3...")

        clip_data = {
            "id": clip["id"],
            "file": f"clip_{clip['id']}.mp4",
            "start_time": clip["start_time"],
            "end_time": clip["end_time"],
            "segment_type": clip["segment_type"],
            "environment_prompt": clip["environment_prompt"],
            "lyrics_excerpt": clip["lyrics"][:100] + "..." if len(clip["lyrics"]) > 100 else clip["lyrics"],
            "generation_status": "pending",
            "lipsync_status": "pending",
            "cost_usd": 0
        }

        try:
            # Generate base video
            print(f"    🎥 Generating video...")
            full_prompt = f"A {gender} performer singing with emotion and energy. {clip['environment_prompt']}"

            # Use 5s duration (Kling supports 5 or 10 seconds)
            clip_duration = 5

            video_result = client.generate_video(
                image_url=performer_image,
                prompt=full_prompt,
                duration=clip_duration,
                aspect_ratio="16:9"
            )

            clip_data["generation_status"] = video_result.get("status", "success")
            clip_data["cost_usd"] += 0.70  # ~$0.14/sec * 5 sec for video generation

            # Slice audio for lip-sync
            audio_slice_path = str(audio_slices_dir / f"slice_{clip['id']}.mp3")

            if slice_audio(str(song_path), clip["start_time"], clip_duration, audio_slice_path):
                print(f"    🎵 Applying lip-sync...")

                # Upload audio slice
                audio_url = client.upload_file(audio_slice_path)

                # Apply lip-sync
                lipsync_result = client.apply_lipsync(
                    video_url=video_result["video_url"],
                    audio_url=audio_url
                )

                clip_data["lipsync_status"] = lipsync_result.get("status", "success")
                clip_data["cost_usd"] += 0.20  # ~$0.04/sec * 5 sec for lipsync

                final_video_url = lipsync_result["video_url"]
            else:
                print(f"    ⚠️ Audio slice failed, using video without lip-sync")
                clip_data["lipsync_status"] = "audio_slice_failed"
                final_video_url = video_result["video_url"]

            # Download final video
            output_path = str(ai_clips_dir / f"clip_{clip['id']}.mp4")
            print(f"    💾 Downloading clip...")

            if client.download_video(final_video_url, output_path):
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
