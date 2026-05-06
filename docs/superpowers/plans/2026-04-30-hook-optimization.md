# Hook Optimization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Dramatically improve first-3-second retention on YouTube Shorts by upgrading hook text, visuals, audio, and pacing -- bundled into two A/B experiments that run simultaneously with phase offsets.

**Architecture:** Two bundled A/B experiments run staggered. Experiment A ("Hook Overhaul") changes the text, visuals, and audio of the first 2 seconds. Experiment B ("Audio & Pacing") changes audio trimming and educational diagram placement. Each experiment uses the existing `phase_offset` system so they alternate independently. All changes are gated behind the experiment system -- when control, the current behavior is preserved exactly.

**Tech Stack:** Python (Claude CLI for hook generation), Remotion (TypeScript, HookText/TitleCard components), FFmpeg (audio SFX), existing A/B framework

---

## A/B Experiment Design

### Experiment A: "Hook Overhaul" (phase_offset=0)
**Control:** Current behavior (title-derived hook text, no SFX, no visual boost)
**Treatment:** All of these together:
- Claude-generated curiosity-gap hook text (from key facts, not title)
- Hook SFX (bright "pop" sound, not the current 200Hz thud)
- Opening saturation/contrast boost (1.35/1.20)

**NOT gated (applied to all videos):** Bigger text (96px hook, 64px title) and always-on animation. These are pure visual quality improvements -- bigger readable text and smooth entrance animation are always better, not worth A/B testing separately.

### Experiment B: "Audio & Pacing" (phase_offset=1)
**Control:** Current behavior (2.0s max intro, edu diagrams placed by phrase timing)
**Treatment:** Both of these together:
- Aggressive audio trim (0.5s max intro for shorts)
- First edu diagram placed at 1-2s (right after hook text fades)

---

## File Structure

### New files

```
agents/generate_hook_text.py                    # Claude-generated curiosity-gap hooks
tests/test_generate_hook_text.py                # Tests for hook generation
```

### Modified files

```
agents/remotion/src/compositions/HookText.tsx    # Bigger text, always-on animation
agents/remotion/src/compositions/TitleCard.tsx    # Bigger text
agents/remotion_props_builder.py                 # Wire curiosity-gap hook, early edu placement
agents/audio_utils.py                            # New hook SFX (pop instead of thud)
agents/5_assemble_video.py                       # Wire visual boost + SFX
agents/engagement_experiments.py                 # Add bundled experiment support
config/config.json                               # New experiment config
automation/state/ab_experiments.json              # Register the two new experiments
```

---

## Task 1: Curiosity-Gap Hook Text Generator

**Files:**
- Create: `agents/generate_hook_text.py`
- Create: `tests/test_generate_hook_text.py`

TDD: Tests first, then implementation.

- [ ] **Step 1: Write failing tests**

Create `tests/test_generate_hook_text.py`:

```python
import json
import pytest
from pathlib import Path
from unittest.mock import patch

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "agents"))


def test_generate_curiosity_hook_returns_short_text():
    from generate_hook_text import generate_curiosity_hook

    mock_response = "Did you know chocolate has 6 crystal forms?"

    with patch("generate_hook_text._call_claude_hook") as mock:
        mock.return_value = mock_response
        hook = generate_curiosity_hook(
            topic="How Chocolate Gets Its Snap",
            key_facts=["Chocolate has 6 possible crystal forms", "Only form V gives the perfect snap"],
        )

    assert hook is not None
    assert len(hook.split()) <= 10  # Max 10 words
    assert len(hook) <= 60  # Max 60 chars


def test_generate_curiosity_hook_falls_back_to_title():
    from generate_hook_text import generate_curiosity_hook

    with patch("generate_hook_text._call_claude_hook") as mock:
        mock.return_value = None  # Claude failed
        hook = generate_curiosity_hook(
            topic="How Chocolate Gets Its Snap",
            key_facts=["Chocolate has 6 forms"],
        )

    # Should fall back to title-derived hook
    assert hook is not None
    assert "?" in hook or "!" in hook


def test_generate_curiosity_hook_truncates_long_response():
    from generate_hook_text import generate_curiosity_hook

    long_response = "This is a really long hook text that has way too many words in it and needs to be truncated"

    with patch("generate_hook_text._call_claude_hook") as mock:
        mock.return_value = long_response
        hook = generate_curiosity_hook(
            topic="Test Topic",
            key_facts=["Test fact"],
        )

    assert len(hook.split()) <= 10


def test_title_derived_hook_patterns():
    from generate_hook_text import _title_derived_hook

    assert "?" in _title_derived_hook("How Chocolate Gets Its Snap") or "!" in _title_derived_hook("How Chocolate Gets Its Snap")
    assert "?" in _title_derived_hook("Why Ice Floats")
    assert _title_derived_hook("The Chemistry of Rust").endswith("?!")
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
./venv/bin/python -m pytest tests/test_generate_hook_text.py -v
```

- [ ] **Step 3: Implement generate_hook_text.py**

Create `agents/generate_hook_text.py`:

```python
#!/usr/bin/env python3
"""
Generate curiosity-gap hook text for YouTube Shorts first frame.

Uses Claude to transform key facts into attention-grabbing questions
that create an information gap the viewer needs to fill.
"""

import subprocess
import sys
from pathlib import Path
from typing import List, Optional

CLAUDE_CLI = "/Users/ethantrokie/.local/bin/claude"


def _call_claude_hook(topic: str, key_facts: List[str]) -> Optional[str]:
    """Call Claude Haiku to generate a curiosity-gap hook."""
    facts_str = "\n".join(f"- {f}" for f in key_facts[:5])

    prompt = f"""Generate a 3-8 word hook text for a YouTube Short about: {topic}

Key facts:
{facts_str}

The hook appears as bold text on frame 0 to stop scrolling. It must:
- Create a CURIOSITY GAP (make viewer NEED to know the answer)
- Be a question or surprising claim, NOT a topic statement
- Be 3-8 words maximum
- Use one of these patterns:
  * Surprising number: "99% of your body is empty space"
  * Counter-intuitive claim: "Ice is actually hot"
  * Challenge: "You can't explain why this works"
  * Specific + surprising: "6 crystal forms hide in chocolate"

BAD hooks (don't do these):
- "How X Works" (too generic, not curious)
- "X Explained" (boring, no gap)
- "Wait for it..." (overused)

Output ONLY the hook text, nothing else. No quotes, no explanation."""

    try:
        result = subprocess.run(
            [CLAUDE_CLI, "-p", prompt, "--model", "claude-haiku-4-5",
             "--dangerously-skip-permissions"],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except (subprocess.TimeoutExpired, Exception):
        pass
    return None


def _title_derived_hook(title: str) -> str:
    """Fallback: derive hook from title (current behavior)."""
    clean = title.replace(" Explained", "").replace(" (Music Video)", "").strip()
    lower = clean.lower()
    if lower.startswith("how "):
        return f"{clean[4:]}?!"
    elif lower.startswith(("why ", "what ")):
        return f"{clean}?"
    elif lower.startswith("the "):
        return f"{clean[4:]}?!"
    return f"{clean}?!"


def generate_curiosity_hook(
    topic: str,
    key_facts: List[str],
) -> str:
    """
    Generate a curiosity-gap hook for frame 0.

    Tries Claude first, falls back to title-derived hook.
    Always returns a string <= 10 words.
    """
    hook = _call_claude_hook(topic, key_facts)

    if hook:
        # Truncate to 10 words max
        words = hook.split()
        if len(words) > 10:
            hook = " ".join(words[:10])
        # Remove quotes if Claude wrapped them
        hook = hook.strip('"\'')
        return hook

    return _title_derived_hook(topic)
```

- [ ] **Step 4: Run tests**

```bash
./venv/bin/python -m pytest tests/test_generate_hook_text.py -v
```

- [ ] **Step 5: Commit**

```bash
git add agents/generate_hook_text.py tests/test_generate_hook_text.py
git commit -m "feat: curiosity-gap hook text generator using Claude Haiku"
```

---

## Task 2: Bigger, Bolder Text Components

**Files:**
- Modify: `agents/remotion/src/compositions/HookText.tsx`
- Modify: `agents/remotion/src/compositions/TitleCard.tsx`
- Modify: `agents/remotion/src/types.ts`

The hook text goes from 72px to 96px for shorts. The title goes from 48px to 64px. The animated pop-in becomes the default (not gated behind A/B).

- [ ] **Step 1: Update HookText.tsx**

Change font sizes:
```tsx
// Line 15: was 72/80, now 96/108
const fontSize = isShort ? 96 : 108;
```

Change stroke width for readability at larger size:
```tsx
// was 4px, now 5px
WebkitTextStroke: "5px black",
```

Make the animated entrance always on (remove the `animate` prop branch). The component always does the per-character stagger. Increase the stagger spring scale from 80%→100% to 85%→100% for smoother entrance at larger size.

- [ ] **Step 2: Update TitleCard.tsx**

Change font sizes:
```tsx
// Line 14: was 48/56, now 64/72
const fontSize = isShort ? 64 : 72;
```

Change stroke width:
```tsx
// was 3px, now 4px
WebkitTextStroke: "4px black",
```

- [ ] **Step 3: Update types.ts**

Remove `animateHook` from `OverlayProps` (animation is now always on, not A/B tested separately).

- [ ] **Step 4: Update OverlayComposition.tsx**

Remove the `animateHook` prop pass -- HookText always animates now (remove `animate={animateHook}` prop).

- [ ] **Step 5: Update Root.tsx**

Remove `animateHook: false` from `defaultProps` in `agents/remotion/src/Root.tsx` (line 17). Also remove it from the `calculateMetadata` return if present.

- [ ] **Step 6: Update render_remotion_overlays.py**

Remove line `props["animateHook"] = is_engagement_feature_enabled("engagement_animated_hook")` from `agents/render_remotion_overlays.py` (currently ~line 135). This is dead code after removing the prop.

- [ ] **Step 7: Run TypeScript check**

```bash
cd agents/remotion && npx tsc --noEmit
```

Verify no type errors from the removed prop.

- [ ] **Step 8: Commit**

```bash
git add agents/remotion/src/compositions/HookText.tsx agents/remotion/src/compositions/TitleCard.tsx agents/remotion/src/types.ts agents/remotion/src/compositions/OverlayComposition.tsx agents/remotion/src/Root.tsx agents/render_remotion_overlays.py
git commit -m "feat: bigger hook text (96px) and title (64px) with always-on animation"
```

---

## Task 3: Better Hook SFX

**Files:**
- Modify: `agents/audio_utils.py`

Replace the 200Hz bass thud with a brighter, attention-grabbing "pop" sound.

- [ ] **Step 1: Update generate_hook_sfx**

In `agents/audio_utils.py`, update `generate_hook_sfx`:

```python
def generate_hook_sfx(output_path: str = "/tmp/hook_sfx.wav") -> str:
    """
    Generate an attention-grabbing 'pop' sound for frame 0.

    Creates a bright, short pop using a 800Hz + 1200Hz layered tone
    with sharp attack and fast decay -- designed to cut through music
    and trigger attention without being annoying.
    """
    ffmpeg = _find_binary("ffmpeg")
    try:
        result = subprocess.run(
            [
                ffmpeg, "-y",
                "-f", "lavfi",
                "-i", "sine=frequency=800:duration=0.08",
                "-f", "lavfi",
                "-i", "sine=frequency=1200:duration=0.05",
                "-filter_complex",
                "[0]afade=t=out:d=0.08,volume=0.4[a];"
                "[1]afade=t=out:d=0.05,volume=0.25[b];"
                "[a][b]amix=inputs=2:duration=shortest",
                output_path,
            ],
            capture_output=True,
            timeout=10,
        )
        if result.returncode == 0:
            return output_path
    except Exception as e:
        print(f"    Hook SFX generation failed: {e}")
    return ""
```

Also increase default volume in config from 0.25 to 0.40.

**Experiment gate:** The SFX is already gated in `5_assemble_video.py` (line 666) via `is_engagement_feature_enabled("engagement_hook_sfx")`. Rewire this to check `hook_overhaul` instead:

```python
# In 5_assemble_video.py, change:
hook_sfx_enabled = is_engagement_feature_enabled("engagement_hook_sfx")
# To:
hook_sfx_enabled = is_engagement_feature_enabled("hook_overhaul")
```

Same for the opening enhancement gate (line 630):
```python
# Change:
enhance_opening = is_engagement_feature_enabled("engagement_opening_enhance")
# To:
enhance_opening = is_engagement_feature_enabled("hook_overhaul")
```

This means both SFX and visual boost are gated behind the single `hook_overhaul` experiment.

- [ ] **Step 2: Commit**

```bash
git add agents/audio_utils.py agents/5_assemble_video.py
git commit -m "feat: brighter pop SFX + rewire SFX and visual boost gates to hook_overhaul experiment"
```

---

## Task 4: Wire Curiosity Hook into Props Builder

**Files:**
- Modify: `agents/remotion_props_builder.py`
- Modify: `agents/render_remotion_overlays.py`
- Modify: `tests/test_remotion_props_builder.py`

When the "hook_overhaul" experiment is in treatment, use the curiosity-gap hook instead of the title-derived one.

- [ ] **Step 1: Write failing test**

Add to `tests/test_remotion_props_builder.py`:

```python
def test_curiosity_hook_used_when_experiment_active(tmp_path):
    """When hook_overhaul experiment is in treatment, use curiosity hook."""
    from remotion_props_builder import build_overlay_props
    from unittest.mock import patch

    (tmp_path / "research.json").write_text(json.dumps({
        "video_title": "How Chocolate Gets Its Snap",
        "key_facts": ["Chocolate has 6 crystal forms", "Only form V snaps"],
    }))
    (tmp_path / "phrase_groups.json").write_text(json.dumps([]))
    (tmp_path / "approved_media.json").write_text(json.dumps({"shot_list": []}))

    config = _make_minimal_config()

    # Mock at the import site (engagement_experiments module, not props builder)
    with patch("engagement_experiments.get_engagement_experiment_variant") as mock_exp:
        mock_exp.return_value = "true"  # Treatment = use curiosity hook
        with patch("remotion_props_builder._generate_curiosity_hook") as mock_hook:
            mock_hook.return_value = "6 crystal forms hide in your chocolate"
            props = build_overlay_props(tmp_path, config, "short_intro", 60000)

    assert props["hookText"] == "6 crystal forms hide in your chocolate"
```

- [ ] **Step 2: Implement in props builder**

In `agents/remotion_props_builder.py`, update `_get_hook_text` to check for the experiment:

```python
def _get_hook_text(run_dir: Path, title: str) -> str:
    """Generate hook text. Uses curiosity-gap when experiment is active."""
    # Check if hook_overhaul experiment is in treatment
    from engagement_experiments import is_engagement_feature_enabled
    use_curiosity = is_engagement_feature_enabled("hook_overhaul")

    if use_curiosity:
        hook = _generate_curiosity_hook(run_dir, title)
        if hook:
            return hook

    # Fall back to existing lyrics/title-derived logic
    # ... existing code ...
```

Add `_generate_curiosity_hook` helper:

```python
def _generate_curiosity_hook(run_dir: Path, title: str) -> Optional[str]:
    """Generate a curiosity-gap hook using Claude."""
    try:
        from generate_hook_text import generate_curiosity_hook
        research = _read_json(run_dir / "research.json")
        key_facts = research.get("key_facts", [])
        topic = research.get("video_title", title)
        if key_facts:
            return generate_curiosity_hook(topic, key_facts)
    except Exception:
        pass
    return None
```

- [ ] **Step 3: Run tests**

```bash
./venv/bin/python -m pytest tests/test_remotion_props_builder.py -v
```

- [ ] **Step 4: Commit**

```bash
git add agents/remotion_props_builder.py tests/test_remotion_props_builder.py
git commit -m "feat: wire curiosity-gap hook into props builder with experiment gate"
```

---

## Task 5: Update Config Values

**Files:**
- Modify: `config/config.json`

The experiment gate rewiring for visual boost and SFX was done in Task 3. This task just updates the config default values so the boost is stronger when active.

- [ ] **Step 1: Update config defaults**

In `config/config.json`, update engagement section:

```json
"opening_saturation": 1.35,
"opening_contrast": 1.20,
"opening_brightness": 1.05,
"hook_sfx_volume": 0.40,
```

- [ ] **Step 2: Commit**

```bash
git add config/config.json
git commit -m "feat: stronger opening visual boost values (saturation 1.35, contrast 1.20, SFX volume 0.40)"
```

---

## Task 6: Aggressive Audio Trim for Shorts

**Files:**
- Modify: `agents/trim_audio.py`
- Modify: `config/config.json`

When experiment B is in treatment, trim audio intros to 0.5s max instead of 2.0s.

- [ ] **Step 1: Update trim_audio.py**

In the `run_trim` function, check for the experiment:

At the top of `run_trim`, before using `max_intro_seconds`:

```python
    # Check if aggressive trim experiment is active
    try:
        from engagement_experiments import is_engagement_feature_enabled
        if is_engagement_feature_enabled("audio_pacing_overhaul"):
            max_intro_seconds = 0.5
            print(f"  🧪 Experiment: Aggressive audio trim (0.5s max intro)")
    except Exception:
        pass
    # ... rest of existing function uses max_intro_seconds
```

Note: `sys.path.insert` is already done at the top of `trim_audio.py` so the import works without adding it again.

- [ ] **Step 2: Commit**

```bash
git add agents/trim_audio.py
git commit -m "feat: aggressive audio trim (0.5s) when audio_pacing experiment active"
```

---

## Task 7: Early Educational Diagram Placement

**Files:**
- Modify: `agents/remotion_props_builder.py`

When experiment B is in treatment, shift the first educational diagram to start at 2.0s (right after hook text fades).

- [ ] **Step 1: Update _build_edu_diagrams or the shift logic**

In `build_overlay_props`, after building edu diagrams, check for the experiment:

```python
    # Experiment B treatment: place first edu diagram early (at 2s)
    from engagement_experiments import is_engagement_feature_enabled
    if is_engagement_feature_enabled("audio_pacing_overhaul") and edu_diagrams:
        # Move first diagram to start right after hook text (2.0s)
        first = edu_diagrams[0]
        original_duration = first["endMs"] - first["startMs"]
        edu_diagrams = [
            {**first, "startMs": 2000, "endMs": 2000 + original_duration},
            *edu_diagrams[1:],
        ]
```

- [ ] **Step 2: Commit**

```bash
git add agents/remotion_props_builder.py
git commit -m "feat: early edu diagram placement (2s) when pacing experiment active"
```

---

## Task 8: Register A/B Experiments

**Files:**
- Modify: `automation/state/ab_experiments.json`
- Modify: `agents/engagement_experiments.py`

Create two new bundled experiments and deactivate the old individual engagement experiments (which never showed results since they all toggled together).

- [ ] **Step 1: Add experiment key mappings**

In `agents/engagement_experiments.py`, add new key mappings:

```python
    key_map = {
        # ... existing mappings ...
        "hook_overhaul": "hook_overhaul_enabled",
        "audio_pacing_overhaul": "audio_pacing_overhaul_enabled",
    }
```

- [ ] **Step 2: Add new experiments to ab_experiments.json**

Add two new experiments:

```json
{
    "id": "exp_20260430_hook_overhaul",
    "name": "Hook Overhaul: Curiosity Text + Big Bold + Pop SFX + Visual Boost",
    "config_key": "hook_overhaul",
    "control_value": "false",
    "treatment_value": "true",
    "duration_weeks": 12,
    "created_at": "2026-04-30T00:00:00.000000",
    "status": "active",
    "phase_offset": 0,
    "stagger_applied_at": "2026-04-30T00:00:00.000000",
    "current_week": 1,
    "current_variant": "control",
    "results": {
        "control": {"videos": [], "total_views": 0, "total_engagement": 0, "avg_retention": 0, "avg_engaged_view_rate": 0, "total_subscribers_gained": 0},
        "treatment": {"videos": [], "total_views": 0, "total_engagement": 0, "avg_retention": 0, "avg_engaged_view_rate": 0, "total_subscribers_gained": 0}
    }
},
{
    "id": "exp_20260430_audio_pacing",
    "name": "Audio & Pacing: Aggressive Trim + Early Edu Diagram",
    "config_key": "audio_pacing_overhaul",
    "control_value": "false",
    "treatment_value": "true",
    "duration_weeks": 12,
    "created_at": "2026-04-30T00:00:00.000000",
    "status": "active",
    "phase_offset": 1,
    "stagger_applied_at": "2026-04-30T00:00:00.000000",
    "current_week": 1,
    "current_variant": "control",
    "results": {
        "control": {"videos": [], "total_views": 0, "total_engagement": 0, "avg_retention": 0, "avg_engaged_view_rate": 0, "total_subscribers_gained": 0},
        "treatment": {"videos": [], "total_views": 0, "total_engagement": 0, "avg_retention": 0, "avg_engaged_view_rate": 0, "total_subscribers_gained": 0}
    }
}
```

- [ ] **Step 3: Conclude old individual experiments**

Mark the old individual engagement experiments (hook_source, opening_enhance, hook_sfx, fast_pacing, animated_hook) as `"status": "concluded"` with reason: "Replaced by bundled Hook Overhaul and Audio & Pacing experiments."

- [ ] **Step 4: Commit**

```bash
git add agents/engagement_experiments.py automation/state/ab_experiments.json
git commit -m "feat: register Hook Overhaul and Audio & Pacing A/B experiments"
```

---

## Task 9: End-to-End Test

**Files:** None (validation only)

- [ ] **Step 1: Run full pipeline on recent run with treatment active**

Temporarily force treatment for both experiments:

```bash
export OUTPUT_DIR=outputs/runs/20260420_090022
./venv/bin/python3 -c "
# Force both experiments to treatment for testing
import json
with open('automation/state/ab_experiments.json') as f:
    data = json.load(f)
for exp in data['experiments']:
    if exp['config_key'] in ('hook_overhaul', 'audio_pacing_overhaul'):
        exp['current_variant'] = 'treatment'
        exp['current_week'] = 2  # Even week = treatment
with open('automation/state/ab_experiments.json', 'w') as f:
    json.dump(data, f, indent=2)
"
```

- [ ] **Step 2: Rebuild video with all hook improvements**

```bash
./venv/bin/python3 agents/build_multiformat_videos.py
./venv/bin/python3 agents/render_remotion_overlays.py --run-dir=$OUTPUT_DIR --format=short_intro --video=$OUTPUT_DIR/short_intro.mp4 --duration-ms=60000
```

- [ ] **Step 3: Extract first-frame screenshots**

```bash
ffmpeg -y -ss 0.0 -i $OUTPUT_DIR/short_intro.mp4 -frames:v 1 /tmp/hook_frame0.png
ffmpeg -y -ss 0.5 -i $OUTPUT_DIR/short_intro.mp4 -frames:v 1 /tmp/hook_frame05.png
ffmpeg -y -ss 2.0 -i $OUTPUT_DIR/short_intro.mp4 -frames:v 1 /tmp/hook_frame2.png
ffmpeg -y -ss 3.0 -i $OUTPUT_DIR/short_intro.mp4 -frames:v 1 /tmp/hook_frame3.png
```

Verify:
- Frame 0: Large 96px yellow hook text visible (curiosity-gap question)
- Frame 0.5: Characters staggering in with spring animation
- Frame 2.0: Hook text fading out, title visible
- Frame 3.0: Educational diagram appearing (early placement)
- Audio: Pop SFX audible at t=0, music starts immediately (aggressive trim)

- [ ] **Step 4: Restore experiment state**

```bash
# Reset to proper calendar-based alternation
./venv/bin/python3 -c "
import json
with open('automation/state/ab_experiments.json') as f:
    data = json.load(f)
for exp in data['experiments']:
    if exp['config_key'] in ('hook_overhaul', 'audio_pacing_overhaul'):
        exp['current_week'] = 1
        exp['current_variant'] = 'control'
with open('automation/state/ab_experiments.json', 'w') as f:
    json.dump(data, f, indent=2)
"
```

- [ ] **Step 5: Run full test suite**

```bash
./venv/bin/python -m pytest tests/ -v
```

- [ ] **Step 6: Open video for review**

```bash
open $OUTPUT_DIR/short_intro.mp4
```
