"""Tests for tone A/B test integration with topic generator."""

import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "automation"))
from topic_generator import _get_tone_mode, _build_tone_prompt_sections


def _make_tone_experiment(created_days_ago, duration_weeks=8):
    """Helper to build tone experiment state."""
    created_at = (datetime.now() - timedelta(days=created_days_ago)).isoformat()
    return {
        "experiments": [{
            "id": "exp_tone_001",
            "name": "Musical Tone Test",
            "config_key": "tone_mode",
            "control_value": "baseline",
            "treatment_value": "diversified",
            "duration_weeks": duration_weeks,
            "status": "active",
            "created_at": created_at,
            "current_week": 1,
            "current_variant": "control",
            "results": {"control": {"videos": []}, "treatment": {"videos": []}}
        }],
        "completed": []
    }


@pytest.fixture
def tone_state_week1(tmp_path):
    """Experiment created 2 days ago — week 1 (control = baseline)."""
    state = _make_tone_experiment(created_days_ago=2)
    state_file = tmp_path / "ab_experiments.json"
    state_file.write_text(json.dumps(state))
    return state_file


@pytest.fixture
def tone_state_week2(tmp_path):
    """Experiment created 10 days ago — week 2 (treatment = diversified)."""
    state = _make_tone_experiment(created_days_ago=10)
    state_file = tmp_path / "ab_experiments.json"
    state_file.write_text(json.dumps(state))
    return state_file


@pytest.fixture
def tone_state_expired(tmp_path):
    """Experiment created 60 days ago — past 8-week duration."""
    state = _make_tone_experiment(created_days_ago=60, duration_weeks=8)
    state_file = tmp_path / "ab_experiments.json"
    state_file.write_text(json.dumps(state))
    return state_file


@pytest.fixture
def tone_state_no_experiment(tmp_path):
    """Empty experiment state."""
    state = {"experiments": [], "completed": []}
    state_file = tmp_path / "ab_experiments.json"
    state_file.write_text(json.dumps(state))
    return state_file


def _patch_path(state_file):
    """Redirect experiment state reads to tmp file."""
    original_path = Path
    def patched(p):
        if p == "automation/state/ab_experiments.json":
            return state_file
        return original_path(p)
    return patched


def test_tone_mode_returns_baseline_in_week1(tone_state_week1):
    """Week 1 (odd) should return baseline (control)."""
    with patch("topic_generator.Path", side_effect=_patch_path(tone_state_week1)):
        result = _get_tone_mode()
    assert result == "baseline"


def test_tone_mode_returns_diversified_in_week2(tone_state_week2):
    """Week 2 (even) should return diversified (treatment)."""
    with patch("topic_generator.Path", side_effect=_patch_path(tone_state_week2)):
        result = _get_tone_mode()
    assert result == "diversified"


def test_tone_mode_returns_diversified_when_expired(tone_state_expired):
    """Expired experiment should fall back to diversified."""
    with patch("topic_generator.Path", side_effect=_patch_path(tone_state_expired)):
        result = _get_tone_mode()
    assert result == "diversified"


def test_tone_mode_returns_diversified_when_no_experiment(tone_state_no_experiment):
    """No active experiment should fall back to diversified."""
    with patch("topic_generator.Path", side_effect=_patch_path(tone_state_no_experiment)):
        result = _get_tone_mode()
    assert result == "diversified"


def test_tone_mode_returns_diversified_when_file_missing():
    """Missing state file should fall back to diversified."""
    original_path = Path
    def patched(p):
        if p == "automation/state/ab_experiments.json":
            return original_path("/nonexistent/ab_experiments.json")
        return original_path(p)

    with patch("topic_generator.Path", side_effect=patched):
        result = _get_tone_mode()
    assert result == "diversified"


def test_baseline_prompt_uses_pop_punk(tone_state_week1):
    """Baseline mode should only offer pop punk / pop rock tones."""
    with patch("topic_generator.Path", side_effect=_patch_path(tone_state_week1)):
        guidelines, examples = _build_tone_prompt_sections()

    assert "pop punk" in guidelines.lower()
    assert "pop rock" in guidelines.lower()
    # Should NOT contain category-specific diversified tones
    assert "synth-pop" not in guidelines.lower()
    assert "lo-fi electronic" not in guidelines.lower()
    assert "progressive rock" not in guidelines.lower()


def test_diversified_prompt_uses_category_tones(tone_state_week2):
    """Diversified mode should offer category-matched tones."""
    with patch("topic_generator.Path", side_effect=_patch_path(tone_state_week2)):
        guidelines, examples = _build_tone_prompt_sections()

    assert "synth-pop" in guidelines.lower()
    assert "lo-fi electronic" in guidelines.lower()
    assert "progressive rock" in guidelines.lower()
    assert "orchestral rock" in guidelines.lower()


def test_baseline_has_no_industrial_rock(tone_state_week1):
    """Baseline mode should NOT contain heavy industrial rock."""
    with patch("topic_generator.Path", side_effect=_patch_path(tone_state_week1)):
        guidelines, examples = _build_tone_prompt_sections()

    assert "industrial rock" not in guidelines.lower()
    assert "metallic percussion" not in guidelines.lower()


def test_diversified_reverted_industrial_to_pop_punk(tone_state_week2):
    """Even diversified mode should use pop punk for manufacturing, not industrial rock."""
    with patch("topic_generator.Path", side_effect=_patch_path(tone_state_week2)):
        guidelines, examples = _build_tone_prompt_sections()

    # Manufacturing line should NOT be heavy industrial rock
    assert "heavy industrial rock" not in guidelines
    # Manufacturing should use pop punk instead
    assert "pop punk" in guidelines.lower()
