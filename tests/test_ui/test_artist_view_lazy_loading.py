"""Tests for ArtistView lazy loading behavior."""

import os
from unittest.mock import MagicMock, Mock

import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from domain.album import Album
from domain.artist import Artist
from domain.track import Track, TrackSource
from system.i18n import t
from system.theme import ThemeManager
from ui.views.artist_view import ArtistView

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


def _build_tracks(count: int) -> list[Track]:
    return [
        Track(
            id=i + 1,
            path=f"/music/{i + 1}.mp3",
            title=f"Song {i + 1}",
            artist="Lazy Artist",
            album="Lazy Album",
            duration=180,
            source=TrackSource.LOCAL,
        )
        for i in range(count)
    ]


def _build_albums(count: int) -> list[Album]:
    return [
        Album(
            name=f"Album {i + 1}",
            artist="Lazy Artist",
            song_count=10,
            duration=1800,
        )
        for i in range(count)
    ]


def test_artist_view_tracks_lazy_load_in_batches(qapp, mock_theme_config):
    ThemeManager.instance(mock_theme_config)

    tracks = _build_tracks(250)
    artist = Artist(name="Lazy Artist", song_count=len(tracks), album_count=0)

    library_service = MagicMock()
    library_service.get_artist_albums.return_value = []
    library_service.get_artist_tracks.return_value = tracks

    view = ArtistView(library_service=library_service)
    view.set_artist(artist)

    QTest.qWait(30)
    qapp.processEvents()

    # Initial render should only load first batch.
    assert view._tracks_table.rowCount() == view.TRACKS_BATCH_SIZE

    # Simulate scrolling near the end to trigger load-more.
    view._on_tracks_scroll_changed(view._tracks_table.verticalScrollBar().maximum())
    qapp.processEvents()
    assert view._tracks_table.rowCount() == view.TRACKS_BATCH_SIZE * 2

    # Continue loading until all rows are rendered.
    guard = 0
    while view._tracks_table.rowCount() < len(tracks) and guard < len(tracks):
        view._on_tracks_scroll_changed(view._tracks_table.verticalScrollBar().maximum())
        qapp.processEvents()
        guard += 1

    assert view._tracks_table.rowCount() == len(tracks)


def test_artist_view_albums_lazy_load_in_batches(qapp, mock_theme_config):
    ThemeManager.instance(mock_theme_config)

    albums = _build_albums(95)
    artist = Artist(name="Lazy Artist", song_count=0, album_count=len(albums))

    library_service = MagicMock()
    library_service.get_artist_albums.return_value = albums
    library_service.get_artist_tracks.return_value = []

    view = ArtistView(library_service=library_service)
    view.set_artist(artist)

    QTest.qWait(30)
    qapp.processEvents()

    # Initial render should only load first batch.
    assert len(view._album_cards) == view.ALBUMS_BATCH_SIZE

    # Simulate scrolling near the end to trigger load-more.
    view._on_albums_scroll_changed(view._albums_scroll_area.verticalScrollBar().maximum())
    qapp.processEvents()
    assert len(view._album_cards) == view.ALBUMS_BATCH_SIZE * 2

    # Continue loading until all cards are rendered.
    guard = 0
    while len(view._album_cards) < len(albums) and guard < len(albums):
        view._on_albums_scroll_changed(view._albums_scroll_area.verticalScrollBar().maximum())
        qapp.processEvents()
        guard += 1

    assert len(view._album_cards) == len(albums)


def test_artist_view_uses_tabs_for_albums_and_tracks(qapp, mock_theme_config):
    ThemeManager.instance(mock_theme_config)

    library_service = MagicMock()
    library_service.get_artist_albums.return_value = _build_albums(1)
    library_service.get_artist_tracks.return_value = _build_tracks(1)

    view = ArtistView(library_service=library_service)
    view.set_artist(Artist(name="Lazy Artist", song_count=1, album_count=1))

    QTest.qWait(30)
    qapp.processEvents()

    assert view._tab_widget.count() == 2
    assert view._tab_widget.currentWidget() is view._albums_section
    assert view._tab_widget.tabText(1) == t("track")
    assert "border-bottom: 2px solid" in view._tab_widget.styleSheet()
    assert view._tab_widget.tabBar().cursor().shape() == Qt.PointingHandCursor
    assert view._albums_scroll_area.maximumHeight() > 10000
    assert not hasattr(view, "_albums_title_label")
    assert not hasattr(view, "_tracks_title_label")

    view._tab_widget.setCurrentWidget(view._tracks_section)
    qapp.processEvents()
    assert view._tab_widget.currentWidget() is view._tracks_section
