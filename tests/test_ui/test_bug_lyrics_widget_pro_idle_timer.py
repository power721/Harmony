"""
Regression tests for lyrics_widget_pro idle animation behavior.
"""

from unittest.mock import Mock

import pytest
from PySide6.QtWidgets import QApplication

from system.theme import ThemeManager
from ui.widgets.lyrics_widget_pro import LyricsWidget


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


@pytest.fixture(autouse=True)
def reset_theme_singleton():
    ThemeManager._instance = None
    yield
    ThemeManager._instance = None


@pytest.fixture
def mock_config():
    config = Mock()
    config.get.return_value = "dark"
    return config


def test_timer_stops_when_lyrics_are_empty(qapp, mock_config):
    """No lyrics should not keep animation timer running."""
    ThemeManager.instance(mock_config)
    widget = LyricsWidget()

    widget.set_lyrics("")

    assert not widget.timer.isActive()


def test_timer_starts_when_lyrics_are_present(qapp, mock_config):
    """Lyrics should enable animation timer."""
    ThemeManager.instance(mock_config)
    widget = LyricsWidget()

    widget.set_lyrics("[00:00.00]hello")

    assert widget.timer.isActive()


def test_set_lyrics_resets_current_index_for_immediate_position_sync(qapp, mock_config):
    """Reloaded lyrics should allow the first position sync to re-scroll to the current line."""
    ThemeManager.instance(mock_config)
    widget = LyricsWidget()
    widget.line_height = 60
    widget.current_index = 1
    widget.target_scroll = 180
    widget.scroll_y = 180

    widget.set_lyrics("[00:00.00]first\n[00:10.00]second")
    widget.update_position(12.0)

    assert widget.target_scroll == 60
