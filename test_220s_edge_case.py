#!/usr/bin/env python3
"""Test 220s full video - worst case scenario"""

# Same 14 clips from actual run
available_clips = [
    {"shot_number": 1, "actual_duration": 10.773},
    {"shot_number": 2, "actual_duration": 30.160},
    {"shot_number": 4, "actual_duration": 30.360},
    {"shot_number": 5, "actual_duration": 20.033},
    {"shot_number": 6, "actual_duration": 15.033},
    {"shot_number": 7, "actual_duration": 17.320},
    {"shot_number": 8, "actual_duration": 20.936},
    {"shot_number": 9, "actual_duration": 16.240},
    {"shot_number": 10, "actual_duration": 12.040},
    {"shot_number": 11, "actual_duration": 8.490},
    {"shot_number": 12, "actual_duration": 13.666},
    {"shot_number": 13, "actual_duration": 10.010},
    {"shot_number": 14, "actual_duration": 19.040},
    {"shot_number": 15, "actual_duration": 8.040},
]

total_available = sum(c["actual_duration"] for c in available_clips)
print(f"Available clips: {len(available_clips)}")
print(f"Total available duration: {total_available:.1f}s\n")

# Test 220s full video
target_duration = 220.0
CLIP_COVERAGE_BUFFER_SECONDS = 15
required_duration = target_duration + CLIP_COVERAGE_BUFFER_SECONDS

print(f"Full video target: {target_duration}s")
print(f"Required (with buffer): {required_duration}s")
print(f"Available: {total_available:.1f}s")
print(f"Surplus/Deficit: {total_available - required_duration:.1f}s")

if total_available < required_duration:
    print(f"⚠️  WARNING: NOT ENOUGH CLIPS! Short by {required_duration - total_available:.1f}s\n")
else:
    print(f"✅ Sufficient clips (surplus: {total_available - required_duration:.1f}s)\n")

# Algorithm
IDEAL_SHOT_DURATION = 5.0
MIN_SHOT_DURATION = 3.0
MAX_SHOT_DURATION = 8.0
TARGET_MIN_SHOTS = 15

ideal_num_shots = int(required_duration / IDEAL_SHOT_DURATION)
num_clips = len(available_clips)
num_shots = max(TARGET_MIN_SHOTS, min(ideal_num_shots, num_clips * 3))
base_duration_per_shot = required_duration / num_shots
base_duration_per_shot = max(MIN_SHOT_DURATION, min(base_duration_per_shot, MAX_SHOT_DURATION))

print(f"Algorithm will try:")
print(f"  Ideal shots: {ideal_num_shots}")
print(f"  Actual shots: {num_shots}")
print(f"  Base duration: {base_duration_per_shot:.2f}s per shot")
print(f"  Clips will be reused: {num_shots / num_clips:.1f}x\n")

# Simulate
import random
random.seed(42)
shot_list = []
current_duration = 0.0
clip_index = 0
clips_exhausted = False

for shot_number in range(1, num_shots + 1):
    clip = available_clips[clip_index % num_clips]
    remaining_needed = required_duration - current_duration
    
    if remaining_needed <= 0:
        print(f"  Reached target at shot {shot_number-1}")
        break

    if shot_number == num_shots:
        clip_duration = min(clip["actual_duration"], remaining_needed + 1.0)
    else:
        variation_factor = random.uniform(0.8, 1.2)
        desired_duration = base_duration_per_shot * variation_factor
        clip_duration = min(
            clip["actual_duration"],
            max(MIN_SHOT_DURATION, min(desired_duration, MAX_SHOT_DURATION))
        )

    shot_list.append({
        "shot": shot_number,
        "source_clip": clip["shot_number"],
        "duration": clip_duration
    })

    current_duration += clip_duration
    clip_index += 1

print(f"Results:")
print(f"  Shots created: {len(shot_list)}")
print(f"  Total duration achieved: {current_duration:.2f}s")
print(f"  Target was: {required_duration}s")
print(f"  Difference: {current_duration - required_duration:.2f}s")

if current_duration < target_duration:
    print(f"\n❌ PROBLEM: Video is {target_duration - current_duration:.1f}s too short!")
    print(f"   The video assembly will need to loop/extend clips")
elif current_duration < required_duration:
    print(f"\n⚠️  Slightly short of buffer target, but should work")
else:
    print(f"\n✅ Sufficient duration achieved")

# Check clip reuse
from collections import Counter
clip_usage = Counter(s["source_clip"] for s in shot_list)
print(f"\nClip reuse pattern:")
for clip_num in sorted(clip_usage.keys())[:5]:
    print(f"  Clip {clip_num:2d}: used {clip_usage[clip_num]}x")
