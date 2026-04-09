"""
Tests for LibraryView list-only behavior.
"""

import os
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock

import pytest
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import QApplication, QDialog

from app.application import Application
from domain.history import PlayHistory
from domain.playlist_item import PlaylistItem
from domain.track import Track, TrackSource
from system.event_bus import EventBus
from system.theme import ThemeManager
from ui.views.library_view import LibraryView

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


@pytest.fixture(autouse=True)
def reset_theme_singleton():
    ThemeManager._instance = None
    yield
    ThemeManager._instance = None


@pytest.fixture
def mock_theme_config():
    config = Mock()
    config.get.return_value = "dark"
    return config


@pytest.fixture
def sample_tracks():
    return [
        Track(id=1, path="/music/one.mp3", title="One", artist="Artist 1", source=TrackSource.LOCAL),
        Track(
            id=2,
            path="online://qqmusic/track/two",
            title="Two",
            artist="Artist 2",
            source=TrackSource.ONLINE,
            cloud_file_id="two",
            online_provider_id="qqmusic",
        ),
    ]


def _build_library_view(theme_config, sample_tracks):
    ThemeManager.instance(theme_config)

    library_service = MagicMock()
    library_service.get_track_count.return_value = len(sample_tracks)
    library_service.get_all_tracks.return_value = sample_tracks
    library_service.search_tracks.return_value = sample_tracks
    library_service.get_search_track_count.return_value = len(sample_tracks)
    library_service.get_tracks_by_ids.return_value = sample_tracks
    library_service.get_track.side_effect = lambda track_id: next(
        (track for track in sample_tracks if track.id == track_id),
        None,
    )

    favorites_service = MagicMock()
    favorites_service.get_all_favorite_track_ids.return_value = {track.id for track in sample_tracks}
    favorites_service.get_favorites.return_value = sample_tracks

    history_service = MagicMock()
    history_service.get_history.return_value = [
        PlayHistory(track_id=sample_tracks[0].id, played_at=datetime(2026, 4, 2, 12, 0, 0))
    ]
    history_service.get_history_tracks.return_value = sample_tracks

    engine = MagicMock()
    engine.current_track_changed = MagicMock()
    engine.current_track_pending = MagicMock()
    engine.state_changed = MagicMock()
    engine.state = None
    engine.playlist_items = []

    player = MagicMock()
    player.engine = engine

    library_config = MagicMock()

    def get_value(key, default=None):
        if key == "view/history_view_mode":
            raise AssertionError("LibraryView should not read history view mode in list-only mode")
        return default

    library_config.get.side_effect = get_value

    view = LibraryView(
        library_service,
        favorites_service,
        history_service,
        player,
        config_manager=library_config,
    )

    return view, library_service, favorites_service, history_service


def test_library_view_avoids_history_view_mode_config_in_list_only_mode(qapp, mock_theme_config, sample_tracks):
    view, _, _, _ = _build_library_view(mock_theme_config, sample_tracks)
    assert view is not None
    assert not hasattr(view, "_view_toggle_btn")


def test_library_view_show_favorites_uses_list_view(qapp, mock_theme_config, sample_tracks):
    view, _, _, _ = _build_library_view(mock_theme_config, sample_tracks)

    view.show_favorites()
    qapp.processEvents()

    assert hasattr(view, "_favorites_list_view")
    assert view._stacked_widget.currentWidget() is view._favorites_list_view
    assert view._favorites_list_view.row_count() == len(sample_tracks)


def test_library_view_show_history_uses_history_list_view(qapp, mock_theme_config, sample_tracks):
    view, _, _, history_service = _build_library_view(mock_theme_config, sample_tracks)

    view.show_history()
    qapp.processEvents()

    history_service.get_history.assert_called()
    assert view._stacked_widget.currentWidget() is view._history_list_view
    assert view._history_list_view.row_count() == 1


def test_favorites_double_click_loads_all_favorites_from_clicked_track(
        qapp, mock_theme_config, sample_tracks
):
    view, _, favorites_service, _ = _build_library_view(mock_theme_config, sample_tracks)

    favorites = [
        Track(id=10, path="/music/ten.mp3", title="Ten", source=TrackSource.LOCAL),
        Track(id=20, path="/music/twenty.mp3", title="Twenty", source=TrackSource.LOCAL),
        Track(id=30, path="/music/thirty.mp3", title="Thirty", source=TrackSource.LOCAL),
    ]
    favorites_service.get_favorites.return_value = favorites

    view._on_favorites_track_activated(favorites[1])

    view._player.play_local_tracks.assert_called_once_with([10, 20, 30], start_index=1)


def test_history_double_click_keeps_existing_queue_when_track_already_present(
        qapp, mock_theme_config, sample_tracks
):
    view, _, _, history_service = _build_library_view(mock_theme_config, sample_tracks)
    view._player.engine.playlist_items = [
        PlaylistItem(track_id=99, title="Other"),
        PlaylistItem(track_id=sample_tracks[1].id, title=sample_tracks[1].title),
    ]

    view._on_history_track_activated(sample_tracks[1])

    view._player.engine.play_at.assert_called_once_with(1)
    view._player.play_local_tracks.assert_not_called()
    history_service.get_history_tracks.assert_not_called()


def test_history_double_click_loads_recent_history_when_track_not_in_queue(
        qapp, mock_theme_config, sample_tracks
):
    view, _, _, history_service = _build_library_view(mock_theme_config, sample_tracks)
    recent_tracks = [
        Track(id=11, path="/music/eleven.mp3", title="Eleven", source=TrackSource.LOCAL),
        Track(id=22, path="/music/twenty-two.mp3", title="Twenty Two", source=TrackSource.LOCAL),
        Track(id=33, path="/music/thirty-three.mp3", title="Thirty Three", source=TrackSource.LOCAL),
    ]
    history_service.get_history_tracks.return_value = recent_tracks
    view._player.engine.playlist_items = [PlaylistItem(track_id=999, title="Other")]

    view._on_history_track_activated(recent_tracks[2])

    history_service.get_history_tracks.assert_called_once_with(limit=100)
    view._player.play_local_tracks.assert_called_once_with([11, 22, 33], start_index=2)
    view._player.engine.play_at.assert_not_called()


class _FakeSignal:
    def __init__(self):
        self.connected = []

    def connect(self, slot):
        self.connected.append(slot)

    def disconnect(self, slot):
        self.connected.remove(slot)


def test_library_view_close_event_disconnects_external_signals(
    qapp, mock_theme_config, sample_tracks, monkeypatch
):
    ThemeManager.instance(mock_theme_config)

    fake_bus = SimpleNamespace(
        favorite_changed=_FakeSignal(),
        tracks_organized=_FakeSignal(),
        track_changed=_FakeSignal(),
        playback_state_changed=_FakeSignal(),
        cover_updated=_FakeSignal(),
    )
    monkeypatch.setattr(EventBus, "instance", classmethod(lambda cls: fake_bus))

    library_service = MagicMock()
    library_service.get_track_count.return_value = len(sample_tracks)
    library_service.get_all_tracks.return_value = sample_tracks
    library_service.search_tracks.return_value = sample_tracks
    library_service.get_search_track_count.return_value = len(sample_tracks)
    library_service.get_tracks_by_ids.return_value = sample_tracks

    favorites_service = MagicMock()
    favorites_service.get_all_favorite_track_ids.return_value = set()
    favorites_service.get_favorites.return_value = []

    history_service = MagicMock()
    history_service.get_history.return_value = []

    engine = SimpleNamespace(
        current_track_changed=_FakeSignal(),
        current_track_pending=_FakeSignal(),
        state_changed=_FakeSignal(),
        state=None,
        playlist_items=[],
    )
    player = SimpleNamespace(engine=engine)

    view = LibraryView(
        library_service,
        favorites_service,
        history_service,
        player,
        config_manager=MagicMock(),
    )

    assert view._on_current_track_changed in engine.current_track_changed.connected
    assert view._on_current_track_changed in engine.current_track_pending.connected
    assert view._on_player_state_changed in engine.state_changed.connected
    assert view._on_tracks_organized in fake_bus.tracks_organized.connected
    assert view._on_favorite_changed in fake_bus.favorite_changed.connected

    view.closeEvent(QCloseEvent())

    assert view._on_current_track_changed not in engine.current_track_changed.connected
    assert view._on_current_track_changed not in engine.current_track_pending.connected
    assert view._on_player_state_changed not in engine.state_changed.connected
    assert view._on_tracks_organized not in fake_bus.tracks_organized.connected
    assert view._on_favorite_changed not in fake_bus.favorite_changed.connected


def test_library_view_opens_organize_dialog_when_list_view_requests_it(
    qapp, mock_theme_config, sample_tracks, monkeypatch
):
    view, _, _, _ = _build_library_view(mock_theme_config, sample_tracks)

    fake_file_org_service = MagicMock()
    fake_app = SimpleNamespace(
        bootstrap=SimpleNamespace(file_org_service=fake_file_org_service)
    )
    monkeypatch.setattr(
        Application,
        "instance",
        classmethod(lambda cls: fake_app),
    )

    import ui.dialogs.organize_files_dialog as organize_dialog_module

    created = {}

    class FakeDialog:
        def __init__(self, tracks, file_org_service, config_manager, parent=None):
            created["tracks"] = tracks
            created["file_org_service"] = file_org_service
            created["config_manager"] = config_manager
            created["parent"] = parent

        def exec(self):
            return QDialog.Accepted

    monkeypatch.setattr(organize_dialog_module, "OrganizeFilesDialog", FakeDialog)
    view.refresh = MagicMock()

    view._all_tracks_list_view.organize_files_requested.emit([sample_tracks[0]])

    assert created["tracks"] == [sample_tracks[0]]
    assert created["file_org_service"] is fake_file_org_service
    assert created["config_manager"] is view._config
    assert created["parent"] is view
    view.refresh.assert_called_once()
