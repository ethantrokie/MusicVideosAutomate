#!/usr/bin/env python3
"""
Kling AI API client for video generation and lip-sync.
Uses fal.ai as the API provider for pay-as-you-go pricing.

Pricing:
- Avatar v2 Pro (image+audio to lip-synced video): ~$0.115/second
- Total for 5s clip: ~$0.575
"""

import os
import time
import requests
from typing import Dict

import fal_client


class KlingAPIClient:
    """Client for Kling AI video generation via fal.ai."""

    BALANCE_EXHAUSTED_KEYWORDS = ["exhausted balance", "user is locked", "insufficient"]

    def __init__(self, api_key: str):
        """
        Initialize client with fal.ai API key.

        Args:
            api_key: fal.ai API key
        """
        self.api_key = api_key
        os.environ["FAL_KEY"] = api_key
        self.balance_exhausted = False

        # Transient errors for retry logic (matches SunoAPIClient pattern)
        self.transient_errors = {502, 503, 504, 429, 408, 520, 521, 522, 523, 524, 525, 526}
        self.max_retries = 5

    def _is_balance_error(self, error_msg: str) -> bool:
        """Check if an error message indicates exhausted balance."""
        error_lower = error_msg.lower()
        return any(kw in error_lower for kw in self.BALANCE_EXHAUSTED_KEYWORDS)

    def check_balance(self) -> dict:
        """
        Check fal.ai account balance using the usage API.
        Returns dict with 'ok' bool and 'message' string.
        Since fal.ai has no direct balance endpoint, this makes a lightweight
        usage query to verify the account isn't locked.
        """
        try:
            response = requests.get(
                "https://api.fal.ai/v1/models/usage",
                headers={"Authorization": f"Key {self.api_key}"},
                params={"limit": 1},
                timeout=10
            )
            if response.status_code == 200:
                return {"ok": True, "message": "fal.ai account accessible"}
            elif response.status_code == 401:
                return {"ok": False, "message": "fal.ai API key invalid or account locked"}
            elif response.status_code == 403:
                # 403 from usage API just means the key lacks Admin scope -
                # regular API keys can still generate videos fine
                return {"ok": True, "message": "fal.ai usage API requires admin key (non-fatal), proceeding"}
            else:
                # Non-fatal - can't determine balance, proceed cautiously
                return {"ok": True, "message": f"fal.ai usage check returned {response.status_code}, proceeding"}
        except Exception as e:
            # Non-fatal - can't reach API, proceed cautiously
            return {"ok": True, "message": f"fal.ai usage check failed ({e}), proceeding"}

    def generate_avatar_video(
        self,
        image_url: str,
        audio_url: str,
        prompt: str = "."
    ) -> Dict:
        """
        Generate lip-synced video from image + audio using Kling Avatar v2 Pro.
        Single-step: takes a performer image and audio, outputs video with
        proper lip-sync generated from scratch.

        Args:
            image_url: URL of performer image (face should be 60-70% of frame)
            audio_url: URL of audio segment to lip-sync to
            prompt: Optional text guidance for the scene

        Returns:
            Dict with video_url, status
        """
        for attempt in range(self.max_retries):
            try:
                print(f"    Calling Kling Avatar v2 Pro (attempt {attempt + 1}/{self.max_retries})...")

                result = fal_client.subscribe(
                    "fal-ai/kling-video/ai-avatar/v2/pro",
                    arguments={
                        "image_url": image_url,
                        "audio_url": audio_url,
                        "prompt": prompt
                    }
                )

                return {
                    "video_url": result["video"]["url"],
                    "status": "success"
                }

            except Exception as e:
                error_msg = str(e)
                # Don't retry balance errors - they won't resolve on their own
                if self._is_balance_error(error_msg):
                    self.balance_exhausted = True
                    raise Exception(f"fal.ai balance exhausted: {error_msg}")
                if attempt < self.max_retries - 1:
                    wait_time = (2 ** attempt) * 2
                    print(f"    ⚠️ Avatar generation error: {error_msg}")
                    print(f"    Retrying in {wait_time}s...")
                    time.sleep(wait_time)
                    continue
                raise Exception(f"Avatar video generation failed after {self.max_retries} retries: {error_msg}")

    def upload_file(self, local_path: str) -> str:
        """
        Upload local file to fal.ai and return URL.

        Args:
            local_path: Path to local file

        Returns:
            URL of uploaded file
        """
        return fal_client.upload_file(local_path)

    def download_video(self, video_url: str, output_path: str) -> bool:
        """
        Download video from URL to local path.

        Args:
            video_url: URL of video to download
            output_path: Local path to save video

        Returns:
            True if successful, False otherwise
        """
        try:
            response = requests.get(video_url, stream=True, timeout=120)
            if response.status_code != 200:
                raise Exception(f"Download error: {response.status_code}")

            with open(output_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            return True

        except Exception as e:
            print(f"    ❌ Download failed: {e}")
            return False
