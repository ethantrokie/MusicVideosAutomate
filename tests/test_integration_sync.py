import pytest
import json
from pathlib import Path


def test_synchronized_assembly_integration():
    """Test full synchronized assembly workflow."""
    # This requires actual API keys and run data
    # Skip if not available
    import os
    if not os.getenv("SUNO_API_KEY"):
        pytest.skip("SUNO_API_KEY not set")

    # Use existing run data
    run_dir = Path("outputs/runs/20251117_185735")
    if not run_dir.exists():
        pytest.skip("Test run data not available")

    # Set output dir
    os.environ["OUTPUT_DIR"] = str(run_dir)

    # Run assembly
    from agents.assemble_video import main
    main()

    # Check outputs
    assert (run_dir / "lyrics_aligned.json").exists()
    assert (run_dir / "phrase_groups.json").exists()
    assert (run_dir / "synchronized_plan.json").exists()
    assert (run_dir / "final_video.mp4").exists()

    # Validate synchronized plan
    with open(run_dir / "synchronized_plan.json") as f:
        plan = json.load(f)

    assert plan["sync_method"] == "suno_timestamps"
    assert len(plan["shot_list"]) > 0
    assert all("start_time" in shot for shot in plan["shot_list"])
