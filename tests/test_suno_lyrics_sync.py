import pytest
from unittest.mock import Mock, patch
from agents.suno_lyrics_sync import SunoLyricsSync


def test_fetch_aligned_lyrics_success():
    """Test successful fetch of aligned lyrics."""
    sync = SunoLyricsSync(api_key="test_key")

    with patch('requests.post') as mock_post:
        mock_post.return_value = Mock(
            status_code=200,
            json=lambda: {
                "code": 200,
                "data": {
                    "alignedWords": [
                        {"word": "Test", "startS": 0.5, "endS": 0.8, "success": True}
                    ]
                }
            }
        )

        result = sync.fetch_aligned_lyrics("task123", "audio456")

        assert "alignedWords" in result
        assert len(result["alignedWords"]) == 1
        assert result["alignedWords"][0]["word"] == "Test"


def test_fetch_aligned_lyrics_retry_on_failure():
    """Test retry logic on API failure."""
    sync = SunoLyricsSync(api_key="test_key", max_retries=2)

    with patch('requests.post') as mock_post:
        mock_post.side_effect = [
            Mock(status_code=500),
            Mock(status_code=200, json=lambda: {"code": 200, "data": {"alignedWords": []}})
        ]

        result = sync.fetch_aligned_lyrics("task123", "audio456")

        assert mock_post.call_count == 2
        assert "alignedWords" in result
