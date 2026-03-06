#!/usr/bin/env python3
"""
Tests for AI clip timing alignment throughout the pipeline.

These tests verify that AI-generated video clips are placed at the correct
timestamps in the final video, matching the lyrics they were generated for.

The pipeline flow for timing is:
  1. clip_placement.py: determines start_time/end_time for each AI clip
  2. generate_ai_clips.py: slices audio at start_time, saves to manifest
  3. build_format_media_plan.py (integrate_ai_clips): reads manifest, places
     AI clips into shot list alongside stock footage
  4. 5_assemble_video.py: concatenates shots sequentially using duration

Key invariant: The AI clip's start_time in the manifest must match where
it actually appears in the final video timeline relative to the audio.
"""

import pytest
import os
import sys
import json
import copy

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'agents'))


# ============================================================
# Fixtures: realistic test data
# ============================================================

@pytest.fixture
def aligned_words():
    """Realistic aligned words from Suno output."""
    return [
        {"word": "[Verse 1]\nThe ", "startS": 2.0, "endS": 2.3},
        {"word": "atoms ", "startS": 2.3, "endS": 2.8},
        {"word": "dance ", "startS": 2.8, "endS": 3.3},
        {"word": "around.\n", "startS": 3.3, "endS": 4.0},
        {"word": "Electrons ", "startS": 5.0, "endS": 5.6},
        {"word": "spinning ", "startS": 5.6, "endS": 6.2},
        {"word": "fast.\n", "startS": 6.2, "endS": 7.0},
        {"word": "Energy ", "startS": 8.0, "endS": 8.5},
        {"word": "levels ", "startS": 8.5, "endS": 9.0},
        {"word": "rising.\n", "startS": 9.0, "endS": 10.0},
        {"word": "Nothing ", "startS": 12.0, "endS": 12.5},
        {"word": "stays ", "startS": 12.5, "endS": 13.0},
        {"word": "the ", "startS": 13.0, "endS": 13.2},
        {"word": "same.\n", "startS": 13.2, "endS": 14.0},
        {"word": "[Chorus]\nQuantum ", "startS": 30.0, "endS": 30.8},
        {"word": "world ", "startS": 30.8, "endS": 31.3},
        {"word": "is ", "startS": 31.3, "endS": 31.5},
        {"word": "strange.\n", "startS": 31.5, "endS": 32.5},
        {"word": "Particles ", "startS": 33.0, "endS": 33.8},
        {"word": "can ", "startS": 33.8, "endS": 34.0},
        {"word": "change.\n", "startS": 34.0, "endS": 35.0},
        {"word": "Wave ", "startS": 36.0, "endS": 36.5},
        {"word": "and ", "startS": 36.5, "endS": 36.7},
        {"word": "particle.\n", "startS": 36.7, "endS": 38.0},
        {"word": "Light ", "startS": 40.0, "endS": 40.5},
        {"word": "is ", "startS": 40.5, "endS": 40.7},
        {"word": "magical.\n", "startS": 40.7, "endS": 42.0},
    ]


@pytest.fixture
def ai_clip_manifest():
    """Realistic AI clip manifest with 3 clips."""
    return {
        "clips": [
            {
                "id": 1,
                "file": "clip_1.mp4",
                "start_time": 2.0,
                "end_time": 7.0,
                "segment_type": "intro",
                "environment_prompt": "Lab setting",
                "lyrics_excerpt": "The atoms dance around...",
                "generation_status": "success",
                "cost_usd": 0.575
            },
            {
                "id": 2,
                "file": "clip_2.mp4",
                "start_time": 12.0,
                "end_time": 17.0,
                "segment_type": "verse",
                "environment_prompt": "Space background",
                "lyrics_excerpt": "Nothing stays the same...",
                "generation_status": "success",
                "cost_usd": 0.575
            },
            {
                "id": 3,
                "file": "clip_3.mp4",
                "start_time": 30.0,
                "end_time": 35.0,
                "segment_type": "chorus",
                "environment_prompt": "Neon lights",
                "lyrics_excerpt": "Quantum world is strange...",
                "generation_status": "success",
                "cost_usd": 0.575
            }
        ]
    }


@pytest.fixture
def stock_footage_shots():
    """Stock footage shot list with relative timing for a full format (0-180s).
    These use relative start_time (0-based) since they're for the full format
    where segment_start=0."""
    return [
        {"shot_number": 1, "local_path": "/tmp/stock_1.mp4", "media_type": "video",
         "source": "pexels", "description": "Atom animation",
         "start_time": 0.0, "end_time": 5.0, "duration": 5.0,
         "absolute_start": 0.0, "absolute_end": 5.0},
        {"shot_number": 2, "local_path": "/tmp/stock_2.mp4", "media_type": "video",
         "source": "pexels", "description": "Molecule structure",
         "start_time": 5.0, "end_time": 10.0, "duration": 5.0,
         "absolute_start": 5.0, "absolute_end": 10.0},
        {"shot_number": 3, "local_path": "/tmp/stock_3.mp4", "media_type": "video",
         "source": "pexels", "description": "Lab equipment",
         "start_time": 10.0, "end_time": 15.0, "duration": 5.0,
         "absolute_start": 10.0, "absolute_end": 15.0},
        {"shot_number": 4, "local_path": "/tmp/stock_4.mp4", "media_type": "video",
         "source": "pexels", "description": "Star field",
         "start_time": 15.0, "end_time": 20.0, "duration": 5.0,
         "absolute_start": 15.0, "absolute_end": 20.0},
        {"shot_number": 5, "local_path": "/tmp/stock_5.mp4", "media_type": "video",
         "source": "pexels", "description": "Electron orbit",
         "start_time": 20.0, "end_time": 30.0, "duration": 10.0,
         "absolute_start": 20.0, "absolute_end": 30.0},
        {"shot_number": 6, "local_path": "/tmp/stock_6.mp4", "media_type": "video",
         "source": "pexels", "description": "Wave pattern",
         "start_time": 30.0, "end_time": 40.0, "duration": 10.0,
         "absolute_start": 30.0, "absolute_end": 40.0},
    ]


# ============================================================
# Test: clip_placement.py timing accuracy
# ============================================================

class TestClipPlacementTiming:
    """Verify clip placements align to phrase boundaries."""

    def test_first_clip_starts_at_zero(self, aligned_words):
        """Clip 1 must always start at 0s so the AI artist is the first thing shown."""
        from clip_placement import determine_clip_placements

        clips = determine_clip_placements(aligned_words)
        assert clips[0]["start_time"] == 0.0, (
            f"Clip 1 starts at {clips[0]['start_time']}s, expected 0.0s"
        )

    def test_non_intro_clips_start_at_phrase_boundaries(self, aligned_words):
        """Clips 2 and 3 must start at a phrase boundary, not mid-word."""
        from clip_placement import determine_clip_placements

        clips = determine_clip_placements(aligned_words)

        # Collect all phrase start times
        phrase_starts = set()
        for word in aligned_words:
            if not word["word"].startswith("["):
                phrase_starts.add(word["startS"])

        # Skip clip 1 — it intentionally starts at 0s (before first lyrics)
        for clip in clips[1:]:
            closest_word_start = min(phrase_starts, key=lambda t: abs(t - clip["start_time"]))
            assert abs(clip["start_time"] - closest_word_start) < 0.5, (
                f"Clip {clip['id']} starts at {clip['start_time']}s but nearest phrase "
                f"boundary is at {closest_word_start}s (gap: {abs(clip['start_time'] - closest_word_start):.2f}s)"
            )

    def test_clips_dont_overlap(self, aligned_words):
        """No two AI clips should overlap in time."""
        from clip_placement import determine_clip_placements

        clips = determine_clip_placements(aligned_words)

        for i in range(len(clips) - 1):
            assert clips[i]["end_time"] <= clips[i + 1]["start_time"], (
                f"Clip {clips[i]['id']} (ends {clips[i]['end_time']}s) overlaps with "
                f"Clip {clips[i + 1]['id']} (starts {clips[i + 1]['start_time']}s)"
            )

    def test_clip_duration_matches_end_minus_start(self, aligned_words):
        """end_time - start_time must equal the expected clip duration (5s)."""
        from clip_placement import determine_clip_placements

        clips = determine_clip_placements(aligned_words)

        for clip in clips:
            duration = clip["end_time"] - clip["start_time"]
            assert abs(duration - 5.0) < 0.01, (
                f"Clip {clip['id']}: end_time - start_time = {duration}s, expected 5.0s"
            )


# ============================================================
# Test: integrate_ai_clips timing
# ============================================================

class TestIntegrateAIClipsTiming:
    """Verify AI clips are placed at correct absolute times in the media plan."""

    def test_ai_clips_preserve_absolute_timing(self, stock_footage_shots, ai_clip_manifest, tmp_path):
        """AI clips must keep their original absolute start/end times after integration."""
        from build_format_media_plan import integrate_ai_clips

        # Write manifest to tmp dir
        ai_dir = tmp_path / "ai_clips"
        ai_dir.mkdir()
        manifest_path = ai_dir / "ai_clip_manifest.json"
        manifest_path.write_text(json.dumps(ai_clip_manifest))

        # Create dummy clip files
        for clip in ai_clip_manifest["clips"]:
            (ai_dir / clip["file"]).write_bytes(b"\x00" * 100)

        result = integrate_ai_clips(stock_footage_shots, str(tmp_path))

        ai_shots = [s for s in result if s.get("source") == "ai_generated"]

        assert len(ai_shots) == 3, f"Expected 3 AI clips, got {len(ai_shots)}"

        for ai_shot in ai_shots:
            # Find matching manifest clip
            manifest_clip = next(
                c for c in ai_clip_manifest["clips"]
                if c["file"] in ai_shot["local_path"]
            )

            assert ai_shot["start_time"] == manifest_clip["start_time"], (
                f"AI clip {manifest_clip['id']}: start_time is {ai_shot['start_time']}s "
                f"but manifest says {manifest_clip['start_time']}s"
            )
            assert ai_shot["end_time"] == manifest_clip["end_time"], (
                f"AI clip {manifest_clip['id']}: end_time is {ai_shot['end_time']}s "
                f"but manifest says {manifest_clip['end_time']}s"
            )

    def test_ai_clips_replace_overlapping_stock_footage(self, stock_footage_shots, ai_clip_manifest, tmp_path):
        """Stock footage that overlaps with AI clip times must be removed."""
        from build_format_media_plan import integrate_ai_clips

        ai_dir = tmp_path / "ai_clips"
        ai_dir.mkdir()
        (ai_dir / "ai_clip_manifest.json").write_text(json.dumps(ai_clip_manifest))
        for clip in ai_clip_manifest["clips"]:
            (ai_dir / clip["file"]).write_bytes(b"\x00" * 100)

        result = integrate_ai_clips(stock_footage_shots, str(tmp_path))

        # Stock shots 1 (0-5) and 3 (10-15) overlap with AI clips 1 (2-7) and 2 (12-17)
        # Stock shot 6 (30-40) overlaps with AI clip 3 (30-35)
        stock_shots = [s for s in result if s.get("source") != "ai_generated"]

        for stock_shot in stock_shots:
            stock_start = stock_shot.get("absolute_start", stock_shot["start_time"])
            stock_end = stock_shot.get("absolute_end", stock_shot["end_time"])

            for ai_clip in ai_clip_manifest["clips"]:
                overlaps = stock_start < ai_clip["end_time"] and stock_end > ai_clip["start_time"]
                assert not overlaps, (
                    f"Stock shot ({stock_start}-{stock_end}s) still present but overlaps "
                    f"AI clip {ai_clip['id']} ({ai_clip['start_time']}-{ai_clip['end_time']}s)"
                )

    def test_integrated_shots_sorted_by_time(self, stock_footage_shots, ai_clip_manifest, tmp_path):
        """After integration, all shots must be sorted by start time."""
        from build_format_media_plan import integrate_ai_clips

        ai_dir = tmp_path / "ai_clips"
        ai_dir.mkdir()
        (ai_dir / "ai_clip_manifest.json").write_text(json.dumps(ai_clip_manifest))
        for clip in ai_clip_manifest["clips"]:
            (ai_dir / clip["file"]).write_bytes(b"\x00" * 100)

        result = integrate_ai_clips(stock_footage_shots, str(tmp_path))

        for i in range(len(result) - 1):
            t1 = result[i].get("absolute_start", result[i]["start_time"])
            t2 = result[i + 1].get("absolute_start", result[i + 1]["start_time"])
            assert t1 <= t2, (
                f"Shot {result[i]['shot_number']} at {t1}s comes before "
                f"shot {result[i + 1]['shot_number']} at {t2}s but is later in list"
            )

    def test_ai_clip_duration_consistent(self, stock_footage_shots, ai_clip_manifest, tmp_path):
        """AI clip duration field must equal end_time - start_time."""
        from build_format_media_plan import integrate_ai_clips

        ai_dir = tmp_path / "ai_clips"
        ai_dir.mkdir()
        (ai_dir / "ai_clip_manifest.json").write_text(json.dumps(ai_clip_manifest))
        for clip in ai_clip_manifest["clips"]:
            (ai_dir / clip["file"]).write_bytes(b"\x00" * 100)

        result = integrate_ai_clips(stock_footage_shots, str(tmp_path))

        for shot in result:
            if shot.get("source") == "ai_generated":
                expected_duration = shot["end_time"] - shot["start_time"]
                assert abs(shot["duration"] - expected_duration) < 0.001, (
                    f"AI shot duration={shot['duration']}s but "
                    f"end-start={expected_duration}s"
                )


# ============================================================
# Test: Sequential assembly timing drift
# ============================================================

class TestSequentialAssemblyTiming:
    """Verify that concatenating clips by duration doesn't drift from intended timing."""

    def test_cumulative_duration_matches_shot_end_times(self, stock_footage_shots, ai_clip_manifest, tmp_path):
        """When clips are concatenated sequentially, cumulative duration must
        match each shot's intended absolute position in the timeline."""
        from build_format_media_plan import integrate_ai_clips

        ai_dir = tmp_path / "ai_clips"
        ai_dir.mkdir()
        (ai_dir / "ai_clip_manifest.json").write_text(json.dumps(ai_clip_manifest))
        for clip in ai_clip_manifest["clips"]:
            (ai_dir / clip["file"]).write_bytes(b"\x00" * 100)

        shots = integrate_ai_clips(stock_footage_shots, str(tmp_path))

        # Simulate what 5_assemble_video.py does: concatenate by duration
        cumulative_time = 0.0
        for shot in shots:
            shot_absolute_start = shot.get("absolute_start", shot["start_time"])
            shot_duration = shot["duration"]

            # The cumulative time (where this clip actually plays in the output)
            # should match the shot's intended absolute start time
            drift = abs(cumulative_time - shot_absolute_start)

            assert drift < 1.0, (
                f"Shot {shot['shot_number']} ({shot.get('source', 'stock')}): "
                f"plays at {cumulative_time:.2f}s in output but intended for "
                f"{shot_absolute_start:.2f}s (drift: {drift:.2f}s)"
            )

            cumulative_time += shot_duration

    def test_no_timeline_gaps_between_shots(self, stock_footage_shots, ai_clip_manifest, tmp_path):
        """There should be no unintended gaps in the timeline after integration."""
        from build_format_media_plan import integrate_ai_clips

        ai_dir = tmp_path / "ai_clips"
        ai_dir.mkdir()
        (ai_dir / "ai_clip_manifest.json").write_text(json.dumps(ai_clip_manifest))
        for clip in ai_clip_manifest["clips"]:
            (ai_dir / clip["file"]).write_bytes(b"\x00" * 100)

        shots = integrate_ai_clips(stock_footage_shots, str(tmp_path))

        for i in range(len(shots) - 1):
            current_end = shots[i].get("absolute_end", shots[i]["end_time"])
            next_start = shots[i + 1].get("absolute_start", shots[i + 1]["start_time"])
            gap = next_start - current_end

            assert gap < 2.0, (
                f"Gap of {gap:.2f}s between shot {shots[i]['shot_number']} "
                f"(ends {current_end:.2f}s) and shot {shots[i + 1]['shot_number']} "
                f"(starts {next_start:.2f}s)"
            )


# ============================================================
# Test: Audio slice timing matches clip placement
# ============================================================

class TestAudioSliceTiming:
    """Verify audio slices are extracted from the correct position in the song."""

    def test_audio_slice_start_matches_clip_start(self):
        """The audio slice must start at exactly the clip's start_time.
        No offset should be applied since we use Kling Avatar v2 Pro now."""
        from clip_placement import determine_clip_placements

        aligned_words = [
            {"word": "Test ", "startS": 2.0, "endS": 2.5},
            {"word": "words.\n", "startS": 2.5, "endS": 3.0},
            {"word": "More ", "startS": 15.0, "endS": 15.5},
            {"word": "words.\n", "startS": 15.5, "endS": 16.0},
            {"word": "[Chorus]\nChorus ", "startS": 32.0, "endS": 33.0},
            {"word": "lyrics.\n", "startS": 33.0, "endS": 34.0},
        ]

        clips = determine_clip_placements(aligned_words)

        # Verify each clip's audio would be sliced starting at its start_time
        # (generate_ai_clips.py calls slice_audio with clip["start_time"])
        for clip in clips:
            # The audio slice should start at clip["start_time"], not offset
            # This is what gets passed to Kling Avatar v2 Pro
            audio_start = clip["start_time"]
            clip_lyrics_start = None

            # Find the first lyric word that falls within this clip's time range
            for word in aligned_words:
                if word["startS"] >= clip["start_time"] and word["startS"] < clip["end_time"]:
                    if not word["word"].startswith("["):
                        clip_lyrics_start = word["startS"]
                        break

            if clip_lyrics_start is not None:
                # Audio start should be at or before the first lyric
                assert audio_start <= clip_lyrics_start, (
                    f"Clip {clip['id']}: audio starts at {audio_start}s but first lyric "
                    f"is at {clip_lyrics_start}s - singer would start before audio"
                )


# ============================================================
# Test: End-to-end timing invariants
# ============================================================

class TestEndToEndTimingInvariants:
    """High-level invariants that must hold across the entire pipeline."""

    def test_ai_clip_lyrics_match_audio_segment(self, aligned_words):
        """The lyrics extracted for each clip must match the audio segment
        that will be playing at that point in the final video."""
        from clip_placement import determine_clip_placements, extract_lyrics_for_clip

        clips = determine_clip_placements(aligned_words)

        for clip in clips:
            lyrics = extract_lyrics_for_clip(
                aligned_words,
                clip["start_time"],
                clip["end_time"]
            )

            # There should be SOME lyrics in the clip's time window
            # (not just empty — that would mean the clip is placed during an
            # instrumental break and there's nothing to lip-sync to)
            assert len(lyrics.strip()) > 0, (
                f"Clip {clip['id']} ({clip['start_time']}-{clip['end_time']}s) "
                f"has no lyrics — lip-sync will have nothing to animate"
            )

    def test_manifest_timing_roundtrips_through_integration(self, ai_clip_manifest, stock_footage_shots, tmp_path):
        """Timing from manifest must survive integration unchanged.
        This is the core invariant: what goes into the manifest must
        come out in the media plan at the same timestamps."""
        from build_format_media_plan import integrate_ai_clips

        ai_dir = tmp_path / "ai_clips"
        ai_dir.mkdir()
        (ai_dir / "ai_clip_manifest.json").write_text(json.dumps(ai_clip_manifest))
        for clip in ai_clip_manifest["clips"]:
            (ai_dir / clip["file"]).write_bytes(b"\x00" * 100)

        result = integrate_ai_clips(stock_footage_shots, str(tmp_path))
        ai_shots = [s for s in result if s.get("source") == "ai_generated"]

        for manifest_clip in ai_clip_manifest["clips"]:
            matching_shot = next(
                (s for s in ai_shots if manifest_clip["file"] in s["local_path"]),
                None
            )
            assert matching_shot is not None, (
                f"Manifest clip {manifest_clip['id']} not found in integrated shot list"
            )

            # All timing fields must match exactly
            assert matching_shot["start_time"] == manifest_clip["start_time"]
            assert matching_shot["end_time"] == manifest_clip["end_time"]
            assert matching_shot["absolute_start"] == manifest_clip["start_time"]
            assert matching_shot["absolute_end"] == manifest_clip["end_time"]
            assert abs(matching_shot["duration"] - (manifest_clip["end_time"] - manifest_clip["start_time"])) < 0.001


# ============================================================
# Test: Segment-relative AI clip integration (shorts)
# ============================================================

class TestSegmentRelativeIntegration:
    """Verify AI clips are correctly filtered and time-adjusted for shorts."""

    def test_ai_clips_filtered_to_segment_range(self, ai_clip_manifest, tmp_path):
        """Only AI clips overlapping the segment range should be included."""
        from build_format_media_plan import integrate_ai_clips

        ai_dir = tmp_path / "ai_clips"
        ai_dir.mkdir()
        (ai_dir / "ai_clip_manifest.json").write_text(json.dumps(ai_clip_manifest))
        for clip in ai_clip_manifest["clips"]:
            (ai_dir / clip["file"]).write_bytes(b"\x00" * 100)

        # Segment 28-45s should include clip 3 (30-35s) but NOT clips 1 (2-7) or 2 (12-17)
        stock_shots = [
            {"shot_number": 1, "local_path": "/tmp/stock.mp4", "media_type": "video",
             "source": "pexels", "description": "Some footage",
             "start_time": 0.0, "end_time": 17.0, "duration": 17.0}
        ]

        result = integrate_ai_clips(stock_shots, str(tmp_path),
                                    segment_start=28.0, segment_end=45.0)

        ai_shots = [s for s in result if s.get("source") == "ai_generated"]
        assert len(ai_shots) == 1, f"Expected 1 AI clip in 28-45s range, got {len(ai_shots)}"
        assert "clip_3" in ai_shots[0]["local_path"]

    def test_ai_clips_times_converted_to_segment_relative(self, ai_clip_manifest, tmp_path):
        """AI clip times must be converted to segment-relative (0-based) coordinates."""
        from build_format_media_plan import integrate_ai_clips

        ai_dir = tmp_path / "ai_clips"
        ai_dir.mkdir()
        (ai_dir / "ai_clip_manifest.json").write_text(json.dumps(ai_clip_manifest))
        for clip in ai_clip_manifest["clips"]:
            (ai_dir / clip["file"]).write_bytes(b"\x00" * 100)

        # Segment 28-45s: clip 3 at abs 30-35s should become rel 2-7s
        stock_shots = [
            {"shot_number": 1, "local_path": "/tmp/stock.mp4", "media_type": "video",
             "source": "pexels", "description": "Some footage",
             "start_time": 0.0, "end_time": 17.0, "duration": 17.0}
        ]

        result = integrate_ai_clips(stock_shots, str(tmp_path),
                                    segment_start=28.0, segment_end=45.0)

        ai_shot = next(s for s in result if s.get("source") == "ai_generated")
        assert abs(ai_shot["start_time"] - 2.0) < 0.01, (
            f"Expected relative start_time=2.0, got {ai_shot['start_time']}"
        )
        assert abs(ai_shot["end_time"] - 7.0) < 0.01, (
            f"Expected relative end_time=7.0, got {ai_shot['end_time']}"
        )

    def test_no_ai_clips_when_segment_doesnt_overlap(self, ai_clip_manifest, tmp_path):
        """When segment range has no overlapping AI clips, shots should be unchanged."""
        from build_format_media_plan import integrate_ai_clips

        ai_dir = tmp_path / "ai_clips"
        ai_dir.mkdir()
        (ai_dir / "ai_clip_manifest.json").write_text(json.dumps(ai_clip_manifest))
        for clip in ai_clip_manifest["clips"]:
            (ai_dir / clip["file"]).write_bytes(b"\x00" * 100)

        # Segment 50-80s has no AI clips (clips are at 2-7, 12-17, 30-35)
        stock_shots = [
            {"shot_number": 1, "local_path": "/tmp/stock.mp4", "media_type": "video",
             "source": "pexels", "description": "Some footage",
             "start_time": 0.0, "end_time": 30.0, "duration": 30.0}
        ]

        result = integrate_ai_clips(stock_shots, str(tmp_path),
                                    segment_start=50.0, segment_end=80.0)

        ai_shots = [s for s in result if s.get("source") == "ai_generated"]
        assert len(ai_shots) == 0, f"Expected no AI clips in 50-80s range, got {len(ai_shots)}"

    def test_full_format_includes_all_ai_clips(self, stock_footage_shots, ai_clip_manifest, tmp_path):
        """Full format (segment_start=0, segment_end=None) should include all AI clips."""
        from build_format_media_plan import integrate_ai_clips

        ai_dir = tmp_path / "ai_clips"
        ai_dir.mkdir()
        (ai_dir / "ai_clip_manifest.json").write_text(json.dumps(ai_clip_manifest))
        for clip in ai_clip_manifest["clips"]:
            (ai_dir / clip["file"]).write_bytes(b"\x00" * 100)

        result = integrate_ai_clips(stock_footage_shots, str(tmp_path),
                                    segment_start=0.0, segment_end=None)

        ai_shots = [s for s in result if s.get("source") == "ai_generated"]
        assert len(ai_shots) == 3, f"Expected all 3 AI clips for full format, got {len(ai_shots)}"


# ============================================================
# Test: AI clip preservation in synchronized assembly
# ============================================================

class TestSynchronizedAssemblyPreservation:
    """Verify AI clips survive the synchronized assembly in 5_assemble_video.py."""

    def test_integrate_ai_clips_into_plan(self):
        """AI clips should be merged into synchronized plan at correct times."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'agents'))
        from importlib import import_module
        assemble = import_module("5_assemble_video")

        stock_shots = [
            {"shot_number": 1, "local_path": "/tmp/stock_1.mp4",
             "start_time": 0.0, "end_time": 10.0, "duration": 10.0},
            {"shot_number": 2, "local_path": "/tmp/stock_2.mp4",
             "start_time": 10.0, "end_time": 20.0, "duration": 10.0},
            {"shot_number": 3, "local_path": "/tmp/stock_3.mp4",
             "start_time": 20.0, "end_time": 35.0, "duration": 15.0},
        ]

        ai_clips = [
            {"local_path": "/tmp/ai_clip_1.mp4", "source": "ai_generated",
             "media_type": "video", "description": "Singer in lab",
             "start_time": 0.0, "end_time": 5.0, "duration": 5.0,
             "absolute_start": 0.0, "absolute_end": 5.0, "priority": "high"},
            {"local_path": "/tmp/ai_clip_2.mp4", "source": "ai_generated",
             "media_type": "video", "description": "Singer in space",
             "start_time": 15.0, "end_time": 20.0, "duration": 5.0,
             "absolute_start": 15.0, "absolute_end": 20.0, "priority": "high"},
        ]

        result = assemble.integrate_ai_clips_into_plan(stock_shots, ai_clips)

        # Check AI clips are present
        ai_shots = [s for s in result if s.get("source") == "ai_generated"]
        assert len(ai_shots) == 2, f"Expected 2 AI clips, got {len(ai_shots)}"

        # Check sorted by time
        for i in range(len(result) - 1):
            assert result[i]["start_time"] <= result[i + 1]["start_time"], (
                f"Shots not sorted: {result[i]['start_time']} > {result[i + 1]['start_time']}"
            )

        # Check no overlaps between AI and stock
        for ai_shot in ai_shots:
            for stock_shot in [s for s in result if s.get("source") != "ai_generated"]:
                overlaps = (stock_shot["start_time"] < ai_shot["end_time"] and
                            stock_shot["end_time"] > ai_shot["start_time"])
                assert not overlaps, (
                    f"Stock shot ({stock_shot['start_time']}-{stock_shot['end_time']}) "
                    f"overlaps AI clip ({ai_shot['start_time']}-{ai_shot['end_time']})"
                )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
