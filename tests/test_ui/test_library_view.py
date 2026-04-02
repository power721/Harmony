"""
Tests for LibraryView list-only behavior.
"""

import os
from datetime import datetime
from unittest.mock import MagicMock, Mock

import pytest
from PySide6.QtWidgets import QApplication

from domain.history import PlayHistory
from domain.track import Track, TrackSource
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
        Track(id=2, path="/music/two.mp3", title="Two", artist="Artist 2", source=TrackSource.QQ),
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

    engine = MagicMock()
    engine.current_track_changed = MagicMock()
    engine.state_changed = MagicMock()
    engine.state = None

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
