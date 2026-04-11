"""Tests for GenreView cover loading behavior."""

import os
from unittest.mock import Mock

import pytest
from PySide6.QtCore import QByteArray, QBuffer, QIODevice, Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QApplication, QTableWidget

from domain.genre import Genre
from infrastructure.cache.image_cache import ImageCache
from system.theme import ThemeManager
from ui.views.genre_view import GenreView
from ui.views.local_tracks_list_view import LocalTracksListView

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


def _make_png_bytes() -> bytes:
    pixmap = QPixmap(8, 8)
    pixmap.fill(Qt.blue)

    ba = QByteArray()
    buffer = QBuffer(ba)
    buffer.open(QIODevice.WriteOnly)
    pixmap.save(buffer, "PNG")
    buffer.close()
    return bytes(ba)


def test_genre_view_normalizes_qq_cover_url(qapp, mock_theme_config):
    ThemeManager.instance(mock_theme_config)

    view = GenreView(library_service=Mock())
    url, headers = view._prepare_cover_request(
        "https://y.qq.com/music/photo_new/T002R300x300M000abc.jpg"
    )

    assert url == "https://y.gtimg.cn/music/photo_new/T002R300x300M000abc.jpg"
    assert headers == {"Referer": "https://y.qq.com/"}


def test_genre_view_loads_cover_from_cached_online_url(qapp, mock_theme_config, monkeypatch):
    ThemeManager.instance(mock_theme_config)

    cover_url = "https://example.com/genre-cover.png"
    image_data = _make_png_bytes()
    monkeypatch.setattr(ImageCache, "get", lambda url: image_data if url == cover_url else None)

    view = GenreView(library_service=Mock())
    view._load_cover(Genre(name="Rock", cover_path=cover_url))

    assert view._current_cover_path == cover_url
    assert view._cover_label.pixmap() is not None


def test_genre_view_uses_local_tracks_list_view(qapp, mock_theme_config):
    ThemeManager.instance(mock_theme_config)

    view = GenreView(library_service=Mock())

    assert isinstance(view._tracks_list, LocalTracksListView)
    assert view.findChild(QTableWidget) is None


def test_genre_view_forwards_all_context_menu_signals(qapp, mock_theme_config):
    ThemeManager.instance(mock_theme_config)

    view = GenreView(library_service=Mock())
    track = Mock()
    tracks = [track]

    captured = {
        "insert": None,
        "add": None,
        "playlist": None,
        "fav": None,
        "edit": None,
        "cover": None,
        "open": None,
        "remove": None,
        "delete": None,
        "redownload": None,
    }

    view.insert_to_queue.connect(lambda payload: captured.__setitem__("insert", payload))
    view.add_to_queue.connect(lambda payload: captured.__setitem__("add", payload))
    view.add_to_playlist.connect(lambda payload: captured.__setitem__("playlist", payload))
    view.favorites_toggle_requested.connect(
        lambda payload, all_favorited: captured.__setitem__("fav", (payload, all_favorited))
    )
    view.edit_info_requested.connect(lambda payload: captured.__setitem__("edit", payload))
    view.download_cover_requested.connect(lambda payload: captured.__setitem__("cover", payload))
    view.open_file_location_requested.connect(lambda payload: captured.__setitem__("open", payload))
    view.remove_from_library_requested.connect(lambda payload: captured.__setitem__("remove", payload))
    view.delete_file_requested.connect(lambda payload: captured.__setitem__("delete", payload))
    view.redownload_requested.connect(lambda payload: captured.__setitem__("redownload", payload))

    view._tracks_list.insert_to_queue_requested.emit(tracks)
    view._tracks_list.add_to_queue_requested.emit(tracks)
    view._tracks_list.add_to_playlist_requested.emit(tracks)
    view._tracks_list.favorites_toggle_requested.emit(tracks, True)
    view._tracks_list.edit_info_requested.emit(track)
    view._tracks_list.download_cover_requested.emit(track)
    view._tracks_list.open_file_location_requested.emit(track)
    view._tracks_list.remove_from_library_requested.emit(tracks)
    view._tracks_list.delete_file_requested.emit(tracks)
    view._tracks_list.redownload_requested.emit(track)

    assert captured["insert"] == tracks
    assert captured["add"] == tracks
    assert captured["playlist"] == tracks
    assert captured["fav"] == (tracks, True)
    assert captured["edit"] is track
    assert captured["cover"] is track
    assert captured["open"] is track
    assert captured["remove"] == tracks
    assert captured["delete"] == tracks
    assert captured["redownload"] is track


def test_genre_view_cover_is_clickable(qapp, mock_theme_config):
    ThemeManager.instance(mock_theme_config)

    view = GenreView(library_service=Mock())

    assert view._cover_label.cursor().shape() == Qt.CursorShape.PointingHandCursor
