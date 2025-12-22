#!/usr/bin/env python3
"""
Media Search CLI Tool
Allows LLMs to search for real videos/GIFs using APIs.

Usage:
    python search_media.py "photon particle" --type=video --source=pexels --max=3
    python search_media.py "electricity spark" --type=gif --source=giphy
"""

import sys
import json
import argparse
from pathlib import Path
from media_search_api import MediaSearcher


def main():
    parser = argparse.ArgumentParser(
        description='Search for videos and GIFs using stock media APIs'
    )
    parser.add_argument(
        'query',
        help='Search query (e.g., "photon particle", "electricity spark")'
    )
    parser.add_argument(
        '--type',
        choices=['video', 'gif'],
        default='video',
        help='Media type to search for (default: video)'
    )
    parser.add_argument(
        '--source',
        choices=['pexels', 'pixabay', 'giphy', 'auto'],
        default='auto',
        help='Source to search (default: auto - tries multiple sources)'
    )
    parser.add_argument(
        '--max',
        type=int,
        default=5,
        help='Maximum results to return (default: 5)'
    )
    parser.add_argument(
        '--min-duration',
        type=float,
        default=3.0,
        help='Minimum video duration in seconds (default: 3.0)'
    )
    parser.add_argument(
        '--max-duration',
        type=float,
        default=30.0,
        help='Maximum video duration in seconds (default: 30.0)'
    )
    parser.add_argument(
        '--json',
        action='store_true',
        help='Output results as JSON (default: human-readable)'
    )

    args = parser.parse_args()

    # Initialize searcher
    searcher = MediaSearcher()

    # Determine source based on media type
    if args.source == 'auto':
        if args.type == 'gif':
            source = 'giphy'
        else:
            source = 'pexels'  # Default to Pexels for videos
    else:
        source = args.source

    # Search for media
    try:
        if args.type == 'gif':
            results = searcher.search_videos(
                args.query,
                source='giphy',
                max_results=args.max
            )
        else:
            results = searcher.search_videos(
                args.query,
                source=source,
                max_results=args.max,
                min_duration=args.min_duration,
                max_duration=args.max_duration
            )

            # If no results from first source, try fallback
            if not results and source == 'pexels':
                results = searcher.search_videos(
                    args.query,
                    source='pixabay',
                    max_results=args.max,
                    min_duration=args.min_duration,
                    max_duration=args.max_duration
                )

        # Output results
        if args.json:
            # JSON output for programmatic use
            print(json.dumps(results, indent=2))
        else:
            # Human-readable output
            if not results:
                print(f"No results found for '{args.query}'")
                sys.exit(1)

            print(f"\nFound {len(results)} result(s) for '{args.query}':\n")
            for i, result in enumerate(results, 1):
                title = result.get('title', 'N/A')
                url = result.get('url', 'N/A')
                duration = result.get('duration', 0)
                width = result.get('width', 0)
                height = result.get('height', 0)
                source_name = result.get('source', 'unknown')

                print(f"{i}. {title}")
                print(f"   URL: {url}")
                print(f"   Source: {source_name}")
                if duration > 0:
                    print(f"   Duration: {duration}s")
                if width > 0 and height > 0:
                    print(f"   Resolution: {width}x{height}")
                print()

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
