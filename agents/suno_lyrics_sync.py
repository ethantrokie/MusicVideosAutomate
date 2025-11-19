#!/usr/bin/env python3
"""
Suno API integration for fetching word-level lyric timestamps.
"""

import os
import time
import logging
from typing import Optional, Dict
import requests


class SunoLyricsSync:
    """Fetches word-level aligned lyrics from Suno API."""

    API_ENDPOINT = "https://api.sunoapi.org/api/v1/generate/get-timestamped-lyrics"

    def __init__(self, api_key: Optional[str] = None, max_retries: int = 3):
        """
        Initialize Suno API client.

        Args:
            api_key: Suno API key (defaults to config.json or SUNO_API_KEY env var)
            max_retries: Maximum number of retry attempts
        """
        if api_key:
            self.api_key = api_key
        else:
            # Try environment variable first, then config file
            self.api_key = os.getenv("SUNO_API_KEY")
            if not self.api_key:
                try:
                    from pathlib import Path
                    config_path = Path("config/config.json")
                    if config_path.exists():
                        import json
                        with open(config_path) as f:
                            config = json.load(f)
                        self.api_key = config.get("suno_api", {}).get("api_key")
                except Exception:
                    pass

        self.max_retries = max_retries
        self.logger = logging.getLogger(__name__)

    def fetch_aligned_lyrics(self, task_id: str, audio_id: str) -> Dict:
        """
        Fetch word-level timestamps from Suno API.

        Args:
            task_id: Task ID from music generation
            audio_id: Audio ID from music generation

        Returns:
            Dictionary with alignedWords array

        Raises:
            Exception: If all retries fail
        """
        if not self.api_key:
            raise ValueError("SUNO_API_KEY not set")

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "taskId": task_id,
            "audioId": audio_id
        }

        for attempt in range(self.max_retries):
            try:
                response = requests.post(
                    self.API_ENDPOINT,
                    json=payload,
                    headers=headers,
                    timeout=30
                )

                if response.status_code == 200:
                    data = response.json()
                    if data.get("code") == 200:
                        return data.get("data", {})
                    else:
                        self.logger.warning(f"API returned error: {data.get('msg')}")
                else:
                    self.logger.warning(f"HTTP {response.status_code}: {response.text}")

            except Exception as e:
                self.logger.warning(f"Attempt {attempt + 1} failed: {e}")

            if attempt < self.max_retries - 1:
                wait_time = 2 ** attempt  # Exponential backoff
                time.sleep(wait_time)

        raise Exception(f"Failed to fetch aligned lyrics after {self.max_retries} attempts")
