#!/Users/ethantrokie/SoftwareDevProjects/MusicVideosAutomate/venv/bin/python3
"""
A/B Test Manager for YouTube channel optimization.
Manages experiments by alternating configurations and tracking results.
"""

import json
import argparse
from pathlib import Path
from datetime import datetime, timedelta

from scipy.stats import mannwhitneyu


def load_experiments():
    """Load active experiments."""
    path = Path("automation/state/ab_experiments.json")
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return {"experiments": [], "completed": []}


def save_experiments(data):
    """Save experiments state."""
    path = Path("automation/state/ab_experiments.json")
    with open(path, 'w') as f:
        json.dump(data, f, indent=2)


def _assign_phase_offset(existing_experiments: list) -> int:
    """
    Assign a phase offset (0 or 1) that balances active experiments.
    Counts active experiments using each offset, returns the minority offset.
    """
    count_0 = sum(
        1 for e in existing_experiments
        if e.get("status") == "active" and e.get("phase_offset", 0) == 0
    )
    count_1 = sum(
        1 for e in existing_experiments
        if e.get("status") == "active" and e.get("phase_offset", 0) == 1
    )
    return 1 if count_1 < count_0 else 0


def create_experiment(name, config_key, control_value, treatment_value, duration_weeks=4):
    """Create a new A/B test experiment."""
    data = load_experiments()

    # Check for duplicate active experiments on same config key
    for exp in data["experiments"]:
        if exp["config_key"] == config_key and exp["status"] == "active":
            print(f"Error: Active experiment already exists for {config_key}")
            return None

    experiment = {
        "id": f"exp_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        "name": name,
        "config_key": config_key,
        "control_value": control_value,
        "treatment_value": treatment_value,
        "duration_weeks": duration_weeks,
        "created_at": datetime.now().isoformat(),
        "status": "active",
        "phase_offset": _assign_phase_offset(data["experiments"]),
        "current_week": 1,
        "current_variant": "control",
        "results": {
            "control": {"videos": [], "total_views": 0, "total_engagement": 0, "avg_retention": 0, "avg_engaged_view_rate": 0, "total_subscribers_gained": 0},
            "treatment": {"videos": [], "total_views": 0, "total_engagement": 0, "avg_retention": 0, "avg_engaged_view_rate": 0, "total_subscribers_gained": 0}
        }
    }

    data["experiments"].append(experiment)
    save_experiments(data)
    print(f"Created experiment: {name} (ID: {experiment['id']})")
    print(f"  Control: {config_key} = {control_value}")
    print(f"  Treatment: {config_key} = {treatment_value}")
    print(f"  Duration: {duration_weeks} weeks (alternating weekly)")
    return experiment


def get_current_config_for_experiment(experiment):
    """Get which variant should be active this week."""
    phase_offset = experiment.get("phase_offset", 0)
    if (experiment["current_week"] + phase_offset) % 2 == 1:
        return "control", experiment["control_value"]
    return "treatment", experiment["treatment_value"]


GAP_THRESHOLD_DAYS = 2


def compute_gap_days(experiment: dict) -> int:
    """
    Count contiguous gap days where no videos were produced.

    A "gap" is any stretch of GAP_THRESHOLD_DAYS or more consecutive days
    within the experiment's lifespan that have zero video production across
    both arms. Short 1-day gaps (weekends, off days) are ignored.

    Only counts gaps between the first and last video dates — the period
    before the first video and after the last video are not gaps (the
    experiment hadn't started producing yet, or is in its current window).

    Returns:
        Total number of gap days to subtract from elapsed calendar time.
    """
    all_videos = (
        experiment["results"]["control"].get("videos", [])
        + experiment["results"]["treatment"].get("videos", [])
    )

    if len(all_videos) < 2:
        # With 0-1 videos we can't determine production cadence.
        # No gap to measure yet — experiment hasn't produced enough data.
        return 0

    # Collect the set of dates (day resolution) that had video production
    production_dates: set[datetime] = set()
    for v in all_videos:
        if "date" in v:
            production_dates.add(
                datetime.fromisoformat(v["date"]).replace(
                    hour=0, minute=0, second=0, microsecond=0
                )
            )

    if not production_dates:
        return 0

    first_date = min(production_dates)
    last_date = max(production_dates)

    # Walk each day between first and last production date, find contiguous gaps
    total_gap = 0
    current_gap = 0
    day = first_date + timedelta(days=1)
    while day <= last_date:
        if day in production_dates:
            if current_gap >= GAP_THRESHOLD_DAYS:
                total_gap += current_gap
            current_gap = 0
        else:
            current_gap += 1
        day += timedelta(days=1)

    # If we ended mid-gap (no videos after last_date up to now),
    # count that trailing gap too
    now = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    trailing_day = last_date + timedelta(days=1)
    trailing_gap = 0
    while trailing_day <= now:
        if trailing_day not in production_dates:
            trailing_gap += 1
        else:
            if trailing_gap >= GAP_THRESHOLD_DAYS:
                total_gap += trailing_gap
            trailing_gap = 0
        trailing_day += timedelta(days=1)

    if trailing_gap >= GAP_THRESHOLD_DAYS:
        total_gap += trailing_gap

    return total_gap


def sync_experiment_week(experiment: dict) -> int:
    """
    Compute the correct week number, adjusted for production gaps.

    Subtracts gap days (periods with no video production) from elapsed
    calendar time so that experiments extend to compensate for downtime.
    Stores gap_days on the experiment for transparency.

    Returns:
        The effective week number (1-based).
    """
    created = datetime.fromisoformat(experiment["created_at"])
    elapsed_days = (datetime.now() - created).days
    gap_days = compute_gap_days(experiment)
    effective_days = max(0, elapsed_days - gap_days)

    experiment["gap_days"] = gap_days

    return max(1, (effective_days // 7) + 1)


MIN_VIDEOS_PER_ARM = 5
MIN_WEEKS_BEFORE_STOPPING = 2
SIGNIFICANCE_THRESHOLD = 0.05


def check_early_stopping(experiment):
    """
    Check whether an experiment can be concluded early via statistical significance.

    Uses Mann-Whitney U test on per-video engaged view rates between control
    and treatment arms. Non-parametric — safe for small, non-normal samples.

    Requirements to trigger early stop:
      - At least MIN_VIDEOS_PER_ARM videos in each arm
      - At least MIN_WEEKS_BEFORE_STOPPING weeks elapsed since creation
      - p-value < SIGNIFICANCE_THRESHOLD

    Returns:
        Dict with should_stop, p_value, and reason.
    """
    created = datetime.fromisoformat(experiment["created_at"])
    elapsed_weeks = (datetime.now() - created).days / 7

    if elapsed_weeks < MIN_WEEKS_BEFORE_STOPPING:
        return {"should_stop": False, "p_value": None, "reason": "min_weeks_not_met"}

    ctrl_videos = experiment["results"]["control"].get("videos", [])
    treat_videos = experiment["results"]["treatment"].get("videos", [])

    if len(ctrl_videos) < MIN_VIDEOS_PER_ARM or len(treat_videos) < MIN_VIDEOS_PER_ARM:
        return {"should_stop": False, "p_value": None, "reason": "insufficient_data"}

    ctrl_rates = [v.get("engaged_view_rate", 0.0) for v in ctrl_videos]
    treat_rates = [v.get("engaged_view_rate", 0.0) for v in treat_videos]

    _, p_value = mannwhitneyu(ctrl_rates, treat_rates, alternative="two-sided")

    if p_value < SIGNIFICANCE_THRESHOLD:
        return {"should_stop": True, "p_value": p_value, "reason": "early_stopping_significant"}

    return {"should_stop": False, "p_value": p_value, "reason": "not_significant"}


def advance_week(experiment_id=None):
    """
    Sync all active experiments to the correct week based on calendar time.
    Resilient to machine restarts and missed runs.
    """
    data = load_experiments()

    for exp in data["experiments"]:
        if exp["status"] != "active":
            continue
        if experiment_id and exp["id"] != experiment_id:
            continue

        correct_week = sync_experiment_week(exp)
        old_week = exp["current_week"]
        exp["current_week"] = correct_week
        variant, value = get_current_config_for_experiment(exp)
        exp["current_variant"] = variant

        if correct_week != old_week:
            print(f"Experiment '{exp['name']}': Week {old_week} -> {correct_week} ({variant}: {value})")
        else:
            print(f"Experiment '{exp['name']}': Week {correct_week} ({variant}: {value}) — no change")

        # Check for early stopping before duration check
        early_stop = check_early_stopping(exp)
        if early_stop["should_stop"]:
            exp["status"] = "completed"
            exp["completed_at"] = datetime.now().isoformat()
            print(f"  ⚡ EARLY STOP: '{exp['name']}' reached statistical significance "
                  f"(p={early_stop['p_value']:.4f}) at week {correct_week}/{exp['duration_weeks']}")
            summary = conclude_experiment(exp, early_stop=early_stop)
            data["completed"].append(exp)
            _save_conclusion_report(exp, summary)
        elif correct_week > exp["duration_weeks"]:
            exp["status"] = "completed"
            exp["completed_at"] = datetime.now().isoformat()
            summary = conclude_experiment(exp)
            data["completed"].append(exp)
            _save_conclusion_report(exp, summary)

    data["experiments"] = [e for e in data["experiments"] if e["status"] == "active"]
    save_experiments(data)


def _normalize(value, min_val, max_val):
    """Min-max normalize a value to [0, 1]. Returns 0.5 if min == max."""
    if max_val == min_val:
        return 0.5
    return (value - min_val) / (max_val - min_val)


def conclude_experiment(experiment, early_stop=None):
    """
    Generate a conclusion summary when an experiment completes.
    Compares control vs treatment using normalized, weighted scoring.

    Weights (optimizing for Shorts "stayed vs swiped" + new subscribers):
    - Engaged view rate (engagedViews/views): 60% — best proxy for "viewed vs swiped away"
    - Subscribers gained per video: 25% — direct growth metric
    - Avg views per video: 15% — reach/distribution signal

    All metrics are min-max normalized before weighting so that
    different scales (e.g. 75% rate vs 500 views) don't distort the score.

    Args:
        experiment: The experiment dict.
        early_stop: Optional dict from check_early_stopping() when concluding early.

    Returns:
        Dict with winner, metrics comparison, and recommendation.
    """
    stagger_date = experiment.get("stagger_applied_at")
    if stagger_date:
        cutoff = datetime.fromisoformat(stagger_date)
        for arm in ("control", "treatment"):
            experiment["results"][arm]["videos"] = [
                v for v in experiment["results"][arm].get("videos", [])
                if datetime.fromisoformat(v["date"]) >= cutoff
            ]

    ctrl = experiment["results"]["control"]
    treat = experiment["results"]["treatment"]

    ctrl_count = max(len(ctrl["videos"]), 1)
    treat_count = max(len(treat["videos"]), 1)

    ctrl_avg_views = ctrl["total_views"] / ctrl_count
    treat_avg_views = treat["total_views"] / treat_count

    ctrl_avg_engagement = ctrl["total_engagement"] / ctrl_count
    treat_avg_engagement = treat["total_engagement"] / treat_count

    ctrl_engaged_rate = ctrl.get("avg_engaged_view_rate", ctrl["avg_retention"])
    treat_engaged_rate = treat.get("avg_engaged_view_rate", treat["avg_retention"])

    ctrl_avg_subs = ctrl.get("total_subscribers_gained", 0) / ctrl_count
    treat_avg_subs = treat.get("total_subscribers_gained", 0) / treat_count

    # Normalize each metric to [0, 1] across the two arms
    metrics = {
        "engaged_view_rate": (ctrl_engaged_rate, treat_engaged_rate),
        "subscribers_per_video": (ctrl_avg_subs, treat_avg_subs),
        "avg_views": (ctrl_avg_views, treat_avg_views),
    }

    weights = {
        "engaged_view_rate": 0.60,
        "subscribers_per_video": 0.25,
        "avg_views": 0.15,
    }

    ctrl_score = 0.0
    treat_score = 0.0
    for metric_name, (c_val, t_val) in metrics.items():
        min_val = min(c_val, t_val)
        max_val = max(c_val, t_val)
        c_norm = _normalize(c_val, min_val, max_val)
        t_norm = _normalize(t_val, min_val, max_val)
        w = weights[metric_name]
        ctrl_score += c_norm * w
        treat_score += t_norm * w

    winner = "treatment" if treat_score > ctrl_score else "control"
    winner_value = experiment["treatment_value"] if winner == "treatment" else experiment["control_value"]

    # Check for statistical significance (rough heuristic: need 5+ videos per arm)
    min_videos = min(len(ctrl["videos"]), len(treat["videos"]))
    is_significant = min_videos >= 5

    # Engaged view rate lift percentage (primary metric)
    engaged_rate_lift = ((treat_engaged_rate - ctrl_engaged_rate) / max(ctrl_engaged_rate, 0.01)) * 100

    # Keep retention_lift_pct for backwards compatibility
    ctrl_retention = ctrl["avg_retention"]
    treat_retention = treat["avg_retention"]
    retention_lift = ((treat_retention - ctrl_retention) / max(ctrl_retention, 0.01)) * 100

    # Compute weeks completed from creation date
    created = datetime.fromisoformat(experiment["created_at"])
    weeks_completed = max(1, (datetime.now() - created).days // 7)

    summary = {
        "winner": winner,
        "winner_value": winner_value,
        "is_significant": is_significant,
        "concluded_reason": early_stop["reason"] if early_stop else "duration_complete",
        "weeks_completed": weeks_completed,
        "retention_lift_pct": round(retention_lift, 1),
        "engaged_rate_lift_pct": round(engaged_rate_lift, 1),
        "scoring_weights": weights,
        "control": {
            "videos": len(ctrl["videos"]),
            "avg_views": round(ctrl_avg_views, 1),
            "avg_engagement": round(ctrl_avg_engagement, 1),
            "avg_retention": round(ctrl_retention, 1),
            "avg_engaged_view_rate": round(ctrl_engaged_rate, 1),
            "avg_subscribers_gained": round(ctrl_avg_subs, 2),
            "normalized_score": round(ctrl_score, 4),
        },
        "treatment": {
            "videos": len(treat["videos"]),
            "avg_views": round(treat_avg_views, 1),
            "avg_engagement": round(treat_avg_engagement, 1),
            "avg_retention": round(treat_retention, 1),
            "avg_engaged_view_rate": round(treat_engaged_rate, 1),
            "avg_subscribers_gained": round(treat_avg_subs, 2),
            "normalized_score": round(treat_score, 4),
        },
    }

    if early_stop and early_stop.get("p_value") is not None:
        summary["p_value"] = early_stop["p_value"]

    config_key = experiment["config_key"]
    print(f"\n  {'=' * 50}")
    if early_stop and early_stop["should_stop"]:
        print(f"  EXPERIMENT EARLY-STOPPED: {experiment['name']}")
        print(f"  Reason: Statistical significance reached (p={early_stop['p_value']:.4f})")
        print(f"  Week {weeks_completed}/{experiment['duration_weeks']} — saved {experiment['duration_weeks'] - weeks_completed} weeks")
    else:
        print(f"  EXPERIMENT CONCLUDED: {experiment['name']}")
    print(f"  {'=' * 50}")
    print(f"  Winner: {winner.upper()} ({config_key} = {winner_value})")
    print(f"  Engaged view rate lift: {engaged_rate_lift:+.1f}%")
    print(f"  Control:   {len(ctrl['videos'])} videos, {ctrl_engaged_rate:.1f}% engaged rate, {ctrl_avg_subs:.1f} subs/vid, {ctrl_avg_views:.0f} avg views")
    print(f"  Treatment: {len(treat['videos'])} videos, {treat_engaged_rate:.1f}% engaged rate, {treat_avg_subs:.1f} subs/vid, {treat_avg_views:.0f} avg views")
    print(f"  Scores: control={ctrl_score:.4f}, treatment={treat_score:.4f} (weights: engaged_rate 60%, subs 25%, views 15%)")

    if not is_significant:
        print(f"  LOW CONFIDENCE: Only {min_videos} videos in smaller arm (need 5+)")
        print(f"  Recommendation: Re-run experiment for more data")
    else:
        print(f"  Sufficient data ({min_videos}+ videos per arm)")
        print(f"  Recommendation: Set {config_key} = {winner_value} in config")

    print(f"  {'=' * 50}\n")

    return summary


def _save_conclusion_report(experiment, summary):
    """Save experiment conclusion as a markdown report."""
    reports_dir = Path("automation/reports")
    reports_dir.mkdir(exist_ok=True)

    date_str = datetime.now().strftime("%Y-%m-%d")
    report_path = reports_dir / f"{date_str}-ab-test-{experiment['config_key']}.md"

    ctrl = summary["control"]
    treat = summary["treatment"]

    weights = summary.get("scoring_weights", {})
    weights_str = ", ".join(f"{k} {int(v*100)}%" for k, v in weights.items())

    concluded_reason = summary.get("concluded_reason", "duration_complete")
    p_value = summary.get("p_value")

    if concluded_reason == "early_stopping_significant":
        conclusion_line = (
            f"- **Conclusion**: Early-stopped at week {summary['weeks_completed']}/{experiment['duration_weeks']} "
            f"(Mann-Whitney U p={p_value:.4f})"
        )
    else:
        conclusion_line = f"- **Duration**: {experiment['duration_weeks']} weeks (full duration)"

    report = f"""# A/B Test Conclusion: {experiment['name']}

## Summary
- **Config key**: `{experiment['config_key']}`
{conclusion_line}
- **Winner**: **{summary['winner'].upper()}** (`{summary['winner_value']}`)
- **Engaged view rate lift**: {summary.get('engaged_rate_lift_pct', 0):+.1f}%
- **Statistical confidence**: {'Sufficient' if summary['is_significant'] else 'INSUFFICIENT — re-run recommended'}
- **Scoring weights**: {weights_str}

## Results

| Metric | Control (`{experiment['control_value']}`) | Treatment (`{experiment['treatment_value']}`) |
|--------|---------|-----------|
| Videos | {ctrl['videos']} | {treat['videos']} |
| Engaged View Rate | {ctrl.get('avg_engaged_view_rate', 0):.1f}% | {treat.get('avg_engaged_view_rate', 0):.1f}% |
| Subscribers/Video | {ctrl.get('avg_subscribers_gained', 0):.2f} | {treat.get('avg_subscribers_gained', 0):.2f} |
| Avg Views | {ctrl['avg_views']:.0f} | {treat['avg_views']:.0f} |
| Avg Engagement | {ctrl['avg_engagement']:.1f} | {treat['avg_engagement']:.1f} |
| Avg Retention | {ctrl['avg_retention']:.1f}% | {treat['avg_retention']:.1f}% |
| Normalized Score | {ctrl.get('normalized_score', 0):.4f} | {treat.get('normalized_score', 0):.4f} |

## Scoring Methodology

Metrics are **min-max normalized** to [0,1] before weighting, so different scales
(e.g., 75% rate vs 500 views) don't distort the comparison.

- **Engaged view rate** ({int(weights.get('engaged_view_rate', 0.6)*100)}%): Best API proxy for YouTube Shorts "Viewed vs Swiped Away" — `engagedViews / views`
- **Subscribers gained per video** ({int(weights.get('subscribers_per_video', 0.25)*100)}%): Direct channel growth signal
- **Average views** ({int(weights.get('avg_views', 0.15)*100)}%): Distribution/reach indicator

## Recommendation

{'Set `' + experiment['config_key'] + ' = ' + str(summary['winner_value']) + '` in config.json.' if summary['is_significant'] else 'Insufficient data to draw conclusions. Consider re-running with a longer duration.'}
"""

    with open(report_path, 'w') as f:
        f.write(report)

    print(f"  📄 Conclusion report saved to {report_path}")


def record_video_result(experiment_id, video_id, views, engagement, retention,
                        engaged_view_rate=0.0, subscribers_gained=0):
    """Record a video's performance for the current variant."""
    data = load_experiments()

    for exp in data["experiments"]:
        if exp["id"] == experiment_id:
            variant = exp["current_variant"]
            results = exp["results"][variant]
            results["videos"].append({
                "video_id": video_id,
                "views": views,
                "engagement": engagement,
                "retention": retention,
                "engaged_view_rate": engaged_view_rate,
                "subscribers_gained": subscribers_gained,
                "date": datetime.now().isoformat()
            })
            results["total_views"] += views
            results["total_engagement"] += engagement
            results["total_subscribers_gained"] = results.get("total_subscribers_gained", 0) + subscribers_gained

            video_count = len(results["videos"])
            results["avg_retention"] = (
                (results["avg_retention"] * (video_count - 1) + retention) / video_count
            )
            results["avg_engaged_view_rate"] = (
                (results.get("avg_engaged_view_rate", 0) * (video_count - 1) + engaged_view_rate) / video_count
            )

            save_experiments(data)
            print(f"Recorded: {video_id} for {variant} in '{exp['name']}'")
            return

    print(f"Error: Experiment {experiment_id} not found")


def list_experiments():
    """List all experiments with status."""
    data = load_experiments()

    if not data["experiments"] and not data["completed"]:
        print("No experiments found.")
        return

    print("\n=== Active Experiments ===")
    for exp in data["experiments"]:
        variant, value = get_current_config_for_experiment(exp)
        control_videos = len(exp["results"]["control"]["videos"])
        treatment_videos = len(exp["results"]["treatment"]["videos"])
        print(f"\n  {exp['name']} ({exp['id']})")
        print(f"    Config: {exp['config_key']}")
        print(f"    Week {exp['current_week']}/{exp['duration_weeks']} - Current: {variant} ({value})")
        print(f"    Control videos: {control_videos}, Treatment videos: {treatment_videos}")

    if data["completed"]:
        print("\n=== Completed Experiments ===")
        for exp in data["completed"]:
            ctrl = exp["results"]["control"]
            treat = exp["results"]["treatment"]
            ctrl_avg_views = ctrl["total_views"] / max(len(ctrl["videos"]), 1)
            treat_avg_views = treat["total_views"] / max(len(treat["videos"]), 1)
            winner = "treatment" if treat_avg_views > ctrl_avg_views else "control"
            print(f"\n  {exp['name']} ({exp['id']})")
            print(f"    Control avg views: {ctrl_avg_views:.0f}, Treatment avg views: {treat_avg_views:.0f}")
            print(f"    Control retention: {ctrl['avg_retention']:.1f}%, Treatment retention: {treat['avg_retention']:.1f}%")
            print(f"    Winner: {winner}")


def main():
    parser = argparse.ArgumentParser(description="A/B Test Manager")
    subparsers = parser.add_subparsers(dest="command")

    create_parser = subparsers.add_parser("create", help="Create new experiment")
    create_parser.add_argument("--name", required=True)
    create_parser.add_argument("--config-key", required=True)
    create_parser.add_argument("--control", required=True)
    create_parser.add_argument("--treatment", required=True)
    create_parser.add_argument("--weeks", type=int, default=4)

    subparsers.add_parser("list", help="List all experiments")

    advance_parser = subparsers.add_parser("advance", help="Advance to next week")
    advance_parser.add_argument("--id", default=None)

    record_parser = subparsers.add_parser("record", help="Record video result")
    record_parser.add_argument("--id", required=True)
    record_parser.add_argument("--video-id", required=True)
    record_parser.add_argument("--views", type=int, required=True)
    record_parser.add_argument("--engagement", type=int, required=True)
    record_parser.add_argument("--retention", type=float, required=True)

    args = parser.parse_args()

    if args.command == "create":
        create_experiment(args.name, args.config_key, args.control, args.treatment, args.weeks)
    elif args.command == "list":
        list_experiments()
    elif args.command == "advance":
        advance_week(args.id)
    elif args.command == "record":
        record_video_result(args.id, args.video_id, args.views, args.engagement, args.retention)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
