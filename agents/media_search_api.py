#!/usr/bin/env python3
"""
Media Search API Extension
Extends StockPhotoResolver with search capabilities to find real videos.
"""

import re
import requests
from typing import List, Dict, Optional
from stock_photo_api import StockPhotoResolver


class MediaSearcher(StockPhotoResolver):
    """Extends StockPhotoResolver with API search capabilities."""

    def search_videos(
        self,
        query: str,
        source: str = 'pexels',
        max_results: int = 5,
        min_duration: float = 3.0,
        max_duration: float = 30.0
    ) -> List[Dict]:
        """
        Search for videos using APIs.

        Args:
            query: Search query (e.g., "photon particle animation")
            source: 'pexels', 'pixabay', or 'giphy'
            max_results: Maximum number of results to return
            min_duration: Minimum video duration in seconds
            max_duration: Maximum video duration in seconds

        Returns:
            List of video dicts with: url, title, duration, width, height
        """
        if source == 'pexels':
            return self._search_pexels_videos(query, max_results, min_duration, max_duration)
        elif source == 'pixabay':
            return self._search_pixabay_videos(query, max_results, min_duration, max_duration)
        elif source == 'giphy':
            return self._search_giphy(query, max_results)
        else:
            return []

    def _search_pexels_videos(
        self,
        query: str,
        max_results: int = 5,
        min_duration: float = 3.0,
        max_duration: float = 30.0
    ) -> List[Dict]:
        """Search Pexels videos API."""
        if not self.pexels_api_key:
            return []

        try:
            url = "https://api.pexels.com/videos/search"
            headers = {"Authorization": self.pexels_api_key}
            params = {
                'query': query,
                'per_page': max_results,
                'orientation': 'landscape'  # Prefer landscape for educational videos
            }

            response = requests.get(url, headers=headers, params=params, timeout=10)

            if response.status_code == 200:
                data = response.json()
                results = []

                for video in data.get('videos', []):
                    duration = video.get('duration', 0)

                    # Filter by duration
                    if duration < min_duration or duration > max_duration:
                        continue

                    # Get HD quality video file
                    video_files = video.get('video_files', [])
                    hd_files = [v for v in video_files if v.get('quality') == 'hd']
                    video_file = hd_files[0] if hd_files else video_files[0] if video_files else None

                    if not video_file:
                        continue

                    results.append({
                        'url': video.get('url'),  # Page URL
                        'download_url': video_file.get('link'),  # Direct download
                        'title': video.get('url', '').split('/')[-2],
                        'duration': duration,
                        'width': video_file.get('width', 0),
                        'height': video_file.get('height', 0),
                        'source': 'pexels',
                        'type': 'video'
                    })

                return results[:max_results]

        except Exception as e:
            print(f"  ⚠️  Pexels search error: {e}")
            return []

    def _search_pixabay_videos(
        self,
        query: str,
        max_results: int = 5,
        min_duration: float = 3.0,
        max_duration: float = 30.0
    ) -> List[Dict]:
        """Search Pixabay videos API."""
        if not self.pixabay_api_key:
            return []

        try:
            url = "https://pixabay.com/api/videos/"
            params = {
                'key': self.pixabay_api_key,
                'q': query,
                'per_page': max_results,
                'video_type': 'all'
            }

            response = requests.get(url, params=params, timeout=10)

            if response.status_code == 200:
                data = response.json()
                results = []

                for video in data.get('hits', []):
                    duration = video.get('duration', 0)

                    # Filter by duration
                    if duration < min_duration or duration > max_duration:
                        continue

                    # Get medium quality video
                    videos = video.get('videos', {})
                    video_url = videos.get('medium', {}).get('url') or videos.get('small', {}).get('url')

                    if not video_url:
                        continue

                    # Build page URL
                    page_url = video.get('pageURL', '')

                    results.append({
                        'url': page_url,
                        'download_url': video_url,
                        'title': video.get('tags', ''),
                        'duration': duration,
                        'width': videos.get('medium', {}).get('width', 0),
                        'height': videos.get('medium', {}).get('height', 0),
                        'source': 'pixabay',
                        'type': 'video'
                    })

                return results[:max_results]

        except Exception as e:
            print(f"  ⚠️  Pixabay search error: {e}")
            return []

    def _search_giphy(
        self,
        query: str,
        max_results: int = 5
    ) -> List[Dict]:
        """Search Giphy API for GIFs."""
        if not self.giphy_api_key:
            return []

        try:
            url = "https://api.giphy.com/v1/gifs/search"
            params = {
                'api_key': self.giphy_api_key,
                'q': query,
                'limit': max_results,
                'rating': 'g'  # Family-friendly content
            }

            response = requests.get(url, params=params, timeout=10)

            if response.status_code == 200:
                data = response.json()
                results = []

                for gif in data.get('data', []):
                    gif_id = gif.get('id')
                    page_url = gif.get('url', f"https://giphy.com/gifs/{gif_id}")

                    # Get original GIF URL
                    images = gif.get('images', {})
                    original = images.get('original', {})
                    gif_url = original.get('url') or original.get('mp4')

                    if not gif_url:
                        continue

                    results.append({
                        'url': page_url,
                        'download_url': gif_url,
                        'title': gif.get('title', ''),
                        'duration': 0,  # GIFs don't have explicit duration
                        'width': int(original.get('width', 0)),
                        'height': int(original.get('height', 0)),
                        'source': 'giphy',
                        'type': 'gif'
                    })

                return results[:max_results]

        except Exception as e:
            print(f"  ⚠️  Giphy search error: {e}")
            return []

    def extract_search_terms(self, description: str, max_terms: int = 3) -> str:
        """
        Extract key search terms from a media description.
        Keeps it simple - just 2-3 core nouns/concepts for better API results.

        Args:
            description: Media description (e.g., "Animated photon traveling through space")
            max_terms: Maximum number of key terms to extract (default 3)

        Returns:
            Space-separated search terms (simplified)
        """
        # Common stop words to remove
        stop_words = {
            'a', 'an', 'the', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
            'of', 'with', 'by', 'from', 'as', 'is', 'was', 'are', 'were', 'be',
            'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will',
            'would', 'should', 'could', 'may', 'might', 'must', 'can', 'that',
            'this', 'these', 'those', 'i', 'you', 'he', 'she', 'it', 'we', 'they',
            'showing', 'demonstrating', 'representing', 'displaying', 'under'
        }

        # Words that add noise - prefer the core concept
        noise_words = {
            'animated', 'animation', 'abstract', 'visual', 'visualization',
            'close', 'closeup', 'view', 'footage', 'video', 'scene'
        }

        # Tokenize and filter
        words = re.findall(r'\b[a-z]+\b', description.lower())

        # Remove stop words and noise words
        keywords = [w for w in words
                   if w not in stop_words
                   and w not in noise_words
                   and len(w) > 3]  # Skip very short words

        # Prioritize scientific/technical terms (longer, more specific)
        # But keep it simple - just pick the most relevant 2-3 terms
        core_terms = keywords[:max_terms]

        return ' '.join(core_terms)

    def validate_url(self, url: str, media_type: str = 'video') -> bool:
        """
        Quickly validate if a URL exists using HEAD request.

        Args:
            url: URL to validate
            media_type: 'video' or 'gif'

        Returns:
            True if URL exists and is accessible
        """
        try:
            # Try to resolve the URL first (handles page URLs)
            resolved_url = self.resolve_url(url, media_type)
            if not resolved_url:
                return False

            # Do a HEAD request to check if resource exists
            response = requests.head(resolved_url, timeout=5, allow_redirects=True)
            return response.status_code == 200

        except Exception:
            return False


if __name__ == "__main__":
    # Test the search functionality
    searcher = MediaSearcher()

    print("Testing Pexels video search...")
    results = searcher.search_videos("photon particle light", source='pexels', max_results=3)
    print(f"Found {len(results)} results")
    for r in results:
        print(f"  - {r['title']}: {r['duration']}s, {r['width']}x{r['height']}")

    print("\nTesting search term extraction...")
    desc = "Animated photon particle traveling through space with glowing energy"
    terms = searcher.extract_search_terms(desc)
    print(f"Description: {desc}")
    print(f"Search terms: {terms}")
