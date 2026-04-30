#!/usr/bin/env python3
"""
Generate curiosity-gap hook text for YouTube Shorts first frame.

Uses Claude to transform key facts into attention-grabbing questions
that create an information gap the viewer needs to fill.
"""

import subprocess
import sys
from pathlib import Path
from typing import List, Optional

CLAUDE_CLI = "/Users/ethantrokie/.local/bin/claude"


def _call_claude_hook(topic: str, key_facts: List[str]) -> Optional[str]:
    """Call Claude Haiku to generate a curiosity-gap hook."""
    facts_str = "\n".join(f"- {f}" for f in key_facts[:5])

    prompt = f"""Generate a 3-8 word hook text for a YouTube Short about: {topic}

Key facts:
{facts_str}

The hook appears as bold text on frame 0 to stop scrolling. It must:
- Create a CURIOSITY GAP (make viewer NEED to know the answer)
- Be a question or surprising claim, NOT a topic statement
- Be 3-8 words maximum
- Use one of these patterns:
  * Surprising number: "99% of your body is empty space"
  * Counter-intuitive claim: "Ice is actually hot"
  * Challenge: "You can't explain why this works"
  * Specific + surprising: "6 crystal forms hide in chocolate"

BAD hooks (don't do these):
- "How X Works" (too generic, not curious)
- "X Explained" (boring, no gap)
- "Wait for it..." (overused)

Output ONLY the hook text, nothing else. No quotes, no explanation."""

    try:
        result = subprocess.run(
            [CLAUDE_CLI, "-p", prompt, "--model", "claude-haiku-4-5",
             "--dangerously-skip-permissions"],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except (subprocess.TimeoutExpired, Exception):
        pass
    return None


def _title_derived_hook(title: str) -> str:
    """Fallback: derive hook from title (current behavior)."""
    clean = title.replace(" Explained", "").replace(" (Music Video)", "").strip()
    lower = clean.lower()
    if lower.startswith("how "):
        return f"{clean[4:]}?!"
    elif lower.startswith(("why ", "what ")):
        return f"{clean}?"
    elif lower.startswith("the "):
        return f"{clean[4:]}?!"
    return f"{clean}?!"


def generate_curiosity_hook(
    topic: str,
    key_facts: List[str],
) -> str:
    """
    Generate a curiosity-gap hook for frame 0.
    Tries Claude first, falls back to title-derived hook.
    Always returns a string <= 10 words.
    """
    hook = _call_claude_hook(topic, key_facts)

    if hook:
        words = hook.split()
        if len(words) > 10:
            hook = " ".join(words[:10])
        hook = hook.strip('"\'')
        return hook

    return _title_derived_hook(topic)
