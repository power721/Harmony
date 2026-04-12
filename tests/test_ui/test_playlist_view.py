"""
Tests for PlaylistView list-view behavior.
"""

import os
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock

import pytest
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import QApplication

from domain.playlist import Playlist
from domain.playlist_folder import PlaylistFolder, PlaylistFolderGroup, PlaylistTree
from domain.track import Track, TrackSource
from system.event_bus import EventBus
from system.theme import ThemeManager
from ui.views.playlist_view import PlaylistView

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


def test_playlist_view_loads_tracks_into_list_view(qapp, mock_theme_config):
    ThemeManager.instance(mock_theme_config)

    playlist_service = MagicMock()
    favorite_service = MagicMock()
    library_service = MagicMock()
    player = MagicMock()
    player.engine = MagicMock()

    playlist = Playlist(id=1, name="My Playlist")
    playlist_service.get_playlist_tree.return_value = PlaylistTree(root_playlists=[playlist], folders=[])
    tracks = [
        Track(id=1, path="/music/1.mp3", title="One", source=TrackSource.LOCAL),
        Track(
            id=2,
            path="online://qqmusic/track/2",
            title="Two",
            source=TrackSource.ONLINE,
            cloud_file_id="2",
            online_provider_id="qqmusic",
        ),
    ]

    playlist_service.get_playlist.return_value = playlist
    playlist_service.get_playlist_tracks.return_value = tracks
    favorite_service.get_all_favorite_track_ids.return_value = {1}

    view = PlaylistView(
        playlist_service=playlist_service,
        favorite_service=favorite_service,
        library_service=library_service,
        player=player,
    )

    view._load_playlist(playlist.id)
    qapp.processEvents()

    assert hasattr(view, "_tracks_list_view")
    assert view._tracks_list_view.row_count() == 2


def test_playlist_view_renders_folder_and_root_nodes(qapp, mock_theme_config):
    ThemeManager.instance(mock_theme_config)

    playlist_service = MagicMock()
    favorite_service = MagicMock()
    library_service = MagicMock()
    player = MagicMock()
    player.engine = MagicMock()

    folder = PlaylistFolder(id=10, name="Gym", position=0)
    tree = PlaylistTree(
        root_playlists=[Playlist(id=1, name="Inbox", position=0)],
        folders=[
            PlaylistFolderGroup(
                folder=folder,
                playlists=[Playlist(id=2, name="Run", folder_id=10, position=0)],
            )
        ],
    )
    playlist_service.get_playlist_tree.return_value = tree
    favorite_service.get_all_favorite_track_ids.return_value = set()

    view = PlaylistView(playlist_service, favorite_service, library_service, player)

    assert view._playlist_tree.topLevelItemCount() == 2
    assert view._playlist_tree.topLevelItem(0).text(0) == "Gym"
    assert view._playlist_tree.topLevelItem(1).text(0) == "Inbox"


def test_clicking_folder_only_toggles_expansion(qapp, mock_theme_config):
    ThemeManager.instance(mock_theme_config)

    playlist_service = MagicMock()
    favorite_service = MagicMock()
    library_service = MagicMock()
    player = MagicMock()
    player.engine = MagicMock()

    folder = PlaylistFolder(id=10, name="Gym", position=0)
    tree = PlaylistTree(
        root_playlists=[],
        folders=[PlaylistFolderGroup(folder=folder, playlists=[])],
    )
    playlist_service.get_playlist_tree.return_value = tree
    favorite_service.get_all_favorite_track_ids.return_value = set()

    view = PlaylistView(playlist_service, favorite_service, library_service, player)
    item = view._playlist_tree.topLevelItem(0)

    view._on_tree_item_clicked(item, 0)

    assert view._current_playlist_id is None
    assert item.isExpanded() is True


class _FakeSignal:
    def __init__(self):
        self.connected = []

    def connect(self, slot):
        self.connected.append(slot)

    def disconnect(self, slot):
        self.connected.remove(slot)


def test_playlist_view_close_event_disconnects_event_bus(qapp, mock_theme_config, monkeypatch):
    ThemeManager.instance(mock_theme_config)

    fake_bus = SimpleNamespace(
        favorite_changed=_FakeSignal(),
        track_changed=_FakeSignal(),
        playback_state_changed=_FakeSignal(),
        cover_updated=_FakeSignal(),
        playlist_created=_FakeSignal(),
        playlist_modified=_FakeSignal(),
        playlist_structure_changed=_FakeSignal(),
    )
    monkeypatch.setattr(EventBus, "instance", classmethod(lambda cls: fake_bus))

    playlist_service = MagicMock()
    favorite_service = MagicMock()
    library_service = MagicMock()
    player = MagicMock()
    player.engine = MagicMock()

    playlist_service.get_playlist_tree.return_value = PlaylistTree(root_playlists=[], folders=[])
    favorite_service.get_all_favorite_track_ids.return_value = set()

    view = PlaylistView(
        playlist_service=playlist_service,
        favorite_service=favorite_service,
        library_service=library_service,
        player=player,
    )

    assert view._on_playlist_created in fake_bus.playlist_created.connected
    assert view._on_playlist_modified in fake_bus.playlist_modified.connected

    view.closeEvent(QCloseEvent())

    assert view._on_playlist_created not in fake_bus.playlist_created.connected
    assert view._on_playlist_modified not in fake_bus.playlist_modified.connected


def test_playlist_view_subscribes_to_structure_signal(qapp, mock_theme_config, monkeypatch):
    ThemeManager.instance(mock_theme_config)

    fake_bus = SimpleNamespace(
        favorite_changed=_FakeSignal(),
        track_changed=_FakeSignal(),
        playback_state_changed=_FakeSignal(),
        cover_updated=_FakeSignal(),
        playlist_created=_FakeSignal(),
        playlist_modified=_FakeSignal(),
        playlist_structure_changed=_FakeSignal(),
    )
    monkeypatch.setattr(EventBus, "instance", classmethod(lambda cls: fake_bus))

    playlist_service = MagicMock()
    favorite_service = MagicMock()
    library_service = MagicMock()
    player = MagicMock()
    player.engine = MagicMock()
    playlist_service.get_playlist_tree.return_value = PlaylistTree(root_playlists=[], folders=[])
    favorite_service.get_all_favorite_track_ids.return_value = set()

    view = PlaylistView(playlist_service, favorite_service, library_service, player)

    assert view._on_playlist_structure_changed in fake_bus.playlist_structure_changed.connected
