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

# Add agents directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))
from output_helper import get_output_path, ensure_output_dir

# Force unbuffered output
sys.stdout = os.fdopen(sys.stdout.fileno(), 'w', buffering=1)
sys.stderr = os.fdopen(sys.stderr.fileno(), 'w', buffering=1)


class SunoAPIClient:
    """Client for Suno API music generation."""

    def __init__(self, api_key: str, base_url: str = "https://api.sunoapi.org", model: str = "V5"):
        self.api_key = api_key
        self.base_url = base_url
        self.model = model
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

    def generate_music(self, lyrics: str, prompt: str, duration: int = 35) -> dict:
        """
        Generate music using Suno API.

        Args:
            lyrics: Song lyrics (max 5000 chars for V5, 3000 chars for V3.5/V4)
            prompt: Style/genre description (max 1000 chars for V5, 200 chars for V3.5/V4)
            duration: Target duration in seconds (ignored, for backwards compatibility)

        Returns:
            dict with generation_id and status
        """
        endpoint = f"{self.base_url}/api/v1/generate"

        # Validate character limits per model
        # V5: 5000 chars for lyrics (prompt field), 1000 chars for style
        # V3.5/V4: 3000 chars for lyrics, 200 chars for style
        max_prompt_length = 5000 if self.model == "V5" else 3000
        max_style_length = 1000 if self.model == "V5" else 200

        if len(lyrics) > max_prompt_length:
            print(f"⚠️  Warning: Lyrics truncated from {len(lyrics)} to {max_prompt_length} chars")
            lyrics = lyrics[:max_prompt_length]

        if len(prompt) > max_style_length:
            print(f"⚠️  Warning: Style truncated from {len(prompt)} to {max_style_length} chars")
            prompt = prompt[:max_style_length]

        payload = {
            "customMode": True,
            "instrumental": False,
            "prompt": lyrics,  # Lyrics go in prompt field
            "style": prompt,   # Music style/genre description
            "title": "Educational Song",
            "model": self.model,
            "callBackUrl": "https://example.com/webhook"  # Placeholder URL for polling
        }

        print(f"  Sending request to Suno API...")
        response = requests.post(endpoint, headers=self.headers, json=payload)

        if response.status_code != 200:
            print(f"❌ API Error Response: {response.text}")
            raise Exception(f"Suno API error: {response.status_code} - {response.text}")

        result = response.json()
        print(f"  API Response: {json.dumps(result, indent=2)}")

        # Extract taskId from response
        if result.get("code") == 200 and result.get("data"):
            result["generation_id"] = result["data"].get("taskId")

        return result

    def check_status(self, task_id: str) -> dict:
        """Check generation status using taskId."""
        endpoint = f"{self.base_url}/api/v1/generate/record-info"
        params = {"taskId": task_id}
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

    def wait_for_completion(self, task_id: str, max_wait: int = 300, poll_interval: int = 5) -> dict:
        """
        Poll for completion with timeout.

        Args:
            task_id: The task ID from Suno API
            max_wait: Maximum seconds to wait
            poll_interval: Seconds between polls

        Returns:
            Final status dict with audio data
        """
        elapsed = 0

        while elapsed < max_wait:
            result = self.check_status(task_id)

            # DEBUG: Print what we're actually getting from status check
            if elapsed % 30 == 0:  # Print every 30 seconds to avoid spam
                print(f"  [DEBUG] Status check response: {json.dumps(result, indent=2)}")

            if result.get("code") == 200 and result.get("data"):
                status = result["data"].get("status")
                print(f"  Status: {status}")

                if status == "SUCCESS":
                    return result
                elif status == "FAILED":
                    raise Exception(f"Generation failed")

            time.sleep(poll_interval)
            elapsed += poll_interval
            print(f"  Waiting for generation... ({elapsed}s)")

        # DEBUG: Show final response before timeout
        print(f"  [DEBUG] Final status before timeout: {json.dumps(result, indent=2)}")
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
    lyrics_path = get_output_path("lyrics.json")
    if not lyrics_path.exists():
        print(f"❌ Error: {lyrics_path} not found")
        print("Run lyrics agent first: ./agents/2_lyrics.sh")
        sys.exit(1)

    with open(lyrics_path) as f:
        lyrics_data = json.load(f)

    # Initialize client
    client = SunoAPIClient(
        api_key=api_key,
        base_url=config["suno_api"]["base_url"],
        model=config["suno_api"].get("model", "V5")
    )

    # Generate music
    print(f"  Lyrics: {len(lyrics_data['lyrics'])} characters")
    print(f"  Prompt: {lyrics_data['music_prompt']}")

    result = client.generate_music(
        lyrics=lyrics_data['lyrics'],
        prompt=lyrics_data['music_prompt'],
        duration=lyrics_data['estimated_duration_seconds']
    )

    task_id = result.get("generation_id")
    print(f"  Task ID: {task_id}")

    if not task_id:
        print("❌ Error: No task ID returned from API")
        sys.exit(1)

    # Wait for completion
    final_result = client.wait_for_completion(task_id)

    # Extract audio data from response - correct path is data.response.sunoData
    audio_data = final_result.get("data", {}).get("response", {}).get("sunoData", [])
    if not audio_data:
        print("❌ Error: No audio data in response")
        sys.exit(1)

    # Get first audio file (API may return multiple variations)
    first_audio = audio_data[0]
    audio_url = first_audio.get("audioUrl")  # camelCase, not snake_case

    # Ensure output directory exists
    ensure_output_dir()
    output_path = str(get_output_path("song.mp3"))

    print(f"  Downloading audio from: {audio_url}")
    client.download_audio(audio_url, output_path)

    # Trim audio to target duration (video duration + 5s outro for fade)
    target_duration = config.get("video_settings", {}).get("duration", 60) + 5
    print(f"  Trimming audio to {target_duration} seconds...")

    # Use ffmpeg directly (Python 3.13 compatible)
    try:
        import subprocess
        temp_output = output_path + ".trimmed.mp3"

        # Use ffmpeg to trim audio
        result = subprocess.run([
            'ffmpeg', '-i', output_path,
            '-t', str(target_duration),
            '-c', 'copy',  # Copy codec for faster processing
            '-y',  # Overwrite output file
            temp_output
        ], capture_output=True, text=True, timeout=30)

        if result.returncode == 0:
            # Get original duration
            probe_result = subprocess.run([
                'ffprobe', '-v', 'error',
                '-show_entries', 'format=duration',
                '-of', 'default=noprint_wrappers=1:nokey=1',
                output_path
            ], capture_output=True, text=True)

            original_duration = float(probe_result.stdout.strip()) if probe_result.returncode == 0 else 0

            # Replace original with trimmed
            import shutil
            shutil.move(temp_output, output_path)
            print(f"  ✓ Trimmed from {original_duration:.1f}s to {target_duration}s")
        else:
            print(f"  ⚠️  ffmpeg trim failed: {result.stderr[:100]}")
    except FileNotFoundError:
        print(f"  ⚠️  ffmpeg not available, skipping trim (song will be full length)")
    except Exception as e:
        print(f"  ⚠️  Could not trim audio: {e}")

    print(f"✅ Music generation complete: {output_path}")

    # Save metadata
    metadata = {
        "task_id": task_id,
        "audio_id": first_audio.get("id"),
        "audio_url": audio_url,
        "source_audio_url": first_audio.get("sourceAudioUrl"),
        "title": first_audio.get("title"),
        "tags": first_audio.get("tags"),
        "duration": first_audio.get("duration"),
        "model": first_audio.get("modelName")
    }

    metadata_path = get_output_path("music_metadata.json")
    with open(metadata_path, "w") as f:
        json.dump(metadata, f, indent=2)

    # Save Suno output with word-level timestamps for subtitle generation and segment analysis
    suno_output_path = get_output_path("suno_output.json")

    # Extract the full response data with all timestamps
    suno_data = {
        'taskId': task_id,
        'song': first_audio,  # Contains all metadata including potential timestamps
        'metadata': {
            'duration': first_audio.get('duration'),
            'title': first_audio.get('title', 'Educational Song'),
            'model': first_audio.get('modelName', 'chirp-crow')
        }
    }

    # Check if word-level timestamps exist in response
    # Suno API v5 might have different structure - save whatever timestamp data is available
    if 'segments' in first_audio:
        suno_data['segments'] = first_audio.get('segments', [])
    if 'words' in first_audio:
        suno_data['words'] = first_audio.get('words', [])

    with open(suno_output_path, 'w') as f:
        json.dump(suno_data, f, indent=2)

    print(f"✅ Saved Suno output: {suno_output_path}")


if __name__ == "__main__":
    main()
