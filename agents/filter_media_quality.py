#!/usr/bin/env python3
"""Filter downloaded media by quality using video LLM."""

import json
import subprocess
import sys
import re
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from output_helper import get_output_path

QUALITY_THRESHOLD = 5  # 1-10 scale, reject below this


def get_video_llm_venv() -> str:
    """Get path to video LLM virtual environment."""
    project_root = Path(__file__).parent.parent
    venv_path = project_root / "venv_video_llm"
    if venv_path.exists():
        return str(venv_path / "bin" / "python")
    return sys.executable  # Fallback to current interpreter


def rate_clip_quality(video_path: str) -> int:
    """Rate clip quality on 1-10 scale using video LLM.
    
    This focuses on TECHNICAL quality, not content relevance.
    """
    prompt = """Rate this video's TECHNICAL quality on a scale of 1-10.

ONLY consider these technical aspects:
- Is it high resolution (1080p or higher)? If yes, add 3 points.
- Is it well-lit and not too dark? If yes, add 2 points.
- Is it in focus and not blurry? If yes, add 2 points.
- Does it have smooth motion without jarring cuts? If yes, add 2 points.
- Is it free of large watermarks covering the content? If yes, add 1 point.

Start with 0 and add points for each criterion that applies.
DO NOT judge the content or subject matter - only technical quality.

Respond with ONLY a single number from 1 to 10."""

    python_path = get_video_llm_venv()
    
    cmd = [
        python_path, "-m", "mlx_vlm.video_generate",
        "--model", "mlx-community/Qwen3-VL-8B-Instruct-4bit",
        "--prompt", prompt,
        "--video", video_path,
        "--max-tokens", "10",
        "--fps", "0.5"
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        
        if result.returncode == 0:
            output = result.stdout
            # Try to find a clear number
            # First check for numbers at the end (most likely the answer)
            numbers = re.findall(r'\b(\d+)\b', output)
            if numbers:
                # Filter to valid range
                valid_scores = [int(n) for n in numbers if 1 <= int(n) <= 10]
                if valid_scores:
                    return valid_scores[-1]  # Take last valid number
                # If numbers found but not in range, default high
                return 7
    except subprocess.TimeoutExpired:
        print("  ⏱️ Timeout during analysis")
    except Exception as e:
        print(f"  ⚠️ Error: {e}")
    
    # Default to 7 (above threshold) when uncertain - keep clips by default
    return 7


def detect_advertisement(video_path: str) -> dict:
    """Detect if video contains advertisement or promotional content.
    
    Returns:
        dict with 'is_ad': bool and 'reason': str
    """
    prompt = """Does this video show advertisements, promotional content, text overlays with URLs, or marketing messages?

Check for: website URLs, marketing slogans (Buy/Subscribe/Click/Download), product promotions, contact info, price tags, business watermarks.

Respond with only one word:
- CLEAN (if educational or stock footage)
- AD (if any promotional content)"""

    python_path = get_video_llm_venv()
    
    cmd = [
        python_path, "-m", "mlx_vlm.video_generate",
        "--model", "mlx-community/Qwen3-VL-8B-Instruct-4bit",
        "--prompt", prompt,
        "--video", video_path,
        "--max-tokens", "50",
        "--fps", "1.0"  # Higher FPS to catch text overlays
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        
        if result.returncode == 0:
            output = result.stdout.strip()

            # Check if response contains AD (case insensitive)
            if "AD" in output.upper() and "CLEAN" not in output.upper():
                return {"is_ad": True, "reason": "Promotional content detected"}

            # If CLEAN is in the output, it's safe
            if "CLEAN" in output.upper():
                return {"is_ad": False, "reason": ""}
                
    except subprocess.TimeoutExpired:
        print("  ⏱️ Timeout during ad detection")
    except Exception as e:
        print(f"  ⚠️ Ad detection error: {e}")
    
    # Default to not an ad when uncertain
    return {"is_ad": False, "reason": ""}


def filter_media(manifest: dict, threshold: int = QUALITY_THRESHOLD, 
                 check_ads: bool = True) -> dict:
    """Filter media clips by quality score and advertisement detection.
    
    Args:
        manifest: Media manifest with 'downloaded' list
        threshold: Minimum quality score (1-10)
        check_ads: Whether to run advertisement detection
        
    Returns:
        Filter results with approved and rejected lists
    """
    downloaded = manifest.get("downloaded", [])
    
    if not downloaded:
        return {"approved": [], "rejected": [], "ads_rejected": [], "threshold": threshold}
    
    print(f"🔍 Quality filtering {len(downloaded)} clips (threshold: {threshold}/10)...")
    if check_ads:
        print("   📺 Advertisement detection enabled")
    
    approved = []
    rejected = []
    ads_rejected = []
    
    for item in downloaded:
        local_path = item.get("local_path", "")
        if not local_path or not Path(local_path).exists():
            print(f"  ⚠️ Skipping missing file: {local_path}")
            continue
            
        filename = Path(local_path).name
        print(f"  Checking {filename}...", end=" ", flush=True)
        
        try:
            # Step 1: Check for advertisements first
            if check_ads:
                ad_result = detect_advertisement(local_path)
                if ad_result["is_ad"]:
                    item["is_advertisement"] = True
                    item["ad_reason"] = ad_result["reason"]
                    ads_rejected.append(item)
                    print(f"🚫 AD REJECTED: {ad_result['reason'][:40]}")
                    continue
            
            # Step 2: Rate technical quality
            score = rate_clip_quality(local_path)
            item["quality_score"] = score
            item["is_advertisement"] = False
            
            if score >= threshold:
                approved.append(item)
                print(f"✅ ({score}/10)")
            else:
                rejected.append(item)
                print(f"❌ ({score}/10 - below threshold)")
        except Exception as e:
            item["quality_score"] = threshold  # Default score
            item["is_advertisement"] = False
            approved.append(item)  # Keep on error
            print(f"⚠️ (defaulting to keep: {e})")
    
    return {
        "approved": approved,
        "rejected": rejected,
        "ads_rejected": ads_rejected,
        "threshold": threshold
    }


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Filter media by quality and detect advertisements')
    parser.add_argument('--threshold', type=int, default=QUALITY_THRESHOLD,
                       help=f'Minimum quality score (default: {QUALITY_THRESHOLD})')
    parser.add_argument('--dry-run', action='store_true',
                       help='Print what would be filtered without saving')
    parser.add_argument('--skip-ads', action='store_true',
                       help='Skip advertisement detection (only quality check)')
    args = parser.parse_args()
    
    manifest_path = get_output_path("media_manifest.json")
    if not manifest_path.exists():
        print(f"❌ Media manifest not found: {manifest_path}")
        sys.exit(1)
    
    with open(manifest_path) as f:
        manifest = json.load(f)
    
    results = filter_media(manifest, args.threshold, check_ads=not args.skip_ads)
    
    total = len(manifest.get('downloaded', []))
    print(f"\n✅ Approved: {len(results['approved'])}/{total}")
    print(f"❌ Low quality: {len(results['rejected'])}")
    print(f"🚫 Ads rejected: {len(results.get('ads_rejected', []))}")
    
    if not args.dry_run:
        # Save filter results
        filter_path = get_output_path("quality_filter_results.json")
        with open(filter_path, "w") as f:
            json.dump(results, f, indent=2)
        print(f"\n📁 Results saved to {filter_path}")
    
    # Return exit code based on whether we have enough clips
    if len(results['approved']) == 0:
        print("❌ CRITICAL: No clips approved - all rejected")
        sys.exit(1)  # Fatal - triggers recovery
    elif len(results['approved']) < 5:
        print("⚠️ WARNING: Too few clips approved, may affect video quality")
        sys.exit(2)  # Non-fatal warning

    sys.exit(0)


if __name__ == "__main__":
    main()
