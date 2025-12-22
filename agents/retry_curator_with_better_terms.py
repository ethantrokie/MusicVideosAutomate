#!/usr/bin/env python3
"""
Retry curator with improved search terms when quality filter fails.
Analyzes rejected clips to generate better search queries.
"""

import json
import sys
import subprocess
from pathlib import Path


def get_output_path(filename: str) -> Path:
    """Get path in OUTPUT_DIR."""
    import os
    output_dir = os.getenv("OUTPUT_DIR", "outputs")
    return Path(output_dir) / filename


def generate_improved_search_terms(research: dict, rejected_ads: list) -> dict:
    """
    Generate improved search terms based on why clips were rejected.

    Args:
        research: Original research.json
        rejected_ads: List of rejected ad clips with reasons

    Returns:
        Modified research with improved search terms
    """
    # Extract common ad patterns from rejected clips
    ad_keywords = set()
    for clip in rejected_ads[:5]:  # Check first 5 rejections
        reason = clip.get('ad_reason', '').lower()
        for keyword in ['url', 'website', 'com', 'brand', 'logo', 'text', 'overlay']:
            if keyword in reason:
                ad_keywords.add(keyword)

    # Modify search terms to exclude problematic content
    improved_research = research.copy()

    # Add negative keywords to visual search
    visual_search = improved_research.get('visual_search_terms', [])

    # Make searches more specific to animations/diagrams
    specific_terms = []
    for term in visual_search:
        # Add modifiers to avoid ads and text overlays
        specific_terms.append(f"{term} animation")
        specific_terms.append(f"{term} diagram")
        specific_terms.append(f"{term} microscope")
        specific_terms.append(f"scientific {term}")

    improved_research['visual_search_terms'] = specific_terms

    print(f"  🔄 Generated {len(specific_terms)} improved search terms")
    print(f"  📝 Focusing on: animations, diagrams, scientific content")

    return improved_research


def main():
    """Main entry point."""
    # Load research
    research_path = get_output_path("research.json")
    if not research_path.exists():
        print("❌ research.json not found")
        sys.exit(1)

    with open(research_path) as f:
        research = json.load(f)

    # Load quality filter results to understand why clips were rejected
    filter_results_path = get_output_path("quality_filter_results.json")
    if filter_results_path.exists():
        with open(filter_results_path) as f:
            filter_results = json.load(f)
        rejected_ads = filter_results.get('ads_rejected', [])
        print(f"🔍 Analyzing {len(rejected_ads)} rejected ads to improve search...")
    else:
        rejected_ads = []
        print("⚠️  No filter results found, using generic improvements")

    # Generate improved search terms
    improved_research = generate_improved_search_terms(research, rejected_ads)

    # Backup original research and replace with improved version
    import shutil
    backup_path = get_output_path("research_original_backup.json")
    shutil.copy(research_path, backup_path)
    print(f"📦 Backed up original research to {backup_path}")

    # Save improved research as main research.json
    with open(research_path, 'w') as f:
        json.dump(improved_research, f, indent=2)
    print(f"✅ Updated research.json with improved search terms")

    # Re-run media planning with improved research
    print("\n📋 Rebuilding media plan with improved search terms...")
    result = subprocess.run([sys.executable, 'agents/build_format_media_plan.py'])
    if result.returncode != 0:
        print("❌ Failed to rebuild media plan")
        # Restore original research
        shutil.copy(backup_path, research_path)
        sys.exit(1)

    # Re-download media with new plan
    print("\n⬇️ Downloading media with improved search terms...")
    result = subprocess.run([sys.executable, 'agents/download_media.py'])
    if result.returncode != 0:
        print("❌ Failed to download media")
        # Restore original research
        shutil.copy(backup_path, research_path)
        sys.exit(1)

    print("✅ Recovery complete - new media downloaded")
    sys.exit(0)


if __name__ == "__main__":
    main()
