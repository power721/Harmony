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

    @staticmethod
    def get_combobox_style():
        return ""


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


def test_get_tracks_by_ids_uses_batch_api_when_available():
    """QueueView should use batch track lookup when library service supports it."""
    from domain.track import Track, TrackSource
    from ui.views.queue_view import QueueView

    view = QueueView.__new__(QueueView)
    view._library_service = MagicMock()
    view._library_service.get_tracks_by_ids.return_value = [
        Track(id=1, title="One", source=TrackSource.QQ),
        Track(id=2, title="Two", source=TrackSource.QQ),
    ]
    view._library_service.get_track.side_effect = AssertionError("Should not call per-item lookup")

    tracks = QueueView._get_tracks_by_ids(view, [1, 2])

    assert [track.id for track in tracks] == [1, 2]
    view._library_service.get_tracks_by_ids.assert_called_once_with([1, 2])


def test_get_tracks_by_ids_falls_back_to_single_lookup():
    """QueueView should keep compatibility with old library services without batch API."""
    from domain.track import Track, TrackSource
    from ui.views.queue_view import QueueView

    class LegacyLibraryService:
        def __init__(self):
            self.calls = []

        def get_track(self, track_id):
            self.calls.append(track_id)
            return Track(id=track_id, title=str(track_id), source=TrackSource.QQ)

    view = QueueView.__new__(QueueView)
    view._library_service = LegacyLibraryService()

    tracks = QueueView._get_tracks_by_ids(view, [3, 4])

    assert [track.id for track in tracks] == [3, 4]
    assert view._library_service.calls == [3, 4]
