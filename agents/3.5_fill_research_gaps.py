#!/usr/bin/env python3
"""
Research Gap Filler: Identifies missing media for lyrics and requests more research.
"""

import os
import sys
import json
import logging
from pathlib import Path
from typing import List, Dict, Set

sys.path.insert(0, str(Path(__file__).parent))
from output_helper import get_output_path


class ResearchGapFiller:
    """Detects gaps between lyrics and available media, fills them."""

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def detect_gaps(self, lyrics_data: Dict, visual_rankings: Dict) -> List[str]:
        """
        Detect which lyric concepts lack matching media.

        Args:
            lyrics_data: Lyrics JSON with key_facts_covered
            visual_rankings: Visual rankings JSON with ranked_media

        Returns:
            List of missing concepts/facts
        """
        # Get facts covered by lyrics
        facts_covered = set(lyrics_data.get('key_facts_covered', []))

        # Get facts covered by ranked media
        ranked_media = visual_rankings.get('ranked_media', [])
        media_fact_coverage = set()

        for media in ranked_media:
            recommended_fact = media.get('recommended_fact')
            if recommended_fact is not None:
                media_fact_coverage.add(recommended_fact)

        # Find gaps
        missing_facts = facts_covered - media_fact_coverage

        return list(missing_facts)

    def generate_research_request(self, missing_facts: List[int], research_data: Dict) -> Dict:
        """
        Generate targeted research request for missing concepts.

        Args:
            missing_facts: Indices of facts needing media
            research_data: Original research JSON

        Returns:
            Research request JSON
        """
        key_facts = research_data.get('key_facts', [])
        missing_fact_texts = [key_facts[i] for i in missing_facts if i < len(key_facts)]

        return {
            'missing_concepts': missing_fact_texts,
            'target_media_count': len(missing_facts),
            'tone': research_data.get('tone', 'educational'),
            'existing_media_count': 0  # No longer using media_suggestions - using lyric-based search
        }


def main():
    """Main entry point for gap filling."""
    logging.basicConfig(level=logging.INFO, format='%(message)s')
    logger = logging.getLogger(__name__)

    # Load data
    lyrics_path = get_output_path('lyrics.json')
    rankings_path = get_output_path('visual_rankings.json')
    research_path = get_output_path('research.json')

    if not all([lyrics_path.exists(), rankings_path.exists(), research_path.exists()]):
        logger.error("Missing required input files")
        sys.exit(1)

    with open(lyrics_path) as f:
        lyrics_data = json.load(f)
    with open(rankings_path) as f:
        visual_rankings = json.load(f)
    with open(research_path) as f:
        research_data = json.load(f)

    # Detect gaps
    filler = ResearchGapFiller()
    missing_facts = filler.detect_gaps(lyrics_data, visual_rankings)

    if not missing_facts:
        logger.info("✅ No research gaps detected - all lyrics have matching media")
        sys.exit(0)

    logger.info(f"⚠️  Detected {len(missing_facts)} missing media for lyric concepts")

    # Generate research request
    research_request = filler.generate_research_request(missing_facts, research_data)

    # Save request
    request_path = get_output_path('research_gap_request.json')
    with open(request_path, 'w') as f:
        json.dump(research_request, f, indent=2)

    logger.info(f"📝 Research gap request saved: {request_path}")
    logger.info("   Re-run research agent with gap-filling mode")

    # Exit with code 2 to signal gaps detected
    sys.exit(2)


if __name__ == '__main__':
    main()
