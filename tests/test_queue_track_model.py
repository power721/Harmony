"""Tests for QueueTrackModel."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from unittest.mock import patch
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


TRACKS = [
    {"id": 1, "title": "Song A", "artist": "Artist", "album": "Album", "duration": 180, "path": "/a.mp3"},
    {"id": 2, "title": "Song B", "artist": "Artist", "album": "Album", "duration": 200, "path": "/b.mp3"},
    {"id": 3, "title": "Song C", "artist": "Other", "album": "Other", "duration": 160, "path": "/c.mp3"},
]


def test_model_row_count():
    with patch('system.theme.ThemeManager', MockThemeManager):
        from ui.views.queue_view import QueueTrackModel
        m = QueueTrackModel()
        m.reset_tracks(TRACKS)
        assert m.rowCount() == 3


def test_model_data_title():
    with patch('system.theme.ThemeManager', MockThemeManager):
        from ui.views.queue_view import QueueTrackModel
        m = QueueTrackModel()
        m.reset_tracks(TRACKS)
        idx = m.index(0)
        track = m.data(idx, QueueTrackModel.TrackRole)
        assert track["title"] == "Song A"


def test_model_data_selected():
    with patch('system.theme.ThemeManager', MockThemeManager):
        from ui.views.queue_view import QueueTrackModel
        m = QueueTrackModel()
        m.reset_tracks(TRACKS)
        idx = m.index(1)
        assert m.data(idx, QueueTrackModel.IsSelectedRole) is False
        m.set_selection({1})
        assert m.data(idx, QueueTrackModel.IsSelectedRole) is True


def test_model_current_index():
    with patch('system.theme.ThemeManager', MockThemeManager):
        from ui.views.queue_view import QueueTrackModel
        m = QueueTrackModel()
        m.reset_tracks(TRACKS)
        assert m.current_index == -1
        m.set_current(2)
        assert m.current_index == 2
        idx = m.index(2)
        assert m.data(idx, QueueTrackModel.IsCurrentRole) is True
        idx0 = m.index(0)
        assert m.data(idx0, QueueTrackModel.IsCurrentRole) is False


def test_model_is_playing():
    with patch('system.theme.ThemeManager', MockThemeManager):
        from ui.views.queue_view import QueueTrackModel
        m = QueueTrackModel()
        m.reset_tracks(TRACKS)
        m.set_current(0)
        m.set_playing(True)
        assert m.data(m.index(0), QueueTrackModel.IsPlayingRole) is True
        m.set_playing(False)
        assert m.data(m.index(0), QueueTrackModel.IsPlayingRole) is False
