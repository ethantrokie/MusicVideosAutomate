#!/usr/bin/env python3 -u
"""
Music composition agent using Suno API.
Generates music based on lyrics and style prompt.
"""

import os
import sys
import json
import time
import requests
from pathlib import Path

# Force unbuffered output
sys.stdout = os.fdopen(sys.stdout.fileno(), 'w', buffering=1)
sys.stderr = os.fdopen(sys.stderr.fileno(), 'w', buffering=1)


class SunoAPIClient:
    """Client for Suno API music generation."""

    def __init__(self, api_key: str, base_url: str = "https://api.sunoapi.org"):
        self.api_key = api_key
        self.base_url = base_url
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

    def generate_music(self, lyrics: str, prompt: str, duration: int = 35) -> dict:
        """
        Generate music using Suno API.

        Args:
            lyrics: Song lyrics
            prompt: Style/genre description
            duration: Target duration in seconds

        Returns:
            dict with generation_id and status
        """
        endpoint = f"{self.base_url}/api/v1/generate"

        payload = {
            "lyrics": lyrics,
            "prompt": prompt,
            "duration": duration,
            "make_instrumental": False
        }

        print(f"  Sending request to Suno API...")
        response = requests.post(endpoint, headers=self.headers, json=payload)

        if response.status_code != 200:
            print(f"❌ API Error Response: {response.text}")
            raise Exception(f"Suno API error: {response.status_code} - {response.text}")

        result = response.json()
        print(f"  API Response: {json.dumps(result, indent=2)}")
        return result

    def check_status(self, generation_id: str) -> dict:
        """Check generation status."""
        endpoint = f"{self.base_url}/api/v1/generate/record-info"
        params = {"id": generation_id}
        response = requests.get(endpoint, headers=self.headers, params=params)

        if response.status_code != 200:
            raise Exception(f"Status check error: {response.status_code}")

        return response.json()

    def download_audio(self, audio_url: str, output_path: str):
        """Download generated audio file."""
        response = requests.get(audio_url, stream=True)

        if response.status_code != 200:
            raise Exception(f"Download error: {response.status_code}")

        with open(output_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)

    def wait_for_completion(self, generation_id: str, max_wait: int = 300, poll_interval: int = 5) -> dict:
        """
        Poll for completion with timeout.

        Args:
            generation_id: The generation job ID
            max_wait: Maximum seconds to wait
            poll_interval: Seconds between polls

        Returns:
            Final status dict with audio_url
        """
        elapsed = 0

        while elapsed < max_wait:
            status = self.check_status(generation_id)

            if status.get("status") == "completed":
                return status
            elif status.get("status") == "failed":
                raise Exception(f"Generation failed: {status.get('error')}")

            time.sleep(poll_interval)
            elapsed += poll_interval
            print(f"  Waiting for generation... ({elapsed}s)")

        raise Exception(f"Timeout after {max_wait}s")


def main():
    """Main execution."""
    print("🎼 Composer Agent: Generating music...")

    # Load config
    config_path = Path("config/config.json")
    if not config_path.exists():
        print("❌ Error: config/config.json not found")
        print("Copy config/config.json.template and add your Suno API key")
        sys.exit(1)

    with open(config_path) as f:
        config = json.load(f)

    api_key = config["suno_api"]["api_key"]
    if api_key == "YOUR_SUNO_API_KEY_HERE":
        print("❌ Error: Suno API key not configured")
        print("Edit config/config.json and add your API key from https://sunoapi.org")
        sys.exit(1)

    # Load lyrics data
    lyrics_path = Path("outputs/lyrics.json")
    if not lyrics_path.exists():
        print("❌ Error: outputs/lyrics.json not found")
        print("Run lyrics agent first: ./agents/2_lyrics.sh")
        sys.exit(1)

    with open(lyrics_path) as f:
        lyrics_data = json.load(f)

    # Initialize client
    client = SunoAPIClient(
        api_key=api_key,
        base_url=config["suno_api"]["base_url"]
    )

    # Generate music
    print(f"  Lyrics: {len(lyrics_data['lyrics'])} characters")
    print(f"  Prompt: {lyrics_data['music_prompt']}")

    result = client.generate_music(
        lyrics=lyrics_data['lyrics'],
        prompt=lyrics_data['music_prompt'],
        duration=lyrics_data['estimated_duration_seconds']
    )

    generation_id = result.get("generation_id")
    print(f"  Generation ID: {generation_id}")

    # Wait for completion
    final_status = client.wait_for_completion(generation_id)

    # Download audio
    audio_url = final_status.get("audio_url")
    output_path = "outputs/song.mp3"

    print(f"  Downloading audio...")
    client.download_audio(audio_url, output_path)

    print(f"✅ Music generation complete: {output_path}")

    # Save metadata
    metadata = {
        "generation_id": generation_id,
        "audio_url": audio_url,
        "duration": final_status.get("duration"),
        "created_at": final_status.get("created_at")
    }

    with open("outputs/music_metadata.json", "w") as f:
        json.dump(metadata, f, indent=2)


if __name__ == "__main__":
    main()
