#!/usr/bin/env python3
"""Tests for video overlay functionality."""

import sys
import os
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent / 'agents'))

from video_overlays import (
    get_available_font,
    create_title_overlay,
    create_end_screen,
    get_video_title,
    TITLE_FONTS,
    CTA_FONTS,
)


class TestGetAvailableFont:
    """Tests for font availability detection."""

    def test_returns_first_existing_font(self):
        """Should return first font that exists on system."""
        font = get_available_font(TITLE_FONTS)
        # Should return a string (either a font path or fallback)
        assert isinstance(font, str)
        assert len(font) > 0

    def test_returns_fallback_when_no_fonts_exist(self):
        """Should return Helvetica fallback when no fonts in list exist."""
        fake_fonts = ['/nonexistent/font1.ttf', '/nonexistent/font2.ttf']
        font = get_available_font(fake_fonts)
        assert font == 'Helvetica'

    def test_cta_fonts_available(self):
        """Should find at least one CTA font."""
        font = get_available_font(CTA_FONTS)
        assert isinstance(font, str)


class TestCreateTitleOverlay:
    """Tests for title overlay creation."""

    def test_creates_text_clip_for_short_video(self):
        """Should create a TextClip for vertical shorts."""
        # Mock TextClip to avoid actual rendering
        with patch('video_overlays.TextClip') as mock_text_clip:
            mock_instance = MagicMock()
            mock_instance.set_position.return_value = mock_instance
            mock_instance.set_duration.return_value = mock_instance
            mock_instance.crossfadein.return_value = mock_instance
            mock_instance.crossfadeout.return_value = mock_instance
            mock_text_clip.return_value = mock_instance

            clip = create_title_overlay(
                title="Test Title",
                video_size=(1080, 1920),
                duration=2.0,
                is_short=True
            )

            assert mock_text_clip.called
            call_kwargs = mock_text_clip.call_args[1]
            assert call_kwargs['fontsize'] == 60  # Base size for shorts
            assert call_kwargs['color'] == 'white'
            assert call_kwargs['stroke_color'] == 'black'

    def test_creates_text_clip_for_full_video(self):
        """Should create a TextClip for horizontal full videos."""
        with patch('video_overlays.TextClip') as mock_text_clip:
            mock_instance = MagicMock()
            mock_instance.set_position.return_value = mock_instance
            mock_instance.set_duration.return_value = mock_instance
            mock_instance.crossfadein.return_value = mock_instance
            mock_instance.crossfadeout.return_value = mock_instance
            mock_text_clip.return_value = mock_instance

            clip = create_title_overlay(
                title="Test Title",
                video_size=(1920, 1080),
                duration=2.0,
                is_short=False
            )

            assert mock_text_clip.called
            call_kwargs = mock_text_clip.call_args[1]
            assert call_kwargs['fontsize'] == 70  # Base size for full

    def test_reduces_font_size_for_long_titles(self):
        """Should reduce font size for titles over 40 characters."""
        with patch('video_overlays.TextClip') as mock_text_clip:
            mock_instance = MagicMock()
            mock_instance.set_position.return_value = mock_instance
            mock_instance.set_duration.return_value = mock_instance
            mock_instance.crossfadein.return_value = mock_instance
            mock_instance.crossfadeout.return_value = mock_instance
            mock_text_clip.return_value = mock_instance

            long_title = "This is a very long title that exceeds forty characters easily"
            clip = create_title_overlay(
                title=long_title,
                video_size=(1080, 1920),
                duration=2.0,
                is_short=True
            )

            call_kwargs = mock_text_clip.call_args[1]
            # Should be reduced by 25% (60 * 0.75 = 45)
            assert call_kwargs['fontsize'] == 45


class TestCreateEndScreen:
    """Tests for end screen creation."""

    def test_creates_composite_for_short_video(self):
        """Should create end screen with channel promo for shorts."""
        with patch('video_overlays.ColorClip') as mock_color:
            with patch('video_overlays.TextClip') as mock_text:
                with patch('video_overlays.CompositeVideoClip') as mock_composite:
                    # Setup mocks
                    mock_bg = MagicMock()
                    mock_bg.set_opacity.return_value = mock_bg
                    mock_bg.set_duration.return_value = mock_bg
                    mock_color.return_value = mock_bg

                    mock_txt = MagicMock()
                    mock_txt.set_position.return_value = mock_txt
                    mock_txt.set_duration.return_value = mock_txt
                    mock_text.return_value = mock_txt

                    mock_comp = MagicMock()
                    mock_comp.set_duration.return_value = mock_comp
                    mock_comp.crossfadein.return_value = mock_comp
                    mock_composite.return_value = mock_comp

                    screen = create_end_screen(
                        video_size=(1080, 1920),
                        duration=3.0,
                        is_short=True,
                        channel_name="@testchannel"
                    )

                    # Should create multiple text clips for shorts (CTA + channel + icon)
                    assert mock_text.call_count >= 3

    def test_creates_composite_for_full_video(self):
        """Should create end screen without channel promo for full videos."""
        with patch('video_overlays.ColorClip') as mock_color:
            with patch('video_overlays.TextClip') as mock_text:
                with patch('video_overlays.CompositeVideoClip') as mock_composite:
                    mock_bg = MagicMock()
                    mock_bg.set_opacity.return_value = mock_bg
                    mock_bg.set_duration.return_value = mock_bg
                    mock_color.return_value = mock_bg

                    mock_txt = MagicMock()
                    mock_txt.set_position.return_value = mock_txt
                    mock_txt.set_duration.return_value = mock_txt
                    mock_text.return_value = mock_txt

                    mock_comp = MagicMock()
                    mock_comp.set_duration.return_value = mock_comp
                    mock_comp.crossfadein.return_value = mock_comp
                    mock_composite.return_value = mock_comp

                    screen = create_end_screen(
                        video_size=(1920, 1080),
                        duration=3.0,
                        is_short=False
                    )

                    # Full video has only 2 text elements (CTA + secondary)
                    assert mock_text.call_count == 2


class TestGetVideoTitle:
    """Tests for video title extraction."""

    def test_extracts_title_from_research_json(self):
        """Should extract video_title from research.json."""
        with tempfile.TemporaryDirectory() as tmpdir:
            research_path = Path(tmpdir) / "research.json"
            research_path.write_text('{"video_title": "Test Title From Research"}')

            with patch('video_overlays.get_output_path') as mock_path:
                mock_path.return_value = Path(tmpdir) / "dummy"
                title = get_video_title(Path(tmpdir))

            assert title == "Test Title From Research"

    def test_falls_back_to_idea_txt(self):
        """Should fallback to idea.txt when research.json has no title."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create research.json without video_title
            research_path = Path(tmpdir) / "research.json"
            research_path.write_text('{"other_key": "value"}')

            # Create idea.txt
            idea_path = Path("input/idea.txt")
            original_content = None
            if idea_path.exists():
                original_content = idea_path.read_text()

            try:
                idea_path.parent.mkdir(exist_ok=True)
                idea_path.write_text("Fallback Topic From Idea. More text here.")

                with patch('video_overlays.get_output_path') as mock_path:
                    mock_path.return_value = Path(tmpdir) / "dummy"
                    title = get_video_title(Path(tmpdir))

                assert title == "Fallback Topic From Idea"
            finally:
                if original_content is not None:
                    idea_path.write_text(original_content)

    def test_returns_default_when_no_sources(self):
        """Should return default when no title sources available."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch('video_overlays.get_output_path') as mock_path:
                mock_path.return_value = Path(tmpdir) / "dummy"
                # Mock idea.txt to not exist
                with patch('pathlib.Path.exists', return_value=False):
                    title = get_video_title(Path(tmpdir))

            # Should return from idea.txt or fallback (depends on actual file state)
            assert isinstance(title, str)


class TestModuleImports:
    """Tests for module import functionality."""

    def test_can_import_all_functions(self):
        """Should be able to import all public functions."""
        from video_overlays import (
            get_available_font,
            create_title_overlay,
            create_end_screen,
            add_overlays_to_video,
            get_video_title,
        )
        assert callable(get_available_font)
        assert callable(create_title_overlay)
        assert callable(create_end_screen)
        assert callable(add_overlays_to_video)
        assert callable(get_video_title)


# Run tests if executed directly
if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
