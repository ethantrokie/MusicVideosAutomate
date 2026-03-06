#!/Users/ethantrokie/SoftwareDevProjects/MusicVideosAutomate/venv/bin/python3
"""
Title optimizer agent.
Generates curiosity-gap title variants for educational videos using Claude,
then selects the best one based on curiosity factor, length, and originality.
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Tuple


CLAUDE_CLI = "/Users/ethantrokie/.local/bin/claude"

OPTIMAL_MIN_LENGTH = 50
OPTIMAL_MAX_LENGTH = 70

GENERIC_PATTERNS = (
    "how x works explained",
    "explained simply",
    "a complete guide",
    "everything you need to know",
    "the ultimate guide",
    "what you need to know",
    "for beginners",
)


def load_topic_from_research(research_path: str) -> str:
    """Load the topic string from a research.json file.

    Args:
        research_path: Absolute or relative path to research.json.

    Returns:
        The topic string extracted from the file.

    Raises:
        SystemExit: If the file cannot be read or has no topic field.
    """
    path = Path(research_path)
    if not path.exists():
        print(f"Error: research file not found: {research_path}", file=sys.stderr)
        sys.exit(1)

    try:
        with open(path) as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        print(f"Error: failed to read research file: {exc}", file=sys.stderr)
        sys.exit(1)

    topic = data.get("topic") or data.get("video_title") or data.get("title")
    if not topic:
        print(
            "Error: research file has no 'topic', 'video_title', or 'title' field",
            file=sys.stderr,
        )
        sys.exit(1)

    return str(topic)


def generate_variants(topic: str) -> list:
    """Call Claude CLI to generate curiosity-gap title variants.

    Args:
        topic: The video topic string.

    Returns:
        A list of title variant strings (3-5 items).

    Raises:
        SystemExit: If the Claude CLI call fails.
    """
    prompt = f"""Generate exactly 5 curiosity-gap YouTube title variants for the following educational video topic.

TOPIC: {topic}

RULES:
1. Each title must create a "curiosity gap" - make the viewer NEED to click.
2. Ideal length is 50-70 characters. Never exceed 80 characters.
3. Avoid generic patterns like "How X Works Explained", "A Complete Guide", "Everything You Need to Know".
4. Use concrete, vivid language. Prefer specific numbers, surprising contrasts, or bold claims.
5. Do NOT use clickbait that misrepresents the content.

GOOD EXAMPLES:
- "How Laser Cutters Vaporize Metal" -> "This Beam of Light Cuts Through Steel Like Butter"
- "How Hash Tables Work" -> "The Data Structure That Makes Google Search Instant"
- "How Grain Elevators Work" -> "How We Store Enough Food to Feed 8 Billion People"

Output ONLY a JSON array of exactly 5 title strings, no explanation:
["title 1", "title 2", "title 3", "title 4", "title 5"]"""

    try:
        result = subprocess.run(
            [CLAUDE_CLI, "-p", prompt, "--model", "claude-sonnet-4-5", "--dangerously-skip-permissions"],
            capture_output=True,
            text=True,
            timeout=60,
        )
    except FileNotFoundError:
        print(f"Error: Claude CLI not found at {CLAUDE_CLI}", file=sys.stderr)
        sys.exit(1)
    except subprocess.TimeoutExpired:
        print("Error: Claude CLI timed out after 60 seconds", file=sys.stderr)
        sys.exit(1)

    if result.returncode != 0:
        print(f"Error: Claude CLI failed: {result.stderr}", file=sys.stderr)
        sys.exit(1)

    output = result.stdout.strip()

    # Extract JSON from markdown code blocks if present
    if "```json" in output:
        output = output.split("```json")[1].split("```")[0].strip()
    elif "```" in output:
        output = output.split("```")[1].split("```")[0].strip()

    try:
        variants = json.loads(output)
    except json.JSONDecodeError as exc:
        print(f"Error: failed to parse Claude output as JSON: {exc}", file=sys.stderr)
        print(f"Raw output: {output}", file=sys.stderr)
        sys.exit(1)

    if not isinstance(variants, list) or len(variants) == 0:
        print("Error: Claude returned empty or non-list output", file=sys.stderr)
        sys.exit(1)

    # Ensure all items are strings
    return [str(v) for v in variants]


def score_title(title: str) -> Tuple[float, str]:
    """Score a single title based on quality heuristics.

    Returns a tuple of (score, explanation) where score is 0.0 to 1.0.
    Uses immutable evaluation -- does not modify the input.
    """
    reasons = []
    score = 0.0

    title_len = len(title)

    # Length scoring (0-0.3)
    if OPTIMAL_MIN_LENGTH <= title_len <= OPTIMAL_MAX_LENGTH:
        score += 0.3
        reasons.append("optimal length")
    elif 40 <= title_len <= 80:
        score += 0.15
        reasons.append("acceptable length")
    else:
        reasons.append(f"poor length ({title_len} chars)")

    # Generic pattern penalty (0 or -0.3)
    title_lower = title.lower()
    is_generic = any(pattern in title_lower for pattern in GENERIC_PATTERNS)
    if is_generic:
        score -= 0.3
        reasons.append("uses generic pattern")
    else:
        score += 0.2
        reasons.append("avoids generic patterns")

    # Curiosity indicators (0-0.3)
    curiosity_signals = (
        any(char in title for char in "?!"),
        any(word in title_lower for word in ("secret", "hidden", "surprising", "unexpected")),
        any(word in title_lower for word in ("never", "always", "every", "nobody")),
        any(char.isdigit() for char in title),
        any(word in title_lower for word in ("why", "how", "what", "the")),
    )
    curiosity_count = sum(curiosity_signals)
    curiosity_score = min(curiosity_count * 0.1, 0.3)
    score += curiosity_score
    if curiosity_count > 0:
        reasons.append(f"{curiosity_count} curiosity signal(s)")

    # Vividness bonus (0-0.2): titles with concrete/sensory language
    vivid_words = (
        "cuts", "burns", "melts", "explodes", "crushes", "smashes",
        "invisible", "tiny", "massive", "billion", "million", "instant",
        "deadly", "fastest", "strongest", "impossible",
    )
    vivid_count = sum(1 for w in vivid_words if w in title_lower)
    vivid_score = min(vivid_count * 0.1, 0.2)
    score += vivid_score
    if vivid_count > 0:
        reasons.append(f"{vivid_count} vivid word(s)")

    return (max(0.0, min(1.0, score)), ", ".join(reasons))


def select_best(variants: list) -> Tuple[str, list]:
    """Score all variants and return the best one plus all scored results.

    Args:
        variants: List of title strings.

    Returns:
        Tuple of (best_title, scored_list) where scored_list contains
        dicts with title, score, and explanation.
    """
    scored = []
    for title in variants:
        title_score, explanation = score_title(title)
        scored = [*scored, {"title": title, "score": title_score, "explanation": explanation}]

    # Sort descending by score (immutable -- creates new list)
    ranked = sorted(scored, key=lambda item: item["score"], reverse=True)

    best_title = ranked[0]["title"] if ranked else ""
    return (best_title, ranked)


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Generate curiosity-gap title variants for educational videos"
    )
    parser.add_argument(
        "--topic",
        type=str,
        help="The video topic string",
    )
    parser.add_argument(
        "--research-file",
        type=str,
        help="Path to research.json to extract topic from",
    )
    parser.add_argument(
        "--variants",
        action="store_true",
        default=False,
        help="Print all scored variants instead of just the best title",
    )

    args = parser.parse_args()

    if not args.topic and not args.research_file:
        parser.error("Either --topic or --research-file is required")

    return args


def main():
    """Main entry point."""
    args = parse_args()

    # Resolve topic
    if args.topic:
        topic = args.topic
    else:
        topic = load_topic_from_research(args.research_file)

    # Generate variants via Claude
    variants = generate_variants(topic)

    # Score and select
    best_title, scored_list = select_best(variants)

    if args.variants:
        for item in scored_list:
            print(f"[{item['score']:.2f}] {item['title']}  ({item['explanation']})")
    else:
        print(best_title)


if __name__ == "__main__":
    main()
