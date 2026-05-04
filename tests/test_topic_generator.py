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
            captured_prompt["text"] = args[0][2]
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
