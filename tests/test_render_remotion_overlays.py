#!/usr/bin/env python3
"""
Tests for render_remotion_overlays module.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "agents"))
from render_remotion_overlays import (
    _build_composite_command,
    _build_remotion_render_command,
    should_render_remotion_overlay,
)


def test_build_ffmpeg_composite_command(tmp_path: Path):
    """FFmpeg composite command contains required arguments."""
    base = tmp_path / "base.mp4"
    overlay = tmp_path / "overlay.mov"
    output = tmp_path / "output.mp4"

    cmd = _build_composite_command(base, overlay, output)

    assert any("ffmpeg" in part for part in cmd)
    assert "-filter_complex" in cmd
    filter_idx = cmd.index("-filter_complex")
    filter_value = cmd[filter_idx + 1]
    assert "overlay" in filter_value
    assert str(base) in cmd
    assert str(overlay) in cmd
    assert str(output) in cmd


def test_remotion_render_command_formed_correctly(tmp_path: Path):
    """Remotion render command includes composition, props path, and prores codec."""
    props = tmp_path / "props.json"
    output = tmp_path / "overlay.mov"
    remotion_dir = tmp_path / "remotion"

    cmd = _build_remotion_render_command(props, output, remotion_dir)

    cmd_str = " ".join(cmd)
    assert "remotion" in cmd_str
    assert str(props) in cmd_str
    assert "prores" in cmd_str or "4444" in cmd_str


def test_config_section_respected():
    """should_render_remotion_overlay respects the enabled flag in config."""
    assert should_render_remotion_overlay({"remotion_overlay": {"enabled": False}}) is False
    assert should_render_remotion_overlay({"remotion_overlay": {"enabled": True}}) is True
    assert should_render_remotion_overlay({}) is False
    assert should_render_remotion_overlay({"remotion_overlay": {}}) is False
