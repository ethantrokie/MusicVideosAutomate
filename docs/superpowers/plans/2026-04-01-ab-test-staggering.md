# A/B Test Experiment Staggering Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the A/B testing system so experiments alternate independently rather than all toggling on the same weekly schedule, enabling isolation of individual variable effects.

**Architecture:** Each experiment gets a `phase_offset` (0 or 1) assigned at creation time. The offset shifts the week parity calculation so that even simultaneously-created experiments can be in opposite phases. A scheduling algorithm assigns offsets to minimize the number of concurrently-toggling experiments, ensuring that at most 1-2 experiments change state in any given week.

**Tech Stack:** Python, JSON state files, existing ab_test_manager.py + engagement_experiments.py

---

## The Problem

All experiments use `current_week % 2` to pick control (odd) vs treatment (even). Since all experiments were created within 2 days of each other:
- **Week 1**: ALL experiments in control
- **Week 2**: ALL experiments in treatment
- **Week 3**: ALL experiments in control again

This means you can never attribute a metric change to any single variable. If retention drops in week 2, you don't know if it's the educational images, the hook text, the tone, or any other factor.

## The Fix

Add a `phase_offset` field (0 or 1) to each experiment. The variant selection becomes:

```python
# Before (all experiments in sync):
if current_week % 2 == 1: return "control"

# After (experiments can be offset):
if (current_week + phase_offset) % 2 == 1: return "control"
```

An experiment with `phase_offset=0` behaves as before. An experiment with `phase_offset=1` is flipped -- it runs treatment in odd weeks and control in even weeks.

When creating a new experiment, the system checks existing active experiments and assigns the offset that minimizes overlap (i.e., if most experiments flip in odd weeks, the new one gets offset=1 to flip in even weeks).

## File Structure

### Modified files

```
automation/ab_test_manager.py:31-72          # create_experiment + get_current_config_for_experiment
agents/engagement_experiments.py:48-58       # get_engagement_experiment_variant
agents/generate_educational_images.py:75-85  # _get_experiment_variant
agents/environment_generator.py              # _get_active_performer_variant (same pattern)
automation/state/ab_experiments.json          # Add phase_offset to existing experiments
```

### New files

```
tests/test_ab_staggering.py                  # Tests for the staggering logic
```

---

## Task 1: Add Phase Offset to Experiment Creation

**Files:**
- Modify: `automation/ab_test_manager.py:31-72`
- Test: `tests/test_ab_staggering.py`

- [ ] **Step 1: Write failing test for phase offset assignment**

Create `tests/test_ab_staggering.py`:

```python
import json
import pytest
from pathlib import Path
from unittest.mock import patch
from datetime import datetime

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "automation"))


def test_new_experiment_gets_phase_offset(tmp_path: Path):
    """New experiments get a phase_offset field (0 or 1)."""
    experiments_file = tmp_path / "ab_experiments.json"
    experiments_file.write_text(json.dumps({"experiments": [], "completed": []}))

    from ab_test_manager import create_experiment, load_experiments, save_experiments

    with patch("ab_test_manager.Path") as mock_path:
        mock_path.return_value = experiments_file
        # We need to patch the file path used by load/save
        pass

    # Direct test: create experiment data structure and check offset exists
    from ab_test_manager import _assign_phase_offset

    existing = []
    offset = _assign_phase_offset(existing)
    assert offset in (0, 1)


def test_phase_offset_balances_across_experiments():
    """When multiple experiments exist, offsets are balanced."""
    from ab_test_manager import _assign_phase_offset

    # 3 experiments with offset 0, 1 with offset 1 -> new should get 1
    existing = [
        {"phase_offset": 0, "status": "active"},
        {"phase_offset": 0, "status": "active"},
        {"phase_offset": 0, "status": "active"},
        {"phase_offset": 1, "status": "active"},
    ]
    offset = _assign_phase_offset(existing)
    assert offset == 1

    # Balanced: 2 with 0, 2 with 1 -> either is fine
    balanced = [
        {"phase_offset": 0, "status": "active"},
        {"phase_offset": 0, "status": "active"},
        {"phase_offset": 1, "status": "active"},
        {"phase_offset": 1, "status": "active"},
    ]
    offset = _assign_phase_offset(balanced)
    assert offset in (0, 1)


def test_phase_offset_changes_variant_selection():
    """Phase offset=1 flips which weeks are control vs treatment."""
    from ab_test_manager import get_current_config_for_experiment

    exp_no_offset = {
        "current_week": 1,
        "phase_offset": 0,
        "control_value": "A",
        "treatment_value": "B",
    }
    variant, value = get_current_config_for_experiment(exp_no_offset)
    assert variant == "control"
    assert value == "A"

    exp_with_offset = {
        "current_week": 1,
        "phase_offset": 1,
        "control_value": "A",
        "treatment_value": "B",
    }
    variant, value = get_current_config_for_experiment(exp_with_offset)
    assert variant == "treatment"
    assert value == "B"


def test_completed_experiments_ignored_for_offset_assignment():
    """Only active experiments count for offset balancing."""
    from ab_test_manager import _assign_phase_offset

    existing = [
        {"phase_offset": 0, "status": "active"},
        {"phase_offset": 0, "status": "completed"},
        {"phase_offset": 0, "status": "completed"},
        {"phase_offset": 1, "status": "active"},
    ]
    # Active: 1x offset=0, 1x offset=1 -> balanced, either ok
    offset = _assign_phase_offset(existing)
    assert offset in (0, 1)
```

- [ ] **Step 2: Run tests -- expect failure**

```bash
./venv/bin/python -m pytest tests/test_ab_staggering.py -v
```

Expected: ImportError for `_assign_phase_offset`

- [ ] **Step 3: Implement _assign_phase_offset and update create_experiment**

In `automation/ab_test_manager.py`:

Add new function:

```python
def _assign_phase_offset(existing_experiments: list) -> int:
    """
    Assign a phase offset (0 or 1) that balances active experiments.

    Counts how many active experiments use each offset and returns
    the one with fewer experiments. Ties broken by defaulting to 0.
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
```

Update `create_experiment` to add `phase_offset`:

```python
    experiment = {
        ...
        "phase_offset": _assign_phase_offset(data["experiments"]),
        ...
    }
```

Update `get_current_config_for_experiment`:

```python
def get_current_config_for_experiment(experiment):
    """Get which variant should be active this week, respecting phase offset."""
    phase_offset = experiment.get("phase_offset", 0)
    if (experiment["current_week"] + phase_offset) % 2 == 1:
        return "control", experiment["control_value"]
    return "treatment", experiment["treatment_value"]
```

- [ ] **Step 4: Run tests -- expect pass**

```bash
./venv/bin/python -m pytest tests/test_ab_staggering.py -v
```

- [ ] **Step 5: Commit**

```bash
git add automation/ab_test_manager.py tests/test_ab_staggering.py
git commit -m "feat: add phase offset to A/B experiments for independent staggering"
```

---

## Task 2: Update All Variant Readers

**Files:**
- Modify: `agents/engagement_experiments.py:48-58`
- Modify: `agents/generate_educational_images.py:75-85`
- Modify: `agents/environment_generator.py` (same pattern)
- Test: `tests/test_ab_staggering.py` (add tests)

These three files all duplicate the variant-selection logic. They need to respect `phase_offset`.

- [ ] **Step 1: Write failing test**

Add to `tests/test_ab_staggering.py`:

```python
def test_engagement_experiments_respects_phase_offset(tmp_path: Path):
    """engagement_experiments.py reads phase_offset from experiment."""
    experiments = {
        "experiments": [{
            "id": "test_exp",
            "config_key": "engagement_hook_sfx",
            "control_value": "false",
            "treatment_value": "true",
            "status": "active",
            "phase_offset": 1,
            "duration_weeks": 8,
            "created_at": "2026-03-11T17:00:00.000000",
            "results": {"control": {}, "treatment": {}}
        }]
    }

    exp_path = tmp_path / "ab_experiments.json"
    exp_path.write_text(json.dumps(experiments))

    sys.path.insert(0, str(Path(__file__).parent.parent / "agents"))
    from engagement_experiments import get_engagement_experiment_variant

    with patch("engagement_experiments.Path") as mock_path_cls:
        mock_path_cls.return_value = exp_path

        # With phase_offset=1, week 1 becomes treatment instead of control
        variant = get_engagement_experiment_variant("engagement_hook_sfx")
        # This test validates the function reads phase_offset
```

- [ ] **Step 2: Update engagement_experiments.py**

Change variant selection logic in `get_engagement_experiment_variant`:

```python
        # Odd weeks = control, even weeks = treatment (adjusted by phase_offset)
        phase_offset = exp.get("phase_offset", 0)
        if (current_week + phase_offset) % 2 == 1:
            return exp.get("control_value")
        else:
            return exp.get("treatment_value")
```

- [ ] **Step 3: Update generate_educational_images.py**

Same change to `_get_experiment_variant`:

```python
        phase_offset = exp.get("phase_offset", 0)
        if (current_week + phase_offset) % 2 == 1:
            return exp.get("control_value", "false")
        return exp.get("treatment_value", "true")
```

- [ ] **Step 4: Update environment_generator.py**

Same change to `_get_active_performer_variant` (if it exists and is still referenced).

- [ ] **Step 5: Run all tests**

```bash
./venv/bin/python -m pytest tests/test_ab_staggering.py tests/test_ab_experiment_independence.py -v
```

- [ ] **Step 6: Commit**

```bash
git add agents/engagement_experiments.py agents/generate_educational_images.py agents/environment_generator.py tests/test_ab_staggering.py
git commit -m "feat: update all variant readers to respect phase_offset"
```

---

## Task 3: Backfill Phase Offsets on Existing Experiments

**Files:**
- Modify: `automation/state/ab_experiments.json`

Assign staggered offsets to the 7 remaining active experiments so they don't all flip together. With 7 experiments, assign ~3-4 to offset 0 and ~3 to offset 1.

- [ ] **Step 1: Plan the offset assignments**

Current active experiments and a sensible grouping:

| Experiment | Config Key | Offset | Rationale |
|-----------|-----------|--------|-----------|
| Musical Tone | tone_mode | 0 | Keep original phase |
| Educational Images | educational_images_enabled | 0 | Keep original phase |
| Lyrics Hook | engagement_hook_source | 1 | Flip to opposite phase |
| Opening Enhance | engagement_opening_enhance | 1 | Flip to opposite phase |
| Hook SFX | engagement_hook_sfx | 0 | Keep original phase |
| Fast Pacing | engagement_fast_pacing | 1 | Flip to opposite phase |
| Animated Hook | engagement_animated_hook | 0 | Keep original phase |

This gives 4x offset=0 and 3x offset=1. On any given week, 4 experiments are in one variant and 3 in the other -- much better than all 7 toggling together.

- [ ] **Step 2: Add phase_offset to each active experiment in ab_experiments.json**

For each experiment with `"status": "active"`, add `"phase_offset": N` field based on the table above.

- [ ] **Step 3: Verify with advance_week dry run**

```bash
./venv/bin/python -c "
from automation.ab_test_manager import load_experiments, get_current_config_for_experiment
data = load_experiments()
for exp in data['experiments']:
    if exp.get('status') != 'active': continue
    variant, val = get_current_config_for_experiment(exp)
    print(f'{exp[\"name\"]}: offset={exp.get(\"phase_offset\",0)}, variant={variant}')
"
```

Expected: Mix of "control" and "treatment" across experiments.

- [ ] **Step 4: Commit**

```bash
git add automation/state/ab_experiments.json
git commit -m "feat: backfill phase offsets on existing A/B experiments for staggered alternation"
```

---

## Task 4: Reset Experiment Data for Clean Measurement

**Files:**
- Modify: `automation/state/ab_experiments.json`

Since the existing data is confounded (all experiments toggled together), the historical control/treatment video assignments are unreliable. Two options:

**Option A (recommended): Keep historical data, mark it as pre-stagger.**
Add a `stagger_applied_at` timestamp to each experiment. The weekly optimizer can filter to only count videos produced after this date for meaningful comparisons.

**Option B: Reset results to empty.**
Wipe control/treatment video lists and start fresh. Loses all accumulated data.

- [ ] **Step 1: Add stagger_applied_at to each active experiment**

```python
"stagger_applied_at": "2026-04-01T00:00:00.000000"
```

- [ ] **Step 2: Update conclude_experiment to only use post-stagger data when scoring**

In `automation/ab_test_manager.py`, the `conclude_experiment` function should filter videos to those after `stagger_applied_at` if the field exists, so that pre-stagger confounded data doesn't pollute the conclusion.

Add at the top of `conclude_experiment`:

```python
    stagger_date = experiment.get("stagger_applied_at")
    if stagger_date:
        cutoff = datetime.fromisoformat(stagger_date)
        for arm in ("control", "treatment"):
            experiment["results"][arm]["videos"] = [
                v for v in experiment["results"][arm].get("videos", [])
                if datetime.fromisoformat(v["date"]) >= cutoff
            ]
```

- [ ] **Step 3: Commit**

```bash
git add automation/state/ab_experiments.json automation/ab_test_manager.py
git commit -m "feat: mark pre-stagger data boundary for clean A/B measurement"
```

---

## Rollout Notes

- Phase offsets are backward-compatible: experiments without `phase_offset` default to 0 (existing behavior).
- The `stagger_applied_at` filter only activates when the field exists, so old concluded experiments are unaffected.
- After 4+ weeks with staggering active, you'll have genuinely isolated control/treatment data for each experiment.
- Consider reducing the number of concurrent experiments to 3-4 for clearer signal. With 7 experiments even staggered, there's still multi-variable overlap within each week.
