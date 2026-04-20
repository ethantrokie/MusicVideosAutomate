#!/usr/bin/env python3
"""
Educational image generation agent.

Generates 5-10 AI concept illustrations per video using fal.ai Reve Image.
Images use a dark whiteboard sketch style (hand-drawn chalk on charcoal)
and are placed during verse sections to visually explain key concepts.

Pipeline Stage: 4.6 (after AI Avatar Clips, before Media Curation)

Cost: ~$0.05-0.10 per video (5-10 images x $0.01 each)
"""

import os
import sys
import json
import subprocess
import requests
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional

# Add agents directory to path
sys.path.insert(0, str(Path(__file__).parent))
from output_helper import get_output_path, ensure_output_dir

COST_PER_IMAGE = 0.01  # Reve Image via fal.ai


def load_config() -> Dict:
    """Load config from config.json."""
    config_path = Path("config/config.json")
    with open(config_path) as f:
        return json.load(f)


def is_educational_images_enabled(config: Dict) -> bool:
    """Check if educational images are enabled in config and A/B experiment."""
    edu_config = config.get("educational_images", {})
    if not edu_config.get("enabled", False):
        return False

    # Check A/B experiment state
    variant = _get_experiment_variant()
    if variant is not None:
        return variant == "true"

    return True


def _get_experiment_variant() -> Optional[str]:
    """
    Check A/B experiment state for educational_images_enabled.
    Uses the same date-based pattern as _get_active_performer_variant().

    Returns:
        "true" or "false" if experiment is active, None if no experiment.
    """
    experiments_path = Path("automation/state/ab_experiments.json")
    if not experiments_path.exists():
        return None

    try:
        with open(experiments_path) as f:
            data = json.load(f)
    except (json.JSONDecodeError, IOError):
        return None

    for exp in data.get("experiments", []):
        if exp.get("status") != "active":
            continue
        if exp.get("config_key") != "educational_images_enabled":
            continue

        created = datetime.fromisoformat(exp["created_at"])
        elapsed_days = (datetime.now() - created).days
        current_week = max(1, (elapsed_days // 7) + 1)

        if current_week > exp.get("duration_weeks", 8):
            continue

        # Odd weeks = control, even weeks = treatment (adjusted by phase_offset)
        phase_offset = exp.get("phase_offset", 0)
        if (current_week + phase_offset) % 2 == 1:
            return exp.get("control_value", "false")
        return exp.get("treatment_value", "true")

    return None


def select_concepts_and_prompts(
    topic: str,
    key_facts: List[str],
    phrase_groups: List[Dict],
    count: int,
    style: str
) -> List[Dict]:
    """
    Use Claude to select key concepts and generate image prompts.

    Args:
        topic: Educational topic
        key_facts: Key facts from research
        phrase_groups: Phrase groups with timing data
        count: Target number of images
        style: Visual style description

    Returns:
        List of dicts with key_fact, matched_phrase_group, prompt, start_time, end_time
    """
    facts_json = json.dumps(key_facts, indent=2)
    groups_summary = json.dumps([
        {
            "index": i,
            "start_time": g.get("startS", g.get("start_time", 0)),
            "end_time": g.get("endS", g.get("end_time", 0)),
            "text": g.get("text", g.get("topic", ""))[:100]
        }
        for i, g in enumerate(phrase_groups)
    ], indent=2)

    prompt = f"""You are selecting key concepts for educational illustration images in a music video.

Topic: {topic}
Target count: {count} images

Key facts from research:
{facts_json}

Phrase groups (lyrics with timestamps):
{groups_summary}

Select {count} key concepts from the facts above. For each:
1. Pick the fact that would benefit most from visual illustration
2. Match it to the phrase group whose lyrics best relate to that concept
3. Generate an image prompt in this exact style: {style}
4. Each image should show for 2-3 seconds (vary duration naturally)

CRITICAL CONSTRAINTS:
- Place images during VERSE sections, NOT during chorus (high-energy sections need motion video)
- Minimum 3 seconds gap between educational images (avoid slideshow feel)
- Distribute images evenly across the timeline
- Keep labels in the UPPER 60% of the frame (subtitles appear at bottom)
- Use minimal text labels (1-3 labels max per image)
- 9:16 vertical aspect ratio (portrait orientation)

Output ONLY valid JSON array, no markdown, no explanation:
[
  {{
    "key_fact": "the original fact text",
    "matched_phrase_group": 0,
    "start_time": 5.2,
    "end_time": 7.7,
    "duration": 2.5,
    "prompt": "Dark charcoal background, hand-drawn white chalk sketch of [concept]. Minimal cream-colored labels in upper portion. Educational diagram style, 9:16 vertical portrait orientation."
  }}
]"""

    try:
        result = subprocess.run(
            [
                "/Users/ethantrokie/.local/bin/claude",
                "-p", prompt,
                "--model", "claude-sonnet-4-6",
                "--dangerously-skip-permissions"
            ],
            capture_output=True,
            text=True,
            timeout=90
        )

        if result.returncode == 0 and result.stdout.strip():
            output = result.stdout.strip()
            # Strip markdown code fences if present
            if output.startswith("```"):
                lines = output.split("\n")
                output = "\n".join(lines[1:-1]) if lines[-1].strip() == "```" else "\n".join(lines[1:])
            return json.loads(output)

    except Exception as e:
        print(f"    Claude concept selection failed: {e}")

    # Fallback: generate simple prompts from facts directly
    return _generate_fallback_concepts(key_facts, phrase_groups, count, style)


def _generate_fallback_concepts(
    key_facts: List[str],
    phrase_groups: List[Dict],
    count: int,
    style: str
) -> List[Dict]:
    """Generate fallback concepts when Claude is unavailable."""
    concepts = []
    facts_to_use = key_facts[:count]

    # Distribute evenly across phrase groups
    if not phrase_groups:
        return []

    step = max(1, len(phrase_groups) // max(1, len(facts_to_use)))

    for i, fact in enumerate(facts_to_use):
        group_idx = min(i * step, len(phrase_groups) - 1)
        group = phrase_groups[group_idx]

        start = group.get("startS", group.get("start_time", i * 5))
        end = group.get("endS", group.get("end_time", start + 2.5))
        duration = min(3.0, max(2.0, end - start))

        concepts.append({
            "key_fact": fact,
            "matched_phrase_group": group_idx,
            "start_time": start,
            "end_time": start + duration,
            "duration": duration,
            "prompt": f"{style}, illustrating: {fact[:80]}. 9:16 vertical portrait orientation."
        })

    return concepts


def enforce_placement_constraints(
    concepts: List[Dict],
    min_gap: float = 3.0
) -> List[Dict]:
    """
    Enforce placement constraints on educational images.

    Args:
        concepts: List of concept dicts with start_time/end_time
        min_gap: Minimum seconds between consecutive images

    Returns:
        Filtered list respecting constraints
    """
    if not concepts:
        return []

    # Sort by start time
    sorted_concepts = sorted(concepts, key=lambda c: c["start_time"])

    filtered = [sorted_concepts[0]]
    for concept in sorted_concepts[1:]:
        prev_end = filtered[-1]["end_time"]
        if concept["start_time"] - prev_end >= min_gap:
            filtered.append(concept)
        else:
            print(f"    Skipping image at {concept['start_time']:.1f}s (too close to previous at {prev_end:.1f}s)")

    return filtered


def generate_image(prompt: str, model: str) -> Optional[Dict]:
    """
    Generate a single image using fal.ai.

    Args:
        prompt: Image generation prompt
        model: fal.ai model identifier

    Returns:
        Dict with image_url on success, None on failure
    """
    import fal_client

    try:
        result = fal_client.subscribe(
            model,
            arguments={
                "prompt": prompt,
                "image_size": {
                    "width": 768,
                    "height": 1344  # 9:16 aspect ratio
                },
                "num_images": 1,
                "enable_safety_checker": False
            }
        )

        images = result.get("images", [])
        if images:
            return {"image_url": images[0].get("url")}

    except Exception as e:
        print(f"    Image generation failed: {e}")

    return None


def download_image(url: str, output_path: str) -> bool:
    """Download image from URL to local path."""
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        with open(output_path, 'wb') as f:
            f.write(response.content)
        return True
    except Exception as e:
        print(f"    Download failed: {e}")
        return False


def main() -> int:
    """Main entry point for educational image generation."""
    # Force unbuffered output when running as script
    sys.stdout = os.fdopen(sys.stdout.fileno(), 'w', buffering=1)
    sys.stderr = os.fdopen(sys.stderr.fileno(), 'w', buffering=1)

    print("Stage 4.6: Educational Image Generation")
    print("=" * 50)

    # Load config
    config = load_config()
    edu_config = config.get("educational_images", {})

    if not is_educational_images_enabled(config):
        print("  Educational images disabled (config or A/B experiment), skipping")
        return 0

    fal_api_key = config.get("fal_api", {}).get("api_key")
    if not fal_api_key or fal_api_key == "YOUR_FAL_API_KEY":
        print("  FAL API key not configured, skipping educational images")
        return 0

    os.environ["FAL_KEY"] = fal_api_key

    # Load required data
    print("  Loading pipeline data...")
    try:
        with open(get_output_path("research.json")) as f:
            research = json.load(f)
        with open(get_output_path("phrase_groups.json")) as f:
            phrase_groups = json.load(f)
    except FileNotFoundError as e:
        print(f"  Required file not found: {e}")
        return 1

    topic = research.get("topic", "Educational topic")
    key_facts = research.get("key_facts", [])

    if not key_facts:
        print("  No key facts found in research, skipping")
        return 0
    if not phrase_groups:
        print("  No phrase groups found, skipping")
        return 0

    # Configuration
    target_count = edu_config.get("count", 8)
    min_count = edu_config.get("min_count", 5)
    max_count = edu_config.get("max_count", 10)
    model = edu_config.get("model", "fal-ai/reve/text-to-image")
    style = edu_config.get(
        "style",
        "hand-drawn whiteboard sketch, dark charcoal background, "
        "white chalk-like lines, educational diagram, minimal labels in upper portion"
    )

    target_count = max(min_count, min(target_count, max_count, len(key_facts)))
    print(f"  Target: {target_count} educational images")
    print(f"  Model: {model}")

    # Select concepts and generate prompts
    print("  Selecting key concepts and generating prompts...")
    concepts = select_concepts_and_prompts(
        topic, key_facts, phrase_groups, target_count, style
    )

    if not concepts:
        print("  No concepts generated, skipping")
        return 0

    # Enforce placement constraints
    concepts = enforce_placement_constraints(concepts, min_gap=3.0)
    print(f"  {len(concepts)} images after placement constraints")

    if len(concepts) < min_count:
        print(f"  Only {len(concepts)} images pass constraints (min: {min_count}), proceeding anyway")

    # Create output directory
    output_dir = os.getenv("OUTPUT_DIR", "outputs")
    images_dir = Path(output_dir) / "educational_images"
    images_dir.mkdir(exist_ok=True)

    # Determine experiment variant for manifest
    variant = _get_experiment_variant()

    # Generate images
    manifest = {
        "generated_at": datetime.now().isoformat(),
        "topic": topic,
        "experiment_variant": variant,
        "total_cost_usd": 0,
        "images": []
    }

    for i, concept in enumerate(concepts, 1):
        print(f"\n  [{i}/{len(concepts)}] Generating image for: {concept['key_fact'][:60]}...")

        image_data = {
            "id": i,
            "file": f"edu_image_{i}.png",
            "start_time": concept["start_time"],
            "end_time": concept["end_time"],
            "duration": concept.get("duration", concept["end_time"] - concept["start_time"]),
            "key_fact": concept["key_fact"],
            "matched_phrase_group": concept.get("matched_phrase_group"),
            "prompt": concept["prompt"],
            "generation_status": "pending",
            "cost_usd": 0
        }

        result = generate_image(concept["prompt"], model)

        if result and result.get("image_url"):
            output_path = str(images_dir / f"edu_image_{i}.png")
            if download_image(result["image_url"], output_path):
                image_data["generation_status"] = "success"
                image_data["cost_usd"] = COST_PER_IMAGE
                print(f"    Image {i} saved")
            else:
                image_data["generation_status"] = "download_failed"
                print(f"    Image {i} download failed")
        else:
            image_data["generation_status"] = "generation_failed"
            print(f"    Image {i} generation failed")

        manifest["images"].append(image_data)
        manifest["total_cost_usd"] += image_data["cost_usd"]

    # Save manifest
    manifest_path = images_dir / "edu_image_manifest.json"
    with open(manifest_path, 'w') as f:
        json.dump(manifest, f, indent=2)

    # Summary
    successful = sum(1 for img in manifest["images"] if img["generation_status"] == "success")
    print(f"\n{'=' * 50}")
    print(f"Educational Image Generation Complete")
    print(f"   Successful: {successful}/{len(concepts)} images")
    print(f"   Total cost: ${manifest['total_cost_usd']:.2f}")
    print(f"   Manifest: {manifest_path}")

    if successful == 0 and edu_config.get("fallback_to_stock", True):
        print("   No images generated, pipeline will use stock footage only")

    return 0 if successful > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
