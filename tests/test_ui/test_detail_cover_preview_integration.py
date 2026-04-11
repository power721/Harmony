"""Integration tests for local detail views using the shared cover preview."""

import os
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from PySide6.QtWidgets import QApplication

import ui.views.album_view as album_module
import ui.views.artist_view as artist_module
import ui.views.genre_view as genre_module
from system.theme import ThemeManager
from ui.views.album_view import AlbumView
from ui.views.artist_view import ArtistView
from ui.views.genre_view import GenreView

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
def theme_config():
    config = Mock()
    config.get.return_value = "dark"
    return config


def test_album_view_cover_click_uses_shared_preview(qapp, theme_config, monkeypatch):
    ThemeManager.instance(theme_config)
    calls = []
    monkeypatch.setattr(
        album_module,
        "show_cover_preview",
        lambda parent, image_source, title="", request_headers=None: calls.append(
            (parent, image_source, title, request_headers)
        ),
    )

    view = AlbumView(library_service=Mock())
    view._album = SimpleNamespace(display_name="Album A")
    view._current_cover_path = "/tmp/album-cover.png"

    view._on_cover_clicked()

    assert calls == [(view, "/tmp/album-cover.png", "Album A", None)]


def test_artist_view_cover_click_uses_shared_preview(qapp, theme_config, monkeypatch):
    ThemeManager.instance(theme_config)
    calls = []
    monkeypatch.setattr(
        artist_module,
        "show_cover_preview",
        lambda parent, image_source, title="", request_headers=None: calls.append(
            (parent, image_source, title, request_headers)
        ),
    )

    view = ArtistView(library_service=Mock())
    view._artist = SimpleNamespace(display_name="Artist A")
    view._current_cover_path = "/tmp/artist-cover.png"

    view._on_cover_clicked()

    assert calls == [(view, "/tmp/artist-cover.png", "Artist A", None)]


def test_genre_view_cover_click_uses_shared_preview(qapp, theme_config, monkeypatch):
    ThemeManager.instance(theme_config)
    calls = []
    monkeypatch.setattr(
        genre_module,
        "show_cover_preview",
        lambda parent, image_source, title="", request_headers=None: calls.append(
            (parent, image_source, title, request_headers)
        ),
    )

    view = GenreView(library_service=Mock())
    view._genre = SimpleNamespace(display_name="Genre A")
    view._current_cover_path = "/tmp/genre-cover.png"

    view._on_cover_clicked()

    assert calls == [(view, "/tmp/genre-cover.png", "Genre A", None)]
