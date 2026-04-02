"""Smoke tests for OnlineTracksListView hover behavior."""

import os
from unittest.mock import MagicMock, PropertyMock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from domain.online_music import OnlineTrack
from ui.views.online_tracks_list_view import OnlineTracksListView


def test_online_tracks_cover_hover_starts_timer_on_cover_area():
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

    bus = MagicMock()

    class _MouseEvent:
        def __init__(self, pos):
            self._pos = pos

        def pos(self):
            return self._pos

    with patch("system.theme.ThemeManager.instance", return_value=theme_manager), \
         patch("system.event_bus.EventBus.instance", return_value=bus):
        view = OnlineTracksListView()
        view.resize(900, 300)
        view.show()
        app.processEvents()

        tracks = [OnlineTrack(mid="mid-1", title="Song", duration=180)]
        view.load_tracks(tracks, favorite_mids=set())
        app.processEvents()

        index = view._model.index(0)
        item_rect = view._list_view.visualRect(index)
        cover_rect = view._delegate.cover_rect_for_item(item_rect)
        view._handle_mouse_move(_MouseEvent(cover_rect.center()))

        assert view._hovered_row == 0
        assert view._hover_timer.isActive()


def test_online_tracks_handle_mouse_leave_is_idempotent_when_idle():
    """When already idle, repeated leave handling should do nothing."""
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

    bus = MagicMock()

    with patch("system.theme.ThemeManager.instance", return_value=theme_manager), \
         patch("system.event_bus.EventBus.instance", return_value=bus):
        view = OnlineTracksListView()
        view.show()
        app.processEvents()

        view._hovered_row = -1
        view._hover_timer.stop()
        view._cover_popup.schedule_hide = MagicMock()

        view._handle_mouse_leave()

        view._cover_popup.schedule_hide.assert_not_called()
