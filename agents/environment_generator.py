#!/usr/bin/env python3
"""Environment prompt generation for AI video clips."""

import subprocess
from typing import Dict, List


def generate_environment_prompts(
    topic: str,
    key_facts: List[str],
    clips: List[Dict]
) -> List[str]:
    """
    Use Claude to generate environment prompts for each clip.

    Args:
        topic: Educational topic
        key_facts: Key facts about the topic
        clips: List of clip definitions with segment_type

    Returns:
        List of environment prompt strings
    """
    prompts = []

    for clip in clips:
        prompt = _build_claude_prompt(topic, key_facts, clip)

        try:
            result = subprocess.run(
                [
                    "/Users/ethantrokie/.local/bin/claude",
                    "-p", prompt,
                    "--model", "claude-sonnet-4-5",
                    "--dangerously-skip-permissions"
                ],
                capture_output=True,
                text=True,
                timeout=60
            )

            if result.returncode == 0 and result.stdout.strip():
                prompts.append(result.stdout.strip())
            else:
                prompts.append(generate_fallback_prompt(topic, clip["segment_type"]))

        except Exception as e:
            print(f"    ⚠️ Claude prompt failed: {e}")
            prompts.append(generate_fallback_prompt(topic, clip["segment_type"]))

    return prompts


def _build_claude_prompt(topic: str, key_facts: List[str], clip: Dict) -> str:
    """Build the Claude prompt for environment generation."""
    facts_str = ", ".join(key_facts[:5]) if key_facts else "general science concepts"

    return f"""You are generating an environment description for an AI video.

Topic: {topic}
Key Facts: {facts_str}
Clip: {clip['id']} of 3
Segment: {clip['segment_type']}

Generate a vivid, cinematic environment description for a music video scene.
A realistic human performer will be singing in this environment.

Requirements:
- Must relate to the educational topic above
- Cinematic and visually striking
- Appropriate for a person to be standing/performing in
- 2-3 sentences maximum
- Include lighting description
- Include specific visual elements related to the topic

Output ONLY the environment description, nothing else. No quotes, no prefix."""


def generate_fallback_prompt(topic: str, segment_type: str) -> str:
    """
    Generate fallback prompt when Claude is unavailable.

    Args:
        topic: Educational topic
        segment_type: intro, verse, or chorus

    Returns:
        Generic but topic-aware environment prompt
    """
    topic_lower = topic.lower()

    # Topic-based environment hints
    if any(w in topic_lower for w in ["ocean", "water", "sonar", "submarine", "marine"]):
        base = "Deep ocean research facility with blue-green ambient lighting"
    elif any(w in topic_lower for w in ["space", "star", "planet", "rocket", "astronaut"]):
        base = "Futuristic space station interior with starfield visible through windows"
    elif any(w in topic_lower for w in ["lab", "chemistry", "molecule", "dna", "cell", "biology"]):
        base = "High-tech laboratory with glowing equipment and holographic displays"
    elif any(w in topic_lower for w in ["engine", "machine", "bearing", "mechanical", "factory"]):
        base = "Modern industrial facility with polished metal surfaces and dramatic lighting"
    elif any(w in topic_lower for w in ["electric", "circuit", "computer", "digital"]):
        base = "Neon-lit tech studio with circuit patterns and digital screens"
    else:
        base = "Professional studio with dramatic lighting and scientific equipment"

    return f"{base}, cinematic atmosphere, modern and sleek environment"


def detect_voice_gender(suno_data: Dict) -> str:
    """
    Detect voice gender from Suno metadata.

    Args:
        suno_data: Suno output data with song tags

    Returns:
        "male" or "female"
    """
    tags = suno_data.get("song", {}).get("tags", "").lower()

    if "female" in tags or "woman" in tags:
        return "female"
    elif "male" in tags or "man" in tags:
        return "male"
    else:
        return "male"  # Default


def get_performer_image_url(gender: str) -> str:
    """
    Get a stock performer image URL for video generation.

    Args:
        gender: "male" or "female"

    Returns:
        URL to performer reference image
    """
    # Stock images for performer reference
    if gender == "female":
        return "https://images.pexels.com/photos/3771089/pexels-photo-3771089.jpeg"
    else:
        return "https://images.pexels.com/photos/2531728/pexels-photo-2531728.jpeg"
