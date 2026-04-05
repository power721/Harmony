"""Tests for GenresView cover loading behavior."""

import os
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from PySide6.QtCore import QByteArray, QBuffer, QIODevice, QPoint, Qt
from PySide6.QtGui import QCloseEvent, QPixmap
from PySide6.QtWidgets import QApplication, QMenu

from domain.genre import Genre
from infrastructure.cache.image_cache import ImageCache
from system.event_bus import EventBus
from system.theme import ThemeManager
from system.i18n import t
from ui.views.genres_view import GenreDelegate, GenresView

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
    pixmap.fill(Qt.red)

    ba = QByteArray()
    buffer = QBuffer(ba)
    buffer.open(QIODevice.WriteOnly)
    pixmap.save(buffer, "PNG")
    buffer.close()
    return bytes(ba)


def test_genre_delegate_loads_cover_from_cached_online_url(qapp, mock_theme_config, monkeypatch):
    ThemeManager.instance(mock_theme_config)

    cover_url = "https://example.com/cover.png"
    image_data = _make_png_bytes()
    monkeypatch.setattr(ImageCache, "get", lambda url: image_data if url == cover_url else None)

    delegate = GenreDelegate()
    loaded = delegate._load_cover(cover_url)

    assert not loaded.isNull()
    assert loaded.toImage() != delegate._default_cover.toImage()


def test_genre_delegate_normalizes_qq_cover_url(qapp, mock_theme_config):
    ThemeManager.instance(mock_theme_config)

    delegate = GenreDelegate()
    url, headers = delegate._prepare_cover_request(
        "https://y.qq.com/music/photo_new/T002R300x300M000abc.jpg"
    )

    assert url == "https://y.gtimg.cn/music/photo_new/T002R300x300M000abc.jpg"
    assert headers == {"Referer": "https://y.qq.com/"}


def test_genres_view_context_menu_includes_download_cover_action(
    qapp, mock_theme_config, monkeypatch
):
    ThemeManager.instance(mock_theme_config)

    library_service = Mock()
    view = GenresView(library_service=library_service)
    genre = Genre(name="Rock", song_count=10, album_count=3, cover_path="")
    view._model.set_genres([genre])

    # Avoid geometry-dependent hit-testing in headless tests.
    monkeypatch.setattr(
        view._list_view, "indexAt", lambda _pos: view._model.index(0, 0)
    )

    triggered = []
    view.download_cover_requested.connect(triggered.append)
    menu_texts = []

    def fake_exec(menu, *_args):
        for action in menu.actions():
            if action.isSeparator():
                continue
            menu_texts.append(action.text())
            if action.text() == t("download_cover_manual"):
                action.trigger()

    monkeypatch.setattr(QMenu, "exec_", fake_exec)

    view._show_context_menu(QPoint(0, 0))

    assert t("download_cover_manual") in menu_texts
    assert triggered == [genre]


class _FakeSignal:
    def __init__(self):
        self.connected = []

    def connect(self, slot):
        self.connected.append(slot)

    def disconnect(self, slot):
        self.connected.remove(slot)


def test_genres_view_close_event_disconnects_event_bus(
    qapp, mock_theme_config, monkeypatch
):
    ThemeManager.instance(mock_theme_config)

    fake_bus = SimpleNamespace(tracks_added=_FakeSignal())
    monkeypatch.setattr(EventBus, "instance", classmethod(lambda cls: fake_bus))

    library_service = Mock()
    view = GenresView(library_service=library_service)

    assert view._on_tracks_added in fake_bus.tracks_added.connected

    view.closeEvent(QCloseEvent())

    assert view._on_tracks_added not in fake_bus.tracks_added.connected
