"""
Regression tests for now-playing window persistence.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock

from ui.windows.now_playing_window import NowPlayingWindow


def test_save_window_settings_persists_geometry_and_maximized_state():
    """NowPlayingWindow should persist geometry and maximize state before closing."""
    fake = SimpleNamespace()
    fake._config = SimpleNamespace(
        set_now_playing_geometry=MagicMock(),
        set_now_playing_maximized=MagicMock(),
    )
    fake.saveGeometry = MagicMock(return_value=b"geometry-bytes")
    fake.isMaximized = MagicMock(return_value=True)

    NowPlayingWindow._save_window_settings(fake)

    fake._config.set_now_playing_geometry.assert_called_once_with(b"geometry-bytes")
    fake._config.set_now_playing_maximized.assert_called_once_with(True)


def test_restore_window_settings_restores_geometry_and_maximized_state():
    """NowPlayingWindow should restore the previous geometry and maximized state on startup."""
    fake = SimpleNamespace()
    fake._config = SimpleNamespace(
        get_now_playing_geometry=MagicMock(return_value=b"geometry-bytes"),
        get_now_playing_maximized=MagicMock(return_value=True),
    )
    fake.restoreGeometry = MagicMock()
    fake.showMaximized = MagicMock()
    fake._sync_maximize_button_icon = MagicMock()

    NowPlayingWindow._restore_window_settings(fake)

    fake.restoreGeometry.assert_called_once_with(b"geometry-bytes")
    fake.showMaximized.assert_called_once_with()
    fake._sync_maximize_button_icon.assert_called_once_with()
