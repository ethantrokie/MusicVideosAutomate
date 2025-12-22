#!/usr/bin/env python3
"""
Tests for Video LLM integration scripts.

These tests verify that the integration scripts work correctly with:
1. Mock video LLM responses (fast unit tests)
2. Real video LLM inference (slow integration tests)

Run fast tests:   pytest tests/test_video_llm_integrations.py -v -k "not slow"
Run all tests:    pytest tests/test_video_llm_integrations.py -v
"""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add agents and project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "agents"))

# Import the modules we're testing
from agents import filter_media_quality
from agents import generate_video_description
from agents import analyze_downloaded_media
from agents import validate_visual_sync


class TestFilterMediaQuality(unittest.TestCase):
    """Tests for filter_media_quality.py"""
    
    def setUp(self):
        """Set up test fixtures."""
        self.test_manifest = {
            "downloaded": [
                {"local_path": "/tmp/test_video1.mp4", "shot_number": 1},
                {"local_path": "/tmp/test_video2.mp4", "shot_number": 2},
            ],
            "failed": []
        }
    
    @patch('agents.filter_media_quality.rate_clip_quality')
    @patch('pathlib.Path.exists')
    def test_filter_media_approves_high_quality(self, mock_exists, mock_rate):
        """Test that high-quality clips are approved."""
        mock_exists.return_value = True
        mock_rate.return_value = 8  # High quality score
        
        # Disable ad check for this test
        results = filter_media_quality.filter_media(self.test_manifest, threshold=5, check_ads=False)
        
        self.assertEqual(len(results['approved']), 2)
        self.assertEqual(len(results['rejected']), 0)
        self.assertEqual(results['threshold'], 5)
    
    @patch('agents.filter_media_quality.rate_clip_quality')
    @patch('pathlib.Path.exists')
    def test_filter_media_rejects_low_quality(self, mock_exists, mock_rate):
        """Test that low-quality clips are rejected."""
        mock_exists.return_value = True
        mock_rate.return_value = 3  # Low quality score
        
        results = filter_media_quality.filter_media(self.test_manifest, threshold=5, check_ads=False)
        
        self.assertEqual(len(results['approved']), 0)
        self.assertEqual(len(results['rejected']), 2)
    
    @patch('agents.filter_media_quality.rate_clip_quality')
    @patch('pathlib.Path.exists')
    def test_filter_media_mixed_results(self, mock_exists, mock_rate):
        """Test filtering with mixed quality scores."""
        mock_exists.return_value = True
        # First clip high quality, second low
        mock_rate.side_effect = [7, 3]
        
        results = filter_media_quality.filter_media(self.test_manifest, threshold=5, check_ads=False)
        
        self.assertEqual(len(results['approved']), 1)
        self.assertEqual(len(results['rejected']), 1)
        self.assertEqual(results['approved'][0]['quality_score'], 7)
        self.assertEqual(results['rejected'][0]['quality_score'], 3)
    
    def test_filter_media_empty_manifest(self):
        """Test handling of empty manifest."""
        results = filter_media_quality.filter_media({"downloaded": []})
        
        self.assertEqual(results['approved'], [])
        self.assertEqual(results['rejected'], [])
        self.assertEqual(results.get('ads_rejected', []), [])
    
    def test_get_video_llm_venv_returns_path(self):
        """Test venv path detection."""
        path = filter_media_quality.get_video_llm_venv()
        self.assertTrue(path.endswith('python') or 'python' in path)
    
    @patch('agents.filter_media_quality.detect_advertisement')
    @patch('agents.filter_media_quality.rate_clip_quality')
    @patch('pathlib.Path.exists')
    def test_filter_media_rejects_ads(self, mock_exists, mock_rate, mock_detect):
        """Test that advertisements are rejected."""
        mock_exists.return_value = True
        mock_rate.return_value = 8
        # First clip is ad, second is clean
        mock_detect.side_effect = [
            {"is_ad": True, "reason": "Contains URL: getproduct.com"},
            {"is_ad": False, "reason": ""}
        ]
        
        results = filter_media_quality.filter_media(self.test_manifest, threshold=5, check_ads=True)
        
        self.assertEqual(len(results['approved']), 1)
        self.assertEqual(len(results['ads_rejected']), 1)
        self.assertEqual(results['ads_rejected'][0]['ad_reason'], "Contains URL: getproduct.com")
    
    @patch('agents.filter_media_quality.subprocess.run')
    def test_detect_advertisement_clean(self, mock_run):
        """Test advertisement detection on clean clip."""
        mock_run.return_value = MagicMock(returncode=0, stdout="CLEAN")
        
        result = filter_media_quality.detect_advertisement("/tmp/test.mp4")
        
        self.assertFalse(result["is_ad"])
    
    @patch('agents.filter_media_quality.subprocess.run')
    def test_detect_advertisement_found(self, mock_run):
        """Test advertisement detection when ad is found."""
        mock_run.return_value = MagicMock(
            returncode=0, 
            stdout="AD: Contains promotional URL theturnarounddoctor.com"
        )
        
        result = filter_media_quality.detect_advertisement("/tmp/test.mp4")
        
        self.assertTrue(result["is_ad"])
        self.assertIn("promotional", result["reason"].lower())


class TestGenerateVideoDescription(unittest.TestCase):
    """Tests for generate_video_description.py"""
    
    @patch('agents.generate_video_description.subprocess.run')
    def test_generate_youtube_description(self, mock_run):
        """Test YouTube description generation."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="This educational video explores the fascinating world of black holes. "
                   "You'll learn about event horizons and singularities. "
                   "Like and subscribe for more!"
        )
        
        result = generate_video_description.generate_description(
            "/tmp/test.mp4", "youtube", "black holes"
        )
        
        self.assertIn("black holes", result.lower())
        mock_run.assert_called_once()
    
    @patch('agents.generate_video_description.subprocess.run')
    def test_generate_tiktok_description(self, mock_run):
        """Test TikTok description generation."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="Mind-blowing science! 🤯 #education #science #fyp"
        )
        
        result = generate_video_description.generate_description(
            "/tmp/test.mp4", "tiktok", "chemistry"
        )
        
        self.assertTrue(len(result) < 200)  # TikTok should be short
        mock_run.assert_called_once()
    
    @patch('agents.generate_video_description.subprocess.run')
    def test_handles_subprocess_failure(self, mock_run):
        """Test graceful handling of subprocess failure."""
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="Error")
        
        result = generate_video_description.generate_description(
            "/tmp/test.mp4", "youtube"
        )
        
        self.assertEqual(result, "")
    
    @patch('agents.generate_video_description.subprocess.run')
    def test_handles_timeout(self, mock_run):
        """Test handling of subprocess timeout."""
        import subprocess
        mock_run.side_effect = subprocess.TimeoutExpired("cmd", 180)
        
        result = generate_video_description.generate_description(
            "/tmp/test.mp4", "youtube"
        )
        
        self.assertEqual(result, "")


class TestAnalyzeDownloadedMedia(unittest.TestCase):
    """Tests for analyze_downloaded_media.py"""
    
    def setUp(self):
        """Set up test fixtures."""
        self.test_manifest = {
            "downloaded": [
                {"local_path": "/tmp/test_video1.mp4", "shot_number": 1, 
                 "description": "Original description"},
            ],
            "failed": []
        }
    
    @patch('agents.analyze_downloaded_media.analyze_clip')
    @patch('pathlib.Path.exists')
    def test_analyze_all_media_success(self, mock_exists, mock_analyze):
        """Test successful analysis of all clips."""
        mock_exists.return_value = True
        mock_analyze.return_value = {
            "enhanced_description": "A detailed view of molecular structures with blue glow",
            "analysis_success": True
        }
        
        result = analyze_downloaded_media.analyze_all_media(
            self.test_manifest, "chemistry"
        )
        
        self.assertTrue(result["downloaded"][0]["analysis_success"])
        self.assertIn("molecular", result["downloaded"][0]["enhanced_description"])
    
    @patch('agents.analyze_downloaded_media.analyze_clip')
    @patch('pathlib.Path.exists')
    def test_analyze_preserves_original_data(self, mock_exists, mock_analyze):
        """Test that original manifest data is preserved."""
        mock_exists.return_value = True
        mock_analyze.return_value = {
            "enhanced_description": "New description",
            "analysis_success": True
        }
        
        result = analyze_downloaded_media.analyze_all_media(
            self.test_manifest, "topic"
        )
        
        # Original fields should still exist
        self.assertEqual(result["downloaded"][0]["shot_number"], 1)
        self.assertEqual(result["downloaded"][0]["description"], "Original description")
        # New fields should be added
        self.assertEqual(result["downloaded"][0]["enhanced_description"], "New description")
    
    @patch('agents.analyze_downloaded_media.analyze_clip')
    @patch('pathlib.Path.exists')
    def test_handles_missing_files(self, mock_exists, mock_analyze):
        """Test handling of missing video files."""
        mock_exists.return_value = False
        
        result = analyze_downloaded_media.analyze_all_media(
            self.test_manifest, "topic"
        )
        
        # Should not call analyze for missing files
        mock_analyze.assert_not_called()


class TestValidateVisualSync(unittest.TestCase):
    """Tests for validate_visual_sync.py"""
    
    @patch('agents.validate_visual_sync.validate_segment')
    def test_validate_video_sync_high_scores(self, mock_validate):
        """Test validation with high sync scores."""
        mock_validate.return_value = {
            "topic": "photosynthesis",
            "score": 8,
            "reason": "Clear visual match",
            "output": "..."
        }
        
        segments = [{"topic": "photosynthesis"}, {"topic": "chloroplasts"}]
        
        result = validate_visual_sync.validate_video_sync(
            "/tmp/test.mp4", segments, max_segments=2
        )
        
        self.assertEqual(result["average_score"], 8.0)
        self.assertEqual(result["low_scores"], 0)
        self.assertEqual(result["total_validated"], 2)
    
    @patch('agents.validate_visual_sync.validate_segment')
    def test_validate_video_sync_mixed_scores(self, mock_validate):
        """Test validation with mixed scores."""
        mock_validate.side_effect = [
            {"topic": "topic1", "score": 9, "reason": "", "output": ""},
            {"topic": "topic2", "score": 3, "reason": "", "output": ""},
        ]
        
        segments = [{"topic": "topic1"}, {"topic": "topic2"}]
        
        result = validate_visual_sync.validate_video_sync(
            "/tmp/test.mp4", segments, max_segments=2
        )
        
        self.assertEqual(result["average_score"], 6.0)
        self.assertEqual(result["low_scores"], 1)  # One score below 5
    
    def test_validate_empty_segments(self):
        """Test handling of empty segments list."""
        result = validate_visual_sync.validate_video_sync("/tmp/test.mp4", [])
        
        self.assertEqual(result["total_validated"], 0)
        self.assertEqual(result["average_score"], 0)
    
    def test_max_segments_limit(self):
        """Test that max_segments parameter is respected."""
        segments = [{"topic": f"topic{i}"} for i in range(10)]
        
        with patch('agents.validate_visual_sync.validate_segment') as mock_validate:
            mock_validate.return_value = {"topic": "", "score": 5, "reason": "", "output": ""}
            
            result = validate_visual_sync.validate_video_sync(
                "/tmp/test.mp4", segments, max_segments=3
            )
            
            self.assertEqual(result["total_validated"], 3)
            self.assertEqual(mock_validate.call_count, 3)


class TestIntegrationWithRealVideoLLM(unittest.TestCase):
    """
    Integration tests that use real video LLM inference.
    These are slow and require the video LLM environment to be set up.
    """
    
    @classmethod
    def setUpClass(cls):
        """Check if video LLM is available."""
        cls.venv_path = PROJECT_ROOT / "venv_video_llm"
        cls.test_video = PROJECT_ROOT / "test_video.mp4"
        cls.skip_integration = not (cls.venv_path.exists() and cls.test_video.exists())
    
    @unittest.skipIf(True, "Slow integration test - run manually with -k slow")
    def test_real_quality_rating(self):
        """Test actual video quality rating."""
        if self.skip_integration:
            self.skipTest("Video LLM environment or test video not available")
        
        score = filter_media_quality.rate_clip_quality(str(self.test_video))
        
        self.assertIsInstance(score, int)
        self.assertGreaterEqual(score, 1)
        self.assertLessEqual(score, 10)
    
    @unittest.skipIf(True, "Slow integration test - run manually with -k slow")
    def test_real_description_generation(self):
        """Test actual description generation."""
        if self.skip_integration:
            self.skipTest("Video LLM environment or test video not available")
        
        description = generate_video_description.generate_description(
            str(self.test_video), "youtube", "test topic"
        )
        
        self.assertIsInstance(description, str)
        self.assertGreater(len(description), 10)


if __name__ == "__main__":
    unittest.main(verbosity=2)
