"""Test for queue selection state synchronization with new model."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from unittest.mock import patch
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
    {"id": 1, "title": "Test", "artist": "A", "album": "B", "duration": 180, "path": "/t.mp3"},
]


def test_selection_state_sync():
    """Model selection state updates correctly."""
    with patch('system.theme.ThemeManager', MockThemeManager):
        from ui.views.queue_view import QueueTrackModel
        m = QueueTrackModel()
        m.reset_tracks(TRACKS)
        idx = m.index(0)
        assert m.data(idx, QueueTrackModel.IsSelectedRole) is False
        m.set_selection({0})
        assert m.data(idx, QueueTrackModel.IsSelectedRole) is True


def test_current_and_selected_state():
    """Current track can be selected simultaneously."""
    with patch('system.theme.ThemeManager', MockThemeManager):
        from ui.views.queue_view import QueueTrackModel
        m = QueueTrackModel()
        m.reset_tracks(TRACKS)
        m.set_current(0)
        m.set_playing(True)
        idx = m.index(0)
        assert m.data(idx, QueueTrackModel.IsCurrentRole) is True
        assert m.data(idx, QueueTrackModel.IsPlayingRole) is True
        m.set_selection({0})
        assert m.data(idx, QueueTrackModel.IsSelectedRole) is True
