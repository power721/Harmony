"""
Tests for PlaylistView list-view behavior.
"""

import os
from unittest.mock import MagicMock, Mock

import pytest
from PySide6.QtWidgets import QApplication

from domain.playlist import Playlist
from domain.track import Track, TrackSource
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
    tracks = [
        Track(id=1, path="/music/1.mp3", title="One", source=TrackSource.LOCAL),
        Track(id=2, path="/music/2.mp3", title="Two", source=TrackSource.QQ),
    ]

    playlist_service.get_all_playlists.return_value = [playlist]
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
