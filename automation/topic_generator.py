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


def get_all_topics_for_exact_match(history):
    """Get all historical topics for exact duplicate checking (not just recent)."""
    return [entry["topic"] for entry in history["topics"]]


def check_category_spacing(new_topic, recent_topics, min_spacing=7):
    """
    Check if topic's category was used too recently.
    Returns (is_too_soon, category, last_index) where last_index is how many videos ago.
    """
    # Define category keywords
    category_keywords = {
        'quantum': ['quantum', 'entanglement', 'tunneling', 'photoelectric', 'superconductivity', 'superconductor'],
        'astronomy': ['galaxy', 'star', 'planet', 'universe', 'cosmic', 'space', 'nebula', 'black hole'],
        'biology': ['cell', 'dna', 'protein', 'photosynthesis', 'bacteria', 'evolution', 'gene', 'crispr'],
        'chemistry': ['molecule', 'chemical', 'reaction', 'atom', 'element', 'compound', 'catalyst'],
    }

    # Identify new topic's category
    new_topic_lower = new_topic.lower()
    new_category = None
    for category, keywords in category_keywords.items():
        if any(keyword in new_topic_lower for keyword in keywords):
            new_category = category
            break

    # If not in tracked categories, no spacing constraint
    if not new_category:
        return False, None, -1

    # Check recent topics for same category
    for i, recent_topic in enumerate(reversed(recent_topics[-min_spacing:])):
        recent_lower = recent_topic.lower()
        for keyword in category_keywords[new_category]:
            if keyword in recent_lower:
                # Found same category within spacing window
                videos_ago = i + 1
                return True, new_category, videos_ago

    return False, None, -1


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
    # First: Check for exact duplicates (case-insensitive)
    new_normalized = new_topic.lower().strip()
    for recent in recent_topics:
        recent_normalized = recent.lower().strip()
        if new_normalized == recent_normalized:
            return True, recent, 1.0  # Exact match

    # Second: Check keyword similarity
    for recent in recent_topics:
        similarity = calculate_topic_similarity(new_topic, recent)
        if similarity >= threshold:
            return True, recent, similarity

    return False, None, 0.0


def analyze_category_distribution(history, recent_count=20):
    """
    Analyze category distribution in recent topics.
    Uses fine-grained categories matching performance data from backfill_analytics.
    Returns dict with category counts and over-represented categories.
    """
    # Get recent entries with full data
    recent_entries = history["topics"][-recent_count:] if history["topics"] else []

    # Fine-grained categories matching the performance data
    # Order matters: more specific categories checked first
    category_keywords = {
        'metalworking': [
            'laser cut', 'plasma cut', 'cnc', 'milling', 'welding', 'weld',
            'forging', 'forge', 'metal explained', 'shapes metal', 'slice metal',
            'vaporize metal', 'joins metal', 'induction heating',
        ],
        'mechanical_engineering': [
            'engine', 'turbofan', 'turbine', 'piston', 'gear', 'transmission',
            'brake', 'hydraulic', 'pneumatic', 'regenerative', 'flywheel',
            'crankshaft', 'excavator', 'jet', 'propulsion', 'aerodynamic',
        ],
        'electrical_engineering': [
            'circuit', 'motor', 'generator', 'transformer', 'capacitor',
            'diode', 'kirchhoff', 'piezoelectric', 'voltage', 'induction motor',
            'battery', 'solar panel', 'wind turbine',
        ],
        'manufacturing': [
            'injection mold', 'die casting', '3d printing', 'extru',
            'grain elevator', 'paper', 'wood chips', 'fiberglass', 'insulation',
            'ball bearing', 'bearing', 'anodiz', 'tempered glass',
            'assembly line', 'production process', 'factory',
            'how steel', 'how glass', 'how plastic', 'how rubber', 'how aluminum',
        ],
        'computer_science': [
            'algorithm', 'data structure', 'hash table', 'sql', 'database',
            'microchip', 'semiconductor', 'processor', 'encryption', 'networking',
            'binary', 'compiler', 'memory', 'cpu',
        ],
        'biology': [
            'cell', 'dna', 'protein', 'photosynthesis', 'bacteria', 'evolution',
            'gene', 'crispr', 'kidney', 'urine', 'eye', 'anatomy', 'organ',
            'blood', 'muscle', 'nerve', 'brain', 'immune', 'virus',
        ],
        'physics': [
            'light', 'wave', 'optic', 'refraction', 'polarized', 'sonar',
            'force', 'pressure', 'momentum', 'doppler', 'magnetism',
            'thermodynamic', 'radiation', 'spectrum',
        ],
        'chemistry': [
            'molecule', 'chemical', 'reaction', 'atom', 'element', 'catalyst',
            'compound', 'oxidation', 'vapor deposition', 'bonding', 'ion',
        ],
        'food_science': [
            'freeze-dry', 'freeze dry', 'chocolate', 'ferment', 'pasteur',
            'food', 'cooking science', 'baking',
        ],
        'environmental': [
            'sewage', 'water purif', 'recycl', 'waste', 'pollution',
            'renewable', 'carbon capture',
        ],
        'earth_science': [
            'ocean', 'hurricane', 'rock', 'tectonic', 'geological',
            'volcano', 'earthquake', 'weather', 'glacier', 'erosion',
        ],
        'quantum': [
            'quantum', 'entanglement', 'tunneling', 'photoelectric',
            'superconductivity', 'superconductor',
        ],
    }

    category_counts = Counter()

    for entry in recent_entries:
        topic = entry.get("topic", "").lower()

        # Check which category this topic belongs to
        matched = False
        for category, keywords in category_keywords.items():
            if any(keyword in topic for keyword in keywords):
                category_counts[category] += 1
                matched = True
                break  # Only count once per topic

        if not matched:
            category_counts['other'] += 1

    # Calculate percentages
    total = len(recent_entries)
    category_percentages = {cat: (count / total * 100) for cat, count in category_counts.items()}

    # Identify over-represented categories using data-driven targets
    over_represented = []
    for cat, pct in category_percentages.items():
        target = CATEGORY_TARGETS.get(cat, 0.10) * 100  # default 10% target
        if pct > target + 10:  # more than 10 percentage points over target
            over_represented.append(cat)

    return {
        'counts': dict(category_counts),
        'percentages': category_percentages,
        'over_represented': over_represented,
        'total': total
    }


def _get_tone_mode():
    """
    Check for active tone A/B test experiment.
    Returns "baseline" or "diversified" based on the current week.
    Falls back to "diversified" if no experiment is running.
    """
    import json as _json
    from datetime import datetime as _dt

    experiments_path = Path("automation/state/ab_experiments.json")
    if not experiments_path.exists():
        return "diversified"

    try:
        with open(experiments_path) as f:
            data = _json.load(f)
    except (_json.JSONDecodeError, IOError):
        return "diversified"

    for exp in data.get("experiments", []):
        if exp.get("status") != "active":
            continue
        if exp.get("config_key") != "tone_mode":
            continue

        created = _dt.fromisoformat(exp["created_at"])
        elapsed_days = (_dt.now() - created).days
        current_week = max(1, (elapsed_days // 7) + 1)

        if current_week > exp.get("duration_weeks", 8):
            continue

        # Odd weeks = control (baseline), even weeks = treatment (diversified)
        if current_week % 2 == 1:
            return exp.get("control_value", "baseline")
        return exp.get("treatment_value", "diversified")

    return "diversified"


def _build_tone_prompt_sections():
    """
    Build tone guidelines and examples for the topic generator prompt.
    In "baseline" mode, all categories use proven pop-punk/pop-rock tones.
    In "diversified" mode, categories use their matched tones.
    """
    mode = _get_tone_mode()

    if mode == "baseline":
        guidelines = """TONE GUIDELINES - Use one of these proven baseline tones:
- For high-energy topics: energetic pop punk with driving guitars, pounding drums, and rebellious energy
- For educational/explanatory topics: upbeat pop rock with catchy hooks, bright guitars, and enthusiastic energy
Choose whichever best fits the energy level of the topic. These are the channel's proven performers."""

        examples = """EXAMPLE OUTPUTS:
Topic: How injection molding creates plastic parts through high-pressure manufacturing
Tone: energetic pop punk with driving guitars, pounding drums, and rebellious energy

Topic: How photosynthesis converts sunlight into chemical energy in plant cells
Tone: upbeat pop rock with catchy hooks, bright guitars, and enthusiastic energy"""

    else:  # diversified
        guidelines = """TONE GUIDELINES - Match the musical tone to the topic category:
- Manufacturing/forging/industrial: energetic pop punk with driving guitars, pounding drums, and rebellious energy
- Biology/nature/ecology: organic flowing pop with ambient textures, melodic hooks, and warm educational energy
- Physics/optics/waves: electronic synth-pop with precise beats, crystalline melodies, and futuristic energy
- Everyday objects/consumer products: upbeat pop rock with catchy hooks, bright guitars, and enthusiastic energy
- Computer science/algorithms: lo-fi electronic with digital glitch textures, steady beats, and curious energy
- Chemistry/materials science: dynamic progressive rock with building intensity, layered sounds, and discovery energy
- Earth science/geology: epic orchestral rock with sweeping melodies, thundering drums, and awe-inspiring energy
- Engineering/mechanical systems: driving rock with mechanical rhythms, powerful guitars, and energetic momentum"""

        examples = """EXAMPLE OUTPUTS:
Topic: How injection molding creates plastic parts through high-pressure manufacturing
Tone: energetic pop punk with driving guitars, pounding drums, and rebellious energy

Topic: How photosynthesis converts sunlight into chemical energy in plant cells
Tone: organic flowing pop with ambient textures, melodic hooks, and warm educational energy"""

    print(f"  🎵 Tone mode: {mode}")
    return guidelines, examples


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

    # Build recent topics section with full context
    recent_topics_section = ""
    if recent_topics:
        # Show last 20 topics (or all if fewer than 20)
        topics_to_show = recent_topics[-20:] if len(recent_topics) > 20 else recent_topics
        recent_topics_formatted = "\n".join([f"  {i+1}. {topic}" for i, topic in enumerate(topics_to_show)])
        recent_topics_section = f"""

RECENT TOPICS (LAST {len(topics_to_show)} VIDEOS) - DO NOT REPEAT OR CREATE SIMILAR TOPICS:
{recent_topics_formatted}

CRITICAL UNIQUENESS REQUIREMENTS:
- Your topic MUST be completely different from ALL topics listed above
- DO NOT use the same scientific concept, phenomenon, or process
- DO NOT use similar keywords or terminology
- If you notice a pattern (e.g., multiple quantum topics), actively avoid that category
- Prefer under-represented scientific domains

"""

    # Build tone sections based on A/B test state
    tone_guidelines, tone_examples = _build_tone_prompt_sections()

    prompt = f"""SYSTEM CONTEXT: This is an automated pipeline. Do NOT use brainstorming skills. Do NOT ask clarifying questions. Just generate the output directly.

You are a topic generator for educational science music videos. Generate ONE topic ONLY.
{trends_section}{category_section}{recent_topics_section}
REQUIREMENTS:
- Category: One of {categories}
- K-12 appropriate (ages 10-18)
- Visually interesting (stock footage available)
- EVERYDAY RELEVANCE: The topic MUST relate to something the viewer personally encounters in daily life (their car, phone, body, food, home appliances, workplace tools, the buildings they enter, the clothes they wear, etc.)
- UNIQUENESS: Your topic will be compared against recent videos listed below (DO NOT repeat)

TOPIC FRAMING - CRITICAL:
Frame every topic as a SINGLE SURPRISING REVELATION, not a process explanation.
- DO NOT write "How X works" or "How X is made"
- DO NOT write multi-step process topics (e.g., "The 12 steps of aluminum stamping")
- DO frame as: "The reason X does Y" or "Why X is actually Y" or "The hidden Z inside every W"
- The topic should make someone say "Wait, really?!" -- a single counterintuitive or mind-blowing fact

GOOD EXAMPLES (revelation-framed, everyday relevance):
- The reason your dishwasher actually uses less water than washing by hand
- Why the tiny holes in airplane windows keep you alive at 35,000 feet
- The hidden generator inside your car that charges itself every time you brake
- Why aluminum cans are thinner than a human hair yet hold 90 PSI of pressure
- The 1788 device inside every engine that prevents it from tearing itself apart

BAD EXAMPLES (process-framed, avoid these):
- How freeze-drying preserves food through sublimation
- How aluminum cans are manufactured through a 12-step stamping process
- How regenerative braking converts kinetic energy into electrical energy
- How solenoid valves control fluid flow through electromagnetic actuation

TOPIC VARIETY - Diversify across these categories (ranked by audience retention):
- Mechanical Engineering (TOP PERFORMER): Engines, brakes, hydraulic systems, pneumatic mechanisms, gear systems
- Biology (TOP PERFORMER, highest subscriber growth): Anatomy, physiology, cell processes, organ systems
- Computer Science (TOP PERFORMER): Microchip fabrication, algorithms, networking, data structures
- Electrical Engineering: Motors, transformers, circuits, power systems
- Manufacturing: Production processes, industrial systems, materials
- Physics: Waves, optics, motion, forces, thermodynamics
- Chemistry: Reactions, materials science, chemical processes

CRITICAL OUTPUT FORMAT - Output EXACTLY these two lines with no other text:
Topic: [single surprising revelation about an everyday thing]
Tone: [musical tone matched to the topic - see guidelines below]

{tone_guidelines}

{tone_examples}

CRITICAL: This is scenario 1 - an automated system. DO NOT brainstorm. DO NOT ask questions. DO NOT offer choices. DO NOT use markdown formatting. Choose a tone that MATCHES the topic category from the guidelines above. Just output the two lines directly.
Generate ONE topic now:"""

    result = subprocess.run(
        ["/Users/ethantrokie/.local/bin/claude", "-p", prompt, "--model", "claude-sonnet-4-5", "--dangerously-skip-permissions"],
        capture_output=True,
        text=True,
        timeout=120
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


def _load_category_performance():
    """
    Load category performance data from backfill analytics.
    Returns dict of category -> {engaged_view_rate, subs_per_topic, views} or None.
    """
    perf_path = Path("automation/state/video_performance_history.json")
    if not perf_path.exists():
        return None
    try:
        with open(perf_path) as f:
            data = json.load(f)
        return data.get("category_summary", None)
    except (json.JSONDecodeError, IOError):
        return None


# Data-driven category targets based on engaged view rate (the "stayed vs swiped" proxy).
# Updated from backfill_analytics.py results across 137 videos.
# Higher engaged_view_rate = more people stay to watch instead of swiping away.
CATEGORY_TARGETS = {
    # Tier 1: Highest engaged view rate (45%+) — grow these
    "mechanical_engineering": 0.20,  # 49.0% engaged rate, turbofans/hydraulics/pneumatics
    "biology": 0.15,                # 47.3% engaged rate, highest subs/topic (6.0)
    "computer_science": 0.15,       # 45.3% engaged rate, microchips/SQL/hash tables

    # Tier 2: Solid performers (37-42%) — maintain
    "electrical_engineering": 0.15, # 38.9% engaged rate, transformers/motors/circuits
    "manufacturing": 0.15,          # 37.5% engaged rate, grain/paper/injection molding

    # Tier 3: Lower engaged rate (33-37%) — reduce frequency
    "metalworking": 0.10,           # 34.8% engaged rate — was over-indexed at ~35% of videos
    "physics": 0.05,                # 35.2% engaged rate, sonar/optics
    "chemistry": 0.05,              # 35.6% engaged rate, CVD/reactions
}


def build_data_driven_category_guidance(category_analysis):
    """
    Build category guidance for the Claude prompt using real performance data.
    Compares current category distribution against targets derived from engaged view rates.
    """
    perf_data = _load_category_performance()
    total = category_analysis['total']
    if total == 0:
        return ""

    counts = category_analysis['counts']

    # Map the analysis categories to our target categories
    # The analysis uses broader buckets, so we need to combine some
    current_pcts = {}
    for cat in CATEGORY_TARGETS:
        current_pcts[cat] = (counts.get(cat, 0) / total * 100) if total > 0 else 0

    # Also check combined eng+mfg+metal since the analyzer may lump them
    eng_combined = counts.get('engineering', 0) + counts.get('manufacturing', 0)
    eng_combined_pct = (eng_combined / total * 100) if total > 0 else 0

    # Find under-represented categories (current % is more than 5 points below target)
    under_rep = []
    over_rep = []
    for cat, target_pct in CATEGORY_TARGETS.items():
        target = target_pct * 100
        actual = current_pcts.get(cat, 0)
        if actual < target - 5:
            under_rep.append((cat, actual, target))
        elif actual > target + 10:
            over_rep.append((cat, actual, target))

    # Build performance insight strings
    perf_insights = ""
    if perf_data:
        # Sort categories by engaged view rate
        sorted_cats = sorted(
            perf_data.items(),
            key=lambda x: x[1].get("engaged_view_rate", 0),
            reverse=True
        )
        top_cats = sorted_cats[:3]
        perf_insights = "PROVEN TOP PERFORMERS (by % of viewers who stay vs swipe away):\n"
        for cat, data in top_cats:
            rate = data.get("engaged_view_rate", 0)
            subs = data.get("subscribers_gained", 0)
            topic_count = data.get("topic_count", 1)
            subs_per = subs / max(topic_count, 1)
            perf_insights += f"- {cat.replace('_', ' ').title()}: {rate:.0f}% stayed to watch, {subs_per:.1f} new subs/topic\n"

    guidance = f"""CATEGORY DISTRIBUTION (data-driven from channel analytics):

{perf_insights}
TARGET MIX for upcoming videos:
- Mechanical Engineering (turbofans, hydraulics, pneumatics): ~20%
- Biology (anatomy, physiology, cell processes): ~15%
- Computer Science (algorithms, chips, databases): ~15%
- Electrical Engineering (motors, circuits, transformers): ~15%
- Manufacturing (production processes, "how it's made"): ~15%
- Metalworking (CNC, welding, forging, laser cutting): ~10%
- Physics & Chemistry: ~10%
"""

    if under_rep:
        cats_str = ", ".join(f"{c.replace('_', ' ')} ({a:.0f}% actual vs {t:.0f}% target)" for c, a, t in under_rep)
        guidance += f"\nUNDER-REPRESENTED — PREFER THESE: {cats_str}\n"

    if over_rep:
        cats_str = ", ".join(f"{c.replace('_', ' ')} ({a:.0f}% actual vs {t:.0f}% target)" for c, a, t in over_rep)
        guidance += f"\nOVER-REPRESENTED — AVOID THESE: {cats_str}\n"

    guidance += "\nAVOID abstract quantum physics — stock footage cannot visualize these well."

    return guidance


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

    # Build data-driven category guidance from real performance metrics
    category_guidance = build_data_driven_category_guidance(category_analysis)

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

    # Get all topics for exact duplicate checking (not just recent)
    all_topics = get_all_topics_for_exact_match(history)

    # Try to generate a unique topic (up to 5 attempts)
    max_attempts = 5
    for attempt in range(1, max_attempts + 1):
        # Generate topic via Claude
        output = generate_topic_via_claude(config, recent_topics, trends_text, category_guidance)
        topic, tone = parse_topic_output(output)

        # Check 1: Duplicate/near-duplicate against ALL history (stricter threshold)
        is_similar, similar_topic, similarity = check_topic_similarity(topic, all_topics, threshold=0.3)

        if is_similar and similarity == 1.0:
            # Exact duplicate found
            print(f"  ⚠️  Attempt {attempt}: EXACT DUPLICATE of historical topic")
            print(f"     Rejected: {similar_topic[:80]}...")
            if attempt < max_attempts:
                print(f"     Retrying...")
                recent_topics.append(topic)
            continue

        # Check 2: Similarity with recent topics (stricter threshold)
        is_similar, similar_topic, similarity = check_topic_similarity(topic, recent_topics, threshold=0.2)

        if is_similar:
            # Topic is too similar to recent topic
            print(f"  ⚠️  Attempt {attempt}: Topic too similar to recent topic")
            print(f"     Similarity: {similarity:.1%} - {similar_topic[:80]}...")
            if attempt < max_attempts:
                print(f"     Retrying...")
                recent_topics.append(topic)
            else:
                # Last attempt failed, but use it anyway
                print(f"     Using topic despite similarity (max attempts reached)")
                print(f"  Topic: {topic}")
                print(f"  Tone: {tone}")
            continue

        # Check 3: Category spacing (e.g., no quantum topics within 7 videos)
        is_too_soon, category, videos_ago = check_category_spacing(topic, recent_topics, min_spacing=7)

        if is_too_soon:
            # Category used too recently
            print(f"  ⚠️  Attempt {attempt}: {category.title()} topic used {videos_ago} video(s) ago")
            print(f"     Need {7 - videos_ago} more videos before another {category} topic")
            if attempt < max_attempts:
                print(f"     Retrying...")
                recent_topics.append(topic)
            else:
                # Last attempt failed, but use it anyway
                print(f"     Using topic despite category spacing (max attempts reached)")
                print(f"  Topic: {topic}")
                print(f"  Tone: {tone}")
            continue

        # All checks passed - topic is unique!
        print(f"  ✅ Unique topic generated (attempt {attempt})")
        print(f"  Topic: {topic}")
        print(f"  Tone: {tone}")
        break

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
