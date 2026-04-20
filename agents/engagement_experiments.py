#!/usr/bin/env python3
"""
Shared helper for engagement A/B experiments.

Each engagement feature (hook source, opening enhance, hook SFX, fast pacing,
animated hook text) is gated behind an A/B experiment. This module provides a
single function to check whether a given engagement feature's experiment is
active and which variant (control/treatment) applies.

Pattern: identical to _get_experiment_variant() in generate_educational_images.py
and _get_active_performer_variant() in environment_generator.py.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Optional


def get_engagement_experiment_variant(config_key: str) -> Optional[str]:
    """
    Check if an engagement A/B experiment is active for the given config key.

    Uses calendar-based week computation (odd weeks = control, even = treatment).

    Args:
        config_key: The experiment config key, e.g. "engagement_hook_source"

    Returns:
        The variant value string if experiment is active, None otherwise.
    """
    experiments_path = Path("automation/state/ab_experiments.json")
    if not experiments_path.exists():
        return None

    try:
        with open(experiments_path) as f:
            data = json.load(f)
    except (json.JSONDecodeError, IOError):
        return None

    for exp in data.get("experiments", []):
        if exp.get("status") != "active":
            continue
        if exp.get("config_key") != config_key:
            continue

        created = datetime.fromisoformat(exp["created_at"])
        elapsed_days = (datetime.now() - created).days
        current_week = max(1, (elapsed_days // 7) + 1)

        if current_week > exp.get("duration_weeks", 8):
            continue

        # Odd weeks = control, even weeks = treatment (adjusted by phase_offset)
        phase_offset = exp.get("phase_offset", 0)
        if (current_week + phase_offset) % 2 == 1:
            return exp.get("control_value")
        else:
            return exp.get("treatment_value")

    return None


def is_engagement_feature_enabled(config_key: str, config: dict = None) -> bool:
    """
    Check if an engagement feature is enabled.

    Priority:
    1. A/B experiment (if active) — "true"/"false" string values
    2. Config value from engagement section
    3. Default: False (feature off unless explicitly enabled)

    Args:
        config_key: Experiment config key, e.g. "engagement_hook_sfx"
        config: Loaded config dict (optional, loads from disk if None)

    Returns:
        True if the feature should be active for this run.
    """
    # Check A/B experiment first
    variant = get_engagement_experiment_variant(config_key)
    if variant is not None:
        return variant == "true"

    # Fall back to config
    if config is None:
        config_path = Path("config/config.json")
        if config_path.exists():
            with open(config_path) as f:
                config = json.load(f)
        else:
            return False

    engagement = config.get("engagement", {})

    # Map experiment config keys to engagement config keys
    key_map = {
        "engagement_hook_source": "hook_source_lyrics",
        "engagement_opening_enhance": "opening_enhance_enabled",
        "engagement_hook_sfx": "hook_sfx_enabled",
        "engagement_fast_pacing": "fast_pacing_enabled",
        "engagement_animated_hook": "animated_hook_text",
    }

    config_field = key_map.get(config_key, config_key)
    return engagement.get(config_field, False)
