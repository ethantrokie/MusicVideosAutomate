"""Tests for A/B experiment independence, snapshot-based attribution, conclusion, and early stopping."""

import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "agents"))
sys.path.insert(0, str(Path(__file__).parent.parent / "automation"))

from experiment_snapshot import snapshot_active_experiments, compute_variant_for_experiment
from ab_test_manager import conclude_experiment, check_early_stopping, compute_gap_days, sync_experiment_week


# --- Experiment snapshot ---

def _make_experiments(*experiments):
    """Build ab_experiments.json content from experiment dicts."""
    return {"experiments": list(experiments), "completed": []}


def _make_exp(config_key, created_days_ago, duration_weeks=8, status="active"):
    created_at = (datetime.now() - timedelta(days=created_days_ago)).isoformat()
    return {
        "id": f"exp_{config_key}",
        "name": f"Test {config_key}",
        "config_key": config_key,
        "control_value": "off",
        "treatment_value": "on",
        "duration_weeks": duration_weeks,
        "created_at": created_at,
        "status": status,
        "current_week": 1,
        "current_variant": "control",
        "results": {
            "control": {"videos": [], "total_views": 0, "total_engagement": 0, "avg_retention": 0, "avg_engaged_view_rate": 0, "total_subscribers_gained": 0},
            "treatment": {"videos": [], "total_views": 0, "total_engagement": 0, "avg_retention": 0, "avg_engaged_view_rate": 0, "total_subscribers_gained": 0}
        }
    }


def test_snapshot_captures_all_active_experiments(tmp_path):
    """Snapshot should include every active experiment."""
    state = _make_experiments(
        _make_exp("tone_mode", created_days_ago=2),
        _make_exp("performer_variant", created_days_ago=10),
        _make_exp("educational_images_enabled", created_days_ago=5),
    )
    state_file = tmp_path / "ab_experiments.json"
    state_file.write_text(json.dumps(state))

    original_path = Path
    def patched(p):
        if p == "automation/state/ab_experiments.json":
            return state_file
        return original_path(p)

    with patch("experiment_snapshot.Path", side_effect=patched):
        result = snapshot_active_experiments()

    assert len(result["experiments"]) == 3
    assert "tone_mode" in result["experiments"]
    assert "performer_variant" in result["experiments"]
    assert "educational_images_enabled" in result["experiments"]


def test_snapshot_excludes_completed(tmp_path):
    """Completed experiments should not appear in snapshot."""
    state = _make_experiments(
        _make_exp("tone_mode", created_days_ago=2),
        _make_exp("old_experiment", created_days_ago=2, status="completed"),
    )
    state_file = tmp_path / "ab_experiments.json"
    state_file.write_text(json.dumps(state))

    original_path = Path
    def patched(p):
        if p == "automation/state/ab_experiments.json":
            return state_file
        return original_path(p)

    with patch("experiment_snapshot.Path", side_effect=patched):
        result = snapshot_active_experiments()

    assert len(result["experiments"]) == 1
    assert "tone_mode" in result["experiments"]


def test_snapshot_excludes_expired(tmp_path):
    """Experiments past their duration should not appear in snapshot."""
    state = _make_experiments(
        _make_exp("expired_exp", created_days_ago=70, duration_weeks=8),
    )
    state_file = tmp_path / "ab_experiments.json"
    state_file.write_text(json.dumps(state))

    original_path = Path
    def patched(p):
        if p == "automation/state/ab_experiments.json":
            return state_file
        return original_path(p)

    with patch("experiment_snapshot.Path", side_effect=patched):
        result = snapshot_active_experiments()

    assert len(result["experiments"]) == 0


def test_snapshot_records_correct_variants(tmp_path):
    """Week 1 (odd) = control, week 2 (even) = treatment."""
    state = _make_experiments(
        _make_exp("exp_week1", created_days_ago=2),   # week 1 -> control
        _make_exp("exp_week2", created_days_ago=10),  # week 2 -> treatment
    )
    state_file = tmp_path / "ab_experiments.json"
    state_file.write_text(json.dumps(state))

    original_path = Path
    def patched(p):
        if p == "automation/state/ab_experiments.json":
            return state_file
        return original_path(p)

    with patch("experiment_snapshot.Path", side_effect=patched):
        result = snapshot_active_experiments()

    assert result["experiments"]["exp_week1"]["variant"] == "control"
    assert result["experiments"]["exp_week2"]["variant"] == "treatment"


def test_snapshot_missing_file():
    """Missing experiments file should return empty snapshot."""
    original_path = Path
    def patched(p):
        if p == "automation/state/ab_experiments.json":
            return original_path("/nonexistent/ab_experiments.json")
        return original_path(p)

    with patch("experiment_snapshot.Path", side_effect=patched):
        result = snapshot_active_experiments()

    assert result["experiments"] == {}


# --- Variant computation ---

def test_compute_variant_week1():
    exp = _make_exp("test", created_days_ago=2)
    result = compute_variant_for_experiment(exp)
    assert result["variant"] == "control"
    assert result["value"] == "off"
    assert result["week"] == 1


def test_compute_variant_week2():
    exp = _make_exp("test", created_days_ago=10)
    result = compute_variant_for_experiment(exp)
    assert result["variant"] == "treatment"
    assert result["value"] == "on"


def test_compute_variant_expired():
    exp = _make_exp("test", created_days_ago=70, duration_weeks=8)
    result = compute_variant_for_experiment(exp)
    assert result is None


# --- Experiment conclusion ---

def test_conclude_experiment_treatment_wins():
    """Treatment with higher engaged view rate should win (dominant 60% weight)."""
    exp = _make_exp("test_config", created_days_ago=60, duration_weeks=8)
    exp["results"]["control"] = {
        "videos": [{"video_id": f"v{i}", "views": 100, "engagement": 5, "retention": 30} for i in range(6)],
        "total_views": 600,
        "total_engagement": 30,
        "avg_retention": 30.0,
        "avg_engaged_view_rate": 55.0,
        "total_subscribers_gained": 6,
    }
    exp["results"]["treatment"] = {
        "videos": [{"video_id": f"t{i}", "views": 150, "engagement": 10, "retention": 45} for i in range(6)],
        "total_views": 900,
        "total_engagement": 60,
        "avg_retention": 45.0,
        "avg_engaged_view_rate": 78.0,
        "total_subscribers_gained": 18,
    }

    summary = conclude_experiment(exp)

    assert summary["winner"] == "treatment"
    assert summary["winner_value"] == "on"
    assert summary["is_significant"] is True
    assert summary["control"]["videos"] == 6
    assert summary["treatment"]["videos"] == 6
    # New scoring fields present
    assert "normalized_score" in summary["control"]
    assert "normalized_score" in summary["treatment"]
    assert summary["treatment"]["normalized_score"] > summary["control"]["normalized_score"]
    assert "scoring_weights" in summary
    assert summary["scoring_weights"]["engaged_view_rate"] == 0.60


def test_conclude_experiment_control_wins():
    """Control with higher engaged view rate should win despite lower views."""
    exp = _make_exp("test_config", created_days_ago=60, duration_weeks=8)
    exp["results"]["control"] = {
        "videos": [{"video_id": f"v{i}"} for i in range(6)],
        "total_views": 300,
        "total_engagement": 10,
        "avg_retention": 50.0,
        "avg_engaged_view_rate": 82.0,
        "total_subscribers_gained": 12,
    }
    exp["results"]["treatment"] = {
        "videos": [{"video_id": f"t{i}"} for i in range(6)],
        "total_views": 900,
        "total_engagement": 60,
        "avg_retention": 20.0,
        "avg_engaged_view_rate": 40.0,
        "total_subscribers_gained": 3,
    }

    summary = conclude_experiment(exp)
    assert summary["winner"] == "control"


def test_conclude_engaged_rate_dominates_views():
    """Engaged view rate (60% weight) should outweigh views (15% weight)."""
    exp = _make_exp("test_config", created_days_ago=60, duration_weeks=8)
    # Treatment has much higher views but worse engaged rate and subs
    exp["results"]["control"] = {
        "videos": [{"video_id": f"v{i}"} for i in range(6)],
        "total_views": 100,
        "total_engagement": 5,
        "avg_retention": 40.0,
        "avg_engaged_view_rate": 80.0,
        "total_subscribers_gained": 6,
    }
    exp["results"]["treatment"] = {
        "videos": [{"video_id": f"t{i}"} for i in range(6)],
        "total_views": 10000,
        "total_engagement": 500,
        "avg_retention": 10.0,
        "avg_engaged_view_rate": 30.0,
        "total_subscribers_gained": 2,
    }

    summary = conclude_experiment(exp)
    # Control should win because engaged_rate (60%) + subs (25%) dominate views (15%)
    assert summary["winner"] == "control"


def test_conclude_insufficient_data():
    """Fewer than 5 videos per arm should flag as not significant."""
    exp = _make_exp("test_config", created_days_ago=60, duration_weeks=8)
    exp["results"]["control"] = {
        "videos": [{"video_id": "v1"}, {"video_id": "v2"}],
        "total_views": 200,
        "total_engagement": 10,
        "avg_retention": 40.0,
        "avg_engaged_view_rate": 70.0,
        "total_subscribers_gained": 2,
    }
    exp["results"]["treatment"] = {
        "videos": [{"video_id": "t1"}],
        "total_views": 100,
        "total_engagement": 5,
        "avg_retention": 35.0,
        "avg_engaged_view_rate": 60.0,
        "total_subscribers_gained": 0,
    }

    summary = conclude_experiment(exp)
    assert summary["is_significant"] is False


def test_conclude_empty_arms():
    """Zero videos should not crash."""
    exp = _make_exp("test_config", created_days_ago=60, duration_weeks=8)

    summary = conclude_experiment(exp)
    assert summary["winner"] in ("control", "treatment")
    assert summary["is_significant"] is False
    assert summary["control"]["videos"] == 0
    assert summary["treatment"]["videos"] == 0


def test_conclude_fallback_to_retention_when_no_engaged_rate():
    """If avg_engaged_view_rate is missing, should fall back to avg_retention."""
    exp = _make_exp("test_config", created_days_ago=60, duration_weeks=8)
    # No avg_engaged_view_rate fields — legacy data
    exp["results"]["control"] = {
        "videos": [{"video_id": f"v{i}"} for i in range(6)],
        "total_views": 600,
        "total_engagement": 30,
        "avg_retention": 30.0,
    }
    exp["results"]["treatment"] = {
        "videos": [{"video_id": f"t{i}"} for i in range(6)],
        "total_views": 900,
        "total_engagement": 60,
        "avg_retention": 50.0,
    }

    summary = conclude_experiment(exp)
    # Should not crash, and treatment should win (higher retention used as fallback)
    assert summary["winner"] == "treatment"
    assert summary["is_significant"] is True


# --- Record with confound tracking ---

def test_record_includes_concurrent_experiments(tmp_path):
    """
    When recording a video result, the concurrent_experiments field
    should contain variants of all other active experiments.
    """
    # Simulate: video produced with snapshot showing 3 experiments
    snapshot = {
        "experiments": {
            "tone_mode": {"variant": "control", "value": "baseline"},
            "performer_variant": {"variant": "treatment", "value": "male_variant_b.png"},
            "educational_images_enabled": {"variant": "treatment", "value": "true"},
        }
    }

    # Create run dir with snapshot
    run_dir = tmp_path / "run_001"
    run_dir.mkdir()
    (run_dir / "experiment_snapshot.json").write_text(json.dumps(snapshot))

    # Create upload queue
    queue = {
        "queue": [{
            "run_id": "run_001",
            "run_dir": str(run_dir),
            "tone": "energetic pop punk",
            "videos": {
                "full": {"video_id": "vid_abc", "status": "uploaded"},
            }
        }]
    }

    # Create experiments
    exp_data = _make_experiments(
        _make_exp("tone_mode", created_days_ago=2),
        _make_exp("educational_images_enabled", created_days_ago=5),
    )

    # Write files
    queue_path = tmp_path / "youtube_upload_queue.json"
    queue_path.write_text(json.dumps(queue))

    exp_path = tmp_path / "ab_experiments.json"
    exp_path.write_text(json.dumps(exp_data))

    # Patch paths and run
    from weekly_optimizer import record_ab_test_results

    metrics_data = {
        "vid_abc": {
            "views": 500,
            "likes": 20,
            "comments": 5,
            "shares": 3,
            "avg_retention": 42.0,
        }
    }

    original_path = Path

    def patched(p):
        p_str = str(p)
        if "youtube_upload_queue.json" in p_str:
            return queue_path
        if "ab_experiments.json" in p_str:
            return exp_path
        return original_path(p)

    with patch("weekly_optimizer.Path", side_effect=patched):
        record_ab_test_results(metrics_data)

    # Read back results
    with open(exp_path) as f:
        result = json.load(f)

    # Check tone_mode experiment
    tone_exp = result["experiments"][0]
    # Snapshot says tone_mode was "control"
    tone_ctrl_videos = tone_exp["results"]["control"]["videos"]
    assert len(tone_ctrl_videos) == 1
    assert tone_ctrl_videos[0]["video_id"] == "vid_abc"
    # Should have concurrent_experiments excluding tone_mode itself
    concurrent = tone_ctrl_videos[0]["concurrent_experiments"]
    assert "tone_mode" not in concurrent
    assert "educational_images_enabled" in concurrent

    # Check educational_images experiment
    edu_exp = result["experiments"][1]
    # Snapshot says educational_images_enabled was "treatment"
    edu_treat_videos = edu_exp["results"]["treatment"]["videos"]
    assert len(edu_treat_videos) == 1
    assert edu_treat_videos[0]["video_id"] == "vid_abc"
    concurrent = edu_treat_videos[0]["concurrent_experiments"]
    assert "educational_images_enabled" not in concurrent
    assert "tone_mode" in concurrent


# --- Early stopping via statistical significance ---

def _make_exp_with_video_data(config_key, created_days_ago, control_rates, treatment_rates,
                               duration_weeks=8):
    """Build an experiment with per-video engaged view rate data in both arms."""
    exp = _make_exp(config_key, created_days_ago=created_days_ago, duration_weeks=duration_weeks)
    exp["results"]["control"]["videos"] = [
        {"video_id": f"c{i}", "views": 100, "engagement": 5, "retention": 40.0,
         "engaged_view_rate": rate, "subscribers_gained": 1}
        for i, rate in enumerate(control_rates)
    ]
    exp["results"]["control"]["total_views"] = 100 * len(control_rates)
    exp["results"]["control"]["avg_engaged_view_rate"] = (
        sum(control_rates) / len(control_rates) if control_rates else 0
    )
    exp["results"]["treatment"]["videos"] = [
        {"video_id": f"t{i}", "views": 100, "engagement": 5, "retention": 40.0,
         "engaged_view_rate": rate, "subscribers_gained": 1}
        for i, rate in enumerate(treatment_rates)
    ]
    exp["results"]["treatment"]["total_views"] = 100 * len(treatment_rates)
    exp["results"]["treatment"]["avg_engaged_view_rate"] = (
        sum(treatment_rates) / len(treatment_rates) if treatment_rates else 0
    )
    return exp


def test_early_stopping_triggers_on_significant_difference():
    """Should return early stop signal when arms are clearly different (p < 0.05)."""
    # Large, clearly separated distributions — 14 days old so min 2 weeks met
    control_rates = [30.0, 32.0, 28.0, 31.0, 29.0, 33.0, 27.0]
    treatment_rates = [70.0, 72.0, 68.0, 71.0, 69.0, 73.0, 67.0]
    exp = _make_exp_with_video_data("test_sig", created_days_ago=14,
                                     control_rates=control_rates,
                                     treatment_rates=treatment_rates)

    result = check_early_stopping(exp)

    assert result["should_stop"] is True
    assert result["p_value"] < 0.05
    assert result["reason"] == "early_stopping_significant"


def test_early_stopping_does_not_trigger_on_similar_arms():
    """Should NOT stop when arms are statistically similar."""
    control_rates = [50.0, 52.0, 48.0, 51.0, 49.0, 53.0, 47.0]
    treatment_rates = [51.0, 49.0, 50.0, 52.0, 48.0, 50.0, 51.0]
    exp = _make_exp_with_video_data("test_nosig", created_days_ago=14,
                                     control_rates=control_rates,
                                     treatment_rates=treatment_rates)

    result = check_early_stopping(exp)

    assert result["should_stop"] is False
    assert result["p_value"] >= 0.05


def test_early_stopping_requires_min_videos():
    """Should NOT stop when fewer than 5 videos per arm, even if data looks different."""
    control_rates = [30.0, 32.0, 28.0]
    treatment_rates = [70.0, 72.0, 68.0]
    exp = _make_exp_with_video_data("test_fewvids", created_days_ago=14,
                                     control_rates=control_rates,
                                     treatment_rates=treatment_rates)

    result = check_early_stopping(exp)

    assert result["should_stop"] is False
    assert result["reason"] == "insufficient_data"


def test_early_stopping_requires_min_weeks():
    """Should NOT stop before 2 weeks even with significant data."""
    control_rates = [30.0, 32.0, 28.0, 31.0, 29.0, 33.0, 27.0]
    treatment_rates = [70.0, 72.0, 68.0, 71.0, 69.0, 73.0, 67.0]
    # Only 7 days old — hasn't hit 2 weeks yet
    exp = _make_exp_with_video_data("test_tooearly", created_days_ago=7,
                                     control_rates=control_rates,
                                     treatment_rates=treatment_rates)

    result = check_early_stopping(exp)

    assert result["should_stop"] is False
    assert result["reason"] == "min_weeks_not_met"


def test_early_stopping_empty_arms():
    """Should handle empty arms gracefully."""
    exp = _make_exp("test_empty", created_days_ago=14)

    result = check_early_stopping(exp)

    assert result["should_stop"] is False
    assert result["reason"] == "insufficient_data"


def test_early_stopping_one_empty_arm():
    """Should handle one populated arm and one empty arm."""
    exp = _make_exp("test_one_arm", created_days_ago=14)
    exp["results"]["control"]["videos"] = [
        {"video_id": f"c{i}", "views": 100, "engaged_view_rate": 50.0}
        for i in range(7)
    ]

    result = check_early_stopping(exp)

    assert result["should_stop"] is False
    assert result["reason"] == "insufficient_data"


def test_early_stop_conclude_includes_reason():
    """When early-stopped, the conclusion should include the reason and p-value."""
    control_rates = [30.0, 32.0, 28.0, 31.0, 29.0, 33.0, 27.0]
    treatment_rates = [70.0, 72.0, 68.0, 71.0, 69.0, 73.0, 67.0]
    exp = _make_exp_with_video_data("test_reason", created_days_ago=14,
                                     control_rates=control_rates,
                                     treatment_rates=treatment_rates,
                                     duration_weeks=8)

    stop_result = check_early_stopping(exp)
    assert stop_result["should_stop"] is True

    summary = conclude_experiment(exp, early_stop=stop_result)

    assert summary["concluded_reason"] == "early_stopping_significant"
    assert summary["p_value"] < 0.05
    assert summary["weeks_completed"] < exp["duration_weeks"]


def test_duration_conclude_has_duration_reason():
    """Normal duration-based conclusion should have concluded_reason='duration_complete'."""
    control_rates = [50.0, 52.0, 48.0, 51.0, 49.0]
    treatment_rates = [51.0, 49.0, 50.0, 52.0, 48.0]
    exp = _make_exp_with_video_data("test_duration", created_days_ago=60,
                                     control_rates=control_rates,
                                     treatment_rates=treatment_rates,
                                     duration_weeks=8)

    summary = conclude_experiment(exp)

    assert summary["concluded_reason"] == "duration_complete"
    assert "p_value" not in summary


# --- Gap-aware week computation ---

def _make_exp_with_dated_videos(config_key, created_days_ago, control_dates, treatment_dates,
                                 duration_weeks=8):
    """Build experiment with videos on specific dates (as days-ago integers)."""
    now = datetime.now()
    exp = _make_exp(config_key, created_days_ago=created_days_ago, duration_weeks=duration_weeks)

    exp["results"]["control"]["videos"] = [
        {"video_id": f"c{i}", "views": 100, "engagement": 5, "retention": 40.0,
         "engaged_view_rate": 50.0, "subscribers_gained": 1,
         "date": (now - timedelta(days=d)).isoformat()}
        for i, d in enumerate(control_dates)
    ]
    exp["results"]["control"]["total_views"] = 100 * len(control_dates)

    exp["results"]["treatment"]["videos"] = [
        {"video_id": f"t{i}", "views": 100, "engagement": 5, "retention": 40.0,
         "engaged_view_rate": 50.0, "subscribers_gained": 1,
         "date": (now - timedelta(days=d)).isoformat()}
        for i, d in enumerate(treatment_dates)
    ]
    exp["results"]["treatment"]["total_views"] = 100 * len(treatment_dates)

    return exp


def test_compute_gap_days_no_gap():
    """Experiment with daily videos should have 0 gap days."""
    # Created 14 days ago, videos every day from day 13 to day 0
    exp = _make_exp_with_dated_videos(
        "no_gap", created_days_ago=14,
        control_dates=[13, 11, 9, 7, 5, 3, 1],
        treatment_dates=[12, 10, 8, 6, 4, 2, 0],
    )

    gap = compute_gap_days(exp)
    assert gap == 0


def test_compute_gap_days_with_gap():
    """Experiment with a multi-day gap should report those gap days."""
    # Created 20 days ago, videos on days 20-15 and 5-0, gap of ~9 days (days 14-6)
    exp = _make_exp_with_dated_videos(
        "with_gap", created_days_ago=20,
        control_dates=[20, 18, 16, 4, 2, 0],
        treatment_dates=[19, 17, 15, 3, 1],
    )

    gap = compute_gap_days(exp)
    # Gap spans from day 14 down to day 6 = 9 contiguous missing days
    # (days 14, 13, 12, 11, 10, 9, 8, 7, 6 — last video day 15, next day 5)
    assert gap >= 7  # At least a week of gap


def test_compute_gap_days_empty_experiment():
    """Experiment with no videos should report 0 gap days (nothing to measure)."""
    exp = _make_exp("empty_gap", created_days_ago=14)

    gap = compute_gap_days(exp)
    assert gap == 0


def test_gap_extends_experiment_week():
    """Gap days should slow down the effective week so experiment extends."""
    # Created 21 days ago = calendar week 4. But if 7 days were a gap,
    # effective elapsed = 14 days = week 3.
    exp = _make_exp_with_dated_videos(
        "gap_extend", created_days_ago=21,
        control_dates=[21, 20, 19, 4, 3, 2, 1, 0],  # videos days 21-19 and 4-0
        treatment_dates=[18, 17, 16, 15],             # videos days 18-15, then gap
        duration_weeks=4,
    )

    # Without gap awareness, calendar says week 4 (21 days / 7 = 3, +1 = 4)
    # With gap awareness, effective week should be less than 4
    effective_week = sync_experiment_week(exp)
    assert effective_week < 4


def test_no_gap_week_matches_calendar():
    """With continuous posting, effective week should equal calendar week."""
    # Created 14 days ago with videos every day
    exp = _make_exp_with_dated_videos(
        "continuous", created_days_ago=14,
        control_dates=[13, 11, 9, 7, 5, 3, 1],
        treatment_dates=[12, 10, 8, 6, 4, 2, 0],
    )

    effective_week = sync_experiment_week(exp)
    # Calendar says week 3 (14 days / 7 = 2, +1 = 3)
    assert effective_week == 3


def test_gap_prevents_premature_conclusion():
    """An experiment should NOT conclude early just because calendar time passed during a gap."""
    # 4-week experiment created 30 days ago (calendar week 5 — would normally be done)
    # But 10 days were a gap, so effective elapsed = 20 days = week 3 (still active)
    exp = _make_exp_with_dated_videos(
        "gap_active", created_days_ago=30,
        control_dates=[30, 29, 28, 5, 4, 3, 2, 1, 0],
        treatment_dates=[27, 26, 25, 24],
        duration_weeks=4,
    )

    effective_week = sync_experiment_week(exp)
    # Should still be within 4 weeks because gap days are subtracted
    assert effective_week <= 4


def test_gap_days_stored_on_experiment():
    """sync_experiment_week should store gap_days on the experiment for transparency."""
    exp = _make_exp_with_dated_videos(
        "stored_gap", created_days_ago=21,
        control_dates=[21, 20, 19, 1, 0],
        treatment_dates=[18, 17, 16],
        duration_weeks=8,
    )

    sync_experiment_week(exp)
    assert "gap_days" in exp
    assert exp["gap_days"] > 0
