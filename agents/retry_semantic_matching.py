#!/usr/bin/env python3
"""
Retry semantic matching with adjusted parameters when sync validation fails.
Attempts different matching strategies to improve visual-lyric synchronization.
"""

import json
import sys
import subprocess
import shutil
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from output_helper import get_output_path


def get_project_root() -> Path:
    """Get project root directory."""
    return Path(__file__).parent.parent


def retry_with_adjusted_params(attempt: int = 1) -> bool:
    """
    Retry semantic matching with adjusted parameters.

    Args:
        attempt: Retry attempt number (1 or 2)

    Returns:
        True if successful, False otherwise
    """
    config_path = get_project_root() / "config" / "config.json"
    backup_path = get_project_root() / "config" / "config_backup.json"

    # Backup original config
    shutil.copy(config_path, backup_path)
    print(f"📦 Backed up config to {backup_path}")

    # Load config
    with open(config_path) as f:
        config = json.load(f)

    sync_config = config.get("synchronization", {})
    original_boost = sync_config.get("keyword_boost_multiplier", 2.0)

    try:
        # Adjust parameters based on attempt
        if attempt == 1:
            # First retry: Reduce keyword boost to rely more on semantic similarity
            new_boost = max(1.0, original_boost * 0.5)
            print(f"🔄 Attempt 1: Reducing keyword_boost from {original_boost} to {new_boost}")
            print("   Strategy: Rely more on semantic similarity, less on exact keyword matches")
        else:
            # Second retry: Minimal keyword boost, pure semantic matching
            new_boost = 1.0
            print(f"🔄 Attempt 2: Setting keyword_boost to {new_boost} (pure semantic matching)")
            print("   Strategy: Ignore keywords, use only visual-semantic similarity")

        sync_config["keyword_boost_multiplier"] = new_boost
        config["synchronization"] = sync_config

        # Save modified config
        with open(config_path, 'w') as f:
            json.dump(config, f, indent=2)

        # Re-run video assembly (which includes semantic matching)
        print("\n🎬 Re-assembling video with adjusted matching parameters...")
        result = subprocess.run([sys.executable, 'agents/5_assemble_video.py'])

        if result.returncode != 0:
            print("❌ Video assembly failed")
            return False

        print("✅ Video assembled with new semantic matching")
        return True

    finally:
        # Restore original config
        shutil.copy(backup_path, config_path)
        print(f"📦 Restored original config")
        backup_path.unlink()


def main():
    """Main entry point."""
    # Check if we have sync validation results to understand the problem
    sync_results_path = get_output_path("sync_validation.json")
    if sync_results_path.exists():
        with open(sync_results_path) as f:
            sync_results = json.load(f)
        avg_score = sync_results.get("average_score", 0)
        low_scores = sync_results.get("low_scores", 0)
        print(f"🔍 Current sync validation: {avg_score}/10 average ({low_scores} segments with poor match)")
    else:
        print("⚠️  No sync validation results found")

    # Try first retry with reduced keyword boost
    print("\n" + "="*60)
    if not retry_with_adjusted_params(attempt=1):
        print("❌ First retry failed")
        sys.exit(1)

    # Check if validation improved (optional - could be called by pipeline)
    print("\n✅ Semantic matching retry complete")
    print("   Pipeline will re-run sync validation to check if matching improved")
    sys.exit(0)


if __name__ == "__main__":
    main()
