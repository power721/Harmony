"""Tests for ArtistView lazy loading behavior."""

import os
from unittest.mock import MagicMock, Mock

import pytest
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from domain.artist import Artist
from domain.track import Track, TrackSource
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
