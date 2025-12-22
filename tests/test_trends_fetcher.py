#!/usr/bin/env python3
"""Tests for Google Trends fetcher integration."""

import sys
import json
import tempfile
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent / 'automation'))

from trends_fetcher import (
    get_trending_science_topics,
    format_trends_for_prompt,
    deduplicate_and_sort,
    fetch_related_queries,
    load_cache,
    save_cache,
    CACHE_FILE,
)


class TestDeduplicateAndSort:
    """Tests for deduplicate_and_sort function."""

    def test_deduplicates_by_lowercase(self):
        """Should remove duplicates case-insensitively."""
        queries = [
            {'query': 'Physics', 'score': 100},
            {'query': 'physics', 'score': 80},
            {'query': 'PHYSICS', 'score': 60},
            {'query': 'Chemistry', 'score': 90},
        ]
        result = deduplicate_and_sort(queries, limit=10)

        assert len(result) == 2
        assert result[0] == 'Physics'  # Highest score kept
        assert result[1] == 'Chemistry'

    def test_sorts_by_score_descending(self):
        """Should return queries sorted by score, highest first."""
        queries = [
            {'query': 'low', 'score': 10},
            {'query': 'high', 'score': 100},
            {'query': 'medium', 'score': 50},
        ]
        result = deduplicate_and_sort(queries, limit=10)

        assert result == ['high', 'medium', 'low']

    def test_respects_limit(self):
        """Should return at most 'limit' items."""
        queries = [
            {'query': f'query{i}', 'score': 100-i}
            for i in range(20)
        ]
        result = deduplicate_and_sort(queries, limit=5)

        assert len(result) == 5
        assert result[0] == 'query0'

    def test_handles_empty_list(self):
        """Should return empty list for empty input."""
        result = deduplicate_and_sort([], limit=10)
        assert result == []


class TestFormatTrendsForPrompt:
    """Tests for format_trends_for_prompt function."""

    def test_formats_both_top_and_rising(self):
        """Should format both top and rising queries."""
        trends = {
            'top': ['physics', 'chemistry'],
            'rising': ['quantum mechanics', 'dna']
        }
        result = format_trends_for_prompt(trends)

        assert 'TRENDING SCIENCE TOPICS' in result
        assert 'Popular searches: physics, chemistry' in result
        assert 'Rising searches: quantum mechanics, dna' in result

    def test_handles_empty_top(self):
        """Should handle missing top queries."""
        trends = {
            'top': [],
            'rising': ['quantum mechanics']
        }
        result = format_trends_for_prompt(trends)

        assert 'Rising searches: quantum mechanics' in result
        assert 'Popular searches' not in result

    def test_handles_empty_rising(self):
        """Should handle missing rising queries."""
        trends = {
            'top': ['physics'],
            'rising': []
        }
        result = format_trends_for_prompt(trends)

        assert 'Popular searches: physics' in result
        assert 'Rising searches' not in result

    def test_returns_empty_string_when_no_trends(self):
        """Should return empty string when no trends available."""
        trends = {'top': [], 'rising': []}
        result = format_trends_for_prompt(trends)

        assert result == ""


class TestCaching:
    """Tests for cache load/save functionality."""

    def test_save_and_load_cache(self):
        """Should save and load cache correctly."""
        # Use a temp file for testing
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            temp_path = Path(f.name)

        try:
            # Patch CACHE_FILE to use temp file
            with patch('trends_fetcher.CACHE_FILE', temp_path):
                test_trends = {'top': ['test1'], 'rising': ['test2']}
                save_cache(test_trends, cache_hours=6)

                loaded = load_cache()

                assert loaded == test_trends
        finally:
            temp_path.unlink(missing_ok=True)

    def test_cache_expires(self):
        """Should return None for expired cache."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            temp_path = Path(f.name)

        try:
            # Write expired cache
            expired_cache = {
                'timestamp': (datetime.now() - timedelta(hours=10)).isoformat(),
                'cache_hours': 6,
                'trends': {'top': ['old'], 'rising': []}
            }
            with open(temp_path, 'w') as f:
                json.dump(expired_cache, f)

            with patch('trends_fetcher.CACHE_FILE', temp_path):
                loaded = load_cache()

                assert loaded is None
        finally:
            temp_path.unlink(missing_ok=True)

    def test_load_cache_returns_none_when_no_file(self):
        """Should return None when cache file doesn't exist."""
        with patch('trends_fetcher.CACHE_FILE', Path('/nonexistent/path.json')):
            result = load_cache()
            assert result is None


class TestFetchRelatedQueries:
    """Tests for fetch_related_queries with mocked pytrends."""

    def test_extracts_top_and_rising_queries(self):
        """Should extract both top and rising queries from pytrends response."""
        # Mock pytrends
        mock_pytrends = MagicMock()

        # Create mock DataFrames
        top_df = pd.DataFrame({
            'query': ['quantum physics', 'relativity'],
            'value': [100, 80]
        })
        rising_df = pd.DataFrame({
            'query': ['dark matter', 'string theory'],
            'value': [500, 'Breakout']
        })

        mock_pytrends.related_queries.return_value = {
            'physics': {
                'top': top_df,
                'rising': rising_df
            }
        }

        result = fetch_related_queries(mock_pytrends, ['physics'], category=174)

        assert len(result['top']) == 2
        assert len(result['rising']) == 2
        assert result['top'][0]['query'] == 'quantum physics'
        assert result['rising'][1]['score'] == 1000  # Breakout converted to 1000

    def test_handles_empty_response(self):
        """Should handle empty/None responses from pytrends."""
        mock_pytrends = MagicMock()
        mock_pytrends.related_queries.return_value = {
            'physics': {
                'top': None,
                'rising': pd.DataFrame()
            }
        }

        result = fetch_related_queries(mock_pytrends, ['physics'], category=174)

        assert result['top'] == []
        assert result['rising'] == []

    def test_handles_api_exception(self):
        """Should handle exceptions gracefully."""
        mock_pytrends = MagicMock()
        mock_pytrends.build_payload.side_effect = Exception("API error")

        result = fetch_related_queries(mock_pytrends, ['physics'], category=174)

        assert result == {'top': [], 'rising': []}


class TestGetTrendingScienceTopics:
    """Tests for main get_trending_science_topics function."""

    def test_uses_cache_when_valid(self):
        """Should return cached data when cache is valid."""
        cached_trends = {'top': ['cached1'], 'rising': ['cached2']}

        with patch('trends_fetcher.load_cache', return_value=cached_trends):
            result = get_trending_science_topics()

            assert result == cached_trends

    def test_fetches_fresh_when_no_cache(self):
        """Should fetch fresh data when no cache available."""
        with patch('trends_fetcher.load_cache', return_value=None):
            with patch('trends_fetcher.TrendReq') as mock_trend_req:
                # Setup mock
                mock_instance = MagicMock()
                mock_trend_req.return_value = mock_instance

                top_df = pd.DataFrame({
                    'query': ['fresh topic'],
                    'value': [100]
                })
                mock_instance.related_queries.return_value = {
                    'science explained': {'top': top_df, 'rising': None}
                }

                with patch('trends_fetcher.save_cache'):
                    result = get_trending_science_topics()

                    assert 'top' in result
                    assert 'rising' in result

    def test_returns_empty_on_exception(self):
        """Should return empty trends on exception."""
        with patch('trends_fetcher.load_cache', return_value=None):
            with patch('trends_fetcher.TrendReq', side_effect=Exception("Network error")):
                result = get_trending_science_topics()

                assert result == {'top': [], 'rising': []}

    def test_respects_config_limits(self):
        """Should respect top_queries_count and rising_queries_count from config."""
        config = {
            'trends': {
                'top_queries_count': 2,
                'rising_queries_count': 3,
                'seed_keywords': ['test'],
                'category': 174,
                'cache_duration_hours': 6
            }
        }

        with patch('trends_fetcher.load_cache', return_value=None):
            with patch('trends_fetcher.TrendReq') as mock_trend_req:
                mock_instance = MagicMock()
                mock_trend_req.return_value = mock_instance

                # Return more results than limits
                top_df = pd.DataFrame({
                    'query': [f'top{i}' for i in range(10)],
                    'value': [100-i for i in range(10)]
                })
                rising_df = pd.DataFrame({
                    'query': [f'rising{i}' for i in range(10)],
                    'value': [100-i for i in range(10)]
                })
                mock_instance.related_queries.return_value = {
                    'test': {'top': top_df, 'rising': rising_df}
                }

                with patch('trends_fetcher.save_cache'):
                    result = get_trending_science_topics(config)

                    assert len(result['top']) <= 2
                    assert len(result['rising']) <= 3


class TestIntegrationWithTopicGenerator:
    """Integration tests with topic_generator module."""

    def test_topic_generator_imports_trends_fetcher(self):
        """Should be able to import trends functions in topic_generator."""
        try:
            sys.path.insert(0, str(Path(__file__).parent.parent / 'automation'))
            from topic_generator import main, generate_topic_via_claude
            assert callable(main)
            assert callable(generate_topic_via_claude)
        except ImportError as e:
            assert False, f"Import failed: {e}"


# Run tests if executed directly
if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
