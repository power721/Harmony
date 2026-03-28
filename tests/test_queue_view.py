"""Integration tests for refactored QueueView."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from unittest.mock import patch, MagicMock
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

app = QApplication.instance() or QApplication(sys.argv)


class MockTheme:
    name = "dark"
    background = "#121212"
    background_alt = "#282828"
    background_hover = "#2a2a2a"
    text = "#ffffff"
    text_secondary = "#b3b3b3"
    highlight = "#1db954"
    highlight_hover = "#1ed760"
    selection = "rgba(40,40,40,0.8)"
    border = "#3a3a3a"


class MockThemeManager:
    _instance = None
    current_theme = MockTheme()

    @classmethod
    def instance(cls, config=None):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def register_widget(self, w):
        pass

    def get_qss(self, template):
        return template


def make_mock_player(playlist=None, current_index=-1, state_value="stopped"):
    """Create a mock PlaybackService with a mock engine."""
    mock_player = MagicMock()
    mock_engine = MagicMock()
    mock_engine.playlist = playlist or []
    mock_engine.current_index = current_index
    state_mock = MagicMock()
    state_mock.value = state_value
    mock_engine.state = state_mock
    mock_engine.current_track_changed = MagicMock()
    mock_engine.state_changed = MagicMock()
    mock_engine.playlist_changed = MagicMock()
    mock_player.engine = mock_engine
    return mock_player


def test_queue_view_creates():
    """QueueView can be instantiated with mock services."""
    with patch('system.theme.ThemeManager', MockThemeManager):
        from ui.views.queue_view import QueueView
        view = QueueView(make_mock_player(), MagicMock(), MagicMock(), MagicMock())
        assert view is not None


def test_queue_view_has_model():
    """QueueView should have a QueueTrackModel."""
    with patch('system.theme.ThemeManager', MockThemeManager):
        from ui.views.queue_view import QueueView, QueueTrackModel
        view = QueueView(make_mock_player(), MagicMock(), MagicMock(), MagicMock())
        assert isinstance(view._model, QueueTrackModel)


def test_queue_view_has_delegate():
    """QueueView should have a QueueItemDelegate."""
    with patch('system.theme.ThemeManager', MockThemeManager):
        from ui.views.queue_view import QueueView, QueueItemDelegate
        view = QueueView(make_mock_player(), MagicMock(), MagicMock(), MagicMock())
        assert isinstance(view._delegate, QueueItemDelegate)


def test_queue_view_refresh():
    """refresh_queue updates model without crash."""
    with patch('system.theme.ThemeManager', MockThemeManager):
        from ui.views.queue_view import QueueView
        tracks = [
            {"id": 1, "title": "A", "artist": "B", "album": "C", "duration": 180, "path": "/a.mp3"},
        ]
        view = QueueView(
            make_mock_player(playlist=tracks, current_index=0, state_value="playing"),
            MagicMock(), MagicMock(), MagicMock()
        )
        view._refresh_queue()
        assert view._model.rowCount() == 1
        assert view._model.current_index == 0


def test_queue_view_refresh_empty():
    """refresh_queue with empty playlist."""
    with patch('system.theme.ThemeManager', MockThemeManager):
        from ui.views.queue_view import QueueView
        view = QueueView(make_mock_player(playlist=[]), MagicMock(), MagicMock(), MagicMock())
        view._refresh_queue()
        assert view._model.rowCount() == 0


def test_queue_view_signals():
    """QueueView should define expected signals."""
    with patch('system.theme.ThemeManager', MockThemeManager):
        from ui.views.queue_view import QueueView
        view = QueueView(make_mock_player(), MagicMock(), MagicMock(), MagicMock())
        # These signals should exist
        assert hasattr(view, 'play_track')
        assert hasattr(view, 'queue_reordered')
