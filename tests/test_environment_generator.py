#!/usr/bin/env python3
"""Tests for environment prompt generation."""

import pytest
import os
import sys
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'agents'))


class TestEnvironmentGenerator:
    """Test environment prompt generation."""

    def test_generate_fallback_prompt(self):
        """Test fallback prompt when Claude fails."""
        from environment_generator import generate_fallback_prompt

        prompt = generate_fallback_prompt("sonar technology", "intro")

        assert len(prompt) > 20
        assert "lighting" in prompt.lower() or "ocean" in prompt.lower()

    def test_detect_voice_gender_male(self):
        """Test male voice detection from tags."""
        from environment_generator import detect_voice_gender

        suno_data = {
            "song": {"tags": "upbeat pop rock, male vocals, energetic"}
        }

        gender = detect_voice_gender(suno_data)

        assert gender == "male"

    def test_detect_voice_gender_female(self):
        """Test female voice detection from tags."""
        from environment_generator import detect_voice_gender

        suno_data = {
            "song": {"tags": "soft ballad, female vocals, emotional"}
        }

        gender = detect_voice_gender(suno_data)

        assert gender == "female"

    def test_detect_voice_gender_default(self):
        """Test default gender when not specified."""
        from environment_generator import detect_voice_gender

        suno_data = {"song": {"tags": "instrumental"}}

        gender = detect_voice_gender(suno_data)

        assert gender == "male"  # Default


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
