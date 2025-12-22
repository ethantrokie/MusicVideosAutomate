#!/Users/ethantrokie/SoftwareDevProjects/MusicVideosAutomate/venv/bin/python3
"""
Google Trends fetcher for topic generation.
Uses pytrends to get trending science/education topics.
"""

import json
import time
from datetime import datetime, timedelta
from pathlib import Path
from pytrends.request import TrendReq


# Google Trends category IDs
CATEGORIES = {
    'science': 174,
    'physics': 444,
    'chemistry': 505,
    'biology': 440,
    'astronomy': 435,
    'education': 74,
    'earth_sciences': 1168,
}

# Default seed keywords for science/education content
DEFAULT_SEEDS = [
    'science explained',
    'how does',
    'physics',
    'biology',
]

CACHE_FILE = Path("automation/state/trends_cache.json")


def load_cache():
    """Load cached trends if still valid."""
    if not CACHE_FILE.exists():
        return None

    try:
        with open(CACHE_FILE) as f:
            cache = json.load(f)

        # Check if cache is still valid
        cached_time = datetime.fromisoformat(cache['timestamp'])
        cache_duration = timedelta(hours=cache.get('cache_hours', 6))

        if datetime.now() - cached_time < cache_duration:
            return cache['trends']
    except (json.JSONDecodeError, KeyError, ValueError):
        pass

    return None


def save_cache(trends, cache_hours=6):
    """Save trends to cache."""
    cache = {
        'timestamp': datetime.now().isoformat(),
        'cache_hours': cache_hours,
        'trends': trends
    }

    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(CACHE_FILE, 'w') as f:
        json.dump(cache, f, indent=2)


def fetch_related_queries(pytrends, keywords, category=174):
    """
    Fetch related queries for given keywords.

    Args:
        pytrends: TrendReq instance
        keywords: List of seed keywords (max 5)
        category: Google Trends category ID (default: 174 = Science)

    Returns:
        Dict with 'top' and 'rising' lists
    """
    results = {'top': [], 'rising': []}

    # Process keywords in batches of 5 (pytrends limit)
    for i in range(0, len(keywords), 5):
        batch = keywords[i:i+5]

        try:
            pytrends.build_payload(
                batch,
                cat=category,
                timeframe='today 3-m',  # Last 3 months
                geo='US'
            )

            related = pytrends.related_queries()

            for keyword in batch:
                if keyword in related:
                    # Extract top queries
                    top_df = related[keyword].get('top')
                    if top_df is not None and not top_df.empty:
                        for _, row in top_df.iterrows():
                            results['top'].append({
                                'query': row['query'],
                                'score': int(row['value']),
                                'source_keyword': keyword
                            })

                    # Extract rising queries
                    rising_df = related[keyword].get('rising')
                    if rising_df is not None and not rising_df.empty:
                        for _, row in rising_df.iterrows():
                            # Rising can have "Breakout" as value
                            score = row['value']
                            if isinstance(score, str) and 'Breakout' in score:
                                score = 1000  # Treat breakout as high score
                            results['rising'].append({
                                'query': row['query'],
                                'score': int(score) if isinstance(score, (int, float)) else 1000,
                                'source_keyword': keyword
                            })

            # Rate limiting - be nice to Google
            time.sleep(1)

        except Exception as e:
            print(f"  Warning: Failed to fetch trends for {batch}: {e}")
            continue

    return results


def deduplicate_and_sort(queries, limit=10):
    """
    Deduplicate queries and return top N by score.

    Args:
        queries: List of query dicts with 'query' and 'score'
        limit: Max number to return

    Returns:
        List of unique query strings, sorted by score
    """
    seen = set()
    unique = []

    # Sort by score descending
    sorted_queries = sorted(queries, key=lambda x: x['score'], reverse=True)

    for q in sorted_queries:
        query_lower = q['query'].lower()
        if query_lower not in seen:
            seen.add(query_lower)
            unique.append(q['query'])
            if len(unique) >= limit:
                break

    return unique


def get_trending_science_topics(config=None):
    """
    Main function to get trending science/education topics.

    Args:
        config: Optional config dict with 'trends' settings

    Returns:
        Dict with 'top' and 'rising' lists of query strings
    """
    # Load config defaults
    if config is None:
        config = {}

    trends_config = config.get('trends', {})
    seed_keywords = trends_config.get('seed_keywords', DEFAULT_SEEDS)
    top_count = trends_config.get('top_queries_count', 5)
    rising_count = trends_config.get('rising_queries_count', 5)
    cache_hours = trends_config.get('cache_duration_hours', 6)
    category = trends_config.get('category', 174)  # Science

    # Check cache first
    cached = load_cache()
    if cached:
        print("  Using cached trends data")
        return cached

    print("  Fetching fresh trends from Google...")

    try:
        # Initialize pytrends
        pytrends = TrendReq(hl='en-US', tz=360)

        # Fetch related queries
        raw_results = fetch_related_queries(pytrends, seed_keywords, category)

        # Deduplicate and get top results
        trends = {
            'top': deduplicate_and_sort(raw_results['top'], top_count),
            'rising': deduplicate_and_sort(raw_results['rising'], rising_count)
        }

        # Cache results
        save_cache(trends, cache_hours)

        return trends

    except Exception as e:
        print(f"  Warning: Could not fetch trends: {e}")
        return {'top': [], 'rising': []}


def format_trends_for_prompt(trends):
    """
    Format trends dict into a string for the Claude prompt.

    Args:
        trends: Dict with 'top' and 'rising' lists

    Returns:
        Formatted string for prompt inclusion
    """
    if not trends['top'] and not trends['rising']:
        return ""

    lines = ["TRENDING SCIENCE TOPICS (from Google Trends):"]

    if trends['top']:
        lines.append(f"Popular searches: {', '.join(trends['top'])}")

    if trends['rising']:
        lines.append(f"Rising searches: {', '.join(trends['rising'])}")

    return '\n'.join(lines)


# CLI for testing
if __name__ == "__main__":
    print("Testing Google Trends fetcher...")

    trends = get_trending_science_topics()

    print("\nTop queries:")
    for q in trends['top']:
        print(f"  - {q}")

    print("\nRising queries:")
    for q in trends['rising']:
        print(f"  - {q}")

    print("\nFormatted for prompt:")
    print(format_trends_for_prompt(trends))
