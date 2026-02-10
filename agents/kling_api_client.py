#!/usr/bin/env python3
"""
Kling AI API client for video generation and lip-sync.
Uses fal.ai as the API provider for pay-as-you-go pricing.

Pricing (identical to direct Kling API):
- Video generation: $0.07/second (Kling 2.6 Pro)
- Lip-sync: $0.014/second (rounded to 5s increments)
- Total for 8s clip with lip-sync: ~$0.70
"""

import os
import time
import requests
from typing import Dict

import fal_client


class KlingAPIClient:
    """Client for Kling AI video generation via fal.ai."""

    def __init__(self, api_key: str):
        """
        Initialize client with fal.ai API key.

        Args:
            api_key: fal.ai API key
        """
        self.api_key = api_key
        os.environ["FAL_KEY"] = api_key

        # Transient errors for retry logic (matches SunoAPIClient pattern)
        self.transient_errors = {502, 503, 504, 429, 408, 520, 521, 522, 523, 524, 525, 526}
        self.max_retries = 5

    def generate_video(
        self,
        image_url: str,
        prompt: str,
        duration: int = 8,
        aspect_ratio: str = "16:9"
    ) -> Dict:
        """
        Generate video from image using Kling 2.6 Pro.

        Args:
            image_url: URL of reference image (performer)
            prompt: Environment/scene description
            duration: Video duration in seconds (max 10 for v2.6)
            aspect_ratio: "16:9" for landscape, "9:16" for portrait

        Returns:
            Dict with video_url, duration, status
        """
        for attempt in range(self.max_retries):
            try:
                print(f"    Calling Kling API (attempt {attempt + 1}/{self.max_retries})...")

                result = fal_client.subscribe(
                    "fal-ai/kling-video/v2.6/pro/image-to-video",
                    arguments={
                        "start_image_url": image_url,
                        "prompt": prompt,
                        "duration": str(min(duration, 10)),
                        "aspect_ratio": aspect_ratio,
                        "negative_prompt": "blur, distort, low quality, static face, frozen expression"
                    }
                )

                return {
                    "video_url": result["video"]["url"],
                    "duration": duration,
                    "status": "success"
                }

            except Exception as e:
                error_msg = str(e)
                if attempt < self.max_retries - 1:
                    wait_time = (2 ** attempt) * 2
                    print(f"    ⚠️ Generation error: {error_msg}")
                    print(f"    Retrying in {wait_time}s...")
                    time.sleep(wait_time)
                    continue
                raise Exception(f"Video generation failed after {self.max_retries} retries: {error_msg}")

    def apply_lipsync(
        self,
        video_url: str,
        audio_url: str
    ) -> Dict:
        """
        Apply lip-sync to video using audio.

        Args:
            video_url: URL of generated video
            audio_url: URL of audio segment for lip-sync

        Returns:
            Dict with video_url and status
        """
        for attempt in range(self.max_retries):
            try:
                print(f"    Applying lip-sync (attempt {attempt + 1}/{self.max_retries})...")

                result = fal_client.subscribe(
                    "fal-ai/kling-video/lipsync/audio-to-video",
                    arguments={
                        "video_url": video_url,
                        "audio_url": audio_url
                    }
                )

                return {
                    "video_url": result["video"]["url"],
                    "status": "success"
                }

            except Exception as e:
                error_msg = str(e)
                if attempt < self.max_retries - 1:
                    wait_time = (2 ** attempt) * 2
                    print(f"    ⚠️ LipSync error: {error_msg}")
                    print(f"    Retrying in {wait_time}s...")
                    time.sleep(wait_time)
                    continue

                # Return original video without lip-sync on final failure
                print(f"    ⚠️ LipSync failed after {self.max_retries} retries, using base video")
                return {
                    "video_url": video_url,
                    "status": "lipsync_failed"
                }

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
