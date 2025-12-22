#!/Users/ethantrokie/SoftwareDevProjects/MusicVideosAutomate/venv/bin/python3
"""
Autonomous topic generator using Claude Code CLI.
Generates educational science topics and writes to input/idea.txt.
Incorporates Google Trends data for relevance.
"""

import json
import subprocess
import sys
import re
from pathlib import Path
from datetime import datetime, timedelta
from collections import Counter

from trends_fetcher import get_trending_science_topics, format_trends_for_prompt


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
    """Get topics from last N days, with fallback to last N entries."""
    cutoff = datetime.now() - timedelta(days=days)
    recent = []

    # Try date-based filtering first
    for entry in history["topics"]:
        try:
            if entry.get("date") and datetime.fromisoformat(entry["date"]) > cutoff:
                recent.append(entry["topic"])
        except (ValueError, TypeError):
            # Skip entries with invalid dates
            continue

    # Fallback: if no valid dates found, use last N entries
    if not recent and history["topics"]:
        # Use last 20 topics as fallback
        recent = [entry["topic"] for entry in history["topics"][-20:]]

    return recent


def extract_keywords(topic):
    """Extract key scientific terms from a topic for similarity checking."""
    # Lowercase and remove punctuation
    cleaned = re.sub(r'[^\w\s]', ' ', topic.lower())

    # Split into words
    words = cleaned.split()

    # Common stop words to remove
    stop_words = {
        'how', 'why', 'what', 'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at',
        'to', 'for', 'of', 'with', 'by', 'from', 'as', 'is', 'are', 'was', 'were',
        'been', 'be', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would',
        'could', 'should', 'can', 'their', 'them', 'they', 'through', 'into', 'using',
        'called', 'when', 'where', 'which', 'that', 'this', 'these', 'those', 'it',
        'its', 'allows', 'enabling', 'enable', 'proves', 'prove', 'showing', 'show',
        'creates', 'create', 'makes', 'make', 'across', 'within', 'without', 'up',
        'down', 'out', 'over', 'under', 'all', 'any', 'both', 'each', 'few', 'more',
        'most', 'other', 'some', 'such'
    }

    # Filter out stop words and very short words
    keywords = [w for w in words if w not in stop_words and len(w) > 3]

    return set(keywords)


def calculate_topic_similarity(topic1, topic2):
    """Calculate similarity between two topics based on shared keywords."""
    keywords1 = extract_keywords(topic1)
    keywords2 = extract_keywords(topic2)

    if not keywords1 or not keywords2:
        return 0.0

    # Calculate Jaccard similarity (intersection over union)
    intersection = len(keywords1 & keywords2)
    union = len(keywords1 | keywords2)

    return intersection / union if union > 0 else 0.0


def check_topic_similarity(new_topic, recent_topics, threshold=0.3):
    """
    Check if a new topic is too similar to recent topics.
    Returns (is_similar, similar_topic, similarity_score)
    """
    for recent in recent_topics:
        similarity = calculate_topic_similarity(new_topic, recent)
        if similarity >= threshold:
            return True, recent, similarity

    return False, None, 0.0


def analyze_category_distribution(history, recent_count=20):
    """
    Analyze category distribution in recent topics.
    Returns dict with category counts and over-represented categories.
    """
    # Get recent entries with full data
    recent_entries = history["topics"][-recent_count:] if history["topics"] else []

    # Extract keywords that might indicate categories
    category_keywords = {
        'quantum': ['quantum', 'entanglement', 'tunneling', 'photoelectric', 'superconductivity', 'superconductor'],
        'biology': ['cells', 'organisms', 'photosynthesis', 'proteins', 'dna', 'bacteria', 'biology', 'alleles', 'genes', 'trait'],
        'physics': ['light', 'waves', 'energy', 'motion', 'force', 'pressure', 'momentum', 'doppler', 'polarized', 'refraction'],
        'chemistry': ['molecules', 'chemical', 'reactions', 'atoms', 'elements', 'catalytic', 'compounds', 'oxidation'],
        'engineering': [
            # Civil/Structural
            'bridge', 'suspension', 'arch', 'beam', 'truss', 'foundation', 'skyscraper', 'dam', 'tunnel',
            # Mechanical/Automotive
            'engine', 'turbine', 'piston', 'gear', 'transmission', 'brake', 'hydraulic', 'pneumatic',
            'regenerative', 'flywheel', 'crankshaft', 'suspension',
            # Aerospace
            'airplane', 'aircraft', 'wing', 'airfoil', 'jet', 'rocket', 'propulsion', 'aerodynamic',
            # Electrical
            'circuit', 'motor', 'generator', 'transformer', 'capacitor', 'battery', 'solar', 'wind turbine',
            # General Engineering
            'mechanical', 'designed', 'built', 'constructed', 'engineered', 'system works'
        ],
        'manufacturing': [
            # Production
            'manufactured', 'factory', 'assembly', 'production', 'fabricated', 'molded', 'forged',
            'stamped', 'extruded', 'machined', 'cast', 'welded',
            # Specific products
            'how steel', 'how glass', 'how plastic', 'how rubber', 'how paper', 'how aluminum',
            'how semiconductors', 'how chips', 'how processors', 'how screens', 'how lenses',
            # Processes
            'injection molding', 'die casting', '3d printing', 'additive', 'cnc', 'laser cutting',
            'assembly line', 'mass production', 'quality control',
            # How it's made style
            'made from', 'production process', 'manufacturing process', 'created by', 'built in factories'
        ],
        'earth_science': ['ocean', 'hurricane', 'rocks', 'tectonic', 'geological', 'metamorphic', 'volcano', 'earthquake']
    }

    category_counts = Counter()

    for entry in recent_entries:
        topic = entry.get("topic", "").lower()

        # Check which category this topic belongs to
        for category, keywords in category_keywords.items():
            if any(keyword in topic for keyword in keywords):
                category_counts[category] += 1
                break  # Only count once per topic

    # Calculate percentages
    total = len(recent_entries)
    category_percentages = {cat: (count / total * 100) for cat, count in category_counts.items()}

    # Identify over-represented categories (>25% of recent topics)
    over_represented = [cat for cat, pct in category_percentages.items() if pct > 25]

    return {
        'counts': dict(category_counts),
        'percentages': category_percentages,
        'over_represented': over_represented,
        'total': total
    }


def generate_topic_via_claude(config, recent_topics, trends_text="", category_guidance=""):
    """Generate topic using Claude Code CLI."""
    categories = ", ".join(config["topic_generation"]["categories"])

    # Build trends section if available
    trends_section = ""
    if trends_text:
        trends_section = f"""
{trends_text}

IMPORTANT: Prefer topics that relate to or are inspired by the trending searches above.
This helps ensure the video is relevant to what people are currently searching for.

"""

    # Build category guidance section if available
    category_section = ""
    if category_guidance:
        category_section = f"""
{category_guidance}

"""

    prompt = f"""SYSTEM CONTEXT: This is an automated pipeline. Do NOT use brainstorming skills. Do NOT ask clarifying questions. Just generate the output directly.

You are a topic generator for educational science videos. Generate ONE topic ONLY.
{trends_section}{category_section}
REQUIREMENTS:
- Category: One of {categories}
- K-12 appropriate (ages 10-18)
- Visually interesting (stock footage available)
- Specific educational science concept (no broad topics) focused on everyday phenomena
- Avoid these recent topics: {', '.join(recent_topics[-10:]) if recent_topics else 'none yet'}

TOPIC VARIETY - Balance engineering/manufacturing with pure science:
- Engineering & Manufacturing: "How it's made" production processes, mechanical systems, industrial manufacturing
- Physics: Waves, optics, motion, forces, energy, thermodynamics, electricity, magnetism
- Biology: Cell processes, genetics, ecology, evolution, anatomy, physiology
- Computer Science: Algorithms, data structures, networking, AI, encryption, computation
- Chemistry: Reactions, molecular structures, materials science, bonding

EXAMPLE DIVERSE TOPICS:
- How injection molding creates plastic parts through high-pressure manufacturing (manufacturing)
- How fiber optic cables transmit data using total internal reflection (physics)
- How CRISPR gene editing targets specific DNA sequences in living cells (biology)
- How public key encryption uses prime factorization for secure communication (computer science)
- How catalytic converters transform toxic exhaust using redox reactions (chemistry)

CRITICAL OUTPUT FORMAT - Output EXACTLY these two lines with no other text:
Topic: [specific educational science concept]
Tone: energetic pop punk with driving guitars, fast tempo, and rebellious educational energy

EXAMPLE OUTPUT:
Topic: How DNA replication works in cells
Tone: energetic pop punk with driving guitars, fast tempo, and rebellious educational energy

CRITICAL: This is scenario 1 - an automated system. DO NOT brainstorm. DO NOT ask questions. DO NOT offer choices. DO NOT use markdown formatting. ALWAYS use the exact tone specified above. Just output the two lines directly.
Generate ONE topic now:"""

    result = subprocess.run(
        ["/Users/ethantrokie/.npm-global/bin/claude", "-p", prompt, "--model", "claude-sonnet-4-5", "--dangerously-skip-permissions"],
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
        # Case-insensitive matching with various markdown formats
        line_lower = line.lower()

        if line_lower.startswith("topic:") or "**topic:**" in line_lower:
            # Remove all possible formatting
            cleaned = line
            for prefix in ["**Topic:**", "Topic:", "**topic:**", "topic:", "**", "*"]:
                cleaned = cleaned.replace(prefix, "")
            topic = cleaned.strip()

        elif line_lower.startswith("tone:") or "**tone:**" in line_lower:
            # Remove all possible formatting
            cleaned = line
            for prefix in ["**Tone:**", "Tone:", "**tone:**", "tone:", "**", "*"]:
                cleaned = cleaned.replace(prefix, "")
            tone = cleaned.strip()

    if not topic or not tone:
        # Try to extract from first two non-empty lines as fallback
        if len(lines) >= 2:
            # Assume first line is topic, second is tone
            topic = lines[0].split(":", 1)[-1].strip() if ":" in lines[0] else lines[0].strip()
            tone = lines[1].split(":", 1)[-1].strip() if ":" in lines[1] else lines[1].strip()

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

    # Analyze category distribution
    category_analysis = analyze_category_distribution(history, recent_count=20)
    if category_analysis['over_represented']:
        print(f"  ⚠️  Over-represented categories: {', '.join(category_analysis['over_represented'])}")
        for cat in category_analysis['over_represented']:
            pct = category_analysis['percentages'][cat]
            print(f"     {cat}: {pct:.1f}% of recent videos")

    # Build category guidance for prompt
    category_guidance = ""

    # Check engineering/manufacturing representation
    eng_count = category_analysis['counts'].get('engineering', 0)
    mfg_count = category_analysis['counts'].get('manufacturing', 0)
    total_eng_mfg = eng_count + mfg_count
    total = category_analysis['total']
    eng_mfg_pct = (total_eng_mfg / total * 100) if total > 0 else 0

    # Preference for engineering/manufacturing if they're under-represented (target ~30%)
    if eng_mfg_pct < 30:  # Less than 30% of recent videos
        category_guidance = f"""CATEGORY BALANCE PREFERENCE:
Engineering and manufacturing topics are currently at {eng_mfg_pct:.1f}% of recent videos.
PREFER engineering or manufacturing topics to improve variety.
Consider: "How it's made" production processes, engineering mechanisms, industrial systems.
Balance with: physics, biology, computer science, chemistry topics to maintain scientific diversity.
"""

    # Add diversity requirements if categories are over-represented
    if category_analysis['over_represented']:
        over_cats = ', '.join(category_analysis['over_represented'])
        additional_guidance = f"""CATEGORY DIVERSITY REQUIREMENT:
Recent analysis shows these categories are OVER-REPRESENTED: {over_cats}
You MUST choose a topic from a DIFFERENT category to ensure diversity.
Strongly prefer: engineering, manufacturing, or other under-represented categories.
AVOID quantum mechanics topics unless it's been 7+ videos since the last quantum topic."""
        category_guidance = category_guidance + "\n" + additional_guidance if category_guidance else additional_guidance

    # Fetch trending topics if enabled
    trends_text = ""
    trends_config = config.get("trends", {})
    if trends_config.get("enabled", False):
        print("📈 Fetching Google Trends data...")
        try:
            trends = get_trending_science_topics(config)
            trends_text = format_trends_for_prompt(trends)
            if trends_text:
                print(f"  Found {len(trends.get('top', []))} top + {len(trends.get('rising', []))} rising trends")
            else:
                print("  No trends data available")
        except Exception as e:
            print(f"  Warning: Could not fetch trends: {e}")
            trends_text = ""

    # Try to generate a unique topic (up to 3 attempts)
    max_attempts = 3
    for attempt in range(1, max_attempts + 1):
        # Generate topic via Claude
        output = generate_topic_via_claude(config, recent_topics, trends_text, category_guidance)
        topic, tone = parse_topic_output(output)

        # Check for similarity with recent topics
        is_similar, similar_topic, similarity = check_topic_similarity(topic, recent_topics, threshold=0.3)

        if not is_similar:
            # Topic is unique, we're done
            print(f"  ✅ Unique topic generated (attempt {attempt})")
            print(f"  Topic: {topic}")
            print(f"  Tone: {tone}")
            break
        else:
            # Topic is too similar
            print(f"  ⚠️  Attempt {attempt}: Topic too similar to recent topic")
            print(f"     Similarity: {similarity:.1%} - {similar_topic[:80]}...")

            if attempt < max_attempts:
                print(f"     Retrying...")
                # Add this topic to avoid list for next attempt
                recent_topics.append(topic)
            else:
                # Last attempt failed, but use it anyway
                print(f"     Using topic despite similarity (max attempts reached)")
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
