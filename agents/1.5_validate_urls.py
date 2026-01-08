#!/usr/bin/env python3
"""
URL Validation and Fixing Agent
Validates URLs in research.json and replaces hallucinated URLs with real ones from APIs.
"""

import json
import sys
from pathlib import Path
from typing import Dict, List, Optional
from media_search_api import MediaSearcher


class URLValidator:
    """Validates and fixes URLs in research data."""

    def __init__(self, verbose: bool = True):
        self.searcher = MediaSearcher()
        self.verbose = verbose
        self.stats = {
            'total': 0,
            'validated': 0,
            'replaced': 0,
            'failed': 0
        }

    def validate_research_file(self, research_path: Path, output_path: Optional[Path] = None) -> Dict:
        """
        Validate and fix URLs in a research.json file.

        Args:
            research_path: Path to research.json
            output_path: Optional output path (defaults to overwriting input)

        Returns:
            Updated research data with fixed URLs
        """
        if self.verbose:
            print(f"\n🔍 Validating URLs in {research_path.name}...")

        # Load research data
        with open(research_path) as f:
            research_data = json.load(f)

        # Validate each media suggestion
        media_suggestions = research_data.get('media_suggestions', [])
        self.stats['total'] = len(media_suggestions)

        for i, media in enumerate(media_suggestions):
            if self.verbose:
                print(f"\n[{i+1}/{len(media_suggestions)}] Checking: {media.get('description', 'N/A')[:50]}...")

            url = media.get('url')
            media_type = media.get('type', 'video')

            if not url:
                if self.verbose:
                    print("  ⚠️  No URL provided, skipping")
                self.stats['failed'] += 1
                continue

            # Try to validate the URL
            if self.verbose:
                print(f"  🔗 Validating: {url}")

            is_valid = self.searcher.validate_url(url, media_type)

            if is_valid:
                if self.verbose:
                    print("  ✅ URL is valid!")
                self.stats['validated'] += 1
            else:
                if self.verbose:
                    print("  ❌ URL is invalid (hallucinated)")

                # Try to find a replacement
                replacement = self._find_replacement(media)

                if replacement:
                    # Update the media entry with new URL
                    old_url = media['url']
                    media['url'] = replacement['url']
                    media['download_url'] = replacement.get('download_url')

                    # Optionally update metadata if search found better info
                    if replacement.get('title'):
                        media['title'] = replacement['title']

                    if self.verbose:
                        print(f"  ✅ Replaced with: {media['url']}")

                    self.stats['replaced'] += 1
                else:
                    if self.verbose:
                        print("  ⚠️  No replacement found")
                    self.stats['failed'] += 1

        # Save updated research data
        output_path = output_path or research_path
        with open(output_path, 'w') as f:
            json.dump(research_data, f, indent=2)

        # Print summary
        if self.verbose:
            self._print_summary()

        return research_data

    def _find_replacement(self, media: Dict) -> Optional[Dict]:
        """
        Find a replacement URL for invalid media.

        Args:
            media: Media entry from research.json

        Returns:
            Dict with url, download_url, title, etc. or None if not found
        """
        description = media.get('description', '')
        media_type = media.get('type', 'video')
        source = self._extract_source(media.get('url', ''))

        if not description:
            return None

        # Extract search terms from description
        search_query = self.searcher.extract_search_terms(description, max_terms=4)

        if self.verbose:
            print(f"  🔎 Searching for: '{search_query}'")

        # Search for replacement based on media type
        if media_type == 'gif':
            results = self.searcher.search_videos(search_query, source='giphy', max_results=3)
        else:
            # Try preferred source first, then fallback
            results = self.searcher.search_videos(
                search_query,
                source=source or 'pexels',
                max_results=3,
                min_duration=5.0,  # Minimum 5 seconds for educational content
                max_duration=20.0  # Maximum 20 seconds
            )

            # If no results from preferred source, try other sources
            if not results and source != 'pixabay':
                results = self.searcher.search_videos(
                    search_query,
                    source='pixabay',
                    max_results=3,
                    min_duration=5.0,
                    max_duration=20.0
                )

        # Return best match (first result is usually most relevant)
        if results:
            best_match = results[0]
            if self.verbose:
                duration = best_match.get('duration', 0)
                print(f"  ✨ Found: {best_match.get('title', 'N/A')[:40]}... ({duration}s)")
            return best_match

        return None

    def _extract_source(self, url: str) -> Optional[str]:
        """Extract the source platform from a URL."""
        if 'pexels.com' in url:
            return 'pexels'
        elif 'pixabay.com' in url:
            return 'pixabay'
        elif 'giphy.com' in url:
            return 'giphy'
        return None

    def _print_summary(self):
        """Print validation summary statistics."""
        total = self.stats['total']
        validated = self.stats['validated']
        replaced = self.stats['replaced']
        failed = self.stats['failed']

        success_rate = ((validated + replaced) / total * 100) if total > 0 else 0

        print("\n" + "="*60)
        print("📊 VALIDATION SUMMARY")
        print("="*60)
        print(f"Total URLs:       {total}")

        if total > 0:
            print(f"✅ Validated:     {validated} ({validated/total*100:.1f}%)")
            print(f"🔄 Replaced:      {replaced} ({replaced/total*100:.1f}%)")
            print(f"❌ Failed:        {failed} ({failed/total*100:.1f}%)")
            print(f"\n🎯 Success Rate:  {success_rate:.1f}%")
        else:
            print("ℹ️  No media_suggestions found in research.json")
            print("   (This is normal when using lyric-based media search)")

        print("="*60)


def main():
    """Main entry point for URL validation."""
    import argparse

    parser = argparse.ArgumentParser(description='Validate and fix URLs in research.json')
    parser.add_argument(
        'research_file',
        nargs='?',
        help='Path to research.json file (default: latest run)'
    )
    parser.add_argument(
        '--output',
        '-o',
        help='Output path (default: overwrite input file)'
    )
    parser.add_argument(
        '--quiet',
        '-q',
        action='store_true',
        help='Quiet mode (minimal output)'
    )

    args = parser.parse_args()

    # Determine research file path
    if args.research_file:
        research_path = Path(args.research_file)
    else:
        # Find latest run directory
        runs_dir = Path('outputs/runs')
        if not runs_dir.exists():
            print("❌ No runs directory found")
            sys.exit(1)

        run_dirs = sorted([d for d in runs_dir.iterdir() if d.is_dir()], reverse=True)
        if not run_dirs:
            print("❌ No run directories found")
            sys.exit(1)

        research_path = run_dirs[0] / 'research.json'

    if not research_path.exists():
        print(f"❌ Research file not found: {research_path}")
        sys.exit(1)

    # Validate and fix URLs
    validator = URLValidator(verbose=not args.quiet)
    output_path = Path(args.output) if args.output else None

    try:
        validator.validate_research_file(research_path, output_path)

        # Exit with error code if too many failures
        success_rate = ((validator.stats['validated'] + validator.stats['replaced']) /
                       validator.stats['total'] * 100) if validator.stats['total'] > 0 else 0

        if success_rate < 80:
            print(f"\n⚠️  Warning: Success rate ({success_rate:.1f}%) is below 80%")
            sys.exit(1)

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
