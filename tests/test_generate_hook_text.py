import json
import pytest
from pathlib import Path
from unittest.mock import patch

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "agents"))


def test_generate_curiosity_hook_returns_short_text():
    from generate_hook_text import generate_curiosity_hook

    mock_response = "Did you know chocolate has 6 crystal forms?"

    with patch("generate_hook_text._call_claude_hook") as mock:
        mock.return_value = mock_response
        hook = generate_curiosity_hook(
            topic="How Chocolate Gets Its Snap",
            key_facts=["Chocolate has 6 possible crystal forms", "Only form V gives the perfect snap"],
        )

    assert hook is not None
    assert len(hook.split()) <= 10
    assert len(hook) <= 60


def test_generate_curiosity_hook_falls_back_to_title():
    from generate_hook_text import generate_curiosity_hook

    with patch("generate_hook_text._call_claude_hook") as mock:
        mock.return_value = None
        hook = generate_curiosity_hook(
            topic="How Chocolate Gets Its Snap",
            key_facts=["Chocolate has 6 forms"],
        )

    assert hook is not None
    assert "?" in hook or "!" in hook


def test_generate_curiosity_hook_truncates_long_response():
    from generate_hook_text import generate_curiosity_hook

    long_response = "This is a really long hook text that has way too many words in it and needs to be truncated"

    with patch("generate_hook_text._call_claude_hook") as mock:
        mock.return_value = long_response
        hook = generate_curiosity_hook(
            topic="Test Topic",
            key_facts=["Test fact"],
        )

    assert len(hook.split()) <= 10


def test_title_derived_hook_patterns():
    from generate_hook_text import _title_derived_hook

    assert "?" in _title_derived_hook("How Chocolate Gets Its Snap") or "!" in _title_derived_hook("How Chocolate Gets Its Snap")
    assert "?" in _title_derived_hook("Why Ice Floats")
    assert _title_derived_hook("The Chemistry of Rust").endswith("?!")
