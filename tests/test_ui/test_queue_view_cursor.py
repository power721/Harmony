"""
Regression tests for queue view cursor behavior.
"""

from PySide6.QtGui import QPainter, QPixmap
from PySide6.QtWidgets import QWidget, QStyle

from ui.views.queue_view import QueueItemDelegate, QueueTrackModel


class _CursorTrackingParent(QWidget):
    def __init__(self):
        super().__init__()
        self.set_cursor_calls = 0

    def setCursor(self, cursor):
        self.set_cursor_calls += 1
        super().setCursor(cursor)


class _DummyTheme:
    background = "#111111"
    highlight = "#22aa55"
    background_hover = "#333333"
    text = "#eeeeee"
    text_secondary = "#bbbbbb"
    background_alt = "#222222"
    border = "#444444"


class _DummyThemeManager:
    current_theme = _DummyTheme()


def test_queue_delegate_paint_does_not_mutate_parent_cursor(qapp, monkeypatch):
    """Painting hovered rows must not leak pointing cursor to the parent widget."""
    parent = _CursorTrackingParent()
    delegate = QueueItemDelegate(parent)
    model = QueueTrackModel(parent)
    model.reset_tracks([
        {
            "title": "Song",
            "artist": "Artist",
            "album": "Album",
            "duration": 120,
            "source": "Local",
            "path": "/tmp/song.mp3",
        }
    ])
    index = model.index(0)
    option = delegate._make_style_option(index)
    option.state |= QStyle.StateFlag.State_MouseOver
    pixmap = QPixmap(400, 82)
    painter = QPainter(pixmap)

    monkeypatch.setattr(
        "ui.views.queue_view.CoverPixmapCache.get",
        lambda cache_key: QPixmap(64, 64),
    )
    monkeypatch.setattr(
        "system.theme.ThemeManager.instance",
        lambda: _DummyThemeManager(),
    )

    try:
        delegate.paint(painter, option, index)
    finally:
        painter.end()

    assert parent.set_cursor_calls == 0
