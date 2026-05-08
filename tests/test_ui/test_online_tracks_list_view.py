"""Smoke tests for OnlineTracksListView hover behavior."""

import os
from unittest.mock import MagicMock, PropertyMock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from domain.online_music import OnlineTrack
from plugins.builtin.qqmusic.lib.context_menus import OnlineTrackContextMenu
import plugins.builtin.qqmusic.lib.online_tracks_list_view as online_tracks_list_view
from plugins.builtin.qqmusic.lib.online_tracks_list_view import OnlineTracksListView
from tests.test_plugins.qqmusic_test_context import bind_test_context


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
    bus.favorite_changed = MagicMock()
    bus.favorite_changed.connect = MagicMock()
    bus.favorite_changed.disconnect = MagicMock()

    class _MouseEvent:
        def __init__(self, pos):
            self._pos = pos

        def pos(self):
            return self._pos

    with patch("system.theme.ThemeManager.instance", return_value=theme_manager):
        bind_test_context(theme_manager=theme_manager, event_bus=bus)
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
        view.close()
        app.processEvents()


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
    bus.favorite_changed = MagicMock()
    bus.favorite_changed.connect = MagicMock()
    bus.favorite_changed.disconnect = MagicMock()

    with patch("system.theme.ThemeManager.instance", return_value=theme_manager):
        bind_test_context(theme_manager=theme_manager, event_bus=bus)
        view = OnlineTracksListView()
        view.show()
        app.processEvents()

        view._hovered_row = -1
        view._hover_timer.stop()
        view._cover_popup.schedule_hide = MagicMock()

        view._handle_mouse_leave()

        view._cover_popup.schedule_hide.assert_not_called()
        view.close()
        app.processEvents()


def test_online_tracks_cover_resolution_uses_existing_cover_service_only(monkeypatch):
    """Background cover workers must not bootstrap host services from scratch."""

    class _BootstrapStub:
        def __init__(self):
            self._cover_service = None
            self.cover_service_accessed = False

        @property
        def cover_service(self):
            self.cover_service_accessed = True
            raise RuntimeError("cover_service should not be initialized in worker")

    bootstrap = _BootstrapStub()
    track = OnlineTrack(mid="mid-1", title="Song", duration=180)

    assert online_tracks_list_view._resolve_online_cover_path(track) is None
    assert bootstrap.cover_service_accessed is False


def test_context_menu_qq_label_uses_remote_favorites_only():
    track = OnlineTrack(mid="mid-1", title="Song", duration=180)
    labels = []

    class _Signal:
        def connect(self, _callback):
            return None

    class _Action:
        def __init__(self, text):
            self.text = text
            self.triggered = _Signal()

    class _Menu:
        def __init__(self, parent=None):
            self.parent = parent

        def addAction(self, text):
            labels.append(text)
            return _Action(text)

        def addSeparator(self):
            return None

        def exec_(self, *_args, **_kwargs):
            return None

    with patch("plugins.builtin.qqmusic.lib.context_menus.QMenu", _Menu):
        menu = OnlineTrackContextMenu()
        menu.show_menu(
            [track],
            favorite_mids={"mid-1"},
            qq_favorite_mids=set(),
            parent_widget=None,
        )

    assert "Remove" in labels[3]
    assert "Favorite" in labels[3]
    assert "Remove" not in labels[4]
    assert "QQ" in labels[4]


def test_online_tracks_view_load_tracks_stores_qq_favorite_mids():
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
    bus.favorite_changed = MagicMock()
    bus.favorite_changed.connect = MagicMock()
    bus.favorite_changed.disconnect = MagicMock()

    with patch("system.theme.ThemeManager.instance", return_value=theme_manager):
        bind_test_context(theme_manager=theme_manager, event_bus=bus)
        view = OnlineTracksListView()
        tracks = [OnlineTrack(mid="mid-1", title="Song", duration=180)]

        view.load_tracks(tracks, favorite_mids=set(), qq_favorite_mids={"mid-1"})

        assert view._model._favorite_mids == set()
        assert view._model._qq_favorite_mids == {"mid-1"}
        view.close()
        app.processEvents()
