#!/usr/bin/env python3
"""
Experiment snapshot utility.

Captures which variant of every active A/B experiment was used when
producing a video. Saved to {OUTPUT_DIR}/experiment_snapshot.json so the
weekly optimizer can attribute metrics to the correct variant bucket —
even if the experiment has since advanced to a different week.

This is critical for experiment independence: when multiple experiments
run concurrently, each video's result must be attributed to the exact
combination of variants it was produced under.
"""

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "automation"))
from output_helper import get_output_path
from ab_test_manager import compute_gap_days


def compute_variant_for_experiment(experiment: Dict) -> Dict:
    """
    Compute the current variant for a single experiment, adjusted for
    production gaps so that downtime extends the experiment rather than
    consuming variant windows.

    Returns:
        Dict with config_key, variant ("control"/"treatment"), and value.
        None if the experiment has expired.
    """
    created = datetime.fromisoformat(experiment["created_at"])
    elapsed_days = (datetime.now() - created).days
    gap_days = compute_gap_days(experiment)
    effective_days = max(0, elapsed_days - gap_days)
    current_week = max(1, (effective_days // 7) + 1)

    if current_week > experiment.get("duration_weeks", 4):
        return None  # Expired

    if current_week % 2 == 1:
        variant = "control"
        value = experiment.get("control_value")
    else:
        variant = "treatment"
        value = experiment.get("treatment_value")

    return {
        "experiment_id": experiment["id"],
        "experiment_name": experiment["name"],
        "config_key": experiment["config_key"],
        "variant": variant,
        "value": value,
        "week": current_week,
    }


def snapshot_active_experiments() -> Dict:
    """
    Capture the current variant state of all active experiments.

    Returns:
        Dict mapping config_key -> variant info, plus metadata.
    """
    experiments_path = Path("automation/state/ab_experiments.json")
    if not experiments_path.exists():
        return {"experiments": {}, "snapshot_at": datetime.now().isoformat()}

    try:
        with open(experiments_path) as f:
            data = json.load(f)
    except (json.JSONDecodeError, IOError):
        return {"experiments": {}, "snapshot_at": datetime.now().isoformat()}

    experiments = {}
    for exp in data.get("experiments", []):
        if exp.get("status") != "active":
            continue

        variant_info = compute_variant_for_experiment(exp)
        if variant_info is None:
            continue

        experiments[variant_info["config_key"]] = variant_info

    return {
        "experiments": experiments,
        "snapshot_at": datetime.now().isoformat(),
    }


def save_snapshot() -> Path:
    """
    Save experiment snapshot to the current output directory.

    Returns:
        Path to the saved snapshot file.
    """
    snapshot = snapshot_active_experiments()
    output_path = get_output_path("experiment_snapshot.json")
    with open(output_path, 'w') as f:
        json.dump(snapshot, f, indent=2)

    exp_count = len(snapshot["experiments"])
    if exp_count > 0:
        print(f"  Saved experiment snapshot ({exp_count} active experiments):")
        for key, info in snapshot["experiments"].items():
            print(f"    {key}: {info['variant']} ({info['value']})")
    else:
        print("  No active experiments to snapshot")

    return output_path


def main() -> int:
    print("Saving A/B experiment snapshot...")
    save_snapshot()
    return 0


if __name__ == "__main__":
    sys.exit(main())
