#!/usr/bin/env python3
"""Test the new unique-first strategy"""

# Same 14 clips from actual run
available_clips = [
    {"shot_number": i, "actual_duration": d}
    for i, d in enumerate([10.773, 30.160, 30.360, 20.033, 15.033,
                            17.320, 20.936, 16.240, 12.040, 8.490,
                            13.666, 10.010, 19.040, 8.040], 1)
]

total_available = sum(c["actual_duration"] for c in available_clips)
num_clips = len(available_clips)

def test_scenario(name, target_duration):
    print(f"\n{'='*60}")
    print(f"Scenario: {name}")
    print(f"{'='*60}")

    CLIP_COVERAGE_BUFFER_SECONDS = 15
    required_duration = target_duration + CLIP_COVERAGE_BUFFER_SECONDS

    print(f"Target: {target_duration}s")
    print(f"Required (with buffer): {required_duration}s")
    print(f"Available: {total_available:.1f}s from {num_clips} clips")

    # New unique-first strategy
    if total_available >= required_duration:
        num_shots = num_clips
        max_reuse = 1
        strategy = f"✅ Unique-first: using all {num_clips} unique clips (no reuse)"
    else:
        if total_available < target_duration:
            max_reuse = 5
            strategy = f"⚠️  Critical shortage: allowing up to {max_reuse}x reuse"
        else:
            max_reuse = 3
            strategy = f"⚠️  Moderate shortage: allowing up to {max_reuse}x reuse"

        # Calculate ideal shots with reuse
        IDEAL_SHOT_DURATION = 3.0 if target_duration < 100 else 5.0
        ideal_num_shots = int(required_duration / IDEAL_SHOT_DURATION)
        num_shots = max(8, min(ideal_num_shots, num_clips * max_reuse))

    base_duration = required_duration / num_shots

    print(f"    {strategy}")
    print(f"    Shots: {num_shots} at ~{base_duration:.1f}s each")

    if max_reuse > 1:
        avg_reuse = num_shots / num_clips
        print(f"    Average reuse per clip: {avg_reuse:.1f}x")

# Test scenarios
test_scenario("Hook short (60s)", 60.0)
test_scenario("Educational short (90s)", 90.0)
test_scenario("Standard full (160s)", 160.9)
test_scenario("Long full (220s)", 220.0)

print(f"\n{'='*60}")
print(f"Summary: Unique-first maximizes visual variety by avoiding")
print(f"unnecessary clip reuse when we have sufficient total duration")
print(f"{'='*60}")
