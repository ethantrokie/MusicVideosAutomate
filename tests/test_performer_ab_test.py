"""Tests for A/B test integration with performer image selection."""

import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "agents"))
from environment_generator import _get_active_performer_variant, get_performer_image_path


def _make_experiment_state(created_days_ago, duration_weeks=4):
    """Helper to build experiment state with a creation date N days ago."""
    created_at = (datetime.now() - timedelta(days=created_days_ago)).isoformat()
    return {
        "experiments": [{
            "id": "exp_test_001",
            "name": "Avatar Test",
            "config_key": "performer_variant",
            "control_value": "male.png",
            "treatment_value": "male_variant_b.png",
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
def ab_state_week1(tmp_path):
    """Experiment created 2 days ago — should be week 1 (control)."""
    state = _make_experiment_state(created_days_ago=2)
    state_file = tmp_path / "ab_experiments.json"
    state_file.write_text(json.dumps(state))
    return state_file


@pytest.fixture
def ab_state_week2(tmp_path):
    """Experiment created 10 days ago — should be week 2 (treatment)."""
    state = _make_experiment_state(created_days_ago=10)
    state_file = tmp_path / "ab_experiments.json"
    state_file.write_text(json.dumps(state))
    return state_file


@pytest.fixture
def ab_state_expired(tmp_path):
    """Experiment created 35 days ago — 5 weeks elapsed, past 4-week duration."""
    state = _make_experiment_state(created_days_ago=35, duration_weeks=4)
    state_file = tmp_path / "ab_experiments.json"
    state_file.write_text(json.dumps(state))
    return state_file


@pytest.fixture
def ab_state_no_experiment(tmp_path):
    """Empty experiment state file."""
    state = {"experiments": [], "completed": []}
    state_file = tmp_path / "ab_experiments.json"
    state_file.write_text(json.dumps(state))
    return state_file


def _patch_path(state_file):
    """Create a Path side_effect that redirects experiment state reads."""
    original_path = Path
    def patched(p):
        if p == "automation/state/ab_experiments.json":
            return state_file
        return original_path(p)
    return patched


def test_variant_returns_control_in_week1(ab_state_week1):
    """Week 1 (odd) should return the control value."""
    with patch("environment_generator.Path", side_effect=_patch_path(ab_state_week1)):
        result = _get_active_performer_variant("male")
    assert result == "male.png"


def test_variant_returns_treatment_in_week2(ab_state_week2):
    """Week 2 (even) should return the treatment value."""
    with patch("environment_generator.Path", side_effect=_patch_path(ab_state_week2)):
        result = _get_active_performer_variant("male")
    assert result == "male_variant_b.png"


def test_variant_returns_none_when_expired(ab_state_expired):
    """Expired experiment (past duration_weeks) should return None."""
    with patch("environment_generator.Path", side_effect=_patch_path(ab_state_expired)):
        result = _get_active_performer_variant("male")
    assert result is None


def test_variant_returns_none_when_no_experiment(ab_state_no_experiment):
    """No active experiment should return None."""
    with patch("environment_generator.Path", side_effect=_patch_path(ab_state_no_experiment)):
        result = _get_active_performer_variant("male")
    assert result is None


def test_variant_returns_none_when_file_missing():
    """Missing state file should return None."""
    original_path = Path
    def patched(p):
        if p == "automation/state/ab_experiments.json":
            return original_path("/nonexistent/path/ab_experiments.json")
        return original_path(p)

    with patch("environment_generator.Path", side_effect=patched):
        result = _get_active_performer_variant("male")
    assert result is None


def test_get_performer_image_falls_back_when_no_experiment():
    """Without an experiment, should return the default male.png path."""
    original_path = Path
    def patched(p):
        if p == "automation/state/ab_experiments.json":
            return original_path("/nonexistent/ab_experiments.json")
        return original_path(p)

    with patch("environment_generator.Path", side_effect=patched):
        path = get_performer_image_path("male")

    # Should fall through to the local file check
    assert "male.png" in path or "pexels" in path
