"""
Smoke tests for LocalTracksListView helper methods used by LibraryView.
"""

import os
from unittest.mock import MagicMock, PropertyMock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QPainter, QPixmap
from PySide6.QtWidgets import QApplication, QStyleOptionViewItem

from domain.track import Track, TrackSource
from system.theme import ThemeManager
from ui.views.history_list_view import HistoryListView
from ui.views.local_tracks_list_view import LocalTracksListView


def test_local_tracks_list_view_supports_append_and_track_selection():
    """Paged loading helpers should preserve row lookup and selection by track ID."""
    app = QApplication.instance() or QApplication([])
    theme_manager = MagicMock()
    theme = MagicMock()
    theme.background = "#101010"
    theme.background_alt = "#1a1a1a"
    theme.background_hover = "#202020"
    theme.text = "#ffffff"
    theme.text_secondary = "#b3b3b3"
    theme.highlight = "#1db954"
    theme.border = "#404040"
    type(theme_manager).current_theme = PropertyMock(return_value=theme)

    with patch("system.theme.ThemeManager.instance", return_value=theme_manager):
        view = LocalTracksListView()
        view.show()
        app.processEvents()

        first_page = [
            Track(id=1, path="/music/1.mp3", title="One", source=TrackSource.LOCAL),
            Track(id=2, path="/music/2.mp3", title="Two", source=TrackSource.LOCAL),
        ]
        next_page = [
            Track(id=3, path="/music/3.mp3", title="Three", source=TrackSource.LOCAL),
        ]

        view.load_tracks(first_page, favorite_ids=set())
        view.append_tracks(next_page)

        assert view.row_count() == 3
        assert view.select_track_by_id(3) is True
        app.processEvents()
        assert [track.id for track in view.selected_tracks()] == [3]


def test_local_tracks_cover_hover_starts_timer_on_cover_area():
    """Hovering the cover area should start the delayed popup timer."""
    app = QApplication.instance() or QApplication([])
    theme_manager = MagicMock()
    theme = MagicMock()
    theme.background = "#101010"
    theme.background_alt = "#1a1a1a"
    theme.background_hover = "#202020"
    theme.text = "#ffffff"
    theme.text_secondary = "#b3b3b3"
    theme.highlight = "#1db954"
    theme.border = "#404040"
    type(theme_manager).current_theme = PropertyMock(return_value=theme)

    class _MouseEvent:
        def __init__(self, pos):
            self._pos = pos

        def pos(self):
            return self._pos

    with patch("system.theme.ThemeManager.instance", return_value=theme_manager):
        view = LocalTracksListView()
        view.resize(900, 300)
        view.show()
        app.processEvents()

        tracks = [Track(id=10, path="/music/10.mp3", title="Hover", source=TrackSource.LOCAL)]
        view.load_tracks(tracks, favorite_ids=set())
        app.processEvents()

        index = view._model.index(0)
        item_rect = view._list_view.visualRect(index)
        cover_rect = view._delegate.cover_rect_for_item(item_rect)
        view._handle_mouse_move(_MouseEvent(cover_rect.center()))

        assert view._hovered_row == 0
        assert view._hover_timer.isActive()


def test_local_tracks_list_view_uses_theme_background_for_empty_state():
    """An empty track list should inherit the main theme background."""
    app = QApplication.instance() or QApplication([])
    theme_manager = MagicMock()
    theme = MagicMock()
    theme.background = "#101010"
    theme.background_alt = "#1a1a1a"
    theme.background_hover = "#202020"
    theme.text = "#ffffff"
    theme.text_secondary = "#b3b3b3"
    theme.highlight = "#1db954"
    theme.border = "#404040"
    type(theme_manager).current_theme = PropertyMock(return_value=theme)

    with patch("system.theme.ThemeManager.instance", return_value=theme_manager):
        view = LocalTracksListView()
        view.load_tracks([], favorite_ids=set())

        stylesheet = view._list_view.styleSheet()
        assert theme.background in stylesheet
        assert theme.background_alt not in stylesheet


def test_local_tracks_list_view_falls_back_when_theme_manager_is_uninitialized():
    """View construction and delegate paint should not require ThemeManager singleton."""
    app = QApplication.instance() or QApplication([])
    ThemeManager._instance = None

    view = LocalTracksListView()
    view.resize(900, 300)
    view.show()
    app.processEvents()

    view.load_tracks(
        [Track(id=11, path="/music/11.mp3", title="Fallback", source=TrackSource.LOCAL)],
        favorite_ids=set(),
    )
    app.processEvents()

    option = QStyleOptionViewItem()
    index = view._model.index(0)
    option.rect = view._list_view.visualRect(index)
    pixmap = QPixmap(option.rect.size())
    painter = QPainter(pixmap)
    view._delegate.paint(painter, option, index)
    painter.end()


def test_history_list_view_cover_hover_works_with_history_delegate():
    """HistoryListView should support cover hover even without delegate-specific helper."""
    app = QApplication.instance() or QApplication([])
    theme_manager = MagicMock()
    theme = MagicMock()
    theme.background = "#101010"
    theme.background_alt = "#1a1a1a"
    theme.background_hover = "#202020"
    theme.text = "#ffffff"
    theme.text_secondary = "#b3b3b3"
    theme.highlight = "#1db954"
    theme.border = "#404040"
    type(theme_manager).current_theme = PropertyMock(return_value=theme)

    class _MouseEvent:
        def __init__(self, pos):
            self._pos = pos

        def pos(self):
            return self._pos

    with patch("system.theme.ThemeManager.instance", return_value=theme_manager):
        view = HistoryListView()
        view.resize(900, 300)
        view.show()
        app.processEvents()

        track = Track(id=20, path="/music/20.mp3", title="History Hover", source=TrackSource.LOCAL)
        view.load_tracks([track], played_at_map={}, favorite_ids=set())
        app.processEvents()

        index = view._model.index(0)
        item_rect = view._list_view.visualRect(index)
        cover_rect = view._cover_rect_for_item(item_rect)
        view._handle_mouse_move(_MouseEvent(cover_rect.center()))

        assert view._hovered_row == 0
        assert view._hover_timer.isActive()
