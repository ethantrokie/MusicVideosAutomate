# JTBD Channel Improvements Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement 4 JTBD-driven improvements to the @learningsciencemusic YouTube channel pipeline: reframe topics as fascination snacks, fix format expectation mismatch, build for shareability, and reduce inauthentic content risk.

**Architecture:** Changes touch 4 layers of the pipeline: (1) topic generation prompt, (2) lyricist prompt + output schema, (3) Remotion overlay components + props builder, and (4) video assembly + upload metadata. Each improvement is independent at the code level but compounding in effect.

**Tech Stack:** Python (pipeline agents), TypeScript/React (Remotion overlays), Bash (upload script, pipeline orchestration)

**Spec:** `docs/superpowers/specs/2026-05-01-jtbd-channel-improvements-design.md`

---

## File Structure

### New Files
| File | Purpose |
|------|---------|
| `agents/remotion/src/compositions/MusicIndicator.tsx` | Animated equalizer bars overlay (first 5s) |
| `agents/remotion/src/compositions/ShareableStat.tsx` | End-card stat text overlay (last 2.5s) |
| `agents/voice_clip_mixer.py` | Select + mix human voice clips into audio |
| `assets/voice_clips/hooks/` | Directory for recorded hook voice clips |
| `assets/voice_clips/reactions/` | Directory for recorded reaction voice clips |
| `assets/voice_clips/outros/` | Directory for recorded outro voice clips |
| `tests/test_voice_clip_mixer.py` | Tests for voice clip selection + mixing |
| `tests/test_shareable_stat_props.py` | Tests for shareable stat in props pipeline |

### Modified Files
| File | Changes |
|------|---------|
| `automation/topic_generator.py` | Rewrite prompt to revelation-framing |
| `agents/prompts/lyricist_prompt.md` | Restructure to single-reveal + add `shareable_stat` output |
| `config/config.json` | Update `audio_trim.max_intro_seconds` to 0.5, add `voice_clips` config |
| `agents/remotion/src/types.ts` | Add `shareableStat` and `musicIndicatorEnabled` to OverlayProps |
| `agents/remotion/src/compositions/OverlayComposition.tsx` | Add MusicIndicator + ShareableStat layers |
| `agents/remotion_props_builder.py` | Pass `shareableStat` from lyrics.json, add `musicIndicatorEnabled` |
| `upload_to_youtube.sh` | Prepend shareable stat to description |
| `pipeline.sh` | Add weekday check (skip Sat/Sun) |
| `agents/5_assemble_video.py` | Integrate voice clip mixing |

---

## Task 1: Rewrite Topic Generator Prompt (Fascination Snacks)

**Files:**
- Modify: `automation/topic_generator.py:402-439`
- Create: `tests/test_topic_generator.py` (new file)

- [ ] **Step 1: Write test for revelation-framed topic format**

Create new test file:

```python
# tests/test_topic_generator.py
import subprocess
from unittest.mock import patch, MagicMock
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "automation"))


def test_topic_prompt_contains_revelation_framing():
    """Verify the prompt instructs Claude to generate revelation-framed topics."""
    import topic_generator as tg

    captured_prompt = {}

    def capture_prompt(*args, **kwargs):
        if args and len(args[0]) > 2:
            captured_prompt["text"] = args[0][2]  # -p prompt
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "Topic: The reason your dishwasher uses less water than hand washing\nTone: energetic pop punk"
        return mock_result

    minimal_config = {"topic_generation": {"categories": ["Physics", "Biology", "Engineering"]}}

    with patch("subprocess.run", side_effect=capture_prompt):
        with patch.object(tg, "check_topic_similarity", return_value=False):
            try:
                tg.generate_topic_via_claude(minimal_config, [], "")
            except Exception:
                pass

    prompt = captured_prompt.get("text", "")
    assert "revelation" in prompt.lower() or "surprising" in prompt.lower(), \
        f"Prompt should contain revelation framing. Got: {prompt[:200]}"
    assert "DO NOT" in prompt and ("How X works" in prompt or "process" in prompt.lower()), \
        "Prompt should explicitly tell Claude NOT to use process framing"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/ethantrokie/SoftwareDevProjects/MusicVideosAutomate && python3 -m pytest tests/test_topic_generator.py::test_topic_prompt_contains_revelation_framing -v 2>/dev/null || echo "EXPECTED FAIL"`

- [ ] **Step 3: Rewrite the topic generation prompt**

In `automation/topic_generator.py`, replace the prompt string (lines ~402-438) with:

```python
    prompt = f"""SYSTEM CONTEXT: This is an automated pipeline. Do NOT use brainstorming skills. Do NOT ask clarifying questions. Just generate the output directly.

You are a topic generator for educational science music videos. Generate ONE topic ONLY.
{trends_section}{category_section}{recent_topics_section}
REQUIREMENTS:
- Category: One of {categories}
- K-12 appropriate (ages 10-18)
- Visually interesting (stock footage available)
- EVERYDAY RELEVANCE: The topic MUST relate to something the viewer personally encounters in daily life (their car, phone, body, food, home appliances, workplace tools, the buildings they enter, the clothes they wear, etc.)
- UNIQUENESS: Your topic will be compared against recent videos listed below (DO NOT repeat)

TOPIC FRAMING - CRITICAL:
Frame every topic as a SINGLE SURPRISING REVELATION, not a process explanation.
- DO NOT write "How X works" or "How X is made"
- DO NOT write multi-step process topics (e.g., "The 12 steps of aluminum stamping")
- DO frame as: "The reason X does Y" or "Why X is actually Y" or "The hidden Z inside every W"
- The topic should make someone say "Wait, really?!" -- a single counterintuitive or mind-blowing fact

GOOD EXAMPLES (revelation-framed, everyday relevance):
- The reason your dishwasher actually uses less water than washing by hand
- Why the tiny holes in airplane windows keep you alive at 35,000 feet
- The hidden generator inside your car that charges itself every time you brake
- Why aluminum cans are thinner than a human hair yet hold 90 PSI of pressure
- The 1788 device inside every engine that prevents it from tearing itself apart

BAD EXAMPLES (process-framed, avoid these):
- How freeze-drying preserves food through sublimation
- How aluminum cans are manufactured through a 12-step stamping process
- How regenerative braking converts kinetic energy into electrical energy
- How solenoid valves control fluid flow through electromagnetic actuation

TOPIC VARIETY - Diversify across these categories (ranked by audience retention):
- Mechanical Engineering (TOP PERFORMER): Engines, brakes, hydraulic systems, pneumatic mechanisms, gear systems
- Biology (TOP PERFORMER, highest subscriber growth): Anatomy, physiology, cell processes, organ systems
- Computer Science (TOP PERFORMER): Microchip fabrication, algorithms, networking, data structures
- Electrical Engineering: Motors, transformers, circuits, power systems
- Manufacturing: Production processes, industrial systems, materials
- Physics: Waves, optics, motion, forces, thermodynamics
- Chemistry: Reactions, materials science, chemical processes

CRITICAL OUTPUT FORMAT - Output EXACTLY these two lines with no other text:
Topic: [single surprising revelation about an everyday thing]
Tone: [musical tone matched to the topic - see guidelines below]

{tone_guidelines}

{tone_examples}

CRITICAL: This is scenario 1 - an automated system. DO NOT brainstorm. DO NOT ask questions. DO NOT offer choices. DO NOT use markdown formatting. Choose a tone that MATCHES the topic category from the guidelines above. Just output the two lines directly.
Generate ONE topic now:"""
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_topic_generator.py::test_topic_prompt_contains_revelation_framing -v`
Expected: PASS

- [ ] **Step 5: Run full topic generator test suite**

Run: `python3 -m pytest tests/test_topic_generator.py -v`
Expected: All existing tests pass (prompt content change shouldn't break structural tests)

- [ ] **Step 6: Commit**

```bash
git add automation/topic_generator.py tests/test_topic_generator.py
git commit -m "feat: reframe topic generation to revelation-based fascination snacks

Update Claude prompt to generate single-revelation topics instead of
process explanations. Topics must relate to everyday objects/experiences."
```

---

## Task 2: Restructure Lyricist Prompt (Single Reveal + Shareable Stat)

**Files:**
- Modify: `agents/prompts/lyricist_prompt.md`

- [ ] **Step 1: Rewrite the VIRAL CONTENT STRUCTURE section**

Replace the existing 5-section structure (Hook, Deep Dive, Pivot, Surprise, Payoff) with:

```markdown
## VIRAL CONTENT STRUCTURE (REQUIRED)

Structure your lyrics to build toward ONE mind-blowing reveal. Do NOT walk through a multi-step process.

### 1. THE HOOK (First 5 seconds - Intro/Opening Lines)
**PURPOSE**: Stop the scroll. Make them HAVE to know what comes next.

Use one of these proven hook formulas:
- **Challenge their assumption**: "Everything you know about X is WRONG..."
- **Promise a revelation**: "Scientists just discovered WHY..."
- **Create urgency**: "This is happening RIGHT NOW and nobody's talking about it..."
- **Ask an impossible question**: "How can X do Y? It shouldn't be possible..."
- **Provocative statement**: "X is actually just Y in disguise..."

The hook MUST:
- Be surprising, counterintuitive, or challenge common knowledge
- Create an "information gap" they need to fill
- Be understandable WITHOUT context

### 2. THE SETUP (Verse 1 - ~15-25 seconds)
**PURPOSE**: Build what the viewer THINKS they know. Make them feel confident before pulling the rug.

- Use "you" language to make it personal: "Every time YOU step on the brakes..."
- Describe the everyday experience everyone recognizes
- Build false confidence: "You probably think X does Y..."
- Set up the contrast for the reveal that's coming
- End with a turn: "But here's what's actually happening..."

### 3. THE REVEAL (Chorus/Bridge - ~10-15 seconds)
**PURPOSE**: The single "holy shit" moment. This is the emotional climax of the entire video.

- Deliver ONE specific, mind-blowing fact with a concrete number or comparison
- This must be the most memorable moment: "Your brakes pump EIGHTEEN times per second"
- Make the scale visceral: compare to something relatable
- This line should be quotable and shareable on its own
- The listener should want to tell someone about THIS fact immediately

### 4. THE AFTERMATH (Verse 2 - ~10-15 seconds)
**PURPOSE**: "Now you'll never see X the same way again."

- Connect the reveal back to the viewer's daily life
- "Next time you press the brake pedal, remember..."
- "Every single time you open a can, this is happening..."
- Make them feel like they have insider knowledge now

### 5. THE PAYOFF (Outro - ~5-10 seconds)
**PURPOSE**: Satisfying close + drive sharing behavior.

- Validate: "Now YOU know the secret..."
- The listener should feel SMARTER than they did 60 seconds ago
- **SHARING CTA (REQUIRED)**: The last line MUST prompt sharing, not just commenting:
  - "Send this to someone who didn't know..." / "Share this before you forget..."
  - Make it feel like part of the song, not tacked on
```

- [ ] **Step 2: Add `shareable_stat` to the output format**

Replace the existing JSON output format section with:

```markdown
## Output Format
Write your output to `{{OUTPUT_PATH}}` in the following JSON format.

\`\`\`json
{
  "lyrics": "[Intro]\nLine 1\nLine 2\n\n[Verse 1]\nLine 3\n...",
  "music_prompt": "upbeat educational pop, energetic hooks, clear vocals, driving beat, catchy melody",
  "estimated_duration_seconds": 180,
  "structure": "intro-hook-verse1-chorus-verse2-outro",
  "key_facts_covered": [0, 1, 2, 3],
  "viral_elements": {
    "hook_type": "challenge_assumption | promise_revelation | impossible_question",
    "hook_line": "The exact opening line that stops the scroll",
    "display_hook_text": "3-7 word bold text overlay for frame 0 (e.g., 'Chocolate's DARK Secret?!')",
    "surprise_fact": "The mind-blowing fact in the reveal section",
    "shareable_stat": "A single sentence combining the most surprising number/fact with a relatable comparison. Example: 'Your brakes pump 18 times per second — faster than you can blink.' This will be displayed as the final text overlay in the video.",
    "quotable_lines": ["Line 1", "Line 2"],
    "payoff_feeling": "What the listener feels at the end"
  }
}
\`\`\`
```

- [ ] **Step 3: Update the CTA section**

In the ENGAGEMENT OPTIMIZATION RULES, update the sharing guidance to prefer share CTAs over comment CTAs (already handled by the new payoff section above -- verify no contradictions remain in the rest of the file).

- [ ] **Step 4: Commit**

```bash
git add agents/prompts/lyricist_prompt.md
git commit -m "feat: restructure lyricist to single-reveal format with shareable_stat

Replace 5-section process walkthrough with setup→reveal→aftermath structure.
Add shareable_stat output field for end-card overlay. Update CTA to
prioritize sharing over commenting."
```

---

## Task 3: Update Audio Trim Config (Music from Frame 1)

**Files:**
- Modify: `config/config.json`
- Verify: `agents/trim_audio.py` (already handles 0.5s via experiment, make it default)

- [ ] **Step 1: Update config**

In `config/config.json`, change:
```json
"audio_trim": {
    "enabled": true,
    "max_intro_seconds": 0.5
}
```

(Change from `2.0` to `0.5`)

- [ ] **Step 2: Verify trim_audio.py handles this correctly**

Read `agents/trim_audio.py` line 160-163 -- it already has logic to set `max_intro_seconds = 0.5` when the experiment is active. By setting the config default to 0.5, this becomes the permanent behavior regardless of experiment state. No code change needed in trim_audio.py.

- [ ] **Step 3: Run existing trim audio tests**

Run: `python3 -m pytest tests/test_trim_audio.py -v`
Expected: All pass (tests use their own config values, not the global config file)

- [ ] **Step 4: Commit**

```bash
git add config/config.json
git commit -m "feat: set audio trim to 0.5s max intro (music from frame 1)

Make aggressive audio trimming the default. Previously only active
during audio_pacing_overhaul experiment."
```

---

## Task 4: MusicIndicator Remotion Component

**Files:**
- Create: `agents/remotion/src/compositions/MusicIndicator.tsx`
- Modify: `agents/remotion/src/types.ts`
- Modify: `agents/remotion/src/compositions/OverlayComposition.tsx`

- [ ] **Step 1: Add types to OverlayProps**

In `agents/remotion/src/types.ts`, add `musicIndicatorEnabled` and `animateHook` (fixing pre-existing drift between Python builder and TypeScript interface) to OverlayProps:

```typescript
export interface OverlayProps {
  // ...existing fields...
  animateHook: boolean;
  musicIndicatorEnabled: boolean;
}
```

- [ ] **Step 2: Create MusicIndicator component**

Create `agents/remotion/src/compositions/MusicIndicator.tsx`:

```tsx
import React from "react";
import { useCurrentFrame, useVideoConfig, interpolate, spring } from "remotion";

interface MusicIndicatorProps {
  durationMs: number;
}

export const MusicIndicator: React.FC<MusicIndicatorProps> = ({ durationMs }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const totalFrames = Math.round((durationMs / 1000) * fps);

  // Fade in over first 0.5s, fade out over last 0.5s
  const fadeInFrames = Math.round(fps * 0.5);
  const fadeOutStart = totalFrames - Math.round(fps * 0.5);
  const opacity = interpolate(
    frame,
    [0, fadeInFrames, fadeOutStart, totalFrames],
    [0, 0.7, 0.7, 0],
    { extrapolateRight: "clamp" }
  );

  // 4 bars with different animation speeds
  const barConfigs = [
    { speed: 1.8, maxHeight: 60 },
    { speed: 2.5, maxHeight: 80 },
    { speed: 1.3, maxHeight: 50 },
    { speed: 2.1, maxHeight: 70 },
  ];

  return (
    <div
      style={{
        position: "absolute",
        bottom: "8%",
        left: "4%",
        display: "flex",
        alignItems: "flex-end",
        gap: 4,
        opacity,
      }}
    >
      {barConfigs.map((bar, i) => {
        const height = interpolate(
          Math.sin((frame / fps) * bar.speed * Math.PI),
          [-1, 1],
          [15, bar.maxHeight]
        );
        return (
          <div
            key={i}
            style={{
              width: 6,
              height: `${height}%`,
              backgroundColor: "white",
              borderRadius: 3,
              minHeight: 8,
              maxHeight: 40,
              transition: "height 0.05s ease",
            }}
          />
        );
      })}
    </div>
  );
};
```

- [ ] **Step 3: Add MusicIndicator to OverlayComposition**

In `agents/remotion/src/compositions/OverlayComposition.tsx`, add import and layer:

```tsx
import { MusicIndicator } from "./MusicIndicator";
```

Add between the hook text layer (Layer 3) and the existing layers, as a new layer:

```tsx
      {/* Layer 3b: Music indicator (first 5s) -- signals this is a music video */}
      {props.musicIndicatorEnabled && (
        <Sequence from={0} durationInFrames={Math.round(fps * 5)}>
          <MusicIndicator durationMs={5000} />
        </Sequence>
      )}
```

Also destructure `musicIndicatorEnabled` from props at the top of the component.

- [ ] **Step 4: Update props builder to pass musicIndicatorEnabled**

In `agents/remotion_props_builder.py`, in the `build_overlay_props` function return dict (line ~429), add:

```python
        "musicIndicatorEnabled": remotion_config.get("music_indicator_enabled", True),
```

- [ ] **Step 5: Add config flag**

In `config/config.json`, add to the `remotion_overlay` section:

```json
"music_indicator_enabled": true
```

- [ ] **Step 6: Commit**

```bash
git add agents/remotion/src/compositions/MusicIndicator.tsx agents/remotion/src/types.ts agents/remotion/src/compositions/OverlayComposition.tsx agents/remotion_props_builder.py config/config.json
git commit -m "feat: add MusicIndicator overlay to signal music video format

Animated equalizer bars in bottom-left corner for first 5 seconds.
Reduces viewer anxiety by setting music video expectation immediately."
```

---

## Task 5: ShareableStat Remotion Component + Props Pipeline

**Files:**
- Create: `agents/remotion/src/compositions/ShareableStat.tsx`
- Modify: `agents/remotion/src/types.ts`
- Modify: `agents/remotion/src/compositions/OverlayComposition.tsx`
- Modify: `agents/remotion_props_builder.py`
- Create: `tests/test_shareable_stat_props.py`

- [ ] **Step 1: Write failing test for shareable_stat in props builder**

```python
# tests/test_shareable_stat_props.py
import json
import tempfile
from pathlib import Path
from agents.remotion_props_builder import build_overlay_props


def test_shareable_stat_passed_from_lyrics_json():
    """shareable_stat from lyrics.json should appear in overlay props."""
    with tempfile.TemporaryDirectory() as tmp:
        run_dir = Path(tmp)

        # Minimal research.json
        (run_dir / "research.json").write_text(json.dumps({
            "video_title": "Test Video",
            "key_facts": ["fact1"],
        }))

        # lyrics.json with shareable_stat
        (run_dir / "lyrics.json").write_text(json.dumps({
            "lyrics": "[Intro]\nTest lyrics",
            "viral_elements": {
                "display_hook_text": "Test Hook",
                "shareable_stat": "Your brakes pump 18 times per second",
            }
        }))

        # Empty approved_media.json
        (run_dir / "approved_media.json").write_text(json.dumps({"shot_list": []}))

        config = {
            "video_settings": {"resolution": [1080, 1920], "fps": 30},
            "remotion_overlay": {
                "channel_name": "@test",
                "music_indicator_enabled": True,
                "karaoke_enabled": True,
                "edu_reveal_enabled": True,
                "transitions_enabled": False,
            },
        }

        props = build_overlay_props(run_dir, config, "full", 75000)
        assert props["shareableStat"] == "Your brakes pump 18 times per second"


def test_shareable_stat_empty_when_missing():
    """Props should have empty shareableStat when lyrics.json lacks it."""
    with tempfile.TemporaryDirectory() as tmp:
        run_dir = Path(tmp)

        (run_dir / "research.json").write_text(json.dumps({
            "video_title": "Test Video",
        }))

        (run_dir / "lyrics.json").write_text(json.dumps({
            "lyrics": "[Intro]\nTest",
            "viral_elements": {"display_hook_text": "Hook"},
        }))

        (run_dir / "approved_media.json").write_text(json.dumps({"shot_list": []}))

        config = {
            "video_settings": {"resolution": [1080, 1920], "fps": 30},
            "remotion_overlay": {
                "channel_name": "@test",
                "music_indicator_enabled": True,
                "karaoke_enabled": True,
                "edu_reveal_enabled": True,
                "transitions_enabled": False,
            },
        }

        props = build_overlay_props(run_dir, config, "full", 75000)
        assert props["shareableStat"] == ""
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_shareable_stat_props.py -v`
Expected: FAIL (no `shareableStat` key in props)

- [ ] **Step 3: Add shareableStat to types.ts**

In `agents/remotion/src/types.ts`, add to OverlayProps:

```typescript
export interface OverlayProps {
  // ...existing fields...
  shareableStat: string;
}
```

- [ ] **Step 4: Create ShareableStat component**

Create `agents/remotion/src/compositions/ShareableStat.tsx`:

```tsx
import React from "react";
import { useCurrentFrame, useVideoConfig, interpolate } from "remotion";

interface ShareableStatProps {
  text: string;
  durationMs: number;
}

export const ShareableStat: React.FC<ShareableStatProps> = ({ text, durationMs }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const totalFrames = Math.round((durationMs / 1000) * fps);

  // Fade in over first 0.3s
  const fadeInFrames = Math.round(fps * 0.3);
  const opacity = interpolate(frame, [0, fadeInFrames], [0, 1], {
    extrapolateRight: "clamp",
  });

  // Slight scale up on entry
  const scale = interpolate(frame, [0, fadeInFrames], [0.95, 1], {
    extrapolateRight: "clamp",
  });

  if (!text) return null;

  const fontSize = "5.5vh";

  return (
    <div
      style={{
        position: "absolute",
        bottom: "15%",
        left: "6%",
        right: "6%",
        display: "flex",
        justifyContent: "center",
        alignItems: "center",
        opacity,
        transform: `scale(${scale})`,
      }}
    >
      <div
        style={{
          backgroundColor: "rgba(0, 0, 0, 0.55)",
          borderRadius: 16,
          padding: "16px 28px",
          maxWidth: "90%",
        }}
      >
        <p
          style={{
            fontFamily: "'Bebas Neue', sans-serif",
            fontSize,
            fontWeight: 700,
            color: "white",
            textAlign: "center",
            lineHeight: 1.3,
            margin: 0,
            textShadow: "0 2px 8px rgba(0,0,0,0.6)",
            letterSpacing: "0.02em",
            textTransform: "uppercase",
          }}
        >
          {text}
        </p>
      </div>
    </div>
  );
};
```

- [ ] **Step 5: Add ShareableStat to OverlayComposition**

In `OverlayComposition.tsx`, add import:

```tsx
import { ShareableStat } from "./ShareableStat";
```

Add new layer between the karaoke subtitles (Layer 5) and end screen (Layer 6):

```tsx
      {/* Layer 5b: Shareable stat (last 2.5s, above karaoke, below end screen) */}
      {props.shareableStat && (
        <Sequence
          from={Math.round(((durationMs - 2500) / 1000) * fps)}
          durationInFrames={Math.round(fps * 2.5)}
        >
          <ShareableStat text={props.shareableStat} durationMs={2500} />
        </Sequence>
      )}
```

- [ ] **Step 6: Update props builder to read shareable_stat from lyrics.json**

In `agents/remotion_props_builder.py`, add a helper function before `build_overlay_props`:

```python
def _get_shareable_stat(run_dir: Path) -> str:
    """Extract shareable_stat from lyrics.json viral_elements."""
    lyrics_path = run_dir / "lyrics.json"
    if not lyrics_path.exists():
        return ""
    try:
        data = json.loads(lyrics_path.read_text())
        return data.get("viral_elements", {}).get("shareable_stat", "")
    except (json.JSONDecodeError, OSError):
        return ""
```

In the `build_overlay_props` return dict, add:

```python
        "shareableStat": _get_shareable_stat(run_dir),
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_shareable_stat_props.py -v`
Expected: PASS

- [ ] **Step 8: Run full props builder test suite**

Run: `python3 -m pytest tests/test_remotion_props_builder.py -v`
Expected: All pass

- [ ] **Step 9: Commit**

```bash
git add agents/remotion/src/compositions/ShareableStat.tsx agents/remotion/src/types.ts agents/remotion/src/compositions/OverlayComposition.tsx agents/remotion_props_builder.py tests/test_shareable_stat_props.py
git commit -m "feat: shareable stat end-card overlay for social sharing

Display the single most surprising fact as text overlay in last 2.5s.
Read from lyrics.json shareable_stat field, passed through props builder."
```

---

## Task 6: Update Upload Script (Shareable Stat in Description)

**Files:**
- Modify: `upload_to_youtube.sh`

- [ ] **Step 1: Read shareable_stat and prepend to description**

In `upload_to_youtube.sh`, after the topic is determined (around where the description template is built), add logic to read the shareable stat from lyrics.json:

```bash
# Read shareable stat from lyrics.json if available
SHAREABLE_STAT=""
LYRICS_PATH="${RUN_DIR}/lyrics.json"
if [ -f "$LYRICS_PATH" ]; then
    SHAREABLE_STAT=$(python3 -c "
import json, sys
try:
    with open(sys.argv[1]) as f:
        data = json.load(f)
    stat = data.get('viral_elements', {}).get('shareable_stat', '')
    print(stat)
except Exception:
    pass
" "$LYRICS_PATH" 2>/dev/null)
fi
```

Then prepend it to the description template. For the FULL video type, change the description from:

```bash
"Learn about ${TOPIC} through music!..."
```

to:

```bash
DESCRIPTION=""
if [ -n "$SHAREABLE_STAT" ]; then
    DESCRIPTION="${SHAREABLE_STAT}\n\n"
fi
DESCRIPTION="${DESCRIPTION}Learn about ${TOPIC} through music!..."
```

Apply the same prepend logic for all video type descriptions (SHORT_HOOK, SHORT_EDUCATIONAL, SHORT_INTRO).

- [ ] **Step 2: Commit**

```bash
git add upload_to_youtube.sh
git commit -m "feat: prepend shareable stat to YouTube video descriptions

First line of description is now the most surprising fact for
easy copy-paste when sharing."
```

---

## Task 7: Voice Clip Mixer Module

**Files:**
- Create: `agents/voice_clip_mixer.py`
- Create: `tests/test_voice_clip_mixer.py`
- Create: `assets/voice_clips/hooks/.gitkeep`
- Create: `assets/voice_clips/reactions/.gitkeep`
- Create: `assets/voice_clips/outros/.gitkeep`

- [ ] **Step 1: Create directory structure**

```bash
mkdir -p assets/voice_clips/hooks assets/voice_clips/reactions assets/voice_clips/outros
touch assets/voice_clips/hooks/.gitkeep assets/voice_clips/reactions/.gitkeep assets/voice_clips/outros/.gitkeep
```

- [ ] **Step 2: Write failing tests**

```python
# tests/test_voice_clip_mixer.py
import json
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest


def test_select_clips_returns_random_path():
    """select_clips should return a random file from the category directory."""
    from agents.voice_clip_mixer import select_clips

    with tempfile.TemporaryDirectory() as tmp:
        hooks_dir = Path(tmp) / "hooks"
        hooks_dir.mkdir()
        (hooks_dir / "hook_01.mp3").write_bytes(b"fake audio")
        (hooks_dir / "hook_02.mp3").write_bytes(b"fake audio")

        result = select_clips(hooks_dir, count=1)
        assert len(result) == 1
        assert result[0].suffix == ".mp3"
        assert result[0].parent == hooks_dir


def test_select_clips_returns_empty_for_missing_dir():
    """select_clips should return empty list if directory doesn't exist."""
    from agents.voice_clip_mixer import select_clips

    result = select_clips(Path("/nonexistent/dir"), count=1)
    assert result == []


def test_select_clips_no_duplicates():
    """select_clips with count=2 should return 2 different clips."""
    from agents.voice_clip_mixer import select_clips

    with tempfile.TemporaryDirectory() as tmp:
        hooks_dir = Path(tmp) / "hooks"
        hooks_dir.mkdir()
        for i in range(5):
            (hooks_dir / f"hook_{i:02d}.mp3").write_bytes(b"fake")

        result = select_clips(hooks_dir, count=2)
        assert len(result) == 2
        assert result[0] != result[1]


def test_mix_voice_clip_calls_ffmpeg():
    """mix_voice_clip should invoke ffmpeg to overlay voice on base audio."""
    from agents.voice_clip_mixer import mix_voice_clip

    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp) / "song.mp3"
        clip = Path(tmp) / "hook.mp3"
        output = Path(tmp) / "mixed.mp3"
        base.write_bytes(b"fake base")
        clip.write_bytes(b"fake clip")

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            mix_voice_clip(base, clip, position_seconds=0.0, output_path=output, volume=0.8)

            mock_run.assert_called_once()
            cmd = mock_run.call_args[0][0]
            assert "ffmpeg" in cmd[0] or "ffmpeg" in str(cmd)
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_voice_clip_mixer.py -v`
Expected: FAIL (module doesn't exist)

- [ ] **Step 4: Implement voice_clip_mixer.py**

```python
#!/usr/bin/env python3
"""
Select and mix human voice clips into video audio.

Provides human fingerprint variation to differentiate from
mass-produced AI content. Voice clips are pre-recorded by the creator
and stored in assets/voice_clips/{hooks,reactions,outros}/.
"""

import os
import random
import subprocess
import tempfile
from pathlib import Path
from typing import List, Optional

AUDIO_EXTENSIONS = {".mp3", ".wav", ".m4a", ".aac"}


def select_clips(category_dir: Path, count: int = 1) -> List[Path]:
    """Select random voice clips from a category directory.

    Args:
        category_dir: Directory containing voice clip audio files
        count: Number of clips to select (no duplicates)

    Returns:
        List of Paths to selected clips. Empty if dir missing or empty.
    """
    if not category_dir.exists():
        return []

    candidates = [
        f for f in category_dir.iterdir()
        if f.is_file() and f.suffix.lower() in AUDIO_EXTENSIONS
    ]

    if not candidates:
        return []

    count = min(count, len(candidates))
    return random.sample(candidates, count)


def mix_voice_clip(
    base_audio: Path,
    clip_path: Path,
    position_seconds: float,
    output_path: Path,
    volume: float = 0.8,
) -> bool:
    """Mix a voice clip into base audio at a specified position.

    Uses ffmpeg to overlay the clip on top of the base audio.
    The clip volume is relative to the base (0.0 to 1.0).

    Args:
        base_audio: Path to the base audio file (song.mp3)
        clip_path: Path to the voice clip to overlay
        position_seconds: Where to place the clip (seconds from start)
        output_path: Where to write the mixed result
        volume: Volume of the voice clip relative to base (0.0-1.0)

    Returns:
        True on success, False on failure.
    """
    delay_ms = int(position_seconds * 1000)

    cmd = [
        "ffmpeg", "-y",
        "-i", str(base_audio),
        "-i", str(clip_path),
        "-filter_complex",
        f"[1:a]adelay={delay_ms}|{delay_ms},volume={volume}[voice];"
        f"[0:a][voice]amix=inputs=2:duration=first:dropout_transition=0:normalize=0[out]",
        "-map", "[out]",
        "-acodec", "libmp3lame",
        "-q:a", "2",
        str(output_path),
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, timeout=60)
        if result.returncode != 0:
            print(f"  ⚠️ Voice clip mix failed: {result.stderr.decode()[:200]}")
            return False
        return output_path.exists() and output_path.stat().st_size > 0
    except (subprocess.TimeoutExpired, Exception) as e:
        print(f"  ⚠️ Voice clip mix error: {e}")
        return False
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_voice_clip_mixer.py -v`
Expected: PASS

- [ ] **Step 6: Add voice_clips config to config.json**

In `config/config.json`, add a new top-level section:

```json
"voice_clips": {
    "enabled": false,
    "hooks_dir": "assets/voice_clips/hooks",
    "reactions_dir": "assets/voice_clips/reactions",
    "outros_dir": "assets/voice_clips/outros",
    "hook_volume": 0.85,
    "reaction_volume": 0.75
}
```

Note: `enabled: false` by default -- will be switched to `true` once Ethan records the voice clips.

- [ ] **Step 7: Commit**

```bash
git add agents/voice_clip_mixer.py tests/test_voice_clip_mixer.py assets/voice_clips/ config/config.json
git commit -m "feat: voice clip mixer for human fingerprint variation

Module to randomly select and mix pre-recorded voice clips into
video audio. Feature-flagged (voice_clips.enabled) until recordings
are provided."
```

---

## Task 8: Integrate Voice Clips into Video Assembly

**Files:**
- Modify: `agents/5_assemble_video.py`

- [ ] **Step 1: Add voice clip mixing after audio load**

In `agents/5_assemble_video.py`, find where the audio is loaded and the final video is rendered. After the audio is loaded but before final render, add:

```python
    # Mix voice clips if enabled
    project_root = Path(__file__).resolve().parent.parent
    config_data = json.loads((project_root / "config" / "config.json").read_text())
    voice_config = config_data.get("voice_clips", {})

    if voice_config.get("enabled", False):
        try:
            from voice_clip_mixer import select_clips, mix_voice_clip

            hooks_dir = project_root / voice_config.get("hooks_dir", "assets/voice_clips/hooks")
            hook_clips = select_clips(hooks_dir, count=1)

            if hook_clips:
                mixed_path = output_dir / "song_with_voice.mp3"
                success = mix_voice_clip(
                    base_audio=song_path,
                    clip_path=hook_clips[0],
                    position_seconds=0.0,
                    output_path=mixed_path,
                    volume=voice_config.get("hook_volume", 0.85),
                )
                if success:
                    # Use the mixed version as the audio source (preserve original)
                    song_path = mixed_path
                    print(f"  🎤 Mixed voice clip: {hook_clips[0].name}")
                else:
                    print("  ⚠️ Voice clip mixing failed, using original audio")
        except Exception as e:
            print(f"  ⚠️ Voice clip integration skipped: {e}")
```

The exact insertion point depends on where `song_path` is defined and used -- insert after the audio file is finalized but before it's attached to the video clips.

- [ ] **Step 2: Commit**

```bash
git add agents/5_assemble_video.py
git commit -m "feat: integrate voice clip mixing into video assembly

When voice_clips.enabled is true, randomly selects a hook voice clip
and mixes it at position 0s over the song audio."
```

---

## Task 9: Add Weekday Check to Pipeline (Skip Weekends)

**Files:**
- Modify: `pipeline.sh`

- [ ] **Step 1: Add day-of-week check at top of pipeline.sh**

After the `set -e` line and before any stage processing, add:

```bash
# Skip weekends (date +%u: 1=Monday, 7=Sunday)
DAY_OF_WEEK=$(date +%u)
if [ "$DAY_OF_WEEK" -eq 6 ] || [ "$DAY_OF_WEEK" -eq 7 ]; then
    echo "📅 Skipping pipeline on weekend (day=$DAY_OF_WEEK)"
    exit 0
fi
```

- [ ] **Step 2: Commit**

```bash
git add pipeline.sh
git commit -m "feat: skip pipeline on weekends (5 uploads/week)

Reduces upload frequency from 7 to 5 per week. Exits cleanly
on Saturday and Sunday."
```

---

## Task 10: Integration Test - Full Pipeline Dry Run

**Files:**
- No new files -- verification step

- [ ] **Step 1: Verify all modified configs are valid JSON**

Run: `python3 -c "import json; json.load(open('config/config.json')); print('config OK')"`

- [ ] **Step 2: Verify Remotion TypeScript compiles**

Run: `cd agents/remotion && npx tsc --noEmit 2>&1 | head -20`
Expected: No errors (or only pre-existing ones)

- [ ] **Step 3: Run full test suite**

Run: `python3 -m pytest tests/ -v --tb=short 2>&1 | tail -30`
Expected: All tests pass

- [ ] **Step 4: Verify props builder produces valid output with new fields**

Run: `python3 -c "
from pathlib import Path
from agents.remotion_props_builder import build_overlay_props
# Just verify it doesn't crash with new fields
config = {'video_settings': {'resolution': [1080, 1920], 'fps': 30}, 'remotion_overlay': {'channel_name': '@test', 'music_indicator_enabled': True}}
import tempfile, json
with tempfile.TemporaryDirectory() as tmp:
    run_dir = Path(tmp)
    (run_dir / 'research.json').write_text(json.dumps({'video_title': 'Test'}))
    (run_dir / 'lyrics.json').write_text(json.dumps({'lyrics': 'test', 'viral_elements': {'shareable_stat': 'Test stat'}}))
    (run_dir / 'approved_media.json').write_text(json.dumps({'shot_list': []}))
    props = build_overlay_props(run_dir, config, 'full', 75000)
    assert 'shareableStat' in props
    assert 'musicIndicatorEnabled' in props
    print('Props builder OK:', list(props.keys()))
"`

- [ ] **Step 5: Final commit**

```bash
git add -A
git commit -m "chore: integration verification for JTBD channel improvements"
```

---

## Deferred Items (From Spec, Not in This Plan)

The following spec requirements are deferred to a follow-up PR to keep this plan focused and shippable:

1. **Thumbnail "MUSIC VIDEO" badge (Spec 2c):** Requires understanding the thumbnail generation pipeline (likely in `upload_to_youtube.sh` or a thumbnail agent). Low complexity but separate from the overlay/pipeline changes.

2. **Structural variation templates (Spec 4b):** The spec describes 4 structural templates (Standard, Reveal-first, Question-answer, Cold open) that vary overlay timing. This is a significant change to `remotion_props_builder.py` and needs its own design iteration to determine how template selection interacts with the existing A/B testing system.

3. **YouTube AI disclosure labels (Spec 4c):** Requires research on the exact YouTube Data API v3 field for AI content disclosure. Once the API field is identified, this is a small change to the upload script.

These are tracked as follow-up work and do not block shipping the core 4 improvements.
