#!/usr/bin/env python3
"""
Stock Photo API Integration
Resolves HTML page URLs to actual download URLs using APIs.
"""

import os
import re
import json
import requests
from pathlib import Path
from urllib.parse import urlparse
from typing import Optional, Tuple, List, Dict


class StockPhotoResolver:
    """Resolves stock photo page URLs to download URLs."""

    def __init__(self, config_path: str = "config/config.json"):
        """Initialize with API keys from config file or environment."""
        # Try to load from config file first
        self.pexels_api_key = ''
        self.unsplash_api_key = ''
        self.pixabay_api_key = ''
        self.giphy_api_key = ''

        if Path(config_path).exists():
            try:
                with open(config_path) as f:
                    config = json.load(f)
                    media_sources = config.get('media_sources', {})
                    self.pexels_api_key = media_sources.get('pexels_api_key', '')
                    self.unsplash_api_key = media_sources.get('unsplash_api_key', '')
                    self.pixabay_api_key = media_sources.get('pixabay_api_key', '')
                    self.giphy_api_key = media_sources.get('giphy_api_key', '')
            except Exception as e:
                print(f"  ⚠️  Warning: Could not load config file: {e}")

        # Fallback to environment variables if not in config
        if not self.pexels_api_key:
            self.pexels_api_key = os.getenv('PEXELS_API_KEY', '')
        if not self.unsplash_api_key:
            self.unsplash_api_key = os.getenv('UNSPLASH_API_KEY', '')
        if not self.pixabay_api_key:
            self.pixabay_api_key = os.getenv('PIXABAY_API_KEY', '')
        if not self.giphy_api_key:
            self.giphy_api_key = os.getenv('GIPHY_API_KEY', '')

    def resolve_url(self, page_url: str, media_type: str) -> Optional[str]:
        """
        Convert HTML page URL to direct download URL.
        Also handles URLs that are already direct download links.

        Args:
            page_url: HTML page URL (e.g. https://www.pexels.com/photo/...)
                     OR direct download URL (e.g. https://images.pexels.com/photos/...)
            media_type: 'image' or 'video'

        Returns:
            Direct download URL or None if resolution failed
        """
        # Check if URL is already a direct media URL (not a page URL)
        if self._is_direct_url(page_url):
            return page_url

        parsed = urlparse(page_url)
        domain = parsed.netloc.lower()

        if 'pexels.com' in domain:
            return self._resolve_pexels(page_url, media_type)
        elif 'unsplash.com' in domain:
            return self._resolve_unsplash(page_url, media_type)
        elif 'pixabay.com' in domain:
            return self._resolve_pixabay(page_url, media_type)
        elif 'giphy.com' in domain:
            return self._resolve_giphy(page_url, media_type)
        else:
            # Unknown source, return as-is and hope it works
            return page_url

    def _is_direct_url(self, url: str) -> bool:
        """Check if URL is already a direct media download link."""
        url_lower = url.lower()

        # Check for direct media file extensions
        if any(url_lower.endswith(ext) for ext in ['.jpg', '.jpeg', '.png', '.gif', '.mp4', '.webp']):
            return True

        # Check for known direct media domains
        direct_domains = [
            'images.pexels.com',
            'videos.pexels.com',
            'cdn.pixabay.com',
            'pixabay.com/get/',
            'media.giphy.com',
            'media0.giphy.com',
            'media1.giphy.com',
            'media2.giphy.com',
            'media3.giphy.com',
            'media4.giphy.com',
        ]

        return any(domain in url_lower for domain in direct_domains)

    def _resolve_pexels(self, page_url: str, media_type: str) -> Optional[str]:
        """Resolve Pexels URL to download link."""
        if not self.pexels_api_key:
            print(f"  ⚠️  No PEXELS_API_KEY set, using alternative method...")
            return self._scrape_pexels(page_url, media_type)

        # Extract ID from URL
        # https://www.pexels.com/photo/green-leaf-plant-86397/
        # https://www.pexels.com/video/green-plants-4508110/
        match = re.search(r'/(?:photo|video)/[^/]+-(\d+)/', page_url)
        if not match:
            return None

        media_id = match.group(1)

        if media_type == 'video':
            return self._get_pexels_video(media_id)
        else:
            return self._get_pexels_photo(media_id)

    def _get_pexels_photo(self, photo_id: str) -> Optional[str]:
        """Get Pexels photo download URL via API."""
        url = f"https://api.pexels.com/v1/photos/{photo_id}"
        headers = {"Authorization": self.pexels_api_key}

        try:
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code == 200:
                data = response.json()
                # Get largest available size
                return data['src']['original']
        except Exception as e:
            print(f"  ⚠️  Pexels API error: {e}")

        return None

    def _get_pexels_video(self, video_id: str) -> Optional[str]:
        """Get Pexels video download URL via API."""
        url = f"https://api.pexels.com/videos/videos/{video_id}"
        headers = {"Authorization": self.pexels_api_key}

        try:
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code == 200:
                data = response.json()
                # Get HD quality if available, otherwise first video file
                video_files = data.get('video_files', [])
                if video_files:
                    # Prefer HD quality
                    hd = [v for v in video_files if v.get('quality') == 'hd']
                    if hd:
                        return hd[0]['link']
                    return video_files[0]['link']
        except Exception as e:
            print(f"  ⚠️  Pexels API error: {e}")

        return None

    def _scrape_pexels(self, page_url: str, media_type: str) -> Optional[str]:
        """Fallback: Try to extract download URL from HTML page."""
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            }
            response = requests.get(page_url, headers=headers, timeout=10)
            if response.status_code == 200:
                html = response.text

                if media_type == 'video':
                    # Try multiple patterns for video URLs
                    patterns = [
                        r'"url":"(https://player\.vimeo\.com/external/[^"]+\.mp4[^"]*)"',
                        r'"file_url":"(https://[^"]+\.mp4[^"]*)"',
                        r'data-video-url="([^"]+)"',
                        r'https://player\.vimeo\.com/external/[^\s"]+\.mp4\?[^\s"]+',
                    ]
                    for pattern in patterns:
                        match = re.search(pattern, html)
                        if match:
                            url = match.group(1) if match.lastindex else match.group(0)
                            url = url.replace('\\/', '/').replace('\\', '')
                            return url
                else:
                    # Try multiple patterns for image URLs
                    patterns = [
                        r'https://images\.pexels\.com/photos/\d+/[^?\s"]+\.jpeg\?auto=compress[^"\s]+',
                        r'"original":"(https://images\.pexels\.com/[^"]+)"',
                        r'srcset="([^"]+)"',
                    ]
                    for pattern in patterns:
                        match = re.search(pattern, html)
                        if match:
                            url = match.group(1) if match.lastindex else match.group(0)
                            url = url.replace('\\/', '/').replace('\\', '')
                            # For srcset, get the largest size (last one)
                            if ' ' in url:
                                parts = url.split(',')
                                if parts:
                                    url = parts[-1].strip().split()[0]
                            return url

        except Exception as e:
            print(f"  ⚠️  Scraping failed: {e}")

        return None

    def _resolve_unsplash(self, page_url: str, media_type: str) -> Optional[str]:
        """Resolve Unsplash URL to download link."""
        # Extract photo ID from URL
        # https://unsplash.com/photos/bright-green-plant-leaves-get-illuminated-by-sunlight-Gon20PpPBws
        match = re.search(r'/photos/[^/]+-([A-Za-z0-9_-]+)$', page_url)
        if not match:
            return None

        photo_id = match.group(1)

        if self.unsplash_api_key:
            url = f"https://api.unsplash.com/photos/{photo_id}"
            headers = {"Authorization": f"Client-ID {self.unsplash_api_key}"}

            try:
                response = requests.get(url, headers=headers, timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    return data['urls']['raw']
            except Exception as e:
                print(f"  ⚠️  Unsplash API error: {e}")

        # Fallback: Scrape the actual download URL from the page
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
            }
            response = requests.get(page_url, headers=headers, timeout=10)
            if response.status_code == 200:
                html = response.text
                # Look for the download link in the HTML
                match = re.search(r'https://images\.unsplash\.com/photo-[^?\s"]+\?[^"\s]+', html)
                if match:
                    return match.group(0)
        except Exception as e:
            print(f"  ⚠️  Unsplash scraping failed: {e}")

        return None

    def _resolve_pixabay(self, page_url: str, media_type: str) -> Optional[str]:
        """Resolve Pixabay URL to download link."""
        # Extract ID from URL
        # https://pixabay.com/videos/air-bubbles-underwater-water-31611/
        match = re.search(r'/(?:photos|videos)/[^/]+-(\d+)/', page_url)
        if not match:
            return None

        media_id = match.group(1)

        # Try API if key is available
        if self.pixabay_api_key:
            if media_type == 'video':
                return self._get_pixabay_video(media_id)
            else:
                return self._get_pixabay_photo(media_id)

        # Fallback to scraping
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
            }
            response = requests.get(page_url, headers=headers, timeout=10)
            if response.status_code == 200:
                html = response.text

                if media_type == 'video':
                    # Look for video source URLs in various formats
                    patterns = [
                        r'"(https://cdn\.pixabay\.com/vimeo/[^"]+/[^"]+\.mp4[^"]*)"',
                        r'src="(https://player\.vimeo\.com/external/[^"]+\.mp4[^"]*)"',
                        r'https://cdn\.pixabay\.com/download/video/[^"\s]+\.mp4',
                    ]
                    for pattern in patterns:
                        match = re.search(pattern, html)
                        if match:
                            url = match.group(1) if match.lastindex else match.group(0)
                            url = url.replace('\\/', '/')
                            return url
                else:
                    # Look for image download links
                    patterns = [
                        r'https://pixabay\.com/get/[^"\s]+\.jpg',
                        r'"(https://cdn\.pixabay\.com/photo/[^"]+\.jpg)"',
                    ]
                    for pattern in patterns:
                        match = re.search(pattern, html)
                        if match:
                            url = match.group(1) if match.lastindex else match.group(0)
                            return url
        except Exception as e:
            print(f"  ⚠️  Pixabay scraping failed: {e}")

        return None

    def _get_pixabay_photo(self, photo_id: str) -> Optional[str]:
        """Get Pixabay photo download URL via API."""
        url = f"https://pixabay.com/api/"
        params = {
            'key': self.pixabay_api_key,
            'id': photo_id
        }

        try:
            response = requests.get(url, params=params, timeout=10)
            if response.status_code == 200:
                data = response.json()
                hits = data.get('hits', [])
                if hits:
                    # Get largest available size
                    return hits[0].get('largeImageURL') or hits[0].get('webformatURL')
        except Exception as e:
            print(f"  ⚠️  Pixabay API error: {e}")

        return None

    def _get_pixabay_video(self, video_id: str) -> Optional[str]:
        """Get Pixabay video download URL via API."""
        url = f"https://pixabay.com/api/videos/"
        params = {
            'key': self.pixabay_api_key,
            'id': video_id
        }

        try:
            response = requests.get(url, params=params, timeout=10)
            if response.status_code == 200:
                data = response.json()
                hits = data.get('hits', [])
                if hits:
                    videos = hits[0].get('videos', {})
                    # Prefer medium quality for reasonable file size
                    if 'medium' in videos:
                        return videos['medium']['url']
                    elif 'large' in videos:
                        return videos['large']['url']
                    elif 'small' in videos:
                        return videos['small']['url']
        except Exception as e:
            print(f"  ⚠️  Pixabay API error: {e}")

        return None

    def _resolve_giphy(self, page_url: str, media_type: str) -> Optional[str]:
        """Resolve Giphy URL to download link."""
        if not self.giphy_api_key:
            print(f"  ⚠️  No GIPHY_API_KEY set")
            return None

        # Extract GIF ID from URL
        # https://giphy.com/gifs/science-chemistry-photosynthesis-abc123
        # https://media.giphy.com/media/abc123/giphy.gif
        match = re.search(r'/gifs/[^/]+-([A-Za-z0-9]+)$', page_url)
        if not match:
            # Try alternate format
            match = re.search(r'/media/([A-Za-z0-9]+)/', page_url)
        if not match:
            return None

        gif_id = match.group(1)

        try:
            url = f"https://api.giphy.com/v1/gifs/{gif_id}"
            params = {'api_key': self.giphy_api_key}
            response = requests.get(url, params=params, timeout=10)

            if response.status_code == 200:
                data = response.json()
                gif_data = data.get('data', {})
                images = gif_data.get('images', {})

                # Get the original or highest quality version
                if 'original' in images:
                    return images['original'].get('url') or images['original'].get('mp4')
                elif 'downsized_large' in images:
                    return images['downsized_large'].get('url')

        except Exception as e:
            print(f"  ⚠️  Giphy API error: {e}")

        return None

    def get_thumbnail_url(self, page_url: str, media_type: str = 'video') -> str:
        """
        Extract thumbnail URL from page URL.

        Args:
            page_url: Webpage URL (e.g., pexels.com/video/...)
            media_type: 'video' or 'image'

        Returns:
            Thumbnail URL or original URL if extraction fails
        """
        # Detect source
        if 'pexels.com' in page_url:
            return self._get_pexels_thumbnail(page_url)
        elif 'pixabay.com' in page_url:
            return self._get_pixabay_thumbnail(page_url)
        elif 'giphy.com' in page_url:
            return self._get_giphy_thumbnail(page_url)
        else:
            return page_url

    def _get_pexels_thumbnail(self, page_url: str) -> str:
        """Extract Pexels thumbnail URL using API."""
        if not self.pexels_api_key:
            return page_url  # Return original URL if no API key

        try:
            # Extract video ID from URL
            match = re.search(r'/(?:photo|video)/[^/]+-(\d+)/', page_url)
            if not match:
                return page_url

            video_id = match.group(1)

            # Call Pexels API to get video metadata
            url = f"https://api.pexels.com/videos/videos/{video_id}"
            headers = {"Authorization": self.pexels_api_key}
            response = requests.get(url, headers=headers, timeout=10)

            if response.status_code == 200:
                data = response.json()
                # Use the 'image' field which contains the thumbnail
                if 'image' in data:
                    return data['image']
                # Fallback to video_pictures if available
                if 'video_pictures' in data and data['video_pictures']:
                    return data['video_pictures'][0].get('picture', page_url)
        except Exception as e:
            # Log error but don't fail - return original URL as fallback
            pass

        return page_url

    def _get_pixabay_thumbnail(self, page_url: str) -> str:
        """Extract Pixabay thumbnail URL."""
        # Pixabay provides preview images
        try:
            # Extract video ID from URL
            video_id = page_url.rstrip('/').split('-')[-1].replace('/', '')
            return f"https://i.vimeocdn.com/video/{video_id}_640x360.jpg"
        except:
            return page_url

    def _get_giphy_thumbnail(self, page_url: str) -> str:
        """Extract Giphy thumbnail URL using API."""
        if not self.giphy_api_key:
            return page_url  # Return original URL if no API key

        try:
            # Extract GIF ID from URL
            # https://giphy.com/gifs/science-chemistry-photosynthesis-abc123
            match = re.search(r'/gifs/[^/]+-([A-Za-z0-9]+)$', page_url)
            if not match:
                # Try alternate format: https://media.giphy.com/media/abc123/
                match = re.search(r'/media/([A-Za-z0-9]+)/', page_url)
            if not match:
                return page_url

            gif_id = match.group(1)

            # Call Giphy API to get GIF metadata
            url = f"https://api.giphy.com/v1/gifs/{gif_id}"
            params = {'api_key': self.giphy_api_key}
            response = requests.get(url, params=params, timeout=10)

            if response.status_code == 200:
                data = response.json()
                # Use 'downsized' version for thumbnails (smaller file, good quality)
                gif_url = (data.get('data', {})
                              .get('images', {})
                              .get('downsized', {})
                              .get('url'))
                if gif_url:
                    return gif_url

                # Fallback to original if downsized not available
                gif_url = (data.get('data', {})
                              .get('images', {})
                              .get('original', {})
                              .get('url'))
                if gif_url:
                    return gif_url
        except Exception as e:
            # Log error but don't fail - return original URL as fallback
            pass

        return page_url

    def enrich_with_thumbnails(self, media_suggestions: List[Dict]) -> List[Dict]:
        """
        Add thumbnail_url field to media suggestions.

        Args:
            media_suggestions: List of media dicts from research

        Returns:
            Enriched media suggestions with thumbnail_url
        """
        for media in media_suggestions:
            media['thumbnail_url'] = self.get_thumbnail_url(
                media['url'],
                media.get('type', 'video')
            )
        return media_suggestions


def test_resolver():
    """Test the resolver with sample URLs."""
    resolver = StockPhotoResolver()

    test_urls = [
        ("https://www.pexels.com/photo/green-leaf-plant-86397/", "image"),
        ("https://www.pexels.com/video/green-plants-4508110/", "video"),
        ("https://unsplash.com/photos/bright-green-plant-leaves-get-illuminated-by-sunlight-Gon20PpPBws", "image"),
    ]

    for url, media_type in test_urls:
        print(f"\nTesting: {url}")
        download_url = resolver.resolve_url(url, media_type)
        if download_url:
            print(f"✅ Resolved to: {download_url[:80]}...")
        else:
            print(f"❌ Failed to resolve")


if __name__ == "__main__":
    test_resolver()
