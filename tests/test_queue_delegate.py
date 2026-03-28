# tests/test_queue_delegate.py
"""Tests for QueueItemDelegate."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from unittest.mock import patch, MagicMock
from PySide6.QtCore import Qt, QSize, QRect
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QPainter, QPixmap, QColor

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


def test_size_hint():
    with patch('system.theme.ThemeManager', MockThemeManager):
        from ui.views.queue_view import QueueItemDelegate
        from PySide6.QtWidgets import QStyleOptionViewItem
        d = QueueItemDelegate()
        option = QStyleOptionViewItem()
        assert d.sizeHint(option, None) == QSize(0, 72)


def test_paint_does_not_crash():
    """Paint should not crash with various track states."""
    with patch('system.theme.ThemeManager', MockThemeManager):
        from ui.views.queue_view import QueueItemDelegate, QueueTrackModel

        model = QueueTrackModel()
        model.reset_tracks([
            {"id": 1, "title": "Test Song", "artist": "Artist", "album": "Album", "duration": 180, "path": "/a.mp3"},
        ])

        delegate = QueueItemDelegate()

        # Paint normal item
        pixmap = QPixmap(400, 72)
        pixmap.fill(QColor("#121212"))
        painter = QPainter(pixmap)
        idx = model.index(0)
        option = delegate._make_style_option(idx)
        delegate.paint(painter, option, idx)
        painter.end()

        # Paint current playing item
        model.set_current(0)
        model.set_playing(True)
        pixmap2 = QPixmap(400, 72)
        pixmap2.fill(QColor("#121212"))
        painter2 = QPainter(pixmap2)
        idx = model.index(0)
        option2 = delegate._make_style_option(idx)
        delegate.paint(painter2, option2, idx)
        painter2.end()

        # Paint selected item
        model.reset_tracks([{"id": 1, "title": "Sel", "artist": "A", "album": "B", "duration": 180, "path": "/a.mp3"}])
        model.set_selection({0})
        pixmap3 = QPixmap(400, 72)
        pixmap3.fill(QColor("#121212"))
        painter3 = QPainter(pixmap3)
        idx = model.index(0)
        option3 = delegate._make_style_option(idx)
        delegate.paint(painter3, option3, idx)
        painter3.end()
