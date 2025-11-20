#!/usr/bin/env python3
"""
Autonomous topic generator using Claude Code CLI.
Generates educational science topics and writes to input/idea.txt.
"""

import json
import subprocess
import sys
from pathlib import Path
from datetime import datetime, timedelta


def load_config():
    """Load automation configuration."""
    config_path = Path("automation/config/automation_config.json")
    with open(config_path) as f:
        return json.load(f)


def load_topic_history():
    """Load topic history to avoid repeats."""
    history_path = Path("automation/state/topic_history.json")
    with open(history_path) as f:
        return json.load(f)


def save_topic_history(history):
    """Save updated topic history."""
    history_path = Path("automation/state/topic_history.json")
    with open(history_path, 'w') as f:
        json.dump(history, f, indent=2)


def get_recent_topics(history, days=30):
    """Get topics from last N days."""
    cutoff = datetime.now() - timedelta(days=days)
    recent = [
        entry["topic"]
        for entry in history["topics"]
        if datetime.fromisoformat(entry["date"]) > cutoff
    ]
    return recent


def generate_topic_via_claude(config, recent_topics):
    """Generate topic using Claude Code CLI."""
    categories = ", ".join(config["topic_generation"]["categories"])

    prompt = f"""Generate ONE educational science topic for a short-form video (60 seconds).

REQUIREMENTS:
- Must be from these categories: {categories}
- K-12 appropriate (ages 10-18)
- Visually interesting (can find stock footage/animations)
- NOT these recent topics: {', '.join(recent_topics[-10:])}

OUTPUT FORMAT (exactly this structure):
Topic: [specific concept]
Tone: [descriptive tone for music/pacing]

EXAMPLE:
Topic: Explain how DNA replication works in cells
Tone: energetic and fast-paced with moments of wonder

Generate now:"""

    result = subprocess.run(
        ["claude", "-p", prompt, "--dangerously-skip-permissions"],
        capture_output=True,
        text=True,
        timeout=30
    )

    if result.returncode != 0:
        raise Exception(f"Claude CLI failed: {result.stderr}")

    return result.stdout.strip()


def parse_topic_output(output):
    """Parse Claude's output into topic and tone."""
    lines = [line.strip() for line in output.split('\n') if line.strip()]

    topic = None
    tone = None

    for line in lines:
        # Match lines that start with Topic: or **Topic:** (markdown bold)
        if line.lower().startswith("topic:") or line.lower().startswith("**topic:"):
            # Remove markdown formatting and prefix
            cleaned = line.replace("**Topic:**", "").replace("Topic:", "").replace("**", "").strip()
            topic = cleaned
        elif line.lower().startswith("tone:") or line.lower().startswith("**tone:"):
            # Remove markdown formatting and prefix
            cleaned = line.replace("**Tone:**", "").replace("Tone:", "").replace("**", "").strip()
            tone = cleaned

    if not topic or not tone:
        raise ValueError(f"Could not parse topic/tone from output: {output}")

    return topic, tone


def write_idea_file(topic, tone):
    """Write topic to input/idea.txt."""
    idea_path = Path("input/idea.txt")
    with open(idea_path, 'w') as f:
        f.write(f"{topic}. Tone: {tone}\n")


def main():
    """Main execution."""
    print("🎯 Generating educational science topic...")

    # Load config and history
    config = load_config()
    history = load_topic_history()

    # Get recent topics to avoid repeats
    avoid_days = config["topic_generation"]["avoid_repeat_days"]
    recent_topics = get_recent_topics(history, days=avoid_days)

    # Generate topic via Claude
    output = generate_topic_via_claude(config, recent_topics)
    topic, tone = parse_topic_output(output)

    print(f"  Topic: {topic}")
    print(f"  Tone: {tone}")

    # Write to idea.txt
    write_idea_file(topic, tone)

    # Update history
    history["topics"].append({
        "date": datetime.now().isoformat(),
        "topic": topic,
        "tone": tone
    })
    save_topic_history(history)

    print(f"✅ Topic written to input/idea.txt")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        sys.exit(1)
