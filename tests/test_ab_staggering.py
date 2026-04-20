import json
import pytest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent / "automation"))
sys.path.insert(0, str(Path(__file__).parent.parent / "agents"))


def test_assign_phase_offset_balances():
    from ab_test_manager import _assign_phase_offset

    # 3 with offset 0, 1 with offset 1 -> new should get 1
    existing = [
        {"phase_offset": 0, "status": "active"},
        {"phase_offset": 0, "status": "active"},
        {"phase_offset": 0, "status": "active"},
        {"phase_offset": 1, "status": "active"},
    ]
    assert _assign_phase_offset(existing) == 1


def test_assign_phase_offset_ignores_completed():
    from ab_test_manager import _assign_phase_offset

    existing = [
        {"phase_offset": 0, "status": "active"},
        {"phase_offset": 0, "status": "completed"},
        {"phase_offset": 0, "status": "completed"},
        {"phase_offset": 1, "status": "active"},
    ]
    # Active only: 1x0, 1x1 -> balanced, default to 0
    assert _assign_phase_offset(existing) == 0


def test_phase_offset_flips_variant():
    from ab_test_manager import get_current_config_for_experiment

    exp_no_offset = {
        "current_week": 1, "phase_offset": 0,
        "control_value": "A", "treatment_value": "B",
    }
    variant, value = get_current_config_for_experiment(exp_no_offset)
    assert variant == "control"
    assert value == "A"

    exp_with_offset = {
        "current_week": 1, "phase_offset": 1,
        "control_value": "A", "treatment_value": "B",
    }
    variant, value = get_current_config_for_experiment(exp_with_offset)
    assert variant == "treatment"
    assert value == "B"


def test_missing_phase_offset_defaults_to_zero():
    from ab_test_manager import get_current_config_for_experiment

    exp = {
        "current_week": 1,
        "control_value": "A", "treatment_value": "B",
    }
    variant, value = get_current_config_for_experiment(exp)
    assert variant == "control"  # Same as offset=0


def test_engagement_experiments_respects_offset(tmp_path):
    """Engagement experiment variant reader respects phase_offset."""
    from engagement_experiments import get_engagement_experiment_variant
    from unittest.mock import patch
    from datetime import datetime, timedelta

    # Create an experiment that started "this week" with phase_offset=1
    now = datetime.now()
    created = now - timedelta(days=1)  # Created 1 day ago = week 1

    experiments = {
        "experiments": [{
            "id": "test",
            "config_key": "engagement_hook_sfx",
            "control_value": "false",
            "treatment_value": "true",
            "status": "active",
            "phase_offset": 1,
            "duration_weeks": 8,
            "created_at": created.isoformat(),
            "results": {"control": {}, "treatment": {}}
        }]
    }

    exp_path = tmp_path / "ab_experiments.json"
    exp_path.write_text(json.dumps(experiments))

    # Week 1 + offset 1 = 2, 2%2=0, so treatment
    with patch("engagement_experiments.Path", return_value=exp_path):
        variant = get_engagement_experiment_variant("engagement_hook_sfx")
        assert variant == "true"  # treatment, because offset flips it
