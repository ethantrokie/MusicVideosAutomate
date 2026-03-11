#!/Users/ethantrokie/SoftwareDevProjects/MusicVideosAutomate/venv/bin/python3
"""
A/B Test Manager for YouTube channel optimization.
Manages experiments by alternating configurations and tracking results.
"""

import json
import argparse
from pathlib import Path
from datetime import datetime


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
        "current_week": 1,
        "current_variant": "control",
        "results": {
            "control": {"videos": [], "total_views": 0, "total_engagement": 0, "avg_retention": 0},
            "treatment": {"videos": [], "total_views": 0, "total_engagement": 0, "avg_retention": 0}
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
    if experiment["current_week"] % 2 == 1:
        return "control", experiment["control_value"]
    return "treatment", experiment["treatment_value"]


def sync_experiment_week(experiment):
    """
    Compute the correct week number from the experiment's creation date.
    This is resilient to missed runs (machine off, skipped Sundays) —
    the week is always derived from elapsed calendar time, not incremented.

    Returns:
        The calculated week number (1-based).
    """
    created = datetime.fromisoformat(experiment["created_at"])
    elapsed_days = (datetime.now() - created).days
    return max(1, (elapsed_days // 7) + 1)


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

        if correct_week > exp["duration_weeks"]:
            exp["status"] = "completed"
            print(f"  Experiment completed! Moving to results.")
            data["completed"].append(exp)

    data["experiments"] = [e for e in data["experiments"] if e["status"] == "active"]
    save_experiments(data)


def record_video_result(experiment_id, video_id, views, engagement, retention):
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
                "date": datetime.now().isoformat()
            })
            results["total_views"] += views
            results["total_engagement"] += engagement

            video_count = len(results["videos"])
            results["avg_retention"] = (
                (results["avg_retention"] * (video_count - 1) + retention) / video_count
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
