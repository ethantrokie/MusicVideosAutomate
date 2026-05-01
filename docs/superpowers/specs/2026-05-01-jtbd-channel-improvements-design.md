# JTBD Channel Improvements - Design Spec

## Context

Based on a Jobs-to-be-Done analysis of @learningsciencemusic (see `docs/JTBD_CHANNEL_ANALYSIS.md`), this spec implements 4 improvements to better serve viewer jobs and reduce platform risk.

**Branch:** `feature/jtbd-channel-improvements`

---

## Improvement 1: Reframe to "Fascination Snacks"

### Problem
The channel tries to teach multi-step processes (e.g., "12 steps of aluminum can stamping"). Data shows multi-step process videos have the lowest retention (21.83%, 0%), while single-revelation videos have the highest views and retention. The functional job ("learn how X works") is overserved by competitors like Lesics (4.5M subs). The underserved emotional job is "give me a 60-second 'holy shit' moment."

### Changes

#### 1a. Topic Generator (`automation/topic_generator.py`)

**Current behavior:** Generates process-framed topics like "How freeze-drying preserves food through sublimation."

**New behavior:** Generates revelation-framed topics like "The reason astronaut food lasts 25 years without refrigeration."

**Changes to the Claude prompt (lines ~402-439):**
- Replace the topic format instruction from "explain how X works" to "frame as a single surprising revelation about something people encounter daily"
- Add an "everyday relevance" requirement: the topic must relate to something the viewer has personally encountered (their car, their phone, their food, their body, their home appliances, their workplace, etc.)
- Add negative examples: "Do NOT generate multi-step process topics. Do NOT frame as 'How X works.' Instead, frame as 'The reason X does Y' or 'Why X is actually Y.'"
- Keep all existing dedup, category spacing, and trend logic unchanged

**Output format change:** The topic line in `input/idea.txt` should now be revelation-framed. No structural change to the file format.

**Examples of old vs. new topics:**

| Old (Process) | New (Revelation) |
|---------------|-----------------|
| How freeze-drying preserves food through sublimation | The reason astronaut food lasts 25 years without refrigeration |
| How aluminum cans are manufactured through stamping | Why aluminum cans are thinner than a human hair yet hold 90 PSI |
| How regenerative braking converts kinetic energy | The hidden generator inside your car that charges itself every time you brake |
| How solenoid valves control fluid flow | The tiny magnet that decides when your dishwasher gets water |

#### 1b. Lyricist Prompt (`agents/prompts/lyricist_prompt.md`)

**Current behavior:** The VIRAL CONTENT STRUCTURE section instructs the lyricist to walk through a full process with a hook, deep dive, pivot, surprise, and payoff.

**New behavior:** Restructure to build toward ONE "holy shit" moment:
1. **Hook (0-5s):** Same curiosity-gap formulas (keep these, they work)
2. **Setup (15-25s):** Build context -- what the viewer thinks they know. Use "you" language to make it personal.
3. **The Reveal (10-15s):** The single mind-blowing fact. This is the emotional climax. Must be a specific number, comparison, or counterintuitive truth.
4. **Aftermath (10-15s):** What this means for the viewer. "Next time you X, remember that Y."
5. **Payoff (5-10s):** Engagement CTA

**New required output field in lyrics.json:**
```json
{
  "viral_elements": {
    ...existing fields...,
    "shareable_stat": "Your brakes pump 18 times per second -- faster than you can blink"
  }
}
```

The `shareable_stat` is a single sentence combining the most surprising fact with a relatable comparison. This field will be used by the video assembly for the end-card overlay (Improvement 3).

---

## Improvement 2: Fix Format Expectation Mismatch

### Problem
Viewers click curiosity-gap titles expecting a visual explainer and get surprised by a song. This is the #1 anxiety force causing drop-off. Current retention (44.65%) is below the 50-65% benchmark for educational Shorts.

### Changes

#### 2a. Music starts at frame 1

**Current behavior:** The Hook Overhaul experiment places a text curiosity hook over the first 3 seconds. The music may or may not start immediately depending on Suno's generated intro (some songs have 1-3 second instrumental intros, some start with vocals).

**New behavior:** The audio MUST start at frame 0 of the final rendered video. The existing `audio_trim` feature (which trims silent/low-energy intros) already helps with this. We need to ensure it's aggressive enough:

**Change in `config/config.json`:**
```json
"audio_trim": {
  "enabled": true,
  "max_intro_seconds": 0.5  // was 2.0 -- trim to <=0.5s of intro
}
```

**Change in `agents/trim_audio.py`:** Verify the trim logic handles the tighter threshold. If the audio has a gradual fade-in rather than silence, ensure the energy threshold catches it. Current threshold should be checked and potentially lowered.

#### 2b. Visual "music video" indicator

**Current behavior:** No visual indicator that this is a music video. The hook text overlay appears but looks like a standard text-on-screen Short.

**New behavior:** Add a small visual indicator in the first 3-5 seconds that signals "this is a music video." Two elements:

1. **Waveform/music note icon:** A small animated waveform bars icon (3 bars, ~40px) in the bottom-left corner during the first 5 seconds. Fades out after the hook text exits.

2. **Hook text styling update:** Add a subtle music-related visual treatment to the existing hook text pill background -- a very faint waveform pattern or musical note watermark inside the pill. This should be subtle enough not to distract but enough to subconsciously signal "music."

**Implementation in Remotion:**
- New component: `MusicIndicator.tsx` -- small animated equalizer bars (3-4 bars bouncing at different rates)
- Added to `OverlayComposition.tsx` layer stack, positioned bottom-left, z-index below hook text
- Duration: first 5 seconds, with 0.5s fade-in and 0.5s fade-out
- Size: ~40x40px equivalent, white with slight transparency

#### 2c. Thumbnail update

**Current behavior:** Thumbnails are auto-generated from the best video frame + text overlay + channel logo. No indication it's a music video.

**New behavior:** Add a small "MUSIC VIDEO" badge or waveform icon to generated thumbnails. This sets expectations BEFORE the click.

**Implementation:** Update the thumbnail generation logic to composite a small badge in the corner. This is a lightweight change to whichever script generates thumbnails (likely in the upload flow).

---

## Improvement 3: Build for Shareability

### Problem
Engagement rate is 0.74% vs. 5.9-9% educational benchmark. The social job ("give me conversation currency") is almost entirely unserved. YouTube's 2026 algorithm weights shares 5x more than likes.

### Changes

#### 3a. Shareable stat end card

**Current behavior:** Videos end with the song ending and possibly a channel end screen animation.

**New behavior:** The last 2-3 seconds of the video overlay the `shareable_stat` (from the lyricist's new output field) as large, clean text over the final clip.

**Implementation in Remotion:**
- New component: `ShareableStat.tsx` -- displays the stat as large, bold text (Bebas Neue, similar to hook text styling)
- Position: centered, lower third of screen (above karaoke subs area, below center)
- Timing: appears 2.5 seconds before video end, fades in over 0.3s
- Style: white text, black stroke, semi-transparent dark pill background (same aesthetic as hook text for brand consistency)
- Font size: slightly smaller than hook text (~6% of screen height)
- Added to `OverlayComposition.tsx` layer stack

**Props flow:**
1. Lyricist outputs `shareable_stat` in `lyrics.json`
2. `remotion_props_builder.py` reads it and passes to Remotion props
3. `OverlayComposition.tsx` renders `ShareableStat` component at the correct timing

#### 3b. Share-optimized CTA in lyrics

**Current behavior:** Lyric payoff section uses generic CTAs like "Drop a comment, what's the topic" or "Tell me what to break down next."

**New behavior:** Update the lyricist prompt's payoff section to prefer share-oriented CTAs:
- "Send this to someone who didn't know"
- "Tag someone who needs to hear this"
- "Share this before you forget"

This is a prompt-level change only -- update the CTA examples in the lyricist prompt.

#### 3c. Share-ready description line

**Current behavior:** Video descriptions use a template with topic + cross-links + hashtags.

**New behavior:** Add the `shareable_stat` as the FIRST line of the video description. This makes it visible in YouTube's truncated description preview and easy to copy-paste when sharing.

**Implementation:** Update `upload_to_youtube.sh` description templates to prepend the stat. The stat will be read from `lyrics.json` in the run directory.

---

## Improvement 4: Reduce "Inauthentic Content" Risk

### Problem
YouTube's July 2025 "inauthentic content" policy targets mass-produced, template-like AI content. The channel's pipeline fits this description. Channels with 500K+ subscribers have been demonetized.

### Changes

#### 4a. Voice clip library (one-time recording)

**Setup:** Ethan records ~20 short voice clips (1-3 seconds each) in categories:
- **Hooks** (8-10 clips): "Wait till you hear this," "You won't believe this one," "Here's something wild," etc.
- **Reactions** (5-7 clips): "Crazy, right?", "Think about that," "Mind blown," etc.
- **Outros** (3-5 clips): "That's how it works," "Now you know," "Science is wild," etc.

**Storage:** `assets/voice_clips/{hooks,reactions,outros}/` directory with numbered WAV/MP3 files.

**Pipeline integration:** New lightweight Python module `agents/voice_clip_mixer.py`:
- `select_clips(category, count=1) -> List[Path]` -- randomly selects from the library
- `mix_voice_clip(base_audio, clip_path, position_seconds, volume=0.8) -> Path` -- mixes a voice clip into the base audio at the specified position using pydub or ffmpeg
- Called by `agents/5_assemble_video.py` after audio loading:
  - Select 1 hook clip, insert at t=0 (before/during music start)
  - Optionally select 1 reaction clip, insert at the "reveal" moment (timing from `lyrics.json` structure)
  - The voice clips play OVER the music, mixed at ~80% relative volume

**Variation logic:** Random selection ensures no two videos have the same voice clip combination. With 20 clips across 3 categories, there are hundreds of unique combinations.

#### 4b. Structural variation in video assembly

**Current behavior:** Every video follows the identical structure: hook text -> karaoke lyrics -> stock footage -> end screen.

**New behavior:** Introduce 3-4 structural templates that the pipeline randomly selects from:

1. **Standard** (current): Hook text -> song with karaoke -> end stat
2. **Reveal-first**: Voice hook -> quick visual montage (3s) -> song starts -> end stat
3. **Question-answer**: Hook text as question -> brief pause -> song answers -> end stat
4. **Cold open**: Song starts immediately (no hook text) -> hook text appears at 3s -> end stat

**Implementation:** Add a `video_structure` field to the pipeline that's randomly assigned. Each template slightly changes the overlay timing and whether the hook text appears at 0s or 3s. This is a config-level variation, not a code rewrite -- it adjusts timing parameters in `remotion_props_builder.py`.

#### 4c. YouTube AI disclosure labels

**Current behavior:** No AI disclosure on uploads.

**New behavior:** Add YouTube's AI-generated content disclosure label to all uploads. This is a metadata field in the YouTube Data API v3 upload request.

**Implementation:** Update the upload script to include the `selfDeclaredMadeForKids: false` and the AI disclosure fields in the video resource body. YouTube's API supports a `contentDetails.contentRating` or similar field for AI disclosure -- research the exact API field and add it.

#### 4d. Reduce upload frequency

**Current behavior:** Daily uploads (7/week).

**New behavior:** 5 uploads/week (skip Saturday and Sunday). The daily launchd job should check the day of week before running the pipeline.

**Implementation:** Add a day-of-week check at the top of `pipeline.sh` or in the launchd plist. If Saturday or Sunday, exit 0 with a log message.

---

## Files Modified (Summary)

| File | Improvements | Change Type |
|------|-------------|-------------|
| `automation/topic_generator.py` | #1 | Prompt rewrite |
| `agents/prompts/lyricist_prompt.md` | #1, #3 | Prompt rewrite + new output field |
| `config/config.json` | #2 | Config value change (audio_trim) |
| `agents/trim_audio.py` | #2 | Threshold verification |
| `agents/remotion/src/compositions/MusicIndicator.tsx` | #2 | New component |
| `agents/remotion/src/compositions/ShareableStat.tsx` | #3 | New component |
| `agents/remotion/src/compositions/OverlayComposition.tsx` | #2, #3 | Add new layers |
| `agents/remotion/src/types.ts` | #2, #3 | New prop types |
| `agents/remotion_props_builder.py` | #2, #3, #4 | Pass new props, structural variation |
| `upload_to_youtube.sh` | #3, #4 | Description template, AI disclosure |
| `agents/voice_clip_mixer.py` | #4 | New module |
| `agents/5_assemble_video.py` | #4 | Voice clip mixing integration |
| `pipeline.sh` | #4 | Day-of-week check |
| `assets/voice_clips/` | #4 | New directory (voice recordings from Ethan) |

## Files NOT Modified

- Music generation (Suno V5 API calls)
- Media curation pipeline
- Analytics/optimization infrastructure
- A/B testing framework
- SVG diagram generation
- Subtitle generation
- YouTube queue processor (staggered uploads)

---

## Testing Strategy

1. **Topic generator:** Unit test that new prompt produces revelation-framed topics (mock Claude response)
2. **Lyricist:** Unit test that `shareable_stat` field is present in output JSON
3. **Remotion components:** Visual snapshot tests for MusicIndicator and ShareableStat
4. **Voice clip mixer:** Unit tests for clip selection (randomness, no repeats in sequence) and audio mixing (output file exists, duration matches)
5. **Structural variation:** Unit test that props builder produces valid props for each template variant
6. **Integration:** Full pipeline dry run with `--express` to verify end-to-end flow
7. **Upload:** Verify description includes shareable_stat, verify AI disclosure metadata

## Success Metrics

| Metric | Current | Target | Timeframe |
|--------|---------|--------|-----------|
| 3-second retention | Unknown (not tracked) | +15% improvement | 4 weeks |
| Overall retention | 44.65% | 55%+ | 8 weeks |
| Engagement rate | 0.74% | 2.5%+ | 8 weeks |
| Shares per video | Not tracked | Begin tracking, establish baseline | 2 weeks |
| YouTube content policy flags | 0 | 0 (maintain) | Ongoing |

## Dependencies / Blockers

- **Voice clips (Improvement 4a):** Requires Ethan to record ~20 clips. This blocks voice clip integration but NOT the other 3 improvements. The pipeline change can be built with a feature flag (`voice_clips.enabled: false`) and activated after recordings are provided.
- **YouTube AI disclosure API field:** Needs research on exact API field name. May require YouTube Data API v3 documentation review.

## Out of Scope

- Channel rebranding or name change
- Topic category reduction (per user preference -- keep broad, everyday topics)
- TikTok distribution fixes
- Custom thumbnail AI generation
- Community building (Discord, polls)
