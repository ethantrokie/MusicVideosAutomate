#!/usr/bin/env python3
"""Tests for Kling API client."""

import pytest
import os
import sys
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'agents'))


class TestKlingAPIClient:
    """Test Kling API client initialization and methods."""

    def test_client_initialization(self):
        """Test client initializes with API key."""
        from kling_api_client import KlingAPIClient

        client = KlingAPIClient("test_api_key")

        assert client.api_key == "test_api_key"
        assert client.max_retries == 5
        assert os.environ.get("FAL_KEY") == "test_api_key"

    def test_transient_errors_defined(self):
        """Test transient error codes are defined for retry logic."""
        from kling_api_client import KlingAPIClient

        client = KlingAPIClient("test_key")

        assert 502 in client.transient_errors
        assert 503 in client.transient_errors
        assert 429 in client.transient_errors

    @patch('kling_api_client.fal_client')
    def test_generate_video_success(self, mock_fal):
        """Test successful video generation."""
        from kling_api_client import KlingAPIClient

        mock_fal.subscribe.return_value = {
            "video": {"url": "https://example.com/video.mp4"}
        }

        client = KlingAPIClient("test_key")
        result = client.generate_video(
            image_url="https://example.com/image.png",
            prompt="Test environment",
            duration=8
        )

        assert result["status"] == "success"
        assert result["video_url"] == "https://example.com/video.mp4"

    @patch('kling_api_client.fal_client')
    def test_apply_lipsync_success(self, mock_fal):
        """Test successful lip-sync application."""
        from kling_api_client import KlingAPIClient

        mock_fal.subscribe.return_value = {
            "video": {"url": "https://example.com/synced.mp4"}
        }

        client = KlingAPIClient("test_key")
        result = client.apply_lipsync(
            video_url="https://example.com/video.mp4",
            audio_url="https://example.com/audio.mp3"
        )

        assert result["status"] == "success"
        assert result["video_url"] == "https://example.com/synced.mp4"

    @patch('kling_api_client.fal_client')
    def test_apply_lipsync_failure_returns_original(self, mock_fal):
        """Test lip-sync failure returns original video."""
        from kling_api_client import KlingAPIClient

        mock_fal.subscribe.side_effect = Exception("API Error")

        client = KlingAPIClient("test_key")
        client.max_retries = 1  # Speed up test

        result = client.apply_lipsync(
            video_url="https://example.com/video.mp4",
            audio_url="https://example.com/audio.mp3"
        )

        assert result["status"] == "lipsync_failed"
        assert result["video_url"] == "https://example.com/video.mp4"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
