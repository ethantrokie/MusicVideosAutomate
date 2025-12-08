#!/usr/bin/env python3
"""Test the safety checks with various scenarios"""

available_clips = [
    {"shot_number": i, "actual_duration": d} 
    for i, d in enumerate([10.773, 30.160, 30.360, 20.033, 15.033, 
                            17.320, 20.936, 16.240, 12.040, 8.490, 
                            13.666, 10.010, 19.040, 8.040], 1)
]

def test_scenario(name, target_duration):
    print(f"\n{'='*60}")
    print(f"Scenario: {name}")
    print(f"{'='*60}")
    
    total_available = sum(c["actual_duration"] for c in available_clips)
    CLIP_COVERAGE_BUFFER_SECONDS = 15
    required_duration = target_duration + CLIP_COVERAGE_BUFFER_SECONDS
    recommended_duration = target_duration * 1.2
    
    print(f"Target: {target_duration}s")
    print(f"Available: {total_available:.1f}s from {len(available_clips)} clips")
    print(f"Required (with buffer): {required_duration:.1f}s")
    print(f"Recommended (1.2x): {recommended_duration:.1f}s")
    
    # Safety checks
    if total_available < target_duration:
        print(f"❌ CRITICAL: Insufficient clips! Have {total_available:.1f}s, need {target_duration:.1f}s")
        print(f"   Video will be too short. Check curator or download failures.")
    elif total_available < required_duration:
        shortage = required_duration - total_available
        print(f"⚠️  Warning: Short by {shortage:.1f}s")
        print(f"   Clips will be reused extensively.")
    elif total_available < recommended_duration:
        print(f"⚠️  Note: Below recommended 1.2x ({recommended_duration:.1f}s)")
        print(f"   Should work but clips will be reused more than ideal.")
    else:
        surplus = total_available - recommended_duration
        print(f"✅ Sufficient clips! Surplus: {surplus:.1f}s above recommended")
    
    # Reuse strategy
    if total_available < required_duration:
        max_reuse = 5
        print(f"📊 Strategy: Allow up to {max_reuse}x clip reuse")
    else:
        max_reuse = 3
        print(f"📊 Strategy: Limit to {max_reuse}x clip reuse for variety")

# Test scenarios
test_scenario("Short video (30s)", 30.0)
test_scenario("Medium video (90s)", 90.0)  
test_scenario("Standard full (160s)", 160.9)
test_scenario("Long full (220s) - Edge Case", 220.0)
test_scenario("Very long (250s) - Critical", 250.0)

print(f"\n{'='*60}")
print(f"Summary: Safety checks will warn about insufficient clips")
print(f"and adjust reuse strategy accordingly.")
print(f"{'='*60}")
